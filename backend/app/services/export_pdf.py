"""PDF export functions for financial reports using fpdf2."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from fpdf import FPDF

from backend.app.services.export_i18n import t


# ── Shared helpers ──────────────────────────────────────────────────────────

_COL_BG = (31, 78, 121)   # dark blue header
_SEC_BG = (214, 228, 240)  # light blue section
_LINE_H = 7

_FONT_DIR = Path(__file__).parent / "fonts"
_ARABIC_FONT = "NotoSansArabic"


def _setup_font(pdf: FPDF, lang: str) -> str:
    """Setup font for PDF. Returns font family name to use."""
    if lang == "ar":
        pdf.add_font(_ARABIC_FONT, "", str(_FONT_DIR / "NotoSansArabic-Regular.ttf"))
        pdf.add_font(_ARABIC_FONT, "B", str(_FONT_DIR / "NotoSansArabic-Bold.ttf"))
        return _ARABIC_FONT
    return "Helvetica"


def _new_pdf(title: str, subtitle: str, lang: str = "en") -> tuple[FPDF, str]:
    """Create a landscape PDF with title and subtitle. Returns (pdf, font)."""
    pdf = FPDF(orientation="L")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    font = _setup_font(pdf, lang)
    pdf.set_font(font, "B", 16)
    pdf.cell(0, 10, title, ln=True)
    pdf.set_font(font, "", 9)
    pdf.cell(0, 6, subtitle, ln=True)
    pdf.ln(4)
    return pdf, font


def _new_pdf_portrait(title: str, subtitle: str, lang: str = "en") -> tuple[FPDF, str]:
    """Create a portrait PDF with title and subtitle. Returns (pdf, font)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    font = _setup_font(pdf, lang)
    pdf.set_font(font, "B", 16)
    pdf.cell(0, 10, title, ln=True)
    pdf.set_font(font, "", 9)
    pdf.cell(0, 6, subtitle, ln=True)
    pdf.ln(4)
    return pdf, font


def _header_row(pdf: FPDF, headers: list[str], widths: list[int], font: str = "Helvetica") -> None:
    """Draw a colored header row."""
    pdf.set_fill_color(*_COL_BG)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(font, "B", 9)
    for i, (h, w) in enumerate(zip(headers, widths)):
        align = "R" if i > 0 else "L"
        pdf.cell(w, _LINE_H, h, border=1, fill=True, align=align)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)


def _data_row(pdf: FPDF, values: list[str], widths: list[int], bold: bool = False, font: str = "Helvetica") -> None:
    """Draw a data row."""
    pdf.set_font(font, "B" if bold else "", 8)
    for i, (v, w) in enumerate(zip(values, widths)):
        align = "R" if i > 0 else "L"
        pdf.cell(w, _LINE_H, v, border="B", align=align)
    pdf.ln()


def _section_header(pdf: FPDF, text: str, total_width: int, font: str = "Helvetica") -> None:
    """Draw a section header with light background."""
    pdf.set_fill_color(*_SEC_BG)
    pdf.set_font(font, "B", 9)
    pdf.cell(total_width, _LINE_H, text, fill=True, ln=True)


def _fmt(value: str) -> str:
    """Format a numeric string for display."""
    try:
        n = float(value)
        return f"{n:,.4f}"
    except (ValueError, TypeError):
        return str(value)


def _safe_text(text: str, lang: str = "en") -> str:
    """Replace non-latin-1 characters for PDF built-in fonts. Skips for Arabic (Unicode font)."""
    if lang == "ar":
        return text
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _to_bytes(pdf: FPDF) -> io.BytesIO:
    """Output PDF to BytesIO."""
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf


# ── 1. Income Statement ────────────────────────────────────────────────────


def export_income_statement_pdf(data: dict[str, Any], lang: str = "en") -> io.BytesIO:
    pdf, font = _new_pdf_portrait(
        t(lang, "income_statement"),
        f"{t(lang, 'period')}: {data['from_date']} to {data['to_date']}",
        lang,
    )
    w1, w2 = 120, 50

    # Revenue
    _section_header(pdf, t(lang, "revenue"), w1 + w2, font)
    for item in data.get("revenue_detail", []):
        _data_row(pdf, [f"  {item['name']}", _fmt(item["amount"])], [w1, w2], font=font)
    _data_row(pdf, [t(lang, "total_revenue"), _fmt(data["revenue"])], [w1, w2], bold=True, font=font)
    pdf.ln(3)

    # COGS
    _section_header(pdf, t(lang, "cogs"), w1 + w2, font)
    for item in data.get("expense_detail", []):
        if item["code"] == "5000":
            _data_row(pdf, [f"  {item['name']}", _fmt(item["amount"])], [w1, w2], font=font)
    _data_row(pdf, [t(lang, "total_cogs"), _fmt(data["cogs"])], [w1, w2], bold=True, font=font)
    pdf.ln(3)

    # Gross Profit
    pdf.set_font(font, "B", 10)
    pdf.cell(w1, 8, t(lang, "gross_profit"))
    pdf.cell(w2, 8, _fmt(data["gross_profit"]), align="R", ln=True)
    pdf.ln(3)

    # OpEx
    _section_header(pdf, t(lang, "operating_expenses"), w1 + w2, font)
    for item in data.get("expense_detail", []):
        if item["code"] != "5000":
            _data_row(pdf, [f"  {item['name']}", _fmt(item["amount"])], [w1, w2], font=font)
    _data_row(pdf, [t(lang, "total_opex"), _fmt(data["operating_expenses"])], [w1, w2], bold=True, font=font)
    pdf.ln(3)

    # Net Income
    pdf.set_font(font, "B", 12)
    pdf.cell(w1, 10, t(lang, "net_income"))
    pdf.cell(w2, 10, _fmt(data["net_income"]), align="R", ln=True)

    return _to_bytes(pdf)


# ── 2. Trial Balance ──────────────────────────────────────────────────────


def export_trial_balance_pdf(data: dict[str, Any], lang: str = "en") -> io.BytesIO:
    pdf, font = _new_pdf(
        t(lang, "trial_balance"),
        f"{t(lang, 'period')}: {data['from_date']} to {data['to_date']}",
        lang,
    )
    widths = [30, 80, 40, 50, 50]

    _header_row(pdf, [t(lang, "code"), t(lang, "account"), t(lang, "type"), t(lang, "debit"), t(lang, "credit")], widths, font)
    for acct in data.get("accounts", []):
        _data_row(pdf, [
            acct["account_code"],
            acct["account_name"],
            acct["account_type"],
            _fmt(acct["debit"]),
            _fmt(acct["credit"]),
        ], widths, font=font)

    _data_row(pdf, [t(lang, "totals"), "", "", _fmt(data["total_debit"]), _fmt(data["total_credit"])], widths, bold=True, font=font)

    pdf.ln(4)
    status = t(lang, "balanced") if data.get("is_balanced") else t(lang, "out_of_balance")
    color = (0, 128, 0) if data.get("is_balanced") else (255, 0, 0)
    pdf.set_text_color(*color)
    pdf.set_font(font, "B", 11)
    pdf.cell(0, 8, status, ln=True)
    pdf.set_text_color(0, 0, 0)

    return _to_bytes(pdf)


# ── 3. Balance Sheet ──────────────────────────────────────────────────────


def export_balance_sheet_pdf(data: dict[str, Any], lang: str = "en") -> io.BytesIO:
    pdf, font = _new_pdf(
        t(lang, "balance_sheet"),
        f"{t(lang, 'as_of')} {data['as_of_date']}",
        lang,
    )
    widths = [30, 100, 60]

    section_map = [
        ("assets", "assets", "total_assets"),
        ("liabilities", "liabilities", "total_liabilities"),
        ("equity", "equity", "total_equity"),
    ]
    total_label_map = {
        "assets": "total_assets",
        "liabilities": "total_liabilities",
        "equity": "total_equity",
    }

    for section_key, items_key, total_key in section_map:
        section_label = t(lang, section_key)
        _section_header(pdf, section_label, sum(widths), font)
        _header_row(pdf, [t(lang, "code"), t(lang, "account"), t(lang, "balance")], widths, font)
        for item in data.get(items_key, []):
            _data_row(pdf, [item["code"], item["name"], _fmt(item["balance"])], widths, font=font)
        if section_key == "equity":
            _data_row(pdf, ["", t(lang, "retained_earnings"), _fmt(data["retained_earnings"])], widths, font=font)
        _data_row(pdf, ["", t(lang, total_label_map[section_key]), _fmt(data[total_key])], widths, bold=True, font=font)
        pdf.ln(3)

    pdf.set_font(font, "B", 11)
    pdf.cell(130, 8, t(lang, "total_le"))
    pdf.cell(60, 8, _fmt(data["total_liabilities_and_equity"]), align="R", ln=True)

    pdf.ln(3)
    status = t(lang, "balanced") if data.get("is_balanced") else t(lang, "out_of_balance")
    color = (0, 128, 0) if data.get("is_balanced") else (255, 0, 0)
    pdf.set_text_color(*color)
    pdf.set_font(font, "B", 10)
    pdf.cell(0, 8, status, ln=True)
    pdf.set_text_color(0, 0, 0)

    return _to_bytes(pdf)


# ── 4. General Ledger ────────────────────────────────────────────────────


def export_general_ledger_pdf(data: dict[str, Any], lang: str = "en") -> io.BytesIO:
    pdf, font = _new_pdf(
        t(lang, "general_ledger"),
        f"{t(lang, 'account')}: {data['account_code']} - {data['account_name']}  |  {data['from_date']} to {data['to_date']}",
        lang,
    )
    widths = [30, 35, 80, 40, 40, 45]

    _header_row(pdf, [t(lang, "date"), t(lang, "reference"), t(lang, "description"), t(lang, "debit"), t(lang, "credit"), t(lang, "balance")], widths, font)

    # Opening balance
    _data_row(pdf, [t(lang, "opening_balance"), "", "", "", "", _fmt(data["opening_balance"])], widths, bold=True, font=font)

    for entry in data.get("entries", []):
        _data_row(pdf, [
            entry["date"],
            entry.get("reference") or "",
            entry["description"][:40],
            _fmt(entry["debit"]),
            _fmt(entry["credit"]),
            _fmt(entry["running_balance"]),
        ], widths, font=font)

    _data_row(pdf, [t(lang, "closing_balance"), "", "", "", "", _fmt(data["closing_balance"])], widths, bold=True, font=font)

    return _to_bytes(pdf)


# ── 5. VAT Report ────────────────────────────────────────────────────────


def export_vat_report_pdf(data: dict[str, Any], lang: str = "en") -> io.BytesIO:
    pdf, font = _new_pdf(
        t(lang, "vat_report"),
        f"{t(lang, 'period')}: {data['from_date']} to {data['to_date']}",
        lang,
    )
    w1, w2 = 100, 60

    # Summary
    pdf.set_font(font, "B", 10)
    for label_key, data_key in [
        ("total_vat_collected", "total_vat_collected"),
        ("total_sales_ex_vat", "total_sales_ex_vat"),
    ]:
        pdf.cell(w1, 8, t(lang, label_key))
        pdf.cell(w2, 8, _fmt(data[data_key]), align="R", ln=True)
    pdf.cell(w1, 8, t(lang, "effective_vat_rate"))
    pdf.cell(w2, 8, f"{data['effective_vat_rate']}%", align="R", ln=True)
    pdf.ln(6)

    # Monthly breakdown
    widths = [50, 55, 55, 40]
    _header_row(pdf, [t(lang, "month"), t(lang, "vat_collected"), t(lang, "sales_ex_vat"), t(lang, "transactions")], widths, font)
    for m in data.get("monthly_breakdown", []):
        _data_row(pdf, [
            m["month"],
            _fmt(m["vat_collected"]),
            _fmt(m["sales_ex_vat"]),
            str(m["transaction_count"]),
        ], widths, font=font)

    return _to_bytes(pdf)


# ── 6. Cash Flow ─────────────────────────────────────────────────────────


def export_cash_flow_pdf(data: dict[str, Any], lang: str = "en") -> io.BytesIO:
    pdf, font = _new_pdf_portrait(
        t(lang, "cash_flow"),
        f"{t(lang, 'period')}: {data['from_date']} to {data['to_date']}",
        lang,
    )
    w1, w2 = 120, 50

    # Opening
    pdf.set_font(font, "B", 10)
    pdf.cell(w1, 8, t(lang, "opening_cash"))
    pdf.cell(w2, 8, _fmt(data["opening_cash_balance"]), align="R", ln=True)
    pdf.ln(3)

    for section_label_key, section_key in [
        ("operating", "operating"),
        ("investing", "investing"),
        ("financing", "financing"),
    ]:
        section = data.get(section_key, {})
        _section_header(pdf, t(lang, section_label_key), w1 + w2, font)
        for item in section.get("items", []):
            _data_row(pdf, [f"  {item['description']}", _fmt(item["amount"])], [w1, w2], font=font)
        _data_row(pdf, [f"{t(lang, 'total')} {t(lang, section_label_key)}", _fmt(section.get("total", "0"))], [w1, w2], bold=True, font=font)
        pdf.ln(3)

    pdf.set_font(font, "B", 10)
    pdf.cell(w1, 8, t(lang, "net_change"))
    pdf.cell(w2, 8, _fmt(data["net_change"]), align="R", ln=True)
    pdf.ln(3)

    pdf.set_font(font, "B", 12)
    pdf.cell(w1, 10, t(lang, "closing_cash"))
    pdf.cell(w2, 10, _fmt(data["closing_cash_balance"]), align="R", ln=True)

    return _to_bytes(pdf)


# ── 7. AR Aging ──────────────────────────────────────────────────────────


def export_ar_aging_pdf(data: dict[str, Any], lang: str = "en") -> io.BytesIO:
    pdf, font = _new_pdf(
        t(lang, "ar_aging"),
        f"{t(lang, 'as_of')} {data['as_of_date']}",
        lang,
    )

    # KPI
    kpi = data.get("kpi", {})
    pdf.set_font(font, "B", 10)
    pdf.cell(80, 8, t(lang, "total_receivable"))
    pdf.cell(50, 8, _fmt(kpi.get("total_receivable", "0")), align="R", ln=True)
    pdf.cell(80, 8, t(lang, "total_overdue"))
    pdf.cell(50, 8, _fmt(kpi.get("total_overdue", "0")), align="R", ln=True)
    pdf.cell(80, 8, t(lang, "dso"))
    pdf.cell(50, 8, f"{kpi.get('dso', '0')} days", align="R", ln=True)
    pdf.ln(4)

    widths = [55, 40, 40, 40, 40, 45]
    _header_row(pdf, [t(lang, "customer"), t(lang, "current_0_30"), t(lang, "days_31_60"), t(lang, "days_61_90"), t(lang, "over_90"), t(lang, "total")], widths, font)
    for cust in data.get("customers", []):
        _data_row(pdf, [
            cust["name"][:25],
            _fmt(cust["current"]),
            _fmt(cust["days_31_60"]),
            _fmt(cust["days_61_90"]),
            _fmt(cust["over_90"]),
            _fmt(cust["total"]),
        ], widths, font=font)

    totals = data.get("totals", {})
    _data_row(pdf, [
        t(lang, "total"),
        _fmt(totals.get("current", "0")),
        _fmt(totals.get("days_31_60", "0")),
        _fmt(totals.get("days_61_90", "0")),
        _fmt(totals.get("over_90", "0")),
        _fmt(totals.get("total", "0")),
    ], widths, bold=True, font=font)

    return _to_bytes(pdf)


# ── 9. Inventory Valuation ──────────────────────────────────────────────


def export_inventory_valuation_pdf(data: dict[str, Any], lang: str = "en") -> io.BytesIO:
    subtitle = f"{t(lang, 'as_of')} {data['as_of_date']}"
    if data.get("warehouse_filter"):
        subtitle += f"  |  {t(lang, 'warehouse')}: {data['warehouse_filter']}"
    if data.get("category_filter"):
        subtitle += f"  |  {t(lang, 'category')}: {data['category_filter']}"
    pdf, font = _new_pdf(t(lang, "inventory_valuation"), subtitle, lang)

    widths = [25, 50, 30, 20, 30, 35]
    _header_row(pdf, [t(lang, "sku"), t(lang, "product"), t(lang, "category"), t(lang, "quantity"), t(lang, "cost_price"), t(lang, "total_value")], widths, font)

    for item in data.get("items", []):
        _data_row(pdf, [
            _safe_text(item["sku"], lang),
            _safe_text(item["name"][:25], lang),
            _safe_text(item["category"][:15], lang),
            str(item["quantity"]),
            _fmt(item["cost_price"]),
            _fmt(item["total_value"]),
        ], widths, font=font)

    # Summary
    _data_row(pdf, [
        t(lang, "totals"),
        "",
        f"{data['total_items']} {t(lang, 'items')}",
        str(data["total_quantity"]),
        "",
        _fmt(data["total_value"]),
    ], widths, bold=True, font=font)

    return _to_bytes(pdf)


# ── 8. AP Aging ──────────────────────────────────────────────────────────


def export_ap_aging_pdf(data: dict[str, Any], lang: str = "en") -> io.BytesIO:
    pdf, font = _new_pdf(
        t(lang, "ap_aging"),
        f"{t(lang, 'as_of')} {data['as_of_date']}",
        lang,
    )

    # KPI
    kpi = data.get("kpi", {})
    pdf.set_font(font, "B", 10)
    pdf.cell(80, 8, t(lang, "total_payable"))
    pdf.cell(50, 8, _fmt(kpi.get("total_payable", "0")), align="R", ln=True)
    pdf.cell(80, 8, t(lang, "total_overdue"))
    pdf.cell(50, 8, _fmt(kpi.get("total_overdue", "0")), align="R", ln=True)
    pdf.ln(4)

    widths = [55, 40, 40, 40, 40, 45]
    _header_row(pdf, [t(lang, "supplier"), t(lang, "current_0_30"), t(lang, "days_31_60"), t(lang, "days_61_90"), t(lang, "over_90"), t(lang, "total")], widths, font)
    for supp in data.get("suppliers", []):
        _data_row(pdf, [
            supp["name"][:25],
            _fmt(supp["current"]),
            _fmt(supp["days_31_60"]),
            _fmt(supp["days_61_90"]),
            _fmt(supp["over_90"]),
            _fmt(supp["total"]),
        ], widths, font=font)

    totals = data.get("totals", {})
    _data_row(pdf, [
        t(lang, "total"),
        _fmt(totals.get("current", "0")),
        _fmt(totals.get("days_31_60", "0")),
        _fmt(totals.get("days_61_90", "0")),
        _fmt(totals.get("over_90", "0")),
        _fmt(totals.get("total", "0")),
    ], widths, bold=True, font=font)

    return _to_bytes(pdf)
