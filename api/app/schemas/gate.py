"""Pydantic schemas for the Readiness-to-Live Gate API (Phase 5g).

The gate verdict is COMPUTED per read by the pure app/services/gate.py from three
sources — (a) `concept_progress`, (b) the shipped 5f expectancy service over
`journal_entries`, (c) the user's `gate_attestations` — and is NOT stored. Note
what is absent by design: no request schema carries a `cleared` field, so there
is no way to declare a model live-ready. The Gate itself is canonical in
concepts/mastery/README §Readiness-to-Live Gate.
"""

from pydantic import BaseModel, Field

from app.models.enums import GateAttestationItem


class GateRequirement(BaseModel):
    """One checkable requirement. `source` is which of the gate's three evidence
    sources it comes from: `concepts` (a) · `evidence` (b) · `behaviour` (c)."""

    key: str
    source: str
    label: str
    met: bool
    detail: str | None = None
    attest: bool = False            # true only for the (c) self-attested items
    concept_slug: str | None = None
    concept_code: str | None = None
    concept_track: str | None = None     # link target: /path/:track/:stage
    concept_stage: str | None = None
    required_ladder: int | None = None   # 3 Backtested / 4 Live-ready
    actual_ladder: int | None = None
    credited_slug: str | None = None     # which concept supplied the evidence…
    credited_track: str | None = None    # …and on which track (cross-ref credit)


class ModelReadiness(BaseModel):
    """One entry_model's verdict. `cleared` is the conjunction of the three
    source groups — never settable, recomputed on every read."""

    entry_model: str
    cleared: bool
    concepts_met: bool
    evidence_met: bool
    behaviour_met: bool
    requirements: list[GateRequirement]
    blocking: list[str]              # human-readable "what's blocking live"
    backtest_logged: int
    backtest_n: int
    backtest_expectancy: float | None
    backtest_win_rate: float | None      # FRACTION 0–1 (UI formats as %)
    backtest_break_even: float | None    # FRACTION 0–1
    backtest_avg_rr: float | None
    sample_target: int
    sample_stretch: int              # README's "ideally ≥100" — surfaced, NOT gating
    stretch_met: bool
    live_n: int                      # shown for honesty; never a requirement
    live_expectancy: float | None


class FrontierConcept(BaseModel):
    """A watch-only (U5 / EMERGING / SPECULATIVE) concept — study-and-watch, and
    NEVER gate-eligible. Returned so the UI can say so explicitly."""

    slug: str
    title: str
    u_stage: str | None
    tier: str | None
    label: str | None


class Attestation(BaseModel):
    item: str
    label: str
    attested: bool
    note: str | None = None


class Corroboration(BaseModel):
    """Objective journal facts shown BESIDE the (c) attestations so a self-attest
    is made in the face of the record. Not gating."""

    entries_logged: int
    entries_closed: int
    journaling_days: int
    live_entries: int
    backtest_entries: int
    last_entry_date: str | None


class GateOut(BaseModel):
    anchor_track: str                # 'unified' — entry_model maps onto U3.2a–g
    credit_track: str | None         # restricts which track may supply credit
    sample_target: int
    sample_stretch: int
    any_cleared: bool
    models: list[ModelReadiness]
    attestations: list[Attestation]
    corroboration: Corroboration
    frontier: list[FrontierConcept]


class AttestationPatch(BaseModel):
    """Attest / revoke ONE behavioural item. There is deliberately no model or
    `cleared` field — attesting is an input to the gate, never an override."""

    item: GateAttestationItem
    attested: bool
    note: str | None = Field(default=None, max_length=2000)
