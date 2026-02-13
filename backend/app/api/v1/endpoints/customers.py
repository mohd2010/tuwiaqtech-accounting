from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import JournalEntry, User
from backend.app.models.customer import Customer, Sale
from backend.app.models.inventory import Product
from backend.app.schemas.customer import (
    CustomerCreate,
    CustomerDetailOut,
    CustomerOut,
    CustomerUpdate,
    SaleOut,
)

router = APIRouter()


@router.get("/", response_model=list[CustomerOut])
def list_customers(
    q: str | None = Query(None, description="Search by name, email, or phone"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("sales:read")),
) -> list[Customer]:
    query = db.query(Customer)
    if q:
        like = f"%{q}%"
        query = query.filter(
            Customer.name.ilike(like)
            | Customer.email.ilike(like)
            | Customer.phone.ilike(like)
        )
    return query.order_by(Customer.name).all()


@router.post("/", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("sales:read")),
) -> Customer:
    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("sales:read")),
) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("sales:read")),
) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}/history", response_model=CustomerDetailOut)
def customer_history(
    customer_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("sales:read")),
) -> dict:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    sales = (
        db.query(Sale, JournalEntry.reference, Product.name.label("product_name"))
        .join(JournalEntry, Sale.journal_entry_id == JournalEntry.id)
        .join(Product, Sale.product_id == Product.id)
        .filter(Sale.customer_id == customer_id)
        .order_by(Sale.created_at.desc())
        .all()
    )

    purchases = [
        SaleOut(
            id=sale.id,
            invoice_number=je_ref or "",
            product_name=prod_name,
            quantity=sale.quantity,
            total_amount=str(sale.total_amount),
            date=sale.created_at,
        )
        for sale, je_ref, prod_name in sales
    ]

    return CustomerDetailOut(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        vat_number=customer.vat_number,
        total_spent=str(customer.total_spent),
        last_purchase_at=customer.last_purchase_at,
        purchases=purchases,
    )
