from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.services.fiscal_close import list_fiscal_closes, perform_fiscal_close

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────


class FiscalCloseOut(BaseModel):
    id: UUID
    fiscal_year: int
    close_date: str
    closing_entry_id: UUID
    closed_by: UUID
    closed_at: str
    notes: str | None

    class Config:
        from_attributes = True


class FiscalCloseRequest(BaseModel):
    fiscal_year: int = Field(..., ge=2000, le=2099)
    notes: str | None = None


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("", response_model=list[FiscalCloseOut])
def get_fiscal_closes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fiscal:close")),
) -> list[dict[str, object]]:
    """List all fiscal closes. Admin only."""
    closes = list_fiscal_closes(db)
    return [
        {
            "id": fc.id,
            "fiscal_year": fc.fiscal_year,
            "close_date": fc.close_date.isoformat(),
            "closing_entry_id": fc.closing_entry_id,
            "closed_by": fc.closed_by,
            "closed_at": fc.closed_at.isoformat() if fc.closed_at else "",
            "notes": fc.notes,
        }
        for fc in closes
    ]


@router.post("", response_model=FiscalCloseOut, status_code=status.HTTP_201_CREATED)
def close_fiscal_year(
    body: FiscalCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fiscal:close")),
) -> dict[str, object]:
    """Close a fiscal year. Admin only.

    Creates a closing journal entry that zeros out all Revenue and Expense
    accounts into Retained Earnings (3000).
    """
    try:
        fc = perform_fiscal_close(
            db,
            fiscal_year=body.fiscal_year,
            admin_id=current_user.id,
            notes=body.notes,
        )
        db.commit()
        return {
            "id": fc.id,
            "fiscal_year": fc.fiscal_year,
            "close_date": fc.close_date.isoformat(),
            "closing_entry_id": fc.closing_entry_id,
            "closed_by": fc.closed_by,
            "closed_at": fc.closed_at.isoformat() if fc.closed_at else "",
            "notes": fc.notes,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
