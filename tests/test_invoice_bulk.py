from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.inventory import Invoice, InvoiceLine, Product, PurchaseOrder, PurchaseOrderLine
from app.parsers.invoice_bulk import BulkInvoiceParseError, parse_bulk_invoice_text
from app.services.invoice_bulk import (
    BulkInvoiceUnknownProductError,
    build_bulk_invoice_preview,
)


def invoice_bulk_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Product.__table__,
        PurchaseOrder.__table__,
        PurchaseOrderLine.__table__,
        Invoice.__table__,
        InvoiceLine.__table__,
    ):
        table.create(engine)
    return Session(engine)


def test_parse_bulk_invoice_text_splits_blocks():
    groups = parse_bulk_invoice_text(
        """
        12.00 SHAMPOO ANA REGENEXT 400 ML. -
        24.00 TOALLITAS HÚMEDAS ANA X 100 -
        ----
        12.00 ACONDICIONADOR ANA REGENEXT 400 ML. -
        ---
        6.00 SHAMPOO ANA REGENEXT 400 ML. -
        """
    )

    assert len(groups) == 3
    assert groups[0][0].quantity == 12
    assert groups[1][0].raw_description == "ACONDICIONADOR ANA REGENEXT 400 ML."
    assert groups[2][0].quantity == 6


def test_parse_bulk_invoice_text_rejects_fractional_units():
    try:
        parse_bulk_invoice_text("12.50 SHAMPOO ANA REGENEXT 400 ML. -")
        assert False, "Expected parse error"
    except BulkInvoiceParseError:
        assert True


def test_parse_bulk_invoice_text_accepts_headers_bullets_and_unit_labels():
    groups = parse_bulk_invoice_text(
        """
        FACTURA: 001-001-101
        OC: 3000863180
        • 12 unidades x SHAMPOO ANA REGENEXT 400 ML.
        ====
        FACTURA 001-001-102
        6 uds. AR001 SHAMPOO ANA REGENEXT 400 ML.
        """
    )

    assert len(groups) == 2
    assert groups[0][0].quantity == 12
    assert groups[0][0].invoice_number == "001-001-101"
    assert groups[0][0].purchase_order_number == "3000863180"
    assert groups[1][0].quantity == 6


def test_build_bulk_invoice_preview_matches_catalog_names():
    db = invoice_bulk_db()
    db.add_all(
        [
            Product(sku="AR001", name="SHAMPOO ANA REGENEXT 400 ML.", units_per_case=12),
            Product(sku="ACP001", name="TOALLITAS HÚMEDAS ANA X 100", units_per_case=12),
        ]
    )
    db.commit()

    preview = build_bulk_invoice_preview(
        db,
        """
        12.00 SHAMPOO ANA REGENEXT 400 ML. -
        24.00 TOALLITAS HUMEDAS ANA X 100 -
        """,
    )

    assert preview.invoice_count == 1
    assert preview.invoices[0].lines[0].sku == "ACP001"
    assert preview.invoices[0].lines[1].sku == "AR001"


def test_build_bulk_invoice_preview_matches_sku_inside_description_and_suggests_order():
    db = invoice_bulk_db()
    product = Product(sku="AR001", name="SHAMPOO ANA REGENEXT 400 ML.", units_per_case=12)
    order = PurchaseOrder(chain_name="TIA", order_number="OC-100")
    db.add_all([product, order])
    db.flush()
    db.add(
        PurchaseOrderLine(
            purchase_order_id=order.id,
            product_id=product.id,
            requested_quantity=12,
        )
    )
    db.commit()

    preview = build_bulk_invoice_preview(
        db,
        "FACTURA: 001-001-900\nOC: OC-100\n12 AR001 - Shampoo Regenext 400 ml",
    )

    assert preview.invoices[0].lines[0].sku == "AR001"
    assert preview.invoices[0].suggested_invoice_number == "001-001-900"
    assert preview.invoices[0].suggested_purchase_order_id == order.id
    assert preview.invoices[0].purchase_order_candidates[0].order_number == "OC-100"


def test_build_bulk_invoice_preview_rejects_unknown_products():
    db = invoice_bulk_db()
    db.add(Product(sku="AR001", name="SHAMPOO ANA REGENEXT 400 ML.", units_per_case=12))
    db.commit()

    try:
        build_bulk_invoice_preview(db, "12.00 PRODUCTO INVENTADO -")
        assert False, "Expected unknown product error"
    except BulkInvoiceUnknownProductError as exc:
        assert "PRODUCTO INVENTADO" in exc.descriptions
