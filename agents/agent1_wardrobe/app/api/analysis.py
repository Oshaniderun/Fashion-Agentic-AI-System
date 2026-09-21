"""
Fashion Request Processing and Outfit Analysis Endpoints.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.user import User
from app.api.auth import get_current_user
from app.schemas.analysis import FashionRequestInput, FashionAnalysisResponse
from app.services.nlp.requirement_extractor import fashion_requirement_service
from app.services.wardrobe.inventory import wardrobe_service
from app.services.wardrobe.matching import wardrobe_matcher
from app.services.outfit_requirements import outfit_requirement_engine
from app.services.missing_items import missing_item_detector
from app.services.compatibility import compatibility_engine
from app.utils.request_id import generate_request_id
from shared.schemas.agent1_schemas import (
    Agent1OutputContract,
    ConfidenceMetrics,
    WardrobeSummaryItem
)
from app.core.logging import logger

router = APIRouter(prefix="/api/analyze", tags=["Fashion Analysis"])

# In-memory session store for recent analysis requests (correlation by request_id)
ANALYSIS_HISTORY_CACHE: Dict[str, FashionAnalysisResponse] = {}


@router.post("/request", response_model=FashionAnalysisResponse)
def analyze_fashion_request(
    req: FashionRequestInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Primary User Flow:
    Analyzes natural-language request, extracts requirements, checks owned wardrobe,
    determines missing categories, evaluates compatibility, and builds Agent 1 Output Contract.
    """
    request_id = generate_request_id()
    start_time = datetime.now(timezone.utc)

    # 1. NLP Processing & Prompt Security Guard
    extracted_reqs, nlp_conf, threat_report = fashion_requirement_service.process_request(req.query_text)

    # Apply any explicit user overrides from form fields
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

    # 2. Retrieve user's owned wardrobe items
    orm_items = wardrobe_service.get_user_items(db=db, user_id=user.id)
    summary_wardrobe = wardrobe_service.to_summary_items(orm_items)

    # 3. Outfit Requirement Analysis (e.g. occasion -> required categories)
    required_cats, optional_cats = outfit_requirement_engine.determine_requirements(extracted_reqs)

    # 4. Missing Item Detection & Agent 2 Handoff formatting
    outfit_reqs, search_handoff = missing_item_detector.analyze_missing(
        required_categories=required_cats,
        optional_categories=optional_cats,
        owned_items=summary_wardrobe,
        user_requirements=extracted_reqs
    )

    # 5. Select compatible wardrobe items
    compatible_items = wardrobe_matcher.select_compatible_items(
        wardrobe=summary_wardrobe,
        requirements=extracted_reqs,
        required_categories=required_cats
    )

    # 6. Compatibility reasoning
    compat_details = compatibility_engine.evaluate_outfit_combination(
        candidate_items=compatible_items,
        requirements=extracted_reqs
    )

    # 7. Confidence estimation
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

    # 8. Strict Agent 1 Output Contract for future Agent 2/3/4 consumption
    contract = Agent1OutputContract(
        request_id=request_id,
        user_requirements=extracted_reqs,
        wardrobe=summary_wardrobe,
        outfit_requirements=outfit_reqs,
        compatible_items=[it.wardrobe_id for it in compatible_items],
        compatibility=compat_details,
        confidence=confidence_metrics,
        search_requirements=search_handoff
    )

    response = FashionAnalysisResponse(
        request_id=request_id,
        timestamp=start_time,
        input_text=req.query_text,
        user_requirements=extracted_reqs,
        available_wardrobe=summary_wardrobe,
        outfit_requirements=outfit_reqs,
        compatible_items=compatible_items,
        compatibility=compat_details,
        confidence=confidence_metrics,
        search_requirements=search_handoff,
        raw_agent1_contract=contract
    )

    ANALYSIS_HISTORY_CACHE[request_id] = response
    logger.info(
        f"Processed analysis {request_id} for user {user.id}",
        extra={"request_id": request_id, "endpoint": "/api/analyze/request", "user_id": user.id}
    )

    return response


@router.get("/recent/latest", response_model=Optional[FashionAnalysisResponse])
def get_latest_analysis():
    """Retrieves the most recent analysis result for dashboard overview."""
    if not ANALYSIS_HISTORY_CACHE:
        return None
    latest_id = list(ANALYSIS_HISTORY_CACHE.keys())[-1]
    return ANALYSIS_HISTORY_CACHE[latest_id]


@router.get("/{request_id}", response_model=FashionAnalysisResponse)
def get_analysis_by_id(request_id: str):
    """Retrieves a previously computed analysis by its unique request ID."""
    if request_id not in ANALYSIS_HISTORY_CACHE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with request ID '{request_id}' was not found in active session cache."
        )
    return ANALYSIS_HISTORY_CACHE[request_id]
