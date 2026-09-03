"""Add crop cycles and plot area occupancy constraints.

Revision ID: 0013_crop_cycles
Revises: 0012_livestock_costs
Create Date: 2026-09-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "0013_crop_cycles"
down_revision = "0012_livestock_costs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "crop_cycles",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("cycle_code", sa.String(length=40), nullable=False),
        sa.Column("plot_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("crop_type_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("variety_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("area_mu", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("planned_start_date", sa.Date(), nullable=False),
        sa.Column("planned_end_date", sa.Date(), nullable=False),
        sa.Column("actual_start_date", sa.Date(), nullable=True),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="PLANNED", nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('PLANNED', 'ACTIVE', 'HARVESTING', 'CLOSED', 'CANCELLED')", name="ck_crop_cycles_status"),
        sa.CheckConstraint("area_mu > 0", name="ck_crop_cycles_area_positive"),
        sa.CheckConstraint("planned_end_date >= planned_start_date", name="ck_crop_cycles_planned_dates"),
        sa.CheckConstraint("actual_end_date IS NULL OR actual_start_date IS NOT NULL", name="ck_crop_cycles_actual_start_before_end"),
        sa.CheckConstraint("actual_end_date IS NULL OR actual_end_date >= actual_start_date", name="ck_crop_cycles_actual_dates"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_crop_cycles_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plot_id"], ["plots.id"], name="fk_crop_cycles_plot", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["crop_type_id"], ["crop_types.id"], name="fk_crop_cycles_crop_type", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variety_id"], ["crop_varieties.id"], name="fk_crop_cycles_variety", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_crop_cycles_created_by", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_crop_cycles_updated_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "cycle_code", name="uq_crop_cycles_farm_code"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_crop_cycles_plot_status_dates", "crop_cycles", ["plot_id", "status", "planned_start_date", "planned_end_date"])
    op.create_index("ix_crop_cycles_farm_status_start", "crop_cycles", ["farm_id", "status", "planned_start_date"])


def downgrade():
    op.drop_table("crop_cycles")
