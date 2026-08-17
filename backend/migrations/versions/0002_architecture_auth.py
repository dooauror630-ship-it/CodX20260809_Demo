"""Add account state and update timestamp.

Revision ID: 0002_architecture_auth
Revises: 0001_auth_baseline
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_architecture_auth"
down_revision = "0001_auth_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade():
    op.drop_column("users", "updated_at")
    op.drop_column("users", "is_active")
