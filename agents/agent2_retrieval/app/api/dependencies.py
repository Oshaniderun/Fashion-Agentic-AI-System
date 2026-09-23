"""
API dependencies: Database sessions and Authentication.
Supports both user JWT Bearer tokens and inter-agent Shared Service Tokens.
"""

from typing import Generator, Optional
import os
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from jose import JWTError

from app.core.config import get_settings
from app.core.security import decode_access_token, verify_service_token

settings = get_settings()

# Engine setup: fallback to SQLite if PostgreSQL fails or if in testing/local mode
db_url = settings.SQLALCHEMY_DATABASE_URI

def create_db_engine(url: str):
    try:
        if "postgresql" in url:
            # Test engine creation
            eng = create_engine(url, pool_pre_ping=True)
            with eng.connect() as conn:
                pass
            return eng
    except Exception:
        pass
    # Fallback to local SQLite database
    sqlite_url = "sqlite:///./agent2.db"
    return create_engine(sqlite_url, connect_args={"check_same_thread": False})

engine = create_db_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def require_auth(
    authorization: Optional[str] = Header(None),
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token")
) -> dict:
    """
    Validates either:
    1. Inter-agent shared service token via 'X-Service-Token' header or 'Bearer <service_token>'
    2. User JWT access token via 'Authorization: Bearer <jwt>'
    """
    # Check X-Service-Token first
    if x_service_token and verify_service_token(x_service_token):
        return {"auth_type": "service", "identity": "inter-agent"}

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials (provide Authorization Bearer token or X-Service-Token)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Check if Bearer token matches service token directly
    if verify_service_token(token):
        return {"auth_type": "service", "identity": "inter-agent"}

    # Validate as JWT
    try:
        payload = decode_access_token(token)
        return {"auth_type": "user", "payload": payload}
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired JWT token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
