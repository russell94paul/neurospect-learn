import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import (
    EntryModel,
    EntryPDA,
    Grade,
    JournalMode,
    Outcome,
    RangePosition,
    SessionType,
    pg_enum,
)


class JournalEntry(Base):
    """The model-aligned journal — one row per logged setup/trade.

    Deliberately NOT the generic `trades` schema: every field traces to the
    Unified Playbook one-glance decision flow + the entry-model checklists. The
    `mode` discriminator (backtest|live) makes the same journal power both axes
    and lets the gate compare them. User-scoped + soft-deleted.

    Phase 6c added `position_size` — RECORD-KEEPING ONLY. Expectancy stays R-based
    (`r_multiple` / `rr_planned` / `risk_pct` carry the %/R framing) and no
    expectancy, analytics or gate computation reads it. The Aura canceled-order
    surface shipped in 6b as the separate `missed_trades` table (see
    app/models/missed_trade.py) — deliberately NOT columns here, so executed-trade
    analytics are never diluted by trades that were never taken.

    Still deferred: screenshots / uploaded evidence (owned by the
    learning-enforcement workstream, which owns verified drill grading).
    """

    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # --- Identity / context -------------------------------------------------
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    session: Mapped[SessionType | None] = mapped_column(pg_enum(SessionType, "session_type"))
    mode: Mapped[JournalMode] = mapped_column(pg_enum(JournalMode, "journal_mode"), nullable=False)

    # --- Model (expectancy-grouping key) ------------------------------------
    entry_model: Mapped[EntryModel] = mapped_column(
        pg_enum(EntryModel, "entry_model"), nullable=False
    )

    # --- Decision-flow capture (the model-aligned part) ---------------------
    draw_on_liquidity: Mapped[str | None] = mapped_column(Text)  # freetext DOL target
    range_position: Mapped[RangePosition | None] = mapped_column(pg_enum(RangePosition, "range_position"))
    swing_qualification: Mapped[int | None] = mapped_column(SmallInteger)  # 0/1/2 double-qualified-swing (R2)
    seq_smt_confirmed: Mapped[bool | None] = mapped_column(Boolean)  # HTF Sequential SMT
    triad_smt_confirmed: Mapped[bool | None] = mapped_column(Boolean)  # LTF triad SMT
    aura_asset_leg: Mapped[bool | None] = mapped_column(Boolean)  # optional 6S 4th leg (R7)
    time_window_valid: Mapped[bool | None] = mapped_column(Boolean)  # entry inside a valid time window
    entry_pda: Mapped[EntryPDA | None] = mapped_column(pg_enum(EntryPDA, "entry_pda"))  # default fvg (R4), set in DDL

    # --- Execution / risk ---------------------------------------------------
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    rr_planned: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))  # planned R:R
    risk_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # % risked per trade (R5 blueprint)
    position_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # contracts/lots — record-keeping ONLY (6c)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    r_multiple: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))  # realized R — core expectancy input
    outcome: Mapped[Outcome | None] = mapped_column(pg_enum(Outcome, "outcome"))
    mae: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))  # max adverse excursion
    mfe: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))  # max favorable excursion

    # --- Frontier stack (watch-only — NEVER gate-eligible) ------------------
    confluence_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # WHERE/WHEN/DIRECTION/CONFIRM filters aligned

    # --- Review -------------------------------------------------------------
    plan_followed: Mapped[bool | None] = mapped_column(Boolean)
    mistake_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # GIN indexed
    grade: Mapped[Grade | None] = mapped_column(pg_enum(Grade, "grade"))
    notes: Mapped[str | None] = mapped_column(Text)

    # --- Metadata -----------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
