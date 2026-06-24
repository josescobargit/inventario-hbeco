from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models.inventory import (
    AuditLog,
    Invoice,
    InvoiceLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Reservation,
    StockMovement,
    StockPosition,
    User,
)
from app.schemas.invoices import InvoiceCreate, InvoiceLineCreate
from app.services.invoice_files import build_invoice_file_preview
from app.services.invoicing import InvoiceExceedsPurchaseOrderError, register_invoice
from app.services.purchase_orders import build_purchase_order_file_preview


def traceability_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def register_greatest(dbapi_connection, _):
        dbapi_connection.create_function("greatest", -1, max, deterministic=True)

    for table in (
        User.__table__,
        Product.__table__,
        StockPosition.__table__,
        PurchaseOrder.__table__,
        PurchaseOrderLine.__table__,
        Reservation.__table__,
        Invoice.__table__,
        InvoiceLine.__table__,
        StockMovement.__table__,
        AuditLog.__table__,
    ):
        table.create(engine)
    return Session(engine)


def seed_order(db: Session):
    user = User(
        username="ventas1",
        email="ventas@example.com",
        full_name="Usuario Ventas",
        password_hash="unused",
        role="ventas",
        must_change_password=False,
    )
    product = Product(sku="AR001", name="Shampoo", units_per_case=12)
    db.add_all([user, product])
    db.flush()
    stock = StockPosition(product_id=product.id, physical_confirmed=100, reserved=30)
    order = PurchaseOrder(chain_name="TIA", order_number="3000863180")
    db.add_all([stock, order])
    db.flush()
    db.add_all(
        [
            PurchaseOrderLine(
                purchase_order_id=order.id,
                product_id=product.id,
                requested_quantity=50,
            ),
            Reservation(
                product_id=product.id,
                purchase_order_id=order.id,
                customer_name="TIA",
                quantity=30,
                reason="Reserva OC",
                created_by_user_id=user.id,
            ),
        ]
    )
    db.commit()
    return user, product, stock, order


def test_invoice_uses_its_own_reservation_and_updates_order_status():
    db = traceability_db()
    user, _, stock, order = seed_order(db)

    result = register_invoice(
        db,
        InvoiceCreate(
            invoice_number="001-001-000000682",
            customer_name="TIA",
            purchase_order_id=order.id,
            reason="Factura confirmada",
            lines=[InvoiceLineCreate(sku="AR001", quantity=40)],
        ),
        user.id,
    )

    db.refresh(stock)
    db.refresh(order)
    reservation = db.query(Reservation).one()
    assert result.invoice_number == "001-001-000000682"
    assert stock.reserved == 0
    assert stock.invoiced_pending_dispatch == 40
    assert reservation.status == "convertida_en_factura"
    assert order.status == "parcialmente_facturada"


def test_invoice_cannot_exceed_remaining_purchase_order_quantity():
    db = traceability_db()
    user, _, _, order = seed_order(db)

    try:
        register_invoice(
            db,
            InvoiceCreate(
                invoice_number="001-001-999",
                purchase_order_id=order.id,
                reason="Validar limite de OC",
                lines=[InvoiceLineCreate(sku="AR001", quantity=51)],
            ),
            user.id,
        )
        assert False, "Expected purchase order quantity error"
    except InvoiceExceedsPurchaseOrderError as exc:
        assert exc.sku == "AR001"
        assert exc.remaining == 50


def test_invoice_file_preview_compares_order_and_available_stock():
    db = traceability_db()
    _, _, _, order = seed_order(db)

    preview = build_invoice_file_preview(
        db,
        {
            "invoice_number": "001-001-000000682",
            "purchase_order_number": "3000863180",
            "customer_name": "TIA",
            "authorization_number": "123",
            "issued_at": None,
            "total_amount": 100.0,
            "source_filename": "factura.pdf",
            "lines": [{"sku": "AR001", "quantity": 40, "description": "Shampoo"}],
        },
    )

    assert preview.purchase_order_id == order.id
    assert preview.can_register is True
    assert preview.lines[0].remaining_after_invoice == 10
    assert preview.lines[0].available_for_this_order == 100


def test_purchase_order_preview_keeps_unrecognized_lines_for_manual_review():
    db = traceability_db()
    seed_order(db)

    preview = build_purchase_order_file_preview(
        db,
        "oc.pdf",
        [
            {
                "chain_name": "TIA",
                "order_number": "3000863180",
                "lines": [
                    {
                        "sku_hint": "AR001",
                        "requested_quantity": 12,
                        "quantity_cases": 1,
                        "units_per_case": 12,
                        "original_description": "Shampoo reconocido",
                    },
                    {
                        "sku_hint": "ZZ999",
                        "requested_quantity": 6,
                        "quantity_cases": 1,
                        "units_per_case": 6,
                        "original_description": "Producto nuevo",
                    },
                ],
            }
        ],
    )

    assert preview.orders[0].line_count == 2
    assert preview.orders[0].lines[0].match_status == "reconocido"
    assert preview.orders[0].lines[1].match_status == "no_reconocido"
    assert preview.orders[0].lines[1].missing_quantity == 6
