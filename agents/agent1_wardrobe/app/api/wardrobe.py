"""
Wardrobe and Clothing Management Endpoints.
Supports secure image upload, computer vision analysis, user attribute confirmation, and CRUD operations.
"""

import uuid
from typing import List, Optional
from pathlib import Path
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.user import User
from app.models.wardrobe import WardrobeItem
from app.schemas.wardrobe import (
    ClothingAttributesDetected,
    ImageAnalysisDraft,
    WardrobeItemCreate,
    WardrobeItemUpdate,
    WardrobeItemResponse
)
from app.api.auth import get_current_user
from app.utils.image_validation import validate_and_save_image
from app.services.image_analysis.analyzer import master_image_analyzer
from app.services.wardrobe.inventory import wardrobe_service
from app.core.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/api/wardrobe", tags=["Wardrobe Management"])


@router.post("/upload", response_model=ImageAnalysisDraft)
def upload_and_analyze_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user)
):
    """
    Step 1 of Wardrobe Addition:
    Uploads clothing photo, verifies binary safety, runs computer vision analysis,
    and returns detected attributes in a draft state for user review and editing.
    """
    # 1. Validate file and save securely
    rel_path, safe_filename = validate_and_save_image(file)
    full_disk_path = Path(settings.UPLOAD_DIR) / safe_filename

    # 2. Run vision analysis
    try:
        with Image.open(full_disk_path) as img:
            detected_attrs = master_image_analyzer.analyze_image(img)
    except Exception as e:
        logger.error(f"Failed to analyze uploaded image: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "IMAGE_ANALYSIS_FAILED",
                "message": "The clothing image could not be analyzed. Please ensure good lighting and clear view."
            }
        )

    draft_id = f"draft_{uuid.uuid4().hex[:8]}"
    return ImageAnalysisDraft(
        draft_id=draft_id,
        image_url=rel_path,
        detected_attributes=detected_attrs,
        is_confirmed=False
    )


@router.post("", response_model=WardrobeItemResponse, status_code=status.HTTP_201_CREATED)
def create_wardrobe_item(
    item_in: WardrobeItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Step 2 of Wardrobe Addition:
    Saves user-confirmed clothing item with final attributes into user's wardrobe inventory.
    """
    db_item = wardrobe_service.create_item(db=db, user_id=user.id, item_in=item_in)
    return WardrobeItemResponse(
        id=db_item.id,
        wardrobe_code=db_item.wardrobe_code,
        user_id=db_item.user_id,
        image_url=db_item.image_path,
        category=db_item.category,
        type=db_item.type,
        colour=db_item.colour,
        secondary_colour=db_item.secondary_colour,
        pattern=db_item.pattern,
        style=db_item.style,
        sleeve_type=db_item.sleeve_type,
        formality=db_item.formality,
        material=db_item.material,
        confidence=db_item.confidence,
        attributes_confirmed=db_item.attributes_confirmed,
        created_at=db_item.created_at,
        updated_at=db_item.updated_at
    )


@router.get("", response_model=List[WardrobeItemResponse])
def list_wardrobe_items(
    category: Optional[str] = Query(None, description="Filter by category (top, bottom, footwear, etc.)"),
    colour: Optional[str] = Query(None, description="Filter by color"),
    style: Optional[str] = Query(None, description="Filter by style"),
    pattern: Optional[str] = Query(None, description="Filter by pattern"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Retrieves all wardrobe items belonging to the authenticated user with optional filtering."""
    items = wardrobe_service.get_user_items(
        db=db,
        user_id=user.id,
        category=category,
        colour=colour,
        style=style,
        pattern=pattern
    )
    return [
        WardrobeItemResponse(
            id=item.id,
            wardrobe_code=item.wardrobe_code,
            user_id=item.user_id,
            image_url=item.image_path,
            category=item.category,
            type=item.type,
            colour=item.colour,
            secondary_colour=item.secondary_colour,
            pattern=item.pattern,
            style=item.style,
            sleeve_type=item.sleeve_type,
            formality=item.formality,
            material=item.material,
            confidence=item.confidence,
            attributes_confirmed=item.attributes_confirmed,
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        for item in items
    ]


@router.get("/{item_id}", response_model=WardrobeItemResponse)
def get_wardrobe_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Retrieves a specific wardrobe item by ID."""
    item = wardrobe_service.get_item_by_id(db=db, item_id=item_id, user_id=user.id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wardrobe item not found."
        )
    return WardrobeItemResponse(
        id=item.id,
        wardrobe_code=item.wardrobe_code,
        user_id=item.user_id,
        image_url=item.image_path,
        category=item.category,
        type=item.type,
        colour=item.colour,
        secondary_colour=item.secondary_colour,
        pattern=item.pattern,
        style=item.style,
        sleeve_type=item.sleeve_type,
        formality=item.formality,
        material=item.material,
        confidence=item.confidence,
        attributes_confirmed=item.attributes_confirmed,
        created_at=item.created_at,
        updated_at=item.updated_at
    )


@router.put("/{item_id}", response_model=WardrobeItemResponse)
def update_wardrobe_item(
    item_id: int,
    item_update: WardrobeItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Updates user-confirmed attributes on a wardrobe item."""
    item = wardrobe_service.get_item_by_id(db=db, item_id=item_id, user_id=user.id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wardrobe item not found."
        )
    updated = wardrobe_service.update_item(db=db, item=item, item_update=item_update)
    return WardrobeItemResponse(
        id=updated.id,
        wardrobe_code=updated.wardrobe_code,
        user_id=updated.user_id,
        image_url=updated.image_path,
        category=updated.category,
        type=updated.type,
        colour=updated.colour,
        secondary_colour=updated.secondary_colour,
        pattern=updated.pattern,
        style=updated.style,
        sleeve_type=updated.sleeve_type,
        formality=updated.formality,
        material=updated.material,
        confidence=updated.confidence,
        attributes_confirmed=updated.attributes_confirmed,
        created_at=updated.created_at,
        updated_at=updated.updated_at
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wardrobe_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Deletes a wardrobe item from inventory."""
    item = wardrobe_service.get_item_by_id(db=db, item_id=item_id, user_id=user.id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wardrobe item not found."
        )
    wardrobe_service.delete_item(db=db, item=item)
    return None
