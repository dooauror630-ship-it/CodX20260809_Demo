"""Add field operation records for crop cycles.

Revision ID: 0014_field_operations
Revises: 0013_crop_cycles
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "0014_field_operations"
down_revision = "0013_crop_cycles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "field_operations",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("crop_cycle_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("operation_type", sa.String(length=24), nullable=False),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("area_mu", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("labor_hours", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("machine_hours", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("labor_cost", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False),
        sa.Column("service_cost", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "operation_type IN ('LAND_PREPARATION', 'SOWING', 'TRANSPLANTING', 'IRRIGATION', 'FERTILIZATION', 'PEST_CONTROL', 'WEEDING', 'OTHER')",
            name="ck_field_operations_type",
        ),
        sa.CheckConstraint("area_mu > 0", name="ck_field_operations_area_positive"),
        sa.CheckConstraint("labor_hours >= 0", name="ck_field_operations_labor_hours_nonnegative"),
        sa.CheckConstraint("machine_hours >= 0", name="ck_field_operations_machine_hours_nonnegative"),
        sa.CheckConstraint("labor_cost >= 0", name="ck_field_operations_labor_cost_nonnegative"),
        sa.CheckConstraint("service_cost >= 0", name="ck_field_operations_service_cost_nonnegative"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_field_operations_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["crop_cycle_id"], ["crop_cycles.id"], name="fk_field_operations_cycle", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_field_operations_created_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_field_operations_cycle_date", "field_operations", ["crop_cycle_id", "operation_date", "id"])
    op.create_index("ix_field_operations_farm_date", "field_operations", ["farm_id", "operation_date", "id"])


def downgrade():
    op.drop_table("field_operations")
