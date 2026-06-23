from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.parsers.purchase_orders import PurchaseOrderFileError, parse_purchase_order_pdf
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderPreviewRead,
    PurchaseOrderRead,
)
from app.services.purchase_orders import (
    PurchaseOrderAlreadyExistsError,
    PurchaseOrderUnknownProductError,
    build_purchase_order_preview,
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


@router.post("/preview-file", response_model=PurchaseOrderPreviewRead)
async def preview_purchase_order_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.manage_reservations)),
) -> PurchaseOrderPreviewRead:
    try:
        detected_chain_name, lines = parse_purchase_order_pdf(file.filename or "oc.pdf", await file.read())
        return build_purchase_order_preview(
            db=db,
            detected_chain_name=detected_chain_name,
            source_filename=file.filename or "oc.pdf",
            lines=lines,
        )
    except PurchaseOrderFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PurchaseOrderUnknownProductError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SKU no encontrados en la OC detectada: {', '.join(exc.skus)}.",
        ) from exc


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
