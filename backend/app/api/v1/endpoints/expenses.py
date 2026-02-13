from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.schemas.expenses import ExpenseCreate, ExpenseOut
from backend.app.services.expenses import list_expenses, record_expense

router = APIRouter()


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expense:write")),
) -> dict:
    try:
        return record_expense(
            db,
            user_id=current_user.id,
            description=payload.description,
            amount=payload.amount,
            expense_account_id=payload.expense_account_id,
            payment_account_id=payload.payment_account_id,
            date=payload.date,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[ExpenseOut])
def get_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expense:read")),
) -> list[dict]:
    return list_expenses(db)
