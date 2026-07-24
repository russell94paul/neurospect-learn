import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StudyPreferences(Base):
    """The Study-Planner availability + pacing prefs (Phase 5e-2).

    User-scoped + soft-deleted, ONE active row per user (partial-unique
    `(user_id) WHERE NOT is_deleted`), mirroring `concept_progress`. Edited by
    the `/plan/setup` UI (5e-3); consumed by the deterministic scheduler.

    `mon_minutes … sun_minutes` are the per-weekday minute budget (0 = day off).
    `max_session_minutes` caps a single block. `timezone` is load-bearing —
    "today"/day-of-week matter to the ICT curriculum. `target_go_live_date` is
    PACING-ONLY: it drives the ETA / on-pace flag and NEVER advances a gate or
    unlocks a stage (the Readiness-to-Live Gate stays evidence-based).
    `active_track` names which of the three graded tracks the planner schedules.
    """

    __tablename__ = "study_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")

    # Per-weekday minute budget (0 = day off). Mon..Sun (Python weekday() 0..6).
    mon_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    tue_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    wed_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    thu_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    fri_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    sat_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    sun_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")

    max_session_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="60"
    )
    blackout_dates: Mapped[list[date] | None] = mapped_column(ARRAY(Date))
    target_go_live_date: Mapped[date | None] = mapped_column(Date)  # PACING-ONLY

    active_track: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="aura"
    )  # aura | ict_course | unified

    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
