from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.accounting import User
from backend.app.models.inventory import (
    Product,
    StockTransfer,
    StockTransferItem,
    TransferStatus,
    Warehouse,
    WarehouseStock,
)
from backend.app.schemas.warehouse import (
    TransferCreate,
    TransferItemOut,
    TransferOut,
    WarehouseCreate,
    WarehouseOut,
    WarehouseStockOut,
    WarehouseUpdate,
)
from backend.app.services.audit import log_action


# ─── Warehouse CRUD ───────────────────────────────────────────────────────────


def create_warehouse(
    db: Session,
    data: WarehouseCreate,
    user_id: UUID,
    ip_address: str | None = None,
) -> WarehouseOut:
    wh = Warehouse(name=data.name, address=data.address)
    db.add(wh)
    db.flush()

    log_action(
        db,
        user_id=user_id,
        action="WAREHOUSE_CREATED",
        resource_type="warehouses",
        resource_id=str(wh.id),
        ip_address=ip_address,
        changes={"name": data.name, "address": data.address},
    )

    db.commit()
    db.refresh(wh)
    return WarehouseOut.model_validate(wh)


def update_warehouse(
    db: Session,
    warehouse_id: UUID,
    data: WarehouseUpdate,
    user_id: UUID,
    ip_address: str | None = None,
) -> WarehouseOut:
    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not wh:
        raise ValueError("Warehouse not found")

    changes: dict[str, object] = {}
    if data.name is not None:
        changes["name"] = {"from": wh.name, "to": data.name}
        wh.name = data.name
    if data.address is not None:
        changes["address"] = {"from": wh.address, "to": data.address}
        wh.address = data.address
    if data.is_active is not None:
        changes["is_active"] = {"from": wh.is_active, "to": data.is_active}
        wh.is_active = data.is_active

    log_action(
        db,
        user_id=user_id,
        action="WAREHOUSE_UPDATED",
        resource_type="warehouses",
        resource_id=str(wh.id),
        ip_address=ip_address,
        changes=changes,
    )

    db.commit()
    db.refresh(wh)
    return WarehouseOut.model_validate(wh)


def list_warehouses(db: Session) -> list[WarehouseOut]:
    rows = db.query(Warehouse).filter(Warehouse.is_active.is_(True)).order_by(Warehouse.name).all()
    return [WarehouseOut.model_validate(w) for w in rows]


def get_warehouse_stock(db: Session, warehouse_id: UUID) -> list[WarehouseStockOut]:
    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not wh:
        raise ValueError("Warehouse not found")

    rows = (
        db.query(WarehouseStock, Product.name, Product.sku)
        .join(Product, WarehouseStock.product_id == Product.id)
        .filter(WarehouseStock.warehouse_id == warehouse_id, WarehouseStock.quantity > 0)
        .order_by(Product.name)
        .all()
    )
    return [
        WarehouseStockOut(
            product_id=ws.product_id,
            product_name=name,
            product_sku=sku,
            quantity=ws.quantity,
        )
        for ws, name, sku in rows
    ]


# ─── Transfer Lifecycle ───────────────────────────────────────────────────────


def create_transfer(
    db: Session,
    data: TransferCreate,
    user_id: UUID,
    ip_address: str | None = None,
) -> TransferOut:
    # Validate warehouses exist
    from_wh = db.query(Warehouse).filter(Warehouse.id == data.from_warehouse_id).first()
    if not from_wh:
        raise ValueError("Source warehouse not found")
    to_wh = db.query(Warehouse).filter(Warehouse.id == data.to_warehouse_id).first()
    if not to_wh:
        raise ValueError("Destination warehouse not found")
    if data.from_warehouse_id == data.to_warehouse_id:
        raise ValueError("Source and destination warehouses must be different")

    # Validate and deduct stock from source
    transfer = StockTransfer(
        from_warehouse_id=data.from_warehouse_id,
        to_warehouse_id=data.to_warehouse_id,
        status=TransferStatus.PENDING,
        notes=data.notes,
        created_by=user_id,
    )
    db.add(transfer)
    db.flush()

    for item in data.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise ValueError(f"Product {item.product_id} not found")

        ws = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == data.from_warehouse_id,
                WarehouseStock.product_id == item.product_id,
            )
            .first()
        )
        available = ws.quantity if ws else 0
        if available < item.quantity:
            raise ValueError(
                f"Insufficient stock for '{product.name}' at source warehouse: "
                f"{available} available, {item.quantity} requested"
            )

        # Deduct from source warehouse_stock
        ws.quantity -= item.quantity
        # Deduct from global product.current_stock
        product.current_stock -= item.quantity

        db.add(
            StockTransferItem(
                transfer_id=transfer.id,
                product_id=item.product_id,
                quantity=item.quantity,
            )
        )

    log_action(
        db,
        user_id=user_id,
        action="TRANSFER_CREATED",
        resource_type="stock_transfers",
        resource_id=str(transfer.id),
        ip_address=ip_address,
        changes={
            "from_warehouse": from_wh.name,
            "to_warehouse": to_wh.name,
            "item_count": len(data.items),
        },
    )

    db.commit()
    db.refresh(transfer)
    return _transfer_to_out(db, transfer)


def ship_transfer(
    db: Session,
    transfer_id: UUID,
    user_id: UUID,
    ip_address: str | None = None,
) -> TransferOut:
    transfer = db.query(StockTransfer).filter(StockTransfer.id == transfer_id).first()
    if not transfer:
        raise ValueError("Transfer not found")
    if transfer.status != TransferStatus.PENDING:
        raise ValueError(f"Cannot ship transfer with status {transfer.status.value}")

    transfer.status = TransferStatus.SHIPPED

    log_action(
        db,
        user_id=user_id,
        action="TRANSFER_SHIPPED",
        resource_type="stock_transfers",
        resource_id=str(transfer.id),
        ip_address=ip_address,
        changes={"status": "SHIPPED"},
    )

    db.commit()
    db.refresh(transfer)
    return _transfer_to_out(db, transfer)


def receive_transfer(
    db: Session,
    transfer_id: UUID,
    user_id: UUID,
    ip_address: str | None = None,
) -> TransferOut:
    transfer = db.query(StockTransfer).filter(StockTransfer.id == transfer_id).first()
    if not transfer:
        raise ValueError("Transfer not found")
    if transfer.status not in (TransferStatus.PENDING, TransferStatus.SHIPPED):
        raise ValueError(f"Cannot receive transfer with status {transfer.status.value}")

    for item in transfer.items:
        # Get or create destination warehouse_stock
        ws = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == transfer.to_warehouse_id,
                WarehouseStock.product_id == item.product_id,
            )
            .first()
        )
        if not ws:
            ws = WarehouseStock(
                warehouse_id=transfer.to_warehouse_id,
                product_id=item.product_id,
                quantity=0,
            )
            db.add(ws)
            db.flush()

        ws.quantity += item.quantity

        # Restore to global product.current_stock (was deducted on create)
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            product.current_stock += item.quantity

    transfer.status = TransferStatus.RECEIVED

    log_action(
        db,
        user_id=user_id,
        action="TRANSFER_RECEIVED",
        resource_type="stock_transfers",
        resource_id=str(transfer.id),
        ip_address=ip_address,
        changes={"status": "RECEIVED"},
    )

    db.commit()
    db.refresh(transfer)
    return _transfer_to_out(db, transfer)


def cancel_transfer(
    db: Session,
    transfer_id: UUID,
    user_id: UUID,
    ip_address: str | None = None,
) -> TransferOut:
    transfer = db.query(StockTransfer).filter(StockTransfer.id == transfer_id).first()
    if not transfer:
        raise ValueError("Transfer not found")
    if transfer.status not in (TransferStatus.PENDING, TransferStatus.SHIPPED):
        raise ValueError(f"Cannot cancel transfer with status {transfer.status.value}")

    # Return stock to source
    for item in transfer.items:
        ws = (
            db.query(WarehouseStock)
            .filter(
                WarehouseStock.warehouse_id == transfer.from_warehouse_id,
                WarehouseStock.product_id == item.product_id,
            )
            .first()
        )
        if ws:
            ws.quantity += item.quantity

        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            product.current_stock += item.quantity

    transfer.status = TransferStatus.CANCELLED

    log_action(
        db,
        user_id=user_id,
        action="TRANSFER_CANCELLED",
        resource_type="stock_transfers",
        resource_id=str(transfer.id),
        ip_address=ip_address,
        changes={"status": "CANCELLED"},
    )

    db.commit()
    db.refresh(transfer)
    return _transfer_to_out(db, transfer)


def list_transfers(db: Session) -> list[TransferOut]:
    rows = (
        db.query(StockTransfer)
        .order_by(StockTransfer.created_at.desc())
        .limit(100)
        .all()
    )
    return [_transfer_to_out(db, t) for t in rows]


def _transfer_to_out(db: Session, transfer: StockTransfer) -> TransferOut:
    from_wh = db.query(Warehouse).filter(Warehouse.id == transfer.from_warehouse_id).first()
    to_wh = db.query(Warehouse).filter(Warehouse.id == transfer.to_warehouse_id).first()
    user = db.query(User).filter(User.id == transfer.created_by).first()

    items_out: list[TransferItemOut] = []
    for item in transfer.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        items_out.append(
            TransferItemOut(
                id=item.id,
                product_id=item.product_id,
                product_name=product.name if product else "Unknown",
                product_sku=product.sku if product else "",
                quantity=item.quantity,
            )
        )

    return TransferOut(
        id=transfer.id,
        from_warehouse_id=transfer.from_warehouse_id,
        from_warehouse_name=from_wh.name if from_wh else "Unknown",
        to_warehouse_id=transfer.to_warehouse_id,
        to_warehouse_name=to_wh.name if to_wh else "Unknown",
        status=transfer.status.value,
        notes=transfer.notes,
        items=items_out,
        created_by_username=user.username if user else "unknown",
        created_at=transfer.created_at.isoformat(),
        updated_at=transfer.updated_at.isoformat(),
    )
