"""User management service — CRUD operations for user accounts.

All mutations are audit-logged. This module does NOT call db.commit();
the caller (endpoint) is responsible for committing.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash, verify_password
from backend.app.models.accounting import RoleEnum, User
from backend.app.models.permission import Role
from backend.app.services.audit import log_action


def list_users(db: Session) -> list[User]:
    """Return all users ordered by creation date descending."""
    return (
        db.query(User)
        .order_by(User.created_at.desc())
        .all()
    )


def get_user(db: Session, user_id: UUID) -> User | None:
    """Return a single user by ID or None."""
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    role: RoleEnum,
    admin_id: UUID,
) -> User:
    """Create a new user account. Raises ValueError if username taken."""
    existing = db.query(User).filter(
        func.lower(User.username) == username.lower()
    ).first()
    if existing:
        raise ValueError("Username already exists")

    # Look up granular Role record matching the enum name
    role_record = db.query(Role).filter(Role.name == role.value).first()

    user = User(
        username=username,
        hashed_password=get_password_hash(password),
        role=role,
        role_id=role_record.id if role_record else None,
    )
    db.add(user)
    db.flush()

    log_action(
        db,
        user_id=admin_id,
        action="USER_CREATED",
        resource_type="users",
        resource_id=str(user.id),
        changes={"username": username, "role": role.value},
    )
    return user


def update_user(
    db: Session,
    *,
    user_id: UUID,
    username: str | None = None,
    role: RoleEnum | None = None,
    admin_id: UUID,
) -> User:
    """Update a user's username and/or role. Raises ValueError on conflicts."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    changes: dict[str, object] = {}

    if username is not None and username != user.username:
        existing = db.query(User).filter(
            func.lower(User.username) == username.lower(),
            User.id != user_id,
        ).first()
        if existing:
            raise ValueError("Username already exists")
        changes["username"] = {"old": user.username, "new": username}
        user.username = username

    if role is not None and role != user.role:
        changes["role"] = {"old": user.role.value, "new": role.value}
        user.role = role
        role_record = db.query(Role).filter(Role.name == role.value).first()
        user.role_id = role_record.id if role_record else None

    if changes:
        db.flush()
        log_action(
            db,
            user_id=admin_id,
            action="USER_UPDATED",
            resource_type="users",
            resource_id=str(user.id),
            changes=changes,
        )

    return user


def toggle_user_active(
    db: Session,
    *,
    user_id: UUID,
    admin_id: UUID,
) -> User:
    """Toggle a user's is_active flag. Admins cannot deactivate themselves."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    if user_id == admin_id and user.is_active:
        raise ValueError("Cannot deactivate yourself")

    user.is_active = not user.is_active
    db.flush()

    log_action(
        db,
        user_id=admin_id,
        action="USER_TOGGLED_ACTIVE",
        resource_type="users",
        resource_id=str(user.id),
        changes={"is_active": user.is_active},
    )
    return user


def reset_password(
    db: Session,
    *,
    user_id: UUID,
    new_password: str,
    admin_id: UUID,
) -> User:
    """Admin resets a user's password."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    user.hashed_password = get_password_hash(new_password)
    db.flush()

    log_action(
        db,
        user_id=admin_id,
        action="USER_PASSWORD_RESET",
        resource_type="users",
        resource_id=str(user.id),
        changes={"reset_by": str(admin_id)},
    )
    return user


def change_own_password(
    db: Session,
    *,
    user_id: UUID,
    current_password: str,
    new_password: str,
) -> User:
    """User changes their own password. Raises ValueError if current is wrong."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    if not verify_password(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect")

    user.hashed_password = get_password_hash(new_password)
    db.flush()

    log_action(
        db,
        user_id=user_id,
        action="USER_PASSWORD_CHANGED",
        resource_type="users",
        resource_id=str(user_id),
    )
    return user
