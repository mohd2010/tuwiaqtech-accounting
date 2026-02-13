"""ZATCA business rule validation (BR-KSA-*) for e-invoice data."""

from __future__ import annotations

import re
from decimal import Decimal

from backend.app.services.zatca.xml_builder import InvoiceData


def validate_invoice_data(data: InvoiceData) -> list[str]:
    """Validate against ZATCA business rules. Returns list of errors (empty = valid)."""
    errors: list[str] = []

    # BR-KSA-01: ProfileID
    if data.profile_id != "reporting:1.0":
        errors.append("BR-KSA-01: ProfileID must be 'reporting:1.0'")

    # BR-KSA-03: UUID format
    uuid_pattern = re.compile(r"^[0-9a-fA-F\-]{36}$")
    if not uuid_pattern.match(data.uuid):
        errors.append("BR-KSA-03: UUID must be 36 chars (letters, digits, dashes)")

    # BR-KSA-05: Type code (includes 386 for prepayment)
    if data.type_code not in ("388", "381", "383", "386"):
        errors.append("BR-KSA-05: InvoiceTypeCode must be 388, 381, 383, or 386")

    # BR-KSA-06: Sub-type format (NNPNESB, 7 chars)
    # Positions 1-2: "01" (standard) or "02" (simplified); positions 3-7: binary
    if not re.match(r"^0[12][01]{5}$", data.sub_type):
        errors.append("BR-KSA-06: Sub-type must be 7-char format: 01/02 prefix + 5 binary digits")

    # BR-KSA-39/40: VAT number = 15 digits, starts & ends with 3
    seller_vat = data.seller.vat_number
    if not re.match(r"^3\d{13}3$", seller_vat):
        errors.append(
            "BR-KSA-39/40: Seller VAT number must be 15 digits starting and ending with 3"
        )

    # BR-KSA-09: Seller address complete
    if not data.seller.street:
        errors.append("BR-KSA-09: Seller street is mandatory")
    if not data.seller.city:
        errors.append("BR-KSA-09: Seller city is mandatory")
    if not data.seller.district:
        errors.append("BR-KSA-09: Seller district is mandatory")

    # BR-KSA-37: Building number mandatory for seller
    if not data.seller.building_number:
        errors.append("BR-KSA-37: Seller building number is mandatory")
    elif not re.match(r"^\d{4}$", data.seller.building_number):
        errors.append("BR-KSA-37: Building number must be exactly 4 digits")

    # BR-KSA-66: Postal code = 5 digits
    if not re.match(r"^\d{5}$", data.seller.postal_code):
        errors.append("BR-KSA-66: Postal code must be exactly 5 digits")

    # BR-KSA-25: Buyer name mandatory for standard (B2B) invoices
    if data.sub_type == "0100000":
        if not data.buyer or not data.buyer.name:
            errors.append("BR-KSA-25: Buyer name is mandatory for standard invoices")
        if not data.buyer or not data.buyer.vat_number:
            errors.append("BR-KSA-25: Buyer VAT number is mandatory for standard invoices")

    # BR-KSA-EN16931-08: Total VAT = sum of line VAT
    line_vat_sum = sum(line.vat_amount for line in data.lines)
    if abs(data.total_vat - line_vat_sum) > Decimal("0.02"):
        errors.append(
            f"BR-KSA-EN16931-08: Total VAT ({data.total_vat}) != sum of line VAT ({line_vat_sum})"
        )

    # BR-KSA-EN16931-11: Line extension = unit_price × quantity
    for line in data.lines:
        expected = (line.unit_price * line.quantity).quantize(Decimal("0.01"))
        actual = line.net_amount.quantize(Decimal("0.01"))
        if abs(expected - actual) > Decimal("0.02"):
            errors.append(
                f"BR-KSA-EN16931-11: Line {line.line_id} net_amount ({actual}) "
                f"!= unit_price * qty ({expected})"
            )

    # BR-KSA-F-04: Monetary amounts max 2 decimals
    for line in data.lines:
        for field_name, val in [
            ("net_amount", line.net_amount),
            ("vat_amount", line.vat_amount),
            ("unit_price", line.unit_price),
        ]:
            if val != val.quantize(Decimal("0.01")):
                errors.append(
                    f"BR-KSA-F-04: Line {line.line_id} {field_name} has more than 2 decimals"
                )

    # BR-KSA-15: Supply date mandatory for tax invoices (standard)
    if data.type_code == "388" and data.sub_type.startswith("01"):
        if not data.supply_date:
            errors.append("BR-KSA-15: Supply date mandatory for standard tax invoices")

    # BR-KSA-17 / BR-KSA-56: Credit/debit notes require reason + billing reference
    if data.type_code in ("381", "383"):
        if not data.billing_reference_id:
            errors.append("BR-KSA-56: Billing reference mandatory for credit/debit notes")
        if not data.credit_debit_reason:
            errors.append("BR-KSA-17: Reason mandatory for credit/debit notes")

    # BR-KSA-18: VAT category must be S, Z, E, or O
    for line in data.lines:
        if line.vat_category_code not in ("S", "Z", "E", "O"):
            errors.append(
                f"BR-KSA-18: Line {line.line_id} invalid VAT category "
                f"'{line.vat_category_code}'"
            )

    # BR-KSA-42: Buyer name mandatory for standard (B2B) invoices
    if data.sub_type.startswith("01"):
        if not data.buyer or not data.buyer.name:
            errors.append("BR-KSA-42: Buyer name mandatory for standard invoices")

    # BR-KSA-44: Buyer VAT number format
    if data.buyer and data.buyer.vat_number:
        if not re.match(r"^3\d{13}3$", data.buyer.vat_number):
            errors.append(
                "BR-KSA-44: Buyer VAT number must be 15 digits starting and ending with 3"
            )

    # BR-KSA-51: Line amount with VAT = net + VAT
    for line in data.lines:
        if line.line_amount_incl_vat > Decimal("0"):
            expected = (line.net_amount + line.vat_amount).quantize(Decimal("0.01"))
            actual = line.line_amount_incl_vat.quantize(Decimal("0.01"))
            if abs(expected - actual) > Decimal("0.01"):
                errors.append(
                    f"BR-KSA-51: Line {line.line_id} amount_incl_vat ({actual}) "
                    f"!= net + vat ({expected})"
                )

    # BR-KSA-63/67: Buyer address mandatory for B2B when country is SA
    if data.sub_type.startswith("01") and data.buyer:
        if data.buyer.country_code == "SA":
            if not data.buyer.street:
                errors.append("BR-KSA-63: Buyer street mandatory when country is SA")
            if not data.buyer.city:
                errors.append("BR-KSA-63: Buyer city mandatory when country is SA")
            if not data.buyer.district:
                errors.append("BR-KSA-63: Buyer district mandatory when country is SA")
            if not data.buyer.building_number:
                errors.append("BR-KSA-63: Buyer building number mandatory when country is SA")
            if data.buyer.postal_code and not re.match(r"^\d{5}$", data.buyer.postal_code):
                errors.append("BR-KSA-67: Buyer postal code must be 5 digits")

    # BR-KSA-70: Issue time mandatory
    if not data.issue_time:
        errors.append("BR-KSA-70: Issue time is mandatory")

    # BR-CO-15: TaxInclusiveAmount = TaxExclusiveAmount + TotalVAT
    expected_incl = (data.total_excluding_vat + data.total_vat).quantize(Decimal("0.01"))
    actual_incl = data.total_including_vat.quantize(Decimal("0.01"))
    if abs(expected_incl - actual_incl) > Decimal("0.01"):
        errors.append(
            f"BR-CO-15: total_including_vat ({actual_incl}) "
            f"!= excl + vat ({expected_incl})"
        )

    return errors
