"""
Persistence helpers for fashion analysis results.
"""

from typing import Optional
from sqlalchemy.orm import Session

from app.models.analysis import AnalysisRecord
from app.schemas.analysis import FashionAnalysisResponse


def save_analysis(
    db: Session,
    user_id: int,
    response: FashionAnalysisResponse,
) -> AnalysisRecord:
    """Persist a completed analysis for the owning user."""
    record = AnalysisRecord(
        request_id=response.request_id,
        user_id=user_id,
        input_text=response.input_text,
        payload=response.model_dump(mode="json"),
        created_at=response.timestamp,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_analysis_for_user(
    db: Session,
    request_id: str,
    user_id: int,
) -> Optional[FashionAnalysisResponse]:
    """Load an analysis by request_id, scoped to the authenticated user."""
    record = (
        db.query(AnalysisRecord)
        .filter(
            AnalysisRecord.request_id == request_id,
            AnalysisRecord.user_id == user_id,
        )
        .first()
    )
    if not record:
        return None
    return FashionAnalysisResponse.model_validate(record.payload)


def get_latest_analysis_for_user(
    db: Session,
    user_id: int,
) -> Optional[FashionAnalysisResponse]:
    """Load the most recent analysis for a user."""
    record = (
        db.query(AnalysisRecord)
        .filter(AnalysisRecord.user_id == user_id)
        .order_by(AnalysisRecord.created_at.desc())
        .first()
    )
    if not record:
        return None
    return FashionAnalysisResponse.model_validate(record.payload)
