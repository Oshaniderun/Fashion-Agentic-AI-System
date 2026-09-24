"""
Security module: JWT validation, inter-agent service token verification,
and input sanitization.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates JWT signature, expiration, and algorithm.
    Raises JWTError if invalid or expired.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.ALGORITHM]
    )
    return payload

def verify_service_token(token: str) -> bool:
    """
    Validates inter-agent shared service token.
    """
    if not token or not settings.AGENT_SERVICE_TOKEN:
        return False
    # Constant-time comparison
    import hmac
    return hmac.compare_digest(token.strip(), settings.AGENT_SERVICE_TOKEN.strip())

def sanitize_input_text(text: Optional[str], max_len: int = 500) -> Optional[str]:
    """
    Basic input sanitization: strips control characters and truncates excessive lengths.
    """
    if text is None:
        return None
    import re
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Truncate
    return sanitized[:max_len].strip()
