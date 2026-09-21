"""
Inter-Agent Communication Endpoints.
Provides stable JSON API contracts for the Orchestrator, Agent 2, Agent 3, and Agent 4.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.user import User
from app.services.nlp.requirement_extractor import fashion_requirement_service
from app.services.wardrobe.inventory import wardrobe_service
from app.services.wardrobe.matching import wardrobe_matcher
from app.services.outfit_requirements import outfit_requirement_engine
from app.services.missing_items import missing_item_detector
from app.services.compatibility import compatibility_engine
from app.utils.request_id import generate_request_id
from shared.schemas.agent1_schemas import (
    Agent1AnalysisRequest,
    Agent1OutputContract,
    ConfidenceMetrics
)
from app.core.config import settings
from app.core.security import decode_access_token

router = APIRouter(tags=["Agent Inter-Service"])


def _resolve_user_for_agent_call(
    req: Agent1AnalysisRequest,
    db: Session,
    authorization: Optional[str],
) -> User:
    """
    Resolve the target user for inter-agent analysis.
    Accepts either:
      - Authorization: Bearer <user JWT> (optional user_id must match token subject), or
      - Authorization: Bearer <AGENT_SERVICE_TOKEN> plus req.user_id
    Never falls back to a demo account.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token. Use a user JWT or the agent service token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = authorization.split(" ", 1)[1].strip()

    # Inter-agent path: shared service token + explicit user_id
    if raw_token == settings.AGENT_SERVICE_TOKEN:
        if not req.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id is required when calling with the agent service token.",
            )
        user = db.query(User).filter(User.id == req.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User id {req.user_id} was not found.",
            )
        return user

    # User JWT path
    payload = decode_access_token(raw_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        token_user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if req.user_id is not None and int(req.user_id) != token_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id does not match the authenticated user.",
        )

    user = db.query(User).filter(User.id == token_user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/api/agent/analyze", response_model=Agent1OutputContract)
def analyze_for_downstream_agents(
    req: Agent1AnalysisRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """
    Primary Inter-Agent Endpoint:
    Processes natural-language query and optional overrides, evaluates wardrobe,
    detects missing categories, and returns the strict Agent 1 Output Contract for Agent 2/3/4.
    """
    request_id = req.request_id or generate_request_id()
    user = _resolve_user_for_agent_call(req, db, authorization)

    # 2. Extract NLP requirements
    extracted_reqs, nlp_conf, _ = fashion_requirement_service.process_request(req.query_text)

    # Apply explicit overrides if provided
    if req.occasion:
        extracted_reqs.occasion = req.occasion.lower()
    if req.style:
        if req.style.lower() not in extracted_reqs.style:
            extracted_reqs.style.append(req.style.lower())
    if req.colour_preference:
        if req.colour_preference.lower() not in extracted_reqs.colour_preferences:
            extracted_reqs.colour_preferences.append(req.colour_preference.lower())
    if req.budget is not None and req.budget > 0:
        extracted_reqs.budget = req.budget

    # 3. Retrieve user wardrobe
    orm_items = wardrobe_service.get_user_items(db=db, user_id=user.id)
    summary_wardrobe = wardrobe_service.to_summary_items(orm_items)

    # 4. Determine outfit requirements
    required_cats, optional_cats = outfit_requirement_engine.determine_requirements(extracted_reqs)

    # 5. Missing items & Agent 2 search handoff
    outfit_reqs, search_handoff, agent2_handoff = missing_item_detector.analyze_missing(
        required_categories=required_cats,
        optional_categories=optional_cats,
        owned_items=summary_wardrobe,
        user_requirements=extracted_reqs,
        request_id=request_id,
    )

    # 6. Compatible items & compatibility reasoning
    compatible_items = wardrobe_matcher.select_compatible_items(
        wardrobe=summary_wardrobe,
        requirements=extracted_reqs,
        required_categories=required_cats
    )
    compat_details = compatibility_engine.evaluate_outfit_combination(
        candidate_items=compatible_items,
        requirements=extracted_reqs
    )

    # 7. Confidence
    vision_conf = (
        round(sum(it.confidence for it in summary_wardrobe) / len(summary_wardrobe), 2)
        if summary_wardrobe else 0.90
    )
    overall_conf = round(float((nlp_conf * 0.5) + (vision_conf * 0.3) + (compat_details.score * 0.2)), 2)

    confidence_metrics = ConfidenceMetrics(
        overall=overall_conf,
        vision=vision_conf,
        nlp=nlp_conf
    )

    return Agent1OutputContract(
        request_id=request_id,
        user_requirements=extracted_reqs,
        wardrobe=summary_wardrobe,
        outfit_requirements=outfit_reqs,
        compatible_items=[it.wardrobe_id for it in compatible_items],
        compatibility=compat_details,
        confidence=confidence_metrics,
        search_requirements=search_handoff,
        agent2_handoff=agent2_handoff,
    )


@router.get("/api/agent/schema")
def get_agent_schema():
    """
    Returns the JSON schemas for the input and output contracts of Agent 1.
    Allows developers of Agent 2, 3, and 4 to programmatically inspect the API shape.
    """
    return {
        "agent": "Agent 1 - Style & Wardrobe Intelligence",
        "version": settings.VERSION,
        "input_contract_schema": Agent1AnalysisRequest.model_json_schema(),
        "output_contract_schema": Agent1OutputContract.model_json_schema()
    }


@router.get("/api/agent/status")
def get_agent_status():
    """
    Returns service health and registered capabilities for orchestrator discovery.
    """
    return {
        "agent": "Agent 1 - Style & Wardrobe Intelligence",
        "status": "healthy",
        "version": settings.VERSION,
        "backend": settings.APP_ENV,
        "vision_backend": settings.VISION_MODEL_BACKEND,
        "llm_provider": settings.LLM_PROVIDER,
        "seed_demo_data": settings.SEED_DEMO_DATA,
        "capabilities": [
            "image_analysis",
            "nlp_requirement_extraction",
            "wardrobe_analysis",
            "missing_item_detection",
            "compatibility_analysis",
            "prompt_injection_guard"
        ]
    }


@router.get("/api/health")
def health_check():
    """Liveness check endpoint."""
    return {"status": "ok", "service": "agent1_wardrobe", "version": settings.VERSION}
