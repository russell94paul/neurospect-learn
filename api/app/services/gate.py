"""Readiness-to-Live Gate — the per-model "cleared to live?" verdict (Phase 5g).

PURE and DB-agnostic (no DB, no I/O), like services/expectancy.py and
services/scheduler.py, so the readiness logic is unit-tested against hand-built
fixtures with known answers. The router loads concepts + progress + journal rows,
maps them to the views below, and calls `compute_readiness`.

The Gate itself is CANONICAL in concepts/mastery/README §Readiness-to-Live Gate —
this module ENCODES it, it does not restate or redefine it. Its seven checkboxes
map onto the three evidence sources learning-platform.md §3 names:

  (a) concepts   every core concept at Backtested+, the model's load-bearing
                 concepts at Live-ready                      → concept_progress
  (b) evidence   a minimum backtest sample with POSITIVE expectancy in R, and a
                 win rate that clears break-even for its R:R → journal_entries,
                 via the ALREADY-SHIPPED pure services/expectancy.py (5f) — the
                 math is reused here, never reimplemented
  (c) behaviour  risk precommitted in writing · a demo/sim track record ·
                 an established journaling habit · circuit-breaker discipline
                 demonstrated                                → user-attested

NORTH STAR — discipline & accountability by design (learning-platform.md):
  * NON-OVERRIDABLE. `cleared` is COMPUTED from (a) ∧ (b) ∧ (c) on every read and
    is never stored, never settable. There is deliberately no "mark cleared"
    input anywhere in this module or its router.
  * FRONTIER IS NEVER GATE-ELIGIBLE. A `watch_only` (U5 / EMERGING /
    SPECULATIVE) concept never becomes a requirement and never supplies credit
    for one. Confluence tags on journal entries are study-only and unread here.
  * NEVER VACUOUSLY CLEARED. A missing curriculum concept or an unseeded
    database yields an UNMET requirement with a reason — never an empty
    requirement list that `all()` would report as cleared.
  * ATTESTATION IS AN INPUT, NOT AN OVERRIDE. Attesting (c) cannot satisfy (a)
    or (b); a model with every box ticked and no sample stays blocked.

ANCHOR TRACK (the load-bearing 5g decision). Requirements are defined by the
UNIFIED curriculum, because `journal_entries.entry_model` — the gate's grouping
key — maps 1:1 onto the unified track's seven U3.2a–g entry-model concepts (the
aura / ict_course tracks enumerate no such per-model set). Progress made on
ANOTHER track still counts: a requirement is satisfied by its anchor concept OR
by any `cross_refs` equivalent that reached the bar (studying "swing points" in
Aura is real evidence for the same primitive). `credit_track` restricts which
track may supply that credit — it can only ever TIGHTEN the gate (default: any
track), so no caller-supplied parameter can loosen a verdict.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.services import expectancy

# Ladder stages (concepts/mastery/README §ladder) — same constants as stages.py.
LEARNED, CAN_MARK, BACKTESTED, LIVE_READY = 1, 2, 3, 4

# The anchor curriculum (see module docstring) and the stages whose core concepts
# the gate reads. U5 is EXCLUDED by design — frontier is never gate-eligible.
ANCHOR_TRACK = "unified"
CORE_STAGES = ("U1", "U2", "U3", "U4")

# entry_model → the unified entry-model concept(s) that model is built on, named
# EXPLICITLY (the same idiom as stages._U2_GATE_SLUGS: greppable, not derived
# from a code-letter ordering that a re-seed could silently shift).
ENTRY_MODEL_CONCEPTS: dict[str, tuple[str, ...]] = {
    "consolidation": ("u3-2a-consolidation",),
    "expansion_retracement": ("u3-2b-expansion-retracement",),
    "reversal_raid_on_stops": ("u3-2c-reversal-raid",),
    "london": ("u3-2d-london",),
    "model_2022_ote": ("u3-2e-model-2022-ote",),
    "daily_bias": ("u3-2f-daily-bias-filter",),
    "smt_confirmation": ("u3-2g-smt-confirmation-entry",),
}

# The unified decision flow ROUTES INTO all seven models at runtime, so it is
# gated on all seven being Live-ready — the advanced track carries the hardest
# bar (north star: default to enforce). See §5g as-built.
UNIFIED_MODEL = "unified"

# Report order: the seven named models, then the unified flow.
ALL_MODELS: tuple[str, ...] = (*ENTRY_MODEL_CONCEPTS.keys(), UNIFIED_MODEL)

# (c) the behavioural checklist — verbatim in substance from
# concepts/mastery/README §Gate items 4–7. User-attested; keys are the
# `gate_attestation_item` Postgres enum labels.
BEHAVIOURAL_ITEMS: tuple[tuple[str, str], ...] = (
    (
        "risk_precommitted",
        "Risk rules internalized and precommitted, in writing — per-trade 1–2% of "
        "capital, daily stop 2–3R, 10R drawdown circuit-breaker, no sizing up in a drawdown",
    ),
    (
        "sim_track_record",
        "A demo/sim track record long enough to show the discipline holds under live "
        "conditions, not just in hindsight replay",
    ),
    (
        "journaling_habit",
        "An established journaling habit — every trade (incl. missed/canceled) logged, "
        "weekly review run, \"never miss twice\" holding",
    ),
    (
        "circuit_breaker",
        "Circuit-breaker discipline demonstrated — you have actually stopped at your daily "
        "stop / two-loss rule under real pressure, not just written it down",
    ),
)

BEHAVIOURAL_KEYS: tuple[str, ...] = tuple(k for k, _ in BEHAVIOURAL_ITEMS)

# The gate's required backtest sample is the shipped 5f reference (≥50 setups per
# the drill reps). The README's "ideally ≥100 executed backtest trades" is a
# STRETCH marker only — surfaced, never gating.
SAMPLE_STRETCH = 100

_LADDER_NAMES = {1: "Learned", 2: "Can-mark", 3: "Backtested", 4: "Live-ready"}


def ladder_name(stage: int | None) -> str:
    return _LADDER_NAMES.get(stage or 0, "not started")


# ---------------------------------------------------------------------------
# Inputs (DB-agnostic views)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConceptGateView:
    """The concept fields the gate reads."""

    slug: str
    track: str
    title: str
    is_core: bool
    watch_only: bool
    code: str | None = None
    u_stage: str | None = None
    stage_code: str | None = None
    tier: str | None = None
    label: str | None = None
    cross_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Corroboration:
    """Objective journal facts shown BESIDE the (c) attestations so a self-attest
    is made in the face of the record (north star: accountability surfaced).
    Deliberately NOT gating — no threshold here is invented."""

    entries_logged: int = 0
    entries_closed: int = 0
    journaling_days: int = 0
    live_entries: int = 0
    backtest_entries: int = 0
    last_entry_date: str | None = None


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

@dataclass
class GateRequirement:
    key: str
    source: str  # "concepts" | "evidence" | "behaviour"
    label: str
    met: bool
    detail: str | None = None
    attest: bool = False
    concept_slug: str | None = None
    concept_code: str | None = None
    # The anchor concept's own track + stage, so the UI can link to the curriculum
    # unit where the requirement is actually worked (/path/:track/:stage).
    concept_track: str | None = None
    concept_stage: str | None = None
    required_ladder: int | None = None
    actual_ladder: int | None = None
    credited_slug: str | None = None
    credited_track: str | None = None


@dataclass
class ModelReadiness:
    entry_model: str
    cleared: bool = False
    concepts_met: bool = False
    evidence_met: bool = False
    behaviour_met: bool = False
    requirements: list[GateRequirement] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    # (b) headline numbers, straight from the 5f expectancy service.
    backtest_logged: int = 0
    backtest_n: int = 0
    backtest_expectancy: float | None = None
    backtest_win_rate: float | None = None
    backtest_break_even: float | None = None
    backtest_avg_rr: float | None = None
    sample_target: int = expectancy.SAMPLE_TARGET
    sample_stretch: int = SAMPLE_STRETCH
    stretch_met: bool = False
    # Live activity is shown for honesty (backtest vs live), never a requirement.
    live_n: int = 0
    live_expectancy: float | None = None


@dataclass
class FrontierConcept:
    slug: str
    title: str
    u_stage: str | None
    tier: str | None
    label: str | None


@dataclass
class AttestationView:
    item: str
    label: str
    attested: bool
    note: str | None = None


@dataclass
class GateResult:
    anchor_track: str
    credit_track: str | None
    sample_target: int
    sample_stretch: int
    models: list[ModelReadiness] = field(default_factory=list)
    attestations: list[AttestationView] = field(default_factory=list)
    corroboration: Corroboration = field(default_factory=Corroboration)
    frontier: list[FrontierConcept] = field(default_factory=list)
    any_cleared: bool = False


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _credit(
    anchor: ConceptGateView,
    by_slug: dict[str, ConceptGateView],
    ladder: dict[str, int | None],
    *,
    bar: int,
    credit_track: str | None,
) -> tuple[bool, ConceptGateView | None, int | None]:
    """Best evidence for `anchor` at `bar`, from the anchor concept itself or any
    cross-ref equivalent. Returns (met, crediting concept, its ladder stage).

    A `watch_only` concept can never supply credit (frontier is never
    gate-eligible). `credit_track`, when given, restricts the candidate set — it
    can only ever remove candidates, i.e. tighten the gate.
    """
    candidates = [anchor, *(by_slug[s] for s in anchor.cross_refs if s in by_slug)]
    best: tuple[ConceptGateView | None, int | None] = (None, None)
    for c in candidates:
        if c.watch_only:
            continue
        if credit_track is not None and c.track != credit_track:
            continue
        stage = ladder.get(c.slug)
        if stage is None:
            if best[0] is None:
                best = (c, None)
            continue
        if best[1] is None or stage > best[1]:
            best = (c, stage)
    creditor, stage = best
    return (stage is not None and stage >= bar), creditor, stage


def _concept_requirement(
    anchor: ConceptGateView,
    by_slug: dict[str, ConceptGateView],
    ladder: dict[str, int | None],
    *,
    bar: int,
    key_prefix: str,
    credit_track: str | None,
) -> GateRequirement:
    met, creditor, stage = _credit(
        anchor, by_slug, ladder, bar=bar, credit_track=credit_track
    )
    bar_name = ladder_name(bar)
    detail = f"at {ladder_name(stage)}"
    if met and creditor is not None and creditor.slug != anchor.slug:
        detail = f"at {ladder_name(stage)} via {creditor.title} ({creditor.track})"
    elif not met:
        detail = f"at {ladder_name(stage)} — needs {bar_name}"
        if credit_track is not None:
            detail += f" on the {credit_track} track"
    return GateRequirement(
        key=f"{key_prefix}:{anchor.slug}",
        source="concepts",
        label=f"{anchor.title} — {bar_name}",
        met=met,
        detail=detail,
        concept_slug=anchor.slug,
        concept_code=anchor.code,
        concept_track=anchor.track,
        concept_stage=anchor.stage_code,
        required_ladder=bar,
        actual_ladder=stage,
        credited_slug=creditor.slug if (met and creditor) else None,
        credited_track=creditor.track if (met and creditor) else None,
    )


def _missing_concept_requirement(slug: str, *, bar: int, key_prefix: str) -> GateRequirement:
    """A named curriculum concept is absent from the DB. Emitted as UNMET so a
    seed gap can never make a model vacuously cleared."""
    return GateRequirement(
        key=f"{key_prefix}:{slug}",
        source="concepts",
        label=f"{slug} — {ladder_name(bar)}",
        met=False,
        detail="concept not found in the curriculum — re-run scripts.seed_concepts",
        concept_slug=slug,
        required_ladder=bar,
    )


def _model_concept_slugs(model: str) -> tuple[str, ...]:
    if model == UNIFIED_MODEL:
        # The unified flow routes into every model → all seven, Live-ready.
        return tuple(s for slugs in ENTRY_MODEL_CONCEPTS.values() for s in slugs)
    return ENTRY_MODEL_CONCEPTS.get(model, ())


def _evidence_requirements(
    model: str, bt: expectancy.Group | None, *, sample_target: int
) -> list[GateRequirement]:
    """(b) — the empirical proof of edge, read from the shipped 5f expectancy
    service. Three requirements matching README §Gate items 2 + 3."""
    n = bt.n if bt else 0
    exp = bt.expectancy if bt else None
    win = bt.win_rate if bt else None
    be = bt.break_even if bt else None

    reqs = [
        GateRequirement(
            key=f"b1:{model}",
            source="evidence",
            label=f"Backtest sample ≥ {sample_target} closed trades",
            met=n >= sample_target,
            detail=f"{n}/{sample_target} closed backtest trades logged",
        ),
        GateRequirement(
            key=f"b2:{model}",
            source="evidence",
            label="Positive expectancy in R over that sample",
            met=exp is not None and exp > 0,
            detail=(
                "no closed backtest trades yet"
                if exp is None
                else f"expectancy {exp:+.2f}R"
                + ("" if exp > 0 else " — must be positive")
            ),
        ),
        GateRequirement(
            key=f"b3:{model}",
            source="evidence",
            label="Win rate clears break-even for its planned R:R",
            met=bool(bt and bt.above_break_even),
            detail=(
                "no planned R:R logged — a win rate without its R:R is meaningless"
                if be is None
                else f"win {win * 100:.0f}% vs break-even {be * 100:.0f}%"
                if win is not None
                else "no closed backtest trades yet"
            ),
        ),
    ]
    return reqs


def _behaviour_requirements(model: str, attested: dict[str, bool]) -> list[GateRequirement]:
    """(c) — the behavioural checklist. Attested per USER (not per model), but
    carried into every model's requirement list so each model's blocking list is
    complete. Attesting these can never satisfy (a) or (b)."""
    return [
        GateRequirement(
            key=f"c:{item}:{model}",
            source="behaviour",
            label=label,
            met=bool(attested.get(item)),
            attest=True,
            detail="self-attested" if attested.get(item) else "not yet attested",
        )
        for item, label in BEHAVIOURAL_ITEMS
    ]


def _blocking_reasons(model: ModelReadiness) -> list[str]:
    """Human-readable "what's blocking live" — the UI's per-model list."""
    out: list[str] = []
    unmet_concepts = [r for r in model.requirements if r.source == "concepts" and not r.met]
    if unmet_concepts:
        shown = ", ".join(r.concept_code or r.concept_slug or "?" for r in unmet_concepts[:4])
        more = f" +{len(unmet_concepts) - 4} more" if len(unmet_concepts) > 4 else ""
        out.append(
            f"{len(unmet_concepts)} concept "
            f"{'requirement' if len(unmet_concepts) == 1 else 'requirements'} short "
            f"({shown}{more})"
        )
    for r in model.requirements:
        if r.source == "evidence" and not r.met:
            out.append(f"{r.label} — {r.detail}")
    unmet_attest = [r for r in model.requirements if r.source == "behaviour" and not r.met]
    if unmet_attest:
        out.append(
            f"{len(unmet_attest)} of {len(BEHAVIOURAL_ITEMS)} behavioural checks not attested"
        )
    return out


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def compute_readiness(
    *,
    concepts: Sequence[ConceptGateView],
    ladder: dict[str, int | None],
    groups: Sequence[expectancy.Group],
    attested: dict[str, bool] | None = None,
    notes: dict[str, str | None] | None = None,
    corroboration: Corroboration | None = None,
    credit_track: str | None = None,
    sample_target: int = expectancy.SAMPLE_TARGET,
    models: Sequence[str] = ALL_MODELS,
) -> GateResult:
    """Compute per-model live-readiness from (a) concepts + (b) evidence + (c) attestation.

    `concepts` are ALL tracks' concepts (cross-ref credit needs the other tracks);
    `ladder` maps concept slug → its ladder stage (absent/None = not started);
    `groups` is the output of `expectancy.compute_groups` over this user's journal.
    """
    attested = attested or {}
    notes = notes or {}
    by_slug = {c.slug: c for c in concepts}

    # (a) the shared core: the anchor track's core U1–U4 concepts, frontier excluded.
    core = [
        c
        for c in concepts
        if c.track == ANCHOR_TRACK
        and c.is_core
        and not c.watch_only
        and (c.u_stage in CORE_STAGES)
    ]
    core.sort(key=lambda c: (c.code or "", c.slug))

    bt_by_model = {g.entry_model: g for g in groups if g.mode == "backtest"}
    live_by_model = {g.entry_model: g for g in groups if g.mode == "live"}

    out = GateResult(
        anchor_track=ANCHOR_TRACK,
        credit_track=credit_track,
        sample_target=sample_target,
        sample_stretch=SAMPLE_STRETCH,
        attestations=[
            AttestationView(
                item=item,
                label=label,
                attested=bool(attested.get(item)),
                note=notes.get(item),
            )
            for item, label in BEHAVIOURAL_ITEMS
        ],
        corroboration=corroboration or Corroboration(),
        frontier=[
            FrontierConcept(
                slug=c.slug, title=c.title, u_stage=c.u_stage, tier=c.tier, label=c.label
            )
            for c in concepts
            if c.watch_only
        ],
    )

    for model in models:
        m = ModelReadiness(entry_model=model, sample_target=sample_target)

        # ---- (a) concepts -------------------------------------------------
        reqs: list[GateRequirement] = []
        if not core:
            reqs.append(
                GateRequirement(
                    key="a1:unseeded",
                    source="concepts",
                    label=f"Core {ANCHOR_TRACK} concepts (U1–U4) at Backtested+",
                    met=False,
                    detail="no core concepts found — re-run scripts.seed_concepts",
                )
            )
        for c in core:
            reqs.append(
                _concept_requirement(
                    c, by_slug, ladder,
                    bar=BACKTESTED, key_prefix="a1", credit_track=credit_track,
                )
            )

        model_slugs = _model_concept_slugs(model)
        if not model_slugs:
            reqs.append(
                GateRequirement(
                    key=f"a2:{model}",
                    source="concepts",
                    label=f"{model} — load-bearing concept at Live-ready",
                    met=False,
                    detail="no entry-model concept mapped for this model",
                )
            )
        for slug in model_slugs:
            anchor = by_slug.get(slug)
            reqs.append(
                _concept_requirement(
                    anchor, by_slug, ladder,
                    bar=LIVE_READY, key_prefix="a2", credit_track=credit_track,
                )
                if anchor is not None
                else _missing_concept_requirement(slug, bar=LIVE_READY, key_prefix="a2")
            )

        # ---- (b) evidence + (c) behaviour ---------------------------------
        bt = bt_by_model.get(model)
        live = live_by_model.get(model)
        ev = _evidence_requirements(model, bt, sample_target=sample_target)
        bh = _behaviour_requirements(model, attested)

        m.requirements = [*reqs, *ev, *bh]
        m.concepts_met = all(r.met for r in reqs)
        m.evidence_met = all(r.met for r in ev)
        m.behaviour_met = all(r.met for r in bh)
        # NON-OVERRIDABLE: the verdict is this conjunction and nothing else.
        m.cleared = m.concepts_met and m.evidence_met and m.behaviour_met

        m.backtest_logged = bt.logged if bt else 0
        m.backtest_n = bt.n if bt else 0
        m.backtest_expectancy = bt.expectancy if bt else None
        m.backtest_win_rate = bt.win_rate if bt else None
        m.backtest_break_even = bt.break_even if bt else None
        m.backtest_avg_rr = bt.avg_rr_planned if bt else None
        m.stretch_met = m.backtest_n >= SAMPLE_STRETCH
        m.live_n = live.n if live else 0
        m.live_expectancy = live.expectancy if live else None

        m.blocking = _blocking_reasons(m)
        out.models.append(m)

    out.any_cleared = any(m.cleared for m in out.models)
    return out
