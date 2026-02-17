from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import Account, JournalEntry, User
from backend.app.schemas.accounting import (
    JournalEntryCreate,
    PaginatedJournalResponse,
)
from backend.app.services.journal import create_journal_entry

router = APIRouter()


@router.get("/accounts")
def list_accounts(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("account:read")),
) -> list[dict[str, str]]:
    accounts = db.query(Account).order_by(Account.code).all()
    return [
        {
            "id": str(a.id),
            "code": a.code,
            "name": a.name,
            "account_type": a.account_type.value,
        }
        for a in accounts
    ]


@router.get("/entries", response_model=PaginatedJournalResponse)
def list_entries(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("journal:read")),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str = Query("", max_length=200),
    sort: str = Query("newest", pattern="^(newest|oldest)$"),
) -> dict:
    query = db.query(JournalEntry)

    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                JournalEntry.description.ilike(term),
                JournalEntry.reference.ilike(term),
            )
        )

    total = query.count()

    if sort == "oldest":
        query = query.order_by(JournalEntry.created_at.asc())
    else:
        query = query.order_by(JournalEntry.created_at.desc())

    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    return {"items": items, "total": total}


@router.post("/entries")
def create_entry(
    entry: JournalEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("journal:write")),
) -> dict[str, str]:
    journal = create_journal_entry(db=db, entry=entry, user_id=current_user.id)
    return {"id": str(journal.id), "description": journal.description}
