from __future__ import annotations
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr

from app.auth.security import (
    ROLE_CONFIG,
    UserPayload,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])

# ─────────────────────────────────────────────────────────────────────────────
# Built-in Demo Enterprise Employees (Pass: <role>123)
# ─────────────────────────────────────────────────────────────────────────────
DEMO_USERS = {
    "employee@enterprise.local": {
        "id": "emp-001",
        "name": "John Doe (Junior Associate)",
        "email": "employee@enterprise.local",
        "password_hash": hash_password("employee123"),
        "role": "employee",
        "department": "Operations",
    },
    "analyst@enterprise.local": {
        "id": "emp-002",
        "name": "Sarah Connor (Senior Analyst)",
        "email": "analyst@enterprise.local",
        "password_hash": hash_password("analyst123"),
        "role": "analyst",
        "department": "Finance & Strategy",
    },
    "manager@enterprise.local": {
        "id": "emp-003",
        "name": "David Miller (Department Manager)",
        "email": "manager@enterprise.local",
        "password_hash": hash_password("manager123"),
        "role": "manager",
        "department": "Engineering & Operations",
    },
    "compliance@enterprise.local": {
        "id": "emp-004",
        "name": "Elena Rostova (Compliance Officer)",
        "email": "compliance@enterprise.local",
        "password_hash": hash_password("compliance123"),
        "role": "compliance_officer",
        "department": "Legal & Compliance",
    },
    "admin@enterprise.local": {
        "id": "emp-005",
        "name": "System Administrator",
        "email": "admin@enterprise.local",
        "password_hash": hash_password("admin123"),
        "role": "admin",
        "department": "Information Technology",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str
    workspace_id: Optional[str] = "default"


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    department: str
    access_scopes: List[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RoleItem(BaseModel):
    role: str
    title: str
    department: str
    access_scopes: List[str]
    permissions: List[str]
    description: str


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse, summary="Log in with credentials")
async def login(req: LoginRequest):
    """Authenticate employee credentials and return a signed HMAC-SHA256 JWT access token."""
    email_clean = req.email.strip().lower()
    user_record = DEMO_USERS.get(email_clean)

    if not user_record or not verify_password(req.password, user_record["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Use demo accounts (e.g. employee@enterprise.local / employee123).",
        )

    role = user_record["role"]
    role_info = ROLE_CONFIG.get(role, ROLE_CONFIG["employee"])
    org_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, req.workspace_id or "default")

    token = create_access_token(
        user_id=user_record["id"],
        organization_id=org_uuid,
        role=role,
        access_scopes=role_info["access_scopes"],
        name=user_record["name"],
        email=user_record["email"],
        department=user_record["department"],
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user_record["id"],
            name=user_record["name"],
            email=user_record["email"],
            role=role,
            department=user_record["department"],
            access_scopes=role_info["access_scopes"],
        ),
    )


@router.get("/demo-token", response_model=LoginResponse, summary="Generate instantaneous demo token for UI Persona Switcher")
async def get_demo_token(
    role: str = Query("employee", description="Role to assume: employee, analyst, manager, compliance_officer, admin"),
    workspace_id: str = Query("default", description="Workspace / Tenant ID"),
):
    """
    Rapid persona switcher for Person 4's frontend.
    Allows judges and testers to switch between Junior Employee, Senior Analyst, and Admin in 1 click.
    """
    role_key = role.lower()
    if role_key not in ROLE_CONFIG:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{role}'. Allowed: {list(ROLE_CONFIG.keys())}",
        )

    role_info = ROLE_CONFIG[role_key]
    user_id = f"demo-{role_key}"
    name = role_info["title"]
    email = f"{role_key}@enterprise.local"
    dept = role_info["department"]
    org_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, workspace_id)

    token = create_access_token(
        user_id=user_id,
        organization_id=org_uuid,
        role=role_key,
        access_scopes=role_info["access_scopes"],
        name=name,
        email=email,
        department=dept,
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user_id,
            name=name,
            email=email,
            role=role_key,
            department=dept,
            access_scopes=role_info["access_scopes"],
        ),
    )


@router.get("/roles", response_model=List[RoleItem], summary="List all RBAC roles and permissions")
async def list_roles():
    """Retrieve full matrix of enterprise roles, department clearances, and permissions."""
    return [
        RoleItem(
            role=key,
            title=cfg["title"],
            department=cfg["department"],
            access_scopes=cfg["access_scopes"],
            permissions=cfg["permissions"],
            description=cfg["description"],
        )
        for key, cfg in ROLE_CONFIG.items()
    ]


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
async def get_me(user: UserPayload = Depends(get_current_user)):
    """Retrieve authenticated user's profile and active clearance scopes."""
    return UserResponse(
        id=user.user_id,
        name=user.name or f"User {user.user_id}",
        email=user.email or f"{user.user_id}@enterprise.local",
        role=user.role,
        department=user.department or "Operations",
        access_scopes=user.access_scopes,
    )
