from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ...extensions import db
from ..auth.models import USER_ID_TYPE


class Customer(db.Model):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_customers_farm_code"),
        Index("ix_customers_farm_active", "farm_id", "is_active"),
    )
    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(40), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="1", nullable=False)
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=datetime.now, nullable=False
    )


class SalesOrder(db.Model):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("farm_id", "order_no", name="uq_sales_orders_farm_no"),
        CheckConstraint("total_amount >= 0", name="ck_sales_orders_total_nonnegative"),
        CheckConstraint(
            "received_amount >= 0 AND received_amount <= total_amount", name="ck_sales_orders_received_range"
        ),
        Index("ix_sales_orders_farm_status_date", "farm_id", "status", "sale_date"),
    )
    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    order_no: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT", nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, server_default="0", nullable=False)
    received_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, server_default="0", nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_by_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class SalesOrderLine(db.Model):
    __tablename__ = "sales_order_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sales_lines_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_sales_lines_price_nonnegative"),
        Index("ix_sales_order_lines_order", "sales_order_id"),
    )
    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    sales_order_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 4), default=0, server_default="0", nullable=False)


class Payment(db.Model):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("farm_id", "payment_no", name="uq_payments_farm_no"),
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        Index("ix_payments_farm_date", "farm_id", "business_date"),
    )
    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    payment_no: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True
    )
    sales_order_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class SalesReturn(db.Model):
    __tablename__ = "sales_returns"
    __table_args__ = (UniqueConstraint("farm_id", "return_no", name="uq_sales_returns_farm_no"),)
    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    return_no: Mapped[str] = mapped_column(String(30), nullable=False)
    sales_order_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=False)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="POSTED", server_default="POSTED", nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, server_default="0", nullable=False)
    created_by_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class SalesReturnLine(db.Model):
    __tablename__ = "sales_return_lines"
    __table_args__ = (UniqueConstraint("sales_return_id", "sales_order_line_id", name="uq_sales_return_lines_line"),)
    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    sales_return_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("sales_returns.id", ondelete="CASCADE"), nullable=False)
    sales_order_line_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("sales_order_lines.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
