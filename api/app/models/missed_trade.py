import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import (
    EntryModel,
    HypotheticalOutcome,
    MissType,
    SessionType,
    pg_enum,
)


class MissedTrade(Base):
    """The missed / canceled trade log (Phase 6b) — one row per setup NOT taken.

    A deliberately separate table from `journal_entries` so executed-trade
    analytics are never diluted by trades that were never taken; nothing here is
    read by `services/expectancy.py` or `services/gate.py`.

    Provenance (concepts/aura/journaling-system, aura-05): missed and canceled
    trades are a distinct, high-value journaling category — Tom Dante found one of
    his biggest edges only because a student tracked his CANCELED orders. The
    analytic the table exists for is opportunity cost in R: a positive
    `hypothetical_r` is a missed winner, a negative one means pulling the order was
    PROTECTIVE.

    Model-aligned like the journal: `entry_model` (not the old `trades` schema's
    `setup_type`) and `entry_date` (not `trade_date`). User-scoped + soft-deleted.

    Screenshots are deliberately absent — user-uploaded evidence belongs to the
    learning-enforcement workstream (verified drill grading), which owns its shape.
    """

    __tablename__ = "missed_trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # --- Identity / context (mirrors journal_entries) -----------------------
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    session: Mapped[SessionType | None] = mapped_column(pg_enum(SessionType, "session_type"))
    entry_model: Mapped[EntryModel] = mapped_column(
        pg_enum(EntryModel, "entry_model"), nullable=False
    )

    # --- The miss itself ----------------------------------------------------
    miss_type: Mapped[MissType] = mapped_column(pg_enum(MissType, "miss_type"), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    hesitation_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # GIN indexed

    # --- The plan you didn't take -------------------------------------------
    planned_entry: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    planned_stop: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    planned_target: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    rr_planned: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # --- What it would have done (the opportunity-cost signal) --------------
    hypothetical_outcome: Mapped[HypotheticalOutcome | None] = mapped_column(
        pg_enum(HypotheticalOutcome, "hypothetical_outcome")
    )
    hypothetical_r: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # --- Review -------------------------------------------------------------
    narrative: Mapped[str | None] = mapped_column(Text)  # the thesis you didn't act on
    notes: Mapped[str | None] = mapped_column(Text)

    # --- Metadata -----------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
