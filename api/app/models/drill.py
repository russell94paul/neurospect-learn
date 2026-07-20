import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Drill(Base):
    """One drill in the catalog — a projection of the two wiki exercise
    libraries' "Drill → concept → ladder-stage map" tables, seeded by
    scripts/seed_drills.py. Seed/content (not user-editable), no soft-delete
    (re-seed replaces), mirroring `concepts`.

    `drill_ref` is the stable identity (e.g. "aura D1-b", "ict-course D3-b") and
    matches the convention in `concepts.drill_refs`; `drill_progress.drill_ref`
    is a soft ref to it. `concept_slugs` is a soft back-link to `concepts.slug`
    (the concepts this drill advances), derived at seed time from the concept
    seed's drill_refs — never a hard FK.
    """

    __tablename__ = "drills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    drill_ref: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    track: Mapped[str] = mapped_column(String(16), nullable=False)  # aura | ict_course
    stage_code: Mapped[str | None] = mapped_column(String(16))  # track stage, e.g. "1"
    title: Mapped[str] = mapped_column(Text, nullable=False)  # the map's Concept col
    advances_to: Mapped[str | None] = mapped_column(String(64))  # e.g. "Can-mark"
    rep_target: Mapped[str | None] = mapped_column(Text)  # freetext, canonical
    concept_slugs: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # soft back-link
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("track IN ('aura', 'ict_course')", name="ck_drills_track"),
    )
