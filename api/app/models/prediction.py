"""The pre-commitment ledger (Phase E5) — `predictions`.

A prediction is a call (bias · DOL · model · target) committed and SERVER-stamped
BEFORE the outcome is revealed, then scored against what actually happened. See
concepts/architecture/learning-enforcement.md §9 and the Alembic `0011` docstring,
which owns the DDL of record.

Three things about this model are deliberate and load-bearing:

* **`committed_at` has no Python default.** It is `server_default=now()` and is
  never accepted from a request, so the timestamp cannot be chosen by the thing
  being timestamped.
* **The call columns are frozen by a DB trigger**, not by application discipline
  (`predictions_freeze_the_call`). There is no code path — present or future —
  that can edit a call after commit.
* **There is NO `is_deleted`.** Every other user table here soft-deletes; this one
  cannot, because the calibration score is a ratio and the way to inflate a ratio
  is to delete your failures. The denominator only grows.

This table mints NO reps. `reps` stays derived from `evidence_assets.reps_claimed`
(E2), so invariant 5 — "`reps` gets strictly harder to satisfy, never easier" —
gains no new write path here.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import EntryModel, PredictionBias, pg_enum


class Prediction(Base):
    """One committed-before-the-reveal call, and (later) what actually happened."""

    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # TEXT soft ref to drills.drill_ref (e.g. "ict-course T-01") — not a hard FK,
    # so a commitment survives a `drills` re-seed.
    drill_ref: Mapped[str] = mapped_column(Text, nullable=False)
    session_label: Mapped[str] = mapped_column(Text, nullable=False)
    instrument: Mapped[str | None] = mapped_column(Text)

    # ---- THE CALL — frozen at commit by the 0011 trigger --------------------
    bias: Mapped[PredictionBias] = mapped_column(
        pg_enum(PredictionBias, "prediction_bias"), nullable=False
    )
    dol: Mapped[str] = mapped_column(Text, nullable=False)
    entry_model: Mapped[EntryModel] = mapped_column(
        pg_enum(EntryModel, "entry_model"), nullable=False
    )
    target: Mapped[str] = mapped_column(Text, nullable=False)

    # SERVER-stamped. No Python-side default on purpose — see the module docstring.
    committed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ---- THE REVEAL — written once, strictly later --------------------------
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_bias: Mapped[PredictionBias | None] = mapped_column(
        pg_enum(PredictionBias, "prediction_bias")
    )
    dol_hit: Mapped[bool | None] = mapped_column(Boolean)
    model_played_out: Mapped[bool | None] = mapped_column(Boolean)
    target_hit: Mapped[bool | None] = mapped_column(Boolean)
    resolution_notes: Mapped[str | None] = mapped_column(Text)

    # The marked chart captured WITH the call. A link, never a rep.
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_assets.id")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None
