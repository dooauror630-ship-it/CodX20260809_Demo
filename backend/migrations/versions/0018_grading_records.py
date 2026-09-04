"""Add harvest grading records.

Revision ID: 0018_grading_records
Revises: 0017_tobacco_curing_batches
Create Date: 2026-09-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0018_grading_records"
down_revision = "0017_tobacco_curing_batches"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "grading_records",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("harvest_batch_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("grade_code", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price_reference", sa.Numeric(16, 4), server_default="0", nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_grading_records_quantity_positive"),
        sa.CheckConstraint("unit_price_reference >= 0", name="ck_grading_records_price_nonnegative"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["harvest_batch_id"], ["harvest_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("harvest_batch_id", "grade_code", name="uq_grading_records_harvest_grade"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_grading_records_harvest", "grading_records", ["harvest_batch_id", "id"])
    op.create_index("ix_grading_records_farm_grade", "grading_records", ["farm_id", "grade_code"])


def downgrade():
    op.drop_table("grading_records")
