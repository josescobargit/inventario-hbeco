from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.schemas.purchase_orders import PurchaseOrderCreate, PurchaseOrderRead
from app.services.purchase_orders import (
    PurchaseOrderAlreadyExistsError,
    PurchaseOrderUnknownProductError,
    create_purchase_order,
    list_purchase_orders,
)


router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


@router.get("", response_model=list[PurchaseOrderRead])
def read_purchase_orders(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.view_inventory)),
) -> list[PurchaseOrderRead]:
    return list_purchase_orders(db, limit)


@router.post("", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def add_purchase_order(
    purchase_order: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.manage_reservations)),
) -> PurchaseOrderRead:
    try:
        return create_purchase_order(db, purchase_order, current_user.id)
    except PurchaseOrderAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La OC ya existe: {exc}.",
        ) from exc
    except PurchaseOrderUnknownProductError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SKU no encontrados: {', '.join(exc.skus)}.",
        ) from exc
