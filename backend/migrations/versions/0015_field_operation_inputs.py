"""Add field operation input links.

Revision ID: 0015_field_operation_inputs
Revises: 0014_field_operations
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "0015_field_operation_inputs"
down_revision = "0014_field_operations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "field_operation_inputs",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("field_operation_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("stock_document_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("item_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_field_operation_inputs_quantity_positive"),
        sa.CheckConstraint("amount >= 0", name="ck_field_operation_inputs_amount_nonnegative"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_field_operation_inputs_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["field_operation_id"], ["field_operations.id"], name="fk_field_operation_inputs_operation", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["stock_document_id"], ["stock_documents.id"], name="fk_field_operation_inputs_document", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_field_operation_inputs_item", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_field_operation_inputs_created_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_document_id", name="uq_field_operation_inputs_stock_document"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_field_operation_inputs_operation", "field_operation_inputs", ["field_operation_id", "id"])
    op.create_index("ix_field_operation_inputs_farm", "field_operation_inputs", ["farm_id", "created_at", "id"])


def downgrade():
    op.drop_table("field_operation_inputs")
