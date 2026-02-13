from __future__ import annotations

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.models.einvoice import (
    EInvoice,
    InvoiceSubType,
    ZatcaSubmissionStatus,
)
from backend.app.models.organization import Organization
from backend.app.schemas.einvoice import (
    EInvoiceListOut,
    EInvoiceOut,
    EInvoiceSummaryOut,
    EInvoiceXmlOut,
)
from backend.app.services.audit import log_action

router = APIRouter()


def _einvoice_to_out(e: EInvoice) -> EInvoiceOut:
    return EInvoiceOut(
        id=e.id,
        invoice_uuid=e.invoice_uuid,
        invoice_number=e.invoice_number,
        icv=e.icv,
        type_code=e.type_code.value,
        sub_type=e.sub_type.value,
        total_excluding_vat=str(e.total_excluding_vat),
        total_vat=str(e.total_vat),
        total_including_vat=str(e.total_including_vat),
        buyer_name=e.buyer_name,
        buyer_vat_number=e.buyer_vat_number,
        submission_status=e.submission_status.value,
        zatca_clearance_status=e.zatca_clearance_status,
        zatca_reporting_status=e.zatca_reporting_status,
        zatca_warnings=e.zatca_warnings,
        zatca_errors=e.zatca_errors,
        submitted_at=e.submitted_at,
        issue_date=e.issue_date,
        created_at=e.created_at,
    )


@router.get("", response_model=EInvoiceListOut)
def list_einvoices(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:read")),
) -> EInvoiceListOut:
    query = db.query(EInvoice)
    if status_filter:
        try:
            status_enum = ZatcaSubmissionStatus(status_filter)
            query = query.filter(EInvoice.submission_status == status_enum)
        except ValueError:
            pass

    total = query.count()
    items = query.order_by(EInvoice.created_at.desc()).offset(skip).limit(limit).all()

    return EInvoiceListOut(
        items=[_einvoice_to_out(e) for e in items],
        total=total,
    )


@router.get("/summary", response_model=EInvoiceSummaryOut)
def einvoice_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:read")),
) -> EInvoiceSummaryOut:
    rows = (
        db.query(EInvoice.submission_status, func.count())
        .group_by(EInvoice.submission_status)
        .all()
    )
    counts: dict[str, int] = {r[0].value: r[1] for r in rows}
    total = sum(counts.values())
    return EInvoiceSummaryOut(
        total=total,
        pending=counts.get("PENDING", 0),
        cleared=counts.get("CLEARED", 0),
        reported=counts.get("REPORTED", 0),
        rejected=counts.get("REJECTED", 0),
        warning=counts.get("WARNING", 0),
    )


@router.get("/{invoice_number}", response_model=EInvoiceOut)
def get_einvoice(
    invoice_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:read")),
) -> EInvoiceOut:
    einvoice = (
        db.query(EInvoice)
        .filter(EInvoice.invoice_number == invoice_number)
        .first()
    )
    if not einvoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"E-invoice {invoice_number} not found",
        )
    return _einvoice_to_out(einvoice)


@router.get("/{invoice_number}/xml", response_model=EInvoiceXmlOut)
def get_einvoice_xml(
    invoice_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:read")),
) -> EInvoiceXmlOut:
    einvoice = (
        db.query(EInvoice)
        .filter(EInvoice.invoice_number == invoice_number)
        .first()
    )
    if not einvoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"E-invoice {invoice_number} not found",
        )
    return EInvoiceXmlOut(
        invoice_number=einvoice.invoice_number,
        xml_content=base64.b64encode(einvoice.xml_content).decode("ascii"),
    )


@router.post("/{invoice_number}/submit", response_model=EInvoiceOut)
async def submit_einvoice(
    invoice_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("einvoice:write")),
) -> EInvoiceOut:
    einvoice = (
        db.query(EInvoice)
        .filter(EInvoice.invoice_number == invoice_number)
        .first()
    )
    if not einvoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"E-invoice {invoice_number} not found",
        )

    if einvoice.submission_status not in (
        ZatcaSubmissionStatus.PENDING,
        ZatcaSubmissionStatus.REJECTED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit invoice with status {einvoice.submission_status.value}",
        )

    org = db.query(Organization).first()
    if not org or not org.csid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ZATCA credentials not configured. Complete onboarding first.",
        )

    # Submit to ZATCA
    from backend.app.services.zatca.api_client import ZatcaApiClient

    client = ZatcaApiClient(org)
    xml_b64 = base64.b64encode(einvoice.xml_content).decode("ascii")

    try:
        if einvoice.sub_type == InvoiceSubType.SIMPLIFIED:
            result = await client.report_simplified_invoice(
                einvoice.invoice_hash, einvoice.invoice_uuid, xml_b64
            )
            einvoice.zatca_reporting_status = result.get("reportingStatus")
            if result.get("reportingStatus") == "REPORTED":
                einvoice.submission_status = ZatcaSubmissionStatus.REPORTED
            elif result.get("reportingStatus") == "NOT_REPORTED":
                einvoice.submission_status = ZatcaSubmissionStatus.REJECTED
            else:
                einvoice.submission_status = ZatcaSubmissionStatus.WARNING
        else:
            result = await client.clear_standard_invoice(
                einvoice.invoice_hash, einvoice.invoice_uuid, xml_b64
            )
            einvoice.zatca_clearance_status = result.get("clearanceStatus")
            if result.get("clearanceStatus") == "CLEARED":
                einvoice.submission_status = ZatcaSubmissionStatus.CLEARED
                # Store ZATCA-stamped XML (replaces our original XML)
                cleared_xml = result.get("clearedInvoice")
                if cleared_xml:
                    einvoice.xml_content = base64.b64decode(cleared_xml)
            elif result.get("clearanceStatus") == "NOT_CLEARED":
                einvoice.submission_status = ZatcaSubmissionStatus.REJECTED
            else:
                einvoice.submission_status = ZatcaSubmissionStatus.WARNING

        einvoice.zatca_request_id = result.get("requestID")
        einvoice.zatca_warnings = (
            {"messages": result.get("validationResults", {}).get("warningMessages", [])}
            if result.get("validationResults", {}).get("warningMessages")
            else None
        )
        einvoice.zatca_errors = (
            {"messages": result.get("validationResults", {}).get("errorMessages", [])}
            if result.get("validationResults", {}).get("errorMessages")
            else None
        )

    except Exception as e:
        einvoice.submission_status = ZatcaSubmissionStatus.REJECTED
        einvoice.zatca_errors = {"messages": [{"message": str(e)}]}

    einvoice.submitted_at = datetime.now(timezone.utc)

    log_action(
        db,
        user_id=current_user.id,
        action="EINVOICE_SUBMITTED",
        resource_type="einvoices",
        resource_id=invoice_number,
        changes={
            "status": einvoice.submission_status.value,
            "zatca_request_id": einvoice.zatca_request_id,
        },
    )

    db.commit()
    db.refresh(einvoice)
    return _einvoice_to_out(einvoice)
