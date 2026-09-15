"""Persist consumed agent confirmation nonces."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "0024_agent_confirmation_nonces"
down_revision = "0023_attachments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_confirmation_nonces",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("resource_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("used_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("nonce", name="uq_agent_confirmation_nonces_nonce"),
        mysql_charset="utf8mb4",
    )
    op.create_index(
        "ix_agent_confirmation_nonces_resource",
        "agent_confirmation_nonces",
        ["farm_id", "resource_id"],
    )


def downgrade():
    op.drop_index("ix_agent_confirmation_nonces_resource", table_name="agent_confirmation_nonces")
    op.drop_table("agent_confirmation_nonces")
