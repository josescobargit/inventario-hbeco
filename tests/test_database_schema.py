from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql, sqlite

from app.core.config import Settings
from app.db.base import Base
from app.models.inventory import StockPosition, User


EXPECTED_TABLES = {
    "approvals",
    "audit_log",
    "dispatches",
    "incidents",
    "invoice_lines",
    "invoices",
    "products",
    "purchase_order_lines",
    "purchase_orders",
    "reservations",
    "stock_movements",
    "stock_positions",
    "user_sessions",
    "users",
}


def test_model_metadata_contains_the_complete_initial_schema():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_identifiers_are_bigint_in_postgres_and_autoincrementable_in_sqlite():
    identifier_type = User.__table__.c.id.type

    assert identifier_type.compile(dialect=postgresql.dialect()) == "BIGINT"
    assert identifier_type.compile(dialect=sqlite.dialect()) == "INTEGER"


def test_available_stock_is_computed_by_the_database():
    computed = StockPosition.__table__.c.available_to_invoice.computed

    assert computed is not None
    assert "physical_confirmed - reserved" in str(computed.sqltext)


def test_alembic_has_one_linear_head():
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))

    assert scripts.get_heads() == ["20260623_0002"]


def test_migrations_use_the_dedicated_url_when_configured():
    settings = Settings(
        database_url="postgresql+psycopg://runtime.example/postgres",
        migration_database_url="postgresql+psycopg://migration.example/postgres",
    )

    assert settings.effective_migration_database_url.endswith("migration.example/postgres")


def test_migrations_fall_back_to_the_runtime_url():
    settings = Settings(
        database_url="postgresql+psycopg://runtime.example/postgres",
        migration_database_url="",
    )

    assert settings.effective_migration_database_url.endswith("runtime.example/postgres")


def test_database_password_is_safely_encoded_in_connection_urls():
    settings = Settings(
        database_url="postgresql+psycopg://postgres:{password}@db.example/postgres",
        database_password="p@ss/word#1",
    )

    assert settings.effective_database_url == (
        "postgresql+psycopg://postgres:p%40ss%2Fword%231@db.example/postgres"
    )
