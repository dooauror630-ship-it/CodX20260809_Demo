"""Allow stock documents without an upstream business source.

Revision ID: 0007_inventory_operations
Revises: 0006_inventory_purchase
Create Date: 2026-08-15
"""

from alembic import op
from sqlalchemy.dialects import mysql


revision = "0007_inventory_operations"
down_revision = "0006_inventory_purchase"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "stock_documents",
        "source_id",
        existing_type=mysql.BIGINT(unsigned=True),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "stock_documents",
        "source_id",
        existing_type=mysql.BIGINT(unsigned=True),
        nullable=False,
    )
