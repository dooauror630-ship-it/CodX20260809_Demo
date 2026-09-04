"""Add farm tasks and audit logs."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql
revision = "0022_workflow_audit"
down_revision = "0021_sales_returns"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("farm_tasks", sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True), sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False), sa.Column("task_no", sa.String(40), nullable=False), sa.Column("title", sa.String(120), nullable=False), sa.Column("due_date", sa.Date(), nullable=False), sa.Column("status", sa.String(20), server_default="OPEN", nullable=False), sa.Column("notes", sa.Text()), sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False), sa.Column("completed_by_id", mysql.BIGINT(unsigned=True)), sa.Column("completed_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["completed_by_id"], ["users.id"], ondelete="RESTRICT"), sa.UniqueConstraint("farm_id", "task_no", name="uq_farm_tasks_farm_no"), mysql_charset="utf8mb4")
    op.create_table("audit_logs", sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True), sa.Column("farm_id", mysql.BIGINT(unsigned=True)), sa.Column("actor_id", mysql.BIGINT(unsigned=True), nullable=False), sa.Column("action", sa.String(40), nullable=False), sa.Column("resource_type", sa.String(40), nullable=False), sa.Column("resource_id", mysql.BIGINT(unsigned=True)), sa.Column("detail", sa.Text()), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"), mysql_charset="utf8mb4")
def downgrade(): op.drop_table("audit_logs"); op.drop_table("farm_tasks")
