from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.schemas.invoices import InvoiceCreate, InvoiceRead, InvoiceSummaryRead
from app.services.invoicing import (
    InsufficientStockError,
    InvoiceAlreadyExistsError,
    UnknownProductError,
    register_invoice,
)
from app.services.tracking import list_invoice_summaries


router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceSummaryRead])
def read_invoices(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.view_inventory)),
) -> list[InvoiceSummaryRead]:
    return list_invoice_summaries(db, limit)


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(
    invoice: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.register_invoice)),
) -> InvoiceRead:
    try:
        return register_invoice(db, invoice, current_user.id)
    except InvoiceAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La factura ya existe: {exc}",
        ) from exc
    except UnknownProductError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SKU no encontrado(s): {', '.join(exc.skus)}",
        ) from exc
    except InsufficientStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stock insuficiente para {exc.sku}. Pedido: {exc.requested}. Disponible: {exc.available}.",
        ) from exc
