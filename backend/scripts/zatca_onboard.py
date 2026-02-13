"""ZATCA Sandbox Onboarding — Interactive Script.

Walks through the full ZATCA onboarding flow against the Developer Portal
(sandbox) environment:

    Phase A — Setup Organization (sandbox test data)
    Phase B — CSR + Compliance CSID
    Phase C — Generate 6 Test Invoices (388/381/383 x B2B/B2C)
    Phase D — Submit Compliance Checks
    Phase E — Production CSID

Usage:
    python -m backend.scripts.zatca_onboard
"""

from __future__ import annotations

import asyncio
import base64
import sys
import uuid as uuid_mod
from datetime import datetime, timezone
from decimal import Decimal

from lxml import etree
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.models.einvoice import (
    EInvoice,
    IcvCounter,
    InvoiceSubType,
    InvoiceTypeCode,
    ZatcaSubmissionStatus,
)
from backend.app.models.organization import Organization
from backend.app.services.zatca.api_client import ZatcaApiClient
from backend.app.services.zatca.hashing import get_initial_pih, hash_invoice_xml
from backend.app.services.zatca.qr_code import generate_phase2_qr
from backend.app.services.zatca.signing import (
    extract_certificate_signature,
    extract_public_key_bytes,
    extract_signature_value,
    generate_csr,
    sign_invoice_xml,
)
from backend.app.services.zatca.xml_builder import (
    CAC,
    CBC,
    BuyerInfo,
    InvoiceData,
    InvoiceLineData,
    PaymentMeansData,
    SellerInfo,
    build_credit_note_xml,
    build_invoice_xml,
)

# ─── Constants ────────────────────────────────────────────────────────────────

SANDBOX_VAT = "399999999999993"
BUYER_VAT = "300000000000003"
Q2 = Decimal("0.01")


def _banner(title: str) -> None:
    width = 60
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def _step(msg: str) -> None:
    print(f"  -> {msg}")


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


# ─── Helpers (mirror einvoice_service.py) ─────────────────────────────────────


def _next_icv(db: Session) -> int:
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
    last = db.query(EInvoice.invoice_hash).order_by(EInvoice.icv.desc()).first()
    if last:
        return last[0]
    return get_initial_pih()


def _build_seller(org: Organization) -> SellerInfo:
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
    )


# ─── Phase A: Setup Organization ─────────────────────────────────────────────


def phase_a(db: Session) -> Organization:
    _banner("Phase A: Setup Organization")

    org = db.query(Organization).first()
    if org:
        _step("Organization already exists, updating to sandbox test data...")
    else:
        _step("Creating organization with sandbox test data...")
        org = Organization()
        db.add(org)

    org.name_en = "Tuwaiq Outdoor"
    org.name_ar = "\u062a\u0648\u0627\u0642 \u0644\u0644\u0623\u0646\u0634\u0637\u0629 \u0627\u0644\u062e\u0627\u0631\u062c\u064a\u0629"
    org.vat_number = SANDBOX_VAT
    org.cr_number = "1010123456"
    org.street = "King Fahd Road"
    org.building_number = "1234"
    org.city = "Riyadh"
    org.district = "Al Olaya"
    org.postal_code = "12345"
    org.country_code = "SA"
    org.is_production = False
    org.zatca_api_base_url = None  # uses sandbox default

    db.flush()

    # Seed ICV counter
    counter = db.query(IcvCounter).filter(IcvCounter.id == 1).first()
    if not counter:
        db.add(IcvCounter(id=1, current_value=0))
        db.flush()
        _step("Created ICV counter (starting at 0)")
    else:
        _step(f"ICV counter exists (current: {counter.current_value})")

    db.commit()
    _ok(f"Organization: {org.name_en} | VAT: {org.vat_number}")
    return org


# ─── Phase B: CSR + Compliance CSID ──────────────────────────────────────────


def phase_b(db: Session, org: Organization) -> tuple[Organization, str]:
    _banner("Phase B: CSR + Compliance CSID")

    egs_serial = str(uuid_mod.uuid4())
    _step(f"EGS serial number: {egs_serial}")

    _step("Generating ECDSA keypair + CSR...")
    private_key_pem, csr_pem = generate_csr(
        common_name="Tuwaiq Outdoor EGS",
        org=org.name_en,
        country="SA",
        serial_number=org.vat_number,
        org_unit="IT",
        environment="sandbox",
        egs_serial=egs_serial,
        solution_name="TuwaiqPOS",
        version="1.0",
        invoice_type_flag="1100",
        registered_address="Riyadh",
        business_category="Outdoor Activities",
    )

    org.private_key_pem = private_key_pem
    db.flush()
    db.commit()
    _ok("Private key stored on organization")

    print()
    print("  --- CSR PEM ---")
    print(csr_pem.decode("utf-8"))
    print("  --- End CSR ---")
    print()
    print("  Instructions:")
    print("  1. Go to https://fatoora.zatca.gov.sa/ (Developer Portal)")
    print("  2. Onboarding & Management > Onboard New Solution Unit")
    print("  3. Paste the CSR above")
    print("  4. Copy the OTP that appears (for Developer Portal, use 123345)")
    print()

    otp = input("  Enter OTP (default: 123345): ").strip()
    if not otp:
        otp = "123345"

    _step(f"Requesting compliance CSID with OTP={otp}...")

    csr_b64 = base64.b64encode(csr_pem).decode("ascii")
    client = ZatcaApiClient(org)

    result = asyncio.run(client.request_compliance_csid(csr_b64, otp))

    # Check for errors
    if "errors" in result and result["errors"]:
        _fail(f"ZATCA returned errors: {result['errors']}")
        if "validationResults" in result:
            vr = result["validationResults"]
            for err in vr.get("errorMessages", []):
                print(f"    ERROR: {err.get('message', err)}")
        sys.exit(1)

    bst = result.get("binarySecurityToken", "")
    secret = result.get("secret", "")
    request_id = result.get("requestID", "")

    if not bst:
        _fail(f"No binarySecurityToken in response: {result}")
        sys.exit(1)

    # Decode the BST — ZATCA returns base64(certificate-base64), so one
    # decode gives us the PEM-style base64 of the certificate.
    cert_b64_bytes = base64.b64decode(bst)  # intermediate base64 of cert
    cert_der = base64.b64decode(cert_b64_bytes)  # raw DER
    # Wrap in PEM
    cert_pem = (
        b"-----BEGIN CERTIFICATE-----\n"
        + base64.encodebytes(cert_der)
        + b"-----END CERTIFICATE-----\n"
    )

    org.csid = bst
    org.certificate_serial = secret  # ZATCA "secret" for Basic Auth
    org.certificate_pem = cert_pem
    db.flush()
    db.commit()

    _ok(f"Compliance CSID received (request_id: {request_id})")
    _ok(f"Secret stored | Certificate stored ({len(cert_der)} bytes DER)")

    return org, request_id


# ─── Phase C: Generate 6 Test Invoices ───────────────────────────────────────


def _build_test_invoice(
    db: Session,
    org: Organization,
    *,
    type_code: str,
    sub_type: str,
    billing_ref: str | None,
    reason: str | None,
    seq: int,
    buyer: BuyerInfo | None,
) -> EInvoice:
    """Build, sign, hash, and store a single test invoice."""
    seller = _build_seller(org)
    icv = _next_icv(db)
    pih = _get_previous_hash(db)
    inv_uuid = str(uuid_mod.uuid4())
    now = datetime.now(timezone.utc)
    invoice_number = f"ONBOARD-{seq:03d}"

    net = Decimal("100.00")
    vat = Decimal("15.00")
    total = Decimal("115.00")

    line = InvoiceLineData(
        line_id="1",
        item_name="Test Item",
        quantity=Decimal("1"),
        unit_price=net,
        net_amount=net,
        vat_amount=vat,
        vat_category_code="S",
        vat_rate=Decimal("15.00"),
        line_amount_incl_vat=total,
    )

    data = InvoiceData(
        invoice_id=invoice_number,
        uuid=inv_uuid,
        issue_date=now.strftime("%Y-%m-%d"),
        issue_time=now.strftime("%H:%M:%S"),
        type_code=type_code,
        sub_type=sub_type,
        currency_code="SAR",
        seller=seller,
        buyer=buyer,
        lines=[line],
        payment_means=[PaymentMeansData(code="10")],
        total_excluding_vat=net,
        total_vat=vat,
        total_including_vat=total,
        icv=icv,
        pih=pih,
        supply_date=now.strftime("%Y-%m-%d"),
        billing_reference_id=billing_ref,
        credit_debit_reason=reason,
    )

    # Build XML
    is_credit = type_code == "381"
    xml_el = build_credit_note_xml(data) if is_credit else build_invoice_xml(data)

    # Sign
    xml_el = sign_invoice_xml(xml_el, org.private_key_pem, org.certificate_pem)  # type: ignore[arg-type]

    # Hash
    invoice_hash = hash_invoice_xml(xml_el)

    # QR
    sig_value = extract_signature_value(xml_el)
    pub_key = extract_public_key_bytes(org.certificate_pem)  # type: ignore[arg-type]
    cert_sig = extract_certificate_signature(org.certificate_pem)  # type: ignore[arg-type]
    qr_code = generate_phase2_qr(
        seller_name=org.name_en,
        vat_number=org.vat_number,
        timestamp=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        total_amount=str(total),
        vat_amount=str(vat),
        invoice_hash=invoice_hash,
        ecdsa_signature=sig_value,
        public_key=pub_key,
        certificate_signature=cert_sig,
    )

    # Inject QR into XML
    for adr in xml_el.findall(f"{{{CAC}}}AdditionalDocumentReference"):
        id_el = adr.find(f"{{{CBC}}}ID")
        if id_el is not None and id_el.text == "QR":
            attach = adr.find(f"{{{CAC}}}Attachment")
            if attach is not None:
                embed = attach.find(f"{{{CBC}}}EmbeddedDocumentBinaryObject")
                if embed is not None:
                    embed.text = qr_code

    xml_bytes = etree.tostring(xml_el, xml_declaration=True, encoding="UTF-8")

    # Determine enum values
    tc_enum = InvoiceTypeCode(type_code)
    st_enum = InvoiceSubType(sub_type)

    einvoice = EInvoice(
        journal_entry_id=_get_or_create_dummy_je_id(db),
        invoice_uuid=inv_uuid,
        invoice_number=invoice_number,
        icv=icv,
        type_code=tc_enum,
        sub_type=st_enum,
        invoice_hash=invoice_hash,
        previous_invoice_hash=pih,
        xml_content=xml_bytes,
        qr_code=qr_code,
        total_excluding_vat=net,
        total_vat=vat,
        total_including_vat=total,
        buyer_name=buyer.name if buyer else None,
        buyer_vat_number=buyer.vat_number if buyer else None,
        submission_status=ZatcaSubmissionStatus.PENDING,
        issue_date=now,
        supply_date=now,
    )
    db.add(einvoice)
    db.flush()
    return einvoice


def _get_or_create_dummy_je_id(db: Session) -> uuid_mod.UUID:
    """Get or create a dummy journal entry for onboarding test invoices.

    The EInvoice model requires a journal_entry_id FK. For onboarding
    test invoices we create a minimal journal entry if none exists.
    """
    from backend.app.models.accounting import JournalEntry, User

    je = db.query(JournalEntry).filter(
        JournalEntry.description.like("ZATCA_ONBOARD_%")
    ).first()
    if je:
        return je.id

    # Need a user for created_by — grab the first admin
    user = db.query(User).first()
    if not user:
        raise RuntimeError(
            "No users in database. Run 'python -m backend.scripts.seed' first."
        )

    je = JournalEntry(
        description="ZATCA_ONBOARD_DUMMY",
        entry_date=datetime.now(timezone.utc),
        created_by=user.id,
    )
    db.add(je)
    db.flush()
    return je.id


def phase_c(db: Session, org: Organization) -> list[EInvoice]:
    _banner("Phase C: Generate 6 Test Invoices")

    b2b_buyer = BuyerInfo(
        name="Test Buyer",
        vat_number=BUYER_VAT,
        street="Test Street",
        building_number="5678",
        city="Riyadh",
        district="Al Malaz",
        postal_code="11111",
        country_code="SA",
    )

    # Invoice specs: (type_code, sub_type, is_credit_note, billing_ref_seq, reason, buyer, label)
    specs: list[tuple[str, str, str | None, str | None, BuyerInfo | None, str]] = [
        ("388", "0100000", None, None, b2b_buyer, "B2B Tax Invoice"),
        ("388", "0200000", None, None, None, "B2C Simplified Invoice"),
        ("381", "0100000", None, "Correction", b2b_buyer, "B2B Credit Note"),
        ("381", "0200000", None, "Correction", None, "B2C Credit Note"),
        ("383", "0100000", None, "Adjustment", b2b_buyer, "B2B Debit Note"),
        ("383", "0200000", None, "Adjustment", None, "B2C Debit Note"),
    ]

    invoices: list[EInvoice] = []
    for seq, (type_code, sub_type, _, reason, buyer, label) in enumerate(specs, start=1):
        # Credit/debit notes reference the corresponding base invoice
        billing_ref: str | None = None
        if type_code in ("381", "383"):
            # B2B notes ref invoice #1, B2C notes ref invoice #2
            ref_idx = 0 if sub_type == "0100000" else 1
            if ref_idx < len(invoices):
                billing_ref = invoices[ref_idx].invoice_number

        _step(f"#{seq} {label} (type={type_code}, sub={sub_type})...")
        einv = _build_test_invoice(
            db, org,
            type_code=type_code,
            sub_type=sub_type,
            billing_ref=billing_ref,
            reason=reason,
            seq=seq,
            buyer=buyer,
        )
        invoices.append(einv)
        _ok(f"  ICV={einv.icv} UUID={einv.invoice_uuid[:8]}... hash={einv.invoice_hash[:16]}...")

    db.commit()
    _ok(f"Generated {len(invoices)} test invoices")
    return invoices


# ─── Phase D: Submit Compliance Checks ────────────────────────────────────────


def phase_d(db: Session, org: Organization, invoices: list[EInvoice]) -> int:
    _banner("Phase D: Submit Compliance Checks")

    client = ZatcaApiClient(org)
    pass_count = 0

    for idx, einv in enumerate(invoices, start=1):
        _step(f"#{idx} Checking {einv.invoice_number} (type={einv.type_code.value}, sub={einv.sub_type.value})...")
        xml_b64 = base64.b64encode(einv.xml_content).decode("ascii")

        try:
            result = asyncio.run(
                client.check_compliance_invoice(einv.invoice_hash, einv.invoice_uuid, xml_b64)
            )
        except Exception as e:
            _fail(f"  API error: {e}")
            continue

        # Parse result
        reporting = result.get("reportingStatus", "")
        clearance = result.get("clearanceStatus", "")
        validation = result.get("validationResults", {})
        status_str = reporting or clearance or "UNKNOWN"

        info_msgs = validation.get("infoMessages", [])
        warn_msgs = validation.get("warningMessages", [])
        err_msgs = validation.get("errorMessages", [])

        is_pass = (
            status_str in ("REPORTED", "CLEARED", "PASS")
            or (not err_msgs and status_str not in ("REJECTED", "ERROR"))
        )

        if is_pass:
            pass_count += 1
            _ok(f"  {status_str}")
        else:
            _fail(f"  {status_str}")

        # Print details
        for msg in err_msgs:
            msg_text = msg.get("message", msg) if isinstance(msg, dict) else msg
            print(f"    ERROR: {msg_text}")
        for msg in warn_msgs:
            msg_text = msg.get("message", msg) if isinstance(msg, dict) else msg
            print(f"    WARN:  {msg_text}")
        for msg in info_msgs:
            msg_text = msg.get("message", msg) if isinstance(msg, dict) else msg
            print(f"    INFO:  {msg_text}")

    print()
    _ok(f"Results: {pass_count}/{len(invoices)} passed")
    return pass_count


# ─── Phase E: Production CSID ────────────────────────────────────────────────


def phase_e(db: Session, org: Organization, compliance_request_id: str) -> None:
    _banner("Phase E: Production CSID")

    _step("Requesting production CSID...")
    client = ZatcaApiClient(org)

    try:
        result = asyncio.run(client.request_production_csid(compliance_request_id))
    except Exception as e:
        _fail(f"API error: {e}")
        sys.exit(1)

    bst = result.get("binarySecurityToken", "")
    secret = result.get("secret", "")
    request_id = result.get("requestID", "")

    if not bst:
        _fail(f"No binarySecurityToken in response: {result}")
        # Print errors if present
        if "validationResults" in result:
            vr = result["validationResults"]
            for err in vr.get("errorMessages", []):
                msg_text = err.get("message", err) if isinstance(err, dict) else err
                print(f"    ERROR: {msg_text}")
        sys.exit(1)

    cert_b64_bytes = base64.b64decode(bst)
    cert_der = base64.b64decode(cert_b64_bytes)
    cert_pem = (
        b"-----BEGIN CERTIFICATE-----\n"
        + base64.encodebytes(cert_der)
        + b"-----END CERTIFICATE-----\n"
    )

    org.csid = bst
    org.certificate_serial = secret  # ZATCA "secret" for Basic Auth
    org.certificate_pem = cert_pem
    org.is_production = True
    db.flush()
    db.commit()

    _ok(f"Production CSID received (request_id: {request_id})")
    _ok("Organization is now in PRODUCTION mode")
    print()
    print("  ZATCA integration is fully active. All future invoices")
    print("  will be submitted for clearance/reporting automatically.")


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print()
    print("  ZATCA Sandbox Onboarding Script")
    print("  ================================")
    print("  Target: Developer Portal (sandbox)")
    print("  Test VAT: " + SANDBOX_VAT)
    print()

    db = SessionLocal()
    try:
        # Phase A
        org = phase_a(db)

        # Phase B
        org, compliance_request_id = phase_b(db, org)

        # Phase C
        invoices = phase_c(db, org)

        # Phase D
        pass_count = phase_d(db, org, invoices)

        # Phase E
        if pass_count == len(invoices):
            phase_e(db, org, compliance_request_id)
        else:
            print()
            _fail(
                f"Only {pass_count}/{len(invoices)} invoices passed compliance. "
                f"Fix errors above before requesting production CSID."
            )
            print("  You can re-run this script after fixing issues.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n  Aborted by user.")
        sys.exit(130)
    finally:
        db.close()


if __name__ == "__main__":
    main()
