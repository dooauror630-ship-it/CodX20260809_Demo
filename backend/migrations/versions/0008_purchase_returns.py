"""Allow multiple stock documents for one business source.

Revision ID: 0008_purchase_returns
Revises: 0007_inventory_operations
Create Date: 2026-08-16
"""

from alembic import op


revision = "0008_purchase_returns"
down_revision = "0007_inventory_operations"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("uq_stock_documents_source", "stock_documents", type_="unique")
    op.create_index(
        "ix_stock_documents_source",
        "stock_documents",
        ["source_type", "source_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_stock_documents_source", table_name="stock_documents")
    op.create_unique_constraint(
        "uq_stock_documents_source",
        "stock_documents",
        ["source_type", "source_id"],
    )
