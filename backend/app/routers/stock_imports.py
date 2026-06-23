from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import Product, User
from app.parsers.physical_stock import StockFileError, parse_physical_stock_file
from app.schemas.stock_imports import (
    PhysicalCountDecision,
    PhysicalCountPreview,
    PhysicalCountRequestCreate,
    PhysicalCountRequestRead,
)
from app.services.stock_imports import (
    PhysicalCountInvalidError,
    PhysicalCountNotFoundError,
    PhysicalCountPendingError,
    PhysicalCountStaleError,
    PhysicalCountStatusError,
    approve_physical_count,
    list_physical_count_requests,
    preview_physical_count,
    reject_physical_count,
    request_physical_count,
)


router = APIRouter(prefix="/stock-imports", tags=["stock-imports"])


@router.get("/template")
def download_template(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.request_stock_adjustment)),
) -> Response:
    products = db.execute(
        select(Product.sku, Product.name)
        .where(Product.is_active.is_(True))
        .order_by(Product.sku)
    ).all()
    lines = ["SKU,Producto,Stock_Fisico"]
    for sku, name in products:
        safe_name = str(name).replace('"', '""')
        lines.append(f'{sku},"{safe_name}",0')
    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plantilla_conteo_fisico.csv"'},
    )


@router.post("/preview", response_model=PhysicalCountPreview)
async def preview_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.request_stock_adjustment)),
) -> PhysicalCountPreview:
    try:
        parsed_rows = parse_physical_stock_file(file.filename or "", await file.read())
        return preview_physical_count(db, file.filename or "archivo", parsed_rows)
    except StockFileError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("", response_model=PhysicalCountRequestRead, status_code=status.HTTP_201_CREATED)
def create_import_request(
    request_data: PhysicalCountRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.request_stock_adjustment)),
) -> PhysicalCountRequestRead:
    try:
        return request_physical_count(db, request_data, current_user.id)
    except PhysicalCountInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.detail) from exc
    except PhysicalCountPendingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una carga pendiente de decision: {exc}.",
        ) from exc


@router.get("", response_model=list[PhysicalCountRequestRead])
def read_import_requests(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.approve_stock_adjustment)),
) -> list[PhysicalCountRequestRead]:
    return list_physical_count_requests(db)


@router.post("/{approval_id}/approve", response_model=PhysicalCountRequestRead)
def approve_import_request(
    approval_id: int,
    decision_data: PhysicalCountDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.approve_stock_adjustment)),
) -> PhysicalCountRequestRead:
    try:
        return approve_physical_count(db, approval_id, decision_data, current_user.id)
    except PhysicalCountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carga no encontrada.") from exc
    except PhysicalCountStatusError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"La carga ya esta {exc}.") from exc
    except PhysicalCountStaleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El stock cambio despues de la solicitud para: {', '.join(exc.skus)}.",
        ) from exc


@router.post("/{approval_id}/reject", response_model=PhysicalCountRequestRead)
def reject_import_request(
    approval_id: int,
    decision_data: PhysicalCountDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.approve_stock_adjustment)),
) -> PhysicalCountRequestRead:
    try:
        return reject_physical_count(db, approval_id, decision_data, current_user.id)
    except PhysicalCountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carga no encontrada.") from exc
    except PhysicalCountStatusError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"La carga ya esta {exc}.") from exc
