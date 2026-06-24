from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.inventory import (
    AuditLog,
    Dispatch,
    Incident,
    Invoice,
    InvoiceLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Reservation,
    ReservationStatus,
    StockPosition,
    User,
)
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderDetailLineRead,
    PurchaseOrderDetailRead,
    PurchaseOrderFilePreviewRead,
    PurchaseOrderPreviewLineRead,
    PurchaseOrderPreviewRead,
    PurchaseOrderRead,
    TraceEventRead,
)


class PurchaseOrderAlreadyExistsError(Exception):
    pass


class PurchaseOrderNotFoundError(Exception):
    pass


class PurchaseOrderUnknownProductError(Exception):
    def __init__(self, skus: list[str]) -> None:
        self.skus = skus
        super().__init__(", ".join(skus))


class PurchaseOrderReservationError(Exception):
    def __init__(self, sku: str, requested: int, available: int) -> None:
        self.sku = sku
        self.requested = requested
        self.available = available
        super().__init__(sku)


def _aggregate_lines(purchase_order: PurchaseOrderCreate) -> dict[str, tuple[int, str | None]]:
    quantities: dict[str, int] = defaultdict(int)
    descriptions: dict[str, str | None] = {}
    for line in purchase_order.lines:
        sku = line.sku.upper().strip()
        quantities[sku] += int(line.requested_quantity)
        if line.original_description:
            descriptions[sku] = line.original_description.strip()
    return {sku: (quantity, descriptions.get(sku)) for sku, quantity in quantities.items()}


def create_purchase_order(
    db: Session,
    purchase_order_data: PurchaseOrderCreate,
    actor_user_id: int,
) -> PurchaseOrderRead:
    chain_name = purchase_order_data.chain_name.strip().upper()
    order_number = purchase_order_data.order_number.strip().upper()

    existing = db.scalar(
        select(PurchaseOrder.id).where(
            PurchaseOrder.chain_name == chain_name,
            PurchaseOrder.order_number == order_number,
        )
    )
    if existing:
        raise PurchaseOrderAlreadyExistsError(f"{chain_name} {order_number}")

    requested_by_sku = _aggregate_lines(purchase_order_data)
    skus = sorted(requested_by_sku)
    if purchase_order_data.reserve_stock:
        rows = db.execute(
            select(Product, StockPosition)
            .outerjoin(StockPosition, StockPosition.product_id == Product.id)
            .where(Product.sku.in_(skus))
            .order_by(Product.sku)
            .with_for_update()
        ).all()
        products_by_sku = {product.sku: (product, stock) for product, stock in rows}
    else:
        products = db.execute(
            select(Product).where(Product.sku.in_(skus)).order_by(Product.sku)
        ).scalars().all()
        products_by_sku = {product.sku: (product, None) for product in products}
    missing_skus = [sku for sku in skus if sku not in products_by_sku]
    if missing_skus:
        raise PurchaseOrderUnknownProductError(missing_skus)

    if purchase_order_data.reserve_stock:
        for sku, (quantity, _) in requested_by_sku.items():
            _, stock = products_by_sku[sku]
            available = int(stock.available_to_invoice) if stock else 0
            if available < quantity:
                raise PurchaseOrderReservationError(sku, quantity, available)

    purchase_order = PurchaseOrder(
        chain_name=chain_name,
        order_number=order_number,
        external_reference=purchase_order_data.external_reference,
        order_date=purchase_order_data.order_date,
        delivery_start_date=purchase_order_data.delivery_start_date,
        delivery_due_date=purchase_order_data.delivery_due_date,
        destination=purchase_order_data.destination,
        notes=purchase_order_data.notes,
        source_filename=None,
        created_by_user_id=actor_user_id,
    )
    db.add(purchase_order)
    db.flush()

    total_units = 0
    for sku, (quantity, description) in requested_by_sku.items():
        product, stock = products_by_sku[sku]
        total_units += quantity
        db.add(
            PurchaseOrderLine(
                purchase_order_id=purchase_order.id,
                product_id=product.id,
                requested_quantity=quantity,
                original_description=description,
            )
        )
        if purchase_order_data.reserve_stock:
            stock.reserved += quantity
            db.add(
                Reservation(
                    product_id=product.id,
                    purchase_order_id=purchase_order.id,
                    customer_name=chain_name,
                    quantity=quantity,
                    original_quantity=quantity,
                    reason=f"Reserva confirmada al registrar OC {order_number}",
                    created_by_user_id=actor_user_id,
                )
            )

    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="create_purchase_order_and_reserve" if purchase_order_data.reserve_stock else "create_purchase_order",
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            before_json=None,
            after_json=(
                f'{{"chain_name":"{chain_name}","order_number":"{order_number}",'
                f'"line_count":{len(requested_by_sku)},"total_units":{total_units},'
                f'"reserved":{str(purchase_order_data.reserve_stock).lower()}}}'
            ),
            reason=purchase_order_data.reason,
        )
    )
    db.commit()
    db.refresh(purchase_order)

    creator_name = db.scalar(select(User.full_name).where(User.id == actor_user_id))
    return PurchaseOrderRead(
        id=purchase_order.id,
        chain_name=chain_name,
        order_number=order_number,
        status=purchase_order.status,
        total_units=total_units,
        line_count=len(requested_by_sku),
        order_date=purchase_order.order_date,
        delivery_due_date=purchase_order.delivery_due_date,
        destination=purchase_order.destination,
        created_by=creator_name,
        created_at=purchase_order.created_at,
    )


def list_purchase_orders(db: Session, limit: int = 100) -> list[PurchaseOrderRead]:
    creator = aliased(User)
    line_totals = (
        select(
            PurchaseOrderLine.purchase_order_id,
            func.sum(PurchaseOrderLine.requested_quantity).label("total_units"),
            func.count(PurchaseOrderLine.id).label("line_count"),
        )
        .group_by(PurchaseOrderLine.purchase_order_id)
        .subquery()
    )
    rows = db.execute(
        select(
            PurchaseOrder.id,
            PurchaseOrder.chain_name,
            PurchaseOrder.order_number,
            PurchaseOrder.status,
            PurchaseOrder.order_date,
            PurchaseOrder.delivery_due_date,
            PurchaseOrder.destination,
            PurchaseOrder.created_at,
            creator.full_name.label("created_by"),
            func.coalesce(line_totals.c.total_units, 0).label("total_units"),
            func.coalesce(line_totals.c.line_count, 0).label("line_count"),
        )
        .outerjoin(line_totals, line_totals.c.purchase_order_id == PurchaseOrder.id)
        .outerjoin(creator, creator.id == PurchaseOrder.created_by_user_id)
        .order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
        .limit(limit)
    ).mappings()
    return [PurchaseOrderRead(**row) for row in rows]


def build_purchase_order_file_preview(
    db: Session,
    source_filename: str,
    parsed_orders: list[dict[str, object]],
) -> PurchaseOrderFilePreviewRead:
    sku_hints = {
        str(line.get("sku_hint") or "").upper()
        for order in parsed_orders
        for line in order["lines"]
        if line.get("sku_hint")
    }
    barcodes = {
        str(line.get("barcode") or "")
        for order in parsed_orders
        for line in order["lines"]
        if line.get("barcode")
    }
    products = db.execute(
        select(Product, StockPosition)
        .outerjoin(StockPosition, StockPosition.product_id == Product.id)
        .where((Product.sku.in_(sku_hints)) | (Product.barcode.in_(barcodes)))
    ).all()
    by_sku = {product.sku: (product, stock) for product, stock in products}
    by_barcode = {product.barcode: (product, stock) for product, stock in products if product.barcode}

    previews = []
    for parsed_order in parsed_orders:
        preview_lines = []
        total_units = 0
        can_invoice_units = 0
        for parsed_line in parsed_order["lines"]:
            sku_hint = str(parsed_line.get("sku_hint") or "").upper()
            barcode = str(parsed_line.get("barcode") or "")
            match = by_sku.get(sku_hint) or by_barcode.get(barcode)
            if not match:
                requested = int(parsed_line["requested_quantity"])
                total_units += requested
                preview_lines.append(
                    PurchaseOrderPreviewLineRead(
                        sku=sku_hint or None,
                        product_name=None,
                        requested_quantity=requested,
                        quantity_cases=parsed_line.get("quantity_cases"),
                        units_per_case=int(parsed_line.get("units_per_case") or 1),
                        available_to_invoice=0,
                        can_invoice_quantity=0,
                        missing_quantity=requested,
                        availability_status="no_reconocido",
                        match_status="no_reconocido",
                        original_description=str(parsed_line.get("original_description") or "") or None,
                    )
                )
                continue
            product, stock = match
            requested = int(parsed_line["requested_quantity"])
            available = int(stock.available_to_invoice) if stock else 0
            can_invoice = min(requested, available)
            missing = max(0, requested - available)
            status = "completa" if missing == 0 else ("parcial" if can_invoice else "sin_stock")
            total_units += requested
            can_invoice_units += can_invoice
            preview_lines.append(
                PurchaseOrderPreviewLineRead(
                    sku=product.sku,
                    product_name=product.name,
                    requested_quantity=requested,
                    quantity_cases=parsed_line.get("quantity_cases"),
                    units_per_case=int(parsed_line.get("units_per_case") or product.units_per_case),
                    available_to_invoice=available,
                    can_invoice_quantity=can_invoice,
                    missing_quantity=missing,
                    availability_status=status,
                    match_status="reconocido",
                    original_description=str(parsed_line.get("original_description") or "") or None,
                )
            )
        previews.append(
            PurchaseOrderPreviewRead(
                chain_name=str(parsed_order["chain_name"]),
                order_number=str(parsed_order["order_number"]),
                order_number_source=str(parsed_order.get("order_number_source") or "missing"),
                external_reference=parsed_order.get("external_reference"),
                order_date=parsed_order.get("order_date"),
                delivery_start_date=parsed_order.get("delivery_start_date"),
                delivery_due_date=parsed_order.get("delivery_due_date"),
                destination=parsed_order.get("destination"),
                total_units=total_units,
                line_count=len(preview_lines),
                can_invoice_units=can_invoice_units,
                missing_units=max(0, total_units - can_invoice_units),
                lines=preview_lines,
            )
        )

    return PurchaseOrderFilePreviewRead(
        source_filename=source_filename,
        order_count=len(previews),
        orders=previews,
    )


def get_purchase_order_detail(db: Session, purchase_order_id: int) -> PurchaseOrderDetailRead:
    purchase_order = db.get(PurchaseOrder, purchase_order_id)
    if not purchase_order:
        raise PurchaseOrderNotFoundError(purchase_order_id)

    line_rows = db.execute(
        select(PurchaseOrderLine.product_id, Product.sku, Product.name, PurchaseOrderLine.requested_quantity)
        .join(Product, Product.id == PurchaseOrderLine.product_id)
        .where(PurchaseOrderLine.purchase_order_id == purchase_order_id)
        .order_by(Product.sku)
    ).all()
    reserved = dict(
        db.execute(
            select(Reservation.product_id, func.sum(Reservation.quantity))
            .where(
                Reservation.purchase_order_id == purchase_order_id,
                Reservation.status == ReservationStatus.activa.value,
            )
            .group_by(Reservation.product_id)
        ).all()
    )
    invoiced = dict(
        db.execute(
            select(InvoiceLine.product_id, func.sum(InvoiceLine.quantity))
            .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
            .where(Invoice.purchase_order_id == purchase_order_id)
            .group_by(InvoiceLine.product_id)
        ).all()
    )
    dispatch_rows = db.execute(
        select(
            Dispatch.product_id,
            func.sum(Dispatch.dispatched_quantity),
            func.sum(Dispatch.missing_quantity),
        )
        .join(Invoice, Invoice.id == Dispatch.invoice_id)
        .where(Invoice.purchase_order_id == purchase_order_id)
        .group_by(Dispatch.product_id)
    ).all()
    dispatched = {product_id: int(quantity or 0) for product_id, quantity, _ in dispatch_rows}
    dispatch_missing = {product_id: int(quantity or 0) for product_id, _, quantity in dispatch_rows}

    detail_lines = []
    for product_id, sku, name, requested in line_rows:
        invoiced_quantity = int(invoiced.get(product_id, 0) or 0)
        detail_lines.append(
            PurchaseOrderDetailLineRead(
                sku=sku,
                product_name=name,
                requested_quantity=int(requested),
                reserved_quantity=int(reserved.get(product_id, 0) or 0),
                invoiced_quantity=invoiced_quantity,
                dispatched_quantity=dispatched.get(product_id, 0),
                missing_dispatch_quantity=dispatch_missing.get(product_id, 0),
                remaining_to_invoice=max(0, int(requested) - invoiced_quantity),
            )
        )

    events = []
    creator_name = db.scalar(select(User.full_name).where(User.id == purchase_order.created_by_user_id))
    creation_reason = db.scalar(
        select(AuditLog.reason)
        .where(
            AuditLog.entity_type == "purchase_order",
            AuditLog.entity_id == purchase_order.id,
        )
        .order_by(AuditLog.created_at, AuditLog.id)
        .limit(1)
    )
    events.append(
        TraceEventRead(
            event_type="purchase_order",
            title="OC registrada",
            detail=creation_reason or f"{purchase_order.chain_name} / {purchase_order.order_number}",
            occurred_at=purchase_order.created_at,
            user_name=creator_name,
        )
    )
    reservation_creator = aliased(User)
    reservation_releaser = aliased(User)
    reservation_events = db.execute(
        select(
            Reservation.id,
            Product.sku,
            Reservation.quantity,
            Reservation.original_quantity,
            Reservation.status,
            Reservation.reason,
            Reservation.created_at,
            reservation_creator.full_name,
            Reservation.release_reason,
            Reservation.released_at,
            reservation_releaser.full_name,
        )
        .join(Product, Product.id == Reservation.product_id)
        .outerjoin(reservation_creator, reservation_creator.id == Reservation.created_by_user_id)
        .outerjoin(reservation_releaser, reservation_releaser.id == Reservation.released_by_user_id)
        .where(Reservation.purchase_order_id == purchase_order_id)
    ).all()
    for (
        reservation_id,
        sku,
        quantity,
        original_quantity,
        reservation_status,
        reason,
        created_at,
        created_by,
        release_reason,
        released_at,
        released_by,
    ) in reservation_events:
        events.append(
            TraceEventRead(
                event_type="reservation",
                title=f"Reserva #{reservation_id}: {sku}",
                detail=f"{int(original_quantity or quantity)} unidades. {reason}",
                occurred_at=created_at,
                user_name=created_by,
            )
        )
        if released_at:
            events.append(
                TraceEventRead(
                    event_type="reservation_released",
                    title=f"Reserva #{reservation_id}: {reservation_status}",
                    detail=release_reason or "Reserva liberada o convertida en factura.",
                    occurred_at=released_at,
                    user_name=released_by,
                )
            )
    registrar = aliased(User)
    invoice_events = db.execute(
        select(
            Invoice.id,
            Invoice.invoice_number,
            Invoice.status,
            func.sum(InvoiceLine.quantity),
            Invoice.notes,
            Invoice.registered_at,
            registrar.full_name,
        )
        .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
        .outerjoin(registrar, registrar.id == Invoice.registered_by_user_id)
        .where(Invoice.purchase_order_id == purchase_order_id)
        .group_by(
            Invoice.id,
            Invoice.invoice_number,
            Invoice.status,
            Invoice.notes,
            Invoice.registered_at,
            registrar.full_name,
        )
    ).all()
    for invoice_id, number, status, total_units, notes, occurred_at, user_name in invoice_events:
        invoice_reason = db.scalar(
            select(AuditLog.reason)
            .where(
                AuditLog.entity_type == "invoice",
                AuditLog.entity_id == invoice_id,
            )
            .order_by(AuditLog.created_at, AuditLog.id)
            .limit(1)
        )
        events.append(
            TraceEventRead(
                event_type="invoice",
                title=f"Factura {number}",
                detail=(
                    f"{int(total_units or 0)} unidades. Estado: {status}. "
                    f"Motivo: {invoice_reason or notes or 'No indicado'}."
                ),
                occurred_at=occurred_at,
                user_name=user_name,
            )
        )
    confirmer = aliased(User)
    dispatch_events = db.execute(
        select(
            Invoice.invoice_number,
            func.sum(Dispatch.dispatched_quantity),
            func.sum(Dispatch.missing_quantity),
            func.min(Dispatch.reason),
            Dispatch.confirmed_at,
            confirmer.full_name,
        )
        .join(Invoice, Invoice.id == Dispatch.invoice_id)
        .outerjoin(confirmer, confirmer.id == Dispatch.confirmed_by_user_id)
        .where(Invoice.purchase_order_id == purchase_order_id)
        .group_by(Invoice.invoice_number, Dispatch.confirmed_at, confirmer.full_name)
    ).all()
    for number, delivered, missing, reason, occurred_at, user_name in dispatch_events:
        events.append(
            TraceEventRead(
                event_type="dispatch",
                title=f"Despacho de factura {number}",
                detail=(
                    f"Entregado: {int(delivered or 0)}. Faltante: {int(missing or 0)}. "
                    f"Motivo: {reason or 'No indicado'}."
                ),
                occurred_at=occurred_at,
                user_name=user_name,
            )
        )
    incident_events = db.execute(
        select(
            Incident.incident_type,
            Incident.status,
            Incident.description,
            Incident.resolution_notes,
            Incident.created_at,
            Incident.resolved_at,
        )
        .where(Incident.purchase_order_id == purchase_order_id)
    ).all()
    for incident_type, status, description, resolution_notes, occurred_at, resolved_at in incident_events:
        events.append(
            TraceEventRead(
                event_type="incident",
                title=f"Incidencia: {incident_type}",
                detail=description,
                occurred_at=occurred_at,
            )
        )
        if resolved_at:
            events.append(
                TraceEventRead(
                    event_type="incident_resolved",
                    title=f"Incidencia resuelta: {incident_type}",
                    detail=f"Estado: {status}. {resolution_notes or 'Sin notas de resolucion.'}",
                    occurred_at=resolved_at,
                )
            )
    events.sort(key=lambda event: event.occurred_at)

    return PurchaseOrderDetailRead(
        id=purchase_order.id,
        chain_name=purchase_order.chain_name,
        order_number=purchase_order.order_number,
        external_reference=purchase_order.external_reference,
        status=purchase_order.status,
        order_date=purchase_order.order_date,
        delivery_start_date=purchase_order.delivery_start_date,
        delivery_due_date=purchase_order.delivery_due_date,
        destination=purchase_order.destination,
        lines=detail_lines,
        events=events,
    )
