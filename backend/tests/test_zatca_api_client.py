"""Unit tests for ZatcaApiClient with httpx mock transport."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import httpx
import pytest

from backend.app.services.zatca.api_client import (
    PRODUCTION_BASE_URL,
    SANDBOX_BASE_URL,
    ZatcaApiClient,
)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _mock_org(**overrides: object) -> MagicMock:
    org = MagicMock()
    org.csid = "test-csid-token"
    org.certificate_serial = "test-secret"
    org.is_production = False
    org.zatca_api_base_url = None
    for k, v in overrides.items():
        setattr(org, k, v)
    return org


def _mock_response(status_code: int, json_data: dict) -> httpx.Response:  # type: ignore[type-arg]
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("POST", "https://test.example.com"),
    )


# ─── Tests ──────────────────────────────────────────────────────────────────


class TestHandleResponse:
    """Unit tests for _handle_response static method."""

    def test_200_returns_data(self) -> None:
        resp = _mock_response(200, {"reportingStatus": "REPORTED"})
        data = ZatcaApiClient._handle_response(resp)
        assert data == {"reportingStatus": "REPORTED"}

    def test_400_returns_validation_results(self) -> None:
        """ZATCA 400 with validation errors should be returned, not raised."""
        body = {
            "reportingStatus": "NOT_REPORTED",
            "validationResults": {
                "errorMessages": [{"message": "Invalid hash"}],
                "warningMessages": [],
            },
        }
        resp = _mock_response(400, body)
        data = ZatcaApiClient._handle_response(resp)
        assert data["reportingStatus"] == "NOT_REPORTED"
        assert data["validationResults"]["errorMessages"][0]["message"] == "Invalid hash"

    def test_5xx_raises(self) -> None:
        resp = _mock_response(500, {"error": "Internal Server Error"})
        with pytest.raises(httpx.HTTPStatusError):
            ZatcaApiClient._handle_response(resp)

    def test_502_raises(self) -> None:
        resp = _mock_response(502, {"error": "Bad Gateway"})
        with pytest.raises(httpx.HTTPStatusError):
            ZatcaApiClient._handle_response(resp)


class TestUrlSelection:
    """Verify sandbox vs production URL selection."""

    def test_sandbox_url(self) -> None:
        org = _mock_org(is_production=False)
        client = ZatcaApiClient(org)
        assert client.base_url == SANDBOX_BASE_URL

    def test_production_url(self) -> None:
        org = _mock_org(is_production=True)
        client = ZatcaApiClient(org)
        assert client.base_url == PRODUCTION_BASE_URL

    def test_custom_url_override(self) -> None:
        custom = "https://custom.example.com/api"
        org = _mock_org(zatca_api_base_url=custom)
        client = ZatcaApiClient(org)
        assert client.base_url == custom


class TestAuthHeader:
    """Test Basic auth header construction."""

    def test_valid_credentials(self) -> None:
        org = _mock_org(csid="my-csid", certificate_serial="my-secret")
        client = ZatcaApiClient(org)
        header = client._auth_header()
        assert "Authorization" in header
        assert header["Authorization"].startswith("Basic ")

    def test_missing_csid_raises(self) -> None:
        org = _mock_org(csid=None)
        client = ZatcaApiClient(org)
        with pytest.raises(ValueError, match="ZATCA credentials not configured"):
            client._auth_header()

    def test_missing_secret_raises(self) -> None:
        org = _mock_org(certificate_serial=None)
        client = ZatcaApiClient(org)
        with pytest.raises(ValueError, match="ZATCA credentials not configured"):
            client._auth_header()

    def test_empty_csid_raises(self) -> None:
        org = _mock_org(csid="")
        client = ZatcaApiClient(org)
        with pytest.raises(ValueError, match="ZATCA credentials not configured"):
            client._auth_header()


class TestReportSimplified:
    """Test report_simplified_invoice method."""

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        org = _mock_org()
        api_client = ZatcaApiClient(org)

        mock_resp = _mock_response(200, {
            "reportingStatus": "REPORTED",
            "requestID": "req-123",
            "validationResults": {"warningMessages": [], "errorMessages": []},
        })

        async def _mock_post(*args: object, **kwargs: object) -> httpx.Response:
            return mock_resp

        monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

        result = asyncio.run(
            api_client.report_simplified_invoice("hash1", "uuid1", "xml-b64")
        )
        assert result["reportingStatus"] == "REPORTED"
        assert result["requestID"] == "req-123"

    def test_400_returns_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        org = _mock_org()
        api_client = ZatcaApiClient(org)

        mock_resp = _mock_response(400, {
            "reportingStatus": "NOT_REPORTED",
            "validationResults": {
                "errorMessages": [{"message": "Bad invoice hash"}],
            },
        })

        async def _mock_post(*args: object, **kwargs: object) -> httpx.Response:
            return mock_resp

        monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

        result = asyncio.run(
            api_client.report_simplified_invoice("hash1", "uuid1", "xml-b64")
        )
        assert result["reportingStatus"] == "NOT_REPORTED"
        assert len(result["validationResults"]["errorMessages"]) == 1


class TestClearStandard:
    """Test clear_standard_invoice method."""

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        org = _mock_org()
        api_client = ZatcaApiClient(org)

        mock_resp = _mock_response(200, {
            "clearanceStatus": "CLEARED",
            "clearedInvoice": "PD94bWw=",
            "requestID": "req-456",
            "validationResults": {"warningMessages": [], "errorMessages": []},
        })

        async def _mock_post(*args: object, **kwargs: object) -> httpx.Response:
            return mock_resp

        monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

        result = asyncio.run(
            api_client.clear_standard_invoice("hash2", "uuid2", "xml-b64")
        )
        assert result["clearanceStatus"] == "CLEARED"
        assert result["clearedInvoice"] == "PD94bWw="


class TestComplianceCheck:
    """Test check_compliance_invoice method."""

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        org = _mock_org()
        api_client = ZatcaApiClient(org)

        mock_resp = _mock_response(200, {
            "reportingStatus": "REPORTED",
            "requestID": "req-789",
            "validationResults": {"warningMessages": [], "errorMessages": []},
        })

        async def _mock_post(*args: object, **kwargs: object) -> httpx.Response:
            return mock_resp

        monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

        result = asyncio.run(
            api_client.check_compliance_invoice("hash3", "uuid3", "xml-b64")
        )
        assert result["reportingStatus"] == "REPORTED"


class TestRequestComplianceCsid:
    """Test request_compliance_csid method."""

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        org = _mock_org()
        api_client = ZatcaApiClient(org)

        mock_resp = _mock_response(200, {
            "binarySecurityToken": "token-abc",
            "secret": "secret-xyz",
            "requestID": "req-onboard",
        })

        async def _mock_post(*args: object, **kwargs: object) -> httpx.Response:
            return mock_resp

        monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

        result = asyncio.run(api_client.request_compliance_csid("csr-b64", "123456"))
        assert result["binarySecurityToken"] == "token-abc"
        assert result["secret"] == "secret-xyz"


class TestRequestProductionCsid:
    """Test request_production_csid method."""

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        org = _mock_org()
        api_client = ZatcaApiClient(org)

        mock_resp = _mock_response(200, {
            "binarySecurityToken": "prod-token",
            "secret": "prod-secret",
            "requestID": "req-prod",
        })

        async def _mock_post(*args: object, **kwargs: object) -> httpx.Response:
            return mock_resp

        monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

        result = asyncio.run(api_client.request_production_csid("req-onboard"))
        assert result["binarySecurityToken"] == "prod-token"

    def test_5xx_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        org = _mock_org()
        api_client = ZatcaApiClient(org)

        mock_resp = _mock_response(500, {"error": "Server Error"})

        async def _mock_post(*args: object, **kwargs: object) -> httpx.Response:
            return mock_resp

        monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(api_client.request_production_csid("req-onboard"))
