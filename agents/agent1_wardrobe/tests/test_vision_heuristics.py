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
