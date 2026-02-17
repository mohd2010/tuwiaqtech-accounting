from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.core.security import validate_password_strength
from backend.app.models.accounting import RoleEnum, User
from backend.app.models.organization import Organization
from backend.app.services.user_management import (
    change_own_password,
    create_user,
    list_users,
    reset_password,
    toggle_user_active,
    update_user,
)

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────


class UserOut(BaseModel):
    id: UUID
    username: str
    role: str
    is_active: bool
    permissions: list[str] = []
    org_configured: bool = False

    class Config:
        from_attributes = True


def _validate_pw(v: str) -> str:
    error = validate_password_strength(v)
    if error:
        raise ValueError(error)
    return v


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=12, max_length=128)
    role: RoleEnum

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        return _validate_pw(v)


class UserUpdate(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=150)
    role: RoleEnum | None = None


class ResetPasswordIn(BaseModel):
    new_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        return _validate_pw(v)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        return _validate_pw(v)


class MessageOut(BaseModel):
    detail: str


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/me", response_model=UserOut)
def read_current_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    from backend.app.api.permission_deps import _load_user_permissions
    perms = sorted(_load_user_permissions(db, current_user))
    org_configured = db.query(Organization.id).first() is not None
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "permissions": perms,
        "org_configured": org_configured,
    }


@router.get("", response_model=list[UserOut])
def list_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage")),
) -> list[User]:
    """List all users. Admin only."""
    return list_users(db)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_new_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage")),
) -> User:
    """Create a new user account. Admin only."""
    try:
        user = create_user(
            db,
            username=body.username,
            password=body.password,
            role=body.role,
            admin_id=current_user.id,
        )
        db.commit()
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )


@router.patch("/{user_id}", response_model=UserOut)
def update_existing_user(
    user_id: UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage")),
) -> User:
    """Update a user's username and/or role. Admin only."""
    try:
        user = update_user(
            db,
            user_id=user_id,
            username=body.username,
            role=body.role,
            admin_id=current_user.id,
        )
        db.commit()
        return user
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )


@router.patch("/{user_id}/toggle-active", response_model=UserOut)
def toggle_active(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage")),
) -> User:
    """Toggle a user's active status. Admin only."""
    try:
        user = toggle_user_active(
            db, user_id=user_id, admin_id=current_user.id
        )
        db.commit()
        return user
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.post("/{user_id}/reset-password", response_model=MessageOut)
def admin_reset_password(
    user_id: UUID,
    body: ResetPasswordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user:manage")),
) -> dict[str, str]:
    """Admin resets a user's password."""
    try:
        reset_password(
            db,
            user_id=user_id,
            new_password=body.new_password,
            admin_id=current_user.id,
        )
        db.commit()
        return {"detail": "Password reset successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )


@router.post("/change-password", response_model=MessageOut)
def change_my_password(
    body: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Change own password. Any authenticated user."""
    try:
        change_own_password(
            db,
            user_id=current_user.id,
            current_password=body.current_password,
            new_password=body.new_password,
        )
        db.commit()
        return {"detail": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
