from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReservationCreate(BaseModel):
    sku: str
    quantity: int = Field(gt=0)
    customer_name: Optional[str] = None
    purchase_order_id: Optional[int] = None
    reason: str = Field(min_length=3)


class ReservationRelease(BaseModel):
    reason: str = Field(min_length=3)


class ReservationRead(BaseModel):
    id: int
    sku: str
    quantity: int
    status: str
    customer_name: Optional[str] = None
    reason: str
    created_at: datetime
