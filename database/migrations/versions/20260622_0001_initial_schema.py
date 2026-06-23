"""Create the initial inventory schema.

Revision ID: 20260622_0001
Revises:
Create Date: 2026-06-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260622_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(40), nullable=False, server_default="consulta"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "role IN ('principal', 'administracion', 'ventas', 'bodega', 'consulta')",
            name="ck_users_role",
        ),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("sku", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("barcode", sa.String(80), nullable=True),
        sa.Column("contifico_aux_code", sa.String(80), nullable=True),
        sa.Column("cost", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("units_per_case", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.create_table(
        "stock_positions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=False, unique=True),
        sa.Column("physical_confirmed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invoiced_pending_dispatch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_incident", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incoming_expected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_to_invoice",
            sa.Integer(),
            sa.Computed(
                "GREATEST(0, physical_confirmed - reserved - invoiced_pending_dispatch - blocked_incident)",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("movement_type", sa.String(80), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_document_type", sa.String(80), nullable=True),
        sa.Column("source_document_id", sa.BigInteger(), nullable=True),
        sa.Column("before_physical", sa.Integer(), nullable=True),
        sa.Column("after_physical", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stock_movements_product_id", "stock_movements", ["product_id"])
    op.create_index("ix_stock_movements_created_at", "stock_movements", ["created_at"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("chain_name", sa.String(120), nullable=False),
        sa.Column("order_number", sa.String(120), nullable=False),
        sa.Column("status", sa.String(60), nullable=False, server_default="recibida"),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("chain_name", "order_number", name="uq_chain_order_number"),
    )
    op.create_index("ix_purchase_orders_chain_name", "purchase_orders", ["chain_name"])
    op.create_index("ix_purchase_orders_order_number", "purchase_orders", ["order_number"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("purchase_order_id", sa.BigInteger(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("original_description", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_purchase_order_lines_purchase_order_id",
        "purchase_order_lines",
        ["purchase_order_id"],
    )

    op.create_table(
        "reservations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("purchase_order_id", sa.BigInteger(), sa.ForeignKey("purchase_orders.id"), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(60), nullable=False, server_default="activa"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("released_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reservations_product_id", "reservations", ["product_id"])
    op.create_index("ix_reservations_status", "reservations", ["status"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("invoice_number", sa.String(120), nullable=False, unique=True),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("purchase_order_id", sa.BigInteger(), sa.ForeignKey("purchase_orders.id"), nullable=True),
        sa.Column("status", sa.String(60), nullable=False, server_default="facturada"),
        sa.Column("contifico_source_id", sa.String(120), nullable=True),
        sa.Column("registered_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

    op.create_table(
        "dispatches",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("dispatched_quantity", sa.Integer(), nullable=False),
        sa.Column("missing_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confirmed_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dispatches_invoice_id", "dispatches", ["invoice_id"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("status", sa.String(60), nullable=False, server_default="abierta"),
        sa.Column("incident_type", sa.String(80), nullable=False),
        sa.Column("product_id", sa.BigInteger(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("invoice_id", sa.BigInteger(), sa.ForeignKey("invoices.id"), nullable=True),
        sa.Column("purchase_order_id", sa.BigInteger(), sa.ForeignKey("purchase_orders.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_incidents_status", "incidents", ["status"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("status", sa.String(60), nullable=False, server_default="solicitada"),
        sa.Column("requested_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("request_type", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(120), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("approvals")
    op.drop_table("incidents")
    op.drop_table("dispatches")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("reservations")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
    op.drop_table("stock_movements")
    op.drop_table("stock_positions")
    op.drop_table("user_sessions")
    op.drop_table("products")
    op.drop_table("users")
