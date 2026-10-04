"""
Agent 4 HTTP surface: /decision/* routes.

Caller-supplies-payloads design (same precedent as Agent 3's plan-purchases
adapter): the orchestrator/frontend posts the cached Agent 1 output, the
Agent 2 retrieval responses and the Agent 3 budget response. Agent 4 makes no outbound calls to the other services and reads no shared
database; the only thing it persists is the hash-keyed decision audit log.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_tenant_access, get_current_principal
from app.core.security import scrub_pii
from app.schemas.agent4_extensions import (
    DecisionRequestExtended,
    DecisionResponseExtended,
)
from app.services import audit_service, decision_extras
from app.services.decision_service import get_decision_service
from shared.schemas.agent4_schemas import (
    AlternativesResponse,
    DecisionAnalysisResponse,
    DecisionRequest,
)

logger = logging.getLogger("decision_routes")

decision_router = APIRouter(prefix="/decision", tags=["Decision"])


def _check_input(request: DecisionRequest) -> None:
    """An unresolved clarification upstream means the decision would guess."""
    a1 = request.agent1_output
    req = a1.outfit_requirements
    if req.clarification_needed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=scrub_pii(req.clarification_message or "Please clarify the request first."),
        )


@decision_router.post("/recommend", response_model=DecisionResponseExtended)
def recommend(
    request: DecisionRequestExtended,
    llm_polish: bool = Query(False, description="Polish the explanation with Gemini; the decision is unchanged."),
    principal: dict = Depends(get_current_principal),
) -> DecisionResponseExtended:
    """Decide the final outfit from validated upstream payloads."""
    enforce_tenant_access(principal, request.user_id)
    _check_input(request)

    service = get_decision_service()
    response, evaluated = service.decide(request)
    template_explanation = response.explanation

    if llm_polish and response.selected_combination_id:
        chosen = next(
            (e for e in evaluated if e.option.combination_id == response.selected_combination_id),
            None,
        )
        if chosen is not None:
            from app.services.llm_explanation_service import get_llm_explanation_service

            polished = get_llm_explanation_service().generate_explanation(
                request=request,
                chosen=chosen,
                alternatives=[e for e in evaluated if e is not chosen],
                issues=response.validation_issues,
            )
            response.explanation = polished

    extended = decision_extras.decorate(
        request,
        response,
        evaluated,
        service=service,
        reoptimization_round=request.reoptimization_round,
        template_explanation=template_explanation,
    )
    extended.decision_id = audit_service.record(request, extended)
    return extended


@decision_router.post("/analyze", response_model=DecisionAnalysisResponse)
def analyze(
    request: DecisionRequest,
    principal: dict = Depends(get_current_principal),
) -> DecisionAnalysisResponse:
    """Diagnostic view: validation issues, per-candidate metrics, rejections."""
    enforce_tenant_access(principal, request.user_id)
    _check_input(request)
    return get_decision_service().analyze(request)


@decision_router.post("/alternatives", response_model=AlternativesResponse)
def alternatives(
    request: DecisionRequest,
    principal: dict = Depends(get_current_principal),
) -> AlternativesResponse:
    """Runner-up outfits with the reason each lost to the chosen one."""
    enforce_tenant_access(principal, request.user_id)
    _check_input(request)
    return get_decision_service().alternatives(request)


@decision_router.get("/health")
def decision_health() -> dict:
    return {"status": "ok", "service": "agent4_decision"}
