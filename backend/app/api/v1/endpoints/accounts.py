from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import AccountType, User
from backend.app.schemas.accounts import AccountCreate, AccountOut, AccountUpdate
from backend.app.services.accounts import (
    create_account,
    delete_account,
    get_next_code_suggestion,
    list_accounts,
    update_account,
)

router = APIRouter()


@router.get("", response_model=list[AccountOut])
def get_accounts(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("account:read")),
) -> list[AccountOut]:
    return list_accounts(db)


@router.get("/next-code")
def next_code(
    account_type: AccountType,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("account:read")),
) -> dict[str, str]:
    code = get_next_code_suggestion(db, account_type)
    return {"code": code}


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def post_account(
    payload: AccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("account:write")),
) -> AccountOut:
    try:
        return create_account(
            db,
            payload=payload,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{account_id}", response_model=AccountOut)
def patch_account(
    account_id: UUID,
    payload: AccountUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("account:write")),
) -> AccountOut:
    try:
        return update_account(
            db,
            account_id=account_id,
            payload=payload,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_account(
    account_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("account:write")),
) -> None:
    try:
        delete_account(
            db,
            account_id=account_id,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
