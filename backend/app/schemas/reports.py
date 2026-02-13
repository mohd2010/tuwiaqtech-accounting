"""Pydantic response schemas for financial reports."""
from __future__ import annotations

from pydantic import BaseModel


# ── Shared line-item ─────────────────────────────────────────────────────────

class AccountLineItem(BaseModel):
    code: str
    name: str
    amount: str


# ── Income Statement ─────────────────────────────────────────────────────────

class IncomeStatementResponse(BaseModel):
    from_date: str
    to_date: str
    revenue: str
    revenue_detail: list[AccountLineItem]
    cogs: str
    gross_profit: str
    operating_expenses: str
    expense_detail: list[AccountLineItem]
    net_income: str


# ── Trial Balance ────────────────────────────────────────────────────────────

class TrialBalanceAccountRow(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    debit: str
    credit: str


class TrialBalanceResponse(BaseModel):
    from_date: str
    to_date: str
    accounts: list[TrialBalanceAccountRow]
    total_debit: str
    total_credit: str
    is_balanced: bool


# ── Balance Sheet ────────────────────────────────────────────────────────────

class BalanceSheetLineItem(BaseModel):
    code: str
    name: str
    balance: str


class BalanceSheetResponse(BaseModel):
    as_of_date: str
    assets: list[BalanceSheetLineItem]
    total_assets: str
    liabilities: list[BalanceSheetLineItem]
    total_liabilities: str
    equity: list[BalanceSheetLineItem]
    total_equity: str
    retained_earnings: str
    total_liabilities_and_equity: str
    is_balanced: bool


# ── General Ledger ───────────────────────────────────────────────────────────

class GeneralLedgerRow(BaseModel):
    date: str
    reference: str | None
    description: str
    debit: str
    credit: str
    running_balance: str


class GeneralLedgerResponse(BaseModel):
    account_code: str
    account_name: str
    from_date: str
    to_date: str
    opening_balance: str
    entries: list[GeneralLedgerRow]
    closing_balance: str


# ── VAT Report ───────────────────────────────────────────────────────────────

class VATMonthlyBreakdown(BaseModel):
    month: str
    vat_collected: str
    sales_ex_vat: str
    transaction_count: int


class VATReportResponse(BaseModel):
    from_date: str
    to_date: str
    total_vat_collected: str
    total_sales_ex_vat: str
    effective_vat_rate: str
    monthly_breakdown: list[VATMonthlyBreakdown]


# ── Cash Flow Statement ─────────────────────────────────────────────────────

class CashFlowLineItem(BaseModel):
    description: str
    amount: str


class CashFlowSection(BaseModel):
    items: list[CashFlowLineItem]
    total: str


class CashFlowResponse(BaseModel):
    from_date: str
    to_date: str
    opening_cash_balance: str
    operating: CashFlowSection
    investing: CashFlowSection
    financing: CashFlowSection
    net_change: str
    closing_cash_balance: str
