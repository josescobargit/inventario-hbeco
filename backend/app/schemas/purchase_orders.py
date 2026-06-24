from __future__ import annotations

from datetime import date, datetime
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
    external_reference: Optional[str] = None
    order_date: Optional[date] = None
    delivery_start_date: Optional[date] = None
    delivery_due_date: Optional[date] = None
    destination: Optional[str] = None
    reserve_stock: bool = False
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)


class PurchaseOrderRead(BaseModel):
    id: int
    chain_name: str
    order_number: str
    status: str
    total_units: int
    line_count: int
    order_date: Optional[date] = None
    delivery_due_date: Optional[date] = None
    destination: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime


class PurchaseOrderPreviewLineRead(BaseModel):
    sku: Optional[str] = None
    product_name: Optional[str] = None
    requested_quantity: int
    quantity_cases: Optional[int] = None
    units_per_case: int
    available_to_invoice: int
    can_invoice_quantity: int
    missing_quantity: int
    availability_status: str
    match_status: str = "reconocido"
    original_description: Optional[str] = None


class PurchaseOrderPreviewRead(BaseModel):
    chain_name: str
    order_number: str
    external_reference: Optional[str] = None
    order_date: Optional[date] = None
    delivery_start_date: Optional[date] = None
    delivery_due_date: Optional[date] = None
    destination: Optional[str] = None
    total_units: int
    line_count: int
    can_invoice_units: int
    missing_units: int
    lines: list[PurchaseOrderPreviewLineRead]


class PurchaseOrderFilePreviewRead(BaseModel):
    source_filename: str
    order_count: int
    orders: list[PurchaseOrderPreviewRead]


class PurchaseOrderDetailLineRead(BaseModel):
    sku: str
    product_name: str
    requested_quantity: int
    reserved_quantity: int
    invoiced_quantity: int
    dispatched_quantity: int
    missing_dispatch_quantity: int
    remaining_to_invoice: int


class TraceEventRead(BaseModel):
    event_type: str
    title: str
    detail: str
    occurred_at: datetime
    user_name: Optional[str] = None


class PurchaseOrderDetailRead(BaseModel):
    id: int
    chain_name: str
    order_number: str
    external_reference: Optional[str] = None
    status: str
    order_date: Optional[date] = None
    delivery_start_date: Optional[date] = None
    delivery_due_date: Optional[date] = None
    destination: Optional[str] = None
    lines: list[PurchaseOrderDetailLineRead]
    events: list[TraceEventRead]
