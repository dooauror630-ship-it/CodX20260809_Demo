"""Add sales return documents."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0021_sales_returns"
down_revision = "0020_trade_sales"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("sales_returns",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("farm_id", mysql.BIGINT(unsigned=True), nullable=False), sa.Column("return_no", sa.String(30), nullable=False),
        sa.Column("sales_order_id", mysql.BIGINT(unsigned=True), nullable=False), sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="POSTED", nullable=False), sa.Column("total_amount", sa.Numeric(16,2), server_default="0", nullable=False),
        sa.Column("created_by_id", mysql.BIGINT(unsigned=True), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"), sa.UniqueConstraint("farm_id", "return_no", name="uq_sales_returns_farm_no"), mysql_charset="utf8mb4")
    op.create_table("sales_return_lines",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("sales_return_id", mysql.BIGINT(unsigned=True), nullable=False), sa.Column("sales_order_line_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("quantity", sa.Numeric(14,3), nullable=False), sa.Column("amount", sa.Numeric(16,2), nullable=False), sa.Column("unit_cost", sa.Numeric(16,4), nullable=False),
        sa.ForeignKeyConstraint(["sales_return_id"], ["sales_returns.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["sales_order_line_id"], ["sales_order_lines.id"], ondelete="RESTRICT"), sa.UniqueConstraint("sales_return_id", "sales_order_line_id", name="uq_sales_return_lines_line"), mysql_charset="utf8mb4")

def downgrade():
    op.drop_table("sales_return_lines")
    op.drop_table("sales_returns")
