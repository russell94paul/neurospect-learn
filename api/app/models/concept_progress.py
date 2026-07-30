import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ConceptProgress(Base):
    """The live tracker grid, one row per (user, concept) — the tracker.md grid
    made editable. Stage/gate status (U0–U6 cleared?) is DERIVED (not stored)
    from the concepts in each stage meeting their exit bar.

    User-scoped + soft-deleted. `concept_progress` rows are created per-user at
    runtime (later phases) — the seed only populates `concepts`.
    """

    __tablename__ = "concept_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id"), nullable=False
    )

    # Ladder 1 Learned → 2 Can-mark → 3 Backtested → 4 Live-ready. NULL = unclaimed.
    ladder_stage: Mapped[int | None] = mapped_column(SmallInteger)
    # Confidence 1 (no feel) … 5 (automatic). NULL = unclaimed.
    confidence: Mapped[int | None] = mapped_column(SmallInteger)
    # Reps claimed BEFORE the evidence layer existed (Phase E2, Alembic 0009).
    # Frozen: nothing writes this column any more. The API's `reps` is DERIVED —
    # `legacy_reps + SUM(evidence_assets.reps_claimed)` — so a rep cannot be
    # minted by any endpoint. Renamed rather than dropped so no already-met stage
    # un-meets (progress stays monotonic) and the pre-evidence gap stays visible.
    legacy_reps: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_practiced: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
