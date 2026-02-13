"""Granular permission dependencies (EventFlow-style).

Usage in endpoints::

    @router.post("")
    def create_account(
        body: AccountCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_permission("account:write")),
    ):
        ...
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.permission import Permission, RolePermission
from backend.app.models.user import User

from backend.app.api.deps import get_current_user


def _load_user_permissions(db: Session, user: User) -> set[str]:
    """Return the set of permission codes assigned to *user* via their role."""
    if user.role_id is None:
        return set()
    rows = (
        db.query(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .filter(RolePermission.role_id == user.role_id)
        .all()
    )
    return {r[0] for r in rows}


def require_permission(*permission_codes: str):
    """FastAPI dependency factory — checks user has **all** listed permissions.

    Returns the authenticated ``User`` so the endpoint can use it::

        current_user = Depends(require_permission("account:write"))
    """

    def _checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        user_perms = _load_user_permissions(db, current_user)
        missing = set(permission_codes) - user_perms
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(sorted(missing))}",
            )
        return current_user

    return _checker
