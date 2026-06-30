from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.parsers.invoice_bulk import BulkInvoiceParseError
from app.parsers.invoice_pdf import InvoiceFileError, parse_contifico_invoice_pdf
from app.schemas.invoices import (
    BulkInvoiceCreate,
    BulkInvoicePreviewRead,
    BulkInvoicePreviewRequest,
    InvoiceCreate,
    InvoiceFilePreviewRead,
    InvoiceRead,
    InvoiceSummaryRead,
)
from app.services.invoice_bulk import (
    BulkInvoiceUnknownProductError,
    build_bulk_invoice_preview,
    register_bulk_invoices,
)
from app.services.invoice_files import InvoiceFileUnknownProductError, build_invoice_file_preview
from app.services.invoicing import (
    InsufficientStockError,
    InvoiceAlreadyExistsError,
    InvoiceExceedsPurchaseOrderError,
    InvoicePurchaseOrderError,
    UnknownProductError,
    register_invoice,
)
from app.services.tracking import list_invoice_summaries


router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/preview-file", response_model=InvoiceFilePreviewRead)
async def preview_invoice_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.register_invoice)),
) -> InvoiceFilePreviewRead:
    try:
        parsed = parse_contifico_invoice_pdf(file.filename or "factura.pdf", await file.read())
        return build_invoice_file_preview(db, parsed)
    except InvoiceFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvoiceFileUnknownProductError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SKU de la factura no encontrados: {', '.join(exc.skus)}.",
        ) from exc


@router.get("", response_model=list[InvoiceSummaryRead])
def read_invoices(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.view_inventory)),
) -> list[InvoiceSummaryRead]:
    return list_invoice_summaries(db, limit)


@router.post("/bulk-preview", response_model=BulkInvoicePreviewRead)
def preview_bulk_invoices(
    payload: BulkInvoicePreviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.register_invoice)),
) -> BulkInvoicePreviewRead:
    try:
        return build_bulk_invoice_preview(db, payload.raw_text)
    except BulkInvoiceUnknownProductError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No pude homologar estos productos: {', '.join(exc.descriptions)}.",
        ) from exc
    except BulkInvoiceParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/bulk", response_model=list[InvoiceRead], status_code=status.HTTP_201_CREATED)
def create_bulk_invoices(
    payload: BulkInvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.register_invoice)),
) -> list[InvoiceRead]:
    try:
        return register_bulk_invoices(db, payload, current_user.id)
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
            detail=(
                f"Stock insuficiente para {exc.sku}. Pedido: {exc.requested}. "
                f"Disponible: {exc.available}."
            ),
        ) from exc
    except InvoicePurchaseOrderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvoiceExceedsPurchaseOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"La factura excede la OC para {exc.sku}. Factura: {exc.requested}. "
                f"Pendiente en OC: {exc.remaining}."
            ),
        ) from exc


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
    except InvoicePurchaseOrderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvoiceExceedsPurchaseOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"La factura excede la OC para {exc.sku}. Factura: {exc.requested}. "
                f"Pendiente en OC: {exc.remaining}."
            ),
        ) from exc
