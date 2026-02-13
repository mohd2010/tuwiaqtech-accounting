from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.schemas.sales import SaleDetailOut, SaleHistoryOut
from backend.app.services.sales import get_sale_detail, list_sales

router = APIRouter()


@router.get("", response_model=list[SaleHistoryOut])
def get_sales(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales:read")),
) -> list[dict]:
    return list_sales(db)


@router.get("/{invoice_number}", response_model=SaleDetailOut)
def get_sale(
    invoice_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales:read")),
) -> dict:
    try:
        return get_sale_detail(db, invoice_number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
