import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DrillProgress(Base):
    """The per-user drill tracker, one active row per (user, drill_ref).

    User-scoped + soft-deleted, mirroring `concept_progress`. `drill_ref` is a
    TEXT soft ref (matching drills.drill_ref / concepts.drill_refs) — NOT a hard
    FK, so a mark can outlive a re-seed. `hand_done` / `tool_done` are the
    ✋ hand-marking / 🛠 tool-assisted variant marks.
    """

    __tablename__ = "drill_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    drill_ref: Mapped[str] = mapped_column(Text, nullable=False)  # soft ref → drills.drill_ref

    reps: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    hand_done: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    tool_done: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    last_practiced: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
