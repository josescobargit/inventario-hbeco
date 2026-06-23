from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.inventory import AuditLog, Product, PurchaseOrder, PurchaseOrderLine, User
from app.schemas.purchase_orders import (
    PurchaseOrderCreate,
    PurchaseOrderPreviewLineRead,
    PurchaseOrderPreviewRead,
    PurchaseOrderRead,
)


class PurchaseOrderAlreadyExistsError(Exception):
    pass


class PurchaseOrderUnknownProductError(Exception):
    def __init__(self, skus: list[str]) -> None:
        self.skus = skus
        super().__init__(", ".join(skus))


def _aggregate_lines(purchase_order: PurchaseOrderCreate) -> dict[str, tuple[int, str | None]]:
    quantities: dict[str, int] = defaultdict(int)
    descriptions: dict[str, str | None] = {}
    for line in purchase_order.lines:
        sku = line.sku.upper().strip()
        quantities[sku] += int(line.requested_quantity)
        if line.original_description:
            descriptions[sku] = line.original_description.strip()
    return {sku: (quantity, descriptions.get(sku)) for sku, quantity in quantities.items()}


def create_purchase_order(
    db: Session,
    purchase_order_data: PurchaseOrderCreate,
    actor_user_id: int,
) -> PurchaseOrderRead:
    chain_name = purchase_order_data.chain_name.strip().upper()
    order_number = purchase_order_data.order_number.strip().upper()

    existing = db.scalar(
        select(PurchaseOrder.id).where(
            PurchaseOrder.chain_name == chain_name,
            PurchaseOrder.order_number == order_number,
        )
    )
    if existing:
        raise PurchaseOrderAlreadyExistsError(f"{chain_name} {order_number}")

    requested_by_sku = _aggregate_lines(purchase_order_data)
    skus = sorted(requested_by_sku)
    products = db.execute(select(Product).where(Product.sku.in_(skus)).order_by(Product.sku)).scalars().all()
    products_by_sku = {product.sku: product for product in products}

    missing_skus = [sku for sku in skus if sku not in products_by_sku]
    if missing_skus:
        raise PurchaseOrderUnknownProductError(missing_skus)

    purchase_order = PurchaseOrder(
        chain_name=chain_name,
        order_number=order_number,
        notes=purchase_order_data.notes,
        source_filename=purchase_order_data.source_filename,
        created_by_user_id=actor_user_id,
    )
    db.add(purchase_order)
    db.flush()

    total_units = 0
    for sku, (quantity, description) in requested_by_sku.items():
        product = products_by_sku[sku]
        total_units += quantity
        db.add(
            PurchaseOrderLine(
                purchase_order_id=purchase_order.id,
                product_id=product.id,
                requested_quantity=quantity,
                original_description=description,
            )
        )

    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="create_purchase_order",
            entity_type="purchase_order",
            entity_id=purchase_order.id,
            before_json=None,
            after_json=(
                f'{{"chain_name":"{chain_name}","order_number":"{order_number}",'
                f'"line_count":{len(requested_by_sku)},"total_units":{total_units}}}'
            ),
            reason=purchase_order_data.reason,
        )
    )
    db.commit()
    db.refresh(purchase_order)

    creator_name = db.scalar(select(User.full_name).where(User.id == actor_user_id))
    return PurchaseOrderRead(
        id=purchase_order.id,
        chain_name=chain_name,
        order_number=order_number,
        status=purchase_order.status,
        total_units=total_units,
        line_count=len(requested_by_sku),
        created_by=creator_name,
        created_at=purchase_order.created_at,
    )


def list_purchase_orders(db: Session, limit: int = 100) -> list[PurchaseOrderRead]:
    creator = aliased(User)
    line_totals = (
        select(
            PurchaseOrderLine.purchase_order_id,
            func.sum(PurchaseOrderLine.requested_quantity).label("total_units"),
            func.count(PurchaseOrderLine.id).label("line_count"),
        )
        .group_by(PurchaseOrderLine.purchase_order_id)
        .subquery()
    )
    rows = db.execute(
        select(
            PurchaseOrder.id,
            PurchaseOrder.chain_name,
            PurchaseOrder.order_number,
            PurchaseOrder.status,
            PurchaseOrder.created_at,
            creator.full_name.label("created_by"),
            func.coalesce(line_totals.c.total_units, 0).label("total_units"),
            func.coalesce(line_totals.c.line_count, 0).label("line_count"),
        )
        .outerjoin(line_totals, line_totals.c.purchase_order_id == PurchaseOrder.id)
        .outerjoin(creator, creator.id == PurchaseOrder.created_by_user_id)
        .order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
        .limit(limit)
    ).mappings()
    return [PurchaseOrderRead(**row) for row in rows]


def build_purchase_order_preview(
    db: Session,
    detected_chain_name: str | None,
    source_filename: str,
    lines: list[dict[str, object]],
) -> PurchaseOrderPreviewRead:
    aggregated: dict[str, dict[str, object]] = {}
    for line in lines:
        sku = str(line["sku"]).upper().strip()
        current = aggregated.setdefault(
            sku,
            {
                "sku": sku,
                "requested_quantity": 0,
                "original_description": line.get("original_description"),
            },
        )
        current["requested_quantity"] = int(current["requested_quantity"]) + int(
            line["requested_quantity"]
        )

    skus = sorted(aggregated)
    products = db.execute(select(Product).where(Product.sku.in_(skus)).order_by(Product.sku)).scalars().all()
    products_by_sku = {product.sku: product for product in products}
    missing_skus = [sku for sku in skus if sku not in products_by_sku]
    if missing_skus:
        raise PurchaseOrderUnknownProductError(missing_skus)

    preview_lines = []
    total_units = 0
    for sku in skus:
        product = products_by_sku[sku]
        quantity = int(aggregated[sku]["requested_quantity"])
        total_units += quantity
        preview_lines.append(
            PurchaseOrderPreviewLineRead(
                sku=sku,
                product_name=product.name,
                requested_quantity=quantity,
                original_description=aggregated[sku]["original_description"],
            )
        )

    return PurchaseOrderPreviewRead(
        detected_chain_name=detected_chain_name,
        source_filename=source_filename,
        total_units=total_units,
        line_count=len(preview_lines),
        lines=preview_lines,
    )
