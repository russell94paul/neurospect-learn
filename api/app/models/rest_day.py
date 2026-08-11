"""Declared rest days (Phase E6) — a day off booked BEFORE it happened.

Alembic `0012` owns the DDL of record and the reasoning; this is the mapping.

Two things about this table are unusual, and both are deliberate:

* **No `is_deleted`.** Like `predictions` (E5), and for a related reason: a rest
  day's only effect is that it does not BREAK a streak, so the record is worth
  reading only if the declared set is the set actually committed to in advance.
  Append-only keeps "what did you book, and when" answerable.
* **`declared_at` is server-stamped and frozen**, and a `rest_date` in the past is
  refused by `trg_rest_days_declared_in_advance`. That trigger IS the mechanic —
  see concepts/architecture/learning-enforcement.md §6 on why a retroactive
  streak freeze would make the streak unreadable.

NOT to be confused with `study_preferences.blackout_dates`, which tells the
SCHEDULER not to plan work on a date (Phase 5e-2). That column is rewritten
wholesale on every `PUT /api/preferences`, accepts past dates, and records nothing
about when a date was added — so it cannot carry the in-advance property and is
left alone by E6.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RestDay(Base):
    """One day this user booked off, ahead of time."""

    __tablename__ = "rest_days"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    rest_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

    # SERVER-STAMPED, never client-supplied (a 422 names the field), never
    # updatable. The comparison `rest_date >= declared_at` is the whole mechanic.
    declared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
