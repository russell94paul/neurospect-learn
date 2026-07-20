"""Stage exit-bar service (Phase 5e-1) — COMPUTED, never stored.

Encodes each U0–U4 stage's exit bar as the *as-implemented* gate. The rules
themselves are canonical in, and LINKED (not restated) from,
concepts/mastery/unified/learning-path.md §Stage gate + concepts/mastery/README
§ladder/confidence. Per learning-platform.md §Stage exit-bar derivation this
module IS the gate of record — if learning-path changes, reconcile it here
(CLAUDE §Architecture Doc Integrity).

The bars encoded (each stage's own gate, independent of lock state):
  - U0  every U0 concept ≥ Can-mark  + held-habit attestation (self-attested)
  - U1  the five structural primitives (U1 core) ≥ Can-mark, conf ≥3, reps ≥ target
  - U2  triad SMT + Sequential SMT ≥ Can-mark, conf ≥3
  - U3  U3 core + the entry-model concepts ≥ Can-mark
  - U4  the U4 concepts ≥ Can-mark  + positive-expectancy + risk-precommit (self-attested)
  - U5  FRONTIER — observation-only, watch_only, NEVER live-gate-eligible;
        unlocks only after U1–U4; its concepts advance to Can-mark (observe) only
  - U6  the readiness arc — OUT OF SCOPE here (Phase 5g); placeholder node

Self-attested requirements (U0 held-habit; U4 expectancy + risk precommit) are
**surfaced honestly, never hidden**, and are not wired until the 5f journal /
5g gate land. So a stage's *auto_met* (objective, concept-based) is kept
distinct from its *met* (fully cleared, incl. attest): the lock chain uses
*auto_met* so an un-wired attestation does not permanently freeze the curriculum
in 5e-1, while the UI still shows the attestation as outstanding.
"""

from dataclasses import dataclass, field

from app.services import rep_targets

# Ladder stages (concepts/mastery/README §ladder).
LEARNED, CAN_MARK, BACKTESTED, LIVE_READY = 1, 2, 3, 4

STAGE_ORDER = ["U0", "U1", "U2", "U3", "U4", "U5", "U6"]
_CORE_STAGES = ["U0", "U1", "U2", "U3", "U4"]  # the objective, non-frontier chain

STAGE_TITLES = {
    "U0": "Psychology & discipline",
    "U1": "Structural primitives",
    "U2": "Nested SMT stack",
    "U3": "Execution",
    "U4": "Risk",
    "U5": "Frontier confluence-stacking",
    "U6": "Readiness arc",
}

# The two SMT legs the U2 gate names (learning-path §U2 stage gate).
_U2_GATE_SLUGS = {"u2-2-triad-smt", "u2-3-sequential-smt"}


@dataclass(frozen=True)
class ConceptView:
    """The concept fields the gate reads (DB-agnostic → unit-testable)."""

    slug: str
    code: str | None
    u_stage: str
    title: str
    is_core: bool
    watch_only: bool
    rep_target: str | None


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
    u_stage: str
    title: str
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
    """U3 entry-model concepts carry codes U3.2a … U3.2g."""
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
    label = c.title
    return f"{label} — {', '.join(bits)}"


def compute_stages(
    concepts: list[ConceptView], progress: dict[str, ProgressView]
) -> list[StageStatus]:
    """Compute every stage's exit-bar status from the user's concept_progress."""
    by_stage: dict[str, list[ConceptView]] = {s: [] for s in STAGE_ORDER}
    for c in concepts:
        by_stage.setdefault(c.u_stage, []).append(c)

    statuses: dict[str, StageStatus] = {}

    for code in STAGE_ORDER:
        stage_concepts = by_stage.get(code, [])
        watch_only = code == "U5"
        st = StageStatus(
            u_stage=code,
            title=STAGE_TITLES.get(code, code),
            watch_only=watch_only,
            never_gate_eligible=watch_only,  # frontier never counts toward live
            concept_slugs=[c.slug for c in stage_concepts],
            total=len(stage_concepts),
        )
        st.reached = sum(
            1
            for c in stage_concepts
            if (pg := progress.get(c.slug)) and pg.ladder_stage and pg.ladder_stage >= CAN_MARK
        )

        reqs: list[Requirement] = []

        if code == "U0":
            # Behavioural: every U0 concept marked (Can-mark). No conf/rep floor.
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

        elif code == "U1":
            for c in stage_concepts:
                if not c.is_core:
                    continue
                pg = progress.get(c.slug)
                reqs.append(Requirement(
                    label=_req_label(c, min_conf=3, require_reps=True),
                    met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=3, require_reps=True),
                    concept_slug=c.slug, concept_code=c.code,
                ))
            auto_met = all(r.met for r in reqs) if reqs else False

        elif code == "U2":
            for c in stage_concepts:
                if c.slug not in _U2_GATE_SLUGS:
                    continue
                pg = progress.get(c.slug)
                reqs.append(Requirement(
                    label=_req_label(c, min_conf=3, require_reps=False),
                    met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=3, require_reps=False),
                    concept_slug=c.slug, concept_code=c.code,
                ))
            auto_met = all(r.met for r in reqs) if reqs else False

        elif code == "U3":
            for c in stage_concepts:
                if not (c.is_core or _is_entry_model(c)):
                    continue
                pg = progress.get(c.slug)
                reqs.append(Requirement(
                    label=_req_label(c, min_conf=None, require_reps=False),
                    met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=None, require_reps=False),
                    concept_slug=c.slug, concept_code=c.code,
                ))
            auto_met = all(r.met for r in reqs) if reqs else False

        elif code == "U4":
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

        elif code == "U5":
            # Frontier: study-and-watch only; advance to Can-mark (observe).
            for c in stage_concepts:
                pg = progress.get(c.slug)
                reqs.append(Requirement(
                    label=f"{c.title} — observed to Can-mark",
                    met=_concept_meets(c, pg, min_ladder=CAN_MARK, min_conf=None, require_reps=False),
                    concept_slug=c.slug, concept_code=c.code,
                ))
            # Observation completeness is informational — NEVER a live gate.
            auto_met = all(r.met for r in reqs) if reqs else False

        else:  # U6 — Phase 5g
            reqs.append(Requirement(
                label="Readiness-to-Live Gate — backtest sample + expectancy + gate checklist (Phase 5g)",
                met=False, attest=True,
            ))
            auto_met = False

        st.requirements = reqs
        st.attest_pending = any(r.attest and not r.met for r in reqs)
        st.auto_met = auto_met
        st.met = auto_met and not st.attest_pending
        statuses[code] = st

    # ---- Lock chain: uses auto_met so un-wired attestations don't freeze ----
    core_all_met = True
    for code in _CORE_STAGES:
        statuses[code].locked = not core_all_met
        core_all_met = core_all_met and statuses[code].auto_met
    u1_u4_met = all(statuses[c].auto_met for c in ["U1", "U2", "U3", "U4"])
    # U5/U6 gate on U1–U4 (learning-path: frontier is deliberately last).
    statuses["U5"].locked = not u1_u4_met
    statuses["U6"].locked = not u1_u4_met

    return [statuses[c] for c in STAGE_ORDER]
