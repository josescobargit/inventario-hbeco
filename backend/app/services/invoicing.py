from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import AuditLog, Invoice, InvoiceLine, Product, StockMovement, StockPosition
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


def _aggregate_lines(invoice: InvoiceCreate) -> dict[str, int]:
    quantities: dict[str, int] = defaultdict(int)
    for line in invoice.lines:
        quantities[line.sku.upper().strip()] += int(line.quantity)
    return dict(quantities)


def register_invoice(db: Session, invoice_data: InvoiceCreate, actor_user_id: int) -> InvoiceRead:
    existing = db.scalar(
        select(Invoice.id).where(Invoice.invoice_number == invoice_data.invoice_number.strip())
    )
    if existing:
        raise InvoiceAlreadyExistsError(invoice_data.invoice_number)

    requested_by_sku = _aggregate_lines(invoice_data)
    skus = sorted(requested_by_sku)

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

    for sku, requested in requested_by_sku.items():
        _, stock = products_by_sku[sku]
        if stock.available_to_invoice < requested:
            raise InsufficientStockError(sku, requested, stock.available_to_invoice)

    invoice = Invoice(
        invoice_number=invoice_data.invoice_number.strip(),
        customer_name=invoice_data.customer_name,
        purchase_order_id=invoice_data.purchase_order_id,
        contifico_source_id=invoice_data.contifico_source_id,
        registered_by_user_id=actor_user_id,
        notes=invoice_data.notes,
    )
    db.add(invoice)
    db.flush()

    response_lines: list[InvoiceLineRead] = []
    for sku, quantity in requested_by_sku.items():
        product, stock = products_by_sku[sku]
        before_pending = stock.invoiced_pending_dispatch
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

    db.commit()
    db.refresh(invoice)
    return InvoiceRead(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        lines=response_lines,
    )
