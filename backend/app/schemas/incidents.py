from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class IncidentRead(BaseModel):
    id: int
    status: str
    incident_type: str
    sku: Optional[str] = None
    product_name: Optional[str] = None
    invoice_number: Optional[str] = None
    customer_name: Optional[str] = None
    purchase_order_reference: Optional[str] = None
    description: str
    created_by: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
