"""
FastAPI route definitions for Agent 2 (Fashion Information Retrieval).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from shared.schemas.agent2_schemas import RetrievalRequest, RetrievalResponse
from app.schemas.product import Product as ProductSchema
from app.repositories.product_repository import ProductRepository
from app.api.dependencies import get_db, require_auth
from app.decision_logic import resolve_retrieval
from app.core.config import get_settings

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
    auth: dict = Depends(require_auth)
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

    # Boundary input sanitization: strip non-printable ASCII control characters
    if request.query_text:
        request.query_text = sanitize_input_text(request.query_text, max_len=2000)
    if request.preferred_colour:
        request.preferred_colour = sanitize_input_text(request.preferred_colour, max_len=100)
    if request.style:
        request.style = sanitize_input_text(request.style, max_len=100)
    if request.occasion:
        request.occasion = sanitize_input_text(request.occasion, max_len=100)

    response = resolve_retrieval(request)
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
