from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PurchaseOrderLineCreate(BaseModel):
    sku: str
    requested_quantity: int = Field(gt=0)
    original_description: Optional[str] = None


class PurchaseOrderCreate(BaseModel):
    chain_name: str = Field(min_length=2, max_length=120)
    order_number: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=3)
    notes: Optional[str] = None
    source_filename: Optional[str] = None
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)


class PurchaseOrderRead(BaseModel):
    id: int
    chain_name: str
    order_number: str
    status: str
    total_units: int
    line_count: int
    created_by: Optional[str] = None
    created_at: datetime

