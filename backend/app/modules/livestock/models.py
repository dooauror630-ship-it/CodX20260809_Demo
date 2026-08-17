from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ...extensions import db
from ..auth.models import USER_ID_TYPE


class LivestockBatch(db.Model):
    __tablename__ = "livestock_batches"
    __table_args__ = (
        UniqueConstraint("farm_id", "batch_no", name="uq_livestock_batches_farm_no"),
        Index("ix_livestock_batches_farm_status_entry", "farm_id", "status", "entry_date"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    species_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("livestock_species.id", ondelete="RESTRICT"), nullable=False
    )
    batch_no: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", server_default="ACTIVE")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
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


class LivestockMovement(db.Model):
    __tablename__ = "livestock_movements"
    __table_args__ = (
        UniqueConstraint("farm_id", "movement_no", name="uq_livestock_movements_farm_no"),
        CheckConstraint("quantity > 0", name="ck_livestock_movements_quantity_positive"),
        CheckConstraint(
            "movement_type IN ('ENTRY', 'TRANSFER', 'DEATH', 'CULL', 'EXIT')",
            name="ck_livestock_movements_type",
        ),
        CheckConstraint(
            "(movement_type = 'ENTRY' AND from_barn_id IS NULL AND to_barn_id IS NOT NULL) OR "
            "(movement_type = 'TRANSFER' AND from_barn_id IS NOT NULL AND to_barn_id IS NOT NULL "
            "AND from_barn_id <> to_barn_id) OR "
            "(movement_type IN ('DEATH', 'CULL', 'EXIT') AND from_barn_id IS NOT NULL "
            "AND to_barn_id IS NULL)",
            name="ck_livestock_movements_barns",
        ),
        Index("ix_livestock_movements_batch_date", "batch_id", "occurred_on", "id"),
        Index("ix_livestock_movements_farm_type_date", "farm_id", "movement_type", "occurred_on"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    batch_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("livestock_batches.id", ondelete="RESTRICT"), nullable=False
    )
    movement_no: Mapped[str] = mapped_column(String(40), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    from_barn_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("barns.id", ondelete="RESTRICT"), nullable=True
    )
    to_barn_id: Mapped[int | None] = mapped_column(
        USER_ID_TYPE, ForeignKey("barns.id", ondelete="RESTRICT"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
