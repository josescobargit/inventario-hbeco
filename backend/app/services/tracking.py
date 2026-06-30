from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.inventory import (
    Dispatch,
    Incident,
    Invoice,
    InvoiceLine,
    Product,
    PurchaseOrder,
    Reservation,
    User,
)
from app.schemas.incidents import IncidentRead
from app.schemas.dispatches import PendingDispatchRead
from app.schemas.invoices import InvoiceSummaryRead
from app.schemas.reservations import ReservationSummaryRead


def list_reservation_summaries(db: Session, limit: int = 100) -> list[ReservationSummaryRead]:
    creator = aliased(User)
    rows = db.execute(
        select(
            Reservation.id,
            Product.sku,
            Product.name.label("product_name"),
            Reservation.quantity,
            Reservation.status,
            Reservation.customer_name,
            Reservation.reason,
            Reservation.created_at,
            Reservation.released_at,
            creator.full_name.label("created_by"),
        )
        .join(Product, Product.id == Reservation.product_id)
        .outerjoin(creator, creator.id == Reservation.created_by_user_id)
        .order_by(Reservation.created_at.desc(), Reservation.id.desc())
        .limit(limit)
    ).mappings()
    return [ReservationSummaryRead(**row) for row in rows]


def list_invoice_summaries(db: Session, limit: int = 100) -> list[InvoiceSummaryRead]:
    line_totals = (
        select(InvoiceLine.invoice_id, func.sum(InvoiceLine.quantity).label("total_units"))
        .group_by(InvoiceLine.invoice_id)
        .subquery()
    )
    dispatch_totals = (
        select(
            Dispatch.invoice_id,
            func.sum(Dispatch.dispatched_quantity).label("dispatched_units"),
            func.sum(Dispatch.missing_quantity).label("missing_units"),
        )
        .group_by(Dispatch.invoice_id)
        .subquery()
    )
    registrar = aliased(User)
    rows = db.execute(
        select(
            Invoice.id,
            Invoice.invoice_number,
            Invoice.customer_name,
            Invoice.purchase_order_id,
            (PurchaseOrder.chain_name + " / " + PurchaseOrder.order_number).label(
                "purchase_order_reference"
            ),
            Invoice.status,
            Invoice.registered_at,
            registrar.full_name.label("registered_by"),
            func.coalesce(line_totals.c.total_units, 0).label("total_units"),
            func.coalesce(dispatch_totals.c.dispatched_units, 0).label("dispatched_units"),
            func.coalesce(dispatch_totals.c.missing_units, 0).label("missing_units"),
        )
        .outerjoin(line_totals, line_totals.c.invoice_id == Invoice.id)
        .outerjoin(dispatch_totals, dispatch_totals.c.invoice_id == Invoice.id)
        .outerjoin(registrar, registrar.id == Invoice.registered_by_user_id)
        .outerjoin(PurchaseOrder, PurchaseOrder.id == Invoice.purchase_order_id)
        .order_by(Invoice.registered_at.desc(), Invoice.id.desc())
        .limit(limit)
    ).mappings()

    summaries = []
    for row in rows:
        values = dict(row)
        values["pending_units"] = max(
            0,
            int(values["total_units"])
            - int(values["dispatched_units"])
            - int(values["missing_units"]),
        )
        summaries.append(InvoiceSummaryRead(**values))
    return summaries


def list_pending_dispatches(db: Session, limit: int = 500) -> list[PendingDispatchRead]:
    dispatched = (
        select(
            Dispatch.invoice_id,
            Dispatch.product_id,
            func.sum(Dispatch.dispatched_quantity).label("dispatched_quantity"),
            func.sum(Dispatch.missing_quantity).label("missing_quantity"),
        )
        .group_by(Dispatch.invoice_id, Dispatch.product_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Invoice.id.label("invoice_id"),
            Invoice.invoice_number,
            Invoice.customer_name,
            Invoice.status.label("invoice_status"),
            Invoice.registered_at,
            Product.sku,
            Product.name.label("product_name"),
            InvoiceLine.quantity.label("invoiced_quantity"),
            func.coalesce(dispatched.c.dispatched_quantity, 0).label("dispatched_quantity"),
            func.coalesce(dispatched.c.missing_quantity, 0).label("missing_quantity"),
        )
        .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
        .join(Product, Product.id == InvoiceLine.product_id)
        .outerjoin(
            dispatched,
            (dispatched.c.invoice_id == Invoice.id)
            & (dispatched.c.product_id == Product.id),
        )
        .order_by(Invoice.registered_at, Invoice.id, Product.sku)
        .limit(limit)
    ).mappings()

    pending_rows = []
    for row in rows:
        values = dict(row)
        values["pending_quantity"] = max(
            0,
            int(values["invoiced_quantity"])
            - int(values["dispatched_quantity"])
            - int(values["missing_quantity"]),
        )
        if values["pending_quantity"] > 0:
            pending_rows.append(PendingDispatchRead(**values))
    return pending_rows


def list_incident_summaries(db: Session, limit: int = 100) -> list[IncidentRead]:
    creator = aliased(User)
    rows = db.execute(
        select(
            Incident.id,
            Incident.status,
            Incident.incident_type,
            Product.sku,
            Product.name.label("product_name"),
            Invoice.invoice_number,
            Invoice.customer_name,
            (PurchaseOrder.chain_name + " / " + PurchaseOrder.order_number).label(
                "purchase_order_reference"
            ),
            Incident.description,
            creator.full_name.label("created_by"),
            Incident.created_at,
            Incident.resolved_at,
        )
        .outerjoin(Product, Product.id == Incident.product_id)
        .outerjoin(Invoice, Invoice.id == Incident.invoice_id)
        .outerjoin(PurchaseOrder, PurchaseOrder.id == Incident.purchase_order_id)
        .outerjoin(creator, creator.id == Incident.created_by_user_id)
        .order_by(Incident.created_at.desc(), Incident.id.desc())
        .limit(limit)
    ).mappings()
    return [IncidentRead(**row) for row in rows]
