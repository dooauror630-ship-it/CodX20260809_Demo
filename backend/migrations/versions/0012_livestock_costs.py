"""Add auditable livestock batch cost entries.

Revision ID: 0012_livestock_costs
Revises: 0011_livestock_production
Create Date: 2026-09-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "0012_livestock_costs"
down_revision = "0011_livestock_production"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cost_entries",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("livestock_batch_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("entry_no", sa.String(length=40), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("cost_type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="POSTED", nullable=False),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_by_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "cost_type IN ('ENTRY', 'LABOR', 'OVERHEAD', 'OTHER')",
            name="ck_cost_entries_type",
        ),
        sa.CheckConstraint("status IN ('POSTED', 'CANCELLED')", name="ck_cost_entries_status"),
        sa.CheckConstraint("amount > 0", name="ck_cost_entries_amount_positive"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_cost_entries_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["livestock_batch_id"],
            ["livestock_batches.id"],
            name="fk_cost_entries_livestock_batch",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_id"], ["users.id"], name="fk_cost_entries_cancelled_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_cost_entries_created_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "entry_no", name="uq_cost_entries_farm_no"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_cost_entries_livestock_batch_date",
        "cost_entries",
        ["livestock_batch_id", "business_date", "id"],
    )


def downgrade():
    op.drop_table("cost_entries")
