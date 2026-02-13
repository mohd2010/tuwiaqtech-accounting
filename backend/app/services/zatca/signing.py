"""XMLDsig + XAdES ECDSA signing and CSR generation for ZATCA."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from typing import Literal

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier
from lxml import etree

from backend.app.services.zatca.hashing import canonicalize_xml
from backend.app.services.zatca.xml_builder import CAC, CBC, DS, EXT, SAC, SBC, SIG, XADES

# ZATCA certificateTemplateName extension OID
_CERT_TEMPLATE_OID = ObjectIdentifier("1.3.6.1.4.1.311.20.2")

# Template name per environment
_CERT_TEMPLATE_NAMES: dict[str, str] = {
    "sandbox": "TSTZATCA-Code-Signing",
    "simulation": "PREZATCA-Code-Signing",
    "production": "ZATCA-Code-Signing",
}

# Additional OIDs for SAN dirName
_REGISTERED_ADDRESS_OID = ObjectIdentifier("2.5.4.26")
_BUSINESS_CATEGORY_OID = ObjectIdentifier("2.5.4.15")


def _encode_asn1_utf8_string(value: str) -> bytes:
    """Encode a string as ASN.1 UTF8String (tag 0x0C, length, value).

    ZATCA requires the certificateTemplateName to be UTF8String.
    """
    encoded = value.encode("utf-8")
    length = len(encoded)
    if length < 128:
        return b"\x0c" + bytes([length]) + encoded
    # Long form length for > 127 bytes
    return b"\x0c\x81" + bytes([length]) + encoded

_DS_NS = {"ds": DS}
_XADES_NS = {"xades": XADES}


def generate_csr(
    common_name: str,
    org: str,
    country: str,
    serial_number: str,
    org_unit: str = "IT",
    environment: Literal["sandbox", "simulation", "production"] = "sandbox",
    egs_serial: str = "1",
    solution_name: str = "TuwaiqPOS",
    version: str = "1.0",
    invoice_type_flag: str = "1100",
    registered_address: str = "Riyadh",
    business_category: str = "Outdoor Activities",
) -> tuple[bytes, bytes]:
    """Generate an ECDSA secp256k1 keypair + CSR for ZATCA onboarding.

    Returns (private_key_pem, csr_pem).
    """
    private_key = ec.generate_private_key(ec.SECP256K1())
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    csr_pem = _build_csr(
        private_key,
        common_name=common_name,
        org=org,
        country=country,
        serial_number=serial_number,
        org_unit=org_unit,
        environment=environment,
        egs_serial=egs_serial,
        solution_name=solution_name,
        version=version,
        invoice_type_flag=invoice_type_flag,
        registered_address=registered_address,
        business_category=business_category,
    )

    return private_key_pem, csr_pem


def generate_csr_from_key(
    private_key_pem: bytes,
    common_name: str,
    org: str,
    country: str,
    serial_number: str,
    org_unit: str = "IT",
    environment: Literal["sandbox", "simulation", "production"] = "sandbox",
    egs_serial: str = "1",
    solution_name: str = "TuwaiqPOS",
    version: str = "1.0",
    invoice_type_flag: str = "1100",
    registered_address: str = "Riyadh",
    business_category: str = "Outdoor Activities",
) -> bytes:
    """Build CSR from an existing private key (for compliance CSID request).

    Unlike generate_csr(), this does NOT create a new keypair — it reuses
    the private key that was stored during the initial CSR generation step.
    """
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)

    return _build_csr(
        private_key,
        common_name=common_name,
        org=org,
        country=country,
        serial_number=serial_number,
        org_unit=org_unit,
        environment=environment,
        egs_serial=egs_serial,
        solution_name=solution_name,
        version=version,
        invoice_type_flag=invoice_type_flag,
        registered_address=registered_address,
        business_category=business_category,
    )


def _build_csr(
    private_key: ec.EllipticCurvePrivateKey,
    *,
    common_name: str,
    org: str,
    country: str,
    serial_number: str,
    org_unit: str,
    environment: str,
    egs_serial: str,
    solution_name: str,
    version: str,
    invoice_type_flag: str,
    registered_address: str,
    business_category: str,
) -> bytes:
    """Build a ZATCA-compliant CSR with all required extensions.

    Shared implementation for both generate_csr() and generate_csr_from_key().
    """
    # SN format: 1-<solution_name>|2-<version>|3-<egs_serial>
    san_sn = f"1-{solution_name}|2-{version}|3-{egs_serial}"

    csr_builder = x509.CertificateSigningRequestBuilder()
    # Subject DN matches ZATCA spec: C, OU, O, CN, serialNumber only
    # (no ST/L — the reference openssl.cnf does not include them)
    csr_builder = csr_builder.subject_name(
        x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, org_unit),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            # ZATCA spec: Subject SERIALNUMBER = EGS SN, not VAT number
            # Force UTF8String because the value contains '|' (invalid in PrintableString)
            x509.NameAttribute(NameOID.SERIAL_NUMBER, san_sn, _type=x509.name._ASN1Type.UTF8String),
        ])
    )

    # NOTE: basicConstraints and keyUsage are NOT included in the CSR.
    # These are added by ZATCA's CA when issuing the certificate.
    # Including them causes ZATCA to reject the CSR with "Invalid Request".

    # certificateTemplateName extension (required by ZATCA)
    # Must be ASN.1 UTF8String tagged (0x0C + length + value), matching OpenSSL's
    # "ASN1:UTF8String:TSTZATCA-Code-Signing" encoding
    template_name = _CERT_TEMPLATE_NAMES[environment]
    csr_builder = csr_builder.add_extension(
        x509.UnrecognizedExtension(_CERT_TEMPLATE_OID, _encode_asn1_utf8_string(template_name)),
        critical=False,
    )

    # ZATCA requires SAN with directory name — 5 mandatory fields
    # OID 2.5.4.4 (SN/Surname) is used for the EGS serial, NOT 2.5.4.5
    _SN_OID = ObjectIdentifier("2.5.4.4")
    csr_builder = csr_builder.add_extension(
        x509.SubjectAlternativeName([
            x509.DirectoryName(x509.Name([
                x509.NameAttribute(_SN_OID, san_sn),
                x509.NameAttribute(NameOID.USER_ID, serial_number),
                x509.NameAttribute(NameOID.TITLE, invoice_type_flag),
                x509.NameAttribute(_REGISTERED_ADDRESS_OID, registered_address),
                x509.NameAttribute(_BUSINESS_CATEGORY_OID, business_category),
            ]))
        ]),
        critical=False,
    )

    csr = csr_builder.sign(private_key, hashes.SHA256())  # type: ignore[arg-type]
    return csr.public_bytes(serialization.Encoding.PEM)


def sign_invoice_xml(
    xml_element: etree._Element,
    private_key_pem: bytes,
    certificate_pem: bytes,
) -> etree._Element:
    """Apply XMLDsig + XAdES enveloped signature using ECDSA-SHA256.

    The signing process is done in two passes:
    1. Build the full signature structure with placeholder hashes, inject into tree
    2. Re-compute SignedProperties hash in tree context (where inherited namespace
       declarations affect C14N output), then re-sign

    This two-pass approach is necessary because C14N of SignedProperties produces
    different output when the element is standalone vs embedded in the tree due
    to inherited namespace declarations.
    """
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)

    # 1. Compute invoice body digest
    invoice_digest = canonicalize_xml(xml_element)
    invoice_hash = base64.b64encode(hashlib.sha256(invoice_digest).digest()).decode()

    # 2. Certificate info
    cert = x509.load_pem_x509_certificate(certificate_pem)
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    cert_hash = base64.b64encode(hashlib.sha256(cert_der).digest()).decode()
    cert_b64 = base64.b64encode(cert_der).decode()
    cert_issuer = cert.issuer.rfc4514_string()
    cert_serial = str(cert.serial_number)

    # 3. Build XAdES SignedProperties
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    signed_props = etree.Element(f"{{{XADES}}}SignedProperties", nsmap={"xades": XADES})
    signed_props.set("Id", "xadesSignedProperties")

    ssp = etree.SubElement(signed_props, f"{{{XADES}}}SignedSignatureProperties")
    st = etree.SubElement(ssp, f"{{{XADES}}}SigningTime")
    st.text = now

    sc = etree.SubElement(ssp, f"{{{XADES}}}SigningCertificate")
    sc_cert = etree.SubElement(sc, f"{{{XADES}}}Cert")
    cd = etree.SubElement(sc_cert, f"{{{XADES}}}CertDigest")
    dm = etree.SubElement(cd, f"{{{DS}}}DigestMethod", nsmap={"ds": DS})
    dm.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha256")
    dv = etree.SubElement(cd, f"{{{DS}}}DigestValue")
    dv.text = cert_hash

    issuer_serial = etree.SubElement(sc_cert, f"{{{XADES}}}IssuerSerial")
    xi = etree.SubElement(issuer_serial, f"{{{DS}}}X509IssuerName")
    xi.text = cert_issuer
    xs = etree.SubElement(issuer_serial, f"{{{DS}}}X509SerialNumber")
    xs.text = cert_serial

    # 4. Build SignedInfo with PLACEHOLDER hash (will be recomputed)
    signed_info = etree.Element(f"{{{DS}}}SignedInfo", nsmap={"ds": DS})

    cm = etree.SubElement(signed_info, f"{{{DS}}}CanonicalizationMethod")
    cm.set("Algorithm", "http://www.w3.org/2006/12/xml-c14n11")

    sm = etree.SubElement(signed_info, f"{{{DS}}}SignatureMethod")
    sm.set("Algorithm", "http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256")

    # Reference to invoice body
    ref1 = etree.SubElement(signed_info, f"{{{DS}}}Reference")
    ref1.set("Id", "invoiceSignedData")
    ref1.set("URI", "")
    transforms = etree.SubElement(ref1, f"{{{DS}}}Transforms")
    t1 = etree.SubElement(transforms, f"{{{DS}}}Transform")
    t1.set("Algorithm", "http://www.w3.org/TR/1999/REC-xpath-19991116")
    xpath_el = etree.SubElement(t1, f"{{{DS}}}XPath")
    xpath_el.text = "not(//ancestor-or-self::ext:UBLExtensions)"
    t2 = etree.SubElement(transforms, f"{{{DS}}}Transform")
    t2.set("Algorithm", "http://www.w3.org/2006/12/xml-c14n11")
    dm1 = etree.SubElement(ref1, f"{{{DS}}}DigestMethod")
    dm1.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha256")
    dv1 = etree.SubElement(ref1, f"{{{DS}}}DigestValue")
    dv1.text = invoice_hash

    # Reference to SignedProperties (placeholder — recomputed in pass 2)
    ref2 = etree.SubElement(signed_info, f"{{{DS}}}Reference")
    ref2.set("Type", "http://www.w3.org/2000/09/xmldsig#SignatureProperties")
    ref2.set("URI", "#xadesSignedProperties")
    dm2 = etree.SubElement(ref2, f"{{{DS}}}DigestMethod")
    dm2.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha256")
    dv2 = etree.SubElement(ref2, f"{{{DS}}}DigestValue")
    dv2.text = "PLACEHOLDER"

    # 5. Build ds:Signature element with placeholder SignatureValue
    ds_sig = etree.Element(f"{{{DS}}}Signature", nsmap={"ds": DS})
    ds_sig.append(signed_info)

    sv = etree.SubElement(ds_sig, f"{{{DS}}}SignatureValue")
    sv.text = "PLACEHOLDER"

    ki = etree.SubElement(ds_sig, f"{{{DS}}}KeyInfo")
    x509_data = etree.SubElement(ki, f"{{{DS}}}X509Data")
    x509_cert = etree.SubElement(x509_data, f"{{{DS}}}X509Certificate")
    x509_cert.text = cert_b64

    # Object → QualifyingProperties → SignedProperties
    obj = etree.SubElement(ds_sig, f"{{{DS}}}Object")
    qp = etree.SubElement(obj, f"{{{XADES}}}QualifyingProperties", nsmap={"xades": XADES})
    qp.set("Target", "signature")
    qp.append(signed_props)

    # 6. Inject full structure into UBLExtensions/ExtensionContent
    ext_content = xml_element.find(f".//{{{EXT}}}ExtensionContent")
    if ext_content is not None:
        ubl_doc_sigs = etree.SubElement(
            ext_content,
            f"{{{SIG}}}UBLDocumentSignatures",
            nsmap={"sig": SIG, "sac": SAC, "sbc": SBC},
        )
        sig_info = etree.SubElement(ubl_doc_sigs, f"{{{SAC}}}SignatureInformation")
        sig_id_el = etree.SubElement(sig_info, f"{{{CBC}}}ID")
        sig_id_el.text = "urn:oasis:names:specification:ubl:signature:1"
        ref_sig_id = etree.SubElement(sig_info, f"{{{SBC}}}ReferencedSignatureID")
        ref_sig_id.text = "urn:oasis:names:specification:ubl:signature:Invoice"
        sig_info.append(ds_sig)

    # ── Pass 2: Recompute hashes in tree context ──
    # Now that SignedProperties is embedded in the full tree, its C14N includes
    # inherited namespace declarations. Recompute the hash and re-sign.

    # Find SignedProperties in the tree
    sp_in_tree = xml_element.find(f".//{{{XADES}}}SignedProperties")
    if sp_in_tree is not None:
        sp_c14n = etree.tostring(sp_in_tree, method="c14n")
        sp_hash = base64.b64encode(hashlib.sha256(sp_c14n).digest()).decode()

        # Update the SignedProperties digest in ref2
        dv2.text = sp_hash

        # Re-compute SignedInfo C14N and sign
        si_in_tree = xml_element.find(f".//{{{DS}}}SignedInfo")
        if si_in_tree is not None:
            si_c14n = etree.tostring(si_in_tree, method="c14n")
            signature_value = private_key.sign(si_c14n, ec.ECDSA(hashes.SHA256()))  # type: ignore[union-attr]
            sig_b64 = base64.b64encode(signature_value).decode()

            # Update the SignatureValue
            sv_in_tree = xml_element.find(f".//{{{DS}}}SignatureValue")
            if sv_in_tree is not None:
                sv_in_tree.text = sig_b64

    return xml_element


def compute_certificate_hash(certificate_pem: bytes) -> str:
    """SHA-256 of X.509 certificate (DER encoding) → base64."""
    cert = x509.load_pem_x509_certificate(certificate_pem)
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    return base64.b64encode(hashlib.sha256(cert_der).digest()).decode()


def extract_certificate_signature(certificate_pem: bytes) -> bytes:
    """Extract the certificate's own DER-encoded ECDSA signature. For QR tag 9.

    This is the signature the CA placed on the certificate, NOT a hash of the cert.
    """
    cert = x509.load_pem_x509_certificate(certificate_pem)
    return cert.signature


def extract_public_key_bytes(certificate_pem: bytes) -> bytes:
    """Extract the public key bytes (DER) from certificate. For QR tag 8."""
    cert = x509.load_pem_x509_certificate(certificate_pem)
    return cert.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def extract_signature_value(signed_xml: etree._Element) -> str:
    """Extract base64 signature value from signed XML. For QR tag 7."""
    sig_val = signed_xml.find(f".//{{{DS}}}SignatureValue")
    if sig_val is not None and sig_val.text:
        return sig_val.text.strip()
    return ""
