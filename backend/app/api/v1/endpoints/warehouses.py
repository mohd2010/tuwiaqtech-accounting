from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.schemas.warehouse import (
    TransferCreate,
    TransferOut,
    WarehouseCreate,
    WarehouseOut,
    WarehouseStockOut,
    WarehouseUpdate,
)
from backend.app.services.warehouse import (
    cancel_transfer,
    create_transfer,
    create_warehouse,
    get_warehouse_stock,
    list_transfers,
    list_warehouses,
    receive_transfer,
    ship_transfer,
    update_warehouse,
)

router = APIRouter()


# ─── Warehouses ───────────────────────────────────────────────────────────────


@router.get("", response_model=list[WarehouseOut])
def get_warehouses(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("warehouse:read")),
) -> list[WarehouseOut]:
    return list_warehouses(db)


@router.post("", response_model=WarehouseOut, status_code=status.HTTP_201_CREATED)
def create_new_warehouse(
    payload: WarehouseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouse:write")),
) -> WarehouseOut:
    try:
        return create_warehouse(
            db=db,
            data=payload,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{warehouse_id}", response_model=WarehouseOut)
def update_existing_warehouse(
    warehouse_id: UUID,
    payload: WarehouseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouse:write")),
) -> WarehouseOut:
    try:
        return update_warehouse(
            db=db,
            warehouse_id=warehouse_id,
            data=payload,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{warehouse_id}/stock", response_model=list[WarehouseStockOut])
def get_stock_at_warehouse(
    warehouse_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouse:read")),
) -> list[WarehouseStockOut]:
    try:
        return get_warehouse_stock(db, warehouse_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── Transfers ────────────────────────────────────────────────────────────────


@router.get("/transfers", response_model=list[TransferOut])
def get_transfers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouse:write")),
) -> list[TransferOut]:
    return list_transfers(db)


@router.post("/transfers", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def create_new_transfer(
    payload: TransferCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouse:write")),
) -> TransferOut:
    try:
        return create_transfer(
            db=db,
            data=payload,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/transfers/{transfer_id}/ship", response_model=TransferOut)
def ship_existing_transfer(
    transfer_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouse:write")),
) -> TransferOut:
    try:
        return ship_transfer(
            db=db,
            transfer_id=transfer_id,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/transfers/{transfer_id}/receive", response_model=TransferOut)
def receive_existing_transfer(
    transfer_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouse:write")),
) -> TransferOut:
    try:
        return receive_transfer(
            db=db,
            transfer_id=transfer_id,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/transfers/{transfer_id}/cancel", response_model=TransferOut)
def cancel_existing_transfer(
    transfer_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("warehouse:write")),
) -> TransferOut:
    try:
        return cancel_transfer(
            db=db,
            transfer_id=transfer_id,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
