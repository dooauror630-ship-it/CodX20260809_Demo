"""Add harvest batches.

Revision ID: 0016_harvest_batches
Revises: 0015_field_operation_inputs
Create Date: 2026-09-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0016_harvest_batches"
down_revision = "0015_field_operation_inputs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "harvest_batches",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("crop_cycle_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("harvest_no", sa.String(40), nullable=False),
        sa.Column("harvest_date", sa.Date(), nullable=False),
        sa.Column("gross_weight", sa.Numeric(14, 3), nullable=False),
        sa.Column("net_weight", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("warehouse_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("gross_weight > 0", name="ck_harvest_batches_gross_positive"),
        sa.CheckConstraint("net_weight > 0", name="ck_harvest_batches_net_positive"),
        sa.CheckConstraint("net_weight <= gross_weight", name="ck_harvest_batches_net_lte_gross"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["crop_cycle_id"], ["crop_cycles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("crop_cycle_id", "harvest_no", name="uq_harvest_batches_cycle_no"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_harvest_batches_cycle_date", "harvest_batches", ["crop_cycle_id", "harvest_date", "id"])
    op.create_index("ix_harvest_batches_farm_date", "harvest_batches", ["farm_id", "harvest_date", "id"])


def downgrade():
    op.drop_table("harvest_batches")
