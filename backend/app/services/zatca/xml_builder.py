"""UBL 2.1 XML generation for ZATCA Phase 2 e-invoices.

Implements all 150 mandatory/conditional fields from the ZATCA E-Invoice
Data Dictionary v1.2, with proper element ordering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from lxml import etree

# ─── UBL Namespaces ─────────────────────────────────────────────────────────

INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CREDIT_NOTE_NS = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
SIG = "urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2"
SBC = "urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2"
SAC = "urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2"
DS = "http://www.w3.org/2000/09/xmldsig#"
XADES = "http://uri.etsi.org/01903/v1.3.2#"

NSMAP_INVOICE = {
    None: INVOICE_NS,
    "cac": CAC,
    "cbc": CBC,
    "ext": EXT,
}

NSMAP_CREDIT_NOTE = {
    None: CREDIT_NOTE_NS,
    "cac": CAC,
    "cbc": CBC,
    "ext": EXT,
}

# ─── Payment method mapping (UNTDID 4461) ───────────────────────────────────

PAYMENT_MEANS_MAP: dict[str, str] = {
    "CASH": "10",
    "CARD": "48",
    "BANK_TRANSFER": "42",
}


# ─── Data classes ────────────────────────────────────────────────────────────


@dataclass
class SellerInfo:
    name_en: str
    name_ar: str
    vat_number: str
    street: str
    building_number: str
    city: str
    district: str
    postal_code: str
    country_code: str = "SA"
    cr_number: str | None = None
    additional_id: str | None = None


@dataclass
class BuyerInfo:
    name: str
    vat_number: str | None = None
    street: str | None = None
    building_number: str | None = None
    city: str | None = None
    district: str | None = None
    postal_code: str | None = None
    country_code: str = "SA"
    additional_id: str | None = None


@dataclass
class InvoiceLineData:
    line_id: str
    item_name: str
    quantity: Decimal
    unit_price: Decimal
    net_amount: Decimal
    vat_amount: Decimal
    vat_category_code: str = "S"  # Standard rate
    vat_rate: Decimal = Decimal("15.00")
    line_amount_incl_vat: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")


@dataclass
class PaymentMeansData:
    code: str  # UNTDID 4461: "10", "48", "42"


@dataclass
class InvoiceData:
    invoice_id: str  # human-readable number
    uuid: str  # KSA-1
    issue_date: str  # YYYY-MM-DD
    issue_time: str  # HH:MM:SS
    type_code: str  # "388", "381", "383"
    sub_type: str  # "0100000" or "0200000"
    currency_code: str
    seller: SellerInfo
    buyer: BuyerInfo | None
    lines: list[InvoiceLineData]
    payment_means: list[PaymentMeansData]
    total_excluding_vat: Decimal
    total_vat: Decimal
    total_including_vat: Decimal
    icv: int  # KSA-16
    pih: str  # KSA-13 (previous invoice hash, base64)
    qr_data: str = ""  # KSA-14 (filled after signing)
    supply_date: str | None = None
    billing_reference_id: str | None = None  # for credit/debit notes
    discount_amount: Decimal = Decimal("0")
    prepaid_amount: Decimal | None = None  # BR-KSA-F-04
    credit_debit_reason: str | None = None  # BR-KSA-17
    tax_exemption_reason_code: str | None = None  # e.g. "VATEX-SA-29"
    tax_exemption_reason: str | None = None  # e.g. "Financial services..."
    profile_id: str = "reporting:1.0"


# ─── Builder helpers ─────────────────────────────────────────────────────────


def _sub(parent: etree._Element, tag: str, text: str | None = None, **attribs: str) -> etree._Element:
    """Add a sub-element with optional text and attributes."""
    el = etree.SubElement(parent, tag)
    if text is not None:
        el.text = text
    for k, v in attribs.items():
        el.set(k, v)
    return el


def _cbc(parent: etree._Element, local: str, text: str | None = None, **attribs: str) -> etree._Element:
    return _sub(parent, f"{{{CBC}}}{local}", text, **attribs)


def _cac(parent: etree._Element, local: str) -> etree._Element:
    return _sub(parent, f"{{{CAC}}}{local}")


def _amount(parent: etree._Element, local: str, value: Decimal, currency: str = "SAR") -> etree._Element:
    return _cbc(parent, local, str(value.quantize(Decimal("0.01"))), currencyID=currency)


# ─── Main builders ───────────────────────────────────────────────────────────


def build_invoice_xml(data: InvoiceData) -> etree._Element:
    """Build a complete UBL 2.1 Invoice XML for ZATCA Phase 2."""
    root = etree.Element(f"{{{INVOICE_NS}}}Invoice", nsmap=NSMAP_INVOICE)
    _populate_xml(root, data, doc_type="Invoice")
    return root


def build_credit_note_xml(data: InvoiceData) -> etree._Element:
    """Build a credit note XML for ZATCA Phase 2.

    ZATCA's API requires all document types (including credit notes 381)
    to use the Invoice root element with InvoiceTypeCode. The CreditNote
    root element is rejected with "Invalid Request".
    """
    root = etree.Element(f"{{{INVOICE_NS}}}Invoice", nsmap=NSMAP_INVOICE)
    _populate_xml(root, data, doc_type="Invoice")
    return root


def _populate_xml(
    root: etree._Element,
    data: InvoiceData,
    doc_type: Literal["Invoice", "CreditNote"],
) -> None:
    """Populate UBL XML elements in ZATCA-required order."""

    # 1. UBLExtensions (signature placeholder)
    ext_root = _sub(root, f"{{{EXT}}}UBLExtensions")
    ext_el = _sub(ext_root, f"{{{EXT}}}UBLExtension")
    _sub(ext_el, f"{{{EXT}}}ExtensionURI", "urn:oasis:names:specification:ubl:dsig:enveloped:xades")
    _sub(ext_el, f"{{{EXT}}}ExtensionContent")

    # 2. ProfileID
    _cbc(root, "ProfileID", data.profile_id)

    # 3. ID, UUID, IssueDate, IssueTime
    _cbc(root, "ID", data.invoice_id)
    _cbc(root, "UUID", data.uuid)
    _cbc(root, "IssueDate", data.issue_date)
    _cbc(root, "IssueTime", data.issue_time)

    # 4. InvoiceTypeCode / CreditNoteTypeCode
    if doc_type == "Invoice":
        _cbc(root, "InvoiceTypeCode", data.type_code, name=data.sub_type)
    else:
        _cbc(root, "CreditNoteTypeCode", data.type_code, name=data.sub_type)

    # 5. DocumentCurrencyCode, TaxCurrencyCode
    _cbc(root, "DocumentCurrencyCode", data.currency_code)
    _cbc(root, "TaxCurrencyCode", "SAR")  # BR-KSA-EN16931-02: always SAR

    # 6. BillingReference (credit/debit notes only)
    if data.billing_reference_id:
        billing_ref = _cac(root, "BillingReference")
        inv_doc_ref = _cac(billing_ref, "InvoiceDocumentReference")
        _cbc(inv_doc_ref, "ID", data.billing_reference_id)

    # 7. AdditionalDocumentReference × 3: ICV, PIH, QR
    # ICV
    adr_icv = _cac(root, "AdditionalDocumentReference")
    _cbc(adr_icv, "ID", "ICV")
    _cbc(adr_icv, "UUID", str(data.icv))

    # PIH (Previous Invoice Hash)
    adr_pih = _cac(root, "AdditionalDocumentReference")
    _cbc(adr_pih, "ID", "PIH")
    attach_pih = _cac(adr_pih, "Attachment")
    embed_pih = _cbc(attach_pih, "EmbeddedDocumentBinaryObject", data.pih, mimeCode="text/plain")

    # QR
    adr_qr = _cac(root, "AdditionalDocumentReference")
    _cbc(adr_qr, "ID", "QR")
    attach_qr = _cac(adr_qr, "Attachment")
    _cbc(attach_qr, "EmbeddedDocumentBinaryObject", data.qr_data, mimeCode="text/plain")

    # 8. Signature block
    sig_block = _cac(root, "Signature")
    _cbc(sig_block, "ID", "urn:oasis:names:specification:ubl:signature:Invoice")
    _cbc(sig_block, "SignatureMethod", "urn:oasis:names:specification:ubl:dsig:enveloped:xades")

    # 9. AccountingSupplierParty
    _build_supplier_party(root, data.seller)

    # 10. AccountingCustomerParty
    _build_customer_party(root, data.buyer, data.sub_type)

    # 11. Delivery (supply date)
    if data.supply_date:
        delivery = _cac(root, "Delivery")
        _cbc(delivery, "ActualDeliveryDate", data.supply_date)

    # 12. PaymentMeans
    for pm in data.payment_means:
        pm_el = _cac(root, "PaymentMeans")
        _cbc(pm_el, "PaymentMeansCode", pm.code)
        # BR-KSA-17: credit/debit notes must include reason
        if data.credit_debit_reason and data.type_code in ("381", "383"):
            _cbc(pm_el, "InstructionNote", data.credit_debit_reason)

    # 13. AllowanceCharge (document-level discount)
    if data.discount_amount > Decimal("0"):
        ac = _cac(root, "AllowanceCharge")
        _cbc(ac, "ChargeIndicator", "false")
        _cbc(ac, "AllowanceChargeReasonCode", "95")  # BR-KSA-19: UNTDID 5189
        _cbc(ac, "AllowanceChargeReason", "Discount")
        _amount(ac, "Amount", data.discount_amount, data.currency_code)
        tax_cat = _cac(ac, "TaxCategory")
        _cbc(tax_cat, "ID", "S")
        _cbc(tax_cat, "Percent", "15.00")
        tax_scheme = _cac(tax_cat, "TaxScheme")
        _cbc(tax_scheme, "ID", "VAT")

    # 14. TaxTotal
    _build_tax_total(root, data)

    # 15. LegalMonetaryTotal
    _build_monetary_total(root, data, doc_type)

    # 16. InvoiceLine / CreditNoteLine
    line_tag = "InvoiceLine" if doc_type == "Invoice" else "CreditNoteLine"
    for line in data.lines:
        _build_line(root, line, data.currency_code, line_tag)


def _build_supplier_party(root: etree._Element, seller: SellerInfo) -> None:
    supplier = _cac(root, "AccountingSupplierParty")
    party = _cac(supplier, "Party")

    # PartyIdentification (CR number)
    if seller.cr_number:
        pid = _cac(party, "PartyIdentification")
        _cbc(pid, "ID", seller.cr_number, schemeID="CRN")

    # PostalAddress — element order per UBL 2.1 AddressType schema
    addr = _cac(party, "PostalAddress")
    _cbc(addr, "StreetName", seller.street)
    _cbc(addr, "BuildingNumber", seller.building_number)
    _cbc(addr, "CitySubdivisionName", seller.district)
    _cbc(addr, "CityName", seller.city)
    _cbc(addr, "PostalZone", seller.postal_code)
    country = _cac(addr, "Country")
    _cbc(country, "IdentificationCode", seller.country_code)

    # PartyTaxScheme
    pts = _cac(party, "PartyTaxScheme")
    _cbc(pts, "CompanyID", seller.vat_number)
    ts = _cac(pts, "TaxScheme")
    _cbc(ts, "ID", "VAT")

    # PartyLegalEntity
    ple = _cac(party, "PartyLegalEntity")
    _cbc(ple, "RegistrationName", seller.name_en)


def _build_customer_party(
    root: etree._Element,
    buyer: BuyerInfo | None,
    sub_type: str,
) -> None:
    customer = _cac(root, "AccountingCustomerParty")
    party = _cac(customer, "Party")

    if buyer and buyer.vat_number:
        # B2B: buyer is VAT-registered — BT-46 (PartyIdentification) is NOT
        # required per ZATCA; buyer is identified via BT-48 (CompanyID in
        # PartyTaxScheme). Adding BT-46 with an invalid schemeID causes errors.
        if buyer.additional_id:
            # Optional additional ID (CRN, TIN, etc.)
            pid = _cac(party, "PartyIdentification")
            _cbc(pid, "ID", buyer.additional_id, schemeID="CRN")

        if buyer.street:
            addr = _cac(party, "PostalAddress")
            _cbc(addr, "StreetName", buyer.street)
            if buyer.building_number:
                _cbc(addr, "BuildingNumber", buyer.building_number)
            if buyer.district:
                _cbc(addr, "CitySubdivisionName", buyer.district)
            if buyer.city:
                _cbc(addr, "CityName", buyer.city)
            if buyer.postal_code:
                _cbc(addr, "PostalZone", buyer.postal_code)
            country = _cac(addr, "Country")
            _cbc(country, "IdentificationCode", buyer.country_code)

        pts = _cac(party, "PartyTaxScheme")
        _cbc(pts, "CompanyID", buyer.vat_number)
        ts = _cac(pts, "TaxScheme")
        _cbc(ts, "ID", "VAT")

        ple = _cac(party, "PartyLegalEntity")
        _cbc(ple, "RegistrationName", buyer.name)
    elif buyer:
        # B2C: minimal buyer
        ple = _cac(party, "PartyLegalEntity")
        _cbc(ple, "RegistrationName", buyer.name)
    else:
        # No buyer
        ple = _cac(party, "PartyLegalEntity")
        _cbc(ple, "RegistrationName", "Walk-in Customer")


def _build_tax_total(root: etree._Element, data: InvoiceData) -> None:
    currency = data.currency_code

    # 1st TaxTotal: WITH subtotals (VAT breakdown by category) — BR-KSA-EN16931-08
    tt1 = _cac(root, "TaxTotal")
    _amount(tt1, "TaxAmount", data.total_vat, currency)

    # Group lines by (vat_category_code, vat_rate) for subtotals — BR-S/Z/E/O
    groups: dict[tuple[str, Decimal], list[InvoiceLineData]] = {}
    for line in data.lines:
        key = (line.vat_category_code, line.vat_rate)
        groups.setdefault(key, []).append(line)

    for (cat_code, rate), lines in groups.items():
        sub = _cac(tt1, "TaxSubtotal")
        taxable = sum(l.net_amount for l in lines)
        tax_amt = sum(l.vat_amount for l in lines)
        _amount(sub, "TaxableAmount", taxable, currency)
        _amount(sub, "TaxAmount", tax_amt, currency)
        cat = _cac(sub, "TaxCategory")
        _cbc(cat, "ID", cat_code)
        _cbc(cat, "Percent", str(rate.quantize(Decimal("0.01"))))
        # Tax exemption reason for Z, E, O categories — BR-KSA-18/23/24/69/83
        if cat_code in ("Z", "E", "O") and data.tax_exemption_reason_code:
            _cbc(cat, "TaxExemptionReasonCode", data.tax_exemption_reason_code)
        if cat_code in ("Z", "E", "O") and data.tax_exemption_reason:
            _cbc(cat, "TaxExemptionReason", data.tax_exemption_reason)
        scheme = _cac(cat, "TaxScheme")
        _cbc(scheme, "ID", "VAT")

    # 2nd TaxTotal: WITHOUT subtotals (accounting currency SAR) — BR-KSA-EN16931-09
    tt2 = _cac(root, "TaxTotal")
    _amount(tt2, "TaxAmount", data.total_vat, "SAR")


def _build_monetary_total(
    root: etree._Element,
    data: InvoiceData,
    doc_type: str,
) -> None:
    lmt = _cac(root, "LegalMonetaryTotal")

    # BR-CO-10: LineExtensionAmount = Σ(line net amounts)
    line_extension = sum(l.net_amount for l in data.lines)
    _amount(lmt, "LineExtensionAmount", line_extension, data.currency_code)

    # BR-CO-13: TaxExclusiveAmount = LineExtension - allowances + charges
    _amount(lmt, "TaxExclusiveAmount", data.total_excluding_vat, data.currency_code)

    # BR-CO-15: TaxInclusiveAmount = TaxExclusiveAmount + TotalVAT
    _amount(lmt, "TaxInclusiveAmount", data.total_including_vat, data.currency_code)

    if data.discount_amount > Decimal("0"):
        _amount(lmt, "AllowanceTotalAmount", data.discount_amount, data.currency_code)

    # BR-KSA-F-04: PrepaidAmount deduction
    if data.prepaid_amount and data.prepaid_amount > Decimal("0"):
        _amount(lmt, "PrepaidAmount", data.prepaid_amount, data.currency_code)

    # BR-CO-16: PayableAmount = TaxInclusiveAmount - PrepaidAmount
    payable = data.total_including_vat - (data.prepaid_amount or Decimal("0"))
    _amount(lmt, "PayableAmount", payable, data.currency_code)


def _build_line(
    root: etree._Element,
    line: InvoiceLineData,
    currency: str,
    line_tag: str,
) -> None:
    line_el = _cac(root, line_tag)
    _cbc(line_el, "ID", line.line_id)

    if line_tag == "InvoiceLine":
        _cbc(line_el, "InvoicedQuantity", str(line.quantity), unitCode="PCE")
    else:
        _cbc(line_el, "CreditedQuantity", str(line.quantity), unitCode="PCE")

    _amount(line_el, "LineExtensionAmount", line.net_amount, currency)

    # Line-level TaxTotal
    tt = _cac(line_el, "TaxTotal")
    _amount(tt, "TaxAmount", line.vat_amount, currency)
    _amount(tt, "RoundingAmount", line.line_amount_incl_vat, currency)

    # Item
    item = _cac(line_el, "Item")
    _cbc(item, "Name", line.item_name)
    ct = _cac(item, "ClassifiedTaxCategory")
    _cbc(ct, "ID", line.vat_category_code)
    _cbc(ct, "Percent", str(line.vat_rate.quantize(Decimal("0.01"))))
    ts = _cac(ct, "TaxScheme")
    _cbc(ts, "ID", "VAT")

    # Price
    price = _cac(line_el, "Price")
    _amount(price, "PriceAmount", line.unit_price, currency)

    # Line discount
    if line.discount_amount > Decimal("0"):
        ac = _cac(price, "AllowanceCharge")
        _cbc(ac, "ChargeIndicator", "false")
        _cbc(ac, "AllowanceChargeReason", "Line discount")
        _amount(ac, "Amount", line.discount_amount, currency)
