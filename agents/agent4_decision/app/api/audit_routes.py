"""
Feature 5 — audit-log read endpoints.

Service-to-service only: these rows describe every decision the model made, so
they are restricted to the shared AGENT_SERVICE_TOKEN principal rather than any
user JWT. Nothing sensitive is returned — hashes, ids and scores only.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dependencies import get_current_principal
from app.core.config import get_settings
from app.schemas.agent4_extensions import AuditEntry, AuditPage
from app.services import audit_service

settings = get_settings()

audit_router = APIRouter(prefix="/audit", tags=["Audit"])

_DECISION_ID = Path(..., pattern=r"^dec_[0-9a-f]{16}$", description="decision_id from a /decision/recommend response.")


def require_service_principal(principal: dict = Depends(get_current_principal)) -> dict:
    if not principal.get("is_service"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The decision audit log is only available to service callers.",
        )
    return principal


@audit_router.get("", response_model=AuditPage)
@audit_router.get("/", response_model=AuditPage)
def list_decisions(
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: Optional[int] = Query(
        None, ge=1, le=settings.AUDIT_MAX_PAGE_SIZE, description="Rows per page."
    ),
    principal: dict = Depends(require_service_principal),
) -> AuditPage:
    """Most recent decisions first, paginated."""
    size = page_size or settings.AUDIT_DEFAULT_PAGE_SIZE
    try:
        data = audit_service.list_entries(limit=size, offset=(page - 1) * size)
    except audit_service.AuditUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The decision audit log is temporarily unavailable.",
        )
    return AuditPage(
        total=data["total"],
        page=page,
        page_size=size,
        items=[AuditEntry(**item) for item in data["items"]],
    )


@audit_router.get("/{decision_id}", response_model=AuditEntry)
def get_decision(
    decision_id: str = _DECISION_ID,
    principal: dict = Depends(require_service_principal),
) -> AuditEntry:
    """One recorded decision, by the id returned on the response."""
    row = audit_service.fetch(decision_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No audit entry for that decision."
        )
    return AuditEntry(**row)
