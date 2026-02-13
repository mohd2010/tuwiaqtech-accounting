from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.models.inventory import Product, Warehouse
from backend.app.models.pos import Register, Shift, ShiftStatus
from backend.app.schemas.pos import (
    InvoiceOut,
    RegisterOut,
    SaleRequest,
    ScanProductOut,
    ScanRequest,
    ShiftCloseRequest,
    ShiftOpenRequest,
    ShiftOut,
)
from backend.app.services.pos import (
    close_shift,
    get_active_shift,
    list_shifts,
    open_shift,
    process_sale,
)

router = APIRouter()


# ─── POS Sales ───────────────────────────────────────────────────────────────


@router.post("/sale", response_model=InvoiceOut)
def create_sale(
    payload: SaleRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("pos:sale")),
) -> dict:
    # ── Shift guard: user must have an open shift ─────────────────────────
    active = (
        db.query(Shift)
        .filter(Shift.user_id == current_user.id, Shift.status == ShiftStatus.OPEN)
        .first()
    )
    if not active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You must open a shift before processing sales",
        )
    # Resolve warehouse from the active shift's register
    register = db.query(Register).filter(Register.id == active.register_id).first()
    warehouse_id = register.warehouse_id if register else None

    try:
        return process_sale(
            db=db,
            items=payload.items,
            user_id=current_user.id,
            customer_id=payload.customer_id,
            ip_address=request.client.host if request.client else None,
            warehouse_id=warehouse_id,
            payments=payload.payments,
            discount_type=payload.discount_type.value if payload.discount_type else None,
            discount_value=payload.discount_value,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/scan", response_model=ScanProductOut)
def scan_barcode(
    payload: ScanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("pos:sale")),
) -> Product:
    product = db.query(Product).filter(Product.sku == payload.barcode).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


# ─── Registers ───────────────────────────────────────────────────────────────


@router.get("/registers", response_model=list[RegisterOut])
def get_registers(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("pos:sale")),
) -> list[RegisterOut]:
    registers = db.query(Register).order_by(Register.name).all()
    result: list[RegisterOut] = []
    for reg in registers:
        wh_name: str | None = None
        if reg.warehouse_id:
            wh = db.query(Warehouse).filter(Warehouse.id == reg.warehouse_id).first()
            wh_name = wh.name if wh else None
        result.append(
            RegisterOut(
                id=reg.id,
                name=reg.name,
                location=reg.location,
                warehouse_id=reg.warehouse_id,
                warehouse_name=wh_name,
            )
        )
    return result


# ─── Shifts ──────────────────────────────────────────────────────────────────


@router.get("/shifts/active", response_model=ShiftOut | None)
def get_my_active_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("pos:shift")),
) -> ShiftOut | None:
    return get_active_shift(db, current_user.id)


@router.post("/shifts/open", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def open_new_shift(
    payload: ShiftOpenRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("pos:shift")),
) -> ShiftOut:
    try:
        return open_shift(
            db=db,
            user_id=current_user.id,
            register_id=payload.register_id,
            opening_cash=payload.opening_cash,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/shifts/{shift_id}/close", response_model=ShiftOut)
def close_existing_shift(
    shift_id: UUID,
    payload: ShiftCloseRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("pos:shift")),
) -> ShiftOut:
    try:
        return close_shift(
            db=db,
            shift_id=shift_id,
            user_id=current_user.id,
            closing_cash_reported=payload.closing_cash_reported,
            notes=payload.notes,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/shifts", response_model=list[ShiftOut])
def get_all_shifts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("pos:shift_list")),
) -> list[ShiftOut]:
    return list_shifts(db)
