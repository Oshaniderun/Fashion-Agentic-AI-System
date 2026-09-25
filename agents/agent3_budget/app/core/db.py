"""
Database session for the budget service.

SAME physical database as Agents 1 & 2 (root .env DATABASE_URL -> shared
PostgreSQL), but a dedicated declarative Base/metadata holding only this
service's budget_* tables.

Why not shared.models.database.Base here: importing that package also
registers Agent 1's User model, whose relationship('WardrobeItem') can only
resolve inside the Agent 1 process (where WardrobeItem is imported). Any
query in this service would then die with "failed to locate name
'WardrobeItem'". A private Base over the same URL keeps the shared-DB
guarantee without cross-registry mapper resolution.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

Base = declarative_base()

_url = settings.DATABASE_URL
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=_connect_args, echo=False, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — session against the shared FASHORA database."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Additively create the budget_* tables in the shared database."""
    import app.models  # noqa: F401 — register tables on this Base

    Base.metadata.create_all(bind=engine)
