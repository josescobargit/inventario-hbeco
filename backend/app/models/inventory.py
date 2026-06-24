from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# PostgreSQL keeps the BIGINT identifiers from the original schema. SQLite only
# autoincrements a primary key declared exactly as INTEGER, so tests use that
# dialect-specific representation of the same logical type.
BigInteger = BigInteger().with_variant(Integer, "sqlite")


class UserRole(str, Enum):
    principal = "principal"
    administracion = "administracion"
    ventas = "ventas"
    bodega = "bodega"
    consulta = "consulta"


class InvoiceStatus(str, Enum):
    facturada = "facturada"
    despachada_parcial = "despachada_parcial"
    despachada_completa = "despachada_completa"
    anulada = "anulada"
    con_incidencia = "con_incidencia"


class PurchaseOrderStatus(str, Enum):
    recibida = "recibida"
    leida = "leida"
    parcialmente_facturada = "parcialmente_facturada"
    facturada_completa = "facturada_completa"
    cerrada = "cerrada"
    con_incidencia = "con_incidencia"


class ReservationStatus(str, Enum):
    activa = "activa"
    eliminada = "eliminada"
    convertida_en_factura = "convertida_en_factura"


class IncidentStatus(str, Enum):
    abierta = "abierta"
    en_revision = "en_revision"
    resuelta = "resuelta"
    cerrada_sin_ajuste = "cerrada_sin_ajuste"


class ApprovalStatus(str, Enum):
    solicitada = "solicitada"
    aprobada = "aprobada"
    rechazada = "rechazada"
    aplicada = "aplicada"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('principal', 'administracion', 'ventas', 'bodega', 'consulta')",
            name="ck_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(40), default=UserRole.consulta.value, server_default=UserRole.consulta.value
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    must_change_password: Mapped[bool] = mapped_column(default=True, server_default=true())
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sku: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(120))
    barcode: Mapped[Optional[str]] = mapped_column(String(80))
    contifico_aux_code: Mapped[Optional[str]] = mapped_column(String(80))
    cost: Mapped[float] = mapped_column(Numeric(12, 4), default=0, server_default="0")
    units_per_case: Mapped[int] = mapped_column(Integer, default=12, server_default="12")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stock_position: Mapped["StockPosition"] = relationship(back_populates="product", uselist=False)


class StockPosition(Base):
    __tablename__ = "stock_positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), unique=True)
    physical_confirmed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reserved: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    invoiced_pending_dispatch: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    blocked_incident: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    incoming_expected: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_to_invoice: Mapped[int] = mapped_column(
        Integer,
        Computed(
            "GREATEST(0, physical_confirmed - reserved - invoiced_pending_dispatch - blocked_incident)",
            persisted=True,
        ),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    product: Mapped[Product] = relationship(back_populates="stock_position")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    movement_type: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    source_document_type: Mapped[Optional[str]] = mapped_column(String(80))
    source_document_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    before_physical: Mapped[Optional[int]] = mapped_column(Integer)
    after_physical: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("chain_name", "order_number", name="uq_chain_order_number"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chain_name: Mapped[str] = mapped_column(String(120), index=True)
    order_number: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(
        String(60),
        default=PurchaseOrderStatus.recibida.value,
        server_default=PurchaseOrderStatus.recibida.value,
    )
    # Legacy column kept for schema compatibility. New OCs never persist uploaded files.
    source_filename: Mapped[Optional[str]] = mapped_column(String(255))
    external_reference: Mapped[Optional[str]] = mapped_column(String(120))
    order_date: Mapped[Optional[date]] = mapped_column(Date)
    delivery_start_date: Mapped[Optional[date]] = mapped_column(Date)
    delivery_due_date: Mapped[Optional[date]] = mapped_column(Date)
    destination: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id"), index=True
    )
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"))
    requested_quantity: Mapped[int] = mapped_column(Integer)
    original_description: Mapped[Optional[str]] = mapped_column(Text)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"), index=True)
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id")
    )
    customer_name: Mapped[Optional[str]] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer)
    original_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(60),
        default=ReservationStatus.activa.value,
        server_default=ReservationStatus.activa.value,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    released_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    release_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship()


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(120), unique=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255))
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id")
    )
    status: Mapped[str] = mapped_column(
        String(60),
        default=InvoiceStatus.facturada.value,
        server_default=InvoiceStatus.facturada.value,
    )
    contifico_source_id: Mapped[Optional[str]] = mapped_column(String(120))
    authorization_number: Mapped[Optional[str]] = mapped_column(String(80))
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    registered_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text)

    lines: Mapped[list["InvoiceLine"]] = relationship(back_populates="invoice")


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("invoices.id"), index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()


class Dispatch(Base):
    __tablename__ = "dispatches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("invoices.id"), index=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id"))
    dispatched_quantity: Mapped[int] = mapped_column(Integer)
    missing_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(60))
    reason: Mapped[str] = mapped_column(Text)
    confirmed_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(
        String(60),
        default=IncidentStatus.abierta.value,
        server_default=IncidentStatus.abierta.value,
        index=True,
    )
    incident_type: Mapped[str] = mapped_column(String(80))
    product_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("products.id"))
    invoice_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("invoices.id"))
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("purchase_orders.id")
    )
    description: Mapped[str] = mapped_column(Text)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(
        String(60),
        default=ApprovalStatus.solicitada.value,
        server_default=ApprovalStatus.solicitada.value,
    )
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    request_type: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(120))
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    before_json: Mapped[Optional[str]] = mapped_column(Text)
    after_json: Mapped[Optional[str]] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
