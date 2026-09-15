"""Add tobacco curing batches.

Revision ID: 0017_tobacco_curing_batches
Revises: 0016_harvest_batches
Create Date: 2026-09-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0017_tobacco_curing_batches"
down_revision = "0016_harvest_batches"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tobacco_curing_batches",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("crop_cycle_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("curing_no", sa.String(40), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("input_weight", sa.Numeric(14, 3), nullable=False),
        sa.Column("output_weight", sa.Numeric(14, 3), nullable=True),
        sa.Column("unit_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("fuel_cost", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("electricity_cost", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="IN_PROGRESS", nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("completed_by_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('IN_PROGRESS', 'COMPLETED')", name="ck_tobacco_curing_batches_status"),
        sa.CheckConstraint("input_weight > 0", name="ck_tobacco_curing_batches_input_positive"),
        sa.CheckConstraint("output_weight IS NULL OR output_weight > 0", name="ck_tobacco_curing_batches_output_positive"),
        sa.CheckConstraint("output_weight IS NULL OR output_weight <= input_weight", name="ck_tobacco_curing_batches_output_lte_input"),
        sa.CheckConstraint("fuel_cost >= 0", name="ck_tobacco_curing_batches_fuel_nonnegative"),
        sa.CheckConstraint("electricity_cost >= 0", name="ck_tobacco_curing_batches_electricity_nonnegative"),
        sa.CheckConstraint("end_at IS NULL OR end_at >= start_at", name="ck_tobacco_curing_batches_dates"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["crop_cycle_id"], ["crop_cycles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["completed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crop_cycle_id", "curing_no", name="uq_tobacco_curing_batches_cycle_no"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_tobacco_curing_batches_cycle_start", "tobacco_curing_batches", ["crop_cycle_id", "start_at", "id"])
    op.create_index("ix_tobacco_curing_batches_farm_status", "tobacco_curing_batches", ["farm_id", "status", "start_at"])


def downgrade():
    op.drop_table("tobacco_curing_batches")
