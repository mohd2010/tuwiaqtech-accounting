"""API endpoints for recurring journal entry templates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.services.recurring import (
    create_recurring_entry,
    delete_recurring_entry,
    get_recurring_entry,
    list_recurring_entries,
    post_recurring_entry,
    update_recurring_entry,
    update_recurring_status,
)

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────


class SplitIn(BaseModel):
    account_id: UUID
    amount: Decimal = Field(..., gt=0)
    type: str  # "debit" or "credit"


class RecurringEntryCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    reference_prefix: str | None = None
    frequency: str
    next_run_date: date
    end_date: date | None = None
    splits: list[SplitIn] = Field(..., min_length=2)

    @field_validator("frequency")
    @classmethod
    def valid_frequency(cls, v: str) -> str:
        allowed = {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUALLY"}
        if v not in allowed:
            raise ValueError(f"Frequency must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("splits")
    @classmethod
    def validate_double_entry(cls, v: list[SplitIn]) -> list[SplitIn]:
        total_d = sum(s.amount for s in v if s.type.lower() == "debit")
        total_c = sum(s.amount for s in v if s.type.lower() == "credit")
        if total_d != total_c:
            raise ValueError(f"Double-entry violation: debits ({total_d}) != credits ({total_c})")
        return v


class RecurringEntryUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    reference_prefix: str | None = None
    frequency: str | None = None
    next_run_date: date | None = None
    end_date: date | None = None
    splits: list[SplitIn] | None = None


class StatusUpdateIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in {"ACTIVE", "PAUSED"}:
            raise ValueError("Status must be ACTIVE or PAUSED")
        return v


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _splits_to_dicts(splits: list[SplitIn]) -> list[dict]:
    return [
        {"account_id": s.account_id, "amount": s.amount, "type": s.type}
        for s in splits
    ]


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("")
def list_entries(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("recurring:read")),
) -> list[dict]:
    return list_recurring_entries(db)


@router.get("/{entry_id}")
def get_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("recurring:read")),
) -> dict:
    try:
        return get_recurring_entry(db, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_entry(
    body: RecurringEntryCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("recurring:write")),
) -> dict:
    try:
        entry = create_recurring_entry(
            db,
            name=body.name,
            description=body.description,
            reference_prefix=body.reference_prefix,
            frequency=body.frequency,
            next_run_date=body.next_run_date,
            end_date=body.end_date,
            splits=_splits_to_dicts(body.splits),
            user_id=current_user.id,
        )
        db.commit()
        return get_recurring_entry(db, entry.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{entry_id}")
def update_entry(
    entry_id: UUID,
    body: RecurringEntryUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("recurring:write")),
) -> dict:
    try:
        update_recurring_entry(
            db,
            entry_id=entry_id,
            user_id=current_user.id,
            name=body.name,
            description=body.description,
            reference_prefix=body.reference_prefix,
            frequency=body.frequency,
            next_run_date=body.next_run_date,
            end_date=body.end_date,
            splits=_splits_to_dicts(body.splits) if body.splits is not None else None,
        )
        db.commit()
        return get_recurring_entry(db, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{entry_id}/status")
def patch_status(
    entry_id: UUID,
    body: StatusUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("recurring:write")),
) -> dict:
    try:
        update_recurring_status(
            db,
            entry_id=entry_id,
            new_status=body.status,
            user_id=current_user.id,
        )
        db.commit()
        return get_recurring_entry(db, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("recurring:write")),
) -> None:
    try:
        delete_recurring_entry(db, entry_id=entry_id, user_id=current_user.id)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{entry_id}/post", status_code=status.HTTP_201_CREATED)
def post_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("recurring:write")),
) -> dict:
    try:
        result = post_recurring_entry(db, entry_id=entry_id, user_id=current_user.id)
        db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
