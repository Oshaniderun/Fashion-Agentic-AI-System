"""
FastAPI dependencies: shared-DB sessions, authentication and IDOR guard.

Authentication accepts exactly the same credentials as Agents 1 and 2:
- 'Authorization: Bearer <user JWT>' issued by Agent 1 (shared JWT_SECRET)
- the inter-agent AGENT_SERVICE_TOKEN (as Bearer or X-Service-Token header)
"""

from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.db import get_db  # re-export: same shared database, service-local Base
from app.core.security import decode_jwt_token, validate_tenant_access, verify_service_token

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_principal(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
) -> Dict[str, Any]:
    """Validate service token or user JWT; never allow anonymous access."""
    if x_service_token and verify_service_token(x_service_token):
        return {"sub": "service_agent", "is_service": True}

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    if verify_service_token(token):
        return {"sub": "service_agent", "is_service": True}

    payload = decode_jwt_token(token)
    return {"sub": payload.get("sub"), "is_service": False, "claims": payload}


def verify_user_authorization(
    requested_user_id: Optional[Any],
    principal: Dict[str, Any] = Depends(get_current_principal),
) -> Dict[str, Any]:
    """IDOR prevention: callers may only touch their own budget records."""
    if requested_user_id is not None:
        validate_tenant_access(principal.get("sub"), requested_user_id)
    return principal
