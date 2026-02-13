from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import AuditLog, User

router = APIRouter()


class AuditLogOut(BaseModel):
    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str
    changes: dict[str, Any] | None
    ip_address: str | None
    timestamp: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=list[AuditLogOut])
def list_audit_logs(
    user_id: UUID | None = Query(None, description="Filter by user ID"),
    action: str | None = Query(None, description="Filter by action type (e.g. LOGIN_SUCCESS, SALE_COMPLETED)"),
    resource_type: str | None = Query(None, description="Filter by resource type (e.g. auth, sales, products)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("audit:read")),
) -> list[dict]:
    query = db.query(AuditLog)

    if user_id is not None:
        query = query.filter(AuditLog.changed_by == user_id)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if resource_type is not None:
        query = query.filter(AuditLog.table_name == resource_type)

    rows = (
        query.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        AuditLogOut(
            id=r.id,
            user_id=r.changed_by,
            action=r.action,
            resource_type=r.table_name,
            resource_id=r.record_id,
            changes=r.new_values,
            ip_address=r.ip_address,
            timestamp=r.created_at,
        )
        for r in rows
    ]
