"""Add barns and plots.

Revision ID: 0004_farm_locations
Revises: 0003_farm_membership
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0004_farm_locations"
down_revision = "0003_farm_membership"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "barns",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("barn_type", sa.String(length=32), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("capacity >= 0", name="ck_barns_capacity_nonnegative"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_barns_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_barns_created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_barns_updated_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "code", name="uq_barns_farm_code"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_barns_farm_active", "barns", ["farm_id", "is_active"], unique=False)

    op.create_table(
        "plots",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("area_mu", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("soil_type", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("area_mu > 0", name="ck_plots_area_positive"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_plots_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_plots_created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_plots_updated_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "code", name="uq_plots_farm_code"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_plots_farm_active", "plots", ["farm_id", "is_active"], unique=False)


def downgrade():
    op.drop_index("ix_plots_farm_active", table_name="plots")
    op.drop_table("plots")
    op.drop_index("ix_barns_farm_active", table_name="barns")
    op.drop_table("barns")
