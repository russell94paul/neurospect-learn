"""Stage exit-bar service (Phase 5e-1 · generalized for multi-track 5e-1b) —
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

Self-attested requirements are surfaced honestly and are not wired until the 5f
journal / 5g gate land, so a stage's *auto_met* (objective, concept-based) is
kept distinct from *met* (fully cleared, incl. attest); the per-track lock chain
uses *auto_met* so an un-wired attestation never permanently freezes a track.
"""

from dataclasses import dataclass, field

from app.services import rep_targets

# Ladder stages (concepts/mastery/README §ladder).
LEARNED, CAN_MARK, BACKTESTED, LIVE_READY = 1, 2, 3, 4

# The two SMT legs the unified U2 gate names (learning-path §U2 stage gate).
_U2_GATE_SLUGS = {"u2-2-triad-smt", "u2-3-sequential-smt"}


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
    attest: bool = False  # self-attested, not wired until 5f/5g
    concept_slug: str | None = None
    concept_code: str | None = None


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
# Unified track — the exact U0–U6 rules (unchanged from 5e-1)
# ---------------------------------------------------------------------------

def _unified_reqs(
    code: str, stage_concepts: list[ConceptView], progress: dict[str, ProgressView]
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
        reqs.append(Requirement(
            label="Routine + written circuit-breakers held ≥1 week; journaling live",
            met=False, attest=True,
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
        reqs.append(Requirement(
            label="Positive expectancy in R computable from journal (Phase 5f)",
            met=False, attest=True,
        ))
        reqs.append(Requirement(
            label="Risk rules precommitted in writing; no sizing up in drawdown",
            met=False, attest=True,
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

    # U6 — Phase 5g placeholder.
    return [Requirement(
        label="Readiness-to-Live Gate — backtest sample + expectancy + gate checklist (Phase 5g)",
        met=False, attest=True,
    )], False


# ---------------------------------------------------------------------------
# Aura / ICT_course — the generic rule
# ---------------------------------------------------------------------------

def _generic_reqs(
    meta: StageMeta, stage_concepts: list[ConceptView], progress: dict[str, ProgressView]
) -> tuple[list[Requirement], bool]:
    if not stage_concepts:
        # Backtest / live / journal — drill/evidence only (5f/5g wire it).
        label = meta.gate_text or "Backtest / live / journal evidence (Phase 5f/5g)"
        return [Requirement(label=label, met=False, attest=True)], False

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
        reqs.append(Requirement(
            label=meta.gate_text or "Discipline routine held; journal live",
            met=False, attest=True,
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
) -> list[StageStatus]:
    """Compute each stage's exit-bar status for `track` from concept_progress.

    `stage_metas` must be the track's stages in order (from track_stages);
    `concepts` are this track's concepts; `progress` maps slug → ProgressView.
    """
    by_stage: dict[str, list[ConceptView]] = {}
    for c in concepts:
        by_stage.setdefault(c.stage_code or "", []).append(c)

    metas = sorted(stage_metas, key=lambda m: m.stage_order)
    statuses: list[StageStatus] = []

    for meta in metas:
        stage_concepts = by_stage.get(meta.stage_code, [])
        watch_only = any(c.watch_only for c in stage_concepts)

        if track == "unified":
            reqs, auto_met = _unified_reqs(meta.stage_code, stage_concepts, progress)
        else:
            reqs, auto_met = _generic_reqs(meta, stage_concepts, progress)

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
        st.met = auto_met and not st.attest_pending
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
