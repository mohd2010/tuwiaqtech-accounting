from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.models.organization import Organization
from backend.app.services.audit import log_action
from backend.app.services.zatca.api_client import ZatcaApiError

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────


class CsrRequest(BaseModel):
    common_name: str
    org_unit: str = "IT"
    environment: str = "sandbox"
    egs_serial: str = "1"
    solution_name: str = "TuwaiqPOS"
    version: str = "1.0"
    invoice_type_flag: str = "1100"
    registered_address: str = "Riyadh"
    business_category: str = "Outdoor Activities"


class CsrResponse(BaseModel):
    csr_pem: str
    message: str


class ComplianceCsidRequest(BaseModel):
    otp: str


class CsidResponse(BaseModel):
    csid: str
    request_id: str
    disposition_message: str
    message: str


class ProductionCsidRequest(BaseModel):
    compliance_request_id: str | None = None


class ComplianceCheckRequest(BaseModel):
    invoice_number: str


class ComplianceCheckResponse(BaseModel):
    reporting_status: str | None = None
    clearance_status: str | None = None
    validation_results: dict | None = None
    request_id: str | None = None


class OnboardingStatusResponse(BaseModel):
    onboarding_status: str | None = None
    has_csr: bool = False
    has_compliance_csid: bool = False
    has_production_csid: bool = False


# ─── Helpers ────────────────────────────────────────────────────────────────


def _get_org(db: Session) -> Organization:
    org = db.query(Organization).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization not configured. Set up organization settings first.",
        )
    return org


def _handle_zatca_api_error(e: ZatcaApiError) -> HTTPException:
    """Convert ZatcaApiError into an HTTPException with structured detail."""
    if e.status_code == 406:
        http_status = status.HTTP_502_BAD_GATEWAY
    else:
        http_status = status.HTTP_502_BAD_GATEWAY
    return HTTPException(
        status_code=http_status,
        detail={
            "error": "ZATCA API error",
            "zatca_code": e.error_code,
            "zatca_message": str(e),
            "zatca_errors": e.raw_errors,
        },
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/generate-csr", response_model=CsrResponse)
def generate_csr_endpoint(
    payload: CsrRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:write")),
) -> CsrResponse:
    org = _get_org(db)

    from backend.app.services.zatca.signing import generate_csr

    private_key_pem, csr_pem = generate_csr(
        common_name=payload.common_name,
        org=org.name_en,
        country=org.country_code,
        serial_number=org.vat_number,
        org_unit=payload.org_unit,
        environment=payload.environment,  # type: ignore[arg-type]
        egs_serial=payload.egs_serial,
        solution_name=payload.solution_name,
        version=payload.version,
        invoice_type_flag=payload.invoice_type_flag,
        registered_address=payload.registered_address,
        business_category=payload.business_category,
    )

    # Store private key AND CSR for reuse in compliance-csid.
    # Clear previous onboarding credentials since we're starting fresh.
    org.private_key_pem = private_key_pem
    org.csr_pem = csr_pem
    org.certificate_pem = None
    org.csid = None
    org.certificate_serial = None
    org.compliance_request_id = None
    org.is_production = False
    org.onboarding_status = "CSR_GENERATED"
    db.flush()

    log_action(
        db,
        user_id=current_user.id,
        action="CSR_GENERATED",
        resource_type="organizations",
        resource_id=str(org.id),
        changes={"common_name": payload.common_name},
    )

    db.commit()

    return CsrResponse(
        csr_pem=csr_pem.decode("utf-8"),
        message="CSR generated. Private key and CSR stored. Submit OTP to get compliance CSID.",
    )


@router.post("/compliance-csid", response_model=CsidResponse)
async def request_compliance_csid(
    payload: ComplianceCsidRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:write")),
) -> CsidResponse:
    org = _get_org(db)
    if not org.private_key_pem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate CSR first.",
        )

    # Use stored CSR if available; fall back to rebuilding from key
    if org.csr_pem:
        csr_pem = org.csr_pem
    else:
        from backend.app.services.zatca.signing import generate_csr_from_key

        csr_pem = generate_csr_from_key(
            private_key_pem=org.private_key_pem,
            common_name=org.name_en,
            org=org.name_en,
            country=org.country_code,
            serial_number=org.vat_number,
        )

    # ZATCA expects base64(full PEM) — the entire PEM file (including headers)
    # is base64-encoded into a single continuous string.
    csr_b64 = base64.b64encode(csr_pem).decode("ascii")

    from backend.app.services.zatca.api_client import ZatcaApiClient

    client = ZatcaApiClient(org)
    try:
        result = await client.request_compliance_csid(csr_b64, payload.otp)
    except ZatcaApiError as e:
        raise _handle_zatca_api_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ZATCA API error: {e}",
        )

    # Check dispositionMessage before storing credentials
    disposition = result.get("dispositionMessage", "")
    if disposition != "ISSUED":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ZATCA did not issue certificate. dispositionMessage: {disposition}",
        )

    # Store CSID and certificate
    # ZATCA returns BST as base64(certificate-base64), so double-decode to DER
    binarySecurityToken = result.get("binarySecurityToken", "")
    if binarySecurityToken:
        cert_b64_bytes = base64.b64decode(binarySecurityToken)
        cert_der = base64.b64decode(cert_b64_bytes)
        cert_pem = (
            b"-----BEGIN CERTIFICATE-----\n"
            + base64.encodebytes(cert_der)
            + b"-----END CERTIFICATE-----\n"
        )
        org.certificate_pem = cert_pem
    org.csid = binarySecurityToken
    org.certificate_serial = result.get("secret", "")  # ZATCA "secret" for Basic Auth

    # Persist compliance request ID for production CSID exchange
    # ZATCA may return requestID as int; coerce to str for Pydantic + DB
    request_id = str(result.get("requestID", ""))
    org.compliance_request_id = request_id
    org.onboarding_status = "COMPLIANCE_CSID_ISSUED"

    db.flush()

    log_action(
        db,
        user_id=current_user.id,
        action="COMPLIANCE_CSID_RECEIVED",
        resource_type="organizations",
        resource_id=str(org.id),
        changes={"request_id": request_id, "disposition": disposition},
    )

    # Capture values before commit (commit expires ORM attributes)
    csid_value = binarySecurityToken

    db.commit()

    return CsidResponse(
        csid=csid_value,
        request_id=request_id,
        disposition_message=disposition,
        message="Compliance CSID received. Run compliance check, then get production CSID.",
    )


@router.post("/production-csid", response_model=CsidResponse)
async def request_production_csid(
    payload: ProductionCsidRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:write")),
) -> CsidResponse:
    org = _get_org(db)
    if not org.csid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Get compliance CSID first.",
        )

    # Use provided compliance_request_id or fall back to stored value
    req_id = payload.compliance_request_id or org.compliance_request_id
    if not req_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No compliance_request_id provided or stored. Get compliance CSID first.",
        )

    from backend.app.services.zatca.api_client import ZatcaApiClient

    client = ZatcaApiClient(org)
    try:
        result = await client.request_production_csid(req_id)
    except ZatcaApiError as e:
        raise _handle_zatca_api_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ZATCA API error: {e}",
        )

    disposition = result.get("dispositionMessage", "")
    if disposition != "ISSUED":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ZATCA did not issue production certificate. dispositionMessage: {disposition}",
        )

    # Update to production credentials
    # ZATCA returns BST as base64(certificate-base64), so double-decode to DER
    binarySecurityToken = result.get("binarySecurityToken", "")
    if binarySecurityToken:
        cert_b64_bytes = base64.b64decode(binarySecurityToken)
        cert_der = base64.b64decode(cert_b64_bytes)
        cert_pem = (
            b"-----BEGIN CERTIFICATE-----\n"
            + base64.encodebytes(cert_der)
            + b"-----END CERTIFICATE-----\n"
        )
        org.certificate_pem = cert_pem
    org.csid = binarySecurityToken
    org.certificate_serial = result.get("secret", "")  # ZATCA "secret" for Basic Auth
    org.is_production = True
    org.onboarding_status = "PRODUCTION_READY"

    db.flush()

    log_action(
        db,
        user_id=current_user.id,
        action="PRODUCTION_CSID_RECEIVED",
        resource_type="organizations",
        resource_id=str(org.id),
        changes={"request_id": str(result.get("requestID", "")), "disposition": disposition},
    )

    # Capture values before commit (commit expires ORM attributes)
    csid_value = binarySecurityToken
    prod_request_id = str(result.get("requestID", ""))

    db.commit()

    return CsidResponse(
        csid=csid_value,
        request_id=prod_request_id,
        disposition_message=disposition,
        message="Production CSID received. ZATCA integration is now live.",
    )


@router.post("/compliance-check", response_model=ComplianceCheckResponse)
async def check_compliance_invoice(
    payload: ComplianceCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:write")),
) -> ComplianceCheckResponse:
    """Submit an e-invoice to ZATCA compliance check (onboarding step)."""
    from backend.app.models.einvoice import EInvoice

    einvoice = (
        db.query(EInvoice)
        .filter(EInvoice.invoice_number == payload.invoice_number)
        .first()
    )
    if not einvoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"E-invoice {payload.invoice_number} not found",
        )

    org = _get_org(db)
    if not org.csid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZATCA credentials not configured. Get compliance CSID first.",
        )

    from backend.app.services.zatca.api_client import ZatcaApiClient

    client = ZatcaApiClient(org)
    xml_b64 = base64.b64encode(einvoice.xml_content).decode("ascii")

    try:
        result = await client.check_compliance_invoice(
            einvoice.invoice_hash, einvoice.invoice_uuid, xml_b64
        )
    except ZatcaApiError as e:
        raise _handle_zatca_api_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ZATCA API error: {e}",
        )

    org.onboarding_status = "COMPLIANCE_CHECKED"
    db.flush()

    log_action(
        db,
        user_id=current_user.id,
        action="COMPLIANCE_CHECK_SUBMITTED",
        resource_type="einvoices",
        resource_id=payload.invoice_number,
        changes={"request_id": result.get("requestID", "")},
    )

    db.commit()

    return ComplianceCheckResponse(
        reporting_status=result.get("reportingStatus"),
        clearance_status=result.get("clearanceStatus"),
        validation_results=result.get("validationResults"),
        request_id=str(result.get("requestID")) if result.get("requestID") is not None else None,
    )


class RenewCsidRequest(BaseModel):
    otp: str


@router.post("/renew-csid", response_model=CsidResponse)
async def renew_production_csid(
    payload: RenewCsidRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:write")),
) -> CsidResponse:
    """Renew production CSID (PATCH /production/csids).

    Requires current production CSID + a new CSR + OTP.
    """
    org = _get_org(db)
    if not org.is_production or not org.csid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Production CSID required. Complete onboarding first.",
        )
    if not org.private_key_pem:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Private key not found. Generate CSR first.",
        )

    # Build a fresh CSR from the existing key
    from backend.app.services.zatca.signing import generate_csr_from_key

    csr_pem = generate_csr_from_key(
        private_key_pem=org.private_key_pem,
        common_name=org.name_en,
        org=org.name_en,
        country=org.country_code,
        serial_number=org.vat_number,
    )
    csr_b64 = base64.b64encode(csr_pem).decode("ascii")

    from backend.app.services.zatca.api_client import ZatcaApiClient

    client = ZatcaApiClient(org)
    try:
        result = await client.renew_production_csid(csr_b64, payload.otp)
    except ZatcaApiError as e:
        raise _handle_zatca_api_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ZATCA API error: {e}",
        )

    disposition = result.get("dispositionMessage", "")
    if disposition != "ISSUED":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ZATCA did not renew certificate. dispositionMessage: {disposition}",
        )

    # Update credentials with renewed certificate
    binarySecurityToken = result.get("binarySecurityToken", "")
    if binarySecurityToken:
        cert_b64_bytes = base64.b64decode(binarySecurityToken)
        cert_der = base64.b64decode(cert_b64_bytes)
        cert_pem = (
            b"-----BEGIN CERTIFICATE-----\n"
            + base64.encodebytes(cert_der)
            + b"-----END CERTIFICATE-----\n"
        )
        org.certificate_pem = cert_pem
    org.csid = binarySecurityToken
    org.certificate_serial = result.get("secret", "")
    org.csr_pem = csr_pem

    db.flush()

    log_action(
        db,
        user_id=current_user.id,
        action="PRODUCTION_CSID_RENEWED",
        resource_type="organizations",
        resource_id=str(org.id),
        changes={"request_id": str(result.get("requestID", "")), "disposition": disposition},
    )

    csid_value = binarySecurityToken
    renew_request_id = str(result.get("requestID", ""))

    db.commit()

    return CsidResponse(
        csid=csid_value,
        request_id=renew_request_id,
        disposition_message=disposition,
        message="Production CSID renewed successfully.",
    )


@router.get("/onboarding-status", response_model=OnboardingStatusResponse)
def get_onboarding_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:write")),
) -> OnboardingStatusResponse:
    """Return current ZATCA onboarding step for the organization."""
    org = _get_org(db)
    return OnboardingStatusResponse(
        onboarding_status=org.onboarding_status,
        has_csr=org.csr_pem is not None,
        has_compliance_csid=org.csid is not None and not org.is_production,
        has_production_csid=org.csid is not None and org.is_production,
    )
