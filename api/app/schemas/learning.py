"""Pydantic schemas for the learning API (Phase 5e-1).

The progress/stage/drill surfaces the /path, /path/:stage, /drills pages and the
ConceptTrackPanel read. All are user-scoped; see app/routers/learning.py.
Mirrored on the frontend in app/src/types/api.ts.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import UStage

# ---------------------------------------------------------------------------
# Concepts
# ---------------------------------------------------------------------------


class ConceptOut(BaseModel):
    """A gradable concept (seed data), plus the parsed rep-target floor."""

    id: uuid.UUID
    slug: str
    code: str | None = None
    u_stage: UStage
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
    u_stage: UStage
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
    reps: int = 0
    last_practiced: date | None = None
    notes: str | None = None


class ProgressPatch(BaseModel):
    """Upsert one concept's progress for the current user. Only the fields
    present are written (partial). Advancing ladder to Can-mark+ is gated on the
    server (reps ≥ target AND confidence set)."""

    concept_id: uuid.UUID
    ladder_stage: int | None = Field(None, ge=1, le=4)
    confidence: int | None = Field(None, ge=1, le=5)
    reps: int | None = Field(None, ge=0)
    last_practiced: date | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Stages — the derived exit-bar status (COMPUTED, never stored)
# ---------------------------------------------------------------------------


class RequirementOut(BaseModel):
    label: str
    met: bool
    attest: bool = False
    concept_slug: str | None = None
    concept_code: str | None = None


class StageOut(BaseModel):
    u_stage: str
    title: str
    watch_only: bool
    never_gate_eligible: bool
    locked: bool
    met: bool
    auto_met: bool
    attest_pending: bool
    total: int
    reached: int
    requirements: list[RequirementOut]


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
    reps: int = 0
    hand_done: bool = False
    tool_done: bool = False
    last_practiced: date | None = None
    notes: str | None = None


class DrillPatch(BaseModel):
    """Upsert one drill_progress for the current user (partial)."""

    drill_ref: str
    reps: int | None = Field(None, ge=0)
    hand_done: bool | None = None
    tool_done: bool | None = None
    last_practiced: date | None = None
    notes: str | None = None
