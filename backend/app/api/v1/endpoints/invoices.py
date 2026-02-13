from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.schemas.invoice import (
    CreditInvoiceCreate,
    InvoicePaymentCreate,
)
from backend.app.services.credit_invoice import (
    create_credit_invoice,
    get_credit_invoice_detail,
    list_credit_invoices,
    record_invoice_payment,
)

router = APIRouter()


@router.post("/credit")
def create_invoice(
    body: CreditInvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("invoice:write")),
) -> dict:
    invoice_date = None
    if body.invoice_date:
        invoice_date = datetime(
            body.invoice_date.year,
            body.invoice_date.month,
            body.invoice_date.day,
            tzinfo=timezone.utc,
        )
    try:
        return create_credit_invoice(
            db,
            customer_id=body.customer_id,
            items=[
                {"product_id": item.product_id, "quantity": item.quantity}
                for item in body.items
            ],
            user_id=current_user.id,
            invoice_date=invoice_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/payment")
def make_payment(
    body: InvoicePaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("invoice:write")),
) -> dict:
    payment_date = None
    if body.payment_date:
        payment_date = datetime(
            body.payment_date.year,
            body.payment_date.month,
            body.payment_date.day,
            tzinfo=timezone.utc,
        )
    try:
        return record_invoice_payment(
            db,
            invoice_id=body.invoice_id,
            amount=body.amount,
            payment_method=body.payment_method,
            user_id=current_user.id,
            payment_date=payment_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/")
def list_invoices(
    customer_id: UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("invoice:read")),
) -> list[dict]:
    return list_credit_invoices(db, customer_id=customer_id, status=status_filter)


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("invoice:read")),
) -> dict:
    try:
        return get_credit_invoice_detail(db, invoice_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
