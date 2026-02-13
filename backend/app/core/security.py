from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from backend.app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

# In-memory token deny-list for logout (NCA ECC 2-1)
# In production with multiple replicas, use Redis instead
_revoked_tokens: set[str] = set()


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> str | None:
    """Validate password meets NCA ECC 2-1 complexity requirements.

    Returns error message if invalid, None if valid.
    """
    if len(password) < 12:
        return "Password must be at least 12 characters"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return "Password must contain at least one digit"
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
        return "Password must contain at least one special character"
    return None


def revoke_token(token: str) -> None:
    """Add a token to the deny-list (logout)."""
    _revoked_tokens.add(token)


def is_token_revoked(token: str) -> bool:
    """Check if a token has been revoked."""
    return token in _revoked_tokens


def cleanup_expired_tokens() -> int:
    """Remove expired tokens from the in-memory deny-list.

    Returns the number of tokens removed.
    """
    expired: list[str] = []
    for token in _revoked_tokens:
        try:
            jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            expired.append(token)
        except jwt.JWTError:
            # Malformed tokens can also be cleaned up
            expired.append(token)
    for token in expired:
        _revoked_tokens.discard(token)
    return len(expired)
