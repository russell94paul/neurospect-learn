import uuid
from datetime import datetime

from sqlalchemy import DateTime, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TrackStage(Base):
    """Per-track stage metadata (5e-1b) — one row per (track, stage).

    Seed/content (no soft-delete, like `concepts`/`drills`; re-seed replaces).
    Holds the title/summary/gate_text the `/path/:track/:stage` curriculum unit
    renders. The stage's concepts and drills are resolved by GROUPING
    (concepts WHERE track=? AND stage_code=?), not stored here — see
    learning-platform.md §Multi-track data model.

    Sourced from the per-track learning-path pages via scripts/seed_tracks.py:
      - aura        A0–A6  (concepts/mastery/aura/learning-path.md)
      - ict_course  M0–M8  (concepts/mastery/ict-course/exercises.md)
      - unified     U0–U6  (concepts/mastery/unified/learning-path.md)
    """

    __tablename__ = "track_stages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    track: Mapped[str] = mapped_column(String(16), nullable=False)  # aura|ict_course|unified
    stage_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stage_code: Mapped[str] = mapped_column(String(16), nullable=False)  # A1 / M2 / U1
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    gate_text: Mapped[str | None] = mapped_column(Text)  # the descriptive exit bar

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
