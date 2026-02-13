from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import (
    Account,
    AccountType,
    JournalEntry,
    TransactionSplit,
    User,
)
from backend.app.models.inventory import Product
from backend.app.models.invoice import CreditInvoice, InvoiceStatus
from backend.app.models.customer import Sale
from backend.app.models.pos import SalePayment
from backend.app.models.supplier import PurchaseOrder, POStatus
from backend.app.services.audit import log_action
from backend.app.services.aging import (
    bucket as _aging_bucket,
    empty_buckets as _aging_empty_buckets,
    get_ap_aging as _get_ap_aging,
    get_ar_aging as _get_ar_aging,
)
from backend.app.services.reports import (
    get_balance_sheet as _get_balance_sheet,
    get_cash_flow as _get_cash_flow,
    get_general_ledger as _get_general_ledger,
    get_income_statement as _get_income_statement,
    get_inventory_valuation as _get_inventory_valuation,
    get_trial_balance as _get_trial_balance,
    get_vat_report as _get_vat_report,
)
from backend.app.services.export_excel import (
    export_income_statement_excel,
    export_trial_balance_excel,
    export_balance_sheet_excel,
    export_general_ledger_excel,
    export_vat_report_excel,
    export_cash_flow_excel,
    export_ar_aging_excel,
    export_ap_aging_excel,
    export_inventory_valuation_excel,
)
from backend.app.services.export_pdf import (
    export_income_statement_pdf,
    export_trial_balance_pdf,
    export_balance_sheet_pdf,
    export_general_ledger_pdf,
    export_vat_report_pdf,
    export_cash_flow_pdf,
    export_ar_aging_pdf,
    export_ap_aging_pdf,
    export_inventory_valuation_pdf,
)

router = APIRouter()

def _check_report_role(user: User) -> None:
    """Legacy helper — kept for endpoints not yet migrated to dependency."""
    pass  # Permission checked by require_permission() dependency


def _default_dates(
    from_date: date | None, to_date: date | None,
) -> tuple[date, date]:
    today = date.today()
    if from_date is None:
        from_date = today.replace(day=1)
    if to_date is None:
        to_date = today
    return from_date, to_date


# ── Income Statement ────────────────────────────────────────────────────────


@router.get("/income-statement")
def income_statement(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> dict[str, object]:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    return _get_income_statement(db, fd, td)


# ── Trial Balance ───────────────────────────────────────────────────────────


@router.get("/trial-balance")
def trial_balance(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> dict[str, object]:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    return _get_trial_balance(db, fd, td)


# ── Balance Sheet ───────────────────────────────────────────────────────────


@router.get("/balance-sheet")
def balance_sheet(
    as_of_date: date | None = Query(None),
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> dict[str, object]:
    _check_report_role(current_user)
    if as_of_date is None:
        as_of_date = date.today()

    result = _get_balance_sheet(db, as_of_date)

    log_action(
        db,
        user_id=current_user.id,
        action="REPORT_EXPORTED",
        resource_type="reports",
        resource_id="balance-sheet",
        ip_address=request.client.host if request and request.client else None,
        changes={"total_assets": result["total_assets"], "is_balanced": str(result["is_balanced"])},
    )
    db.commit()

    return result


# ── General Ledger ──────────────────────────────────────────────────────────


@router.get("/general-ledger")
def general_ledger(
    account_code: str = Query(...),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> dict[str, object]:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    try:
        return _get_general_ledger(db, account_code, fd, td)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── VAT Report ──────────────────────────────────────────────────────────────


@router.get("/vat-report")
def vat_report(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> dict[str, object]:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    return _get_vat_report(db, fd, td)


# ── Cash Flow ───────────────────────────────────────────────────────────────


@router.get("/cash-flow")
def cash_flow(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> dict[str, object]:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    return _get_cash_flow(db, fd, td)


# ── AR Aging ───────────────────────────────────────────────────────────────


@router.get("/ar-aging")
def ar_aging(
    as_of_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> dict[str, object]:
    _check_report_role(current_user)
    if as_of_date is None:
        as_of_date = date.today()
    return _get_ar_aging(db, as_of_date)


# ── AP Aging ───────────────────────────────────────────────────────────────


@router.get("/ap-aging")
def ap_aging(
    as_of_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> dict[str, object]:
    _check_report_role(current_user)
    if as_of_date is None:
        as_of_date = date.today()
    return _get_ap_aging(db, as_of_date)


# ── Export helpers ────────────────────────────────────────────────────────

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PDF_MIME = "application/pdf"


def _export_response(
    buf: object, media_type: str, filename: str,
) -> StreamingResponse:
    return StreamingResponse(
        buf,  # type: ignore[arg-type]
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _log_export(
    db: Session, user_id: object, report_name: str, fmt: str,
) -> None:
    log_action(
        db,
        user_id=user_id,  # type: ignore[arg-type]
        action="REPORT_EXPORTED",
        resource_type="reports",
        resource_id=report_name,
        changes={"format": fmt},
    )
    db.commit()


# ── Income Statement exports ─────────────────────────────────────────────


@router.get("/income-statement/export/excel")
def income_statement_export_excel(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    data = _get_income_statement(db, fd, td)
    buf = export_income_statement_excel(data, lang=lang)
    _log_export(db, current_user.id, "income-statement", "excel")
    return _export_response(buf, _XLSX_MIME, "income-statement.xlsx")


@router.get("/income-statement/export/pdf")
def income_statement_export_pdf(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    data = _get_income_statement(db, fd, td)
    buf = export_income_statement_pdf(data, lang=lang)
    _log_export(db, current_user.id, "income-statement", "pdf")
    return _export_response(buf, _PDF_MIME, "income-statement.pdf")


# ── Trial Balance exports ────────────────────────────────────────────────


@router.get("/trial-balance/export/excel")
def trial_balance_export_excel(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    data = _get_trial_balance(db, fd, td)
    buf = export_trial_balance_excel(data, lang=lang)
    _log_export(db, current_user.id, "trial-balance", "excel")
    return _export_response(buf, _XLSX_MIME, "trial-balance.xlsx")


@router.get("/trial-balance/export/pdf")
def trial_balance_export_pdf(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    data = _get_trial_balance(db, fd, td)
    buf = export_trial_balance_pdf(data, lang=lang)
    _log_export(db, current_user.id, "trial-balance", "pdf")
    return _export_response(buf, _PDF_MIME, "trial-balance.pdf")


# ── Balance Sheet exports ────────────────────────────────────────────────


@router.get("/balance-sheet/export/excel")
def balance_sheet_export_excel(
    as_of_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    if as_of_date is None:
        as_of_date = date.today()
    data = _get_balance_sheet(db, as_of_date)
    buf = export_balance_sheet_excel(data, lang=lang)
    _log_export(db, current_user.id, "balance-sheet", "excel")
    return _export_response(buf, _XLSX_MIME, "balance-sheet.xlsx")


@router.get("/balance-sheet/export/pdf")
def balance_sheet_export_pdf(
    as_of_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    if as_of_date is None:
        as_of_date = date.today()
    data = _get_balance_sheet(db, as_of_date)
    buf = export_balance_sheet_pdf(data, lang=lang)
    _log_export(db, current_user.id, "balance-sheet", "pdf")
    return _export_response(buf, _PDF_MIME, "balance-sheet.pdf")


# ── General Ledger exports ───────────────────────────────────────────────


@router.get("/general-ledger/export/excel")
def general_ledger_export_excel(
    account_code: str = Query(...),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    try:
        data = _get_general_ledger(db, account_code, fd, td)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    buf = export_general_ledger_excel(data, lang=lang)
    _log_export(db, current_user.id, "general-ledger", "excel")
    return _export_response(buf, _XLSX_MIME, "general-ledger.xlsx")


@router.get("/general-ledger/export/pdf")
def general_ledger_export_pdf(
    account_code: str = Query(...),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    try:
        data = _get_general_ledger(db, account_code, fd, td)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    buf = export_general_ledger_pdf(data, lang=lang)
    _log_export(db, current_user.id, "general-ledger", "pdf")
    return _export_response(buf, _PDF_MIME, "general-ledger.pdf")


# ── VAT Report exports ──────────────────────────────────────────────────


@router.get("/vat-report/export/excel")
def vat_report_export_excel(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    data = _get_vat_report(db, fd, td)
    buf = export_vat_report_excel(data, lang=lang)
    _log_export(db, current_user.id, "vat-report", "excel")
    return _export_response(buf, _XLSX_MIME, "vat-report.xlsx")


@router.get("/vat-report/export/pdf")
def vat_report_export_pdf(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    data = _get_vat_report(db, fd, td)
    buf = export_vat_report_pdf(data, lang=lang)
    _log_export(db, current_user.id, "vat-report", "pdf")
    return _export_response(buf, _PDF_MIME, "vat-report.pdf")


# ── Cash Flow exports ───────────────────────────────────────────────────


@router.get("/cash-flow/export/excel")
def cash_flow_export_excel(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    data = _get_cash_flow(db, fd, td)
    buf = export_cash_flow_excel(data, lang=lang)
    _log_export(db, current_user.id, "cash-flow", "excel")
    return _export_response(buf, _XLSX_MIME, "cash-flow.xlsx")


@router.get("/cash-flow/export/pdf")
def cash_flow_export_pdf(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    fd, td = _default_dates(from_date, to_date)
    data = _get_cash_flow(db, fd, td)
    buf = export_cash_flow_pdf(data, lang=lang)
    _log_export(db, current_user.id, "cash-flow", "pdf")
    return _export_response(buf, _PDF_MIME, "cash-flow.pdf")


# ── AR Aging exports ────────────────────────────────────────────────────


@router.get("/ar-aging/export/excel")
def ar_aging_export_excel(
    as_of_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    if as_of_date is None:
        as_of_date = date.today()
    data = _get_ar_aging(db, as_of_date)
    buf = export_ar_aging_excel(data, lang=lang)
    _log_export(db, current_user.id, "ar-aging", "excel")
    return _export_response(buf, _XLSX_MIME, "ar-aging.xlsx")


@router.get("/ar-aging/export/pdf")
def ar_aging_export_pdf(
    as_of_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    if as_of_date is None:
        as_of_date = date.today()
    data = _get_ar_aging(db, as_of_date)
    buf = export_ar_aging_pdf(data, lang=lang)
    _log_export(db, current_user.id, "ar-aging", "pdf")
    return _export_response(buf, _PDF_MIME, "ar-aging.pdf")


# ── AP Aging exports ────────────────────────────────────────────────────


@router.get("/ap-aging/export/excel")
def ap_aging_export_excel(
    as_of_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    if as_of_date is None:
        as_of_date = date.today()
    data = _get_ap_aging(db, as_of_date)
    buf = export_ap_aging_excel(data, lang=lang)
    _log_export(db, current_user.id, "ap-aging", "excel")
    return _export_response(buf, _XLSX_MIME, "ap-aging.xlsx")


@router.get("/ap-aging/export/pdf")
def ap_aging_export_pdf(
    as_of_date: date | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    if as_of_date is None:
        as_of_date = date.today()
    data = _get_ap_aging(db, as_of_date)
    buf = export_ap_aging_pdf(data, lang=lang)
    _log_export(db, current_user.id, "ap-aging", "pdf")
    return _export_response(buf, _PDF_MIME, "ap-aging.pdf")


# ── Inventory Valuation ───────────────────────────────────────────────────


@router.get("/valuation")
def inventory_valuation(
    warehouse_id: UUID | None = Query(None),
    category_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> dict[str, object]:
    _check_report_role(current_user)
    return _get_inventory_valuation(db, warehouse_id, category_id)


@router.get("/valuation/export/excel")
def valuation_export_excel(
    warehouse_id: UUID | None = Query(None),
    category_id: UUID | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    data = _get_inventory_valuation(db, warehouse_id, category_id)
    buf = export_inventory_valuation_excel(data, lang=lang)
    _log_export(db, current_user.id, "valuation", "excel")
    return _export_response(buf, _XLSX_MIME, "inventory-valuation.xlsx")


@router.get("/valuation/export/pdf")
def valuation_export_pdf(
    warehouse_id: UUID | None = Query(None),
    category_id: UUID | None = Query(None),
    lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:read")),
) -> StreamingResponse:
    _check_report_role(current_user)
    data = _get_inventory_valuation(db, warehouse_id, category_id)
    buf = export_inventory_valuation_pdf(data, lang=lang)
    _log_export(db, current_user.id, "valuation", "pdf")
    return _export_response(buf, _PDF_MIME, "inventory-valuation.pdf")


# ── Dashboard Summary ─────────────────────────────────────────────────────

SALES_ACCOUNT_CODE = "4000"
COGS_ACCOUNT_CODE = "5000"
CASH_ACCOUNT_CODE = "1000"
BANK_ACCOUNT_CODE = "1200"
AP_ACCOUNT_CODE = "2100"


def _account_net_30d(
    db: Session, account_id: object, thirty_days_ago: datetime, normal_debit: bool,
) -> Decimal:
    """Net balance for an account over the last 30 days."""
    row = (
        db.query(
            func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("d"),
            func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("c"),
        )
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .filter(
            TransactionSplit.account_id == account_id,
            JournalEntry.entry_date >= thirty_days_ago,
        )
        .one()
    )
    d, c = Decimal(str(row.d)), Decimal(str(row.c))
    return (d - c) if normal_debit else (c - d)


@router.get("/dashboard-summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # ── Revenue (30d): credits − debits on Sales Revenue ──────────────────
    sales_account = db.query(Account).filter(Account.code == SALES_ACCOUNT_CODE).first()
    revenue = Decimal("0")
    if sales_account:
        revenue = _account_net_30d(db, sales_account.id, thirty_days_ago, normal_debit=False)

    # ── Total Expenses (30d): COGS + all other EXPENSE accounts ──────────
    expense_accounts = (
        db.query(Account.id).filter(Account.account_type == AccountType.EXPENSE).all()
    )
    total_expenses = Decimal("0")
    for (acct_id,) in expense_accounts:
        total_expenses += _account_net_30d(db, acct_id, thirty_days_ago, normal_debit=True)

    net_profit = revenue - total_expenses

    # ── Inventory Value (sum of current_stock × cost_price) ──────────────
    inventory_value = Decimal(str(
        db.query(
            func.coalesce(func.sum(Product.current_stock * Product.cost_price), 0)
        ).scalar()
    ))

    # ── Low Stock ────────────────────────────────────────────────────────
    low_stock_count: int = (
        db.query(func.count(Product.id))
        .filter(Product.current_stock <= Product.reorder_level)
        .scalar()
    ) or 0

    low_stock_items_rows = (
        db.query(Product.id, Product.name, Product.sku, Product.current_stock, Product.reorder_level)
        .filter(Product.current_stock <= Product.reorder_level)
        .order_by(Product.current_stock.asc())
        .limit(3)
        .all()
    )
    low_stock_items = [
        {
            "id": str(r.id),
            "name": r.name,
            "sku": r.sku,
            "current_stock": r.current_stock,
            "reorder_level": r.reorder_level,
        }
        for r in low_stock_items_rows
    ]

    # ── Sales Trend (last 7 days) ────────────────────────────────────────
    sales_trend: list[dict[str, str]] = []
    if sales_account:
        rows = (
            db.query(
                cast(JournalEntry.entry_date, Date).label("day"),
                func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("total_sales"),
            )
            .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
            .filter(
                TransactionSplit.account_id == sales_account.id,
                JournalEntry.entry_date >= seven_days_ago,
            )
            .group_by(cast(JournalEntry.entry_date, Date))
            .order_by(cast(JournalEntry.entry_date, Date))
            .all()
        )
        sales_trend = [
            {"date": str(r.day), "total_sales": str(r.total_sales)} for r in rows
        ]

    # ── Recent Journal Entries (last 3) ──────────────────────────────────
    recent_entries = (
        db.query(JournalEntry)
        .order_by(JournalEntry.created_at.desc())
        .limit(3)
        .all()
    )
    recent_activity = [
        {
            "id": str(e.id),
            "date": e.entry_date.isoformat(),
            "description": e.description,
            "reference": e.reference or "",
        }
        for e in recent_entries
    ]

    # ── NEW: COGS (30d) for gross margin ────────────────────────────────
    cogs_account = db.query(Account).filter(Account.code == COGS_ACCOUNT_CODE).first()
    cogs_30d = Decimal("0")
    if cogs_account:
        cogs_30d = _account_net_30d(db, cogs_account.id, thirty_days_ago, normal_debit=True)

    # 1. Gross Margin %
    gross_margin_pct = Decimal("0")
    if revenue > 0:
        gross_margin_pct = ((revenue - cogs_30d) / revenue * 100).quantize(Decimal("0.01"))

    # 2. Accounts Receivable (outstanding on OPEN/PARTIAL credit invoices)
    ar_result = (
        db.query(
            func.coalesce(
                func.sum(CreditInvoice.total_amount - CreditInvoice.amount_paid), 0
            )
        )
        .filter(CreditInvoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.PARTIAL]))
        .scalar()
    )
    accounts_receivable = Decimal(str(ar_result))

    # 3. Accounts Payable (received PO totals − AP debit payments)
    po_total_result = (
        db.query(func.coalesce(func.sum(PurchaseOrder.total_amount), 0))
        .filter(PurchaseOrder.status == POStatus.RECEIVED)
        .scalar()
    )
    po_total = Decimal(str(po_total_result))

    ap_account = db.query(Account).filter(Account.code == AP_ACCOUNT_CODE).first()
    ap_debits = Decimal("0")
    if ap_account:
        ap_debits_result = (
            db.query(func.coalesce(func.sum(TransactionSplit.debit_amount), 0))
            .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
            .filter(TransactionSplit.account_id == ap_account.id)
            .scalar()
        )
        ap_debits = Decimal(str(ap_debits_result))
    accounts_payable = po_total - ap_debits

    # 4. Cash Position (all-time balance of Cash + Bank)
    cash_position = Decimal("0")
    for code in (CASH_ACCOUNT_CODE, BANK_ACCOUNT_CODE):
        acct = db.query(Account).filter(Account.code == code).first()
        if acct:
            row = (
                db.query(
                    func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("d"),
                    func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("c"),
                )
                .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
                .filter(TransactionSplit.account_id == acct.id)
                .one()
            )
            cash_position += Decimal(str(row.d)) - Decimal(str(row.c))

    # 5. Revenue vs Expenses (daily, last 30 days)
    revenue_expense_trend: list[dict[str, str]] = []
    # Daily revenue
    daily_rev: dict[str, Decimal] = {}
    if sales_account:
        rev_rows = (
            db.query(
                cast(JournalEntry.entry_date, Date).label("day"),
                func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("amt"),
            )
            .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
            .filter(
                TransactionSplit.account_id == sales_account.id,
                JournalEntry.entry_date >= thirty_days_ago,
            )
            .group_by(cast(JournalEntry.entry_date, Date))
            .all()
        )
        for r in rev_rows:
            daily_rev[str(r.day)] = Decimal(str(r.amt))

    # Daily expenses
    daily_exp: dict[str, Decimal] = {}
    if expense_accounts:
        exp_ids = [aid for (aid,) in expense_accounts]
        exp_rows = (
            db.query(
                cast(JournalEntry.entry_date, Date).label("day"),
                func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("amt"),
            )
            .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
            .filter(
                TransactionSplit.account_id.in_(exp_ids),
                JournalEntry.entry_date >= thirty_days_ago,
            )
            .group_by(cast(JournalEntry.entry_date, Date))
            .all()
        )
        for r in exp_rows:
            daily_exp[str(r.day)] = Decimal(str(r.amt))

    all_days = sorted(set(daily_rev.keys()) | set(daily_exp.keys()))
    for day in all_days:
        revenue_expense_trend.append({
            "date": day,
            "revenue": str(daily_rev.get(day, Decimal("0"))),
            "expenses": str(daily_exp.get(day, Decimal("0"))),
        })

    # 6. Top 5 Products by sales amount (30d)
    top_products_rows = (
        db.query(
            Product.name,
            func.coalesce(func.sum(Sale.total_amount), 0).label("total"),
        )
        .join(Sale, Sale.product_id == Product.id)
        .filter(Sale.created_at >= thirty_days_ago)
        .group_by(Product.name)
        .order_by(func.sum(Sale.total_amount).desc())
        .limit(5)
        .all()
    )
    top_products = [
        {"name": r.name, "total": str(r.total)} for r in top_products_rows
    ]

    # 7. Sales by Payment Method (30d)
    payment_method_rows = (
        db.query(
            SalePayment.payment_method,
            func.coalesce(func.sum(SalePayment.amount), 0).label("total"),
        )
        .filter(SalePayment.created_at >= thirty_days_ago)
        .group_by(SalePayment.payment_method)
        .all()
    )
    sales_by_payment_method = [
        {"method": r.payment_method.value, "total": str(r.total)}
        for r in payment_method_rows
    ]

    # 8. Cash Flow Forecast = cash_position + AR − AP
    cash_flow_forecast = cash_position + accounts_receivable - accounts_payable

    # 9. Inventory Turnover = COGS(30d) / inventory_value
    inventory_turnover = Decimal("0")
    if inventory_value > 0:
        inventory_turnover = (cogs_30d / inventory_value).quantize(Decimal("0.01"))

    # 10. AR Aging Summary (bucket distribution from open credit invoices)
    ar_aging_buckets = _aging_empty_buckets()
    open_invoices = (
        db.query(CreditInvoice)
        .filter(CreditInvoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.PARTIAL]))
        .all()
    )
    for inv in open_invoices:
        outstanding = Decimal(str(inv.total_amount)) - Decimal(str(inv.amount_paid))
        if outstanding <= 0:
            continue
        days_since_due = (now - inv.due_date).days
        days_overdue = max(0, days_since_due)
        bkt = _aging_bucket(days_overdue)
        ar_aging_buckets[bkt] += outstanding
    ar_aging_summary = {k: str(v) for k, v in ar_aging_buckets.items()}

    return {
        "revenue": str(revenue),
        "net_profit": str(net_profit),
        "inventory_value": str(inventory_value),
        "low_stock_count": low_stock_count,
        "low_stock_items": low_stock_items,
        "sales_trend": sales_trend,
        "recent_activity": recent_activity,
        "gross_margin_pct": str(gross_margin_pct),
        "accounts_receivable": str(accounts_receivable),
        "accounts_payable": str(accounts_payable),
        "cash_position": str(cash_position),
        "revenue_expense_trend": revenue_expense_trend,
        "top_products": top_products,
        "sales_by_payment_method": sales_by_payment_method,
        "cash_flow_forecast": str(cash_flow_forecast),
        "inventory_turnover": str(inventory_turnover),
        "ar_aging_summary": ar_aging_summary,
    }
