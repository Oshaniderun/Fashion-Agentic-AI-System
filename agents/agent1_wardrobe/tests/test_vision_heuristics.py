"""
Vision heuristic tests for frock/check detection without CLIP.
"""

from PIL import Image, ImageDraw
from app.services.image_analysis.analyzer import master_image_analyzer


def _make_checked_frock_like_image(path=None):
    """Tall beige/white gingham-like garment crop."""
    img = Image.new("RGB", (240, 420), (210, 185, 150))
    draw = ImageDraw.Draw(img)
    cell = 10
    for y in range(50, 370, cell):
        for x in range(60, 180, cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(245, 235, 220))
            else:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(185, 155, 115))
    return img


def test_checked_tall_image_prefers_dress_not_jeans():
    img = _make_checked_frock_like_image()
    attrs = master_image_analyzer.analyze_image(img)
    assert attrs.category == "dress"
    assert attrs.type in ["frock", "midi_dress", "maxi_dress", "dress"]
    assert attrs.pattern == "checked"
    assert attrs.colour in ["beige", "brown", "white", "grey"]
    assert attrs.material != "denim"


def test_vivid_red_square_image_prefers_blouse_not_frock():
    """Saturated red upper-body style frame should not be forced to dress."""
    img = Image.new("RGB", (300, 320), (190, 30, 40))
    attrs = master_image_analyzer.analyze_image(img)
    assert attrs.category == "top"
    assert attrs.type in ["blouse", "shirt", "t-shirt"]


def test_wide_slipper_like_object_prefers_shoes():
    """Wide footwear silhouette on plain background should not become a top."""
    img = Image.new("RGB", (420, 240), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    # Dark wide shoe/slipper blob
    draw.ellipse([70, 90, 350, 180], fill=(40, 35, 35))
    draw.rectangle([90, 150, 330, 175], fill=(25, 20, 20))
    attrs = master_image_analyzer.analyze_image(img)
    assert attrs.category == "shoes"
    assert attrs.type in ["slippers", "sandals", "loafers", "sneakers", "boots", "heels"]


def test_small_accessory_on_plain_background():
    img = Image.new("RGB", (320, 320), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.ellipse([140, 140, 180, 180], fill=(200, 160, 40))
    attrs = master_image_analyzer.analyze_image(img)
    assert attrs.category == "accessory"


def test_bag_like_compact_object():
    img = Image.new("RGB", (360, 360), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([110, 120, 250, 260], radius=18, fill=(35, 30, 28))
    draw.arc([150, 95, 210, 140], 0, 180, fill=(60, 50, 45), width=6)
    attrs = master_image_analyzer.analyze_image(img)
    assert attrs.category in ["bag", "accessory", "shoes"]
    # Bag preferred; accessory/shoes acceptable over apparel mislabel
    assert attrs.category != "top"
