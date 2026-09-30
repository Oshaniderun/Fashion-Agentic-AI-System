"""
Operational endpoints for Agent 2:

- GET  /api/v1/status                 service inspection (catalogue/index counts, embedding model)
- POST /api/v1/search/agent1-handoff  adapter from Agent 1's Agent2HandoffPayload to
  Agent 2's scalar RetrievalRequest contract.

Why the adapter exists: Agent 1 hands off LIST-shaped requirements
(categories[], colour_preferences[], style[], types[]) with an optional budget,
while RetrievalRequest takes ONE required_category and a REQUIRED max_price.
This route fans out one retrieval per missing category and resolves the
budget/shape mismatches without touching the retrieval or ranking logic.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.constants import ProductCategory
from shared.schemas.agent1_schemas import Agent2HandoffPayload
from shared.schemas.agent2_schemas import RetrievalRequest, RetrievalResponse
from app.api.dependencies import SessionLocal, get_db, require_auth
from app.decision_logic import resolve_retrieval
from app.services import history_service
from app.services.retrieval_service import get_retrieval_service

router = APIRouter()

CATALOGUE_CURRENCY = "USD"  # actual currency of the Amazon_Fashion_2023 catalogue


class CategoryRetrieval(BaseModel):
    category: str
    request: Optional[RetrievalRequest] = None
    response: Optional[RetrievalResponse] = None
    error: Optional[str] = None


class HandoffRetrievalResponse(BaseModel):
    request_id: str
    price_ceiling_used: float
    price_currency: str = CATALOGUE_CURRENCY
    warnings: List[str] = Field(default_factory=list)
    retrievals: List[CategoryRetrieval] = Field(default_factory=list)


_price_ceiling_cache: Optional[float] = None


def _catalogue_ceiling() -> float:
    """Highest catalogue price + 1: used when Agent 1 gave no budget, so nothing
    is silently filtered out. The concrete value is reported to the caller."""
    global _price_ceiling_cache
    if _price_ceiling_cache is None:
        svc = get_retrieval_service()
        numeric = [float(p["price"]) for p in svc.products.values() if p.get("price") is not None]
        _price_ceiling_cache = max(numeric) + 1 if numeric else 1_000_000.0
    return _price_ceiling_cache


def _dedupe_join(parts: List[str]) -> str:
    seen = []
    for p in parts:
        if p and p.lower() not in {s.lower() for s in seen}:
            seen.append(p)
    return " ".join(seen)


def _colour_for_category(payload: Agent2HandoffPayload, cat: str) -> Optional[str]:
    """Item-specific colour from Agent 1's identified_items (unambiguous pairing).
    Only falls back to a general preference when a single colour was stated."""
    for item in payload.user_requirements.identified_items:
        if (item.category or "").lower() == cat and item.colour:
            return item.colour
    prefs = [c for c in payload.search_requirements.colour_preferences if c]
    if len(set(p.lower() for p in prefs)) == 1:
        return prefs[0]
    return None


def _style_for_request(payload: Agent2HandoffPayload) -> Optional[str]:
    """style is a HARD filter in RetrievalRequest, so it is only set when exactly
    one style was requested; multiple styles stay as query text for ranking."""
    styles = [s for s in (payload.search_requirements.style or payload.user_requirements.style) if s]
    if len(set(s.lower() for s in styles)) == 1:
        return styles[0]
    return None


def _type_for_category(payload: Agent2HandoffPayload, cat: str) -> Optional[str]:
    for item in payload.user_requirements.identified_items:
        if (item.category or "").lower() == cat and item.type:
            return item.type
    types = payload.search_requirements.types
    if len(types) == 1:
        return types[0]
    return None


@router.post(
    "/api/v1/search/agent1-handoff",
    response_model=HandoffRetrievalResponse,
    tags=["Retrieval"],
    summary="Run hybrid retrieval directly from an Agent 1 handoff payload (one search per missing category)",
)
def search_from_agent1_handoff(
    payload: Agent2HandoffPayload,
    auth: dict = Depends(require_auth),
    db: Session = Depends(get_db),
) -> HandoffRetrievalResponse:
    sr = payload.search_requirements
    categories = [c for c in (sr.categories or sr.missing_categories or payload.wardrobe_status.missing_categories) if c]

    warnings: List[str] = []
    if sr.maximum_price is not None:
        ceiling = float(sr.maximum_price)
        # Budget-currency note removed 2026-09-25 at user request (budgets are USD by convention):
        # warnings.append(
        #     "Budget is interpreted as USD, matching the catalogue currency "
        #     "(team convention from 2026-09-25: users state budgets in USD)."
        # )
    else:
        ceiling = _catalogue_ceiling()
        warnings.append(
            "No budget in the handoff; using the full-catalogue price ceiling "
            f"({ceiling:g} {CATALOGUE_CURRENCY}) so nothing is filtered by price."
        )

    if not categories:
        warnings.append("Agent 1 reported no missing categories — nothing to retrieve.")
        return HandoffRetrievalResponse(
            request_id=payload.request_id, price_ceiling_used=ceiling,
            warnings=warnings, retrievals=[],
        )

    retrievals: List[CategoryRetrieval] = []
    for cat in categories:
        cat_key = cat.lower().strip()
        try:
            pc = ProductCategory(cat_key)
        except ValueError:
            retrievals.append(CategoryRetrieval(
                category=cat, error=f"'{cat}' is not a valid ProductCategory; skipped."))
            continue

        colour = _colour_for_category(payload, cat_key)
        style = _style_for_request(payload)
        garment_type = _type_for_category(payload, cat_key)
        query_text = _dedupe_join(
            [garment_type or cat_key]
            + ([colour] if colour else [])
            + list(payload.search_requirements.style or [])
            + ([sr.occasion] if sr.occasion else [])
        )

        req = RetrievalRequest(
            request_id=f"{payload.request_id}:{cat_key}",
            required_category=pc,
            preferred_colour=colour,
            style=style,
            occasion=sr.occasion,
            query_text=query_text,
            max_price=ceiling,
            top_k=5,
        )
        resp = resolve_retrieval(req)
        history_service.record_search(db, auth, req, resp, source="agent1_handoff")
        retrievals.append(CategoryRetrieval(category=cat_key, request=req, response=resp))

    return HandoffRetrievalResponse(
        request_id=payload.request_id,
        price_ceiling_used=ceiling,
        warnings=warnings,
        retrievals=retrievals,
    )


@router.get(
    "/api/v1/status",
    tags=["Status"],
    summary="Agent 2 service status: catalogue, index and embedding inspection",
)
def service_status(auth: dict = Depends(require_auth)):
    def safe(fn):
        try:
            return fn()
        except Exception:
            return None

    db_product_count = safe(lambda: _db_product_count())

    svc_ok = safe(lambda: get_retrieval_service())
    svc = svc_ok
    return {
        "service": "agent2_retrieval",
        "database_connected": db_product_count is not None,
        "db_product_count": db_product_count,
        "catalogue_loaded": len(svc.products) if svc else 0,
        "bm25_index_loaded": bool(svc and svc.bm25_service.count() > 0),
        "bm25_document_count": safe(lambda: svc.bm25_service.get_count()) if svc else None,
        "chroma_connected": svc is not None,
        "chroma_using_memory_fallback": (
            type(svc.chroma_service.collection).__name__ == "InMemoryVectorStore" if svc else None
        ),
        "chroma_document_count": safe(lambda: svc.chroma_service.get_count()) if svc else None,
        "embedding_model": svc.embedding_service.model_name if svc else None,
        "embedding_model_loaded": bool(svc and svc.embedding_service.model is not None) if svc else None,
        "embedding_dimensions": safe(lambda: svc.embedding_service.get_embedding_dimension()) if svc else None,
        "price_currency": CATALOGUE_CURRENCY,
    }


def _db_product_count() -> int:
    db = SessionLocal()
    try:
        return int(db.execute(text("SELECT COUNT(*) FROM products")).scalar_one())
    finally:
        db.close()
