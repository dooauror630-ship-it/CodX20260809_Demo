"""Add livestock batches and head-count movements.

Revision ID: 0010_livestock
Revises: 0009_inventory_counts
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "0010_livestock"
down_revision = "0009_inventory_counts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "livestock_batches",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("species_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("batch_no", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("updated_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], name="fk_livestock_batches_farm", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["species_id"], ["livestock_species.id"], name="fk_livestock_batches_species", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_livestock_batches_created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["users.id"], name="fk_livestock_batches_updated_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "batch_no", name="uq_livestock_batches_farm_no"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_livestock_batches_farm_status_entry",
        "livestock_batches",
        ["farm_id", "status", "entry_date"],
        unique=False,
    )

    op.create_table(
        "livestock_movements",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("batch_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("movement_no", sa.String(length=40), nullable=False),
        sa.Column("movement_type", sa.String(length=20), nullable=False),
        sa.Column("from_barn_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("to_barn_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_livestock_movements_quantity_positive"),
        sa.CheckConstraint(
            "movement_type IN ('ENTRY', 'TRANSFER', 'DEATH', 'CULL', 'EXIT')",
            name="ck_livestock_movements_type",
        ),
        sa.CheckConstraint(
            "(movement_type = 'ENTRY' AND from_barn_id IS NULL AND to_barn_id IS NOT NULL) OR "
            "(movement_type = 'TRANSFER' AND from_barn_id IS NOT NULL AND to_barn_id IS NOT NULL "
            "AND from_barn_id <> to_barn_id) OR "
            "(movement_type IN ('DEATH', 'CULL', 'EXIT') AND from_barn_id IS NOT NULL "
            "AND to_barn_id IS NULL)",
            name="ck_livestock_movements_barns",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farms.id"], name="fk_livestock_movements_farm", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["livestock_batches.id"], name="fk_livestock_movements_batch", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["from_barn_id"], ["barns.id"], name="fk_livestock_movements_from_barn", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["to_barn_id"], ["barns.id"], name="fk_livestock_movements_to_barn", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_livestock_movements_created_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("farm_id", "movement_no", name="uq_livestock_movements_farm_no"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_livestock_movements_batch_date",
        "livestock_movements",
        ["batch_id", "occurred_on", "id"],
        unique=False,
    )
    op.create_index(
        "ix_livestock_movements_farm_type_date",
        "livestock_movements",
        ["farm_id", "movement_type", "occurred_on"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_livestock_movements_farm_type_date", table_name="livestock_movements")
    op.drop_index("ix_livestock_movements_batch_date", table_name="livestock_movements")
    op.drop_table("livestock_movements")
    op.drop_index("ix_livestock_batches_farm_status_entry", table_name="livestock_batches")
    op.drop_table("livestock_batches")
