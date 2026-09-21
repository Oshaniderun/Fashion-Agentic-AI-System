"""
Database seeding with sample wardrobe items and default demo user.
Creates styled seed images with Pillow so the frontend renders visual clothing cards immediately.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wardrobe import WardrobeItem
from app.core.security import hash_password
from app.core.config import settings
from app.core.logging import logger

DEMO_USER_EMAIL = "demo@fashora.ai"
DEMO_USER_PASSWORD = "password123"


def create_styled_seed_image(filename: str, bg_color: tuple, text: str, subtitle: str) -> str:
    """Generates a stylish minimal garment card image for seed items."""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    
    if file_path.exists():
        return f"uploads/{filename}"
        
    width, height = 400, 400
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Draw soft inner frame
    draw.rectangle([(20, 20), (width - 20, height - 20)], outline=(255, 255, 255, 60), width=2)
    
    # Draw text label in center
    # Primary label
    draw.text((width // 2, height // 2 - 20), text, fill=(255, 255, 255), anchor="mm")
    # Subtitle
    draw.text((width // 2, height // 2 + 25), subtitle, fill=(200, 200, 200), anchor="mm")
    
    img.save(file_path, format="PNG")
    return f"uploads/{filename}"


def seed_database_if_empty(db: Session) -> User:
    """Seeds the demo user and standard test wardrobe items if not already present."""
    demo_user = db.query(User).filter(User.email == DEMO_USER_EMAIL).first()
    
    if not demo_user:
        demo_user = User(
            name="Demo Stylist",
            email=DEMO_USER_EMAIL,
            password_hash=hash_password(DEMO_USER_PASSWORD)
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
        logger.info(f"Created default demo user: {DEMO_USER_EMAIL}")
        
    # Check if wardrobe items exist for demo user
    existing_items = db.query(WardrobeItem).filter(WardrobeItem.user_id == demo_user.id).count()
    if existing_items == 0:
        seed_items = [
            {
                "wardrobe_code": "W001",
                "category": "top",
                "type": "blouse",
                "colour": "black",
                "secondary_colour": None,
                "pattern": "solid",
                "style": "smart_casual",
                "sleeve_type": "long_sleeve",
                "formality": 0.70,
                "material": "silk",
                "confidence": 0.92,
                "filename": "seed_w001_black_blouse.png",
                "bg_color": (26, 26, 30),
                "title": "Black Silk Blouse",
                "sub": "Top • Smart Casual"
            },
            {
                "wardrobe_code": "W002",
                "category": "bottom",
                "type": "jeans",
                "colour": "blue",
                "secondary_colour": None,
                "pattern": "solid",
                "style": "casual",
                "sleeve_type": None,
                "formality": 0.40,
                "material": "denim",
                "confidence": 0.95,
                "filename": "seed_w002_blue_jeans.png",
                "bg_color": (32, 50, 78),
                "title": "Blue Straight Jeans",
                "sub": "Bottom • Casual Denim"
            },
            {
                "wardrobe_code": "W003",
                "category": "shoes",
                "type": "loafers",
                "colour": "beige",
                "secondary_colour": "brown",
                "pattern": "solid",
                "style": "smart_casual",
                "sleeve_type": None,
                "formality": 0.65,
                "material": "leather",
                "confidence": 0.89,
                "filename": "seed_w003_beige_loafers.png",
                "bg_color": (75, 65, 55),
                "title": "Beige Suede Loafers",
                "sub": "Footwear • Smart Casual"
            },
            {
                "wardrobe_code": "W004",
                "category": "top",
                "type": "shirt",
                "colour": "white",
                "secondary_colour": None,
                "pattern": "solid",
                "style": "formal",
                "sleeve_type": "long_sleeve",
                "formality": 0.85,
                "material": "cotton",
                "confidence": 0.94,
                "filename": "seed_w004_white_shirt.png",
                "bg_color": (50, 50, 58),
                "title": "Classic White Shirt",
                "sub": "Top • Formal Oxford"
            },
            {
                "wardrobe_code": "W005",
                "category": "bottom",
                "type": "trousers",
                "colour": "black",
                "secondary_colour": None,
                "pattern": "solid",
                "style": "formal",
                "sleeve_type": None,
                "formality": 0.85,
                "material": "wool",
                "confidence": 0.93,
                "filename": "seed_w005_black_trousers.png",
                "bg_color": (20, 20, 24),
                "title": "Black Tailored Trousers",
                "sub": "Bottom • Formal Suit"
            },
        ]
        
        for item_data in seed_items:
            img_rel_path = create_styled_seed_image(
                item_data["filename"],
                item_data["bg_color"],
                item_data["title"],
                item_data["sub"]
            )
            
            w_item = WardrobeItem(
                wardrobe_code=item_data["wardrobe_code"],
                user_id=demo_user.id,
                image_path=img_rel_path,
                category=item_data["category"],
                type=item_data["type"],
                colour=item_data["colour"],
                secondary_colour=item_data["secondary_colour"],
                pattern=item_data["pattern"],
                style=item_data["style"],
                sleeve_type=item_data["sleeve_type"],
                formality=item_data["formality"],
                material=item_data["material"],
                confidence=item_data["confidence"],
                attributes_confirmed=True
            )
            db.add(w_item)
            
        db.commit()
        logger.info("Successfully seeded 5 initial demo wardrobe items (W001-W005).")
        
    return demo_user
