from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.sql import func

from app.models.product import Base


class SearchHistory(Base):
    __tablename__ = "agent2_search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), index=True, nullable=False)
    source = Column(String(30), nullable=False)  # 'search' | 'agent1_handoff'
    request_id = Column(String(200), index=True)
    query_text = Column(Text)
    category = Column(String(100))
    preferred_colour = Column(String(100))
    style = Column(String(100))
    occasion = Column(String(100))
    max_price = Column(Float)
    status = Column(String(30))
    result_count = Column(Integer)
    relaxed_constraints = Column(Text)  # JSON list
    product_ids = Column(Text)  # JSON list, ranked order
    created_at = Column(DateTime(timezone=True), server_default=func.now())
