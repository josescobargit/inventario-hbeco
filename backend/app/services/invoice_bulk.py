from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inventory import (
    Invoice,
    InvoiceLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.parsers.invoice_bulk import parse_bulk_invoice_text
from app.schemas.invoices import (
    BulkInvoiceCreate,
    BulkInvoicePreviewItemRead,
    BulkInvoicePreviewLineRead,
    BulkInvoicePurchaseOrderCandidateRead,
    BulkInvoicePreviewRead,
    InvoiceRead,
)
from app.services.invoicing import InvoiceAlreadyExistsError, register_invoice


class BulkInvoiceUnknownProductError(Exception):
    def __init__(self, descriptions: list[str]) -> None:
        self.descriptions = descriptions
        super().__init__(", ".join(descriptions))


def _catalog_map(db: Session) -> tuple[dict[str, Product], dict[str, Product], list[Product]]:
    products = (
        db.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.sku))
        .scalars()
        .all()
    )
    by_sku = {product.sku.upper().strip(): product for product in products}
    by_name = {
        _normalize_name(product.name): product
        for product in products
    }
    return by_sku, by_name, products


def _normalize_name(value: str) -> str:
    from app.parsers.invoice_bulk import normalize_product_text

    return normalize_product_text(value)


def _resolve_product(
    normalized_description: str,
    by_sku: dict[str, Product],
    by_name: dict[str, Product],
    products: list[Product],
) -> Product | None:
    exact = by_sku.get(normalized_description) or by_name.get(normalized_description)
    if exact is not None:
        return exact

    description_tokens = set(normalized_description.split())
    sku_matches = [
        product for product in products if product.sku.upper().strip() in description_tokens
    ]
    if len(sku_matches) == 1:
        return sku_matches[0]

    contained = [
        product
        for product in products
        if _normalize_name(product.name) in normalized_description
        or normalized_description in _normalize_name(product.name)
    ]
    if len(contained) == 1:
        return contained[0]

    ranked = sorted(
        [
            (
                SequenceMatcher(
                    None, normalized_description, _normalize_name(product.name)
                ).ratio(),
                product,
            )
            for product in products
        ],
        key=lambda item: item[0],
    )
    if ranked and ranked[-1][0] >= 0.9:
        second_best = ranked[-2][0] if len(ranked) > 1 else 0
        if ranked[-1][0] - second_best >= 0.05:
            return ranked[-1][1]
    return None


def _purchase_order_candidates(
    db: Session,
    requested_by_sku: dict[str, int],
    preferred_order_number: str | None = None,
) -> tuple[int | None, list[BulkInvoicePurchaseOrderCandidateRead]]:
    order_rows = db.execute(
        select(PurchaseOrder, Product.sku, PurchaseOrderLine.requested_quantity)
        .join(PurchaseOrderLine, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .join(Product, Product.id == PurchaseOrderLine.product_id)
        .order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
    ).all()
    invoiced_rows = db.execute(
        select(Invoice.purchase_order_id, Product.sku, func.sum(InvoiceLine.quantity))
        .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
        .join(Product, Product.id == InvoiceLine.product_id)
        .where(Invoice.purchase_order_id.is_not(None))
        .group_by(Invoice.purchase_order_id, Product.sku)
    ).all()
    invoiced = {
        (int(purchase_order_id), sku): int(quantity or 0)
        for purchase_order_id, sku, quantity in invoiced_rows
    }

    orders: dict[int, dict[str, object]] = {}
    for order, sku, ordered_quantity in order_rows:
        entry = orders.setdefault(order.id, {"order": order, "remaining": {}})
        remaining = max(0, int(ordered_quantity) - invoiced.get((order.id, sku), 0))
        if remaining:
            entry["remaining"][sku] = remaining

    matches: list[tuple[bool, int, PurchaseOrder]] = []
    requested_skus = set(requested_by_sku)
    for entry in orders.values():
        order = entry["order"]
        remaining_by_sku = entry["remaining"]
        if all(
            remaining_by_sku.get(sku, 0) >= quantity
            for sku, quantity in requested_by_sku.items()
        ):
            exact_skus = requested_skus == set(remaining_by_sku)
            unused_units = sum(remaining_by_sku.values()) - sum(requested_by_sku.values())
            matches.append((exact_skus, unused_units, order))

    matches.sort(key=lambda item: (not item[0], item[1], -item[2].id))
    candidates = [
        BulkInvoicePurchaseOrderCandidateRead(
            id=order.id,
            order_number=order.order_number,
            chain_name=order.chain_name,
        )
        for _, _, order in matches
    ]
    exact_matches = [order for exact, _, order in matches if exact]
    preferred_matches = [
        order
        for _, _, order in matches
        if preferred_order_number
        and _normalize_name(order.order_number) == _normalize_name(preferred_order_number)
    ]
    suggested = (
        preferred_matches[0].id
        if len(preferred_matches) == 1
        else (
            candidates[0].id
            if len(candidates) == 1
            else exact_matches[0].id if len(exact_matches) == 1 else None
        )
    )
    return suggested, candidates


def build_bulk_invoice_preview(db: Session, raw_text: str) -> BulkInvoicePreviewRead:
    groups = parse_bulk_invoice_text(raw_text)
    by_sku, by_name, products = _catalog_map(db)

    preview_items: list[BulkInvoicePreviewItemRead] = []
    total_lines = 0

    for index, group in enumerate(groups, start=1):
        aggregated: dict[str, dict[str, object]] = defaultdict(
            lambda: {"quantity": 0, "product_name": "", "raw_description": ""}
        )
        unknown_descriptions: list[str] = []

        for line in group:
            product = _resolve_product(line.normalized_description, by_sku, by_name, products)
            if product is None:
                unknown_descriptions.append(line.raw_description)
                continue
            aggregated[product.sku]["quantity"] = int(aggregated[product.sku]["quantity"]) + line.quantity
            aggregated[product.sku]["product_name"] = product.name
            aggregated[product.sku]["raw_description"] = line.raw_description

        if unknown_descriptions:
            raise BulkInvoiceUnknownProductError(unknown_descriptions)

        preview_lines = [
            BulkInvoicePreviewLineRead(
                sku=sku,
                product_name=str(values["product_name"]),
                quantity=int(values["quantity"]),
                raw_description=str(values["raw_description"]),
            )
            for sku, values in sorted(aggregated.items())
        ]
        total_lines += len(preview_lines)
        requested_by_sku = {line.sku: line.quantity for line in preview_lines}
        suggested_invoice_number = group[0].invoice_number
        preferred_order_number = group[0].purchase_order_number
        suggested_purchase_order_id, purchase_order_candidates = _purchase_order_candidates(
            db, requested_by_sku, preferred_order_number
        )
        preview_items.append(
            BulkInvoicePreviewItemRead(
                block_number=index,
                total_units=sum(line.quantity for line in preview_lines),
                lines=preview_lines,
                suggested_invoice_number=suggested_invoice_number,
                suggested_purchase_order_id=suggested_purchase_order_id,
                purchase_order_candidates=purchase_order_candidates,
            )
        )

    return BulkInvoicePreviewRead(
        invoice_count=len(preview_items),
        lines_total=total_lines,
        invoices=preview_items,
    )


def register_bulk_invoices(
    db: Session,
    payload: BulkInvoiceCreate,
    actor_user_id: int,
) -> list[InvoiceRead]:
    numbers = [invoice.invoice_number.strip() for invoice in payload.invoices]
    duplicate_numbers = sorted({number for number in numbers if numbers.count(number) > 1})
    if duplicate_numbers:
        raise InvoiceAlreadyExistsError(", ".join(duplicate_numbers))

    try:
        created = [
            register_invoice(db, invoice, actor_user_id, commit=False)
            for invoice in payload.invoices
        ]
        db.commit()
        return created
    except Exception:
        db.rollback()
        raise
