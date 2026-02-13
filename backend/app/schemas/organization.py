from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, field_validator


class OrganizationCreate(BaseModel):
    name_en: str
    name_ar: str
    vat_number: str
    additional_id: str | None = None
    cr_number: str | None = None
    street: str
    building_number: str
    city: str
    district: str
    postal_code: str
    province: str | None = None
    country_code: str = "SA"
    is_production: bool = False
    zatca_api_base_url: str | None = None

    @field_validator("vat_number")
    @classmethod
    def validate_vat_number(cls, v: str) -> str:
        if not re.match(r"^3\d{13}3$", v):
            raise ValueError("VAT number must be 15 digits starting and ending with 3")
        return v

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: str) -> str:
        if not re.match(r"^\d{5}$", v):
            raise ValueError("Postal code must be exactly 5 digits")
        return v

    @field_validator("building_number")
    @classmethod
    def validate_building_number(cls, v: str) -> str:
        if not re.match(r"^\d{4}$", v):
            raise ValueError("Building number must be exactly 4 digits")
        return v


class OrganizationUpdate(BaseModel):
    name_en: str | None = None
    name_ar: str | None = None
    vat_number: str | None = None
    additional_id: str | None = None
    cr_number: str | None = None
    street: str | None = None
    building_number: str | None = None
    city: str | None = None
    district: str | None = None
    postal_code: str | None = None
    province: str | None = None
    country_code: str | None = None
    is_production: bool | None = None
    zatca_api_base_url: str | None = None

    @field_validator("vat_number")
    @classmethod
    def validate_vat_number(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^3\d{13}3$", v):
            raise ValueError("VAT number must be 15 digits starting and ending with 3")
        return v

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^\d{5}$", v):
            raise ValueError("Postal code must be exactly 5 digits")
        return v

    @field_validator("building_number")
    @classmethod
    def validate_building_number(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^\d{4}$", v):
            raise ValueError("Building number must be exactly 4 digits")
        return v


class OrganizationOut(BaseModel):
    id: UUID
    name_en: str
    name_ar: str
    vat_number: str
    additional_id: str | None
    cr_number: str | None
    street: str
    building_number: str
    city: str
    district: str
    postal_code: str
    province: str | None
    country_code: str
    is_production: bool
    zatca_api_base_url: str | None
    has_certificate: bool

    class Config:
        from_attributes = True
