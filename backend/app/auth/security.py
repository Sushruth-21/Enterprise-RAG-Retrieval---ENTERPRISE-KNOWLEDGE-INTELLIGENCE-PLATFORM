from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import os
from typing import Dict, List, Optional
import uuid
import warnings

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

# Suppress PyJWT short key warning to maintain compatibility with default dev secrets
warnings.filterwarnings("ignore", message=".*InsecureKeyLengthWarning.*")

logger = logging.getLogger(__name__)

# Secret key & token parameters
SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", "change-me-in-production"))
ALGORITHM = "HS256"
DEFAULT_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Bcrypt password hashing context with SHA-256 fallback
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

security_scheme = HTTPBearer(auto_error=False)


# ─────────────────────────────────────────────────────────────────────────────
# Role & Scope Configuration (Mapping to Person 4's employee_role_enum)
# ─────────────────────────────────────────────────────────────────────────────
ROLE_CONFIG: Dict[str, Dict[str, Any]] = {
    "employee": {
        "title": "Junior Employee",
        "department": "Operations",
        "access_scopes": ["public"],
        "permissions": ["read"],
        "description": "Standard staff member. Can read public policy and operational guidelines.",
    },
    "analyst": {
        "title": "Senior Business Analyst",
        "department": "Finance & Strategy",
        "access_scopes": ["public", "internal"],
        "permissions": ["read"],
        "description": "Senior staff. Can access public and internal departmental documents.",
    },
    "manager": {
        "title": "Department Manager",
        "department": "Engineering & Operations",
        "access_scopes": ["public", "internal"],
        "permissions": ["read"],
        "description": "Department head. Can access public and internal business data.",
    },
    "compliance_officer": {
        "title": "Chief Compliance Officer",
        "department": "Legal & Compliance",
        "access_scopes": ["public", "internal", "confidential"],
        "permissions": ["read", "admin"],
        "description": "Compliance auditor. Access to all public, internal, and confidential records.",
    },
    "admin": {
        "title": "System Administrator",
        "department": "Information Technology",
        "access_scopes": ["public", "internal", "confidential"],
        "permissions": ["read", "write", "admin"],
        "description": "Full enterprise administrator with upload, deletion, and full audit clearance.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Password Hashing Functions (bcrypt / scrypt)
# ─────────────────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.warning("Bcrypt hashing failed, falling back to scrypt: %s", e)
        salt = os.urandom(16)
        key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
        return f"scrypt${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    if hashed_password.startswith("scrypt$"):
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        salt = bytes.fromhex(parts[1])
        expected_key = bytes.fromhex(parts[2])
        actual_key = hashlib.scrypt(plain_password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
        return actual_key == expected_key
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error("Password verification error: %s", e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# User Payload & JWT
# ─────────────────────────────────────────────────────────────────────────────
class UserPayload(BaseModel):
    user_id: str
    organization_id: uuid.UUID
    role: str = "employee"
    access_scopes: List[str] = Field(default_factory=lambda: ["public"])
    name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None

    def can_access_scope(self, scope: str) -> bool:
        return scope in self.access_scopes

    def is_admin(self) -> bool:
        return self.role in ("admin", "compliance_officer")


def create_access_token(
    user_id: str,
    organization_id: uuid.UUID | str,
    role: str = "employee",
    access_scopes: Optional[List[str]] = None,
    name: Optional[str] = None,
    email: Optional[str] = None,
    department: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate an HMAC-SHA256 JWT access token."""
    if access_scopes is None:
        role_info = ROLE_CONFIG.get(role, ROLE_CONFIG["employee"])
        access_scopes = role_info["access_scopes"]

    org_id_str = str(organization_id)
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=DEFAULT_EXPIRE_MINUTES))

    payload = {
        "sub": user_id,
        "user_id": user_id,
        "organization_id": org_id_str,
        "role": role,
        "access_scopes": access_scopes,
        "name": name or f"Demo {role.capitalize()}",
        "email": email or f"{role}@enterprise.local",
        "department": department or ROLE_CONFIG.get(role, {}).get("department", "Operations"),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> UserPayload:
    """Decode and cryptographically verify JWT token."""
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
            org_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(org_id_raw))

        role = payload.get("role", "employee")
        scopes = payload.get("access_scopes", ["public"])

        return UserPayload(
            user_id=str(user_id),
            organization_id=org_uuid,
            role=str(role),
            access_scopes=list(scopes),
            name=payload.get("name"),
            email=payload.get("email"),
            department=payload.get("department"),
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
    """FastAPI security dependency for authenticated endpoints."""
    if auth is None or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected 'Bearer <JWT>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(auth.credentials)


def get_optional_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> Optional[UserPayload]:
    """Optional security dependency: returns UserPayload if valid token supplied, else None."""
    if auth and auth.credentials:
        try:
            return decode_access_token(auth.credentials)
        except HTTPException:
            return None
    return None


def require_admin(user: UserPayload = Security(get_current_user)) -> UserPayload:
    """Guard ensuring the user has administrative privileges (admin or compliance_officer)."""
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Role '{user.role}' lacks administrative permissions to perform this action.",
        )
    return user
