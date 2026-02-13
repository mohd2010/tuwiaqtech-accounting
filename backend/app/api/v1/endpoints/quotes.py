from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.schemas.quotes import (
    QuoteConvertOut,
    QuoteCreate,
    QuoteListOut,
    QuoteOut,
    QuoteStatusUpdate,
)
from backend.app.services.quotes import (
    convert_to_invoice,
    create_quote,
    get_quote,
    list_quotes,
    update_quote_status,
)

router = APIRouter()


@router.post("", response_model=QuoteOut, status_code=status.HTTP_201_CREATED)
def create_new_quote(
    payload: QuoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quote:write")),
) -> dict:
    try:
        return create_quote(
            db,
            customer_name=payload.customer_name,
            customer_vat=payload.customer_vat,
            expiry_date=payload.expiry_date,
            notes=payload.notes,
            items=[item.model_dump() for item in payload.items],
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[QuoteListOut])
def get_quotes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quote:read")),
) -> list[dict]:
    return list_quotes(db)


@router.get("/{quote_id}", response_model=QuoteOut)
def get_single_quote(
    quote_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quote:read")),
) -> dict:
    try:
        return get_quote(db, quote_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{quote_id}/status", response_model=QuoteOut)
def patch_quote_status(
    quote_id: UUID,
    payload: QuoteStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quote:write")),
) -> dict:
    try:
        return update_quote_status(
            db,
            quote_id=quote_id,
            new_status=payload.status,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{quote_id}/convert", response_model=QuoteConvertOut)
def convert_quote_to_invoice(
    quote_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("quote:write")),
) -> dict:
    try:
        return convert_to_invoice(
            db,
            quote_id=quote_id,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
