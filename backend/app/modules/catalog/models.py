from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


class Unit(db.Model):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("code", name="uq_units_code"),
        CheckConstraint("base_factor > 0", name="ck_units_base_factor_positive"),
        CheckConstraint("scale >= 0 AND scale <= 6", name="ck_units_scale_range"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    base_factor: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    scale: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class LivestockSpecies(db.Model):
    __tablename__ = "livestock_species"
    __table_args__ = (UniqueConstraint("code", name="uq_livestock_species_code"),)

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    tracking_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="BATCH", server_default="BATCH"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class CropType(db.Model):
    __tablename__ = "crop_types"
    __table_args__ = (UniqueConstraint("code", name="uq_crop_types_code"),)

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=datetime.now,
    )


class CropVariety(db.Model):
    __tablename__ = "crop_varieties"
    __table_args__ = (
        UniqueConstraint("crop_type_id", "code", name="uq_crop_varieties_type_code"),
        Index("ix_crop_varieties_type_active", "crop_type_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    crop_type_id: Mapped[int] = mapped_column(
        USER_ID_TYPE, ForeignKey("crop_types.id", ondelete="RESTRICT"), nullable=False
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
