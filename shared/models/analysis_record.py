"""
AnalysisRecord ORM model — shared across all FASHORA agents.

Stores the full Agent 1 output (user prompt + structured JSON contract) per user.
Agent 2, 3, and 4 can look up a past analysis by request_id via:
  - REST: GET /api/analyze/{request_id}   (preferred — no direct DB coupling)
  - DB:   query analysis_records directly using the shared session (orchestrator internal use)

Table lives in the shared database so every agent can read it without calling Agent 1's HTTP API.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship

from shared.models.database import Base


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id = Column(Integer, primary_key=True, index=True)

    # Unique analysis identifier (format: REQ-YYYY-XXXXXX)
    request_id = Column(String(64), unique=True, nullable=False, index=True)

    # Owner — FK to shared users table
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Raw natural-language input the user typed
    input_text = Column(Text, nullable=False)

    # Full FashionAnalysisResponse (contains Agent1OutputContract) serialized as JSON.
    # Agent 2/3/4 can deserialize this directly without calling Agent 1 over HTTP.
    payload = Column(JSON, nullable=False)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    user = relationship("User", back_populates="analysis_records")
