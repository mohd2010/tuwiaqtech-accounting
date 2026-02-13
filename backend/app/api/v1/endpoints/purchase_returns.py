from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.models.supplier import PRStatus, PurchaseReturn
from backend.app.schemas.supplier import (
    POLookupOut,
    PurchaseReturnOut,
    PurchaseReturnRequest,
)
from backend.app.services.purchase_return import lookup_po, process_purchase_return

router = APIRouter()


@router.get("/po/{po_id}", response_model=POLookupOut)
def get_po_for_return(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase:write")),
) -> dict:
    try:
        return lookup_po(db=db, po_id=po_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/process", response_model=PurchaseReturnOut)
def create_purchase_return(
    payload: PurchaseReturnRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase:write")),
) -> dict:
    try:
        return process_purchase_return(
            db=db,
            po_id=payload.po_id,
            items=[item.model_dump() for item in payload.items],
            reason=payload.reason,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=list[PurchaseReturnOut])
def list_purchase_returns(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchase:read")),
) -> list[dict]:
    prs = (
        db.query(PurchaseReturn)
        .filter(PurchaseReturn.status == PRStatus.ISSUED)
        .order_by(PurchaseReturn.created_at.desc())
        .all()
    )
    results: list[dict] = []
    for pr in prs:
        results.append({
            "return_number": pr.return_number,
            "po_id": str(pr.po_id),
            "supplier_name": pr.purchase_order.supplier.name,
            "timestamp": pr.created_at.isoformat(timespec="seconds"),
            "reason": pr.reason,
            "items": [
                {
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "condition": item.condition.value,
                    "unit_cost": str(item.unit_cost),
                    "line_total": str(item.unit_cost * item.quantity),
                }
                for item in pr.items
            ],
            "total_amount": str(pr.total_amount),
            "journal_entry_id": str(pr.journal_entry_id) if pr.journal_entry_id else "",
        })
    return results
