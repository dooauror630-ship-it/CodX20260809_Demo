"""Add warehouse inventory count documents.

Revision ID: 0009_inventory_counts
Revises: 0008_purchase_returns
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "0009_inventory_counts"
down_revision = "0008_purchase_returns"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_counts",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("count_no", sa.String(length=40), nullable=False),
        sa.Column("warehouse_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("count_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("posted_by_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_inventory_counts_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouses.id"], name="fk_inventory_counts_warehouse", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["posted_by_id"], ["users.id"], name="fk_inventory_counts_posted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_inventory_counts_created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["users.id"], name="fk_inventory_counts_updated_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "count_no", name="uq_inventory_counts_farm_no"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_inventory_counts_farm_status_date",
        "inventory_counts",
        ["farm_id", "status", "count_date"],
        unique=False,
    )

    op.create_table(
        "inventory_count_lines",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("inventory_count_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("item_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("lot_no", sa.String(length=64), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("book_quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("difference_quantity", sa.Numeric(precision=14, scale=3), server_default="0", nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=16, scale=4), server_default="0", nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.CheckConstraint("book_quantity >= 0", name="ck_inventory_count_lines_book_nonnegative"),
        sa.CheckConstraint("actual_quantity >= 0", name="ck_inventory_count_lines_actual_nonnegative"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_inventory_count_lines_cost_nonnegative"),
        sa.ForeignKeyConstraint(
            ["inventory_count_id"],
            ["inventory_counts.id"],
            name="fk_inventory_count_lines_count",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"], ["items.id"], name="fk_inventory_count_lines_item", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_inventory_count_lines_count",
        "inventory_count_lines",
        ["inventory_count_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_inventory_count_lines_count", table_name="inventory_count_lines")
    op.drop_table("inventory_count_lines")
    op.drop_index("ix_inventory_counts_farm_status_date", table_name="inventory_counts")
    op.drop_table("inventory_counts")
