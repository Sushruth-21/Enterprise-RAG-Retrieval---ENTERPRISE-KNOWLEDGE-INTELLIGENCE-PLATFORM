from __future__ import annotations
from datetime import datetime, timedelta, timezone
import logging
import os
from typing import List, Optional
import uuid
import warnings

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from pydantic import BaseModel, Field

# Suppress PyJWT short key warning to maintain compatibility with Person 1's backend default key
warnings.filterwarnings("ignore", message=".*InsecureKeyLengthWarning.*")

logger = logging.getLogger(__name__)

# Person 1 backend shared secrets and settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", "change-me-in-production"))
ALGORITHM = "HS256"
DEFAULT_EXPIRE_MINUTES = 60 * 24  # 24 hours

security_scheme = HTTPBearer(auto_error=False)


class UserPayload(BaseModel):
    """Authenticated user context derived strictly from verified JWT claims."""
    user_id: str
    organization_id: uuid.UUID
    role: str = "member"
    access_scopes: List[str] = Field(default_factory=lambda: ["public"])

    def can_access_scope(self, scope: str) -> bool:
        """Check if user has clearance for a particular document/chunk access scope."""
        return scope in self.access_scopes


def create_access_token(
    user_id: str,
    organization_id: uuid.UUID | str,
    role: str = "member",
    access_scopes: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generate an RFC 7519 compliant HMAC-SHA256 JWT access token.
    Compatible with Person 1's backend authentication.
    """
    if access_scopes is None:
        access_scopes = ["public"]

    org_id_str = str(organization_id)
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=DEFAULT_EXPIRE_MINUTES))

    payload = {
        "sub": user_id,
        "user_id": user_id,
        "organization_id": org_id_str,
        "role": role,
        "access_scopes": access_scopes,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> UserPayload:
    """
    Decode and cryptographically verify JWT token signature and expiration.
    Raises HTTPException(401) on failure.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id") or payload.get("sub")
        org_id_raw = payload.get("organization_id")
        if not user_id or not org_id_raw:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing user_id or organization_id claim.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            org_uuid = uuid.UUID(str(org_id_raw))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token organization_id UUID: {org_id_raw}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        role = payload.get("role", "member")
        scopes = payload.get("access_scopes", ["public"])

        return UserPayload(
            user_id=str(user_id),
            organization_id=org_uuid,
            role=str(role),
            access_scopes=list(scopes),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signature has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> UserPayload:
    """
    FastAPI security dependency for authenticated endpoints.
    Enforces JWT bearer authentication and extracts authenticated user context.
    """
    if auth is None or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected 'Bearer <JWT>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(auth.credentials)
