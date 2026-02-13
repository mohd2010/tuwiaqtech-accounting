"""ZATCA Fatoora API HTTP client for invoice submission and CSID management."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from backend.app.models.organization import Organization

# Default ZATCA sandbox URL
SANDBOX_BASE_URL = "https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal"
SIMULATION_BASE_URL = "https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation"
PRODUCTION_BASE_URL = "https://gw-fatoora.zatca.gov.sa/e-invoicing/core"


class ZatcaApiError(Exception):
    """Structured error from ZATCA API (4xx responses)."""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        raw_errors: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.raw_errors = raw_errors
        super().__init__(message)


class ZatcaApiClient:
    """HTTP client for ZATCA Fatoora Portal API."""

    def __init__(self, org: Organization) -> None:
        self.org = org
        self.base_url = org.zatca_api_base_url or (
            PRODUCTION_BASE_URL if org.is_production else SANDBOX_BASE_URL
        )

    def _auth_header(self) -> dict[str, str]:
        """Basic auth using CSID:secret."""
        if not self.org.csid or not self.org.certificate_serial:
            raise ValueError("ZATCA credentials not configured")
        creds = base64.b64encode(
            f"{self.org.csid}:{self.org.certificate_serial}".encode()
        ).decode()
        return {"Authorization": f"Basic {creds}"}

    @staticmethod
    def _handle_response(resp: httpx.Response) -> dict[str, Any]:
        """Parse response, extracting validation results even from 4xx errors.

        Invoice submission endpoints (reporting, clearance, compliance check)
        return validation results in 400 responses that callers need to process
        (e.g. to mark invoices as REJECTED). These are returned as data, not raised.
        Only 5xx are true server errors.
        """
        if resp.status_code == 406:
            raise ZatcaApiError(
                status_code=406,
                error_code="Version-Not-Supported",
                message=resp.text or "API version not supported",
            )

        if resp.status_code >= 500:
            resp.raise_for_status()

        # Handle empty/non-JSON responses from ZATCA (e.g. credit note errors)
        try:
            data: dict[str, Any] = resp.json()
        except Exception:
            if resp.status_code >= 400:
                raise ZatcaApiError(
                    status_code=resp.status_code,
                    error_code="INVALID_RESPONSE",
                    message=resp.text or f"HTTP {resp.status_code} (empty body)",
                )
            raise ZatcaApiError(
                status_code=resp.status_code,
                error_code="PARSE_ERROR",
                message=f"Non-JSON response: {resp.text[:200] if resp.text else '(empty)'}",
            )
        return data

    @staticmethod
    def _handle_onboarding_response(resp: httpx.Response) -> dict[str, Any]:
        """Parse response for onboarding endpoints (CSID requests).

        Unlike invoice submission, onboarding 400s contain structured error
        codes (Invalid-OTP, Missing-CSR, etc.) that should be raised.
        ZATCA may also return plain-text error bodies for some 400s.
        """
        if resp.status_code == 406:
            raise ZatcaApiError(
                status_code=406,
                error_code="Version-Not-Supported",
                message=resp.text or "API version not supported",
            )

        if resp.status_code >= 500:
            resp.raise_for_status()

        # Parse JSON; handle plain-text error bodies gracefully
        try:
            data: dict[str, Any] = resp.json()
        except Exception:
            if resp.status_code >= 400:
                raise ZatcaApiError(
                    status_code=resp.status_code,
                    error_code="INVALID_RESPONSE",
                    message=resp.text or f"HTTP {resp.status_code}",
                )
            raise ZatcaApiError(
                status_code=resp.status_code,
                error_code="PARSE_ERROR",
                message=f"Non-JSON response: {resp.text[:200]}",
            )

        if resp.status_code >= 400:
            errors: list[dict[str, Any]] = data.get("errors", [])
            if errors:
                first = errors[0]
                code = first.get("code", "UNKNOWN")
                msg = first.get("message", str(data))
            else:
                code = "UNKNOWN"
                msg = data.get("message", str(data))
            raise ZatcaApiError(
                status_code=resp.status_code,
                error_code=code,
                message=msg,
                raw_errors=errors or None,
            )

        return data

    async def report_simplified_invoice(
        self, invoice_hash: str, invoice_uuid: str, xml_base64: str
    ) -> dict[str, Any]:
        """Report a simplified (B2C) invoice to ZATCA."""
        url = f"{self.base_url}/invoices/reporting/single"
        payload = {
            "invoiceHash": invoice_hash,
            "uuid": invoice_uuid,
            "invoice": xml_base64,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    **self._auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Version": "V2",
                    "Accept-Language": "en",
                    "Clearance-Status": "0",
                },
            )
            return self._handle_response(resp)

    async def clear_standard_invoice(
        self, invoice_hash: str, invoice_uuid: str, xml_base64: str
    ) -> dict[str, Any]:
        """Submit a standard (B2B) invoice for clearance to ZATCA."""
        url = f"{self.base_url}/invoices/clearance/single"
        payload = {
            "invoiceHash": invoice_hash,
            "uuid": invoice_uuid,
            "invoice": xml_base64,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    **self._auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Version": "V2",
                    "Accept-Language": "en",
                    "Clearance-Status": "1",
                },
            )
            return self._handle_response(resp)

    async def check_compliance_invoice(
        self, invoice_hash: str, invoice_uuid: str, xml_base64: str
    ) -> dict[str, Any]:
        """Submit test invoice for compliance check (onboarding step 3)."""
        url = f"{self.base_url}/compliance/invoices"
        payload = {
            "invoiceHash": invoice_hash,
            "uuid": invoice_uuid,
            "invoice": xml_base64,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    **self._auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Version": "V2",
                    "Accept-Language": "en",
                },
            )
            return self._handle_response(resp)

    async def request_compliance_csid(
        self, csr_base64: str, otp: str
    ) -> dict[str, Any]:
        """Submit CSR with OTP to get compliance CSID."""
        url = f"{self.base_url}/compliance"
        payload = {"csr": csr_base64}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Version": "V2",
                    "OTP": otp,
                },
            )
            return self._handle_onboarding_response(resp)

    async def request_production_csid(
        self, compliance_request_id: str
    ) -> dict[str, Any]:
        """Exchange compliance CSID for production CSID."""
        url = f"{self.base_url}/production/csids"
        payload = {"compliance_request_id": compliance_request_id}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    **self._auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Version": "V2",
                },
            )
            return self._handle_onboarding_response(resp)

    async def renew_production_csid(
        self, csr_base64: str, otp: str
    ) -> dict[str, Any]:
        """Renew production CSID (PATCH /production/csids).

        Uses current production CSID + secret for Basic auth, plus OTP
        header and a new CSR in the body. ZATCA returns a new
        binarySecurityToken, secret, and requestID.
        """
        url = f"{self.base_url}/production/csids"
        payload = {"csr": csr_base64}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                url,
                json=payload,
                headers={
                    **self._auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Version": "V2",
                    "OTP": otp,
                },
            )
            return self._handle_onboarding_response(resp)
