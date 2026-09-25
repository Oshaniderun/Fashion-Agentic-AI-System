"""Clean the raw Amazon_Fashion_2023 parquet into Agent 2's catalogue formats.

Outputs:
  1. data/processed/products_cleaned.json   (path RetrievalService already expects)
  2. optional: rows into the Postgres `products` table (--with-db)

Category is derived by keyword classification of the product title because the
dataset's `categories` column is empty ("[]") for every row. Items matching no
fashion category keep category=null (never guessed). Missing values stay null.

Usage:
  python scripts/load_products.py            # JSON only, prints a report
  python scripts/load_products.py --with-db  # also upsert into Postgres
"""

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

AGENT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = AGENT_DIR / "data" / "raw"
OUT_JSON = AGENT_DIR / "data" / "processed" / "products_cleaned.json"
ROOT_ENV = AGENT_DIR.parent.parent / ".env"

NULL_TOKENS = {"nan", "none", "null", "", "n/a", "#n/a", "-", "--"}

# --- category keyword rules (word-boundary, lowercased, hyphens -> spaces) ---
CATEGORY_RULES = {
    "footwear": [
        "shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers", "boot",
        "boots", "sandal", "sandals", "slipper", "slippers", "heel", "heels",
        "pump", "pumps", "clog", "clogs", "loafer", "loafers", "moccasin",
        "oxford", "espadrille", "mule", "mules", "flip flop", "flip flops",
        "mary jane", "brogue", "wedge sandals", "ballet flats", "flats",
        "footwear", "bootie", "booties",
    ],
    "dress": [
        "dress", "dresses", "gown", "gowns", "frock", "jumpsuit", "jumpsuits",
        "romper", "rompers", "sundress", "bodycon", "maxi dress", "mini dress",
        "swimsuit", "swimwear", "one piece swim", "cover up", "coverup",
        "evening gown", "cocktail dress",
    ],
    "outerwear": [
        "jacket", "jackets", "coat", "coats", "blazer", "trench", "parka",
        "windbreaker", "anorak", "cardigan", "cardigans", "poncho", "cape",
        "cloak", "overcoat", "raincoat", "puffer", "down vest", "waistcoat",
        "bolero", "fur coat", "vest",
    ],
    "bag": [
        "bag", "bags", "purse", "purses", "handbag", "handbags", "tote",
        "totes", "backpack", "backpacks", "rucksack", "satchel", "clutch",
        "duffel", "weekender", "crossbody", "fanny pack", "luggage",
        "shoulder bag", "waist pack", "diaper bag",
    ],
    "bottom": [
        "pant", "pants", "jean", "jeans", "trouser", "trousers", "short",
        "shorts", "skirt", "skirts", "legging", "leggings", "capri",
        "capris", "culottes", "jogger", "joggers", "sweatpants", "chino",
        "chinos", "khaki", "khakis", "overalls", "bottoms", "denim pants",
    ],
    "top": [
        "shirt", "shirts", "tee", "tees", "t shirt", "top", "tops", "blouse",
        "blouses", "sweater", "sweaters", "sweatshirt", "sweatshirts",
        "hoodie", "hoodies", "hoody", "hooded", "pullover", "tank top", "camisole", "tunic",
        "polo", "henley", "jersey", "crop top", "tshirt", "sleeve top",
    ],
    "jewelry": [
        "necklace", "necklaces", "pendant", "pendants", "earring", "earrings",
        "bracelet", "bracelets", "bangle", "bangles", "anklet", "ring",
        "rings", "brooch", "tiara", "cufflink", "cufflinks", "jewelry",
        "jewellery", "charm", "charms", "beads", "ear studs",
    ],
    "accessory": [
        "hat", "hats", "cap", "caps", "beanie", "bonnet", "scarf", "scarves",
        "glove", "gloves", "mitten", "mittens", "belt", "belts", "wallet",
        "wallets", "sunglass", "sunglasses", "glasses", "eyewear",
        "headband", "scrunchie", "scrunchies", "sock", "socks", "necktie",
        "tie clip", "mask", "masks", "hosiery", "tights", "pantyhose",
        "lanyard", "earmuffs", "watch", "watches", "hair clip", "hair pins",
        "hair ties", "shawl", "wrap scarf",
    ],
}
# Resolution order for tied scores: most specific/valuable first.
PRIORITY = ["footwear", "dress", "outerwear", "bag", "bottom", "top", "jewelry", "accessory"]

# The dataset's `color` column is ~90% empty; fall back to colour words that
# appear verbatim in Amazon's own title text (e.g. "Matte Black", "Rose Red").
COLOR_WORDS = [
    "black", "white", "grey", "gray", "red", "orange", "yellow", "green",
    "blue", "purple", "pink", "brown", "beige", "tan", "cream", "ivory",
    "gold", "golden", "silver", "navy", "maroon", "burgundy", "turquoise",
    "teal", "coral", "aqua", "lavender", "violet", "indigo", "khaki",
    "olive", "charcoal", "rose", "mint", "peach", "bronze", "copper",
    "multicolor", "multicolored",
]

# "dress" only counts for the dress category when it is the garment itself:
# "dress shoes" -> footwear, "dress shirt" -> top, "dress pants" -> bottom.
DRESS_FALSE_POSSESSIVE = re.compile(
    r"\bdress(?:es)?\s+(shoes?|pumps?|slippers?|flats?|boots?|sandals?|"
    r"pants?|trousers?|jeans?|skirts?|shirts?|blouses?|socks)\b"
)


def clean(value):
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    if text.lower() in NULL_TOKENS:
        return None
    return re.sub(r"\s+", " ", text)


def strip_html(text):
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [ln.strip() for ln in text.split("\n")]
    return clean(" ".join(ln for ln in lines if ln)) or None


def first_image(raw):
    items = raw
    if isinstance(items, str):
        try:
            items = ast.literal_eval(items)
        except (ValueError, SyntaxError):
            return None
    if not isinstance(items, list):
        return None
    for img in items:
        if isinstance(img, dict):
            url = img.get("large") or img.get("hi_res") or img.get("thumb")
            if isinstance(url, str) and url.startswith("http"):
                return url
    return None


def colour_from_title(title):
    if not title:
        return None
    text = re.sub(r"[^\w\s]", " ", title.lower())
    for w in COLOR_WORDS:
        if re.search(rf"\b{w}\b", text):
            return w
    return None


def classify(title):
    if not title:
        return None
    text = title.lower().replace("-", " ").replace("/", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    scores = {}
    for cat, kws in CATEGORY_RULES.items():
        score = 0
        for kw in kws:
            if cat == "dress" and kw == "dress":
                if DRESS_FALSE_POSSESSIVE.search(text):
                    m = re.search(r"\bdress(?:es)?\b(?!\s+(?:shoes?|pumps?|slippers?|flats?|boots?|sandals?|pants?|trousers?|jeans?|skirts?|shirts?|blouses?|socks))", text)
                    if m:
                        score += 1
                    continue
            if re.search(rf"\b{re.escape(kw)}\b", text):
                score += 1
        if score:
            scores[cat] = score
    if not scores:
        return None
    best = max(scores.values())
    for cat in PRIORITY:
        if scores.get(cat) == best:
            return cat
    return None


def parse_db_url(env_path):
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            return url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return None


def load_to_db(products, env_path):
    sys.path.insert(0, str(AGENT_DIR))
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from app.models.product import Base, Product

    url = os.environ.get("AGENT2_DATABASE_URL") or parse_db_url(env_path)
    if not url:
        print("ERROR: no DATABASE_URL found (env file missing and AGENT2_DATABASE_URL unset).")
        return False
    # never print the URL: it contains the password
    print(f"Connecting to database from {env_path if not os.environ.get('AGENT2_DATABASE_URL') else 'AGENT2_DATABASE_URL'} (credentials not shown)...")
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=[Product.__table__])
    Session = sessionmaker(bind=engine)
    with Session() as session:
        rows = [{**p, "currency": "USD" if p.get("price") is not None else None} for p in products]
        session.execute(text("TRUNCATE TABLE products"))
        session.bulk_insert_mappings(Product, rows)
        session.commit()
        count = session.execute(text("SELECT COUNT(*) FROM products")).scalar_one()
    print(f"Loaded {count} rows into products table.")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-db", action="store_true", help="also upsert into Postgres products table")
    parser.add_argument("--env-file", type=Path, default=ROOT_ENV)
    args = parser.parse_args()

    parquet_files = list(RAW_DIR.rglob("*.parquet"))
    if not parquet_files:
        print("No parquet found under data/raw — nothing to do.")
        return 1
    f = parquet_files[0]
    print(f"Reading {f}")
    df = pd.read_parquet(f)
    print(f"Raw rows: {len(df)}")

    products = []
    cat_counts = {}
    for _, row in df.iterrows():
        title = clean(row.get("title"))
        color = clean(row.get("color"))
        style = clean(row.get("style"))
        material = clean(row.get("material"))
        brand = clean(row.get("brand"))
        store = clean(row.get("store"))
        size = clean(row.get("size"))
        desc = strip_html(clean(row.get("description")))
        price_raw = row.get("price")
        try:
            price = float(price_raw) if price_raw is not None and not pd.isna(price_raw) else None
            if price is not None and (price != price):  # NaN guard: float("nan") strings
                price = None
        except (TypeError, ValueError):
            price = None
        cat = classify(title)
        if color is None:
            color = colour_from_title(title)
        cat_counts[cat or "null"] = cat_counts.get(cat or "null", 0) + 1
        products.append({
            "product_id": str(row["parent_asin"]),
            "product_name": title or "Unknown Product",
            "category": cat,
            "subcategory": None,
            "brand": brand,
            "price": price,
            "currency": "USD" if price is not None else None,
            "colour": color,
            "material": material,
            "style": style,
            "size": size,
            "description": desc,
            "store": store,
            "image_url": first_image(row.get("images")),
            "product_url": None,   # dataset has no URL column; not fabricated
            "availability": None,  # dataset has no availability; left missing
        })

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(products, fh, ensure_ascii=False)
    print(f"Wrote {len(products)} products -> {OUT_JSON}")

    n = len(products)
    classified = n - cat_counts.get("null", 0)
    print(f"\nCategory coverage: {classified}/{n} ({classified/n*100:.1f}%)")
    for k, v in sorted(cat_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:12s} {v:6d}")
    for field in ("colour", "price", "style", "image_url", "brand", "material", "description"):
        missing = sum(1 for p in products if p[field] is None)
        print(f"  {field:12s} missing: {missing} ({missing/n*100:.1f}%)")

    print("\nSample per category:")
    for cat in PRIORITY:
        sample = [p["product_name"] for p in products if p["category"] == cat][:3]
        print(f"  [{cat}]")
        for s in sample:
            print(f"     - {s[:95]}")
    nulls = [p["product_name"] for p in products if p["category"] is None][:5]
    print("  [null (unclassified, examples)]")
    for s in nulls:
        print(f"     - {s[:95]}")

    if args.with_db:
        if not load_to_db(products, args.env_file):
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
