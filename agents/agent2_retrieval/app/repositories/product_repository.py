from sqlalchemy.orm import Session
from app.models.product import Product
from app.schemas.product import ProductCreate
from typing import List, Optional

class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, product_id: str) -> Optional[Product]:
        return self.db.query(Product).filter(Product.product_id == product_id).first()

    def get_multi(self, skip: int = 0, limit: int = 100) -> List[Product]:
        return self.db.query(Product).offset(skip).limit(limit).all()

    def get_by_ids(self, product_ids: List[str]) -> List[Product]:
        return self.db.query(Product).filter(Product.product_id.in_(product_ids)).all()

    def create(self, product_in: ProductCreate) -> Product:
        db_obj = Product(**product_in.model_dump())
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
        
    def bulk_create(self, products_in: List[ProductCreate]) -> List[Product]:
        db_objs = [Product(**p.model_dump()) for p in products_in]
        self.db.add_all(db_objs)
        self.db.commit()
        return db_objs
