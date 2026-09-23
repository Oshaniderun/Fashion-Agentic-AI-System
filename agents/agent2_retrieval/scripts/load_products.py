"""
Load cleaned products into PostgreSQL / SQLite database.
"""

import argparse
import json
from pathlib import Path
import sys

current_dir = Path(__file__).resolve().parent
agent_dir = current_dir.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

from app.models.product import Base, Product
from app.schemas.product import ProductCreate
from app.api.dependencies import SessionLocal, engine

BATCH_SIZE = 1000


def load_products_to_db(json_file_path: Path):
    if not json_file_path.exists():
        raise FileNotFoundError(f"Cleaned products file not found at: {json_file_path}")

    Base.metadata.create_all(bind=engine)

    with open(json_file_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    db = SessionLocal()
    try:
        existing_count = db.query(Product).count()
        db.query(Product).delete()
        db.commit()

        inserted = 0
        batch = []
        for item in records:
            product = Product(**ProductCreate(**item).model_dump())
            batch.append(product)
            if len(batch) >= BATCH_SIZE:
                db.add_all(batch)
                db.commit()
                inserted += len(batch)
                batch = []
                print(f"  inserted {inserted}/{len(records)}", flush=True)

        if batch:
            db.add_all(batch)
            db.commit()
            inserted += len(batch)

        final_count = db.query(Product).count()
        print("Database ingestion completed:")
        print(f"  - Previous table rows: {existing_count}")
        print(f"  - Newly inserted: {inserted}")
        print(f"  - Updated: 0 (table replaced to match cleaned catalogue)")
        print(f"  - Total processed: {len(records)}")
        print(f"  - Table count: {final_count}")
    except Exception as e:
        db.rollback()
        print(f"Error ingesting products into database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load cleaned products into the Agent 2 database.")
    parser.add_argument(
        "--input",
        type=Path,
        default=agent_dir / "data" / "processed" / "products_cleaned.json",
    )
    args = parser.parse_args()
    path = args.input if args.input.exists() else agent_dir / args.input
    load_products_to_db(path)
