from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.schemas.stock_adjustments import (
    StockAdjustmentDecision,
    StockAdjustmentRead,
    StockAdjustmentRequestCreate,
)
from app.services.stock_adjustments import (
    StockAdjustmentApprovalNotFoundError,
    StockAdjustmentInvalidStatusError,
    StockAdjustmentInvalidTypeError,
    StockAdjustmentProductNotFoundError,
    approve_stock_adjustment,
    reject_stock_adjustment,
    request_stock_adjustment,
)


router = APIRouter(prefix="/stock-adjustments", tags=["stock-adjustments"])


@router.post("", response_model=StockAdjustmentRead, status_code=status.HTTP_201_CREATED)
def create_stock_adjustment_request(
    adjustment: StockAdjustmentRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.request_stock_adjustment)),
) -> StockAdjustmentRead:
    try:
        return request_stock_adjustment(db, adjustment, current_user.id)
    except StockAdjustmentProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto no encontrado: {exc}",
        ) from exc


@router.post("/{approval_id}/approve", response_model=StockAdjustmentRead)
def approve_stock_adjustment_request(
    approval_id: int,
    decision: StockAdjustmentDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.approve_stock_adjustment)),
) -> StockAdjustmentRead:
    try:
        return approve_stock_adjustment(db, approval_id, decision, current_user.id)
    except StockAdjustmentApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solicitud de ajuste no encontrada: {exc}",
        ) from exc
    except StockAdjustmentInvalidTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La solicitud no es un ajuste de stock: {exc}",
        ) from exc
    except StockAdjustmentInvalidStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La solicitud ya fue decidida o aplicada: {exc}",
        ) from exc


@router.post("/{approval_id}/reject", response_model=StockAdjustmentRead)
def reject_stock_adjustment_request(
    approval_id: int,
    decision: StockAdjustmentDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.approve_stock_adjustment)),
) -> StockAdjustmentRead:
    try:
        return reject_stock_adjustment(db, approval_id, decision, current_user.id)
    except StockAdjustmentApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solicitud de ajuste no encontrada: {exc}",
        ) from exc
    except StockAdjustmentInvalidTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La solicitud no es un ajuste de stock: {exc}",
        ) from exc
    except StockAdjustmentInvalidStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La solicitud ya fue decidida o aplicada: {exc}",
        ) from exc
