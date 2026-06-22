from pydantic import BaseModel, Field


class DispatchLineCreate(BaseModel):
    sku: str
    dispatched_quantity: int = Field(ge=0)
    missing_quantity: int = Field(ge=0)


class DispatchCreate(BaseModel):
    invoice_number: str
    reason: str = Field(min_length=3)
    lines: list[DispatchLineCreate] = Field(min_length=1)


class DispatchLineRead(BaseModel):
    sku: str
    dispatched_quantity: int
    missing_quantity: int
    status: str


class DispatchRead(BaseModel):
    invoice_number: str
    invoice_status: str
    lines: list[DispatchLineRead]
