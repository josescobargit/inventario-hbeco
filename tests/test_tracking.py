from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.inventory import (
    Dispatch,
    Incident,
    Invoice,
    InvoiceLine,
    Product,
    PurchaseOrder,
    Reservation,
    User,
)
from app.services.tracking import (
    list_incident_summaries,
    list_invoice_summaries,
    list_pending_dispatches,
    list_reservation_summaries,
)


def tracking_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        User.__table__,
        Product.__table__,
        Invoice.__table__,
        InvoiceLine.__table__,
        Dispatch.__table__,
        Reservation.__table__,
        PurchaseOrder.__table__,
        Incident.__table__,
    ):
        table.create(engine)
    return Session(engine)


def test_tracking_summaries_keep_pending_quantities_consistent():
    db = tracking_db()
    user = User(
        username="ventas1",
        email="ventas@example.com",
        full_name="Usuario Ventas",
        password_hash="not-used",
        role="ventas",
        must_change_password=False,
    )
    product = Product(sku="AE001", name="Shampoo", units_per_case=12)
    db.add_all([user, product])
    db.flush()

    invoice = Invoice(
        invoice_number="001-001-123",
        customer_name="TIA",
        registered_by_user_id=user.id,
    )
    db.add(invoice)
    db.flush()
    db.add(InvoiceLine(invoice_id=invoice.id, product_id=product.id, quantity=10))
    db.add(
        Dispatch(
            invoice_id=invoice.id,
            product_id=product.id,
            dispatched_quantity=4,
            missing_quantity=1,
            status="con_faltante",
            reason="Conteo de despacho",
            confirmed_by_user_id=user.id,
        )
    )
    db.add(
        Reservation(
            product_id=product.id,
            customer_name="FAVORITA",
            quantity=3,
            reason="OC pendiente",
            created_by_user_id=user.id,
        )
    )
    db.commit()

    invoices = list_invoice_summaries(db)
    assert invoices[0].total_units == 10
    assert invoices[0].dispatched_units == 4
    assert invoices[0].missing_units == 1
    assert invoices[0].pending_units == 5
    assert invoices[0].registered_by == "Usuario Ventas"

    pending = list_pending_dispatches(db)
    assert len(pending) == 1
    assert pending[0].sku == "AE001"
    assert pending[0].pending_quantity == 5

    reservations = list_reservation_summaries(db)
    assert reservations[0].customer_name == "FAVORITA"
    assert reservations[0].product_name == "Shampoo"
    assert reservations[0].created_by == "Usuario Ventas"


def test_fully_reported_invoice_is_not_pending():
    db = tracking_db()
    product = Product(sku="AE001", name="Shampoo", units_per_case=12)
    invoice = Invoice(invoice_number="001-001-999", customer_name="TIA")
    db.add_all([product, invoice])
    db.flush()
    db.add(InvoiceLine(invoice_id=invoice.id, product_id=product.id, quantity=6))
    db.add(
        Dispatch(
            invoice_id=invoice.id,
            product_id=product.id,
            dispatched_quantity=6,
            missing_quantity=0,
            status="despachado",
            reason="Completo",
        )
    )
    db.commit()

    assert list_pending_dispatches(db) == []


def test_incident_summaries_include_invoice_and_purchase_order_reference():
    db = tracking_db()
    user = User(
        username="bodega1",
        email="bodega@example.com",
        full_name="Usuario Bodega",
        password_hash="not-used",
        role="bodega",
        must_change_password=False,
    )
    product = Product(sku="AE001", name="Shampoo", units_per_case=12)
    invoice = Invoice(invoice_number="001-001-777", customer_name="TIA")
    purchase_order = PurchaseOrder(chain_name="TIA", order_number="OC-55")
    db.add_all([user, product, invoice, purchase_order])
    db.flush()
    db.add(
        Incident(
            status="abierta",
            incident_type="faltante_despacho",
            product_id=product.id,
            invoice_id=invoice.id,
            purchase_order_id=purchase_order.id,
            description="Faltante detectado al despachar",
            created_by_user_id=user.id,
        )
    )
    db.commit()

    incidents = list_incident_summaries(db)
    assert incidents[0].sku == "AE001"
    assert incidents[0].invoice_number == "001-001-777"
    assert incidents[0].purchase_order_reference == "TIA / OC-55"
    assert incidents[0].created_by == "Usuario Bodega"
