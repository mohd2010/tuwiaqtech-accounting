from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.accounting import AuditLog


def log_action(
    db: Session,
    *,
    user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str,
    changes: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Write a single row to the audit_logs table.

    This is a thin utility so every service logs in a consistent format.
    It does NOT call db.commit() — the caller is responsible for committing
    as part of its own transaction.
    """
    db.add(
        AuditLog(
            table_name=resource_type,
            record_id=resource_id,
            action=action,
            changed_by=user_id,
            new_values=changes,
            ip_address=ip_address,
        )
    )
