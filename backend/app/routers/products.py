from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import Product, StockPosition, User
from app.schemas.products import ProductRead, StockPositionRead


router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
def list_products(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.view_inventory)),
) -> list[Product]:
    statement = select(Product).order_by(Product.sku)
    return list(db.scalars(statement).all())


@router.get("/availability", response_model=list[StockPositionRead])
def list_product_availability(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.view_inventory)),
) -> list[StockPositionRead]:
    statement = (
        select(
            Product.sku,
            Product.name,
            Product.units_per_case,
            StockPosition.physical_confirmed,
            StockPosition.reserved,
            StockPosition.invoiced_pending_dispatch,
            StockPosition.blocked_incident,
            StockPosition.incoming_expected,
            StockPosition.available_to_invoice,
        )
        .join(StockPosition, StockPosition.product_id == Product.id)
        .order_by(Product.sku)
    )
    rows = db.execute(statement).mappings().all()
    return [StockPositionRead(**row) for row in rows]
