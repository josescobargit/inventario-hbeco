from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.parsers.purchase_orders import PurchaseOrderFileError, parse_purchase_order_pdf
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderDetailRead,
    PurchaseOrderFilePreviewRead,
    PurchaseOrderRead,
)
from app.services.purchase_orders import (
    PurchaseOrderAlreadyExistsError,
    PurchaseOrderNotFoundError,
    PurchaseOrderReservationError,
    PurchaseOrderUnknownProductError,
    build_purchase_order_file_preview,
    create_purchase_order,
    get_purchase_order_detail,
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


@router.post("/preview-file", response_model=PurchaseOrderFilePreviewRead)
async def preview_purchase_order_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.manage_reservations)),
) -> PurchaseOrderFilePreviewRead:
    try:
        parsed_orders = parse_purchase_order_pdf(file.filename or "oc.pdf", await file.read())
        return build_purchase_order_file_preview(
            db=db,
            source_filename=file.filename or "oc.pdf",
            parsed_orders=parsed_orders,
        )
    except PurchaseOrderFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PurchaseOrderUnknownProductError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SKU no encontrados en la OC detectada: {', '.join(exc.skus)}.",
        ) from exc


@router.get("/{purchase_order_id}", response_model=PurchaseOrderDetailRead)
def read_purchase_order_detail(
    purchase_order_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.view_inventory)),
) -> PurchaseOrderDetailRead:
    try:
        return get_purchase_order_detail(db, purchase_order_id)
    except PurchaseOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OC no encontrada.") from exc


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
    except PurchaseOrderReservationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No se puede reservar toda la OC. {exc.sku}: solicitado {exc.requested}, "
                f"disponible {exc.available}. Puedes guardarla sin reservar."
            ),
        ) from exc
