"""Add suppliers, purchase receipts and inventory ledger.

Revision ID: 0006_inventory_purchase
Revises: 0005_base_catalogs
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0006_inventory_purchase"
down_revision = "0005_base_catalogs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("contact", sa.String(length=40), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_suppliers_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_suppliers_created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_suppliers_updated_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "code", name="uq_suppliers_farm_code"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_suppliers_farm_active", "suppliers", ["farm_id", "is_active"], unique=False)

    op.create_table(
        "purchase_orders",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("order_no", sa.String(length=30), nullable=False),
        sa.Column("supplier_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("posted_by_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("total_amount >= 0", name="ck_purchase_orders_total_nonnegative"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_purchase_orders_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], name="fk_purchase_orders_supplier", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], name="fk_purchase_orders_warehouse", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by_id"], ["users.id"], name="fk_purchase_orders_posted_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_purchase_orders_created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_purchase_orders_updated_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "order_no", name="uq_purchase_orders_farm_no"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_purchase_orders_farm_status_date",
        "purchase_orders",
        ["farm_id", "status", "order_date"],
        unique=False,
    )

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("purchase_order_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("item_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("lot_no", sa.String(length=64), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_lines_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_purchase_lines_price_nonnegative"),
        sa.CheckConstraint("amount >= 0", name="ck_purchase_lines_amount_nonnegative"),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"], ["purchase_orders.id"], name="fk_purchase_lines_order", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_purchase_lines_item", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_purchase_order_lines_order", "purchase_order_lines", ["purchase_order_id"], unique=False
    )

    op.create_table(
        "stock_documents",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("document_no", sa.String(length=40), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("from_warehouse_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("to_warehouse_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_stock_documents_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["from_warehouse_id"], ["warehouses.id"], name="fk_stock_documents_from_warehouse", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["to_warehouse_id"], ["warehouses.id"], name="fk_stock_documents_to_warehouse", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_stock_documents_created_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "document_no", name="uq_stock_documents_farm_no"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_stock_documents_source"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_stock_documents_farm_type_time",
        "stock_documents",
        ["farm_id", "document_type", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "stock_movement_lines",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("stock_document_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("item_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("lot_no", sa.String(length=64), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("cost_object_type", sa.String(length=32), nullable=True),
        sa.Column("cost_object_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("quantity_delta <> 0", name="ck_stock_movements_quantity_nonzero"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_stock_movements_cost_nonnegative"),
        sa.ForeignKeyConstraint(
            ["stock_document_id"], ["stock_documents.id"], name="fk_stock_movements_document", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouses.id"], name="fk_stock_movements_warehouse", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_stock_movements_item", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_stock_movements_document", "stock_movement_lines", ["stock_document_id"], unique=False
    )
    op.create_index(
        "ix_stock_movements_balance", "stock_movement_lines", ["warehouse_id", "item_id"], unique=False
    )

    op.create_table(
        "inventory_balances",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("item_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), server_default="0", nullable=False),
        sa.Column("average_cost", sa.Numeric(precision=16, scale=4), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_balances_quantity_nonnegative"),
        sa.CheckConstraint("average_cost >= 0", name="ck_inventory_balances_cost_nonnegative"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_inventory_balances_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouses.id"], name="fk_inventory_balances_warehouse", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_inventory_balances_item", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("warehouse_id", "item_id", name="uq_inventory_balances_warehouse_item"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_inventory_balances_farm", "inventory_balances", ["farm_id"], unique=False)


def downgrade():
    op.drop_index("ix_inventory_balances_farm", table_name="inventory_balances")
    op.drop_table("inventory_balances")
    op.drop_index("ix_stock_movements_balance", table_name="stock_movement_lines")
    op.drop_index("ix_stock_movements_document", table_name="stock_movement_lines")
    op.drop_table("stock_movement_lines")
    op.drop_index("ix_stock_documents_farm_type_time", table_name="stock_documents")
    op.drop_table("stock_documents")
    op.drop_index("ix_purchase_order_lines_order", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
    op.drop_index("ix_purchase_orders_farm_status_date", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index("ix_suppliers_farm_active", table_name="suppliers")
    op.drop_table("suppliers")
