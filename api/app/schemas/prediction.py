"""Pydantic schemas for the pre-commitment ledger + calibration (Phase E5).

Mirrored on the frontend in app/src/types/api.ts.

There is no update model for a committed call, on purpose — `PredictionCommit`
writes it once and `PredictionResolve` writes only the reveal. The DB trigger
`predictions_freeze_the_call` (Alembic `0011`) is the backstop, not the only guard,
exactly as the 0009 subject CHECK backstops `_resolve_subject`.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import EntryModel, PredictionBias


class PredictionCommit(BaseModel):
    """The call, committed BEFORE the replay steps forward.

    `committed_at` is deliberately ABSENT: the server stamps it, so the timestamp
    cannot be chosen by the thing being timestamped. `extra="forbid"` plus the
    validator below means an attempt to send one gets a 422 that NAMES the reason
    rather than pydantic's generic "extra inputs are not permitted" — the same
    courtesy `ProgressPatch` extends to a `reps` write (E2).
    """

    drill_ref: str = Field(min_length=1)
    session_label: str = Field(min_length=1, description="Which session this call is for")
    instrument: str | None = None

    bias: PredictionBias
    dol: str = Field(min_length=1, description="The draw on liquidity you are calling")
    entry_model: EntryModel
    target: str = Field(min_length=1)

    # The marked chart captured with the call, if one was.
    evidence_id: uuid.UUID | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def _reject_a_client_timestamp(cls, data):
        if isinstance(data, dict):
            for field in ("committed_at", "resolved_at"):
                if field in data:
                    raise ValueError(
                        f"`{field}` is set by the server, not the client — a prediction is "
                        "only worth something if the time it was committed is not chosen by "
                        "whoever is being scored."
                    )
        return data


class PredictionResolve(BaseModel):
    """What actually happened. A strictly later request, accepted exactly once.

    Every field is required: `ck_predictions_resolution_complete` is all-or-nothing
    at the database, and a half-written reveal would leave the calibration
    denominator ambiguous.
    """

    outcome_bias: PredictionBias
    dol_hit: bool
    model_played_out: bool
    target_hit: bool
    resolution_notes: str | None = None

    model_config = {"extra": "forbid"}


class PredictionOut(BaseModel):
    """A committed call and, if it has been resolved, how it scored.

    The `*_correct` fields are COMPUTED per read (never stored), like every other
    verdict in this codebase.
    """

    id: uuid.UUID
    drill_ref: str
    session_label: str
    instrument: str | None = None

    bias: PredictionBias
    dol: str
    entry_model: EntryModel
    target: str
    committed_at: datetime

    resolved_at: datetime | None = None
    outcome_bias: PredictionBias | None = None
    dol_hit: bool | None = None
    model_played_out: bool | None = None
    target_hit: bool | None = None
    resolution_notes: str | None = None
    evidence_id: uuid.UUID | None = None

    # Computed
    resolved: bool = False
    bias_correct: bool | None = None
    dol_correct: bool | None = None
    entry_model_correct: bool | None = None
    target_correct: bool | None = None
    # Seconds between the commitment and the reveal. Surfaced rather than judged:
    # the app cannot observe a TradingView replay, so it can prove ORDERING in its
    # own record and must not pretend to prove more (see §E5 as-built).
    seconds_to_reveal: int | None = None


class ComponentScoreOut(BaseModel):
    key: str
    label: str
    correct: int
    resolved: int
    # None when nothing has resolved — NEVER 0.0. A zero from an instrument that
    # has seen nothing is not a measurement.
    accuracy: float | None = None


class CalibrationOut(BaseModel):
    """Informational feedback (§6). Nothing in the app gates on any of it."""

    committed: int
    resolved: int
    unresolved: int
    resolution_rate: float | None = None
    accuracy: float | None = None
    components: list[ComponentScoreOut] = []
    # The M6 bar, reported here too so the calibration surface can say what the
    # stage actually asks for — which is COMMITMENT, not correctness.
    tape_drills_total: int = 0
    tape_drills_committed: int = 0
    tape_drills_resolved: int = 0
