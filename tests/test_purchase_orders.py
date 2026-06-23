from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.inventory import AuditLog, Product, PurchaseOrder, PurchaseOrderLine, User
from app.schemas.purchase_orders import PurchaseOrderCreate, PurchaseOrderLineCreate
from app.services.purchase_orders import (
    PurchaseOrderAlreadyExistsError,
    PurchaseOrderUnknownProductError,
    create_purchase_order,
    list_purchase_orders,
)


def purchase_order_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        User.__table__,
        Product.__table__,
        PurchaseOrder.__table__,
        PurchaseOrderLine.__table__,
        AuditLog.__table__,
    ):
        table.create(engine)
    return Session(engine)


def test_create_purchase_order_groups_lines_and_saves_audit():
    db = purchase_order_db()
    user = User(
        username="ventas1",
        email="ventas@example.com",
        full_name="Usuario Ventas",
        password_hash="not-used",
        role="ventas",
        must_change_password=False,
    )
    db.add_all(
        [
            user,
            Product(sku="AE001", name="Shampoo", units_per_case=12),
            Product(sku="AE002", name="Acondicionador", units_per_case=12),
        ]
    )
    db.commit()

    created = create_purchase_order(
        db,
        PurchaseOrderCreate(
            chain_name="TIA",
            order_number="OC-100",
            reason="Registro inicial",
            lines=[
                PurchaseOrderLineCreate(sku="AE001", requested_quantity=4),
                PurchaseOrderLineCreate(sku="AE001", requested_quantity=3),
                PurchaseOrderLineCreate(sku="AE002", requested_quantity=2),
            ],
        ),
        user.id,
    )

    assert created.chain_name == "TIA"
    assert created.order_number == "OC-100"
    assert created.total_units == 9
    assert created.line_count == 2

    orders = list_purchase_orders(db)
    assert orders[0].total_units == 9
    assert db.query(AuditLog).count() == 1


def test_create_purchase_order_rejects_duplicate_order():
    db = purchase_order_db()
    user = User(
        username="ventas1",
        email="ventas@example.com",
        full_name="Usuario Ventas",
        password_hash="not-used",
        role="ventas",
        must_change_password=False,
    )
    db.add_all([user, Product(sku="AE001", name="Shampoo", units_per_case=12)])
    db.commit()

    payload = PurchaseOrderCreate(
        chain_name="TIA",
        order_number="OC-100",
        reason="Registro inicial",
        lines=[PurchaseOrderLineCreate(sku="AE001", requested_quantity=1)],
    )
    create_purchase_order(db, payload, user.id)

    try:
        create_purchase_order(db, payload, user.id)
        assert False, "Expected duplicate purchase order error"
    except PurchaseOrderAlreadyExistsError:
        assert True


def test_create_purchase_order_rejects_unknown_products():
    db = purchase_order_db()
    user = User(
        username="ventas1",
        email="ventas@example.com",
        full_name="Usuario Ventas",
        password_hash="not-used",
        role="ventas",
        must_change_password=False,
    )
    db.add(user)
    db.commit()

    try:
        create_purchase_order(
            db,
            PurchaseOrderCreate(
                chain_name="TIA",
                order_number="OC-200",
                reason="Registro inicial",
                lines=[PurchaseOrderLineCreate(sku="AE999", requested_quantity=2)],
            ),
            user.id,
        )
        assert False, "Expected unknown product error"
    except PurchaseOrderUnknownProductError as exc:
        assert exc.skus == ["AE999"]
