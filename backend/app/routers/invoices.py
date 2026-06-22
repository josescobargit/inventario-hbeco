from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.schemas.invoices import InvoiceCreate, InvoiceRead
from app.services.invoicing import (
    InsufficientStockError,
    InvoiceAlreadyExistsError,
    UnknownProductError,
    register_invoice,
)


router = APIRouter(prefix="/invoices", tags=["invoices"])


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
