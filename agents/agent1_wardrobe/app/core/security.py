"""
Security, authentication, and prompt injection defense utilities.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import jwt
import bcrypt
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


# ---------------------------------------------------------------------------
# JWT Token Handling
# ---------------------------------------------------------------------------

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.PyJWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


# ---------------------------------------------------------------------------
# Prompt Injection & Jailbreak Defense
# ---------------------------------------------------------------------------

PROMPT_INJECTION_PATTERNS = [
    # Direct instruction override
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"forget\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"bypass\s+(all\s+)?(security|safety|guidelines?)",
    
    # System prompt extraction & leakage
    r"system\s*prompt",
    r"reveal\s+(your\s+)?(system|internal|hidden)\s+(instructions?|prompt)",
    r"print\s+(your\s+)?(system|internal|hidden)\s+(prompt|instructions?)",
    r"show\s+me\s+(the\s+)?system\s+prompt",
    r"what\s+are\s+your\s+(initial|system)\s+instructions?",
    
    # Secret / credential extraction
    r"(api[_\s]?key|jwt[_\s]?secret|database[_\s]?url|environment\s*variables?)",
    r"(reveal|extract|print|show)\s+(the\s+)?(api\s*key|secret|credentials?)",
    
    # Role-play jailbreaks
    r"act\s+as\s+(a\s+)?(system\s*admin|unrestricted|god\s*mode|dan)",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"jailbreak",
    r"pretend\s+you\s+have\s+no\s+(rules|guidelines|ethics)",
    
    # Format hijacking
    r"ignore\s+(the\s+)?json\s+format",
    r"output\s+only\s+plain\s+text\s+saying",
]

INJECTION_REGEX = re.compile("|".join(PROMPT_INJECTION_PATTERNS), re.IGNORECASE)


class SecuritySanitizeResult(BaseModel):
    is_safe: bool
    detected_patterns: List[str]
    sanitized_text: str
    risk_level: str  # "clean", "suspicious", "malicious"


def inspect_and_sanitize_user_text(text: str) -> SecuritySanitizeResult:
    """
    Evaluates incoming natural-language text for prompt injection, jailbreak attempts,
    and secret extraction. Sanitizes dangerous constructs while preserving fashion context.
    """
    matches = INJECTION_REGEX.findall(text)
    detected: List[str] = []
    for match in matches:
        if isinstance(match, tuple):
            detected.extend([m for m in match if m])
        elif match:
            detected.append(match)
            
    # Deduplicate matches
    detected = list(set([d.strip().lower() for d in detected if d.strip()]))
    
    if not detected:
        return SecuritySanitizeResult(
            is_safe=True,
            detected_patterns=[],
            sanitized_text=text,
            risk_level="clean"
        )
        
    risk_level = "malicious" if any(
        kw in " ".join(detected) for kw in ["ignore", "system", "api_key", "secret", "dan", "jailbreak"]
    ) else "suspicious"
    
    # Strip or neutralize identified injection segments from user query
    sanitized = INJECTION_REGEX.sub("[FILTERED_UNTRUSTED_INSTRUCTION]", text)
    
    logger.warning(
        f"Prompt injection pattern detected! Risk: {risk_level}. Matches: {detected}",
        extra={"processing_stage": "security_sanitization", "risk_level": risk_level}
    )
    
    return SecuritySanitizeResult(
        is_safe=(risk_level != "malicious"),
        detected_patterns=detected,
        sanitized_text=sanitized,
        risk_level=risk_level
    )


# ---------------------------------------------------------------------------
# Inter-service & User Auth Dependencies
# ---------------------------------------------------------------------------

def verify_service_token(authorization: Optional[str] = Header(None)) -> bool:
    """Verifies that an inter-agent request provides the shared AGENT_SERVICE_TOKEN."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header for agent-to-agent communication."
        )
    token = authorization.replace("Bearer ", "").strip()
    if token != settings.AGENT_SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid agent service token."
        )
    return True
