"""One-time script to create an admin user.

Usage:
    python -m backend.create_admin
"""

from __future__ import annotations

import getpass

from sqlalchemy import func

from backend.app.core.database import SessionLocal
from backend.app.core.security import get_password_hash, validate_password_strength

# Import all models so SQLAlchemy resolves relationships
import backend.app.models.accounting  # noqa: F401
import backend.app.models.journal  # noqa: F401
import backend.app.models.permission  # noqa: F401

from backend.app.models.user import RoleEnum, User
from backend.app.models.permission import Role


def main() -> None:
    username = input("Username [admin]: ").strip() or "admin"
    password = getpass.getpass("Password: ")
    if not password:
        print("Error: password cannot be empty.")
        return
    pw_error = validate_password_strength(password)
    if pw_error:
        print(f"Error: {pw_error}")
        return

    db = SessionLocal()
    try:
        # Check if user already exists
        existing = db.query(User).filter(
            func.lower(User.username) == username.lower()
        ).first()
        if existing:
            # Reset password, unlock, activate, and ensure role_id is set
            existing.hashed_password = get_password_hash(password)
            existing.is_active = True
            existing.failed_login_attempts = 0
            existing.locked_until = None
            admin_role = db.query(Role).filter(Role.name == "ADMIN").first()
            if admin_role and existing.role_id != admin_role.id:
                existing.role_id = admin_role.id
            db.commit()
            print(f"Admin user already exists — password reset!")
            print(f"  ID:       {existing.id}")
            print(f"  Username: {username}")
            print(f"  Role:     ADMIN")
            return

        # Look up the ADMIN role (created by the permissions migration)
        admin_role = db.query(Role).filter(Role.name == "ADMIN").first()

        user = User(
            username=username,
            hashed_password=get_password_hash(password),
            role=RoleEnum.ADMIN,
            role_id=admin_role.id if admin_role else None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"Admin user created successfully!")
        print(f"  ID:       {user.id}")
        print(f"  Username: {username}")
        print(f"  Role:     ADMIN")
        if admin_role:
            print(f"  Role ID:  {admin_role.id} (all 38 permissions)")
        else:
            print("  WARNING:  ADMIN role not found — run the permissions migration first.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
