"""Stage exit-bar service (Phase 5e-1 · multi-track 5e-1b · evidence-wired 6a) —
COMPUTED, never stored.

Encodes each track-stage's exit bar as the *as-implemented* gate. The rules are
canonical in, and LINKED (not restated) from, the per-track learning-path pages
+ concepts/mastery/README §ladder/confidence. Per learning-platform.md §Stage
exit-bar derivation this module IS the gate of record — if a learning-path
changes, reconcile it here (CLAUDE §Architecture Doc Integrity).

The UNIFIED track keeps its exact U0–U6 rules (unchanged from 5e-1):
  - U0  every U0 concept ≥ Can-mark  + held-habit attestation (self-attested)
  - U1  the five structural primitives (U1 core) ≥ Can-mark, conf ≥3, reps ≥ target
  - U2  triad SMT + Sequential SMT ≥ Can-mark, conf ≥3
  - U3  U3 core + the entry-model concepts ≥ Can-mark
  - U4  the U4 concepts ≥ Can-mark  + positive-expectancy + risk-precommit (self-attested)
  - U5  FRONTIER — observation-only, watch_only, NEVER live-gate-eligible
  - U6  the readiness arc — placeholder (Phase 5g)

The AURA / ICT_COURSE tracks use the GENERIC rule (learning-platform.md
§Multi-track data model): a stage's gate = its `is_core` concepts ≥ Can-mark
(+ conf ≥3, reps ≥ parsed target where the page specifies). Two shapes:
  - foundation stage (stage_order 0 — psychology/discipline): every concept ≥
    Can-mark (behavioural, no conf/rep floor) + a held-habit self-attestation.
  - concept-less stage (backtest / live / journal): a single attest placeholder
    (auto_met False) carrying the page's descriptive gate_text.

PHASE 6a — THE BEHAVIOURAL / EMPIRICAL BARS ARE NOW WIRED TO REAL EVIDENCE.
Until 6a these rows were emitted `attest=True, met=False` and could never become
met (a dead checkbox teaches the user the process is theatre). They now grade on
evidence that already exists:

  * behavioural bars  → the SHIPPED 5g `gate_attestations` store, mapped
    explicitly in STAGE_ATTESTATIONS. ONE source of truth: the row REFLECTS the
    tick made on /gate — /path never carries a second checkbox of its own.
  * empirical bars    → the SHIPPED 5f pure `services/expectancy.py` (reused,
    never reimplemented) and, for the unified U6 readiness arc, the 5g
    `services/gate.py` verdict. Where a learning-path page NAMES a bar it is
    encoded verbatim (A4/M7's "≥50 setups with positive expectancy in R and a
    win rate clearing break-even" is `expectancy.SAMPLE_TARGET` + the shipped
    `above_break_even`); where it does not, the row stays self-attested and SAYS
    SO rather than inventing a threshold (see STAGE_UNWIRED).

A stage's *auto_met* (objective, CONCEPT-based) stays distinct from *met* (every
requirement satisfied), and the per-track lock chain still uses *auto_met* only —
so wiring the attestations cannot freeze a track on behavioural evidence, and the
lock chain is byte-identical to 5e-1b (asserted in tests/test_stages.py). With no
evidence supplied (`evidence=None`, the pure default) every wired row reads unmet
and the whole result is identical to the pre-6a behaviour.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.services import expectancy, rep_targets

# Ladder stages (concepts/mastery/README §ladder).
LEARNED, CAN_MARK, BACKTESTED, LIVE_READY = 1, 2, 3, 4

# The two SMT legs the unified U2 gate names (learning-path §U2 stage gate).
_U2_GATE_SLUGS = {"u2-2-triad-smt", "u2-3-sequential-smt"}

# ---------------------------------------------------------------------------
# Phase 6a — which shipped evidence grades which stage's exit bar
# ---------------------------------------------------------------------------

# (track, stage_code) → the `gate_attestations` item(s) whose tick evidences this
# stage's BEHAVIOURAL exit bar, plus the row label. Named EXPLICITLY (the
# _U2_GATE_SLUGS / gate.ENTRY_MODEL_CONCEPTS idiom: greppable, and immune to a
# re-seed rewording `track_stages.gate_text`). Keys are the `gate_attestation_item`
# Postgres enum labels == app/services/gate.BEHAVIOURAL_KEYS; the descriptive full
# bar stays where it already lives, in the stage's `gate_text`.
STAGE_ATTESTATIONS: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {
    # unified U0 — "pre-market routine + written circuit-breakers ACTUALLY FOLLOWED
    # for one week; journal live and logging every trade incl. misses"
    ("unified", "U0"): (
        ("circuit_breaker", "Pre-market routine + written circuit-breakers held ≥1 week"),
        ("journaling_habit", "Journal live — every trade logged, including misses"),
    ),
    # unified U4 — "risk rules PRECOMMITTED IN WRITING; no sizing up in a drawdown"
    ("unified", "U4"): (
        ("risk_precommitted", "Risk rules precommitted in writing; no sizing up in a drawdown"),
    ),
    # aura A0 — "circuit breakers written and actually followed for one week; journal live"
    ("aura", "A0"): (
        ("circuit_breaker", "Pre-market 3-question routine + circuit breakers held ≥1 week"),
        ("journaling_habit", "Journal live"),
    ),
    # aura A5 — "a demo/sim track record showing the plan + circuit-breaker
    # discipline hold under live pressure"
    ("aura", "A5"): (
        ("sim_track_record",
         "A demo/sim track record — plan + circuit-breaker discipline held under live pressure"),
    ),
    # aura A6 — "journaling habit established (every trade incl. missed); at least
    # one concrete rule change made from your own logged data"
    ("aura", "A6"): (
        ("journaling_habit",
         "Journaling habit established (every trade incl. missed); ≥1 rule change from your own data"),
    ),
    # ict_course M0 — "loss-limit precommitment written & honoured; set-and-forget
    # contract; three-requirements self-audit; bad-conditions log"
    ("ict_course", "M0"): (
        ("risk_precommitted", "Loss-limit precommitment + set-and-forget contract written"),
        ("circuit_breaker", "Loss limit actually honoured under pressure"),
    ),
    # ict_course M8 — "weekly review + set-and-forget audit + missed/canceled log
    # habit established"
    ("ict_course", "M8"): (
        ("journaling_habit", "Weekly review + set-and-forget audit + missed/canceled log habit"),
    ),
}

# (track, stage_code) → the objective, journal-derived bar its exit bar NAMES.
#   expectancy_computable  unified U4 "can compute a trade's expectancy
#                          contribution in R" — COMPUTABILITY, not positivity
#                          (positivity is A4/M7's bar, not U4's; encode what the
#                          page says, nothing more).
#   backtest_edge          aura A4 / ict_course M7 "≥50 setups … logged with
#                          positive expectancy in R and a known win-rate-with-R:R
#                          clearing break-even" — the three conditions verbatim.
#   gate_verdict           unified U6 "run the full Readiness-to-Live Gate" — the
#                          shipped per-model verdict, rolled up to the stage.
STAGE_EVIDENCE: dict[tuple[str, str], str] = {
    ("unified", "U4"): "expectancy_computable",
    ("unified", "U6"): "gate_verdict",
    ("aura", "A4"): "backtest_edge",
    ("ict_course", "M7"): "backtest_edge",
}

# Stages whose exit bar NO shipped evidence source covers. Left honestly
# self-attested with a note saying where the work is tracked — deliberately NOT
# wired to an invented threshold. `ict_course` M6's bar is drill completion
# (T-01…T-14 on /drills); grading a drill as genuinely done is the subject of the
# learning-enforcement workstream (verified evidence of markings), so self-declared
# drill marks are NOT promoted to stage-gate evidence here.
STAGE_UNWIRED: dict[tuple[str, str], tuple[str, str]] = {
    ("ict_course", "M6"): (
        "no gate attestation covers this bar — the 14 tape studies are tracked on /drills",
        "/drills",
    ),
}


@dataclass(frozen=True)
class Evidence:
    """The already-shipped evidence a behavioural / empirical exit bar grades on
    (Phase 6a). PURE data: the router loads it (`learning.load_stage_evidence`)
    and this module never touches a DB.

    All fields default to "no evidence", so `compute_stages(...)` without an
    Evidence bundle behaves exactly as it did before 6a.
    """

    # (c) the 5g gate_attestations store: item label → attested?
    attested: Mapping[str, bool] = field(default_factory=dict)
    # (b) the POOLED backtest group from the shipped 5f expectancy service
    # (pooled, not per-model: a stage is not per-model, unlike the gate).
    backtest: expectancy.Group | None = None
    sample_target: int = expectancy.SAMPLE_TARGET
    # Objective corroboration shown BESIDE a self-attest (the 5g idiom) — never a
    # threshold, never gating on its own.
    live_logged: int = 0
    journaling_days: int = 0
    missed_logged: int = 0
    # The 5g per-model verdict, rolled up. `gate_computed` distinguishes "the
    # verdict says nothing is cleared" from "the verdict was not loaded for this
    # call" (the planner does not need it) — the latter never guesses.
    cleared_models: tuple[str, ...] = ()
    gate_computed: bool = False


_NO_EVIDENCE = Evidence()


@dataclass(frozen=True)
class ConceptView:
    """The concept fields the gate reads (DB-agnostic → unit-testable)."""

    slug: str
    code: str | None
    stage_code: str | None
    title: str
    is_core: bool
    watch_only: bool
    rep_target: str | None
    u_stage: str | None = None  # unified-only (drives the U-stage special rules)


@dataclass(frozen=True)
class StageMeta:
    """Per-track stage metadata (from track_stages)."""

    track: str
    stage_code: str
    stage_order: int
    title: str
    summary: str | None = None
    gate_text: str | None = None


@dataclass(frozen=True)
class ProgressView:
    ladder_stage: int | None
    confidence: int | None
    reps: int


@dataclass
class Requirement:
    label: str
    met: bool
    attest: bool = False  # satisfied by a user attestation (6a: wired to /gate)
    concept_slug: str | None = None
    concept_code: str | None = None
    # --- Phase 6a -----------------------------------------------------------
    derived: bool = False  # objectively derived from logged evidence (earned, not declared)
    detail: str | None = None  # the evidence in words/numbers, or what is missing
    attest_item: str | None = None  # the `gate_attestations` item this row REFLECTS
    link: str | None = None  # where the row is satisfied ("/gate", "/expectancy", "/drills")


@dataclass
class StageStatus:
    track: str
    stage_code: str
    stage_order: int
    title: str
    summary: str | None
    gate_text: str | None
    watch_only: bool
    never_gate_eligible: bool
    requirements: list[Requirement] = field(default_factory=list)
    concept_slugs: list[str] = field(default_factory=list)
    total: int = 0
    reached: int = 0  # concepts at ≥ Can-mark (the ring numerator)
    auto_met: bool = False
    attest_pending: bool = False
    met: bool = False
    locked: bool = False


def _is_entry_model(c: ConceptView) -> bool:
    """Unified U3 entry-model concepts carry codes U3.2a … U3.2g."""
    return bool(c.code and c.code.startswith("U3.2"))


def _concept_meets(
    c: ConceptView,
    pg: ProgressView | None,
    *,
    min_ladder: int,
    min_conf: int | None,
    require_reps: bool,
) -> bool:
    if pg is None or pg.ladder_stage is None or pg.ladder_stage < min_ladder:
        return False
    if min_conf is not None and (pg.confidence is None or pg.confidence < min_conf):
        return False
    if require_reps and not rep_targets.meets(pg.reps, rep_targets.parse(c.rep_target)):
        return False
    return True


def _req_label(c: ConceptView, *, min_conf: int | None, require_reps: bool) -> str:
    bits = ["Can-mark"]
    if min_conf is not None:
        bits.append(f"conf ≥{min_conf}")
    if require_reps:
        t = rep_targets.parse(c.rep_target)
        if t.has_floor:
            bits.append(f"reps ≥{t.count}")
    return f"{c.title} — {', '.join(bits)}"


# ---------------------------------------------------------------------------
# Phase 6a — the wired behavioural / empirical requirement rows
# ---------------------------------------------------------------------------

def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _corroboration(item: str, ev: Evidence) -> str | None:
    """Objective journal facts shown BESIDE a self-attest so the tick is made in
    the face of the record (the 5g corroboration idiom). Never a threshold."""
    if item == "journaling_habit":
        return (
            f"{_plural(ev.journaling_days, 'journaling day', 'journaling days')}"
            f" · {_plural(ev.missed_logged, 'miss logged', 'misses logged')}"
        )
    if item == "sim_track_record":
        return _plural(ev.live_logged, "live entry logged", "live entries logged")
    return None


def _attestation_reqs(track: str, stage_code: str, ev: Evidence) -> list[Requirement]:
    """The stage's behavioural bar, graded on the SHIPPED 5g `gate_attestations`
    store. The row REFLECTS the /gate tick — it is not a second checkbox."""
    out: list[Requirement] = []
    for item, label in STAGE_ATTESTATIONS.get((track, stage_code), ()):
        met = bool(ev.attested.get(item))
        detail = "attested on the Gate" if met else "attest it on the Gate once it is true"
        corr = _corroboration(item, ev)
        if corr:
            detail = f"{detail} · {corr}"
        out.append(Requirement(
            label=label, met=met, attest=True, attest_item=item, link="/gate", detail=detail,
        ))
    return out


def _evidence_req(kind: str, ev: Evidence) -> Requirement:
    """A stage's EMPIRICAL bar, derived from the shipped 5f expectancy service /
    5g gate verdict. Objectively earned — never self-declared."""
    bt = ev.backtest

    if kind == "expectancy_computable":
        # unified U4: "can compute a trade's expectancy contribution in R".
        # COMPUTABILITY is the whole bar — do NOT read "positive" into it.
        computable = bt is not None and bt.expectancy is not None
        return Requirement(
            label="Can compute a trade's expectancy contribution in R (from your journal)",
            met=computable,
            derived=True,
            link="/expectancy",
            detail=(
                f"expectancy {bt.expectancy:+.2f}R over "
                f"{_plural(bt.n, 'closed backtest trade', 'closed backtest trades')}"
                if computable and bt is not None
                else "no closed backtest trade yet — log a realized R in the journal"
            ),
        )

    if kind == "backtest_edge":
        # aura A4 / ict_course M7: "≥50 setups (ideally ≥100 executed backtest
        # trades) logged with positive expectancy in R and a known
        # win-rate-with-R:R clearing break-even" — all three, verbatim.
        n = bt.n if bt else 0
        exp = bt.expectancy if bt else None
        win = bt.win_rate if bt else None
        be = bt.break_even if bt else None
        sample_ok = n >= ev.sample_target
        positive = exp is not None and exp > 0
        above_be = bool(bt and bt.above_break_even)
        bits = [f"{n}/{ev.sample_target} closed backtest trades"]
        if n == 0:
            bits.append("nothing to compute yet")
        else:
            bits.append("expectancy not computable" if exp is None else f"expectancy {exp:+.2f}R")
            if be is None:
                bits.append("break-even unknown — no planned R:R logged")
            elif win is not None:
                bits.append(f"win {win * 100:.0f}% vs break-even {be * 100:.0f}%")
        return Requirement(
            label=(
                f"≥{ev.sample_target} backtest setups logged with positive expectancy in R "
                "and a win rate clearing break-even"
            ),
            met=sample_ok and positive and above_be,
            derived=True,
            link="/expectancy",
            detail=" · ".join(bits),
        )

    # kind == "gate_verdict" — unified U6: "run the full Readiness-to-Live Gate".
    # A stage is not per-model, so it rolls the shipped per-model verdict up to
    # "at least one entry model cleared" and links to /gate for the detail.
    if not ev.gate_computed:
        return Requirement(
            label="Readiness-to-Live Gate cleared for at least one entry model",
            met=False,
            derived=True,
            link="/gate",
            detail="open the Gate for the per-model verdict",
        )
    return Requirement(
        label="Readiness-to-Live Gate cleared for at least one entry model",
        met=bool(ev.cleared_models),
        derived=True,
        link="/gate",
        detail=(
            "cleared: " + ", ".join(ev.cleared_models)
            if ev.cleared_models
            else "no entry model is cleared to live yet — the Gate computes this per model"
        ),
    )


def _behavioural_reqs(
    track: str, stage_code: str, ev: Evidence, *, fallback_label: str
) -> list[Requirement]:
    """Every wired row for a stage's non-concept bar: derived evidence first, then
    the mapped attestations. Falls back to an honest, explicitly-unwired row when
    no shipped evidence covers the bar (never an invented threshold)."""
    reqs: list[Requirement] = []
    kind = STAGE_EVIDENCE.get((track, stage_code))
    if kind is not None:
        reqs.append(_evidence_req(kind, ev))
    reqs.extend(_attestation_reqs(track, stage_code, ev))
    if reqs:
        return reqs
    note, link = STAGE_UNWIRED.get(
        (track, stage_code),
        ("no gate attestation covers this bar yet — self-attested", None),
    )
    return [Requirement(label=fallback_label, met=False, attest=True, detail=note, link=link)]


# ---------------------------------------------------------------------------
# Unified track — the exact U0–U6 rules (unchanged from 5e-1)
# ---------------------------------------------------------------------------

def _unified_reqs(
    code: str,
    stage_concepts: list[ConceptView],
    progress: dict[str, ProgressView],
    ev: Evidence,
) -> tuple[list[Requirement], bool]:
    reqs: list[Requirement] = []

    if code == "U0":
        for c in stage_concepts:
            pg = progress.get(c.slug)
            reqs.append(Requirement(
                label=f"{c.title} — Can-mark",
                met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=None, require_reps=False),
                concept_slug=c.slug, concept_code=c.code,
            ))
        auto_met = all(r.met for r in reqs) if reqs else False
        # 6a: was one permanently-unmet row; now the two /gate attestations it names.
        reqs.extend(_behavioural_reqs(
            "unified", "U0", ev,
            fallback_label="Routine + written circuit-breakers held ≥1 week; journaling live",
        ))
        return reqs, auto_met

    if code == "U1":
        for c in stage_concepts:
            if not c.is_core:
                continue
            pg = progress.get(c.slug)
            reqs.append(Requirement(
                label=_req_label(c, min_conf=3, require_reps=True),
                met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=3, require_reps=True),
                concept_slug=c.slug, concept_code=c.code,
            ))
        return reqs, (all(r.met for r in reqs) if reqs else False)

    if code == "U2":
        for c in stage_concepts:
            if c.slug not in _U2_GATE_SLUGS:
                continue
            pg = progress.get(c.slug)
            reqs.append(Requirement(
                label=_req_label(c, min_conf=3, require_reps=False),
                met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=3, require_reps=False),
                concept_slug=c.slug, concept_code=c.code,
            ))
        return reqs, (all(r.met for r in reqs) if reqs else False)

    if code == "U3":
        for c in stage_concepts:
            if not (c.is_core or _is_entry_model(c)):
                continue
            pg = progress.get(c.slug)
            reqs.append(Requirement(
                label=_req_label(c, min_conf=None, require_reps=False),
                met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=None, require_reps=False),
                concept_slug=c.slug, concept_code=c.code,
            ))
        return reqs, (all(r.met for r in reqs) if reqs else False)

    if code == "U4":
        for c in stage_concepts:
            pg = progress.get(c.slug)
            reqs.append(Requirement(
                label=f"{c.title} — Can-mark",
                met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=None, require_reps=False),
                concept_slug=c.slug, concept_code=c.code,
            ))
        auto_met = all(r.met for r in reqs) if reqs else False
        # 6a: the expectancy row is now DERIVED from the shipped 5f service and the
        # risk row REFLECTS the /gate `risk_precommitted` attestation. Note the
        # label correction: the page's bar is "CAN COMPUTE a trade's expectancy
        # contribution in R" — not "positive" (that is A4/M7's bar).
        reqs.extend(_behavioural_reqs(
            "unified", "U4", ev,
            fallback_label="Risk rules precommitted in writing; no sizing up in drawdown",
        ))
        return reqs, auto_met

    if code == "U5":
        # Frontier: study-and-watch only; advance to Can-mark (observe).
        for c in stage_concepts:
            pg = progress.get(c.slug)
            reqs.append(Requirement(
                label=f"{c.title} — observed to Can-mark",
                met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=None, require_reps=False),
                concept_slug=c.slug, concept_code=c.code,
            ))
        return reqs, (all(r.met for r in reqs) if reqs else False)

    # U6 — the readiness arc. The Gate is computed per model by services/gate.py;
    # a stage is not per-model, so 6a rolls that verdict up to "at least one entry
    # model cleared" and links to /gate for the per-model detail.
    return _behavioural_reqs(
        "unified", "U6", ev,
        fallback_label="Readiness-to-Live Gate — backtest sample + expectancy + checklist, on /gate",
    ), False


# ---------------------------------------------------------------------------
# Aura / ICT_course — the generic rule
# ---------------------------------------------------------------------------

def _generic_reqs(
    meta: StageMeta,
    stage_concepts: list[ConceptView],
    progress: dict[str, ProgressView],
    ev: Evidence,
) -> tuple[list[Requirement], bool]:
    if not stage_concepts:
        # Backtest / live / journal stages — no concepts of their own. 6a grades
        # them on the shipped journal evidence (A4/M7) or the /gate attestation
        # they name (A5/A6/M8); M6's drill bar stays honestly unwired.
        return _behavioural_reqs(
            meta.track, meta.stage_code, ev,
            fallback_label=(
                meta.gate_text
                or "Backtest / live / journal evidence — logged in /journal, judged on /gate"
            ),
        ), False

    reqs: list[Requirement] = []

    if meta.stage_order == 0:
        # Foundation / discipline — behavioural: every concept ≥ Can-mark.
        for c in stage_concepts:
            pg = progress.get(c.slug)
            reqs.append(Requirement(
                label=f"{c.title} — Can-mark",
                met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=None, require_reps=False),
                concept_slug=c.slug, concept_code=c.code,
            ))
        auto_met = all(r.met for r in reqs) if reqs else False
        reqs.extend(_behavioural_reqs(
            meta.track, meta.stage_code, ev,
            fallback_label=meta.gate_text or "Discipline routine held; journal live",
        ))
        return reqs, auto_met

    # Concept stage: gate on the core concepts (conf ≥3, reps ≥ target where the
    # page specifies a floor). If none are flagged core, fall back to all.
    cores = [c for c in stage_concepts if c.is_core]
    targets = cores or stage_concepts
    for c in targets:
        pg = progress.get(c.slug)
        reqs.append(Requirement(
            label=_req_label(c, min_conf=3, require_reps=True),
            met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=3, require_reps=True),
            concept_slug=c.slug, concept_code=c.code,
        ))
    return reqs, (all(r.met for r in reqs) if reqs else False)


# ---------------------------------------------------------------------------
# Public: compute every stage's exit-bar status for one track
# ---------------------------------------------------------------------------

def compute_stages(
    track: str,
    stage_metas: list[StageMeta],
    concepts: list[ConceptView],
    progress: dict[str, ProgressView],
    evidence: Evidence | None = None,
) -> list[StageStatus]:
    """Compute each stage's exit-bar status for `track` from concept_progress.

    `stage_metas` must be the track's stages in order (from track_stages);
    `concepts` are this track's concepts; `progress` maps slug → ProgressView.

    `evidence` (Phase 6a, optional) supplies the shipped gate-attestation /
    expectancy / gate-verdict evidence the behavioural + empirical bars grade on.
    Omitting it (the pure default) leaves every such row unmet — identical to the
    pre-6a behaviour — and NEVER changes `auto_met` or `locked`, which stay
    concept-based so behavioural evidence can never freeze a track.
    """
    ev = evidence or _NO_EVIDENCE
    by_stage: dict[str, list[ConceptView]] = {}
    for c in concepts:
        by_stage.setdefault(c.stage_code or "", []).append(c)

    metas = sorted(stage_metas, key=lambda m: m.stage_order)
    statuses: list[StageStatus] = []

    for meta in metas:
        stage_concepts = by_stage.get(meta.stage_code, [])
        watch_only = any(c.watch_only for c in stage_concepts)

        if track == "unified":
            reqs, auto_met = _unified_reqs(meta.stage_code, stage_concepts, progress, ev)
        else:
            reqs, auto_met = _generic_reqs(meta, stage_concepts, progress, ev)

        st = StageStatus(
            track=track,
            stage_code=meta.stage_code,
            stage_order=meta.stage_order,
            title=meta.title,
            summary=meta.summary,
            gate_text=meta.gate_text,
            watch_only=watch_only,
            never_gate_eligible=watch_only,
            requirements=reqs,
            concept_slugs=[c.slug for c in stage_concepts],
            total=len(stage_concepts),
        )
        st.reached = sum(
            1
            for c in stage_concepts
            if (pg := progress.get(c.slug)) and pg.ladder_stage and pg.ladder_stage >= CAN_MARK
        )
        st.attest_pending = any(r.attest and not r.met for r in reqs)
        st.auto_met = auto_met
        # Every requirement satisfied — concept rows, wired attestations AND the
        # 6a derived evidence rows. (Pre-6a this was `auto_met and not
        # attest_pending`, which is the same expression when the only non-concept
        # rows are attestations; the generalization is what lets a concept-less
        # backtest stage read "met" once its evidence is actually in.)
        st.met = all(r.met for r in reqs) if reqs else False
        statuses.append(st)

    # ---- Lock chain --------------------------------------------------------
    if track == "unified":
        _lock_unified(statuses)
    else:
        # Sequential: a stage is locked until every earlier stage is auto_met.
        chain_ok = True
        for st in statuses:
            st.locked = not chain_ok
            chain_ok = chain_ok and st.auto_met

    return statuses


def _lock_unified(statuses: list[StageStatus]) -> None:
    """Unified's exact lock chain: core U0–U4 chain on auto_met; U5/U6 on U1–U4."""
    by_code = {s.stage_code: s for s in statuses}
    core_all_met = True
    for code in ("U0", "U1", "U2", "U3", "U4"):
        if code in by_code:
            by_code[code].locked = not core_all_met
            core_all_met = core_all_met and by_code[code].auto_met
    u1_u4_met = all(by_code[c].auto_met for c in ("U1", "U2", "U3", "U4") if c in by_code)
    for code in ("U5", "U6"):
        if code in by_code:
            by_code[code].locked = not u1_u4_met
