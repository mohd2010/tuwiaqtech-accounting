"""Translation dictionary for report exports (en/ar)."""
from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Common
        "period": "Period",
        "as_of": "As of",
        "code": "Code",
        "account": "Account",
        "type": "Type",
        "debit": "Debit",
        "credit": "Credit",
        "balance": "Balance",
        "total": "Total",
        "totals": "TOTALS",
        "date": "Date",
        "reference": "Reference",
        "description": "Description",

        # Income Statement
        "income_statement": "Income Statement",
        "revenue": "Revenue",
        "total_revenue": "Total Revenue",
        "cogs": "Cost of Goods Sold",
        "total_cogs": "Total COGS",
        "gross_profit": "Gross Profit",
        "operating_expenses": "Operating Expenses",
        "total_opex": "Total Operating Expenses",
        "net_income": "NET INCOME",

        # Trial Balance
        "trial_balance": "Trial Balance",
        "balanced": "BALANCED",
        "out_of_balance": "OUT OF BALANCE",

        # Balance Sheet
        "balance_sheet": "Balance Sheet",
        "assets": "Assets",
        "liabilities": "Liabilities",
        "equity": "Equity",
        "retained_earnings": "Retained Earnings",
        "total_assets": "Total Assets",
        "total_liabilities": "Total Liabilities",
        "total_equity": "Total Equity",
        "total_le": "Total Liabilities & Equity",

        # General Ledger
        "general_ledger": "General Ledger",
        "opening_balance": "Opening Balance",
        "closing_balance": "Closing Balance",

        # VAT Report
        "vat_report": "VAT Report",
        "total_vat_collected": "Total VAT Collected",
        "total_sales_ex_vat": "Total Sales (excl. VAT)",
        "effective_vat_rate": "Effective VAT Rate",
        "month": "Month",
        "vat_collected": "VAT Collected",
        "sales_ex_vat": "Sales (excl. VAT)",
        "transactions": "Transactions",

        # Cash Flow
        "cash_flow": "Cash Flow Statement",
        "opening_cash": "Opening Cash Balance",
        "closing_cash": "Closing Cash Balance",
        "net_change": "Net Change in Cash",
        "operating": "Operating Activities",
        "investing": "Investing Activities",
        "financing": "Financing Activities",

        # AR/AP Aging
        "ar_aging": "Accounts Receivable Aging",
        "ap_aging": "Accounts Payable Aging",
        "total_receivable": "Total Receivable",
        "total_payable": "Total Payable",
        "total_overdue": "Total Overdue",
        "dso": "Days Sales Outstanding",
        "customer": "Customer",
        "supplier": "Supplier",
        "current_0_30": "Current (0-30)",
        "days_31_60": "31-60 Days",
        "days_61_90": "61-90 Days",
        "over_90": "Over 90 Days",

        # Inventory Valuation
        "inventory_valuation": "Inventory Valuation Report",
        "sku": "SKU",
        "product": "Product",
        "category": "Category",
        "quantity": "Qty",
        "cost_price": "Cost Price",
        "total_value": "Total Value",
        "warehouse": "Warehouse",
        "items": "items",
    },
    "ar": {
        # Common
        "period": "\u0627\u0644\u0641\u062a\u0631\u0629",
        "as_of": "\u0643\u0645\u0627 \u0641\u064a",
        "code": "\u0627\u0644\u0631\u0645\u0632",
        "account": "\u0627\u0644\u062d\u0633\u0627\u0628",
        "type": "\u0627\u0644\u0646\u0648\u0639",
        "debit": "\u0645\u062f\u064a\u0646",
        "credit": "\u062f\u0627\u0626\u0646",
        "balance": "\u0627\u0644\u0631\u0635\u064a\u062f",
        "total": "\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a",
        "totals": "\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a\u0627\u062a",
        "date": "\u0627\u0644\u062a\u0627\u0631\u064a\u062e",
        "reference": "\u0627\u0644\u0645\u0631\u062c\u0639",
        "description": "\u0627\u0644\u0648\u0635\u0641",

        # Income Statement
        "income_statement": "\u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u062f\u062e\u0644",
        "revenue": "\u0627\u0644\u0625\u064a\u0631\u0627\u062f\u0627\u062a",
        "total_revenue": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0625\u064a\u0631\u0627\u062f\u0627\u062a",
        "cogs": "\u062a\u0643\u0644\u0641\u0629 \u0627\u0644\u0628\u0636\u0627\u0639\u0629 \u0627\u0644\u0645\u0628\u0627\u0639\u0629",
        "total_cogs": "\u0625\u062c\u0645\u0627\u0644\u064a \u062a\u0643\u0644\u0641\u0629 \u0627\u0644\u0628\u0636\u0627\u0639\u0629",
        "gross_profit": "\u0645\u062c\u0645\u0644 \u0627\u0644\u0631\u0628\u062d",
        "operating_expenses": "\u0627\u0644\u0645\u0635\u0631\u0648\u0641\u0627\u062a \u0627\u0644\u062a\u0634\u063a\u064a\u0644\u064a\u0629",
        "total_opex": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0635\u0631\u0648\u0641\u0627\u062a \u0627\u0644\u062a\u0634\u063a\u064a\u0644\u064a\u0629",
        "net_income": "\u0635\u0627\u0641\u064a \u0627\u0644\u062f\u062e\u0644",

        # Trial Balance
        "trial_balance": "\u0645\u064a\u0632\u0627\u0646 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
        "balanced": "\u0645\u062a\u0648\u0627\u0632\u0646",
        "out_of_balance": "\u063a\u064a\u0631 \u0645\u062a\u0648\u0627\u0632\u0646",

        # Balance Sheet
        "balance_sheet": "\u0627\u0644\u0645\u064a\u0632\u0627\u0646\u064a\u0629 \u0627\u0644\u0639\u0645\u0648\u0645\u064a\u0629",
        "assets": "\u0627\u0644\u0623\u0635\u0648\u0644",
        "liabilities": "\u0627\u0644\u0627\u0644\u062a\u0632\u0627\u0645\u0627\u062a",
        "equity": "\u062d\u0642\u0648\u0642 \u0627\u0644\u0645\u0644\u0643\u064a\u0629",
        "retained_earnings": "\u0627\u0644\u0623\u0631\u0628\u0627\u062d \u0627\u0644\u0645\u0628\u0642\u0627\u0629",
        "total_assets": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0623\u0635\u0648\u0644",
        "total_liabilities": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0627\u0644\u062a\u0632\u0627\u0645\u0627\u062a",
        "total_equity": "\u0625\u062c\u0645\u0627\u0644\u064a \u062d\u0642\u0648\u0642 \u0627\u0644\u0645\u0644\u0643\u064a\u0629",
        "total_le": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0627\u0644\u062a\u0632\u0627\u0645\u0627\u062a \u0648\u062d\u0642\u0648\u0642 \u0627\u0644\u0645\u0644\u0643\u064a\u0629",

        # General Ledger
        "general_ledger": "\u062f\u0641\u062a\u0631 \u0627\u0644\u0623\u0633\u062a\u0627\u0630 \u0627\u0644\u0639\u0627\u0645",
        "opening_balance": "\u0627\u0644\u0631\u0635\u064a\u062f \u0627\u0644\u0627\u0641\u062a\u062a\u0627\u062d\u064a",
        "closing_balance": "\u0627\u0644\u0631\u0635\u064a\u062f \u0627\u0644\u062e\u062a\u0627\u0645\u064a",

        # VAT Report
        "vat_report": "\u062a\u0642\u0631\u064a\u0631 \u0636\u0631\u064a\u0628\u0629 \u0627\u0644\u0642\u064a\u0645\u0629 \u0627\u0644\u0645\u0636\u0627\u0641\u0629",
        "total_vat_collected": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0636\u0631\u064a\u0628\u0629 \u0627\u0644\u0645\u062d\u0635\u0644\u0629",
        "total_sales_ex_vat": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0628\u064a\u0639\u0627\u062a (\u0628\u062f\u0648\u0646 \u0636\u0631\u064a\u0628\u0629)",
        "effective_vat_rate": "\u0645\u0639\u062f\u0644 \u0627\u0644\u0636\u0631\u064a\u0628\u0629 \u0627\u0644\u0641\u0639\u0644\u064a",
        "month": "\u0627\u0644\u0634\u0647\u0631",
        "vat_collected": "\u0627\u0644\u0636\u0631\u064a\u0628\u0629 \u0627\u0644\u0645\u062d\u0635\u0644\u0629",
        "sales_ex_vat": "\u0627\u0644\u0645\u0628\u064a\u0639\u0627\u062a (\u0628\u062f\u0648\u0646 \u0636\u0631\u064a\u0628\u0629)",
        "transactions": "\u0627\u0644\u0645\u0639\u0627\u0645\u0644\u0627\u062a",

        # Cash Flow
        "cash_flow": "\u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u062a\u062f\u0641\u0642\u0627\u062a \u0627\u0644\u0646\u0642\u062f\u064a\u0629",
        "opening_cash": "\u0627\u0644\u0631\u0635\u064a\u062f \u0627\u0644\u0646\u0642\u062f\u064a \u0627\u0644\u0627\u0641\u062a\u062a\u0627\u062d\u064a",
        "closing_cash": "\u0627\u0644\u0631\u0635\u064a\u062f \u0627\u0644\u0646\u0642\u062f\u064a \u0627\u0644\u062e\u062a\u0627\u0645\u064a",
        "net_change": "\u0635\u0627\u0641\u064a \u0627\u0644\u062a\u063a\u064a\u0631 \u0641\u064a \u0627\u0644\u0646\u0642\u062f",
        "operating": "\u0627\u0644\u0623\u0646\u0634\u0637\u0629 \u0627\u0644\u062a\u0634\u063a\u064a\u0644\u064a\u0629",
        "investing": "\u0627\u0644\u0623\u0646\u0634\u0637\u0629 \u0627\u0644\u0627\u0633\u062a\u062b\u0645\u0627\u0631\u064a\u0629",
        "financing": "\u0627\u0644\u0623\u0646\u0634\u0637\u0629 \u0627\u0644\u062a\u0645\u0648\u064a\u0644\u064a\u0629",

        # AR/AP Aging
        "ar_aging": "\u062a\u0642\u0627\u062f\u0645 \u0627\u0644\u0630\u0645\u0645 \u0627\u0644\u0645\u062f\u064a\u0646\u0629",
        "ap_aging": "\u062a\u0642\u0627\u062f\u0645 \u0627\u0644\u0630\u0645\u0645 \u0627\u0644\u062f\u0627\u0626\u0646\u0629",
        "total_receivable": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0633\u062a\u062d\u0642\u0627\u062a",
        "total_payable": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u0633\u062a\u062d\u0642\u0627\u062a",
        "total_overdue": "\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0645\u062a\u0623\u062e\u0631\u0627\u062a",
        "dso": "\u0623\u064a\u0627\u0645 \u0627\u0644\u0645\u0628\u064a\u0639\u0627\u062a \u0627\u0644\u0645\u0639\u0644\u0642\u0629",
        "customer": "\u0627\u0644\u0639\u0645\u064a\u0644",
        "supplier": "\u0627\u0644\u0645\u0648\u0631\u062f",
        "current_0_30": "\u062c\u0627\u0631\u064a (0-30)",
        "days_31_60": "31-60 \u064a\u0648\u0645",
        "days_61_90": "61-90 \u064a\u0648\u0645",
        "over_90": "\u0623\u0643\u062b\u0631 \u0645\u0646 90 \u064a\u0648\u0645",

        # Inventory Valuation
        "inventory_valuation": "\u062a\u0642\u0631\u064a\u0631 \u062a\u0642\u064a\u064a\u0645 \u0627\u0644\u0645\u062e\u0632\u0648\u0646",
        "sku": "\u0631\u0645\u0632 \u0627\u0644\u0645\u0646\u062a\u062c",
        "product": "\u0627\u0644\u0645\u0646\u062a\u062c",
        "category": "\u0627\u0644\u0641\u0626\u0629",
        "quantity": "\u0627\u0644\u0643\u0645\u064a\u0629",
        "cost_price": "\u0633\u0639\u0631 \u0627\u0644\u062a\u0643\u0644\u0641\u0629",
        "total_value": "\u0627\u0644\u0642\u064a\u0645\u0629 \u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a\u0629",
        "warehouse": "\u0627\u0644\u0645\u0633\u062a\u0648\u062f\u0639",
        "items": "\u0639\u0646\u0627\u0635\u0631",
    },
}


def t(lang: str, key: str) -> str:
    """Get translated label. Falls back to English."""
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(
        key, TRANSLATIONS["en"].get(key, key)
    )
