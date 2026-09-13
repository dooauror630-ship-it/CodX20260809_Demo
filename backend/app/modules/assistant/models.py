from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ...extensions import db
from ..auth.models import USER_ID_TYPE


class AgentConfirmationNonce(db.Model):
    __tablename__ = "agent_confirmation_nonces"
    __table_args__ = (
        UniqueConstraint("nonce", name="uq_agent_confirmation_nonces_nonce"),
        Index("ix_agent_confirmation_nonces_resource", "farm_id", "resource_id"),
    )

    id: Mapped[int] = mapped_column(USER_ID_TYPE, primary_key=True, autoincrement=True)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    farm_id: Mapped[int] = mapped_column(USER_ID_TYPE, ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[int] = mapped_column(USER_ID_TYPE, nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.current_timestamp())
