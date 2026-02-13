from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.schemas.returns import (
    CreditNoteOut,
    InvoiceLookupOut,
    ReturnRequest,
)
from backend.app.services.returns import lookup_invoice, process_return

router = APIRouter()


@router.get("/invoice/{invoice_number}", response_model=InvoiceLookupOut)
def get_invoice_for_return(
    invoice_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("returns:process")),
) -> dict:
    try:
        return lookup_invoice(db=db, invoice_number=invoice_number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/process", response_model=CreditNoteOut)
def create_return(
    payload: ReturnRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("returns:process")),
) -> dict:
    try:
        return process_return(
            db=db,
            invoice_number=payload.invoice_number,
            items=[item.model_dump() for item in payload.items],
            reason=payload.reason,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
