"""Add shared catalogs, warehouses and item profiles.

Revision ID: 0005_base_catalogs
Revises: 0004_farm_locations
Create Date: 2026-08-15
"""

from decimal import Decimal

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0005_base_catalogs"
down_revision = "0004_farm_locations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "units",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("base_factor", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("scale", sa.Integer(), server_default="3", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("base_factor > 0", name="ck_units_base_factor_positive"),
        sa.CheckConstraint("scale >= 0 AND scale <= 6", name="ck_units_scale_range"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_units_code"),
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "livestock_species",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("tracking_mode", sa.String(length=20), server_default="BATCH", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_livestock_species_code"),
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "crop_types",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_crop_types_code"),
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "crop_varieties",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("crop_type_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["crop_type_id"], ["crop_types.id"], name="fk_crop_varieties_crop_type", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_crop_varieties_created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["users.id"], name="fk_crop_varieties_updated_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crop_type_id", "code", name="uq_crop_varieties_type_code"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_crop_varieties_type_active", "crop_varieties", ["crop_type_id", "is_active"], unique=False
    )
    op.create_table(
        "warehouses",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_warehouses_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_warehouses_created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["users.id"], name="fk_warehouses_updated_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "code", name="uq_warehouses_farm_code"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_warehouses_farm_active", "warehouses", ["farm_id", "is_active"], unique=False)
    op.create_table(
        "item_categories",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("parent_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_item_categories_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["item_categories.id"], name="fk_item_categories_parent", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_item_categories_created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["users.id"], name="fk_item_categories_updated_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "code", name="uq_item_categories_farm_code"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_item_categories_farm_active", "item_categories", ["farm_id", "is_active"], unique=False
    )
    op.create_index("ix_item_categories_parent", "item_categories", ["parent_id"], unique=False)
    op.create_table(
        "items",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("category_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("unit_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("safety_stock", sa.Numeric(precision=14, scale=3), server_default="0", nullable=False),
        sa.Column("lot_tracking", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("safety_stock >= 0", name="ck_items_safety_stock_nonnegative"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_items_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["item_categories.id"], name="fk_items_category", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], name="fk_items_unit", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_items_created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_items_updated_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "code", name="uq_items_farm_code"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_items_farm_active", "items", ["farm_id", "is_active"], unique=False)
    op.create_index("ix_items_category", "items", ["category_id"], unique=False)

    units = sa.table(
        "units",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("dimension", sa.String),
        sa.column("base_factor", sa.Numeric),
        sa.column("scale", sa.Integer),
    )
    op.bulk_insert(units, [
        {"code": "KG", "name": "千克", "dimension": "WEIGHT", "base_factor": Decimal("1"), "scale": 3},
        {"code": "JIN", "name": "斤", "dimension": "WEIGHT", "base_factor": Decimal("0.5"), "scale": 3},
        {"code": "TON", "name": "吨", "dimension": "WEIGHT", "base_factor": Decimal("1000"), "scale": 3},
        {"code": "L", "name": "升", "dimension": "VOLUME", "base_factor": Decimal("1"), "scale": 3},
        {"code": "HEAD", "name": "头", "dimension": "LIVESTOCK", "base_factor": Decimal("1"), "scale": 0},
        {"code": "BIRD", "name": "只", "dimension": "LIVESTOCK", "base_factor": Decimal("1"), "scale": 0},
        {"code": "MU", "name": "亩", "dimension": "AREA", "base_factor": Decimal("1"), "scale": 3},
        {"code": "BAG", "name": "袋", "dimension": "PACKAGE", "base_factor": Decimal("1"), "scale": 0},
    ])
    species = sa.table(
        "livestock_species",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(species, [{"code": "PIG", "name": "猪"}, {"code": "CHICKEN", "name": "鸡"}])
    crops = sa.table(
        "crop_types",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(crops, [
        {"code": "TOBACCO", "name": "烟草"},
        {"code": "GARLIC", "name": "大蒜"},
        {"code": "RICE", "name": "水稻"},
        {"code": "RAPESEED", "name": "油菜"},
    ])


def downgrade():
    op.drop_index("ix_items_category", table_name="items")
    op.drop_index("ix_items_farm_active", table_name="items")
    op.drop_table("items")
    op.drop_index("ix_item_categories_parent", table_name="item_categories")
    op.drop_index("ix_item_categories_farm_active", table_name="item_categories")
    op.drop_table("item_categories")
    op.drop_index("ix_warehouses_farm_active", table_name="warehouses")
    op.drop_table("warehouses")
    op.drop_index("ix_crop_varieties_type_active", table_name="crop_varieties")
    op.drop_table("crop_varieties")
    op.drop_table("crop_types")
    op.drop_table("livestock_species")
    op.drop_table("units")
