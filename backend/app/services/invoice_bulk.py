from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import Product
from app.parsers.invoice_bulk import parse_bulk_invoice_text
from app.schemas.invoices import (
    BulkInvoicePreviewItemRead,
    BulkInvoicePreviewLineRead,
    BulkInvoicePreviewRead,
)


class BulkInvoiceUnknownProductError(Exception):
    def __init__(self, descriptions: list[str]) -> None:
        self.descriptions = descriptions
        super().__init__(", ".join(descriptions))


def _catalog_map(db: Session) -> tuple[dict[str, Product], dict[str, Product]]:
    products = db.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)).scalars().all()
    by_sku = {product.sku.upper().strip(): product for product in products}
    by_name = {
        _normalize_name(product.name): product
        for product in products
    }
    return by_sku, by_name


def _normalize_name(value: str) -> str:
    from app.parsers.invoice_bulk import normalize_product_text

    return normalize_product_text(value)


def build_bulk_invoice_preview(db: Session, raw_text: str) -> BulkInvoicePreviewRead:
    groups = parse_bulk_invoice_text(raw_text)
    by_sku, by_name = _catalog_map(db)

    preview_items: list[BulkInvoicePreviewItemRead] = []
    total_lines = 0

    for index, group in enumerate(groups, start=1):
        aggregated: dict[str, dict[str, object]] = defaultdict(
            lambda: {"quantity": 0, "product_name": "", "raw_description": ""}
        )
        unknown_descriptions: list[str] = []

        for line in group:
            product = by_sku.get(line.normalized_description) or by_name.get(line.normalized_description)
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
        preview_items.append(
            BulkInvoicePreviewItemRead(
                block_number=index,
                total_units=sum(line.quantity for line in preview_lines),
                lines=preview_lines,
            )
        )

    return BulkInvoicePreviewRead(
        invoice_count=len(preview_items),
        lines_total=total_lines,
        invoices=preview_items,
    )
