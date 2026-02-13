from __future__ import annotations

from pydantic import BaseModel


# ─── Aging Bucket Row ─────────────────────────────────────────────────────────


class AgingBucketRow(BaseModel):
    name: str
    current: str  # 0-30 days
    days_31_60: str
    days_61_90: str
    over_90: str
    total: str


# ─── AR Aging ────────────────────────────────────────────────────────────────


class ARAgingKPI(BaseModel):
    total_receivable: str
    total_overdue: str
    dso: str  # Days Sales Outstanding


class ARAgingResponse(BaseModel):
    as_of_date: str
    kpi: ARAgingKPI
    customers: list[AgingBucketRow]
    totals: AgingBucketRow


# ─── AP Aging ────────────────────────────────────────────────────────────────


class APAgingKPI(BaseModel):
    total_payable: str
    total_overdue: str


class APAgingResponse(BaseModel):
    as_of_date: str
    kpi: APAgingKPI
    suppliers: list[AgingBucketRow]
    totals: AgingBucketRow
