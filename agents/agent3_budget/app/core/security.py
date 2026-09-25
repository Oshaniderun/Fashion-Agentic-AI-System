"""
Security & privacy utilities for the Budget & Purchase Planning service.

Ported from the team Agent 3 build, adapted to this repo's canonical
JWT_SECRET / AGENT_SERVICE_TOKEN (root .env, issued and verified with the
same HS256 key as Agent 1).

Defenses:
- Constant-time inter-service token comparison (timing-attack safe)
- IDOR / tenant isolation on per-user budget endpoints
- PII & financial-data scrubbing for logs (cards, emails, phone numbers)
- JWT signature + expiry verification (Agent 1-issued tokens accepted as-is)
"""

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import jwt

from app.core.config import get_settings

logger = logging.getLogger("budget_security")
settings = get_settings()

# ---------------------------------------------------------------------------
# PII / financial scrubbing (used on log lines and stored free-text)
# ---------------------------------------------------------------------------

RE_CARD = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
RE_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
RE_PHONE = re.compile(r"(?:\+?94|0)\s?[0-9]{2,3}[-\s]?[0-9]{6,7}")


def scrub_pii(text: str) -> str:
    """Redact card numbers, emails and phone numbers from any text."""
    if not isinstance(text, str):
        return text
    scrubbed = RE_CARD.sub("[REDACTED_FINANCIAL_CARD]", text)
    scrubbed = RE_EMAIL.sub("[REDACTED_EMAIL]", scrubbed)
    scrubbed = RE_PHONE.sub("[REDACTED_PHONE]", scrubbed)
    return scrubbed


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def verify_service_token(token: str) -> bool:
    """Constant-time comparison against the shared AGENT_SERVICE_TOKEN."""
    if not token or not settings.AGENT_SERVICE_TOKEN:
        return False
    return secrets.compare_digest(token, settings.AGENT_SERVICE_TOKEN)


def create_access_token(
    user_id: Union[str, int],
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Mint an Agent-1-compatible JWT (sub/exp/iat, HS256). Used by tests."""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=2))
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode/validate a JWT. Raises HTTPException(401) when invalid."""
    from fastapi import HTTPException, status

    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please re-authenticate.",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed authentication credentials.",
        )


# ---------------------------------------------------------------------------
# IDOR / tenant isolation
# ---------------------------------------------------------------------------

def validate_tenant_access(
    authenticated_sub: Optional[str],
    requested_user_id: Optional[Union[str, int]],
) -> None:
    """
    A caller may only read or mutate budget data for their own user_id.
    Trusted inter-agent service principals (sub == 'service_agent') bypass
    the check because they act on behalf of the orchestrator.
    """
    from fastapi import HTTPException, status

    if authenticated_sub is None or requested_user_id is None:
        return
    if authenticated_sub == "service_agent":
        return
    if str(authenticated_sub) != str(requested_user_id):
        logger.warning(
            "IDOR attempt detected: authenticated user '%s' tried to access "
            "budget records of user '%s'",
            authenticated_sub,
            requested_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Access forbidden: you cannot access or manipulate budget "
                "records belonging to another user."
            ),
        )
