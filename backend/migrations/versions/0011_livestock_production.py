"""Add livestock health and weight production records.

Revision ID: 0011_livestock_production
Revises: 0010_livestock
Create Date: 2026-08-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "0011_livestock_production"
down_revision = "0010_livestock"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "livestock_health_records",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("batch_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("record_no", sa.String(length=40), nullable=False),
        sa.Column("record_type", sa.String(length=20), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("medicine_name", sa.String(length=120), nullable=True),
        sa.Column("dosage", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "record_type IN ('VACCINATION', 'MEDICATION', 'DISEASE', 'OTHER')",
            name="ck_livestock_health_records_type",
        ),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_livestock_health_records_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["batch_id"], ["livestock_batches.id"], name="fk_livestock_health_records_batch", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_livestock_health_records_created_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "record_no", name="uq_livestock_health_records_farm_no"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_livestock_health_records_batch_date", "livestock_health_records", ["batch_id", "occurred_on", "id"])

    op.create_table(
        "livestock_weight_records",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("batch_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("record_no", sa.String(length=40), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("average_weight", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("sample_count > 0", name="ck_livestock_weight_records_sample_count_positive"),
        sa.CheckConstraint("average_weight > 0", name="ck_livestock_weight_records_average_weight_positive"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_livestock_weight_records_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["batch_id"], ["livestock_batches.id"], name="fk_livestock_weight_records_batch", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_livestock_weight_records_created_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "record_no", name="uq_livestock_weight_records_farm_no"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_livestock_weight_records_batch_date", "livestock_weight_records", ["batch_id", "occurred_on", "id"])


def downgrade():
    op.drop_index("ix_livestock_weight_records_batch_date", table_name="livestock_weight_records")
    op.drop_table("livestock_weight_records")
    op.drop_index("ix_livestock_health_records_batch_date", table_name="livestock_health_records")
    op.drop_table("livestock_health_records")
