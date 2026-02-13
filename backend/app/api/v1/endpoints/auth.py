from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import (
    create_access_token,
    revoke_token,
    verify_password,
)
from backend.app.middleware.rate_limit import InMemoryRateLimiter
from backend.app.models.accounting import User
from backend.app.services.audit import log_action

router = APIRouter()

# ─── Rate Limiting (NCA ECC 2-1) ─────────────────────────────────────────────
# In-memory per-IP rate limiter. For multi-replica, use Redis.
_login_limiter = InMemoryRateLimiter(window_seconds=60, max_attempts=5)


@router.post("/login/access-token")
def login_access_token(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> dict[str, str]:
    ip = request.client.host if request.client else "unknown"

    # Rate limit by IP (NCA ECC 2-1)
    _login_limiter.check(ip)

    user = db.query(User).filter(User.username == form_data.username).first()

    # Check account lockout (NCA ECC 2-1)
    if user and user.locked_until:
        if datetime.now(timezone.utc) < user.locked_until:
            remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() // 60) + 1
            log_action(
                db,
                user_id=user.id,
                action="LOGIN_BLOCKED",
                resource_type="auth",
                resource_id=form_data.username,
                ip_address=ip,
                changes={"reason": "account_locked"},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked. Try again in {remaining} minutes.",
            )
        # Lockout expired — reset
        user.failed_login_attempts = 0
        user.locked_until = None

    if not user or not verify_password(form_data.password, user.hashed_password):
        # Track failed attempts for lockout
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.LOCKOUT_MINUTES
                )
                log_action(
                    db,
                    user_id=user.id,
                    action="ACCOUNT_LOCKED",
                    resource_type="auth",
                    resource_id=form_data.username,
                    ip_address=ip,
                    changes={"failed_attempts": user.failed_login_attempts},
                )

        log_action(
            db,
            user_id=user.id if user else None,
            action="LOGIN_FAILED",
            resource_type="auth",
            resource_id=form_data.username,
            ip_address=ip,
            changes={"reason": "invalid_credentials"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        log_action(
            db,
            user_id=user.id,
            action="LOGIN_FAILED",
            resource_type="auth",
            resource_id=form_data.username,
            ip_address=ip,
            changes={"reason": "inactive_user"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None

    log_action(
        db,
        user_id=user.id,
        action="LOGIN_SUCCESS",
        resource_type="auth",
        resource_id=str(user.id),
        ip_address=ip,
        changes={"username": user.username, "role": user.role.value},
    )
    db.commit()

    return {
        "access_token": create_access_token(subject=str(user.id)),
        "token_type": "bearer",
    }


# ─── Logout (NCA ECC 2-1 — Session Management) ──────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/access-token")


@router.post("/logout")
def logout(token: str = Depends(oauth2_scheme)) -> dict[str, str]:
    """Invalidate the current access token."""
    revoke_token(token)
    return {"detail": "Logged out successfully"}
