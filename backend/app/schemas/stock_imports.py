from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PhysicalCountLine(BaseModel):
    sku: str = Field(min_length=1, max_length=30)
    physical_confirmed: int = Field(ge=0)


class PhysicalCountPreviewRow(BaseModel):
    sku: str
    product_name: str
    units_per_case: int
    current_physical_confirmed: int
    requested_physical_confirmed: int
    difference: int


class PhysicalCountPreview(BaseModel):
    filename: str
    valid: bool
    catalog_products: int
    file_products: int
    total_units: int
    changed_products: int
    missing_skus: list[str]
    unknown_skus: list[str]
    duplicate_skus: list[str]
    rows: list[PhysicalCountPreviewRow]


class PhysicalCountRequestCreate(BaseModel):
    reason: str = Field(min_length=3)
    lines: list[PhysicalCountLine] = Field(min_length=1, max_length=500)


class PhysicalCountDecision(BaseModel):
    reason: str = Field(min_length=3)


class PhysicalCountRequestRead(BaseModel):
    approval_id: int
    status: str
    line_count: int
    total_units: int
    changed_products: int
    reason: str
    created_at: datetime
    decided_at: Optional[datetime] = None
