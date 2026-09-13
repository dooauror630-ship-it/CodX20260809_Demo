"""Add optimistic versioning for stock document drafts."""

import sqlalchemy as sa
from alembic import op


revision = "0025_stock_document_versions"
down_revision = "0024_agent_confirmation_nonces"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stock_documents", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    op.drop_column("stock_documents", "version")
