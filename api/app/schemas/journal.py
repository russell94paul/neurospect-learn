"""Pydantic schemas for the model-aligned journal API (Phase 5f).

Mirrors app/models/journal_entry.py (the as-built 5c table) + the 7 journal enums
in app/models/enums.py. Deliberately NOT the generic `trades` shape: every field
traces to the Unified Playbook one-glance decision flow + the entry-model
checklists. `mode` (backtest|live) makes the same journal power both axes and lets
the expectancy dashboard (and the future 5g gate) compare them.

Numeric price / R fields are typed `float` for clean JSON; the DB stores them as
NUMERIC. Expectancy is computed in R (`r_multiple` / `rr_planned` / `risk_pct`),
never dollars: `position_size` (added in 6c) is RECORD-KEEPING ONLY and is read by
no expectancy, analytics or gate computation.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    EntryModel,
    EntryPDA,
    Grade,
    JournalMode,
    Outcome,
    RangePosition,
    SessionType,
)


class JournalEntryIn(BaseModel):
    """Create body. `mode` + `entry_model` are required (they discriminate the
    axis + are the expectancy-grouping key); `entry_date` + `instrument` are the
    NOT-NULL identity columns. Everything else is optional (a backtest setup may
    be logged before it is closed). `entry_pda` defaults to FVG (R4)."""

    # Identity / context
    entry_date: date
    instrument: str = Field(min_length=1, max_length=20)
    session: SessionType | None = None
    mode: JournalMode

    # Model (expectancy-grouping key)
    entry_model: EntryModel

    # Decision-flow capture (the model-aligned part)
    draw_on_liquidity: str | None = None
    range_position: RangePosition | None = None
    swing_qualification: int | None = Field(None, ge=0, le=2)  # double-qualified swing (R2)
    seq_smt_confirmed: bool | None = None  # HTF Sequential SMT
    triad_smt_confirmed: bool | None = None  # LTF triad SMT
    aura_asset_leg: bool | None = None  # optional 6S 4th leg (R7)
    time_window_valid: bool | None = None
    entry_pda: EntryPDA = EntryPDA.FVG  # default fvg (R4)

    # Execution / risk (R units — no dollar sizing)
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    rr_planned: float | None = None
    risk_pct: float | None = None
    position_size: float | None = None  # contracts/lots — record-keeping only (6c)
    exit_price: float | None = None
    r_multiple: float | None = None  # realized R — the core expectancy input
    outcome: Outcome | None = None
    mae: float | None = None
    mfe: float | None = None

    # Frontier stack (watch-only — study-only, NEVER gate-eligible)
    confluence_tags: list[str] | None = None

    # Review
    plan_followed: bool | None = None
    mistake_tags: list[str] | None = None
    grade: Grade | None = None
    notes: str | None = None


class JournalEntryUpdate(BaseModel):
    """Partial update — every field optional. `mode` / `entry_model` may be
    corrected but never cleared (they are NOT NULL). Only fields explicitly
    supplied are written (the router uses `exclude_unset`)."""

    entry_date: date | None = None
    instrument: str | None = Field(None, min_length=1, max_length=20)
    session: SessionType | None = None
    mode: JournalMode | None = None
    entry_model: EntryModel | None = None
    draw_on_liquidity: str | None = None
    range_position: RangePosition | None = None
    swing_qualification: int | None = Field(None, ge=0, le=2)
    seq_smt_confirmed: bool | None = None
    triad_smt_confirmed: bool | None = None
    aura_asset_leg: bool | None = None
    time_window_valid: bool | None = None
    entry_pda: EntryPDA | None = None
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    rr_planned: float | None = None
    risk_pct: float | None = None
    position_size: float | None = None  # contracts/lots — record-keeping only (6c)
    exit_price: float | None = None
    r_multiple: float | None = None
    outcome: Outcome | None = None
    mae: float | None = None
    mfe: float | None = None
    confluence_tags: list[str] | None = None
    plan_followed: bool | None = None
    mistake_tags: list[str] | None = None
    grade: Grade | None = None
    notes: str | None = None


class JournalEntryOut(BaseModel):
    """One journal row as returned. A row is "closed" (and thus counts toward
    expectancy) iff it carries a realized `r_multiple` — the UI derives that from
    the field, so no separate flag is stored."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    entry_date: date
    instrument: str
    session: SessionType | None = None
    mode: JournalMode
    entry_model: EntryModel
    draw_on_liquidity: str | None = None
    range_position: RangePosition | None = None
    swing_qualification: int | None = None
    seq_smt_confirmed: bool | None = None
    triad_smt_confirmed: bool | None = None
    aura_asset_leg: bool | None = None
    time_window_valid: bool | None = None
    entry_pda: EntryPDA | None = None
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    rr_planned: float | None = None
    risk_pct: float | None = None
    position_size: float | None = None  # contracts/lots — record-keeping only (6c)
    exit_price: float | None = None
    r_multiple: float | None = None
    outcome: Outcome | None = None
    mae: float | None = None
    mfe: float | None = None
    confluence_tags: list[str] | None = None
    plan_followed: bool | None = None
    mistake_tags: list[str] | None = None
    grade: Grade | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
