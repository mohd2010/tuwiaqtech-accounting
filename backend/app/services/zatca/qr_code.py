"""Phase 2 QR code generation with 9 TLV tags for ZATCA e-invoices."""

from __future__ import annotations

import base64
import struct


def _tlv(tag: int, value: bytes) -> bytes:
    """Encode a single TLV field with 1-byte tag and 1-byte length (max 255)."""
    length = len(value)
    if length > 255:
        raise ValueError(f"TLV value too long: {length} bytes (max 255)")
    return struct.pack("BB", tag, length) + value


def _tlv_utf8(tag: int, text: str) -> bytes:
    """TLV with UTF-8 encoded text value."""
    return _tlv(tag, text.encode("utf-8"))


def _tlv_bytes(tag: int, data: bytes) -> bytes:
    """TLV with raw bytes value."""
    return _tlv(tag, data)


def generate_phase2_qr(
    seller_name: str,
    vat_number: str,
    timestamp: str,
    total_amount: str,
    vat_amount: str,
    invoice_hash: str,
    ecdsa_signature: str,
    public_key: bytes,
    certificate_signature: bytes,
    is_simplified: bool = True,
) -> str:
    """Generate a Phase 2 ZATCA QR code with 9 TLV tags.

    Tags 1-7: UTF-8 text (tags 6-7 are base64-encoded strings)
    Tags 8-9: Raw bytes (DER-encoded binary data)

    Args:
        seller_name: Seller name (UTF-8)
        vat_number: VAT number (UTF-8)
        timestamp: ISO 8601 timestamp (UTF-8)
        total_amount: Total incl. VAT (UTF-8)
        vat_amount: VAT amount (UTF-8)
        invoice_hash: Base64-encoded SHA-256 hash of the invoice XML
        ecdsa_signature: Base64-encoded ECDSA signature from ds:SignatureValue
        public_key: Public key in SubjectPublicKeyInfo DER format (raw bytes)
        certificate_signature: Certificate's own DER-encoded ECDSA signature (raw bytes)

    Returns:
        Base64-encoded TLV payload.
    """
    tlv_data = b"".join([
        _tlv_utf8(1, seller_name),
        _tlv_utf8(2, vat_number),
        _tlv_utf8(3, timestamp),
        _tlv_utf8(4, total_amount),
        _tlv_utf8(5, vat_amount),
        _tlv_utf8(6, invoice_hash),
        _tlv_utf8(7, ecdsa_signature),
        _tlv_bytes(8, public_key),
        _tlv_bytes(9, certificate_signature),
    ])

    return base64.b64encode(tlv_data).decode("ascii")
