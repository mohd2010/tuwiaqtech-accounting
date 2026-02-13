from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.accounting import Account, AccountType, TransactionSplit
from backend.app.schemas.accounts import AccountCreate, AccountOut, AccountUpdate
from backend.app.services.audit import log_action

# Account-type code ranges (first digit)
_TYPE_PREFIX: dict[AccountType, str] = {
    AccountType.ASSET: "1",
    AccountType.LIABILITY: "2",
    AccountType.EQUITY: "3",
    AccountType.REVENUE: "4",
    AccountType.EXPENSE: "5",
}

# Debit-normal types: balance = debits - credits
_DEBIT_NORMAL = {AccountType.ASSET, AccountType.EXPENSE}


def _compute_balance(db: Session, account_id: UUID, account_type: AccountType) -> Decimal:
    row = (
        db.query(
            func.coalesce(func.sum(TransactionSplit.debit_amount), Decimal("0")).label("total_debit"),
            func.coalesce(func.sum(TransactionSplit.credit_amount), Decimal("0")).label("total_credit"),
        )
        .filter(TransactionSplit.account_id == account_id)
        .one()
    )
    total_debit: Decimal = row.total_debit
    total_credit: Decimal = row.total_credit

    if account_type in _DEBIT_NORMAL:
        return total_debit - total_credit
    return total_credit - total_debit


def list_accounts(db: Session) -> list[AccountOut]:
    accounts = db.query(Account).order_by(Account.code).all()
    result: list[AccountOut] = []
    for a in accounts:
        balance = _compute_balance(db, a.id, a.account_type)
        result.append(
            AccountOut(
                id=a.id,
                code=a.code,
                name=a.name,
                account_type=a.account_type,
                parent_id=a.parent_id,
                is_active=a.is_active,
                is_system=a.is_system,
                balance=str(balance),
                created_at=a.created_at,
            )
        )
    return result


def get_next_code_suggestion(db: Session, account_type: AccountType) -> str:
    prefix = _TYPE_PREFIX[account_type]
    # Find max code that starts with this prefix
    max_code = (
        db.query(func.max(Account.code))
        .filter(Account.code.like(f"{prefix}%"))
        .scalar()
    )
    if max_code is None:
        return f"{prefix}000"
    next_val = int(max_code) + 10
    return str(next_val)


def create_account(
    db: Session,
    payload: AccountCreate,
    user_id: UUID,
    ip_address: str | None,
) -> AccountOut:
    # Validate unique code
    existing = db.query(Account).filter(Account.code == payload.code).first()
    if existing:
        raise ValueError(f"Account code '{payload.code}' already exists")

    account = Account(
        code=payload.code,
        name=payload.name,
        account_type=payload.account_type,
        parent_id=payload.parent_id,
        is_system=False,
    )
    db.add(account)
    db.flush()

    log_action(
        db,
        user_id=user_id,
        action="INSERT",
        resource_type="accounts",
        resource_id=str(account.id),
        changes={
            "code": payload.code,
            "name": payload.name,
            "account_type": payload.account_type.value,
        },
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(account)

    balance = _compute_balance(db, account.id, account.account_type)
    return AccountOut(
        id=account.id,
        code=account.code,
        name=account.name,
        account_type=account.account_type,
        parent_id=account.parent_id,
        is_active=account.is_active,
        is_system=account.is_system,
        balance=str(balance),
        created_at=account.created_at,
    )


def update_account(
    db: Session,
    account_id: UUID,
    payload: AccountUpdate,
    user_id: UUID,
    ip_address: str | None,
) -> AccountOut:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError("Account not found")
    if account.is_system:
        raise ValueError("System accounts cannot be modified")

    old_values: dict[str, str | bool] = {}
    new_values: dict[str, str | bool] = {}

    if payload.name is not None:
        old_values["name"] = account.name
        account.name = payload.name
        new_values["name"] = payload.name

    if payload.is_active is not None:
        old_values["is_active"] = account.is_active
        account.is_active = payload.is_active
        new_values["is_active"] = payload.is_active

    log_action(
        db,
        user_id=user_id,
        action="UPDATE",
        resource_type="accounts",
        resource_id=str(account.id),
        changes={"old": old_values, "new": new_values},
        ip_address=ip_address,
    )

    db.commit()
    db.refresh(account)

    balance = _compute_balance(db, account.id, account.account_type)
    return AccountOut(
        id=account.id,
        code=account.code,
        name=account.name,
        account_type=account.account_type,
        parent_id=account.parent_id,
        is_active=account.is_active,
        is_system=account.is_system,
        balance=str(balance),
        created_at=account.created_at,
    )


def delete_account(
    db: Session,
    account_id: UUID,
    user_id: UUID,
    ip_address: str | None,
) -> None:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError("Account not found")
    if account.is_system:
        raise ValueError("System accounts cannot be deleted")

    # Check for transaction splits
    split_count = (
        db.query(func.count(TransactionSplit.id))
        .filter(TransactionSplit.account_id == account_id)
        .scalar()
    )
    if split_count and split_count > 0:
        raise ValueError("Cannot delete account with existing transactions")

    log_action(
        db,
        user_id=user_id,
        action="DELETE",
        resource_type="accounts",
        resource_id=str(account.id),
        changes={"code": account.code, "name": account.name},
        ip_address=ip_address,
    )

    db.delete(account)
    db.commit()
