from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.models.inventory import Category, Product
from backend.app.services.audit import log_action
from backend.app.schemas.inventory import (
    CategoryCreate,
    CategoryOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    StockAdjustmentCreate,
    StockAdjustmentOut,
    StockInRequest,
)
from backend.app.services.inventory import (
    add_stock_with_transaction,
    create_stock_adjustment,
    list_adjustments,
)

router = APIRouter()


# ─── Categories ───────────────────────────────────────────────────────────────


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("inventory:read")),
) -> list[Category]:
    return db.query(Category).order_by(Category.name).all()


@router.post(
    "/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED
)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("inventory:write")),
) -> Category:
    category = Category(name=payload.name, description=payload.description)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


# ─── Products ─────────────────────────────────────────────────────────────────


@router.get("/products", response_model=list[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("inventory:read")),
) -> list[Product]:
    return db.query(Product).order_by(Product.name).all()


@router.post(
    "/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED
)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("inventory:write")),
) -> Product:
    product = Product(
        name=payload.name,
        sku=payload.sku,
        category_id=payload.category_id,
        description=payload.description,
        unit_price=payload.unit_price,
        cost_price=payload.cost_price,
        current_stock=0,
        reorder_level=payload.reorder_level,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission("inventory:read")),
) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return product


@router.post("/products/{product_id}/stock-in", response_model=ProductOut)
def stock_in(
    product_id: UUID,
    payload: StockInRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:write")),
) -> Product:
    try:
        return add_stock_with_transaction(
            db=db,
            product_id=product_id,
            quantity=payload.quantity,
            total_cost=payload.total_cost,
            payment_account_id=payload.payment_account_id,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:write")),
) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    update_data = payload.model_dump(exclude_unset=True)
    old_values = {f: str(getattr(product, f)) for f in update_data}
    for field, value in update_data.items():
        setattr(product, field, value)

    log_action(
        db,
        user_id=current_user.id,
        action="PRICE_CHANGE" if ("unit_price" in update_data or "cost_price" in update_data) else "PRODUCT_UPDATED",
        resource_type="products",
        resource_id=str(product.id),
        ip_address=request.client.host if request.client else None,
        changes={"old": old_values, "new": {f: str(v) for f, v in update_data.items()}},
    )

    db.commit()
    db.refresh(product)
    return product


# ─── Stock Adjustments ──────────────────────────────────────────────────────


@router.post(
    "/adjustments",
    response_model=StockAdjustmentOut,
    status_code=status.HTTP_201_CREATED,
)
def post_adjustment(
    payload: StockAdjustmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:adjust")),
) -> StockAdjustmentOut:
    try:
        return create_stock_adjustment(
            db=db,
            user_id=current_user.id,
            product_id=payload.product_id,
            quantity=payload.quantity,
            adjustment_type=payload.adjustment_type,
            notes=payload.notes,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/adjustments", response_model=list[StockAdjustmentOut])
def get_adjustments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:adjust")),
) -> list[StockAdjustmentOut]:
    return list_adjustments(db)
