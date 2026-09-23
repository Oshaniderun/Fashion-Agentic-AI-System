"""
Shared SQLAlchemy engine, session, and declarative Base.

ALL agents connect to the same PostgreSQL database via DATABASE_URL.
Each agent creates its own tables using this shared Base so that
`Base.metadata.create_all()` in any agent will also create the
shared tables (users, analysis_records) on first run.

DATABASE_URL resolution order:
  1. os.environ["DATABASE_URL"]          ← set by each agent's config at startup
  2. Fallback: sqlite:///./fashora.db    ← zero-config local dev / tests
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session


def _get_database_url() -> str:
    """
    Reads DATABASE_URL lazily from os.environ.
    Each agent's config.py must call os.environ.setdefault('DATABASE_URL', ...)
    or set it before the first DB operation. In tests, the conftest overrides
    the FastAPI dependency (get_db) with an in-memory SQLite engine instead.
    """
    return os.environ.get("DATABASE_URL", "sqlite:///./fashora.db")


def _build_engine():
    url = _get_database_url()
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, connect_args=connect_args, echo=False)


# Engine and session are built once at import time.
# Agents must set DATABASE_URL in os.environ BEFORE importing this module.
# (Agent 1's main.py imports app.core.config first, which calls os.environ.setdefault.)
engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Single shared declarative Base — every ORM model in every agent inherits from this
# so all tables are registered on one metadata and created together.
Base = declarative_base()


def get_shared_db() -> Generator[Session, None, None]:
    """FastAPI dependency for a shared database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_shared_db() -> None:
    """Creates all tables registered on the shared Base (called by each agent on startup)."""
    Base.metadata.create_all(bind=engine)
