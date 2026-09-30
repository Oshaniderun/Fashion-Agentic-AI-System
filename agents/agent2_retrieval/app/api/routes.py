"""
FastAPI route definitions for Agent 2 (Fashion Information Retrieval).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from shared.schemas.agent2_schemas import RetrievalRequest, RetrievalResponse
from app.schemas.product import Product as ProductSchema
from app.repositories.product_repository import ProductRepository
from app.api.dependencies import get_db, require_auth
from app.decision_logic import resolve_retrieval
from app.core.config import get_settings
from app.services import history_service
from app.services.retrieval_service import get_retrieval_service

from app.core.security import sanitize_input_text

router = APIRouter()
settings = get_settings()

@router.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "agent2_retrieval",
        "version": settings.VERSION
    }

@router.post(
    "/retrieve-products",
    response_model=RetrievalResponse,
    tags=["Retrieval"],
    summary="Retrieve and rank fashion products using hybrid search & relaxation ladder"
)
@router.post(
    "/api/v1/retrieval/search",
    response_model=RetrievalResponse,
    tags=["Retrieval"],
    include_in_schema=False
)
@router.post(
    "/api/v1/search",
    response_model=RetrievalResponse,
    tags=["Retrieval"],
    summary="Retrieve and rank fashion products (API v1 alias)"
)
def retrieve_products(
    request: RetrievalRequest,
    auth: dict = Depends(require_auth),
    db: Session = Depends(get_db),
) -> RetrievalResponse:
    # Security checks on boundaries
    if request.top_k > 20 or request.top_k < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="top_k exceeds the allowed limit (must be between 1 and 20)."
        )
    if request.max_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_price must be greater than zero."
        )
    if request.query_text and len(request.query_text) > 2000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="query_text exceeds the maximum allowed character limit (2000)."
        )
    if request.excluded_product_ids:
        if len(request.excluded_product_ids) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="excluded_product_ids exceeds the maximum allowed limit of 100 items."
            )
        if any(len(pid) > 100 for pid in request.excluded_product_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each excluded product ID must not exceed 100 characters."
            )

    # Boundary input sanitization: strip non-printable ASCII control characters
    if request.query_text:
        request.query_text = sanitize_input_text(request.query_text, max_len=2000)
    if request.preferred_colour:
        request.preferred_colour = sanitize_input_text(request.preferred_colour, max_len=100)
    if request.style:
        request.style = sanitize_input_text(request.style, max_len=100)
    if request.occasion:
        request.occasion = sanitize_input_text(request.occasion, max_len=100)
    if request.excluded_product_ids:
        request.excluded_product_ids = [
            sanitize_input_text(pid, max_len=100) for pid in request.excluded_product_ids if pid
        ]

    response = resolve_retrieval(request)
    history_service.record_search(db, auth, request, response, source="search")
    return response

@router.get(
    "/api/v1/products/{product_id}",
    response_model=ProductSchema,
    tags=["Products"],
    summary="Get single product by ID"
)
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth)
):
    repo = ProductRepository(db)
    prod = repo.get(product_id)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found."
        )
    return prod


# ---------------------------------------------------------------------------
# Search history (user-scoped)
# ---------------------------------------------------------------------------

def _require_user(auth: dict) -> str:
    user_id = history_service.user_id_from_auth(auth)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Search history is only available to authenticated users.",
        )
    return user_id


HISTORY_PRODUCT_FIELDS = (
    "product_id", "product_name", "brand", "category", "price", "currency",
    "colour", "style", "store", "image_url", "product_url", "availability",
)


def _history_products(product_ids: List[str]) -> List[dict]:
    catalogue = get_retrieval_service().products
    out = []
    for pid in product_ids:
        prod = catalogue.get(pid)
        if prod:
            out.append({k: prod.get(k) for k in HISTORY_PRODUCT_FIELDS})
    return out


@router.get(
    "/api/v1/history",
    tags=["History"],
    summary="List your past searches (newest first)",
)
def list_search_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    user_id = _require_user(auth)
    return {"entries": history_service.list_history(db, user_id, limit)}


@router.get(
    "/api/v1/history/{history_id}",
    tags=["History"],
    summary="One search with its retrieved products resolved from the catalogue",
)
def get_search_history_entry(
    history_id: int,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    user_id = _require_user(auth)
    entry = history_service.get_history_entry(db, user_id, history_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found.")
    entry["products"] = _history_products(entry.pop("product_ids", []))
    return entry


@router.delete(
    "/api/v1/history",
    tags=["History"],
    summary="Delete all your search history",
)
def clear_search_history(
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    user_id = _require_user(auth)
    return {"deleted": history_service.clear_history(db, user_id)}


@router.delete(
    "/api/v1/history/{history_id}",
    tags=["History"],
    summary="Delete one search history entry",
)
def delete_search_history_entry(
    history_id: int,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    user_id = _require_user(auth)
    if not history_service.delete_history_entry(db, user_id, history_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found.")
    return {"deleted": history_id}
