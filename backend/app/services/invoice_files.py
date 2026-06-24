from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import (
    Invoice,
    InvoiceLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Reservation,
    ReservationStatus,
    StockPosition,
)
from app.schemas.invoices import InvoiceFilePreviewLineRead, InvoiceFilePreviewRead


class InvoiceFileUnknownProductError(Exception):
    def __init__(self, skus: list[str]) -> None:
        self.skus = skus
        super().__init__(", ".join(skus))


def build_invoice_file_preview(db: Session, parsed: dict[str, object]) -> InvoiceFilePreviewRead:
    parsed_lines = list(parsed["lines"])
    skus = sorted({str(line["sku"]).upper() for line in parsed_lines})
    product_rows = db.execute(
        select(Product, StockPosition)
        .outerjoin(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.sku.in_(skus))
    ).all()
    products = {product.sku: (product, stock) for product, stock in product_rows}
    missing_skus = [sku for sku in skus if sku not in products]
    if missing_skus:
        raise InvoiceFileUnknownProductError(missing_skus)

    order_number = parsed.get("purchase_order_number")
    purchase_order = None
    if order_number:
        purchase_order = db.scalar(
            select(PurchaseOrder).where(PurchaseOrder.order_number == str(order_number).strip())
        )

    warnings = []
    if not order_number:
        warnings.append("La factura no indica un numero de OC.")
    elif not purchase_order:
        warnings.append(f"La OC {order_number} todavia no esta registrada en el sistema.")

    ordered: dict[int, int] = {}
    previously_invoiced: dict[int, int] = {}
    own_reserved: dict[int, int] = {}
    if purchase_order:
        ordered = dict(
            db.execute(
                select(PurchaseOrderLine.product_id, PurchaseOrderLine.requested_quantity).where(
                    PurchaseOrderLine.purchase_order_id == purchase_order.id
                )
            ).all()
        )
        previously_invoiced = dict(
            db.execute(
                select(InvoiceLine.product_id, func.sum(InvoiceLine.quantity))
                .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
                .where(Invoice.purchase_order_id == purchase_order.id)
                .group_by(InvoiceLine.product_id)
            ).all()
        )
        own_reserved = dict(
            db.execute(
                select(Reservation.product_id, func.sum(Reservation.quantity))
                .where(
                    Reservation.purchase_order_id == purchase_order.id,
                    Reservation.status == ReservationStatus.activa.value,
                )
                .group_by(Reservation.product_id)
            ).all()
        )

    lines = []
    can_register = purchase_order is not None
    for parsed_line in parsed_lines:
        sku = str(parsed_line["sku"]).upper()
        quantity = int(parsed_line["quantity"])
        product, stock = products[sku]
        ordered_quantity = int(ordered.get(product.id, 0) or 0)
        previous_quantity = int(previously_invoiced.get(product.id, 0) or 0)
        remaining_before = max(0, ordered_quantity - previous_quantity)
        available = (int(stock.available_to_invoice) if stock else 0) + int(
            own_reserved.get(product.id, 0) or 0
        )
        line_can_register = (
            purchase_order is not None
            and ordered_quantity > 0
            and quantity <= remaining_before
            and quantity <= available
        )
        can_register = can_register and line_can_register
        if purchase_order and ordered_quantity == 0:
            warnings.append(f"{sku} no pertenece a la OC {purchase_order.order_number}.")
        elif purchase_order and quantity > remaining_before:
            warnings.append(
                f"{sku}: la factura tiene {quantity}, pero quedan {remaining_before} unidades en la OC."
            )
        if quantity > available:
            warnings.append(f"{sku}: la factura tiene {quantity}, pero solo hay {available} disponibles.")
        lines.append(
            InvoiceFilePreviewLineRead(
                sku=sku,
                product_name=product.name,
                quantity=quantity,
                ordered_quantity=ordered_quantity,
                previously_invoiced_quantity=previous_quantity,
                remaining_before_invoice=remaining_before,
                remaining_after_invoice=max(0, remaining_before - quantity),
                available_for_this_order=available,
                can_register=line_can_register,
            )
        )

    return InvoiceFilePreviewRead(
        invoice_number=str(parsed["invoice_number"]),
        authorization_number=parsed.get("authorization_number"),
        issued_at=parsed.get("issued_at"),
        customer_name=parsed.get("customer_name"),
        purchase_order_number=str(order_number) if order_number else None,
        purchase_order_id=purchase_order.id if purchase_order else None,
        purchase_order_reference=(
            f"{purchase_order.chain_name} / {purchase_order.order_number}" if purchase_order else None
        ),
        total_amount=parsed.get("total_amount"),
        source_filename=str(parsed["source_filename"]),
        can_register=can_register,
        warnings=warnings,
        lines=lines,
    )
