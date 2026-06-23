from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InvoiceLineCreate(BaseModel):
    sku: str
    quantity: int = Field(gt=0)


class InvoiceCreate(BaseModel):
    invoice_number: str
    customer_name: Optional[str] = None
    purchase_order_id: Optional[int] = None
    contifico_source_id: Optional[str] = None
    reason: str = Field(min_length=3)
    notes: Optional[str] = None
    lines: list[InvoiceLineCreate] = Field(min_length=1)


class InvoiceLineRead(BaseModel):
    sku: str
    quantity: int


class InvoiceRead(BaseModel):
    id: int
    invoice_number: str
    status: str
    lines: list[InvoiceLineRead]


class InvoiceSummaryRead(BaseModel):
    id: int
    invoice_number: str
    customer_name: Optional[str] = None
    status: str
    total_units: int
    dispatched_units: int
    missing_units: int
    pending_units: int
    registered_by: Optional[str] = None
    registered_at: datetime
