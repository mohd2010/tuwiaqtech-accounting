"""XML canonicalization and SHA-256 hashing for ZATCA e-invoices."""

from __future__ import annotations

import base64
import hashlib

from lxml import etree

from backend.app.services.zatca.xml_builder import CAC, CBC, EXT

# XPath expressions for elements to exclude during hashing
_EXTENSIONS_XPATH = f"//*[local-name()='UBLExtensions']"
_SIGNATURE_XPATH = f"//*[local-name()='Signature' and namespace-uri()='{CAC}']"
_QR_XPATH = (
    f"//*[local-name()='AdditionalDocumentReference']"
    f"[*[local-name()='ID' and text()='QR']]"
)


def canonicalize_xml(xml_element: etree._Element) -> bytes:
    """C14N canonicalization, excluding UBLExtensions, Signature, and QR reference.

    Returns the canonicalized bytes of the invoice body for hashing.
    """
    # Work on a deep copy to avoid mutating the original
    tree = etree.fromstring(etree.tostring(xml_element))

    # Remove elements that must be excluded from the hash
    for xpath in [_EXTENSIONS_XPATH, _SIGNATURE_XPATH, _QR_XPATH]:
        for el in tree.xpath(xpath):
            el.getparent().remove(el)

    return etree.tostring(tree, method="c14n")


def hash_invoice_xml(xml_element: etree._Element) -> str:
    """SHA-256 hash of canonicalized XML, returned as base64 string."""
    canonical = canonicalize_xml(xml_element)
    digest = hashlib.sha256(canonical).digest()
    return base64.b64encode(digest).decode("ascii")


def get_initial_pih() -> str:
    """Base64 of hex SHA-256 of "0" — used as PIH for the first invoice in the chain.

    Per BR-KSA-26, the initial PIH is base64(hex_string_of_sha256("0")),
    yielding: NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ==
    """
    hex_str = hashlib.sha256(b"0").hexdigest()
    return base64.b64encode(hex_str.encode("ascii")).decode("ascii")
