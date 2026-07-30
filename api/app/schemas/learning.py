"""Pydantic schemas for the learning API (Phase 5e-1).

The progress/stage/drill surfaces the /path, /path/:stage, /drills pages and the
ConceptTrackPanel read. All are user-scoped; see app/routers/learning.py.
Mirrored on the frontend in app/src/types/api.ts.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models.enums import UStage

# Phase E2 — the message a rep-writing attempt gets. `extra="forbid"` alone would
# say "Extra inputs are not permitted", which tells the caller nothing about what
# to do instead; a refusal that does not name the alternative is exactly the
# friction the north star warns against.
_REPS_DERIVED_MSG = (
    "`reps` is not writable — a rep counts only when there is evidence of the "
    "work. Upload the capture to POST /api/evidence with `reps_claimed`; the "
    "count is derived from it."
)


class _RejectsReps:
    """Mixin: turn a `reps` key into a 422 that names the evidence endpoint."""

    @model_validator(mode="before")
    @classmethod
    def _no_reps(cls, data):
        if isinstance(data, dict) and "reps" in data:
            raise ValueError(_REPS_DERIVED_MSG)
        return data

# ---------------------------------------------------------------------------
# Concepts
# ---------------------------------------------------------------------------


class ConceptOut(BaseModel):
    """A gradable concept (seed data), plus the parsed rep-target floor."""

    id: uuid.UUID
    slug: str
    code: str | None = None
    track: str
    stage_code: str | None = None
    stage_order: int | None = None
    cross_refs: list[str] | None = None
    u_stage: UStage | None = None
    title: str
    is_core: bool
    tier: str | None = None
    label: str | None = None
    axis: str | None = None
    watch_only: bool
    rep_target: str | None = None
    rep_target_kind: str = "habit"
    rep_target_count: int | None = None
    content_slug: str | None = None
    drill_refs: list[str] | None = None
    sort_order: int
    notes: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Progress — the LEFT JOIN of concepts × the current user's concept_progress
# ---------------------------------------------------------------------------


class ProgressRow(BaseModel):
    """One concept + this user's progress (null progress = untracked)."""

    concept_id: uuid.UUID
    slug: str
    code: str | None = None
    track: str
    stage_code: str | None = None
    stage_order: int | None = None
    cross_refs: list[str] | None = None
    u_stage: UStage | None = None
    title: str
    is_core: bool
    watch_only: bool
    content_slug: str | None = None
    drill_refs: list[str] | None = None
    rep_target: str | None = None
    rep_target_kind: str = "habit"
    rep_target_count: int | None = None
    sort_order: int

    # Progress (null/0 when untracked)
    ladder_stage: int | None = None
    confidence: int | None = None
    #: DERIVED (Phase E2) = reps_legacy + reps_evidenced. Read-only everywhere.
    reps: int = 0
    #: Σ reps_claimed over this concept's live evidence — the part that is proven.
    reps_evidenced: int = 0
    #: Claimed before the evidence layer existed (Alembic 0009 froze it). Shown
    #: separately so the pre-evidence gap is visible rather than folded away.
    reps_legacy: int = 0
    last_practiced: date | None = None
    notes: str | None = None


class ProgressPatch(_RejectsReps, BaseModel):
    """Upsert one concept's progress for the current user. Only the fields
    present are written (partial). Advancing ladder to Can-mark+ is gated on the
    server (reps ≥ target AND confidence set).

    `reps` is DELIBERATELY ABSENT and `extra="forbid"` rejects it: since Phase E2
    a rep exists only as evidence of the work, so the count is derived from
    `evidence_assets` and this endpoint cannot mint one. Sending `reps` is a 422
    naming `POST /api/evidence`, not a silently ignored field.
    """

    model_config = {"extra": "forbid"}

    concept_id: uuid.UUID
    ladder_stage: int | None = Field(None, ge=1, le=4)
    confidence: int | None = Field(None, ge=1, le=5)
    last_practiced: date | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Stages — the derived exit-bar status (COMPUTED, never stored)
# ---------------------------------------------------------------------------


class RequirementOut(BaseModel):
    """One exit-bar row. Phase 6a added the wiring fields: `derived` marks a row
    objectively EARNED from logged evidence (journal expectancy / the gate verdict),
    `attest` + `attest_item` a row that REFLECTS a /gate attestation (never a second
    checkbox), `detail` the evidence in numbers, and `link` where it is satisfied."""

    label: str
    met: bool
    attest: bool = False
    concept_slug: str | None = None
    concept_code: str | None = None
    derived: bool = False
    detail: str | None = None
    attest_item: str | None = None
    link: str | None = None


class StageRollup(BaseModel):
    """A stage's status without the requirement detail (track switcher/spine)."""

    track: str
    stage_code: str
    stage_order: int
    title: str
    summary: str | None = None
    gate_text: str | None = None
    watch_only: bool
    never_gate_eligible: bool
    locked: bool
    met: bool
    auto_met: bool
    attest_pending: bool
    total: int
    reached: int


class StageOut(StageRollup):
    """A stage rollup + the full exit-bar requirement checklist."""

    requirements: list[RequirementOut]


class TrackOut(BaseModel):
    """One graded track + its ordered stages (GET /api/tracks)."""

    track: str
    label: str
    stages: list[StageRollup]


# ---------------------------------------------------------------------------
# Drills — the catalog + this user's drill_progress
# ---------------------------------------------------------------------------


class DrillOut(BaseModel):
    id: uuid.UUID
    drill_ref: str
    track: str
    stage_code: str | None = None
    title: str
    advances_to: str | None = None
    rep_target: str | None = None
    rep_target_count: int | None = None
    concept_slugs: list[str] | None = None
    sort_order: int

    # Progress (null/0/false when untracked)
    #: DERIVED (Phase E2) = reps_legacy + reps_evidenced.
    reps: int = 0
    reps_evidenced: int = 0
    reps_legacy: int = 0
    hand_done: bool = False
    tool_done: bool = False
    last_practiced: date | None = None
    notes: str | None = None


class DrillPatch(_RejectsReps, BaseModel):
    """Upsert one drill_progress for the current user (partial).

    `reps` is DELIBERATELY ABSENT (see `ProgressPatch`) — reps come from
    `POST /api/evidence` alone. The ✋/🛠 variant marks stay writable: they are
    descriptive and gate nothing.
    """

    model_config = {"extra": "forbid"}

    drill_ref: str
    hand_done: bool | None = None
    tool_done: bool | None = None
    last_practiced: date | None = None
    notes: str | None = None
