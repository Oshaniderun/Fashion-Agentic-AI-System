"""
Wardrobe Inventory Database Operations Service.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.wardrobe import WardrobeItem
from app.schemas.wardrobe import WardrobeItemCreate, WardrobeItemUpdate
from shared.schemas.agent1_schemas import WardrobeSummaryItem


class WardrobeInventoryService:
    """Handles DB operations for wardrobe items."""

    def get_user_items(
        self,
        db: Session,
        user_id: int,
        category: Optional[str] = None,
        colour: Optional[str] = None,
        style: Optional[str] = None,
        pattern: Optional[str] = None
    ) -> List[WardrobeItem]:
        """Queries wardrobe items for a given user with optional attribute filtering."""
        query = db.query(WardrobeItem).filter(WardrobeItem.user_id == user_id)
        if category:
            query = query.filter(WardrobeItem.category == category.lower())
        if colour:
            query = query.filter(WardrobeItem.colour == colour.lower())
        if style:
            query = query.filter(WardrobeItem.style == style.lower())
        if pattern:
            query = query.filter(WardrobeItem.pattern == pattern.lower())
        return query.order_by(desc(WardrobeItem.created_at)).all()

    def get_item_by_id(self, db: Session, item_id: int, user_id: int) -> Optional[WardrobeItem]:
        """Retrieves a single wardrobe item ensuring user ownership."""
        return db.query(WardrobeItem).filter(
            WardrobeItem.id == item_id,
            WardrobeItem.user_id == user_id
        ).first()

    def create_item(self, db: Session, user_id: int, item_in: WardrobeItemCreate) -> WardrobeItem:
        """Creates and stores a confirmed wardrobe item."""
        # Generate next code like W001, W002
        count = db.query(WardrobeItem).filter(WardrobeItem.user_id == user_id).count()
        code = f"W{count + 1:03d}"

        db_item = WardrobeItem(
            wardrobe_code=code,
            user_id=user_id,
            image_path=item_in.image_path,
            category=item_in.category.lower(),
            type=item_in.type.lower(),
            colour=item_in.colour.lower(),
            secondary_colour=item_in.secondary_colour.lower() if item_in.secondary_colour else None,
            pattern=item_in.pattern.lower(),
            style=item_in.style.lower(),
            sleeve_type=item_in.sleeve_type,
            formality=item_in.formality,
            material=item_in.material,
            confidence=item_in.confidence,
            attributes_confirmed=item_in.attributes_confirmed
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

    def update_item(
        self,
        db: Session,
        item: WardrobeItem,
        item_update: WardrobeItemUpdate
    ) -> WardrobeItem:
        """Updates user-confirmed attributes on a wardrobe item."""
        update_data = item_update.model_dump(exclude_unset=True)
        for key, val in update_data.items():
            if val is not None:
                if isinstance(val, str):
                    setattr(item, key, val.lower())
                else:
                    setattr(item, key, val)
        item.attributes_confirmed = True
        db.commit()
        db.refresh(item)
        return item

    def delete_item(self, db: Session, item: WardrobeItem) -> bool:
        """Deletes a wardrobe item."""
        db.delete(item)
        db.commit()
        return True

    def to_summary_items(self, items: List[WardrobeItem]) -> List[WardrobeSummaryItem]:
        """Converts ORM items to shared WardrobeSummaryItem contracts."""
        return [
            WardrobeSummaryItem(
                wardrobe_id=item.wardrobe_code,
                category=item.category,
                type=item.type,
                colour=item.colour,
                secondary_colour=item.secondary_colour,
                pattern=item.pattern,
                style=item.style,
                sleeve_type=item.sleeve_type,
                formality=item.formality,
                material=item.material,
                image_url=item.image_path,
                confidence=item.confidence
            )
            for item in items
        ]


wardrobe_service = WardrobeInventoryService()
