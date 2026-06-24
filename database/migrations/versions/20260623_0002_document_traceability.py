"""Add document metadata required for traceability.

Revision ID: 20260623_0002
Revises: 20260622_0001
Create Date: 2026-06-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260623_0002"
down_revision: Union[str, None] = "20260622_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reservations", sa.Column("original_quantity", sa.Integer(), nullable=True))
    op.execute("UPDATE reservations SET original_quantity = quantity WHERE original_quantity IS NULL")

    op.add_column("purchase_orders", sa.Column("external_reference", sa.String(120), nullable=True))
    op.add_column("purchase_orders", sa.Column("order_date", sa.Date(), nullable=True))
    op.add_column("purchase_orders", sa.Column("delivery_start_date", sa.Date(), nullable=True))
    op.add_column("purchase_orders", sa.Column("delivery_due_date", sa.Date(), nullable=True))
    op.add_column("purchase_orders", sa.Column("destination", sa.String(255), nullable=True))

    op.add_column("invoices", sa.Column("authorization_number", sa.String(80), nullable=True))
    op.add_column("invoices", sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("total_amount", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "total_amount")
    op.drop_column("invoices", "issued_at")
    op.drop_column("invoices", "authorization_number")
    op.drop_column("purchase_orders", "destination")
    op.drop_column("purchase_orders", "delivery_due_date")
    op.drop_column("purchase_orders", "delivery_start_date")
    op.drop_column("purchase_orders", "order_date")
    op.drop_column("purchase_orders", "external_reference")
    op.drop_column("reservations", "original_quantity")
