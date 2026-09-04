from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ...extensions import db
from ..auth.models import USER_ID_TYPE


class FarmTask(db.Model):
    __tablename__ = "farm_tasks"
    __table_args__ = (UniqueConstraint("farm_id", "task_no", name="uq_farm_tasks_farm_no"), Index("ix_farm_tasks_farm_status_due", "farm_id", "status", "due_date"))
    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    task_no: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", server_default="OPEN", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    completed_by_id: Mapped[int | None] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_farm_time", "farm_id", "created_at"),)
    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int | None] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=True)
    actor_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(USER_ID_TYPE, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)


class Attachment(db.Model):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_resource", "farm_id", "resource_type", "resource_id"),)
    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(USER_ID_TYPE, nullable=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), nullable=False)
