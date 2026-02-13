from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.models.banking import ReconciliationStatus
from backend.app.schemas.banking import (
    BankReconciliationSummary,
    BankStatementLineBulkCreate,
    BankStatementLineOut,
    MatchRequest,
    ReconcileRequest,
    UnmatchRequest,
    UnreconciledSplitOut,
)
from backend.app.services.bank_reconciliation import (
    auto_match,
    create_statement_lines,
    get_reconciliation_summary,
    list_statement_lines,
    list_unreconciled_splits,
    manual_match,
    reconcile_lines,
    unmatch,
)

router = APIRouter()


@router.get("/summary", response_model=BankReconciliationSummary)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("banking:read")),
) -> dict:
    return get_reconciliation_summary(db)


@router.get("/statement-lines", response_model=list[BankStatementLineOut])
def get_statement_lines(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("banking:read")),
) -> list[dict]:
    recon_status: ReconciliationStatus | None = None
    if status_filter:
        try:
            recon_status = ReconciliationStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )
    return list_statement_lines(db, status=recon_status)


@router.post("/statement-lines", response_model=list[BankStatementLineOut], status_code=status.HTTP_201_CREATED)
def add_statement_lines(
    payload: BankStatementLineBulkCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("banking:write")),
) -> list[dict]:
    try:
        create_statement_lines(
            db,
            lines=payload.lines,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return list_statement_lines(db)


@router.get("/unreconciled-splits", response_model=list[UnreconciledSplitOut])
def get_unreconciled_splits(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("banking:read")),
) -> list[dict]:
    return list_unreconciled_splits(db)


@router.post("/auto-match")
def run_auto_match(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("banking:write")),
) -> dict:
    count = auto_match(db, current_user.id)
    return {"matched": count}


@router.post("/match")
def match_line(
    payload: MatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("banking:write")),
) -> dict:
    try:
        manual_match(
            db,
            statement_line_id=payload.statement_line_id,
            split_id=payload.split_id,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "matched"}


@router.post("/unmatch")
def unmatch_line(
    payload: UnmatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("banking:write")),
) -> dict:
    try:
        unmatch(
            db,
            statement_line_id=payload.statement_line_id,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "unmatched"}


@router.post("/reconcile")
def reconcile(
    payload: ReconcileRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("banking:write")),
) -> dict:
    try:
        count = reconcile_lines(
            db,
            statement_line_ids=payload.statement_line_ids,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"reconciled": count}
