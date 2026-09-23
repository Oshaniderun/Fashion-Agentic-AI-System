"""
Preprocess Amazon Fashion 2023 dataset.
Validates, cleans, and normalizes product records before ingestion into PostgreSQL and vector DB.
Supports JSON arrays (small fixtures) and JSONL/NDJSON (full catalogue) via streaming.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
import sys

# Ensure shared and app modules are importable
current_dir = Path(__file__).resolve().parent
agent_dir = current_dir.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

from shared.constants import ProductCategory

MISSING_STRINGS = {"", "nan", "none", "null", "n/a", "na"}

CATEGORY_MAPPING = {
    # Tops
    "top": ProductCategory.TOP,
    "tops": ProductCategory.TOP,
    "shirt": ProductCategory.TOP,
    "shirts": ProductCategory.TOP,
    "t-shirt": ProductCategory.TOP,
    "t-shirts": ProductCategory.TOP,
    "tee": ProductCategory.TOP,
    "blouse": ProductCategory.TOP,
    "blouses": ProductCategory.TOP,
    "sweaters": ProductCategory.TOP,
    "sweater": ProductCategory.TOP,
    "cardigan": ProductCategory.OUTERWEAR,
    "cardigans": ProductCategory.OUTERWEAR,
    "knitwear": ProductCategory.TOP,
    # Bottoms
    "bottom": ProductCategory.BOTTOM,
    "bottoms": ProductCategory.BOTTOM,
    "pant": ProductCategory.BOTTOM,
    "pants": ProductCategory.BOTTOM,
    "trouser": ProductCategory.BOTTOM,
    "trousers": ProductCategory.BOTTOM,
    "jean": ProductCategory.BOTTOM,
    "jeans": ProductCategory.BOTTOM,
    "skirt": ProductCategory.BOTTOM,
    "skirts": ProductCategory.BOTTOM,
    "short": ProductCategory.BOTTOM,
    "shorts": ProductCategory.BOTTOM,
    "leggings": ProductCategory.BOTTOM,
    # Dresses
    "dress": ProductCategory.DRESS,
    "dresses": ProductCategory.DRESS,
    "cocktail": ProductCategory.DRESS,
    "gown": ProductCategory.DRESS,
    "jumpsuit": ProductCategory.DRESS,
    # Outerwear
    "outerwear": ProductCategory.OUTERWEAR,
    "jacket": ProductCategory.OUTERWEAR,
    "jackets": ProductCategory.OUTERWEAR,
    "coat": ProductCategory.OUTERWEAR,
    "coats": ProductCategory.OUTERWEAR,
    "blazer": ProductCategory.OUTERWEAR,
    "blazers": ProductCategory.OUTERWEAR,
    "suiting & blazers": ProductCategory.OUTERWEAR,
    "trench": ProductCategory.OUTERWEAR,
    "trench coat": ProductCategory.OUTERWEAR,
    "trench coats": ProductCategory.OUTERWEAR,
    # Shoes
    "shoes": ProductCategory.SHOES,
    "shoe": ProductCategory.SHOES,
    "pumps": ProductCategory.SHOES,
    "flats": ProductCategory.SHOES,
    "loafers": ProductCategory.SHOES,
    "loafer": ProductCategory.SHOES,
    "sneakers": ProductCategory.SHOES,
    "sneaker": ProductCategory.SHOES,
    "boots": ProductCategory.SHOES,
    "boot": ProductCategory.SHOES,
    "sandals": ProductCategory.SHOES,
    "sandal": ProductCategory.SHOES,
    "heels": ProductCategory.SHOES,
    # Bags
    "bag": ProductCategory.BAG,
    "bags": ProductCategory.BAG,
    "handbag": ProductCategory.BAG,
    "handbags": ProductCategory.BAG,
    "handbags & wallets": ProductCategory.BAG,
    "top-handle bags": ProductCategory.BAG,
    "tote": ProductCategory.BAG,
    "clutch": ProductCategory.BAG,
    "crossbody": ProductCategory.BAG,
    "purse": ProductCategory.BAG,
    # Jewelry
    "jewelry": ProductCategory.JEWELRY,
    "jewellery": ProductCategory.JEWELRY,
    "necklace": ProductCategory.JEWELRY,
    "necklaces": ProductCategory.JEWELRY,
    "pendants": ProductCategory.JEWELRY,
    "ring": ProductCategory.JEWELRY,
    "rings": ProductCategory.JEWELRY,
    "earrings": ProductCategory.JEWELRY,
    "bracelet": ProductCategory.JEWELRY,
    "bracelets": ProductCategory.JEWELRY,
    "watches": ProductCategory.JEWELRY,
    "watch": ProductCategory.JEWELRY,
    "wrist watches": ProductCategory.JEWELRY,
    # Accessories
    "accessory": ProductCategory.ACCESSORY,
    "accessories": ProductCategory.ACCESSORY,
    "belt": ProductCategory.ACCESSORY,
    "belts": ProductCategory.ACCESSORY,
    "scarf": ProductCategory.ACCESSORY,
    "sunglasses": ProductCategory.ACCESSORY,
    "hat": ProductCategory.ACCESSORY,
}


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        return value != value  # NaN
    if isinstance(value, str) and value.strip().lower() in MISSING_STRINGS:
        return True
    return False


def clean_text(text: Any) -> Optional[str]:
    if is_missing(text) or not isinstance(text, str):
        return None
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()
    if not cleaned or cleaned.lower() in MISSING_STRINGS:
        return None
    return cleaned


def parse_structured(value: Any) -> Any:
    """Parse JSON/Python-literal lists and dicts stored as strings."""
    if is_missing(value):
        return None
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return value


def parse_categories(raw: Any) -> List[str]:
    parsed = parse_structured(raw)
    if parsed is None:
        return []
    if isinstance(parsed, str):
        text = clean_text(parsed)
        return [text] if text else []
    if isinstance(parsed, list):
        out: List[str] = []
        for item in parsed:
            text = clean_text(item if isinstance(item, str) else str(item))
            if text:
                out.append(text)
        return out
    return []


def extract_image_url(item: Dict[str, Any]) -> Optional[str]:
    if not is_missing(item.get("image_url")):
        return clean_text(item.get("image_url"))

    parsed = parse_structured(item.get("images"))
    if not isinstance(parsed, list) or not parsed:
        return None

    first = parsed[0]
    if isinstance(first, str):
        return clean_text(first)
    if isinstance(first, dict):
        for key in ("hi_res", "large", "thumb"):
            url = clean_text(first.get(key))
            if url:
                return url
    return None


def parse_price(raw: Any) -> Tuple[Optional[float], Optional[str]]:
    """Return (price, error_reason). Missing price is valid (None, None)."""
    if is_missing(raw):
        return None, None
    try:
        price = float(raw)
    except (ValueError, TypeError):
        return None, "invalid_price"
    if price != price:  # NaN
        return None, None
    if price <= 0:
        return None, "invalid_price"
    return price, None


def map_category(raw_categories: List[str], title: str, extra_text: str = "") -> Optional[ProductCategory]:
    for cat in reversed(raw_categories):
        lowered = cat.lower().strip()
        if lowered in CATEGORY_MAPPING:
            return CATEGORY_MAPPING[lowered]
        for key, mapped in CATEGORY_MAPPING.items():
            if key in lowered:
                return mapped

    search_text = f"{title} {extra_text}".lower()
    for key, mapped in CATEGORY_MAPPING.items():
        if re.search(rf"\b{re.escape(key)}\b", search_text):
            return mapped
    return None


def preprocess_item(item: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(item, dict):
        return None, "malformed_record"

    product_id = clean_text(
        item.get("parent_asin") or item.get("asin") or item.get("product_id")
    )
    product_name = clean_text(item.get("title") or item.get("product_name"))

    if not product_id:
        return None, "missing_product_id"
    if not product_name:
        return None, "missing_product_name"

    price, price_error = parse_price(item.get("price"))
    if price_error:
        return None, price_error

    categories = parse_categories(item.get("categories"))
    extra_text = " ".join(
        part for part in (clean_text(item.get("description")), clean_text(item.get("features"))) if part
    )
    mapped = map_category(categories, product_name, extra_text)

    brand = clean_text(item.get("brand")) or clean_text(item.get("manufacturer"))
    description = clean_text(item.get("description")) or clean_text(item.get("features"))

    return {
        "product_id": product_id,
        "product_name": product_name,
        "category": mapped.value if mapped else None,
        "subcategory": categories[-1] if categories else None,
        "brand": brand,
        "price": price,
        "currency": clean_text(item.get("currency")),
        "colour": clean_text(item.get("color") or item.get("colour")),
        "material": clean_text(item.get("material")),
        "style": (clean_text(item.get("style")) or "").lower() or None,
        "size": clean_text(item.get("size")),
        "description": description,
        "store": clean_text(item.get("store")),
        "image_url": extract_image_url(item),
        "product_url": clean_text(item.get("product_url")),
        "availability": None if is_missing(item.get("availability")) else bool(item.get("availability")),
    }, None


def resolve_path(path: Path) -> Path:
    if path.exists():
        return path.resolve()
    alt = agent_dir / path
    if alt.exists():
        return alt.resolve()
    cwd_alt = Path.cwd() / path
    if cwd_alt.exists():
        return cwd_alt.resolve()
    return path


def iter_raw_records(raw_file: Path) -> Iterator[Any]:
    """Yield records from a JSON array or JSONL/NDJSON file without requiring JSONL-only input."""
    with open(raw_file, "r", encoding="utf-8") as f:
        while True:
            ch = f.read(1)
            if not ch:
                return
            if not ch.isspace():
                break
        f.seek(0)
        if ch == "[":
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError(f"Expected a JSON array in {raw_file}")
            yield from data
            return
        for line_no, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError:
                yield {"__parse_error__": True, "__line__": line_no}


def run_preprocessing(raw_file: Path, processed_file: Path) -> Dict[str, Any]:
    if not raw_file.exists():
        raise FileNotFoundError(f"Raw data file not found: {raw_file}")

    processed_file.parent.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    drop_reasons: Counter[str] = Counter()
    raw_count = 0
    cleaned_count = 0

    with open(processed_file, "w", encoding="utf-8") as out:
        out.write("[")
        first = True
        for item in iter_raw_records(raw_file):
            raw_count += 1
            if isinstance(item, dict) and item.get("__parse_error__"):
                drop_reasons["malformed_json"] += 1
                continue

            processed, reason = preprocess_item(item)
            if processed is None:
                drop_reasons[reason or "malformed_record"] += 1
                continue

            pid = processed["product_id"]
            if pid in seen_ids:
                drop_reasons["duplicate_product_id"] += 1
                continue
            seen_ids.add(pid)

            if first:
                out.write("\n")
                first = False
            else:
                out.write(",\n")
            json.dump(processed, out, ensure_ascii=False)
            cleaned_count += 1
        out.write("\n]\n")

    dropped_count = raw_count - cleaned_count
    print("Preprocessing completed:")
    print(f"  - Total raw records: {raw_count}")
    print(f"  - Successfully processed: {cleaned_count}")
    print(f"  - Dropped / malformed: {dropped_count}")
    if drop_reasons:
        print("  - Drop reasons:")
        for reason, count in drop_reasons.most_common():
            print(f"      {reason}: {count}")
    print(f"  - Saved to: {processed_file}")

    return {
        "raw_count": raw_count,
        "cleaned_count": cleaned_count,
        "dropped_count": dropped_count,
        "drop_reasons": dict(drop_reasons),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess Agent 2 fashion catalogue data.")
    parser.add_argument(
        "--input",
        type=Path,
        default=agent_dir / "data" / "raw" / "amazon_fashion_2023.json",
        help="Raw catalogue path (JSON array or JSONL).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=agent_dir / "data" / "processed" / "products_cleaned.json",
        help="Cleaned JSON array output path.",
    )
    args = parser.parse_args()
    input_path = resolve_path(args.input)
    output_path = args.output
    if not output_path.is_absolute():
        output_path = output_path.resolve() if output_path.exists() else (agent_dir / output_path)
    run_preprocessing(input_path, output_path)


if __name__ == "__main__":
    main()
