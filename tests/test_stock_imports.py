import io

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.models.inventory import Approval, AuditLog, Product, StockMovement, StockPosition, User
from app.parsers.physical_stock import StockFileError, parse_physical_stock_file
from app.schemas.stock_imports import (
    PhysicalCountDecision,
    PhysicalCountLine,
    PhysicalCountRequestCreate,
)
from app.services.stock_imports import (
    PhysicalCountInvalidError,
    PhysicalCountStaleError,
    approve_physical_count,
    preview_physical_count,
    request_physical_count,
)


def test_csv_parser_accepts_semicolon_and_accented_header():
    rows = parse_physical_stock_file(
        "conteo.csv",
        "SKU;Stock Físico\nAE001;24\nAR005;288\n".encode("utf-8"),
    )

    assert rows == [
        {"sku": "AE001", "physical_confirmed": 24, "row_number": 2},
        {"sku": "AR005", "physical_confirmed": 288, "row_number": 3},
    ]


def test_xlsx_parser_reads_the_first_sheet():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["SKU", "Producto", "Stock_Fisico"])
    sheet.append(["AE001", "Shampoo", 36])
    output = io.BytesIO()
    workbook.save(output)

    rows = parse_physical_stock_file("conteo.xlsx", output.getvalue())

    assert rows[0]["sku"] == "AE001"
    assert rows[0]["physical_confirmed"] == 36


def test_parser_rejects_negative_or_decimal_stock():
    with pytest.raises(StockFileError):
        parse_physical_stock_file("conteo.csv", b"SKU,Stock_Fisico\nAE001,-1\n")
    with pytest.raises(StockFileError):
        parse_physical_stock_file("conteo.csv", b"SKU,Stock_Fisico\nAE001,1.5\n")


@pytest.fixture
def stock_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def add_greatest(dbapi_connection, _):
        dbapi_connection.create_function("greatest", -1, max, deterministic=True)

    for table in (
        User.__table__,
        Product.__table__,
        StockPosition.__table__,
        Approval.__table__,
        StockMovement.__table__,
        AuditLog.__table__,
    ):
        table.create(engine)

    with Session(engine) as session:
        user = User(
            username="principal",
            email="principal@example.com",
            full_name="Principal",
            password_hash="not-used",
            role="principal",
            must_change_password=False,
        )
        session.add(user)
        session.flush()
        for sku, name, units in (("AE001", "Shampoo", 12), ("AR005", "Sachet", 288)):
            product = Product(sku=sku, name=name, units_per_case=units)
            session.add(product)
            session.flush()
            session.add(StockPosition(product_id=product.id))
        session.commit()
        yield session, user


def _request_data(ae_quantity=24, ar_quantity=288):
    return PhysicalCountRequestCreate(
        reason="Conteo fisico inicial completo",
        lines=[
            PhysicalCountLine(sku="AE001", physical_confirmed=ae_quantity),
            PhysicalCountLine(sku="AR005", physical_confirmed=ar_quantity),
        ],
    )


def test_full_count_requires_approval_before_changing_stock(stock_db):
    db, user = stock_db
    parsed = [
        {"sku": "AE001", "physical_confirmed": 24},
        {"sku": "AR005", "physical_confirmed": 288},
    ]
    preview = preview_physical_count(db, "conteo.csv", parsed)
    assert preview.valid
    assert preview.total_units == 312

    request = request_physical_count(db, _request_data(), user.id)
    assert request.status == "solicitada"
    assert db.scalar(select(func.sum(StockPosition.physical_confirmed))) == 0

    result = approve_physical_count(
        db,
        request.approval_id,
        PhysicalCountDecision(reason="Conteo revisado y aprobado"),
        user.id,
    )
    assert result.status == "aplicada"
    assert db.scalar(select(func.sum(StockPosition.physical_confirmed))) == 312
    assert db.scalar(select(func.count(StockMovement.id))) == 2


def test_preview_marks_missing_unknown_and_duplicate_skus(stock_db):
    db, _ = stock_db
    preview = preview_physical_count(
        db,
        "conteo.csv",
        [
            {"sku": "AE001", "physical_confirmed": 12},
            {"sku": "AE001", "physical_confirmed": 24},
            {"sku": "NO-EXISTE", "physical_confirmed": 1},
        ],
    )

    assert not preview.valid
    assert preview.duplicate_skus == ["AE001"]
    assert preview.unknown_skus == ["NO-EXISTE"]
    assert preview.missing_skus == ["AR005"]


def test_direct_incomplete_request_is_rejected(stock_db):
    db, user = stock_db
    incomplete = PhysicalCountRequestCreate(
        reason="Intento incompleto",
        lines=[PhysicalCountLine(sku="AE001", physical_confirmed=12)],
    )

    with pytest.raises(PhysicalCountInvalidError):
        request_physical_count(db, incomplete, user.id)


def test_approval_is_blocked_if_stock_changed_after_request(stock_db):
    db, user = stock_db
    request = request_physical_count(db, _request_data(), user.id)
    stock = db.scalar(
        select(StockPosition)
        .join(Product, Product.id == StockPosition.product_id)
        .where(Product.sku == "AE001")
    )
    stock.physical_confirmed = 1
    db.commit()

    with pytest.raises(PhysicalCountStaleError):
        approve_physical_count(
            db,
            request.approval_id,
            PhysicalCountDecision(reason="Intento sobre conteo antiguo"),
            user.id,
        )
