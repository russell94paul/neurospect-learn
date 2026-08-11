"""Pydantic schemas for the Study-Planner API (Phase 5e-2).

Preferences (availability + pacing), plan items (the prescriptive daily cards),
and the Today / calendar / regenerate envelopes carrying adherence + pace. All
user-scoped; see app/routers/planner.py. Mirrored on the frontend in 5e-3.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import PlanActivity, PlanItemStatus

_TRACKS = {"aura", "ict_course", "unified"}


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


class PreferencesIn(BaseModel):
    """Upsert the single active study_preferences row for the current user.
    `target_go_live_date` is PACING-ONLY (never gates)."""

    timezone: str = "UTC"
    mon_minutes: int = Field(0, ge=0, le=1440)
    tue_minutes: int = Field(0, ge=0, le=1440)
    wed_minutes: int = Field(0, ge=0, le=1440)
    thu_minutes: int = Field(0, ge=0, le=1440)
    fri_minutes: int = Field(0, ge=0, le=1440)
    sat_minutes: int = Field(0, ge=0, le=1440)
    sun_minutes: int = Field(0, ge=0, le=1440)
    max_session_minutes: int = Field(60, ge=1, le=1440)
    blackout_dates: list[date] = Field(default_factory=list)
    target_go_live_date: date | None = None
    active_track: str = "aura"

    def normalized_track(self) -> str:
        return self.active_track if self.active_track in _TRACKS else "aura"


class PreferencesOut(PreferencesIn):
    """The active prefs (or server defaults when the user has none yet)."""

    id: uuid.UUID | None = None
    plan_version: int = 1
    generated_at: datetime | None = None
    is_configured: bool = False  # False = these are defaults, not a saved row


# ---------------------------------------------------------------------------
# Plan items
# ---------------------------------------------------------------------------


class PlanItemOut(BaseModel):
    """One prescribed task. `id` is null for COMPUTED (future, not-yet-frozen)
    items; present for FROZEN (past/today) items materialized in the DB."""

    id: uuid.UUID | None = None
    plan_version: int = 1
    scheduled_date: date
    activity: PlanActivity
    concept_id: uuid.UUID | None = None
    concept_slug: str | None = None
    concept_title: str | None = None
    content_slug: str | None = None
    drill_ref: str | None = None
    drill_title: str | None = None
    drill_variant: str | None = None
    target_qty: int | None = None
    target_unit: str | None = None
    est_minutes: int = 0
    status: PlanItemStatus = PlanItemStatus.PENDING
    done_qty: int = 0
    completed_at: datetime | None = None
    sort_order: int = 0
    carried_over: bool = False
    frozen: bool = False  # True = a persisted plan_items row


class PlanItemPatch(BaseModel):
    """Mark a plan item done/partial/skipped. `done_qty` feeds
    concept_progress/drill_progress reps + last_practiced when done/partial."""

    status: PlanItemStatus
    done_qty: int | None = Field(None, ge=0)


# ---------------------------------------------------------------------------
# Adherence + pace (accountability, surfaced — never hidden)
# ---------------------------------------------------------------------------


class ConsistencyOut(BaseModel):
    """The EVIDENCE-BACKED counterparts of the self-reported figures beside them
    (Phase E6). Computed from `evidence_assets` + `rest_days`, never stored, and
    no new currency: §6 forbids XP/badges/points, so nothing here is a new score —
    these are the shipped surfaces re-derived from a source a click cannot move.

    Published BESIDE the marked figures rather than replacing them, which is E2's
    idiom for exactly this (`reps` ships beside `reps_evidenced`/`reps_legacy` so
    the gap is visible rather than folded away)."""

    evidenced_days: int = 0
    evidence_streak: int = 0
    #: Of the streak above, how many days were DECLARED REST DAYS rather than
    #: worked. Surfaced because the app cannot tell booked leave from a pre-emptive
    #: excuse, so it shows the composition instead of judging it.
    rest_days_in_streak: int = 0
    last_evidence_date: date | None = None
    #: Days marked done in the planner with no evidence captured at all — the gap
    #: between the claim and the record. Surfaced, never deducted.
    days_marked_without_evidence: int = 0
    rest_days_declared: int = 0
    rest_days_upcoming: int = 0


class AdherenceOut(BaseModel):
    total: int = 0          # items scheduled on/before today
    done: int = 0
    partial: int = 0
    skipped: int = 0
    pending: int = 0
    adherence_pct: float | None = None  # (done + 0.5·partial) / total
    current_streak: int = 0             # consecutive fully-cleared days ending today
    days_behind: int = 0                # distinct past dates with pending items
    carried_over: int = 0               # past pending items re-queued today
    #: E6 — the same consistency, derived from evidence instead of from a click.
    consistency: ConsistencyOut = Field(default_factory=ConsistencyOut)


# ---------------------------------------------------------------------------
# Declared rest days (Phase E6) — booked IN ADVANCE, never after the fact
# ---------------------------------------------------------------------------


class RestDayIn(BaseModel):
    """Declare a day off. There is deliberately NO `declared_at` field — the
    server owns that clock, and a rest day for a day that has already passed is
    refused by `rest_days`' own trigger (Alembic `0012`), not by this schema.
    §6 rejects the retroactive streak freeze: a day off booked after you missed a
    day is not a day off."""

    rest_date: date
    reason: str | None = Field(default=None, max_length=500)


class RestDayOut(BaseModel):
    id: uuid.UUID
    rest_date: date
    reason: str | None = None
    declared_at: datetime      # SERVER-stamped, frozen after insert
    #: How many days ahead it was booked. Surfaced so a same-day declaration is
    #: visible as one — the trigger blocks the past, the surface shows the rest.
    days_declared_ahead: int = 0


class PaceOut(BaseModel):
    """ETA projection — PACING-ONLY (never advances a gate)."""

    target_go_live_date: date | None = None
    projected_go_live: date | None = None
    on_pace: bool | None = None
    projected_clear: dict[str, date] = Field(default_factory=dict)  # stage_code → date


class TodayOut(BaseModel):
    date: date
    active_track: str
    plan_version: int
    items: list[PlanItemOut]
    adherence: AdherenceOut
    pace: PaceOut


class PlanRangeOut(BaseModel):
    date_from: date
    date_to: date
    active_track: str
    plan_version: int
    items: list[PlanItemOut]   # past/today frozen (id set), future computed (id null)
    pace: PaceOut
    unplaced: int = 0          # items that couldn't fit within the horizon
