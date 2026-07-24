import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import UStage, pg_enum


class Concept(Base):
    """One gradable concept on a track's learning path (5e-1b: multi-track).

    Seed data (not user-editable), sourced from the per-track learning-path +
    exercise pages via scripts/seed_concepts.py. The live per-user grid lives in
    `concept_progress`.

    Multi-track (5e-1b): every concept belongs to exactly one `track`
    (aura | ict_course | unified) and one per-track stage (`stage_code` /
    `stage_order`, e.g. A1 / M2 / U1) — a concept taught by two mentors is
    DUPLICATED across tracks on purpose (more reps + a second explanation).
    `cross_refs` are the equivalent concept slugs in the OTHER tracks
    (display-only "Also taught in …"; never merges progress). `u_stage` is now
    UNIFIED-ONLY (nullable) — it still drives the frontier CHECK, the
    content_pages join, and the unified exit bars.

    `content_slug` and `drill_refs` are deliberately SOFT references — a
    nullable slug + a TEXT[] of drill IDs — NOT hard FKs. `content_pages` is
    empty until the 5d ingest and drill IDs live in the wiki, so a hard FK
    would break the seed.
    """

    __tablename__ = "concepts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(16))  # e.g. "U1.3"

    # Multi-track (5e-1b) — the (track, stage_code) grouping key.
    track: Mapped[str] = mapped_column(String(16), nullable=False, server_default="unified")
    stage_code: Mapped[str | None] = mapped_column(String(16))  # A1 / M2 / U1
    stage_order: Mapped[int | None] = mapped_column()  # SMALLINT — stage position
    cross_refs: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # equivalent slugs (other tracks)

    # Unified-only (nullable): frontier CHECK + content join + unified exit bars.
    u_stage: Mapped[UStage | None] = mapped_column(pg_enum(UStage, "u_stage"))
    title: Mapped[str] = mapped_column(Text, nullable=False)

    # Core = part of the established U1–U4 playbook the gate requires at
    # Backtested+. Frontier (U5) is NEVER core (enforced by a CHECK constraint).
    is_core: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Frontier-only provenance (nullable elsewhere): source tier + label.
    tier: Mapped[str | None] = mapped_column(String(32))  # "Tier 1" / "Tier 2-3" / ...
    label: Mapped[str | None] = mapped_column(String(32))  # ESTABLISHED / EMERGING / SPECULATIVE
    axis: Mapped[str | None] = mapped_column(String(16))  # WHERE / WHEN / DIRECTION / CONFIRM / STACK

    # Study-and-watch flag: watch_only concepts may never count toward the
    # Readiness-to-Live Gate (all frontier U5 rows are watch-only here).
    watch_only: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    rep_target: Mapped[str | None] = mapped_column(Text)  # freetext target ("≥50 ranges")
    content_slug: Mapped[str | None] = mapped_column(String(128))  # soft ref → content_pages.slug
    drill_refs: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # soft refs, e.g. ["aura D1-a"]
    sort_order: Mapped[int] = mapped_column(nullable=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
