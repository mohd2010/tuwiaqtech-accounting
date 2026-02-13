"""Unit tests for ZATCA XML builder, hashing, QR code, and validation."""

from __future__ import annotations

import base64
import hashlib
from decimal import Decimal

import pytest
from lxml import etree

from backend.app.services.zatca.hashing import (
    get_initial_pih,
    hash_invoice_xml,
)
from backend.app.services.zatca.qr_code import generate_phase2_qr
from backend.app.services.zatca.validation import validate_invoice_data
from backend.app.services.zatca.xml_builder import (
    CAC,
    CBC,
    EXT,
    BuyerInfo,
    InvoiceData,
    InvoiceLineData,
    PaymentMeansData,
    SellerInfo,
    build_credit_note_xml,
    build_invoice_xml,
)


# ─── Shared fixtures ────────────────────────────────────────────────────────


def _sample_seller() -> SellerInfo:
    return SellerInfo(
        name_en="Tuwaiq Outdoor",
        name_ar="تواق للأنشطة الخارجية",
        vat_number="399999999999993",
        street="King Fahd Road",
        building_number="1234",
        city="Riyadh",
        district="Al Olaya",
        postal_code="12345",
        country_code="SA",
        cr_number="1010123456",
    )


def _sample_buyer() -> BuyerInfo:
    return BuyerInfo(
        name="Test B2B Customer",
        vat_number="300000000000003",
        street="Prince Sultan St",
        building_number="5678",
        city="Jeddah",
        district="Al Rawdah",
        postal_code="23456",
        country_code="SA",
    )


def _sample_lines() -> list[InvoiceLineData]:
    return [
        InvoiceLineData(
            line_id="1",
            item_name="Product A",
            quantity=Decimal("2"),
            unit_price=Decimal("86.96"),
            net_amount=Decimal("173.91"),
            vat_amount=Decimal("26.09"),
            line_amount_incl_vat=Decimal("200.00"),
        ),
        InvoiceLineData(
            line_id="2",
            item_name="Product B",
            quantity=Decimal("1"),
            unit_price=Decimal("173.91"),
            net_amount=Decimal("173.91"),
            vat_amount=Decimal("26.09"),
            line_amount_incl_vat=Decimal("200.00"),
        ),
    ]


def _sample_invoice_data(**overrides: object) -> InvoiceData:
    defaults = dict(
        invoice_id="INV-2026-0001",
        uuid="550e8400-e29b-41d4-a716-446655440000",
        issue_date="2026-02-12",
        issue_time="14:30:00",
        type_code="388",
        sub_type="0200000",
        currency_code="SAR",
        seller=_sample_seller(),
        buyer=_sample_buyer(),
        lines=_sample_lines(),
        payment_means=[PaymentMeansData(code="10")],
        total_excluding_vat=Decimal("347.82"),
        total_vat=Decimal("52.18"),
        total_including_vat=Decimal("400.00"),
        icv=1,
        pih=get_initial_pih(),
        supply_date="2026-02-12",
    )
    defaults.update(overrides)
    return InvoiceData(**defaults)  # type: ignore[arg-type]


# ─── XML Builder Tests ───────────────────────────────────────────────────────


class TestBuildInvoiceXml:
    def test_build_simplified_invoice_xml(self) -> None:
        data = _sample_invoice_data(sub_type="0200000", buyer=None)
        xml = build_invoice_xml(data)
        xml_str = etree.tostring(xml, encoding="unicode")

        # ProfileID
        assert "reporting:1.0" in xml_str
        # ID
        assert "INV-2026-0001" in xml_str
        # UUID
        assert "550e8400-e29b-41d4-a716-446655440000" in xml_str
        # Type code
        assert "388" in xml_str
        # Currency
        assert "SAR" in xml_str
        # Seller name
        assert "Tuwaiq Outdoor" in xml_str

    def test_build_standard_invoice_xml(self) -> None:
        data = _sample_invoice_data(sub_type="0100000", buyer=_sample_buyer())
        xml = build_invoice_xml(data)
        xml_str = etree.tostring(xml, encoding="unicode")

        # Buyer info present
        assert "Test B2B Customer" in xml_str
        assert "300000000000003" in xml_str
        assert "Prince Sultan St" in xml_str

    def test_build_credit_note_xml(self) -> None:
        data = _sample_invoice_data(
            type_code="381",
            billing_reference_id="INV-2026-0001",
            credit_debit_reason="Customer return",
        )
        xml = build_credit_note_xml(data)
        xml_str = etree.tostring(xml, encoding="unicode")

        # Credit note type code
        assert "381" in xml_str
        # Billing reference
        assert "INV-2026-0001" in xml_str
        # Uses Invoice root (ZATCA requires Invoice root for all types)
        assert "InvoiceLine" in xml_str

    def test_xml_element_ordering(self) -> None:
        """ZATCA requires elements in a specific order."""
        data = _sample_invoice_data()
        xml = build_invoice_xml(data)

        children = [child.tag for child in xml]

        # UBLExtensions must come first
        assert f"{{{EXT}}}UBLExtensions" in children[0]
        # ProfileID second
        assert f"{{{CBC}}}ProfileID" in children[1]
        # ID third
        assert f"{{{CBC}}}ID" in children[2]

    def test_monetary_amounts_have_currency(self) -> None:
        """All monetary amounts must have currencyID='SAR'."""
        data = _sample_invoice_data()
        xml = build_invoice_xml(data)

        # Find all elements with currencyID attribute
        for el in xml.iter():
            if "currencyID" in el.attrib:
                assert el.attrib["currencyID"] == "SAR"

    def test_vat_breakdown_matches_totals(self) -> None:
        """Both TaxTotal TaxAmount values should match total_vat."""
        data = _sample_invoice_data()
        xml = build_invoice_xml(data)

        # Two TaxTotal elements: 1st with subtotals, 2nd without
        tax_totals = xml.findall(f"{{{CAC}}}TaxTotal")
        assert len(tax_totals) == 2

        # Both should have TaxAmount = 52.18
        for tt in tax_totals:
            tax_amount = Decimal(tt.find(f"{{{CBC}}}TaxAmount").text)
            assert tax_amount == Decimal("52.18")

    def test_two_tax_totals_structure(self) -> None:
        """1st TaxTotal has subtotals, 2nd does not (BR-KSA-EN16931-08/09)."""
        data = _sample_invoice_data()
        xml = build_invoice_xml(data)

        tax_totals = xml.findall(f"{{{CAC}}}TaxTotal")
        assert len(tax_totals) == 2

        # 1st TaxTotal must have TaxSubtotal children
        subtotals = tax_totals[0].findall(f"{{{CAC}}}TaxSubtotal")
        assert len(subtotals) >= 1

        # 2nd TaxTotal must NOT have TaxSubtotal children
        subtotals_2 = tax_totals[1].findall(f"{{{CAC}}}TaxSubtotal")
        assert len(subtotals_2) == 0

    def test_second_tax_total_is_sar(self) -> None:
        """2nd TaxTotal must always use SAR (BR-KSA-EN16931-09)."""
        data = _sample_invoice_data()
        xml = build_invoice_xml(data)

        tax_totals = xml.findall(f"{{{CAC}}}TaxTotal")
        second_tax_amount = tax_totals[1].find(f"{{{CBC}}}TaxAmount")
        assert second_tax_amount.attrib["currencyID"] == "SAR"

    def test_tax_currency_code_is_sar(self) -> None:
        """TaxCurrencyCode must always be SAR (BR-KSA-EN16931-02)."""
        data = _sample_invoice_data(currency_code="USD")
        xml = build_invoice_xml(data)
        xml_str = etree.tostring(xml, encoding="unicode")

        # TaxCurrencyCode should be SAR even when document currency is USD
        tax_curr = xml.find(f"{{{CBC}}}TaxCurrencyCode")
        assert tax_curr.text == "SAR"

        # DocumentCurrencyCode should be USD
        doc_curr = xml.find(f"{{{CBC}}}DocumentCurrencyCode")
        assert doc_curr.text == "USD"

    def test_payable_amount_present(self) -> None:
        """LegalMonetaryTotal must have PayableAmount."""
        data = _sample_invoice_data()
        xml = build_invoice_xml(data)

        lmt = xml.find(f"{{{CAC}}}LegalMonetaryTotal")
        payable = lmt.find(f"{{{CBC}}}PayableAmount")
        assert payable is not None
        assert Decimal(payable.text) == Decimal("400.00")

    def test_payable_with_prepaid(self) -> None:
        """PayableAmount = TaxInclusiveAmount - PrepaidAmount."""
        data = _sample_invoice_data(prepaid_amount=Decimal("100.00"))
        xml = build_invoice_xml(data)

        lmt = xml.find(f"{{{CAC}}}LegalMonetaryTotal")
        payable = lmt.find(f"{{{CBC}}}PayableAmount")
        assert Decimal(payable.text) == Decimal("300.00")

        prepaid = lmt.find(f"{{{CBC}}}PrepaidAmount")
        assert prepaid is not None
        assert Decimal(prepaid.text) == Decimal("100.00")

    def test_multi_vat_category_breakdown(self) -> None:
        """Multiple VAT categories produce multiple TaxSubtotals."""
        lines = [
            InvoiceLineData(
                line_id="1",
                item_name="Taxable Product",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                net_amount=Decimal("100.00"),
                vat_amount=Decimal("15.00"),
                vat_category_code="S",
                vat_rate=Decimal("15.00"),
                line_amount_incl_vat=Decimal("115.00"),
            ),
            InvoiceLineData(
                line_id="2",
                item_name="Exempt Product",
                quantity=Decimal("1"),
                unit_price=Decimal("200.00"),
                net_amount=Decimal("200.00"),
                vat_amount=Decimal("0.00"),
                vat_category_code="E",
                vat_rate=Decimal("0.00"),
                line_amount_incl_vat=Decimal("200.00"),
            ),
        ]
        data = _sample_invoice_data(
            lines=lines,
            total_excluding_vat=Decimal("300.00"),
            total_vat=Decimal("15.00"),
            total_including_vat=Decimal("315.00"),
            tax_exemption_reason_code="VATEX-SA-29",
            tax_exemption_reason="Financial services",
        )
        xml = build_invoice_xml(data)

        # 1st TaxTotal should have 2 subtotals (S and E)
        tt1 = xml.findall(f"{{{CAC}}}TaxTotal")[0]
        subtotals = tt1.findall(f"{{{CAC}}}TaxSubtotal")
        assert len(subtotals) == 2

        # Check categories
        categories = []
        for sub in subtotals:
            cat = sub.find(f"{{{CAC}}}TaxCategory/{{{CBC}}}ID")
            categories.append(cat.text)
        assert "S" in categories
        assert "E" in categories

    def test_allowance_charge_has_reason_code(self) -> None:
        """Document-level AllowanceCharge must have AllowanceChargeReasonCode."""
        data = _sample_invoice_data(discount_amount=Decimal("10.00"))
        xml = build_invoice_xml(data)

        ac = xml.find(f"{{{CAC}}}AllowanceCharge")
        assert ac is not None
        reason_code = ac.find(f"{{{CBC}}}AllowanceChargeReasonCode")
        assert reason_code is not None
        assert reason_code.text == "95"

    def test_credit_note_instruction_note(self) -> None:
        """Credit notes must have InstructionNote in PaymentMeans (BR-KSA-17)."""
        data = _sample_invoice_data(
            type_code="381",
            billing_reference_id="INV-2026-0001",
            credit_debit_reason="Defective goods",
        )
        xml = build_credit_note_xml(data)

        pm = xml.find(f"{{{CAC}}}PaymentMeans")
        note = pm.find(f"{{{CBC}}}InstructionNote")
        assert note is not None
        assert note.text == "Defective goods"


# ─── Hashing Tests ───────────────────────────────────────────────────────────


class TestHashing:
    def test_initial_pih(self) -> None:
        """The initial PIH is base64(hex_of_sha256('0')) per BR-KSA-26."""
        expected = base64.b64encode(
            hashlib.sha256(b"0").hexdigest().encode("ascii")
        ).decode()
        assert get_initial_pih() == expected
        # Known value from ZATCA spec
        assert (
            get_initial_pih()
            == "NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ=="
        )

    def test_hash_deterministic(self) -> None:
        """Same XML should produce the same hash."""
        data = _sample_invoice_data()
        xml1 = build_invoice_xml(data)
        xml2 = build_invoice_xml(data)

        hash1 = hash_invoice_xml(xml1)
        hash2 = hash_invoice_xml(xml2)
        assert hash1 == hash2

    def test_hash_is_base64(self) -> None:
        data = _sample_invoice_data()
        xml = build_invoice_xml(data)
        h = hash_invoice_xml(xml)
        # Should be valid base64
        decoded = base64.b64decode(h)
        assert len(decoded) == 32  # SHA-256 = 32 bytes


# ─── QR Code Tests ───────────────────────────────────────────────────────────


class TestPhase2Qr:
    def test_phase2_qr_9_tags(self) -> None:
        """Phase 2 QR must contain all 9 TLV tags."""
        qr = generate_phase2_qr(
            seller_name="Test Seller",
            vat_number="399999999999993",
            timestamp="2026-02-12T14:30:00Z",
            total_amount="400.00",
            vat_amount="52.18",
            invoice_hash="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            ecdsa_signature="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=",
            public_key=b"\x02" * 33,
            certificate_signature=b"\x03" * 32,
        )

        # Should be valid base64
        raw = base64.b64decode(qr)

        # Parse TLV tags — simple 1-byte tag + 1-byte length
        tags_found: list[int] = []
        pos = 0
        while pos < len(raw):
            tag = raw[pos]
            pos += 1
            length = raw[pos]
            pos += 1
            pos += length
            tags_found.append(tag)

        assert sorted(tags_found) == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    def test_phase2_qr_is_base64(self) -> None:
        qr = generate_phase2_qr(
            seller_name="S",
            vat_number="V",
            timestamp="T",
            total_amount="1",
            vat_amount="0",
            invoice_hash="AA==",
            ecdsa_signature="AA==",
            public_key=b"\x00",
            certificate_signature=b"\x00",
        )
        # Should not raise
        base64.b64decode(qr)


# ─── Validation Tests ────────────────────────────────────────────────────────


class TestValidation:
    def test_valid_invoice_passes(self) -> None:
        data = _sample_invoice_data()
        errors = validate_invoice_data(data)
        assert errors == []

    def test_invalid_vat_number(self) -> None:
        seller = _sample_seller()
        seller.vat_number = "1234567890"
        data = _sample_invoice_data(seller=seller)
        errors = validate_invoice_data(data)
        assert any("BR-KSA-39/40" in e for e in errors)

    def test_invalid_postal_code(self) -> None:
        seller = _sample_seller()
        seller.postal_code = "123"
        data = _sample_invoice_data(seller=seller)
        errors = validate_invoice_data(data)
        assert any("BR-KSA-66" in e for e in errors)

    def test_invalid_building_number(self) -> None:
        seller = _sample_seller()
        seller.building_number = "12"
        data = _sample_invoice_data(seller=seller)
        errors = validate_invoice_data(data)
        assert any("BR-KSA-37" in e for e in errors)

    def test_standard_invoice_requires_buyer(self) -> None:
        data = _sample_invoice_data(sub_type="0100000", buyer=None)
        errors = validate_invoice_data(data)
        assert any("BR-KSA-25" in e for e in errors)

    def test_invalid_type_code(self) -> None:
        data = _sample_invoice_data(type_code="999")
        errors = validate_invoice_data(data)
        assert any("BR-KSA-05" in e for e in errors)

    def test_vat_total_mismatch(self) -> None:
        data = _sample_invoice_data(total_vat=Decimal("999.99"))
        errors = validate_invoice_data(data)
        assert any("BR-KSA-EN16931-08" in e for e in errors)

    def test_line_amount_mismatch(self) -> None:
        lines = [
            InvoiceLineData(
                line_id="1",
                item_name="Bad Line",
                quantity=Decimal("2"),
                unit_price=Decimal("100.00"),
                net_amount=Decimal("999.00"),  # Wrong: should be 200
                vat_amount=Decimal("30.00"),
            ),
        ]
        data = _sample_invoice_data(lines=lines)
        errors = validate_invoice_data(data)
        assert any("BR-KSA-EN16931-11" in e for e in errors)

    def test_credit_note_requires_reason(self) -> None:
        data = _sample_invoice_data(
            type_code="381",
            billing_reference_id="INV-001",
            credit_debit_reason=None,
        )
        errors = validate_invoice_data(data)
        assert any("BR-KSA-17" in e for e in errors)

    def test_credit_note_requires_billing_reference(self) -> None:
        data = _sample_invoice_data(
            type_code="381",
            billing_reference_id=None,
            credit_debit_reason="Return",
        )
        errors = validate_invoice_data(data)
        assert any("BR-KSA-56" in e for e in errors)

    def test_invalid_vat_category(self) -> None:
        lines = [
            InvoiceLineData(
                line_id="1",
                item_name="Bad",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                net_amount=Decimal("100.00"),
                vat_amount=Decimal("0.00"),
                vat_category_code="X",
            ),
        ]
        data = _sample_invoice_data(
            lines=lines,
            total_excluding_vat=Decimal("100.00"),
            total_vat=Decimal("0.00"),
            total_including_vat=Decimal("100.00"),
        )
        errors = validate_invoice_data(data)
        assert any("BR-KSA-18" in e for e in errors)

    def test_buyer_vat_format_validation(self) -> None:
        buyer = _sample_buyer()
        buyer.vat_number = "1234567890"
        data = _sample_invoice_data(buyer=buyer)
        errors = validate_invoice_data(data)
        assert any("BR-KSA-44" in e for e in errors)

    def test_prepayment_type_code_accepted(self) -> None:
        data = _sample_invoice_data(type_code="386")
        errors = validate_invoice_data(data)
        assert not any("BR-KSA-05" in e for e in errors)

    def test_issue_time_mandatory(self) -> None:
        data = _sample_invoice_data(issue_time="")
        errors = validate_invoice_data(data)
        assert any("BR-KSA-70" in e for e in errors)

    def test_tax_inclusive_mismatch(self) -> None:
        data = _sample_invoice_data(
            total_excluding_vat=Decimal("347.82"),
            total_vat=Decimal("52.18"),
            total_including_vat=Decimal("999.00"),  # Wrong
        )
        errors = validate_invoice_data(data)
        assert any("BR-CO-15" in e for e in errors)

    def test_standard_requires_buyer_name(self) -> None:
        buyer = BuyerInfo(name="", vat_number="300000000000003")
        data = _sample_invoice_data(sub_type="0100000", buyer=buyer)
        errors = validate_invoice_data(data)
        assert any("BR-KSA-42" in e for e in errors)
