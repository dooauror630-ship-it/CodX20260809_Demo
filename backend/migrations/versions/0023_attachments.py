"""Add controlled attachment metadata."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql
revision = "0023_attachments"
down_revision = "0022_workflow_audit"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("attachments", sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True), sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False), sa.Column("resource_type", sa.String(40), nullable=False), sa.Column("resource_id", mysql.BIGINT(unsigned=True)), sa.Column("original_name", sa.String(255), nullable=False), sa.Column("stored_name", sa.String(80), nullable=False), sa.Column("mime_type", sa.String(120), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("sha256", sa.String(64), nullable=False), sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"), sa.UniqueConstraint("stored_name"), mysql_charset="utf8mb4")
def downgrade(): op.drop_table("attachments")
