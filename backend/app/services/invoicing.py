from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import (
    AuditLog,
    Invoice,
    InvoiceLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    Reservation,
    ReservationStatus,
    StockMovement,
    StockPosition,
)
from app.schemas.invoices import InvoiceCreate, InvoiceLineRead, InvoiceRead


class InvoiceAlreadyExistsError(Exception):
    pass


class UnknownProductError(Exception):
    def __init__(self, skus: list[str]) -> None:
        self.skus = skus
        super().__init__(", ".join(skus))


class InsufficientStockError(Exception):
    def __init__(self, sku: str, requested: int, available: int) -> None:
        self.sku = sku
        self.requested = requested
        self.available = available
        super().__init__(f"{sku}: requested={requested}, available={available}")


class InvoicePurchaseOrderError(Exception):
    pass


class InvoiceExceedsPurchaseOrderError(Exception):
    def __init__(self, sku: str, requested: int, remaining: int) -> None:
        self.sku = sku
        self.requested = requested
        self.remaining = remaining
        super().__init__(sku)


def _aggregate_lines(invoice: InvoiceCreate) -> dict[str, int]:
    quantities: dict[str, int] = defaultdict(int)
    for line in invoice.lines:
        quantities[line.sku.upper().strip()] += int(line.quantity)
    return dict(quantities)


def register_invoice(
    db: Session,
    invoice_data: InvoiceCreate,
    actor_user_id: int,
    *,
    commit: bool = True,
) -> InvoiceRead:
    existing = db.scalar(
        select(Invoice.id).where(Invoice.invoice_number == invoice_data.invoice_number.strip())
    )
    if existing:
        raise InvoiceAlreadyExistsError(invoice_data.invoice_number)

    requested_by_sku = _aggregate_lines(invoice_data)
    skus = sorted(requested_by_sku)

    purchase_order = db.get(PurchaseOrder, invoice_data.purchase_order_id)
    if not purchase_order:
        raise InvoicePurchaseOrderError("La OC indicada no existe.")

    statement = (
        select(Product, StockPosition)
        .join(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.sku.in_(skus))
        .order_by(Product.sku)
        .with_for_update()
    )
    rows = db.execute(statement).all()
    products_by_sku = {product.sku: (product, stock) for product, stock in rows}

    missing_skus = [sku for sku in skus if sku not in products_by_sku]
    if missing_skus:
        raise UnknownProductError(missing_skus)

    ordered_by_product = dict(
        db.execute(
            select(PurchaseOrderLine.product_id, PurchaseOrderLine.requested_quantity).where(
                PurchaseOrderLine.purchase_order_id == purchase_order.id
            )
        ).all()
    )
    invoiced_by_product = dict(
        db.execute(
            select(InvoiceLine.product_id, func.sum(InvoiceLine.quantity))
            .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
            .where(Invoice.purchase_order_id == purchase_order.id)
            .group_by(InvoiceLine.product_id)
        ).all()
    )
    active_reservations = db.execute(
        select(Reservation)
        .where(
            Reservation.purchase_order_id == purchase_order.id,
            Reservation.status == ReservationStatus.activa.value,
        )
        .order_by(Reservation.created_at, Reservation.id)
        .with_for_update()
    ).scalars().all()
    reservations_by_product: dict[int, list[Reservation]] = defaultdict(list)
    for reservation in active_reservations:
        reservations_by_product[reservation.product_id].append(reservation)

    for sku, requested in requested_by_sku.items():
        product, stock = products_by_sku[sku]
        ordered = int(ordered_by_product.get(product.id, 0) or 0)
        previous = int(invoiced_by_product.get(product.id, 0) or 0)
        remaining = max(0, ordered - previous)
        if requested > remaining:
            raise InvoiceExceedsPurchaseOrderError(sku, requested, remaining)
        own_reserved = sum(item.quantity for item in reservations_by_product.get(product.id, []))
        effective_available = int(stock.available_to_invoice) + own_reserved
        if effective_available < requested:
            raise InsufficientStockError(sku, requested, effective_available)

    invoice = Invoice(
        invoice_number=invoice_data.invoice_number.strip(),
        customer_name=invoice_data.customer_name,
        purchase_order_id=invoice_data.purchase_order_id,
        contifico_source_id=invoice_data.contifico_source_id,
        authorization_number=invoice_data.authorization_number,
        issued_at=invoice_data.issued_at,
        total_amount=invoice_data.total_amount,
        registered_by_user_id=actor_user_id,
        notes=invoice_data.notes,
    )
    db.add(invoice)
    db.flush()

    response_lines: list[InvoiceLineRead] = []
    for sku, quantity in requested_by_sku.items():
        product, stock = products_by_sku[sku]
        before_pending = stock.invoiced_pending_dispatch
        quantity_to_convert = quantity
        for reservation in reservations_by_product.get(product.id, []):
            if quantity_to_convert <= 0:
                break
            converted = min(quantity_to_convert, reservation.quantity)
            reservation.quantity -= converted
            stock.reserved -= converted
            quantity_to_convert -= converted
            if reservation.quantity == 0:
                reservation.status = ReservationStatus.convertida_en_factura.value
                reservation.released_by_user_id = actor_user_id
                reservation.released_at = datetime.now(timezone.utc)
                reservation.release_reason = f"Convertida en factura {invoice.invoice_number}"
        stock.invoiced_pending_dispatch += quantity

        db.add(
            InvoiceLine(
                invoice_id=invoice.id,
                product_id=product.id,
                quantity=quantity,
            )
        )
        db.add(
            StockMovement(
                product_id=product.id,
                user_id=actor_user_id,
                movement_type="FACTURA_CONTIFICO",
                quantity=-quantity,
                reason=invoice_data.reason,
                source_document_type="invoice",
                source_document_id=invoice.id,
                before_physical=stock.physical_confirmed,
                after_physical=stock.physical_confirmed,
            )
        )
        db.add(
            AuditLog(
                user_id=actor_user_id,
                action="register_invoice",
                entity_type="invoice",
                entity_id=invoice.id,
                before_json=f'{{"sku":"{sku}","invoiced_pending_dispatch":{before_pending}}}',
                after_json=f'{{"sku":"{sku}","invoiced_pending_dispatch":{stock.invoiced_pending_dispatch}}}',
                reason=invoice_data.reason,
            )
        )
        response_lines.append(InvoiceLineRead(sku=sku, quantity=quantity))

    total_ordered = sum(int(value or 0) for value in ordered_by_product.values())
    total_previously_invoiced = sum(int(value or 0) for value in invoiced_by_product.values())
    total_after_invoice = total_previously_invoiced + sum(requested_by_sku.values())
    purchase_order.status = (
        PurchaseOrderStatus.facturada_completa.value
        if total_after_invoice >= total_ordered
        else PurchaseOrderStatus.parcialmente_facturada.value
    )

    if commit:
        db.commit()
        db.refresh(invoice)
    else:
        db.flush()
    return InvoiceRead(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        lines=response_lines,
    )
