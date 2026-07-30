"""Pydantic schemas for the missed-trade log + its opportunity-cost analytic (6b).

Mirrors app/models/missed_trade.py (Alembic 0008) and follows the 5f journal
schema idiom: numeric fields typed `float` for clean JSON (NUMERIC in the DB),
partial PATCH, and `from_attributes` on the Out model.

Model-aligned like the journal: `entry_model` (not the old `trades` schema's
`setup_type`) and `entry_date` (not `trade_date`). NOTHING here enters expectancy
or the Readiness-to-Live Gate — these are trades that were never taken.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import EntryModel, HypotheticalOutcome, MissType, SessionType


class MissedTradeIn(BaseModel):
    """Create body. `entry_date` + `instrument` + `entry_model` + `miss_type` are
    the NOT-NULL columns; everything else is optional so a miss can be logged in
    the moment and resolved later (PATCH in `hypothetical_outcome`/`_r` after
    watching what price did)."""

    entry_date: date
    instrument: str = Field(min_length=1, max_length=20)
    session: SessionType | None = None
    entry_model: EntryModel
    miss_type: MissType

    reason: str | None = None
    hesitation_tags: list[str] | None = None

    planned_entry: float | None = None
    planned_stop: float | None = None
    planned_target: float | None = None
    rr_planned: float | None = None

    hypothetical_outcome: HypotheticalOutcome | None = None
    hypothetical_r: float | None = None

    narrative: str | None = None
    notes: str | None = None


class MissedTradeUpdate(BaseModel):
    """Partial update — every field optional; only supplied fields are written."""

    entry_date: date | None = None
    instrument: str | None = Field(None, min_length=1, max_length=20)
    session: SessionType | None = None
    entry_model: EntryModel | None = None
    miss_type: MissType | None = None
    reason: str | None = None
    hesitation_tags: list[str] | None = None
    planned_entry: float | None = None
    planned_stop: float | None = None
    planned_target: float | None = None
    rr_planned: float | None = None
    hypothetical_outcome: HypotheticalOutcome | None = None
    hypothetical_r: float | None = None
    narrative: str | None = None
    notes: str | None = None


class MissedTradeOut(BaseModel):
    """One missed/canceled trade as returned. A row is "resolved" (and thus enters
    the opportunity-cost sums) iff it carries a `hypothetical_r`."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    entry_date: date
    instrument: str
    session: SessionType | None = None
    entry_model: EntryModel
    miss_type: MissType
    reason: str | None = None
    hesitation_tags: list[str] | None = None
    planned_entry: float | None = None
    planned_stop: float | None = None
    planned_target: float | None = None
    rr_planned: float | None = None
    hypothetical_outcome: HypotheticalOutcome | None = None
    hypothetical_r: float | None = None
    narrative: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class MissBucket(BaseModel):
    """One slice of the log. `net_r` NEGATIVE means standing down was PROTECTIVE —
    the sign carries the whole insight, so it is never abs()'d away."""

    key: str
    logged: int
    resolved: int
    would_win: int
    would_lose: int
    would_breakeven: int
    forgone_r: float | None = None
    saved_r: float | None = None
    net_r: float | None = None
    avg_r: float | None = None


class OpportunityCostOut(BaseModel):
    """GET /api/analytics/missed-summary — the "what is hesitation costing you?"
    number, in R. NOT expectancy: these trades were never taken."""

    total: MissBucket
    by_miss_type: list[MissBucket]
    by_hesitation_tag: list[MissBucket]
    by_entry_model: list[MissBucket]
