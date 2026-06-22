from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    barcode: Optional[str] = None
    cost: float
    units_per_case: int


class StockPositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    name: str
    units_per_case: int
    physical_confirmed: int
    reserved: int
    invoiced_pending_dispatch: int
    blocked_incident: int
    incoming_expected: int
    available_to_invoice: int
