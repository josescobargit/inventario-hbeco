from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import (
    AuditLog,
    Dispatch,
    Incident,
    IncidentStatus,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Product,
    StockMovement,
    StockPosition,
)
from app.schemas.dispatches import DispatchCreate, DispatchLineRead, DispatchRead


class InvoiceNotFoundError(Exception):
    pass


class DispatchQuantityError(Exception):
    pass


class DispatchStockError(Exception):
    def __init__(self, sku: str, requested: int, physical_confirmed: int) -> None:
        self.sku = sku
        self.requested = requested
        self.physical_confirmed = physical_confirmed
        super().__init__(f"{sku}: requested={requested}, physical_confirmed={physical_confirmed}")


def _line_map(invoice: Invoice) -> dict[str, tuple[Product, InvoiceLine]]:
    return {line.product.sku: (line.product, line) for line in invoice.lines}


def _reported_by_sku(db: Session, invoice_id: int) -> dict[str, int]:
    statement = (
        select(Product.sku, Dispatch.dispatched_quantity, Dispatch.missing_quantity)
        .join(Product, Product.id == Dispatch.product_id)
        .where(Dispatch.invoice_id == invoice_id)
    )
    reported: dict[str, int] = defaultdict(int)
    for sku, dispatched, missing in db.execute(statement).all():
        reported[sku] += int(dispatched or 0) + int(missing or 0)
    return dict(reported)


def _remaining_invoice_quantities(db: Session, invoice: Invoice) -> dict[str, int]:
    reported = _reported_by_sku(db, invoice.id)
    remaining: dict[str, int] = {}
    for line in invoice.lines:
        sku = line.product.sku
        remaining[sku] = max(0, int(line.quantity) - reported.get(sku, 0))
    return remaining


def confirm_dispatch(db: Session, dispatch_data: DispatchCreate, actor_user_id: int) -> DispatchRead:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.invoice_number == dispatch_data.invoice_number.strip())
        .with_for_update()
    )
    if invoice is None:
        raise InvoiceNotFoundError(dispatch_data.invoice_number)

    line_map = _line_map(invoice)
    remaining_before = _remaining_invoice_quantities(db, invoice)

    requested_skus = [line.sku.upper().strip() for line in dispatch_data.lines]
    stock_rows = db.execute(
        select(Product, StockPosition)
        .join(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.sku.in_(requested_skus))
        .with_for_update()
    ).all()
    stock_by_sku = {product.sku: (product, stock) for product, stock in stock_rows}

    response_lines: list[DispatchLineRead] = []
    has_missing = False

    for request_line in dispatch_data.lines:
        sku = request_line.sku.upper().strip()
        dispatched_qty = int(request_line.dispatched_quantity)
        missing_qty = int(request_line.missing_quantity)
        total_reported = dispatched_qty + missing_qty

        if total_reported <= 0:
            raise DispatchQuantityError("Cada linea debe tener despachado o faltante mayor a cero.")
        if sku not in line_map:
            raise DispatchQuantityError(f"El SKU {sku} no pertenece a la factura.")
        if total_reported > remaining_before.get(sku, 0):
            raise DispatchQuantityError(f"El reporte supera lo pendiente para {sku}.")

        product, stock = stock_by_sku[sku]
        if dispatched_qty > stock.physical_confirmed:
            raise DispatchStockError(sku, dispatched_qty, stock.physical_confirmed)

        before_physical = stock.physical_confirmed
        before_pending = stock.invoiced_pending_dispatch
        before_blocked = stock.blocked_incident

        stock.physical_confirmed -= dispatched_qty
        stock.invoiced_pending_dispatch = max(0, stock.invoiced_pending_dispatch - total_reported)
        stock.blocked_incident += missing_qty

        line_status = "con_faltante" if missing_qty else "despachado"
        has_missing = has_missing or missing_qty > 0

        dispatch = Dispatch(
            invoice_id=invoice.id,
            product_id=product.id,
            dispatched_quantity=dispatched_qty,
            missing_quantity=missing_qty,
            status=line_status,
            reason=dispatch_data.reason,
            confirmed_by_user_id=actor_user_id,
        )
        db.add(dispatch)
        db.flush()

        if dispatched_qty:
            db.add(
                StockMovement(
                    product_id=product.id,
                    user_id=actor_user_id,
                    movement_type="DESPACHO_BODEGA",
                    quantity=-dispatched_qty,
                    reason=dispatch_data.reason,
                    source_document_type="dispatch",
                    source_document_id=dispatch.id,
                    before_physical=before_physical,
                    after_physical=stock.physical_confirmed,
                )
            )
        if missing_qty:
            db.add(
                Incident(
                    status=IncidentStatus.abierta.value,
                    incident_type="faltante_despacho",
                    product_id=product.id,
                    invoice_id=invoice.id,
                    purchase_order_id=invoice.purchase_order_id,
                    description=(
                        f"Bodega reporto faltante de {missing_qty} unidad(es) para {sku} "
                        f"en factura {invoice.invoice_number}. Motivo: {dispatch_data.reason}"
                    ),
                    created_by_user_id=actor_user_id,
                )
            )

        db.add(
            AuditLog(
                user_id=actor_user_id,
                action="confirm_dispatch",
                entity_type="dispatch",
                entity_id=dispatch.id,
                before_json=(
                    f'{{"sku":"{sku}","physical_confirmed":{before_physical},'
                    f'"invoiced_pending_dispatch":{before_pending},"blocked_incident":{before_blocked}}}'
                ),
                after_json=(
                    f'{{"sku":"{sku}","physical_confirmed":{stock.physical_confirmed},'
                    f'"invoiced_pending_dispatch":{stock.invoiced_pending_dispatch},'
                    f'"blocked_incident":{stock.blocked_incident}}}'
                ),
                reason=dispatch_data.reason,
            )
        )

        response_lines.append(
            DispatchLineRead(
                sku=sku,
                dispatched_quantity=dispatched_qty,
                missing_quantity=missing_qty,
                status=line_status,
            )
        )

    remaining_after = _remaining_invoice_quantities(db, invoice)
    if has_missing:
        invoice.status = InvoiceStatus.con_incidencia.value
    elif any(quantity > 0 for quantity in remaining_after.values()):
        invoice.status = InvoiceStatus.despachada_parcial.value
    else:
        invoice.status = InvoiceStatus.despachada_completa.value

    db.commit()
    return DispatchRead(
        invoice_number=invoice.invoice_number,
        invoice_status=invoice.status,
        lines=response_lines,
    )
