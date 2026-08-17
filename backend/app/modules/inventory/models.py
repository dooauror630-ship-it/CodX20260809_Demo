from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ...extensions import db
from ..auth.models import USER_ID_TYPE


class Warehouse(db.Model):
    __tablename__ = "warehouses"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_warehouses_farm_code"),
        Index("ix_warehouses_farm_active", "farm_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class ItemCategory(db.Model):
    __tablename__ = "item_categories"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_item_categories_farm_code"),
        Index("ix_item_categories_farm_active", "farm_id", "is_active"),
        Index("ix_item_categories_parent", "parent_id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("item_categories.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class Item(db.Model):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_items_farm_code"),
        CheckConstraint("safety_stock >= 0", name="ck_items_safety_stock_nonnegative"),
        Index("ix_items_farm_active", "farm_id", "is_active"),
        Index("ix_items_category", "category_id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("item_categories.id", ondelete="RESTRICT"), nullable=False
    )
    unit_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0, server_default="0")
    lot_tracking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class Supplier(db.Model):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_suppliers_farm_code"),
        Index("ix_suppliers_farm_active", "farm_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(40), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("farm_id", "order_no", name="uq_purchase_orders_farm_no"),
        CheckConstraint("total_amount >= 0", name="ck_purchase_orders_total_nonnegative"),
        Index("ix_purchase_orders_farm_status_date", "farm_id", "status", "order_date"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    order_no: Mapped[str] = mapped_column(String(30), nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", server_default="DRAFT")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_by_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class PurchaseOrderLine(db.Model):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_lines_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_purchase_lines_price_nonnegative"),
        CheckConstraint("amount >= 0", name="ck_purchase_lines_amount_nonnegative"),
        Index("ix_purchase_order_lines_order", "purchase_order_id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    lot_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class StockDocument(db.Model):
    __tablename__ = "stock_documents"
    __table_args__ = (
        UniqueConstraint("farm_id", "document_no", name="uq_stock_documents_farm_no"),
        Index("ix_stock_documents_source", "source_type", "source_id"),
        Index("ix_stock_documents_farm_type_time", "farm_id", "document_type", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    document_no: Mapped[str] = mapped_column(String(40), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_warehouse_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True
    )
    to_warehouse_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="POSTED", server_default="POSTED")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int | None] = mapped_column(USER_ID_TYPE, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())


class StockMovementLine(db.Model):
    __tablename__ = "stock_movement_lines"
    __table_args__ = (
        CheckConstraint("quantity_delta <> 0", name="ck_stock_movements_quantity_nonzero"),
        CheckConstraint("unit_cost >= 0", name="ck_stock_movements_cost_nonnegative"),
        Index("ix_stock_movements_document", "stock_document_id"),
        Index("ix_stock_movements_balance", "warehouse_id", "item_id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    stock_document_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("stock_documents.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    lot_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost_object_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cost_object_id: Mapped[int | None] = mapped_column(USER_ID_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())


class InventoryBalance(db.Model):
    __tablename__ = "inventory_balances"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "item_id", name="uq_inventory_balances_warehouse_item"),
        CheckConstraint("quantity >= 0", name="ck_inventory_balances_quantity_nonnegative"),
        CheckConstraint("average_cost >= 0", name="ck_inventory_balances_cost_nonnegative"),
        Index("ix_inventory_balances_farm", "farm_id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0, server_default="0")
    average_cost: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class InventoryCount(db.Model):
    __tablename__ = "inventory_counts"
    __table_args__ = (
        UniqueConstraint("farm_id", "count_no", name="uq_inventory_counts_farm_no"),
        Index("ix_inventory_counts_farm_status_date", "farm_id", "status", "count_date"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    count_no: Mapped[str] = mapped_column(String(40), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    count_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", server_default="DRAFT")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_by_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class InventoryCountLine(db.Model):
    __tablename__ = "inventory_count_lines"
    __table_args__ = (
        CheckConstraint("book_quantity >= 0", name="ck_inventory_count_lines_book_nonnegative"),
        CheckConstraint("actual_quantity >= 0", name="ck_inventory_count_lines_actual_nonnegative"),
        CheckConstraint("unit_cost >= 0", name="ck_inventory_count_lines_cost_nonnegative"),
        Index("ix_inventory_count_lines_count", "inventory_count_id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    inventory_count_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("inventory_counts.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False
    )
    lot_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    book_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    actual_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    difference_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0, server_default="0")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False, default=0, server_default="0")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
