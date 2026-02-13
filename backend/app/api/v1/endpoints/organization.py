from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.permission_deps import require_permission
from backend.app.core.database import get_db
from backend.app.models.accounting import User
from backend.app.models.organization import Organization
from backend.app.schemas.organization import (
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
)
from backend.app.services.audit import log_action

router = APIRouter()


def _org_to_out(org: Organization) -> OrganizationOut:
    return OrganizationOut(
        id=org.id,
        name_en=org.name_en,
        name_ar=org.name_ar,
        vat_number=org.vat_number,
        additional_id=org.additional_id,
        cr_number=org.cr_number,
        street=org.street,
        building_number=org.building_number,
        city=org.city,
        district=org.district,
        postal_code=org.postal_code,
        province=org.province,
        country_code=org.country_code,
        is_production=org.is_production,
        zatca_api_base_url=org.zatca_api_base_url,
        has_certificate=org.certificate_pem is not None,
    )


@router.get("", response_model=OrganizationOut)
def get_organization(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write")),
) -> OrganizationOut:
    org = db.query(Organization).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not configured",
        )
    return _org_to_out(org)


@router.put("", response_model=OrganizationOut)
def upsert_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write")),
) -> OrganizationOut:
    org = db.query(Organization).first()
    if org:
        # Update existing
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(org, field, value)
    else:
        # Create new
        org = Organization(**payload.model_dump())
        db.add(org)

    db.flush()

    log_action(
        db,
        user_id=current_user.id,
        action="ORGANIZATION_UPDATED",
        resource_type="organizations",
        resource_id=str(org.id),
        changes=payload.model_dump(exclude_unset=True),
    )

    db.commit()
    db.refresh(org)
    return _org_to_out(org)


@router.patch("", response_model=OrganizationOut)
def patch_organization(
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("organization:write")),
) -> OrganizationOut:
    org = db.query(Organization).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not configured. Use PUT to create.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    db.flush()

    log_action(
        db,
        user_id=current_user.id,
        action="ORGANIZATION_UPDATED",
        resource_type="organizations",
        resource_id=str(org.id),
        changes=update_data,
    )

    db.commit()
    db.refresh(org)
    return _org_to_out(org)
