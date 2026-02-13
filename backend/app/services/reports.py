"""Service layer for financial reports."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.accounting import (
    Account,
    AccountType,
    JournalEntry,
    TransactionSplit,
)
from backend.app.models.inventory import (
    Category,
    Product,
    Warehouse,
    WarehouseStock,
)

ZERO = Decimal("0")
Q = Decimal("0.0001")

COGS_CODE = "5000"
VAT_ACCOUNT_CODE = "2200"
SALES_ACCOUNT_CODE = "4000"
CASH_ACCOUNT_CODE = "1000"
BANK_ACCOUNT_CODE = "1200"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _to_dt(d: date) -> datetime:
    """Convert a date to start-of-day UTC datetime."""
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _sum_by_type_in_range(
    db: Session,
    account_type: AccountType,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict[str, object]]:
    """Per-account debit/credit totals for an account type, optionally date-bounded."""
    query = (
        db.query(
            Account.code,
            Account.name,
            func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("total_debit"),
            func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("total_credit"),
        )
        .join(TransactionSplit, TransactionSplit.account_id == Account.id)
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .filter(Account.account_type == account_type)
    )
    if from_date:
        query = query.filter(JournalEntry.entry_date >= _to_dt(from_date))
    if to_date:
        query = query.filter(JournalEntry.entry_date < _to_dt(to_date + timedelta(days=1)))

    return [
        {
            "code": r.code,
            "name": r.name,
            "total_debit": r.total_debit,
            "total_credit": r.total_credit,
        }
        for r in query.group_by(Account.id, Account.code, Account.name)
        .order_by(Account.code)
        .all()
    ]


def _balance_for_type_in_range(
    db: Session,
    account_type: AccountType,
    normal_debit: bool,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[list[dict[str, str]], Decimal]:
    """Per-account balances and total for an account type, optionally date-bounded."""
    rows = _sum_by_type_in_range(db, account_type, from_date, to_date)
    items: list[dict[str, str]] = []
    total = ZERO
    for r in rows:
        if normal_debit:
            balance = Decimal(str(r["total_debit"])) - Decimal(str(r["total_credit"]))
        else:
            balance = Decimal(str(r["total_credit"])) - Decimal(str(r["total_debit"]))
        items.append({"code": r["code"], "name": r["name"], "balance": str(balance)})
        total += balance
    return items, total


def _account_net_in_range(
    db: Session,
    account_id: object,
    normal_debit: bool,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> Decimal:
    """Net balance for an account in a datetime range."""
    query = (
        db.query(
            func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("d"),
            func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("c"),
        )
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .filter(TransactionSplit.account_id == account_id)
    )
    if from_dt:
        query = query.filter(JournalEntry.entry_date >= from_dt)
    if to_dt:
        query = query.filter(JournalEntry.entry_date < to_dt)

    row = query.one()
    d, c = Decimal(str(row.d)), Decimal(str(row.c))
    return (d - c) if normal_debit else (c - d)


# ── Income Statement ────────────────────────────────────────────────────────


def get_income_statement(
    db: Session, from_date: date, to_date: date,
) -> dict[str, object]:
    revenue_rows = _sum_by_type_in_range(db, AccountType.REVENUE, from_date, to_date)
    total_revenue = sum(
        Decimal(str(r["total_credit"])) - Decimal(str(r["total_debit"]))
        for r in revenue_rows
    )

    expense_rows = _sum_by_type_in_range(db, AccountType.EXPENSE, from_date, to_date)
    cogs = ZERO
    operating_expenses = ZERO
    expense_detail: list[dict[str, object]] = []

    for r in expense_rows:
        balance = Decimal(str(r["total_debit"])) - Decimal(str(r["total_credit"]))
        expense_detail.append({"code": r["code"], "name": r["name"], "amount": str(balance)})
        if r["code"] == COGS_CODE:
            cogs += balance
        else:
            operating_expenses += balance

    gross_profit = total_revenue - cogs
    net_income = gross_profit - operating_expenses

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "revenue": str(total_revenue),
        "revenue_detail": [
            {
                "code": r["code"],
                "name": r["name"],
                "amount": str(
                    Decimal(str(r["total_credit"])) - Decimal(str(r["total_debit"]))
                ),
            }
            for r in revenue_rows
        ],
        "cogs": str(cogs),
        "gross_profit": str(gross_profit),
        "operating_expenses": str(operating_expenses),
        "expense_detail": expense_detail,
        "net_income": str(net_income),
    }


# ── Trial Balance ───────────────────────────────────────────────────────────


def get_trial_balance(
    db: Session, from_date: date, to_date: date,
) -> dict[str, object]:
    from_dt = _to_dt(from_date)
    to_dt = _to_dt(to_date + timedelta(days=1))

    query = (
        db.query(
            Account.code,
            Account.name,
            Account.account_type,
            func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("total_debit"),
            func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("total_credit"),
        )
        .outerjoin(
            TransactionSplit,
            (TransactionSplit.account_id == Account.id)
            & (TransactionSplit.journal_entry_id == JournalEntry.id),
        )
        .outerjoin(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
    )

    # Apply date filters only to splits (not accounts without splits)
    query = (
        db.query(
            Account.code,
            Account.name,
            Account.account_type,
            func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("total_debit"),
            func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("total_credit"),
        )
        .outerjoin(
            JournalEntry,
            JournalEntry.id == TransactionSplit.journal_entry_id,
        )
        .outerjoin(
            TransactionSplit,
            (TransactionSplit.account_id == Account.id)
            & (
                (JournalEntry.entry_date >= from_dt)
                & (JournalEntry.entry_date < to_dt)
            ),
        )
    )

    # Simpler approach: use a subquery for date-filtered splits
    from sqlalchemy import and_, literal_column
    from sqlalchemy.orm import aliased

    # Subquery: splits in date range joined to journal entries
    filtered_splits = (
        db.query(
            TransactionSplit.account_id,
            TransactionSplit.debit_amount,
            TransactionSplit.credit_amount,
        )
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .filter(
            JournalEntry.entry_date >= from_dt,
            JournalEntry.entry_date < to_dt,
        )
        .subquery()
    )

    rows = (
        db.query(
            Account.code,
            Account.name,
            Account.account_type,
            func.coalesce(func.sum(filtered_splits.c.debit_amount), 0).label("total_debit"),
            func.coalesce(func.sum(filtered_splits.c.credit_amount), 0).label("total_credit"),
        )
        .outerjoin(filtered_splits, filtered_splits.c.account_id == Account.id)
        .group_by(Account.id, Account.code, Account.name, Account.account_type)
        .order_by(Account.code)
        .all()
    )

    accounts: list[dict[str, str]] = []
    total_debit = ZERO
    total_credit = ZERO

    for r in rows:
        balance = Decimal(str(r.total_debit)) - Decimal(str(r.total_credit))
        if balance > 0:
            debit = balance
            credit = ZERO
        elif balance < 0:
            debit = ZERO
            credit = abs(balance)
        else:
            debit = ZERO
            credit = ZERO

        total_debit += debit
        total_credit += credit

        accounts.append({
            "account_code": r.code,
            "account_name": r.name,
            "account_type": r.account_type.value,
            "debit": str(debit),
            "credit": str(credit),
        })

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "accounts": accounts,
        "total_debit": str(total_debit),
        "total_credit": str(total_credit),
        "is_balanced": total_debit == total_credit,
    }


# ── Balance Sheet ───────────────────────────────────────────────────────────


def get_balance_sheet(db: Session, as_of_date: date) -> dict[str, object]:
    """Balance sheet is cumulative from beginning of time to as_of_date."""
    asset_items, total_assets = _balance_for_type_in_range(
        db, AccountType.ASSET, normal_debit=True, to_date=as_of_date,
    )
    liability_items, total_liabilities = _balance_for_type_in_range(
        db, AccountType.LIABILITY, normal_debit=False, to_date=as_of_date,
    )
    equity_items, total_equity = _balance_for_type_in_range(
        db, AccountType.EQUITY, normal_debit=False, to_date=as_of_date,
    )

    # Retained Earnings = Revenue - Expenses (cumulative)
    revenue_rows = _sum_by_type_in_range(db, AccountType.REVENUE, to_date=as_of_date)
    total_revenue = sum(
        Decimal(str(r["total_credit"])) - Decimal(str(r["total_debit"]))
        for r in revenue_rows
    )
    expense_rows = _sum_by_type_in_range(db, AccountType.EXPENSE, to_date=as_of_date)
    total_expenses = sum(
        Decimal(str(r["total_debit"])) - Decimal(str(r["total_credit"]))
        for r in expense_rows
    )
    retained_earnings = total_revenue - total_expenses

    total_liabilities_and_equity = total_liabilities + total_equity + retained_earnings

    return {
        "as_of_date": as_of_date.isoformat(),
        "assets": asset_items,
        "total_assets": str(total_assets),
        "liabilities": liability_items,
        "total_liabilities": str(total_liabilities),
        "equity": equity_items,
        "total_equity": str(total_equity),
        "retained_earnings": str(retained_earnings),
        "total_liabilities_and_equity": str(total_liabilities_and_equity),
        "is_balanced": total_assets == total_liabilities_and_equity,
    }


# ── General Ledger ──────────────────────────────────────────────────────────


def get_general_ledger(
    db: Session, account_code: str, from_date: date, to_date: date,
) -> dict[str, object]:
    account = db.query(Account).filter(Account.code == account_code).first()
    if not account:
        raise ValueError(f"Account {account_code} not found")

    normal_debit = account.account_type in (AccountType.ASSET, AccountType.EXPENSE)

    from_dt = _to_dt(from_date)
    to_dt = _to_dt(to_date + timedelta(days=1))

    # Opening balance: all activity before from_date
    opening_balance = _account_net_in_range(
        db, account.id, normal_debit, to_dt=from_dt,
    )

    # Transactions in range
    splits = (
        db.query(TransactionSplit, JournalEntry)
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .filter(
            TransactionSplit.account_id == account.id,
            JournalEntry.entry_date >= from_dt,
            JournalEntry.entry_date < to_dt,
        )
        .order_by(JournalEntry.entry_date, JournalEntry.id)
        .all()
    )

    running = opening_balance
    entries: list[dict[str, str | None]] = []
    for split, je in splits:
        dr = Decimal(str(split.debit_amount))
        cr = Decimal(str(split.credit_amount))
        running += (dr - cr) if normal_debit else (cr - dr)
        entries.append({
            "date": je.entry_date.isoformat(),
            "reference": je.reference,
            "description": je.description,
            "debit": str(dr),
            "credit": str(cr),
            "running_balance": str(running),
        })

    return {
        "account_code": account.code,
        "account_name": account.name,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "opening_balance": str(opening_balance),
        "entries": entries,
        "closing_balance": str(running),
    }


# ── VAT Report ──────────────────────────────────────────────────────────────


def get_vat_report(
    db: Session, from_date: date, to_date: date,
) -> dict[str, object]:
    vat_account = db.query(Account).filter(Account.code == VAT_ACCOUNT_CODE).first()
    sales_account = db.query(Account).filter(Account.code == SALES_ACCOUNT_CODE).first()

    from_dt = _to_dt(from_date)
    to_dt = _to_dt(to_date + timedelta(days=1))

    # Total VAT collected (credit normal for liability)
    total_vat = ZERO
    if vat_account:
        total_vat = _account_net_in_range(
            db, vat_account.id, normal_debit=False, from_dt=from_dt, to_dt=to_dt,
        )

    # Total sales ex-VAT (credit normal for revenue)
    total_sales = ZERO
    if sales_account:
        total_sales = _account_net_in_range(
            db, sales_account.id, normal_debit=False, from_dt=from_dt, to_dt=to_dt,
        )

    effective_rate = (
        (total_vat / total_sales * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total_sales > ZERO
        else ZERO
    )

    # Monthly breakdown
    monthly_breakdown: list[dict[str, object]] = []
    if vat_account and sales_account:
        # VAT per month — define expression once for GROUP BY compatibility
        vat_month_expr = func.date_trunc("month", JournalEntry.entry_date)
        vat_monthly = (
            db.query(
                vat_month_expr.label("month"),
                func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("c"),
                func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("d"),
                func.count(func.distinct(JournalEntry.id)).label("tx_count"),
            )
            .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
            .filter(
                TransactionSplit.account_id == vat_account.id,
                JournalEntry.entry_date >= from_dt,
                JournalEntry.entry_date < to_dt,
            )
            .group_by(vat_month_expr)
            .order_by(vat_month_expr)
            .all()
        )

        # Sales per month
        sales_month_expr = func.date_trunc("month", JournalEntry.entry_date)
        sales_monthly = (
            db.query(
                sales_month_expr.label("month"),
                func.coalesce(func.sum(TransactionSplit.credit_amount), 0).label("c"),
                func.coalesce(func.sum(TransactionSplit.debit_amount), 0).label("d"),
            )
            .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
            .filter(
                TransactionSplit.account_id == sales_account.id,
                JournalEntry.entry_date >= from_dt,
                JournalEntry.entry_date < to_dt,
            )
            .group_by(sales_month_expr)
            .order_by(sales_month_expr)
            .all()
        )

        sales_by_month: dict[str, Decimal] = {}
        for row in sales_monthly:
            month_str = row.month.strftime("%Y-%m")
            sales_by_month[month_str] = Decimal(str(row.c)) - Decimal(str(row.d))

        for row in vat_monthly:
            month_str = row.month.strftime("%Y-%m")
            vat_amt = Decimal(str(row.c)) - Decimal(str(row.d))
            monthly_breakdown.append({
                "month": month_str,
                "vat_collected": str(vat_amt),
                "sales_ex_vat": str(sales_by_month.get(month_str, ZERO)),
                "transaction_count": row.tx_count,
            })

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "total_vat_collected": str(total_vat),
        "total_sales_ex_vat": str(total_sales),
        "effective_vat_rate": str(effective_rate),
        "monthly_breakdown": monthly_breakdown,
    }


# ── Cash Flow Statement ────────────────────────────────────────────────────


def get_cash_flow(
    db: Session, from_date: date, to_date: date,
) -> dict[str, object]:
    cash_account = db.query(Account).filter(Account.code == CASH_ACCOUNT_CODE).first()
    bank_account = db.query(Account).filter(Account.code == BANK_ACCOUNT_CODE).first()

    cash_ids: list[object] = []
    if cash_account:
        cash_ids.append(cash_account.id)
    if bank_account:
        cash_ids.append(bank_account.id)

    from_dt = _to_dt(from_date)
    to_dt = _to_dt(to_date + timedelta(days=1))

    # Opening balance (cumulative before from_date)
    opening_balance = ZERO
    for aid in cash_ids:
        opening_balance += _account_net_in_range(db, aid, normal_debit=True, to_dt=from_dt)

    if not cash_ids:
        return _empty_cash_flow(from_date, to_date, opening_balance)

    # Fetch all cash/bank splits in range
    cash_splits = (
        db.query(TransactionSplit, JournalEntry)
        .join(JournalEntry, TransactionSplit.journal_entry_id == JournalEntry.id)
        .filter(
            TransactionSplit.account_id.in_(cash_ids),
            JournalEntry.entry_date >= from_dt,
            JournalEntry.entry_date < to_dt,
        )
        .all()
    )

    # Batch-fetch all journal entry IDs to avoid N+1
    je_ids = list({je.id for _, je in cash_splits})

    # Get all counter-splits for those journal entries
    counter_splits_raw = []
    if je_ids:
        counter_splits_raw = (
            db.query(TransactionSplit.journal_entry_id, Account.name, Account.account_type)
            .join(Account, TransactionSplit.account_id == Account.id)
            .filter(
                TransactionSplit.journal_entry_id.in_(je_ids),
                ~TransactionSplit.account_id.in_(cash_ids),
            )
            .all()
        )

    # Build journal_entry_id → primary counter-account type
    je_classification: dict[object, tuple[str, AccountType]] = {}
    for je_id, name, acct_type in counter_splits_raw:
        if je_id not in je_classification:
            je_classification[je_id] = (name, acct_type)

    # Classify cash movements
    operating: dict[str, Decimal] = {}
    investing: dict[str, Decimal] = {}
    financing: dict[str, Decimal] = {}

    for split, je in cash_splits:
        net = Decimal(str(split.debit_amount)) - Decimal(str(split.credit_amount))
        counter = je_classification.get(je.id)

        if counter is None:
            operating["Other"] = operating.get("Other", ZERO) + net
            continue

        name, acct_type = counter
        if acct_type in (AccountType.REVENUE, AccountType.EXPENSE, AccountType.LIABILITY):
            operating[name] = operating.get(name, ZERO) + net
        elif acct_type == AccountType.EQUITY:
            financing[name] = financing.get(name, ZERO) + net
        elif acct_type == AccountType.ASSET:
            investing[name] = investing.get(name, ZERO) + net
        else:
            operating["Other"] = operating.get("Other", ZERO) + net

    def _section(items: dict[str, Decimal]) -> dict[str, object]:
        line_items = [
            {"description": desc, "amount": str(amt)}
            for desc, amt in sorted(items.items())
            if amt != ZERO
        ]
        total = sum(items.values(), ZERO)
        return {"items": line_items, "total": str(total)}

    op_section = _section(operating)
    inv_section = _section(investing)
    fin_section = _section(financing)

    net_change = (
        Decimal(str(op_section["total"]))
        + Decimal(str(inv_section["total"]))
        + Decimal(str(fin_section["total"]))
    )
    closing_balance = opening_balance + net_change

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "opening_cash_balance": str(opening_balance),
        "operating": op_section,
        "investing": inv_section,
        "financing": fin_section,
        "net_change": str(net_change),
        "closing_cash_balance": str(closing_balance),
    }


def _empty_cash_flow(
    from_date: date, to_date: date, opening: Decimal,
) -> dict[str, object]:
    empty_section: dict[str, object] = {"items": [], "total": "0"}
    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "opening_cash_balance": str(opening),
        "operating": empty_section,
        "investing": empty_section,
        "financing": empty_section,
        "net_change": "0",
        "closing_cash_balance": str(opening),
    }


# ── Inventory Valuation ──────────────────────────────────────────────────


def get_inventory_valuation(
    db: Session,
    warehouse_id: UUID | None = None,
    category_id: UUID | None = None,
) -> dict[str, object]:
    """Point-in-time inventory valuation report."""
    warehouse_name: str | None = None
    category_name: str | None = None

    if warehouse_id:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        warehouse_name = wh.name if wh else None

    if category_id:
        cat = db.query(Category).filter(Category.id == category_id).first()
        category_name = cat.name if cat else None

    if warehouse_id:
        # Per-warehouse stock
        query = (
            db.query(
                Product.id.label("product_id"),
                Product.sku,
                Product.name,
                Category.name.label("category"),
                WarehouseStock.quantity,
                Product.cost_price,
            )
            .join(WarehouseStock, WarehouseStock.product_id == Product.id)
            .join(Category, Product.category_id == Category.id)
            .filter(WarehouseStock.warehouse_id == warehouse_id)
        )
    else:
        # Aggregate stock across all warehouses
        query = (
            db.query(
                Product.id.label("product_id"),
                Product.sku,
                Product.name,
                Category.name.label("category"),
                Product.current_stock.label("quantity"),
                Product.cost_price,
            )
            .join(Category, Product.category_id == Category.id)
        )

    if category_id:
        query = query.filter(Product.category_id == category_id)

    rows = query.order_by(Product.sku).all()

    items: list[dict[str, object]] = []
    total_quantity = 0
    total_value = ZERO

    for r in rows:
        qty = int(r.quantity)
        cost = Decimal(str(r.cost_price))
        value = cost * qty
        items.append({
            "product_id": str(r.product_id),
            "sku": r.sku,
            "name": r.name,
            "category": r.category,
            "quantity": qty,
            "cost_price": str(cost),
            "total_value": str(value),
        })
        total_quantity += qty
        total_value += value

    return {
        "as_of_date": date.today().isoformat(),
        "warehouse_filter": warehouse_name,
        "category_filter": category_name,
        "items": items,
        "total_items": len(items),
        "total_quantity": total_quantity,
        "total_value": str(total_value),
    }
