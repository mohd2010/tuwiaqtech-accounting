"""E-Invoice orchestrator: build XML → sign → hash → store → submit.

This is the main entry point called by POS and Returns services.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from lxml import etree
from sqlalchemy.orm import Session

from backend.app.models.customer import Customer
from backend.app.models.einvoice import (
    EInvoice,
    IcvCounter,
    InvoiceSubType,
    InvoiceTypeCode,
    ZatcaSubmissionStatus,
)
from backend.app.models.organization import Organization
from backend.app.services.zatca.api_client import ZatcaApiClient, ZatcaApiError
from backend.app.services.zatca.hashing import get_initial_pih, hash_invoice_xml
from backend.app.services.zatca.qr_code import generate_phase2_qr
from backend.app.services.zatca.signing import (
    extract_certificate_signature,
    extract_public_key_bytes,
    extract_signature_value,
    sign_invoice_xml,
)
from backend.app.services.zatca.validation import validate_invoice_data
from backend.app.services.zatca.xml_builder import (
    CAC,
    CBC,
    PAYMENT_MEANS_MAP,
    BuyerInfo,
    InvoiceData,
    InvoiceLineData,
    PaymentMeansData,
    SellerInfo,
    build_credit_note_xml,
    build_invoice_xml,
)

logger = logging.getLogger(__name__)

Q = Decimal("0.0001")
Q2 = Decimal("0.01")
VAT_RATE = Decimal("15")
VAT_DIVISOR = Decimal("115")


def _next_icv(db: Session) -> int:
    """Atomically increment and return the next ICV value."""
    counter = db.query(IcvCounter).filter(IcvCounter.id == 1).with_for_update().first()
    if not counter:
        counter = IcvCounter(id=1, current_value=0)
        db.add(counter)
        db.flush()
        counter = db.query(IcvCounter).filter(IcvCounter.id == 1).with_for_update().first()
    counter.current_value += 1  # type: ignore[operator]
    db.flush()
    return counter.current_value  # type: ignore[return-value]


def _get_previous_hash(db: Session) -> str:
    """Return the hash of the last EInvoice, or the initial PIH for the first invoice."""
    last = (
        db.query(EInvoice.invoice_hash)
        .order_by(EInvoice.icv.desc())
        .first()
    )
    if last:
        return last[0]
    return get_initial_pih()


def _get_organization(db: Session) -> Organization:
    """Fetch the singleton Organization record."""
    org = db.query(Organization).first()
    if not org:
        raise ValueError("Organization not configured. Set up organization settings first.")
    return org


def _build_seller_info(org: Organization) -> SellerInfo:
    return SellerInfo(
        name_en=org.name_en,
        name_ar=org.name_ar,
        vat_number=org.vat_number,
        street=org.street,
        building_number=org.building_number,
        city=org.city,
        district=org.district,
        postal_code=org.postal_code,
        country_code=org.country_code,
        cr_number=org.cr_number,
        additional_id=org.additional_id,
    )


def _build_buyer_info(customer: Customer | None) -> BuyerInfo | None:
    if not customer:
        return None
    return BuyerInfo(
        name=customer.name,
        vat_number=customer.vat_number,
        street=customer.street,
        building_number=customer.building_number,
        city=customer.city,
        district=customer.district,
        postal_code=customer.postal_code,
        country_code=customer.country_code or "SA",
        additional_id=customer.additional_id,
    )


def create_einvoice_for_sale(
    db: Session,
    *,
    journal_entry_id: uuid.UUID,
    invoice_number: str,
    customer: Customer | None,
    line_details: list[dict],
    payments: list[dict],
    total_net: Decimal,
    total_vat: Decimal,
    grand_total: Decimal,
    discount_amount: Decimal = Decimal("0"),
    now: datetime,
) -> EInvoice:
    """Create an e-invoice for a POS sale.

    1. Read Organization (raise ValueError if missing)
    2. Determine B2B vs B2C from customer.vat_number
    3. Get next ICV + previous PIH
    4. Build InvoiceData from sale details
    5. Validate via validation.validate_invoice_data()
    6. Build XML via xml_builder.build_invoice_xml()
    7. Sign XML if certificate configured
    8. Compute invoice hash
    9. Generate Phase 2 QR
    10. Store EInvoice record
    """
    org = _get_organization(db)
    seller = _build_seller_info(org)
    buyer = _build_buyer_info(customer)

    # B2B vs B2C
    is_b2b = buyer is not None and buyer.vat_number is not None
    sub_type = InvoiceSubType.STANDARD if is_b2b else InvoiceSubType.SIMPLIFIED

    icv = _next_icv(db)
    pih = _get_previous_hash(db)
    inv_uuid = str(uuid.uuid4())

    # Build line data
    lines: list[InvoiceLineData] = []
    for idx, ld in enumerate(line_details, start=1):
        product = ld["product"]
        qty = Decimal(str(ld["quantity"]))
        unit_price_incl = Decimal(str(ld["unit_price"]))
        line_total_incl = Decimal(str(ld["line_total"]))

        # Decompose VAT-inclusive prices
        line_vat = (line_total_incl * VAT_RATE / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)
        line_net = line_total_incl - line_vat
        unit_net = (unit_price_incl * Decimal("100") / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)

        lines.append(InvoiceLineData(
            line_id=str(idx),
            item_name=product.name,
            quantity=qty,
            unit_price=unit_net.quantize(Q2),
            net_amount=line_net.quantize(Q2),
            vat_amount=line_vat.quantize(Q2),
            line_amount_incl_vat=line_total_incl.quantize(Q2),
        ))

    # Build payment means
    payment_means = [
        PaymentMeansData(code=PAYMENT_MEANS_MAP.get(p["method"], "10"))
        for p in payments
    ]

    invoice_data = InvoiceData(
        invoice_id=invoice_number,
        uuid=inv_uuid,
        issue_date=now.strftime("%Y-%m-%d"),
        issue_time=now.strftime("%H:%M:%S"),
        type_code=InvoiceTypeCode.TAX_INVOICE.value,
        sub_type=sub_type.value,
        currency_code="SAR",
        seller=seller,
        buyer=buyer,
        lines=lines,
        payment_means=payment_means,
        total_excluding_vat=total_net.quantize(Q2),
        total_vat=total_vat.quantize(Q2),
        total_including_vat=grand_total.quantize(Q2),
        icv=icv,
        pih=pih,
        supply_date=now.strftime("%Y-%m-%d"),
        discount_amount=discount_amount.quantize(Q2),
    )

    # Validate
    errors = validate_invoice_data(invoice_data)
    if errors:
        raise ValueError(f"ZATCA validation errors: {'; '.join(errors)}")

    # Build XML
    xml_el = build_invoice_xml(invoice_data)

    # Sign if certificate configured
    has_cert = org.certificate_pem is not None and org.private_key_pem is not None
    if has_cert:
        xml_el = sign_invoice_xml(xml_el, org.private_key_pem, org.certificate_pem)  # type: ignore[arg-type]

    # Hash
    invoice_hash = hash_invoice_xml(xml_el)

    # QR Code — timestamp must match XML IssueDate + IssueTime (KSA-25)
    qr_timestamp = f"{now.strftime('%Y-%m-%d')}T{now.strftime('%H:%M:%S')}Z"
    if has_cert:
        sig_value = extract_signature_value(xml_el)
        pub_key = extract_public_key_bytes(org.certificate_pem)  # type: ignore[arg-type]
        cert_sig = extract_certificate_signature(org.certificate_pem)  # type: ignore[arg-type]
        qr_code = generate_phase2_qr(
            seller_name=org.name_en,
            vat_number=org.vat_number,
            timestamp=qr_timestamp,
            total_amount=str(grand_total.quantize(Q2)),
            vat_amount=str(total_vat.quantize(Q2)),
            invoice_hash=invoice_hash,
            ecdsa_signature=sig_value,
            public_key=pub_key,
            certificate_signature=cert_sig,
        )
    else:
        # Phase 2 QR without signing (sandbox/testing)
        qr_code = generate_phase2_qr(
            seller_name=org.name_en,
            vat_number=org.vat_number,
            timestamp=qr_timestamp,
            total_amount=str(grand_total.quantize(Q2)),
            vat_amount=str(total_vat.quantize(Q2)),
            invoice_hash=invoice_hash,
            ecdsa_signature="",
            public_key=b"",
            certificate_signature=b"",
        )

    # Update QR in XML
    invoice_data.qr_data = qr_code

    # Inject QR code into the XML AdditionalDocumentReference
    for adr in xml_el.findall(f"{{{CAC}}}AdditionalDocumentReference"):
        id_el = adr.find(f"{{{CBC}}}ID")
        if id_el is not None and id_el.text == "QR":
            attach = adr.find(f"{{{CAC}}}Attachment")
            if attach is not None:
                embed = attach.find(f"{{{CBC}}}EmbeddedDocumentBinaryObject")
                if embed is not None:
                    embed.text = qr_code

    xml_bytes = etree.tostring(xml_el, xml_declaration=True, encoding="UTF-8")

    # Store
    einvoice = EInvoice(
        journal_entry_id=journal_entry_id,
        invoice_uuid=inv_uuid,
        invoice_number=invoice_number,
        icv=icv,
        type_code=InvoiceTypeCode.TAX_INVOICE,
        sub_type=sub_type,
        invoice_hash=invoice_hash,
        previous_invoice_hash=pih,
        xml_content=xml_bytes,
        qr_code=qr_code,
        total_excluding_vat=total_net,
        total_vat=total_vat,
        total_including_vat=grand_total,
        buyer_name=buyer.name if buyer else None,
        buyer_vat_number=buyer.vat_number if buyer else None,
        submission_status=ZatcaSubmissionStatus.PENDING,
        issue_date=now,
        supply_date=now,
    )
    db.add(einvoice)
    db.flush()
    return einvoice


def create_einvoice_for_credit_note(
    db: Session,
    *,
    journal_entry_id: uuid.UUID,
    credit_note_number: str,
    original_invoice_number: str,
    customer: Customer | None,
    line_details: list[dict],
    total_net: Decimal,
    total_vat: Decimal,
    gross_total: Decimal,
    now: datetime,
    credit_note_id: uuid.UUID | None = None,
    reason: str = "",
) -> EInvoice:
    """Create an e-invoice (credit note) for a return."""
    org = _get_organization(db)
    seller = _build_seller_info(org)
    buyer = _build_buyer_info(customer)

    is_b2b = buyer is not None and buyer.vat_number is not None
    sub_type = InvoiceSubType.STANDARD if is_b2b else InvoiceSubType.SIMPLIFIED

    icv = _next_icv(db)
    pih = _get_previous_hash(db)
    inv_uuid = str(uuid.uuid4())

    lines: list[InvoiceLineData] = []
    for idx, ld in enumerate(line_details, start=1):
        product = ld["product"]
        qty = Decimal(str(ld["quantity"]))
        line_refund = Decimal(str(ld["line_refund"]))
        unit_price = Decimal(str(ld["unit_price"]))

        line_vat = (line_refund * VAT_RATE / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)
        line_net = line_refund - line_vat
        unit_net = (unit_price * Decimal("100") / VAT_DIVISOR).quantize(Q, rounding=ROUND_HALF_UP)

        lines.append(InvoiceLineData(
            line_id=str(idx),
            item_name=product.name,
            quantity=qty,
            unit_price=unit_net.quantize(Q2),
            net_amount=line_net.quantize(Q2),
            vat_amount=line_vat.quantize(Q2),
            line_amount_incl_vat=line_refund.quantize(Q2),
        ))

    invoice_data = InvoiceData(
        invoice_id=credit_note_number,
        uuid=inv_uuid,
        issue_date=now.strftime("%Y-%m-%d"),
        issue_time=now.strftime("%H:%M:%S"),
        type_code=InvoiceTypeCode.CREDIT_NOTE.value,
        sub_type=sub_type.value,
        currency_code="SAR",
        seller=seller,
        buyer=buyer,
        lines=lines,
        payment_means=[PaymentMeansData(code="10")],
        total_excluding_vat=total_net.quantize(Q2),
        total_vat=total_vat.quantize(Q2),
        total_including_vat=gross_total.quantize(Q2),
        icv=icv,
        pih=pih,
        billing_reference_id=original_invoice_number,
        supply_date=now.strftime("%Y-%m-%d"),
        credit_debit_reason=reason or None,
    )

    errors = validate_invoice_data(invoice_data)
    if errors:
        raise ValueError(f"ZATCA validation errors: {'; '.join(errors)}")

    xml_el = build_credit_note_xml(invoice_data)

    has_cert = org.certificate_pem is not None and org.private_key_pem is not None
    if has_cert:
        xml_el = sign_invoice_xml(xml_el, org.private_key_pem, org.certificate_pem)  # type: ignore[arg-type]

    invoice_hash = hash_invoice_xml(xml_el)

    qr_timestamp = f"{now.strftime('%Y-%m-%d')}T{now.strftime('%H:%M:%S')}Z"
    if has_cert:
        sig_value = extract_signature_value(xml_el)
        pub_key = extract_public_key_bytes(org.certificate_pem)  # type: ignore[arg-type]
        cert_sig = extract_certificate_signature(org.certificate_pem)  # type: ignore[arg-type]
        qr_code = generate_phase2_qr(
            seller_name=org.name_en,
            vat_number=org.vat_number,
            timestamp=qr_timestamp,
            total_amount=str(gross_total.quantize(Q2)),
            vat_amount=str(total_vat.quantize(Q2)),
            invoice_hash=invoice_hash,
            ecdsa_signature=sig_value,
            public_key=pub_key,
            certificate_signature=cert_sig,
        )
    else:
        qr_code = generate_phase2_qr(
            seller_name=org.name_en,
            vat_number=org.vat_number,
            timestamp=qr_timestamp,
            total_amount=str(gross_total.quantize(Q2)),
            vat_amount=str(total_vat.quantize(Q2)),
            invoice_hash=invoice_hash,
            ecdsa_signature="",
            public_key=b"",
            certificate_signature=b"",
        )

    xml_bytes = etree.tostring(xml_el, xml_declaration=True, encoding="UTF-8")

    einvoice = EInvoice(
        journal_entry_id=journal_entry_id,
        credit_note_id=credit_note_id,
        invoice_uuid=inv_uuid,
        invoice_number=credit_note_number,
        icv=icv,
        type_code=InvoiceTypeCode.CREDIT_NOTE,
        sub_type=sub_type,
        invoice_hash=invoice_hash,
        previous_invoice_hash=pih,
        xml_content=xml_bytes,
        qr_code=qr_code,
        total_excluding_vat=total_net,
        total_vat=total_vat,
        total_including_vat=gross_total,
        buyer_name=buyer.name if buyer else None,
        buyer_vat_number=buyer.vat_number if buyer else None,
        submission_status=ZatcaSubmissionStatus.PENDING,
        issue_date=now,
        supply_date=now,
    )
    db.add(einvoice)
    db.flush()
    return einvoice


def submit_einvoice_to_zatca(db: Session, einvoice: EInvoice) -> EInvoice:
    """Submit an e-invoice to the ZATCA reporting/clearance API.

    - B2C (SIMPLIFIED): calls reporting endpoint
    - B2B (STANDARD): calls clearance endpoint

    Updates the EInvoice record with the ZATCA response (status, request ID,
    warnings/errors). If ZATCA returns a re-signed clearedInvoice (B2B), the
    xml_content is updated with it.

    On network or API errors the invoice is marked REJECTED with error details
    so it can be retried later.
    """
    org = _get_organization(db)
    if not org.csid or not org.certificate_serial:
        logger.warning("ZATCA credentials not configured — skipping submission for %s", einvoice.invoice_number)
        return einvoice

    client = ZatcaApiClient(org)
    xml_b64 = base64.b64encode(einvoice.xml_content).decode("ascii")

    try:
        if einvoice.sub_type == InvoiceSubType.SIMPLIFIED:
            result = asyncio.run(
                client.report_simplified_invoice(
                    einvoice.invoice_hash, einvoice.invoice_uuid, xml_b64
                )
            )
        else:
            result = asyncio.run(
                client.clear_standard_invoice(
                    einvoice.invoice_hash, einvoice.invoice_uuid, xml_b64
                )
            )
    except (ZatcaApiError, Exception) as exc:
        logger.error("ZATCA submission failed for %s: %s", einvoice.invoice_number, exc)
        einvoice.submission_status = ZatcaSubmissionStatus.REJECTED
        einvoice.zatca_errors = {"error": str(exc)}
        einvoice.submitted_at = datetime.now(timezone.utc)
        db.flush()
        return einvoice

    # Parse ZATCA response
    reporting_status = result.get("reportingStatus")
    clearance_status = result.get("clearanceStatus")
    validation_results = result.get("validationResults", {})
    request_id = str(result.get("requestID", "")) if result.get("requestID") is not None else None

    einvoice.zatca_request_id = request_id
    einvoice.zatca_reporting_status = reporting_status
    einvoice.zatca_clearance_status = clearance_status
    einvoice.submitted_at = datetime.now(timezone.utc)

    # Store warnings and errors from validationResults
    warnings_list = validation_results.get("warningMessages", [])
    errors_list = validation_results.get("errorMessages", [])
    if warnings_list:
        einvoice.zatca_warnings = {"warnings": warnings_list}
    if errors_list:
        einvoice.zatca_errors = {"errors": errors_list}

    # Determine submission status from response
    if clearance_status == "CLEARED":
        einvoice.submission_status = ZatcaSubmissionStatus.CLEARED
        # B2B clearance: ZATCA may return a re-signed invoice
        cleared_invoice_b64 = result.get("clearedInvoice")
        if cleared_invoice_b64:
            einvoice.xml_content = base64.b64decode(cleared_invoice_b64)
    elif reporting_status == "REPORTED":
        einvoice.submission_status = ZatcaSubmissionStatus.REPORTED
    elif reporting_status == "NOT_REPORTED" or clearance_status == "NOT_CLEARED":
        einvoice.submission_status = ZatcaSubmissionStatus.REJECTED
    elif warnings_list and not errors_list:
        einvoice.submission_status = ZatcaSubmissionStatus.WARNING
    else:
        # Any other unexpected status — mark as rejected for safety
        einvoice.submission_status = ZatcaSubmissionStatus.REJECTED

    db.flush()
    logger.info(
        "ZATCA submission for %s: status=%s, request_id=%s",
        einvoice.invoice_number,
        einvoice.submission_status.value,
        request_id,
    )
    return einvoice
