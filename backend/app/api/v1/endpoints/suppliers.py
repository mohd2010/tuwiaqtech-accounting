from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.models.supplier import Supplier
from backend.app.schemas.supplier import SupplierCreate, SupplierOut
from backend.app.services.supplier_payment import get_supplier_balance, pay_supplier_invoice

router = APIRouter()


class PaymentRequest(BaseModel):
    amount: Decimal
    payment_account_id: UUID

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


@router.get("/", response_model=list[SupplierOut])
def list_suppliers(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("supplier:read")),
) -> list[Supplier]:
    return db.query(Supplier).order_by(Supplier.name).all()


@router.post("/", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("supplier:write")),
) -> Supplier:
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("supplier:read")),
) -> Supplier:
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.get("/{supplier_id}/balance")
def supplier_balance(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("supplier:read")),
) -> dict[str, str]:
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    balance = get_supplier_balance(db, supplier_id)
    return {"supplier_id": str(supplier_id), "balance": str(balance)}


@router.post("/{supplier_id}/pay")
def pay_supplier(
    supplier_id: UUID,
    payload: PaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("supplier:write")),
) -> dict[str, str]:
    try:
        return pay_supplier_invoice(
            db=db,
            supplier_id=supplier_id,
            amount=payload.amount,
            payment_account_id=payload.payment_account_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
