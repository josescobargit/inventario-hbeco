from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.schemas.reservations import ReservationCreate, ReservationRead, ReservationRelease
from app.services.reservations import (
    ReservationInactiveError,
    ReservationNotFoundError,
    ReservationStockError,
    create_reservation,
    release_reservation,
)


router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
def reserve_stock(
    reservation: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.manage_reservations)),
) -> ReservationRead:
    try:
        return create_reservation(db, reservation, current_user.id)
    except ReservationStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede reservar {exc.requested} de {exc.sku}. Disponible: {exc.available}.",
        ) from exc


@router.post("/{reservation_id}/release", response_model=ReservationRead)
def release_stock_reservation(
    reservation_id: int,
    release: ReservationRelease,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.manage_reservations)),
) -> ReservationRead:
    try:
        return release_reservation(db, reservation_id, release, current_user.id)
    except ReservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reserva no encontrada: {exc}",
        ) from exc
    except ReservationInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La reserva ya no esta activa: {exc}",
        ) from exc
