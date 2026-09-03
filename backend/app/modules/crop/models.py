from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ...extensions import db
from ..auth.models import USER_ID_TYPE


class CropCycle(db.Model):
    __tablename__ = "crop_cycles"
    __table_args__ = (
        UniqueConstraint("farm_id", "cycle_code", name="uq_crop_cycles_farm_code"),
        CheckConstraint(
            "status IN ('PLANNED', 'ACTIVE', 'HARVESTING', 'CLOSED', 'CANCELLED')",
            name="ck_crop_cycles_status",
        ),
        CheckConstraint("area_mu > 0", name="ck_crop_cycles_area_positive"),
        CheckConstraint("planned_end_date >= planned_start_date", name="ck_crop_cycles_planned_dates"),
        CheckConstraint(
            "actual_end_date IS NULL OR actual_start_date IS NOT NULL",
            name="ck_crop_cycles_actual_start_before_end",
        ),
        CheckConstraint(
            "actual_end_date IS NULL OR actual_end_date >= actual_start_date",
            name="ck_crop_cycles_actual_dates",
        ),
        Index("ix_crop_cycles_plot_status_dates", "plot_id", "status", "planned_start_date", "planned_end_date"),
        Index("ix_crop_cycles_farm_status_start", "farm_id", "status", "planned_start_date"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    cycle_code: Mapped[str] = mapped_column(String(40), nullable=False)
    plot_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("plots.id", ondelete="RESTRICT"), nullable=False)
    crop_type_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("crop_types.id", ondelete="RESTRICT"), nullable=False
    )
    variety_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("crop_varieties.id", ondelete="RESTRICT"), nullable=False
    )
    area_mu: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PLANNED", server_default="PLANNED")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=datetime.now
    )


class FieldOperation(db.Model):
    __tablename__ = "field_operations"
    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('LAND_PREPARATION', 'SOWING', 'TRANSPLANTING', 'IRRIGATION', 'FERTILIZATION', 'PEST_CONTROL', 'WEEDING', 'OTHER')",
            name="ck_field_operations_type",
        ),
        CheckConstraint("area_mu > 0", name="ck_field_operations_area_positive"),
        CheckConstraint("labor_hours >= 0", name="ck_field_operations_labor_hours_nonnegative"),
        CheckConstraint("machine_hours >= 0", name="ck_field_operations_machine_hours_nonnegative"),
        CheckConstraint("labor_cost >= 0", name="ck_field_operations_labor_cost_nonnegative"),
        CheckConstraint("service_cost >= 0", name="ck_field_operations_service_cost_nonnegative"),
        Index("ix_field_operations_cycle_date", "crop_cycle_id", "operation_date", "id"),
        Index("ix_field_operations_farm_date", "farm_id", "operation_date", "id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    crop_cycle_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("crop_cycles.id", ondelete="RESTRICT"), nullable=False
    )
    operation_type: Mapped[str] = mapped_column(String(24), nullable=False)
    operation_date: Mapped[date] = mapped_column(Date, nullable=False)
    area_mu: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    labor_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    machine_hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    service_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())


class FieldOperationInput(db.Model):
    __tablename__ = "field_operation_inputs"
    __table_args__ = (
        UniqueConstraint("stock_document_id", name="uq_field_operation_inputs_stock_document"),
        CheckConstraint("quantity > 0", name="ck_field_operation_inputs_quantity_positive"),
        CheckConstraint("amount >= 0", name="ck_field_operation_inputs_amount_nonnegative"),
        Index("ix_field_operation_inputs_operation", "field_operation_id", "id"),
        Index("ix_field_operation_inputs_farm", "farm_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    field_operation_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("field_operations.id", ondelete="RESTRICT"), nullable=False
    )
    stock_document_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("stock_documents.id", ondelete="RESTRICT"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    created_by_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())


class HarvestBatch(db.Model):
    __tablename__ = "harvest_batches"
    __table_args__ = (
        UniqueConstraint("crop_cycle_id", "harvest_no", name="uq_harvest_batches_cycle_no"),
        CheckConstraint("gross_weight > 0", name="ck_harvest_batches_gross_positive"),
        CheckConstraint("net_weight > 0", name="ck_harvest_batches_net_positive"),
        CheckConstraint("net_weight <= gross_weight", name="ck_harvest_batches_net_lte_gross"),
        Index("ix_harvest_batches_cycle_date", "crop_cycle_id", "harvest_date", "id"),
        Index("ix_harvest_batches_farm_date", "farm_id", "harvest_date", "id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    crop_cycle_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("crop_cycles.id", ondelete="RESTRICT"), nullable=False)
    harvest_no: Mapped[str] = mapped_column(String(40), nullable=False)
    harvest_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross_weight: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    net_weight: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("units.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())


class TobaccoCuringBatch(db.Model):
    __tablename__ = "tobacco_curing_batches"
    __table_args__ = (
        UniqueConstraint("crop_cycle_id", "curing_no", name="uq_tobacco_curing_batches_cycle_no"),
        CheckConstraint("status IN ('IN_PROGRESS', 'COMPLETED')", name="ck_tobacco_curing_batches_status"),
        CheckConstraint("input_weight > 0", name="ck_tobacco_curing_batches_input_positive"),
        CheckConstraint("output_weight IS NULL OR output_weight > 0", name="ck_tobacco_curing_batches_output_positive"),
        CheckConstraint("output_weight IS NULL OR output_weight <= input_weight", name="ck_tobacco_curing_batches_output_lte_input"),
        CheckConstraint("fuel_cost >= 0", name="ck_tobacco_curing_batches_fuel_nonnegative"),
        CheckConstraint("electricity_cost >= 0", name="ck_tobacco_curing_batches_electricity_nonnegative"),
        CheckConstraint("end_at IS NULL OR end_at >= start_at", name="ck_tobacco_curing_batches_dates"),
        Index("ix_tobacco_curing_batches_cycle_start", "crop_cycle_id", "start_at", "id"),
        Index("ix_tobacco_curing_batches_farm_status", "farm_id", "status", "start_at"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    crop_cycle_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("crop_cycles.id", ondelete="RESTRICT"), nullable=False)
    curing_no: Mapped[str] = mapped_column(String(40), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    input_weight: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    output_weight: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("units.id", ondelete="RESTRICT"), nullable=False)
    fuel_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    electricity_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="IN_PROGRESS", server_default="IN_PROGRESS")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    completed_by_id: Mapped[int | None] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
