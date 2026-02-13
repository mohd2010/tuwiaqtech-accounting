from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from backend.app.models.accounting import AccountType


class AccountCreate(BaseModel):
    code: str
    name: str
    account_type: AccountType
    parent_id: UUID | None = None

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d{4,20}$", v):
            raise ValueError("Code must be 4-20 digits")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name must not be empty")
        return v.strip()


class AccountUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Name must not be empty")
        return v.strip() if v else v


class AccountOut(BaseModel):
    id: UUID
    code: str
    name: str
    account_type: AccountType
    parent_id: UUID | None
    is_active: bool
    is_system: bool
    balance: str
    created_at: datetime

    class Config:
        from_attributes = True
