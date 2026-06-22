from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StockAdjustmentRequestCreate(BaseModel):
    sku: str
    requested_physical_confirmed: int = Field(ge=0)
    reason: str = Field(min_length=3)


class StockAdjustmentDecision(BaseModel):
    reason: str = Field(min_length=3)


class StockAdjustmentRead(BaseModel):
    approval_id: int
    sku: str
    status: str
    current_physical_confirmed: int
    requested_physical_confirmed: int
    reason: str
    created_at: datetime
    decided_at: Optional[datetime] = None
