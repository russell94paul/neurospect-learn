"""The evidence layer (Phase E2) — `evidence_assets` + `evidence_grades`.

ONE polymorphic table serves all four subjects (drill · concept · journal entry ·
missed trade), which is the whole reason the design rejected the per-owner child
tables `neurospect-api` used. See concepts/architecture/learning-enforcement.md
§7 and the Alembic `0009` docstring, which own the DDL of record.

`evidence_grades` is append-only in spirit: ONE ROW PER GRADING PASS, so a
re-grade adds a row rather than mutating a verdict. E2 writes only the
`deterministic` grader.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import (
    EvidenceGradeState,
    EvidenceGrader,
    EvidenceKind,
    EvidenceSubject,
    pg_enum,
)


class EvidenceAsset(Base):
    """One captured piece of evidence of the work, attached to exactly one subject.

    `subject_drill_ref` is a TEXT soft ref (matching `drill_progress.drill_ref` /
    `concepts.drill_refs`) — NOT a hard FK, so evidence survives a re-seed. The
    exactly-one-subject rule is enforced by a DB CHECK that fails closed.

    `reps_claimed` is what this asset counts for; the API's derived `reps` is
    `legacy_reps + SUM(reps_claimed)`. No endpoint writes a rep directly.
    """

    __tablename__ = "evidence_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    subject_type: Mapped[EvidenceSubject] = mapped_column(
        pg_enum(EvidenceSubject, "evidence_subject"), nullable=False
    )
    subject_drill_ref: Mapped[str | None] = mapped_column(Text)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id")
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id")
    )
    missed_trade_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("missed_trades.id")
    )

    kind: Mapped[EvidenceKind] = mapped_column(
        pg_enum(EvidenceKind, "evidence_kind"), nullable=False
    )

    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    perceptual_hash: Mapped[str | None] = mapped_column(String(64))

    # User-asserted capture time (back-dating is SURFACED, never blocked — E6).
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reps_claimed: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvidenceGrade(Base):
    """One grading PASS over one evidence asset. Additive, never destructive.

    A grade may FLAG but never retracts a rep: `stages.py` and `gate.py` read
    reps, so retraction would make progress non-monotonic (a met stage could
    un-meet, a Gate verdict could flip backwards with no user action).
    """

    __tablename__ = "evidence_grades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_assets.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    grader: Mapped[EvidenceGrader] = mapped_column(
        pg_enum(EvidenceGrader, "evidence_grader"), nullable=False
    )
    state: Mapped[EvidenceGradeState] = mapped_column(
        pg_enum(EvidenceGradeState, "evidence_grade_state"), nullable=False
    )
    # ADVISORY only. Never writes confidence or ladder_stage (invariant 7).
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    rubric_slug: Mapped[str | None] = mapped_column(Text)
    rubric_version: Mapped[int | None] = mapped_column(Integer)
    findings: Mapped[dict | list | None] = mapped_column(JSONB)

    # Model / cost telemetry (E4 fills these; E2 leaves them null).
    model: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
