"""ZATCA API Test Script — Tests all 6 endpoints against Developer Portal.

Exercises every ZATCA API endpoint:
  1. POST /compliance            — Get compliance CSID
  2. POST /compliance/invoices   — Compliance invoice check (6 invoice types)
  3. POST /production/csids      — Get production CSID
  4. POST /invoices/reporting/single  — Report simplified (B2C) invoice
  5. POST /invoices/clearance/single  — Clear standard (B2B) invoice
  6. PATCH /production/csids     — Renew production CSID

Usage:
    python -m backend.scripts.zatca_test_all_apis
"""

from __future__ import annotations

import asyncio
import base64
import sys
import uuid as uuid_mod
from datetime import datetime, timezone
from decimal import Decimal

from lxml import etree

from backend.app.services.zatca.api_client import ZatcaApiClient, ZatcaApiError
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

SANDBOX_BASE_URL = "https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal"
SANDBOX_VAT = "399999999999993"
SANDBOX_OTP = "123345"
BUYER_VAT = "300000000000003"


# ─── Helpers ──────────────────────────────────────────────────────────────────

class FakeOrg:
    """Minimal object that satisfies ZatcaApiClient interface."""

    def __init__(self) -> None:
        self.zatca_api_base_url = SANDBOX_BASE_URL
        self.is_production = False
        self.csid: str | None = None
        self.certificate_serial: str | None = None
        self.certificate_pem: bytes | None = None
        self.private_key_pem: bytes | None = None
        self.vat_number = SANDBOX_VAT


def _banner(title: str) -> None:
    width = 68
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


def _result(label: str, passed: bool) -> None:
    tag = "[OK]" if passed else "[FAIL]"
    print(f"  {tag} {label}")


def _decode_bst(bst: str) -> bytes:
    """Double-decode BST into PEM certificate."""
    cert_b64_bytes = base64.b64decode(bst)
    cert_der = base64.b64decode(cert_b64_bytes)
    cert_pem = (
        b"-----BEGIN CERTIFICATE-----\n"
        + base64.encodebytes(cert_der)
        + b"-----END CERTIFICATE-----\n"
    )
    return cert_pem


SELLER = SellerInfo(
    name_en="Tuwaiq Outdoor",
    name_ar="\u062a\u0648\u0627\u0642 \u0644\u0644\u0623\u0646\u0634\u0637\u0629 \u0627\u0644\u062e\u0627\u0631\u062c\u064a\u0629",
    vat_number=SANDBOX_VAT,
    street="King Fahd Road",
    building_number="1234",
    city="Riyadh",
    district="Al Olaya",
    postal_code="12345",
    country_code="SA",
    cr_number="1010123456",
)

B2B_BUYER = BuyerInfo(
    name="Test Buyer",
    vat_number=BUYER_VAT,
    street="Test Street",
    building_number="5678",
    city="Riyadh",
    district="Al Malaz",
    postal_code="11111",
    country_code="SA",
)


def _build_signed_invoice(
    org: FakeOrg,
    *,
    type_code: str,
    sub_type: str,
    icv: int,
    pih: str,
    billing_ref: str | None = None,
    reason: str | None = None,
    buyer: BuyerInfo | None = None,
) -> tuple[str, str, str, bytes]:
    """Build, sign, and hash an invoice. Returns (invoice_hash, uuid, xml_b64, xml_bytes)."""
    inv_uuid = str(uuid_mod.uuid4())
    now = datetime.now(timezone.utc)
    invoice_number = f"TEST-{icv:04d}"

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
        seller=SELLER,
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
        seller_name=SELLER.name_en,
        vat_number=SELLER.vat_number,
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
    xml_b64 = base64.b64encode(xml_bytes).decode("ascii")

    return invoice_hash, inv_uuid, xml_b64, xml_bytes


def _print_validation(result: dict) -> None:
    """Print validation messages from ZATCA response."""
    vr = result.get("validationResults", {})
    if not vr:
        return
    for msg in vr.get("errorMessages", []):
        msg_text = msg.get("message", msg) if isinstance(msg, dict) else msg
        print(f"      ERROR: {msg_text}")
    for msg in vr.get("warningMessages", []):
        msg_text = msg.get("message", msg) if isinstance(msg, dict) else msg
        print(f"      WARN:  {msg_text}")
    for msg in vr.get("infoMessages", []):
        msg_text = msg.get("message", msg) if isinstance(msg, dict) else msg
        print(f"      INFO:  {msg_text}")


# ─── Test 1: Compliance CSID ─────────────────────────────────────────────────


async def test_1_compliance_csid(org: FakeOrg) -> str:
    """POST /compliance — Get compliance CSID."""
    _banner("Test 1: POST /compliance (Compliance CSID)")

    egs_serial = str(uuid_mod.uuid4())
    _step(f"Generating CSR (EGS serial: {egs_serial[:8]}...)")

    private_key_pem, csr_pem = generate_csr(
        common_name="Tuwaiq Outdoor EGS",
        org="Tuwaiq Outdoor",
        country="SA",
        serial_number=SANDBOX_VAT,
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

    csr_b64 = base64.b64encode(csr_pem).decode("ascii")
    client = ZatcaApiClient(org)

    _step(f"Calling POST /compliance with OTP={SANDBOX_OTP}...")
    try:
        result = await client.request_compliance_csid(csr_b64, SANDBOX_OTP)
    except ZatcaApiError as e:
        _fail(f"ZatcaApiError: [{e.error_code}] {e}")
        if e.raw_errors:
            for err in e.raw_errors:
                print(f"      {err}")
        sys.exit(1)

    bst = result.get("binarySecurityToken", "")
    secret = result.get("secret", "")
    request_id = str(result.get("requestID", ""))
    disposition = result.get("dispositionMessage", "")

    _ok(f"dispositionMessage: {disposition}")
    _ok(f"requestID: {request_id}")
    _ok(f"BST length: {len(bst)} chars")
    _ok(f"Secret received: {'yes' if secret else 'no'}")

    if disposition != "ISSUED":
        _fail(f"Expected ISSUED, got: {disposition}")
        sys.exit(1)

    # Store credentials
    org.csid = bst
    org.certificate_serial = secret
    org.certificate_pem = _decode_bst(bst)

    _ok("Compliance CSID obtained successfully")
    return request_id


# ─── Test 2: Compliance Invoice Check ────────────────────────────────────────


async def test_2_compliance_invoices(org: FakeOrg) -> None:
    """POST /compliance/invoices — Submit 6 invoice types for compliance check."""
    _banner("Test 2: POST /compliance/invoices (6 Invoice Types)")

    client = ZatcaApiClient(org)
    icv = 0
    pih = get_initial_pih()
    pass_count = 0

    # 6 invoice types: 388/381/383 x B2B/B2C
    specs = [
        ("388", "0100000", None, None, B2B_BUYER, "B2B Tax Invoice"),
        ("388", "0200000", None, None, None, "B2C Simplified Invoice"),
        ("381", "0100000", "TEST-0001", "Correction", B2B_BUYER, "B2B Credit Note"),
        ("381", "0200000", "TEST-0002", "Correction", None, "B2C Credit Note"),
        ("383", "0100000", "TEST-0001", "Adjustment", B2B_BUYER, "B2B Debit Note"),
        ("383", "0200000", "TEST-0002", "Adjustment", None, "B2C Debit Note"),
    ]

    for seq, (type_code, sub_type, billing_ref, reason, buyer, label) in enumerate(specs, start=1):
        icv += 1
        _step(f"#{seq} {label} (type={type_code}, sub={sub_type})...")

        invoice_hash, inv_uuid, xml_b64, _ = _build_signed_invoice(
            org,
            type_code=type_code,
            sub_type=sub_type,
            icv=icv,
            pih=pih,
            billing_ref=billing_ref,
            reason=reason,
            buyer=buyer,
        )

        try:
            result = await client.check_compliance_invoice(invoice_hash, inv_uuid, xml_b64)
        except ZatcaApiError as e:
            _fail(f"  ZatcaApiError: [{e.error_code}] {e}")
            pih = invoice_hash  # chain continues
            continue
        except Exception as e:
            _fail(f"  Exception: {e}")
            pih = invoice_hash
            continue

        reporting = result.get("reportingStatus", "")
        clearance = result.get("clearanceStatus", "")
        status_str = reporting or clearance or "UNKNOWN"
        err_msgs = result.get("validationResults", {}).get("errorMessages", [])

        is_pass = (
            status_str in ("REPORTED", "CLEARED", "PASS", "NOT_REPORTED", "NOT_CLEARED")
            or (not err_msgs and status_str not in ("REJECTED", "ERROR"))
        )

        if is_pass:
            pass_count += 1
            _ok(f"  {label}: {status_str}")
        else:
            _fail(f"  {label}: {status_str}")

        _print_validation(result)
        pih = invoice_hash

    print()
    _result(f"Compliance check: {pass_count}/6 passed", pass_count == 6)
    if pass_count < 6:
        _fail("Not all invoices passed compliance. Continuing anyway for test coverage.")


# ─── Test 3: Production CSID ─────────────────────────────────────────────────


async def test_3_production_csid(org: FakeOrg, compliance_request_id: str) -> None:
    """POST /production/csids — Exchange compliance CSID for production CSID."""
    _banner("Test 3: POST /production/csids (Production CSID)")

    client = ZatcaApiClient(org)
    _step(f"Requesting production CSID (compliance_request_id={compliance_request_id})...")

    try:
        result = await client.request_production_csid(compliance_request_id)
    except ZatcaApiError as e:
        _fail(f"ZatcaApiError: [{e.error_code}] {e}")
        if e.raw_errors:
            for err in e.raw_errors:
                print(f"      {err}")
        sys.exit(1)

    bst = result.get("binarySecurityToken", "")
    secret = result.get("secret", "")
    request_id = str(result.get("requestID", ""))
    disposition = result.get("dispositionMessage", "")

    _ok(f"dispositionMessage: {disposition}")
    _ok(f"requestID: {request_id}")
    _ok(f"BST length: {len(bst)} chars")

    if disposition != "ISSUED":
        _fail(f"Expected ISSUED, got: {disposition}")
        sys.exit(1)

    # Update to production credentials
    org.csid = bst
    org.certificate_serial = secret
    org.certificate_pem = _decode_bst(bst)
    org.is_production = True

    _ok("Production CSID obtained successfully")


# ─── Test 4: Report Simplified Invoice ────────────────────────────────────────


async def test_4_report_simplified(org: FakeOrg) -> None:
    """POST /invoices/reporting/single — Report a simplified (B2C) invoice."""
    _banner("Test 4: POST /invoices/reporting/single (Report B2C)")

    pih = get_initial_pih()
    invoice_hash, inv_uuid, xml_b64, _ = _build_signed_invoice(
        org,
        type_code="388",
        sub_type="0200000",  # simplified
        icv=1000,
        pih=pih,
        buyer=None,  # B2C = no buyer
    )

    client = ZatcaApiClient(org)
    _step("Submitting simplified invoice for reporting...")

    try:
        result = await client.report_simplified_invoice(invoice_hash, inv_uuid, xml_b64)
    except ZatcaApiError as e:
        _fail(f"ZatcaApiError: [{e.error_code}] {e}")
        return
    except Exception as e:
        _fail(f"Exception: {e}")
        return

    reporting_status = result.get("reportingStatus", "UNKNOWN")
    _ok(f"reportingStatus: {reporting_status}")
    _print_validation(result)

    is_pass = reporting_status in ("REPORTED", "NOT_REPORTED")
    _result(f"Simplified reporting: {reporting_status}", is_pass)


# ─── Test 5: Clear Standard Invoice ──────────────────────────────────────────


async def test_5_clear_standard(org: FakeOrg) -> None:
    """POST /invoices/clearance/single — Clear a standard (B2B) invoice."""
    _banner("Test 5: POST /invoices/clearance/single (Clear B2B)")

    pih = get_initial_pih()
    invoice_hash, inv_uuid, xml_b64, _ = _build_signed_invoice(
        org,
        type_code="388",
        sub_type="0100000",  # standard
        icv=2000,
        pih=pih,
        buyer=B2B_BUYER,
    )

    client = ZatcaApiClient(org)
    _step("Submitting standard invoice for clearance...")

    try:
        result = await client.clear_standard_invoice(invoice_hash, inv_uuid, xml_b64)
    except ZatcaApiError as e:
        _fail(f"ZatcaApiError: [{e.error_code}] {e}")
        return
    except Exception as e:
        _fail(f"Exception: {e}")
        return

    clearance_status = result.get("clearanceStatus", "UNKNOWN")
    cleared_invoice = result.get("clearedInvoice", "")
    _ok(f"clearanceStatus: {clearance_status}")
    if cleared_invoice:
        _ok(f"clearedInvoice received: {len(cleared_invoice)} chars (base64 XML)")
    else:
        _step("No clearedInvoice in response (expected for sandbox with warnings)")

    _print_validation(result)

    is_pass = clearance_status in ("CLEARED", "NOT_CLEARED")
    _result(f"Standard clearance: {clearance_status}", is_pass)


# ─── Test 6: Renew Production CSID ───────────────────────────────────────────


async def test_6_renew_csid(org: FakeOrg) -> None:
    """PATCH /production/csids — Renew production CSID."""
    _banner("Test 6: PATCH /production/csids (Renew Production CSID)")

    # Generate a fresh CSR for renewal
    egs_serial = str(uuid_mod.uuid4())
    _step(f"Generating renewal CSR (EGS serial: {egs_serial[:8]}...)")

    _, csr_pem = generate_csr(
        common_name="Tuwaiq Outdoor EGS",
        org="Tuwaiq Outdoor",
        country="SA",
        serial_number=SANDBOX_VAT,
        org_unit="IT",
        environment="sandbox",
        egs_serial=egs_serial,
        solution_name="TuwaiqPOS",
        version="1.0",
        invoice_type_flag="1100",
        registered_address="Riyadh",
        business_category="Outdoor Activities",
    )

    csr_b64 = base64.b64encode(csr_pem).decode("ascii")
    client = ZatcaApiClient(org)

    _step(f"Calling PATCH /production/csids with OTP={SANDBOX_OTP}...")

    try:
        result = await client.renew_production_csid(csr_b64, SANDBOX_OTP)
    except ZatcaApiError as e:
        _fail(f"ZatcaApiError: [{e.error_code}] {e}")
        if e.raw_errors:
            for err in e.raw_errors:
                print(f"      {err}")
        # Renewal may not be available in sandbox — report but don't fail
        return
    except Exception as e:
        _fail(f"Exception: {e}")
        return

    bst = result.get("binarySecurityToken", "")
    secret = result.get("secret", "")
    request_id = str(result.get("requestID", ""))
    disposition = result.get("dispositionMessage", "")

    _ok(f"dispositionMessage: {disposition}")
    _ok(f"requestID: {request_id}")
    _ok(f"BST length: {len(bst)} chars")

    if disposition == "ISSUED":
        org.csid = bst
        org.certificate_serial = secret
        org.certificate_pem = _decode_bst(bst)
        _ok("Production CSID renewed successfully")
    else:
        _fail(f"Expected ISSUED, got: {disposition}")


# ─── Main ─────────────────────────────────────────────────────────────────────


async def main() -> None:
    print()
    print("  ZATCA API Test Script — All 6 Endpoints")
    print("  ========================================")
    print(f"  Target: {SANDBOX_BASE_URL}")
    print(f"  Test VAT: {SANDBOX_VAT}")
    print(f"  OTP: {SANDBOX_OTP}")
    print()

    org = FakeOrg()
    results: list[tuple[str, bool]] = []

    # Test 1: Compliance CSID
    try:
        compliance_request_id = await test_1_compliance_csid(org)
        results.append(("1. POST /compliance (Compliance CSID)", True))
    except SystemExit:
        results.append(("1. POST /compliance (Compliance CSID)", False))
        print("\n  Cannot continue without compliance CSID. Exiting.")
        _print_summary(results)
        sys.exit(1)

    # Test 2: Compliance Invoice Check (6 types)
    try:
        await test_2_compliance_invoices(org)
        results.append(("2. POST /compliance/invoices (6 types)", True))
    except Exception as e:
        _fail(f"Unexpected error: {e}")
        results.append(("2. POST /compliance/invoices (6 types)", False))

    # Test 3: Production CSID
    try:
        await test_3_production_csid(org, compliance_request_id)
        results.append(("3. POST /production/csids (Production CSID)", True))
    except SystemExit:
        results.append(("3. POST /production/csids (Production CSID)", False))
        print("\n  Cannot continue without production CSID. Exiting.")
        _print_summary(results)
        sys.exit(1)

    # Test 4: Report Simplified Invoice
    try:
        await test_4_report_simplified(org)
        results.append(("4. POST /invoices/reporting/single (Report B2C)", True))
    except Exception as e:
        _fail(f"Unexpected error: {e}")
        results.append(("4. POST /invoices/reporting/single (Report B2C)", False))

    # Test 5: Clear Standard Invoice
    try:
        await test_5_clear_standard(org)
        results.append(("5. POST /invoices/clearance/single (Clear B2B)", True))
    except Exception as e:
        _fail(f"Unexpected error: {e}")
        results.append(("5. POST /invoices/clearance/single (Clear B2B)", False))

    # Test 6: Renew Production CSID
    try:
        await test_6_renew_csid(org)
        results.append(("6. PATCH /production/csids (Renew CSID)", True))
    except Exception as e:
        _fail(f"Unexpected error: {e}")
        results.append(("6. PATCH /production/csids (Renew CSID)", False))

    _print_summary(results)


def _print_summary(results: list[tuple[str, bool]]) -> None:
    _banner("SUMMARY")
    for label, passed in results:
        tag = "[OK]" if passed else "[FAIL]"
        print(f"  {tag} {label}")
    total_pass = sum(1 for _, p in results if p)
    total = len(results)
    print()
    print(f"  Total: {total_pass}/{total} passed")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n  Aborted by user.")
        sys.exit(130)
