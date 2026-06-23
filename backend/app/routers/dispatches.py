from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.schemas.dispatches import DispatchCreate, DispatchRead, PendingDispatchRead
from app.services.dispatching import (
    DispatchQuantityError,
    DispatchStockError,
    InvoiceNotFoundError,
    confirm_dispatch,
)
from app.services.tracking import list_pending_dispatches


router = APIRouter(prefix="/dispatches", tags=["dispatches"])


@router.get("/pending", response_model=list[PendingDispatchRead])
def read_pending_dispatches(
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.view_inventory)),
) -> list[PendingDispatchRead]:
    return list_pending_dispatches(db, limit)


@router.post("", response_model=DispatchRead, status_code=status.HTTP_201_CREATED)
def create_dispatch(
    dispatch: DispatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.confirm_dispatch)),
) -> DispatchRead:
    try:
        return confirm_dispatch(db, dispatch, current_user.id)
    except InvoiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factura no encontrada: {exc}",
        ) from exc
    except DispatchQuantityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DispatchStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No se puede despachar {exc.requested} de {exc.sku}; "
                f"fisico confirmado: {exc.physical_confirmed}."
            ),
        ) from exc
