from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import (
    AuditLog,
    Product,
    Reservation,
    ReservationStatus,
    StockMovement,
    StockPosition,
)
from app.schemas.reservations import ReservationCreate, ReservationRead, ReservationRelease


class ReservationNotFoundError(Exception):
    pass


class ReservationInactiveError(Exception):
    pass


class ReservationStockError(Exception):
    def __init__(self, sku: str, requested: int, available: int) -> None:
        self.sku = sku
        self.requested = requested
        self.available = available
        super().__init__(f"{sku}: requested={requested}, available={available}")


def create_reservation(
    db: Session,
    reservation_data: ReservationCreate,
    actor_user_id: int,
) -> ReservationRead:
    sku = reservation_data.sku.upper().strip()
    row = db.execute(
        select(Product, StockPosition)
        .join(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.sku == sku)
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise ReservationStockError(sku, reservation_data.quantity, 0)

    product, stock = row
    requested = int(reservation_data.quantity)
    if stock.available_to_invoice < requested:
        raise ReservationStockError(sku, requested, stock.available_to_invoice)

    before_reserved = stock.reserved
    stock.reserved += requested

    reservation = Reservation(
        product_id=product.id,
        purchase_order_id=reservation_data.purchase_order_id,
        customer_name=reservation_data.customer_name,
        quantity=requested,
        reason=reservation_data.reason,
        created_by_user_id=actor_user_id,
    )
    db.add(reservation)
    db.flush()

    db.add(
        StockMovement(
            product_id=product.id,
            user_id=actor_user_id,
            movement_type="RESERVA",
            quantity=-requested,
            reason=reservation_data.reason,
            source_document_type="reservation",
            source_document_id=reservation.id,
            before_physical=stock.physical_confirmed,
            after_physical=stock.physical_confirmed,
        )
    )
    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="create_reservation",
            entity_type="reservation",
            entity_id=reservation.id,
            before_json=f'{{"sku":"{sku}","reserved":{before_reserved}}}',
            after_json=f'{{"sku":"{sku}","reserved":{stock.reserved}}}',
            reason=reservation_data.reason,
        )
    )
    db.commit()
    db.refresh(reservation)

    return ReservationRead(
        id=reservation.id,
        sku=sku,
        quantity=reservation.quantity,
        status=reservation.status,
        customer_name=reservation.customer_name,
        reason=reservation.reason,
        created_at=reservation.created_at,
    )


def release_reservation(
    db: Session,
    reservation_id: int,
    release_data: ReservationRelease,
    actor_user_id: int,
) -> ReservationRead:
    reservation = db.scalar(
        select(Reservation)
        .where(Reservation.id == reservation_id)
        .with_for_update()
    )
    if reservation is None:
        raise ReservationNotFoundError(str(reservation_id))
    if reservation.status != ReservationStatus.activa.value:
        raise ReservationInactiveError(str(reservation_id))

    row = db.execute(
        select(Product, StockPosition)
        .join(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.id == reservation.product_id)
        .with_for_update()
    ).one()
    product, stock = row

    before_reserved = stock.reserved
    stock.reserved = max(0, stock.reserved - reservation.quantity)
    reservation.status = ReservationStatus.eliminada.value
    reservation.released_by_user_id = actor_user_id
    reservation.release_reason = release_data.reason
    reservation.released_at = datetime.now(timezone.utc)

    db.add(
        StockMovement(
            product_id=product.id,
            user_id=actor_user_id,
            movement_type="ELIMINAR_RESERVA",
            quantity=reservation.quantity,
            reason=release_data.reason,
            source_document_type="reservation",
            source_document_id=reservation.id,
            before_physical=stock.physical_confirmed,
            after_physical=stock.physical_confirmed,
        )
    )
    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="release_reservation",
            entity_type="reservation",
            entity_id=reservation.id,
            before_json=f'{{"sku":"{product.sku}","reserved":{before_reserved}}}',
            after_json=f'{{"sku":"{product.sku}","reserved":{stock.reserved}}}',
            reason=release_data.reason,
        )
    )
    db.commit()
    db.refresh(reservation)

    return ReservationRead(
        id=reservation.id,
        sku=product.sku,
        quantity=reservation.quantity,
        status=reservation.status,
        customer_name=reservation.customer_name,
        reason=reservation.reason,
        created_at=reservation.created_at,
    )
