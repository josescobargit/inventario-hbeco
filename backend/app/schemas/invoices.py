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
    purchase_order_id: int = Field(gt=0)
    contifico_source_id: Optional[str] = None
    authorization_number: Optional[str] = None
    issued_at: Optional[datetime] = None
    total_amount: Optional[float] = None
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
    purchase_order_id: Optional[int] = None
    purchase_order_reference: Optional[str] = None
    status: str
    total_units: int
    dispatched_units: int
    missing_units: int
    pending_units: int
    registered_by: Optional[str] = None
    registered_at: datetime


class BulkInvoicePreviewRequest(BaseModel):
    raw_text: str = Field(min_length=3)


class BulkInvoicePreviewLineRead(BaseModel):
    sku: str
    product_name: str
    quantity: int
    raw_description: str


class BulkInvoicePurchaseOrderCandidateRead(BaseModel):
    id: int
    order_number: str
    chain_name: str


class BulkInvoicePreviewItemRead(BaseModel):
    block_number: int
    total_units: int
    lines: list[BulkInvoicePreviewLineRead]
    suggested_invoice_number: Optional[str] = None
    suggested_purchase_order_id: Optional[int] = None
    purchase_order_candidates: list[BulkInvoicePurchaseOrderCandidateRead] = Field(
        default_factory=list
    )


class BulkInvoicePreviewRead(BaseModel):
    invoice_count: int
    lines_total: int
    invoices: list[BulkInvoicePreviewItemRead]


class BulkInvoiceCreate(BaseModel):
    invoices: list[InvoiceCreate] = Field(min_length=1)


class InvoiceFilePreviewLineRead(BaseModel):
    sku: str
    product_name: str
    quantity: int
    ordered_quantity: int
    previously_invoiced_quantity: int
    remaining_before_invoice: int
    remaining_after_invoice: int
    available_for_this_order: int
    can_register: bool


class InvoiceFilePreviewRead(BaseModel):
    invoice_number: str
    authorization_number: Optional[str] = None
    issued_at: Optional[datetime] = None
    customer_name: Optional[str] = None
    purchase_order_number: Optional[str] = None
    purchase_order_id: Optional[int] = None
    purchase_order_reference: Optional[str] = None
    total_amount: Optional[float] = None
    source_filename: str
    can_register: bool
    warnings: list[str]
    lines: list[InvoiceFilePreviewLineRead]
