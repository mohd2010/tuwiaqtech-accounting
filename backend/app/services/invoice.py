from __future__ import annotations

import base64
import struct
from datetime import datetime

# ── Seller defaults (move to config / DB for multi-tenant) ───────────────────
SELLER_NAME = "Tuwaiq Outdoor"
VAT_REGISTRATION_NUMBER = "399999999999993"  # placeholder – replace with real TIN


def _tlv(tag: int, value: str) -> bytes:
    """Encode a single TLV field per ZATCA simplified e-invoice spec.

    Format: [tag: 1 byte] [length: 1 byte] [value: n bytes (UTF-8)]
    """
    encoded = value.encode("utf-8")
    return struct.pack("BB", tag, len(encoded)) + encoded


def generate_zatca_qr(
    seller_name: str,
    vat_number: str,
    timestamp: datetime,
    total_amount: str,
    vat_amount: str,
) -> str:
    """Build a ZATCA Phase-1 QR payload (Base64-encoded TLV).

    The five mandatory tags are:
        1 – Seller's name
        2 – VAT registration number
        3 – Timestamp (ISO 8601 with timezone)
        4 – Invoice total (including VAT)
        5 – VAT amount
    """
    iso_ts = timestamp.isoformat(timespec="seconds")

    tlv_bytes = b"".join([
        _tlv(1, seller_name),
        _tlv(2, vat_number),
        _tlv(3, iso_ts),
        _tlv(4, total_amount),
        _tlv(5, vat_amount),
    ])

    return base64.b64encode(tlv_bytes).decode("ascii")


def generate_invoice_number(sequence: int, year: int | None = None) -> str:
    """Return a formatted invoice number like INV-2026-0001."""
    if year is None:
        year = datetime.now().year
    return f"INV-{year}-{sequence:04d}"


def generate_credit_note_number(sequence: int, year: int | None = None) -> str:
    """Return a formatted credit note number like CN-2026-0001."""
    if year is None:
        year = datetime.now().year
    return f"CN-{year}-{sequence:04d}"


def generate_expense_number(sequence: int, year: int | None = None) -> str:
    """Return a formatted expense reference like EXP-2026-0001."""
    if year is None:
        year = datetime.now().year
    return f"EXP-{year}-{sequence:04d}"


def generate_quote_number(sequence: int, year: int | None = None) -> str:
    """Return a formatted quote number like Q-2026-001."""
    if year is None:
        year = datetime.now().year
    return f"Q-{year}-{sequence:03d}"
