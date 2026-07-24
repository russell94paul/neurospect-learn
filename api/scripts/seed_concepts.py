"""Idempotent seed for the `concepts` table (multi-track, Phase 5e-1b).

Sources of truth (READ-ONLY wiki pages — consumed/linked, never restated):
  - unified (U0–U6)   concepts/mastery/unified/learning-path.md + tracker.md
  - aura    (A0–A6)   concepts/mastery/aura/learning-path.md + exercises.md
  - ict_course (M0–M8) concepts/course/README.md + mastery/ict-course/exercises.md
Seeds `concepts` ONLY — `concept_progress` rows are created per-user at runtime.

Run:  poetry run python -m scripts.seed_concepts     (from api/)

Idempotent: UPSERT on `slug` (ON CONFLICT DO UPDATE). Re-running refreshes the
seeded columns without creating duplicates.

Multi-track (5e-1b): every concept carries `track` (aura|ict_course|unified),
`stage_code` (A1/M2/U1) and `stage_order` (the (track, stage_code) grouping the
`/path/:track/:stage` curriculum unit renders). A concept taught by two mentors
is DUPLICATED across tracks on purpose. `cross_refs` (equivalent slugs in the
OTHER tracks) are assigned from EQUIV_GROUPS at build time (guaranteed to
resolve; symmetric; never same-track). The 41 unified rows keep `u_stage`
(unified-only); aura/ict_course rows leave it NULL.

Notes on the data:
- `is_core` follows each track's learning-path explicit core/gate annotations —
  NOT invented (unified: tracker.md; aura: the 3 Stage-1 primitives + Seq SMT/
  Skip + cascade + risk; ict: the module lessons the module gate names).
- `watch_only` is true for every frontier (U5, unified) row. The DB enforces
  `u_stage <> 'U5' OR NOT is_core`.
- `content_slug` resolves against the 5d `content_pages` slug scheme (verified).
- Concept-less stages (unified U6; aura A4–A6; ict M6–M8 — backtest/live/journal)
  carry NO gradable concept rows; their `track_stages` metadata + drills stand
  alone (5f/5g wire the evidence). Faithful to the wiki (drills, not concepts).
"""

import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import AsyncSessionLocal, engine
from app.models.concept import Concept

# fmt: off
CONCEPTS: list[dict] = []

# Unified u_stage → stage_order (U0..U6 → 0..6). Unified stage_code == u_stage.
_USTAGE_ORDER = {"U0": 0, "U1": 1, "U2": 2, "U3": 3, "U4": 4, "U5": 5, "U6": 6}


def _c(slug, code, u_stage, title, is_core=False, tier=None, label=None, axis=None,
       watch_only=False, rep_target=None, content_slug=None, drill_refs=None, notes=None,
       track="unified", stage_code=None, stage_order=None):
    # Unified rows: derive the per-track stage from u_stage (stage_code == U-stage).
    if track == "unified":
        stage_code = stage_code or u_stage
        stage_order = _USTAGE_ORDER[u_stage] if stage_order is None else stage_order
    CONCEPTS.append(dict(
        slug=slug, code=code, u_stage=u_stage, title=title, is_core=is_core,
        tier=tier, label=label, axis=axis, watch_only=watch_only,
        rep_target=rep_target, content_slug=content_slug,
        drill_refs=drill_refs or [], notes=notes, sort_order=len(CONCEPTS),
        track=track, stage_code=stage_code, stage_order=stage_order,
        cross_refs=None,  # assigned from EQUIV_GROUPS below
    ))


# --- U0 — Psychology & discipline (behavioural; held-habit gate) ------------
_c("u0-identity-killers", "U0", "U0", "Identity / four killers / circuit breakers",
   content_slug="mind-and-emotional-control", drill_refs=["aura D0-a", "aura D0-b", "aura D0-c"],
   notes="R8 · behavioural")
_c("u0-routine-environment", "U0", "U0", "Routine & environment",
   content_slug="discipline-systems", drill_refs=["aura D0-a", "ict-course D0-d"])
_c("u0-loss-limit-precommitment", "U0", "U0", "Loss-limit precommitment (R5)",
   content_slug="discipline-systems", drill_refs=["ict-course D0-a"],
   notes="%/R blueprint = framework")
_c("u0-set-and-forget", "U0", "U0", "Set-and-forget contract",
   content_slug="discipline-systems", drill_refs=["ict-course D0-b"])
_c("u0-journal-live", "U0", "U0", "Journal live (every trade incl. misses)",
   content_slug="journaling-system", drill_refs=["aura D0-d", "ict-course D0-e"],
   notes="prerequisite for size")

# --- U1 — Structural primitives (eye-training core; by hand) — all core -----
_c("u1-1-liquidity-draw", "U1.1", "U1", "Liquidity & draw (BSL/SSL/DOL)", is_core=True,
   rep_target="≥5 + ≥50 swings", content_slug="ict-liquidity",
   drill_refs=["ict-course D1-a", "aura D1-a"])
_c("u1-2-range-premium-discount", "U1.2", "U1", "Range & premium/discount (R3)", is_core=True,
   rep_target="≥50 ranges", content_slug="ranges",
   drill_refs=["aura D1-b", "ict-course D5-a"])
_c("u1-3-double-qualified-swing", "U1.3", "U1", "Double-qualified swing (R2, 0/1/2)", is_core=True,
   rep_target="score by hand", content_slug="ict-market-structure",
   drill_refs=["ict-course D1-a", "ict-course D4-a", "aura D1-a"], notes="needs both filters")
_c("u1-4-gaps-within", "U1.4", "U1", "Gaps & what lies within", is_core=True,
   rep_target="≥20 gaps", content_slug="gaps",
   drill_refs=["aura D1-c", "ict-course D1-b"])
_c("u1-5-delivery-narrative", "U1.5", "U1", "Delivery narrative (PO3 / four stages)", is_core=True,
   rep_target="5 sessions / 10 days", content_slug="ict-narratives",
   drill_refs=["ict-course D2-a", "ict-course D3-a"], notes="real vs. fake retracement")

# --- U2 — Confirmation: the nested SMT stack ⭐ ------------------------------
_c("u2-1-triads-asset-selection", "U2.1", "U2", "Triads & asset selection (validated)",
   rep_target="1 triad + spot-check", content_slug="triads-asset-selection",
   drill_refs=["aura D2-a"])
_c("u2-2-triad-smt", "U2.2", "U2", "Same-TF triad SMT (LTF trigger)", is_core=True,
   rep_target="5 days", content_slug="ict-smt", drill_refs=["ict-course D5-b"])
_c("u2-3-sequential-smt", "U2.3", "U2", "Sequential SMT (HTF anchor)", is_core=True,
   rep_target="~50", content_slug="sequential-smt", drill_refs=["aura D2-c"])
_c("u2-4-nested-smt-stack", "U2.4", "U2", "Nested SMT stack (R1) + Sequential Skip", is_core=True,
   rep_target="simple-first", content_slug=None, drill_refs=["aura D2-d"],
   notes="the confluence to wait for; synthesis across unified/README + divergence-rulings")
_c("u2-5-aura-asset", "U2.5", "U2", "Aura Asset / 6S (optional 4th leg, R7)",
   rep_target="≥20", content_slug="aura-asset", drill_refs=["aura D2-b"],
   notes="adopt quant case; ignore origin story")

# --- U3 — Execution (time → entry → levels) ---------------------------------
_c("u3-1a-kill-zones", "U3.1a", "U3", "Kill zones / session windows", is_core=True,
   rep_target="1 week", content_slug="session-kill-zones", drill_refs=["ict-course D3-b"])
_c("u3-1b-deviations", "U3.1b", "U3", "Deviations (Fib targeting)",
   rep_target="10 days", content_slug=None, drill_refs=["ict-course D3-c"])
_c("u3-1c-daily-bias", "U3.1c", "U3", "Daily bias (day-of-week)", is_core=True,
   rep_target="10 days", content_slug="daily-bias", drill_refs=["ict-course D3-d"])
_c("u3-2a-consolidation", "U3.2a", "U3", "Consolidation model",
   rep_target="Class-2 hw", content_slug="consolidation-model", drill_refs=["ict-course D2-b"],
   notes="YAML canonical — don't fork")
_c("u3-2b-expansion-retracement", "U3.2b", "U3", "Expansion & Retracement model",
   rep_target="≥10", content_slug="expansion-retracement-model", drill_refs=["ict-course D2-c"])
_c("u3-2c-reversal-raid", "U3.2c", "U3", "Reversal — raid on stops",
   rep_target="≥10", content_slug="reversal-raid-on-stops", drill_refs=["ict-course D2-d"])
_c("u3-2d-london", "U3.2d", "U3", "London model",
   rep_target="≥10", content_slug="london-model", drill_refs=["ict-course S7"])
_c("u3-2e-model-2022-ote", "U3.2e", "U3", "Model 2022 OTE + CSD (richer PDA, R4)",
   rep_target="≥10", content_slug="model-2022-ote", drill_refs=["ict-course D4-d"],
   notes="reach only when structure calls")
_c("u3-2f-daily-bias-filter", "U3.2f", "U3", "Daily-bias filter model",
   rep_target=None, content_slug="daily-bias-model", drill_refs=["ict-course D3-d"],
   notes="filter, not entry/exit")
_c("u3-2g-smt-confirmation-entry", "U3.2g", "U3", "SMT-confirmation entry (U2 executable)",
   rep_target="≥10", content_slug="smt-confirmation-entry", drill_refs=["ict-course D5-b"],
   notes="default FVG/iFVG (R4)")
_c("u3-3-htf-ltf-cascade", "U3.3", "U3", "HTF→LTF cascade + stop/target",
   rep_target="per entry", content_slug="htf-ltf-application", drill_refs=["aura D3-a"],
   notes="write confirm and invalidate")

# --- U4 — Risk --------------------------------------------------------------
_c("u4-r-blueprint", "U4", "U4", "R-multiple blueprint (R5) — 1–2% / 2–3R stop / 10R breaker",
   content_slug="risk-management", drill_refs=["aura D3-c"],
   notes="canonical numbers on aura/risk-management")
_c("u4-expectancy-math", "U4", "U4", "Expectancy / break-even math",
   content_slug="risk-management", drill_refs=["aura D3-c"],
   notes="(win%×avgWinR)−(loss%×avgLossR)")
_c("u4-evolving-r", "U4", "U4", "Evolving-R trade management",
   content_slug="risk-management", drill_refs=["aura D3-c"],
   notes="recalc risk from current price")

# --- U5 — Frontier confluence-stacking ⚠ study-and-watch only ---------------
_c("u5-ipda-ranges", "U5", "U5", "IPDA 20/40/60-day ranges", axis="WHERE", watch_only=True,
   tier="Tier 1", label="ESTABLISHED", content_slug="ipda-data-ranges",
   drill_refs=["ict-course D1-a", "aura D1-c"],
   notes="windows + trading-days Tier 1; 20→40→60 ranking Tier-3 UNVERIFIED")
_c("u5-irl-erl", "U5", "U5", "IRL / ERL cycle", axis="WHERE", watch_only=True,
   tier="Tier 2", label="ESTABLISHED", content_slug="ipda-data-ranges",
   drill_refs=["ict-course D1-a"])
_c("u5-liquidity-matrix", "U5", "U5", '"Liquidity matrix" (use PD Array Matrix instead)',
   axis="WHERE", watch_only=True, tier=None, label="SPECULATIVE",
   content_slug="ipda-data-ranges", drill_refs=[],
   notes="⛔ not edge — do not build a concept off this")
_c("u5-cbdr-asian-range", "U5", "U5", "CBDR / Asian range / flout", axis="WHERE", watch_only=True,
   tier="Tier 1", label="ESTABLISHED", content_slug="cbdr-and-sd-projections",
   drill_refs=["ict-course D3-c"],
   notes="measure on bodies · Asian range 20:00–00:00 ET · index-point calibration still an open gap")
_c("u5-sd-projections", "U5", "U5", "SD projections (arithmetic ≠ Fib ≠ std-dev)",
   axis="WHERE", watch_only=True, tier=None, label="EMERGING",
   content_slug="cbdr-and-sd-projections", drill_refs=["ict-course D3-c"],
   notes="method ESTABLISHED / multiples EMERGING · ⚠ watch-only")
_c("u5-silver-bullet", "U5", "U5", "Silver Bullet (3 one-hour windows)", axis="WHEN", watch_only=True,
   tier="Tier 1", label="ESTABLISHED", content_slug="ict-macros-and-silver-bullet",
   drill_refs=["ict-course D3-b"], notes="disciplined recipe, not proven-edge")
_c("u5-ict-macros", "U5", "U5", "ICT Macros (~20-min windows)", axis="WHEN", watch_only=True,
   tier="Tier 2-3", label="ESTABLISHED", content_slug="ict-macros-and-silver-bullet",
   drill_refs=["ict-course D3-b"], notes="ESTABLISHED concept / reconstructed table · time attention, not a trigger")
_c("u5-killzone-microstructure", "U5", "U5", "Killzone micro-structure / Judas swing",
   axis="WHEN", watch_only=True, tier="Tier 2", label="ESTABLISHED",
   content_slug="ict-macros-and-silver-bullet", drill_refs=["ict-course D3-b"],
   notes="sequence ESTABLISHED / boundaries disputed")
_c("u5-quarterly-theory", "U5", "U5", "Quarterly Theory / 90-min cycles", axis="WHEN", watch_only=True,
   tier="Tier 2", label="EMERGING", content_slug="quarterly-theory",
   drill_refs=["ict-course D3-a"], notes="Trader Daye, not ICT · daily level best-corroborated · ⚠ watch-only")
_c("u5-midnight-open", "U5", "U5", "Midnight Open (00:00 ET) bias", axis="DIRECTION", watch_only=True,
   tier="Tier 1", label="ESTABLISHED", content_slug="quarterly-theory",
   drill_refs=["ict-course D3-d"], notes="partial/caveated · NDOG = target, not bias rule")
_c("u5-smt-confirm-axis", "U5", "U5", "SMT triad non-confirmation (= U2)", axis="CONFIRM", watch_only=True,
   tier=None, label=None, content_slug=None, drill_refs=[],
   notes="= U2 nested stack · required — filters worthless without it")
_c("u5-confluence-stack", "U5", "U5", "The 4-axis confluence stack (combined)", axis="STACK", watch_only=True,
   tier=None, label="EMERGING", content_slug=None, drill_refs=[],
   notes="EMERGING, unbacktested here · ⛔ never trade live on this")

# ===========================================================================
# AURA track (A0–A6) — concepts/mastery/aura/learning-path.md + exercises.md.
# A4–A6 (backtest / live tape / journal) are drill-only → no concept rows.
# ===========================================================================
def _a(slug, title, stage_code, stage_order, is_core=False, rep_target=None,
       content_slug=None, drill_refs=None, notes=None):
    _c(slug, None, None, title, is_core=is_core, rep_target=rep_target,
       content_slug=content_slug, drill_refs=drill_refs, notes=notes,
       track="aura", stage_code=stage_code, stage_order=stage_order)

# --- A0 — Foundation: psychology & discipline ---
_a("aura-psychology-foundations", "Psychology foundations & self-audit", "A0", 0,
   content_slug="psychology-foundations", drill_refs=["aura D0-e"])
_a("aura-mind-emotional-control", "Mind & emotional control (four killers, circuit breakers)", "A0", 0,
   content_slug="mind-and-emotional-control", drill_refs=["aura D0-b", "aura D0-c"])
_a("aura-discipline-systems", "Discipline systems & routine", "A0", 0,
   content_slug="discipline-systems", drill_refs=["aura D0-a"])
_a("aura-journaling-system", "Journaling system", "A0", 0,
   content_slug="journaling-system", drill_refs=["aura D0-d"])

# --- A1 — The three structural primitives (by hand; all core) ---
_a("aura-swing-points", "Swing points", "A1", 1, is_core=True, rep_target="≥50",
   content_slug="swing-points", drill_refs=["aura D1-a"])
_a("aura-ranges", "Ranges (expansive-move method)", "A1", 1, is_core=True, rep_target="≥50 ranges",
   content_slug="ranges", drill_refs=["aura D1-b"])
_a("aura-gaps", "Gaps & what lies within", "A1", 1, is_core=True, rep_target="reuses 50 ranges",
   content_slug="gaps", drill_refs=["aura D1-c"])

# --- A2 — The confirmation engine ---
_a("aura-triads-asset-selection", "Triads & asset selection", "A2", 2, rep_target="1 triad + spot-check",
   content_slug="triads-asset-selection", drill_refs=["aura D2-a"])
_a("aura-aura-asset", "Aura Asset / 6S (optional 4th SMT leg)", "A2", 2, rep_target="≥20",
   content_slug="aura-asset", drill_refs=["aura D2-b"])
_a("aura-sequential-smt", "Sequential SMT", "A2", 2, is_core=True, rep_target="~50",
   content_slug="sequential-smt", drill_refs=["aura D2-c"])
_a("aura-sequential-skip", "Sequential Skip", "A2", 2, is_core=True, rep_target="simple-first",
   content_slug="sequential-smt", drill_refs=["aura D2-d"], notes="down-cycle + cross-asset")

# --- A3 — Putting it together: the cascade & risk ---
_a("aura-htf-ltf-cascade", "HTF→LTF cascade + stop/target", "A3", 3, is_core=True, rep_target="per entry",
   content_slug="htf-ltf-application", drill_refs=["aura D3-a"], notes="write confirm AND invalidate")
_a("aura-time-sum", "Time Sum (de-emphasized — awareness only)", "A3", 3,
   content_slug="time-sum", drill_refs=[])
_a("aura-risk-management", "Risk management & expectancy in R", "A3", 3, is_core=True,
   rep_target="per backtest batch", content_slug="risk-management", drill_refs=["aura D3-c"])

# ===========================================================================
# ICT_COURSE (AXL / MrWitness) track (M0–M8) — concepts/course/README.md +
# mastery/ict-course/exercises.md. M6–M8 (tape / backtest / journal) are
# drill-only → no concept rows.
# ===========================================================================
def _m(slug, title, stage_code, stage_order, is_core=False, rep_target=None,
       content_slug=None, drill_refs=None, notes=None):
    _c(slug, None, None, title, is_core=is_core, rep_target=rep_target,
       content_slug=content_slug, drill_refs=drill_refs, notes=notes,
       track="ict_course", stage_code=stage_code, stage_order=stage_order)

# --- M0 — Discipline & journal setup ---
_m("ict-loss-limit-precommit", "Loss-limit precommitment (R37)", "M0", 0,
   content_slug="ict-live-commentary", drill_refs=["ict-course D0-a"])
_m("ict-set-and-forget", "Set-and-forget contract (R38)", "M0", 0,
   content_slug="ict-live-commentary", drill_refs=["ict-course D0-b"])
_m("ict-journal-setup", "Journal & missed-trade log setup", "M0", 0,
   content_slug="journaling-system", drill_refs=["ict-course D0-e"])

# --- M1 — Module 1: Foundations (eye-training core) ---
_m("ict-liquidity-swings", "Liquidity & swing points (BSL/SSL/DOL)", "M1", 1, is_core=True, rep_target="≥5",
   content_slug="what-moves-the-market", drill_refs=["ict-course D1-a"])
_m("ict-fvg", "Fair value gaps (BISI/SIBI/IOFED/inversion)", "M1", 1, is_core=True, rep_target="≥20 gaps",
   content_slug="fair-value-gaps", drill_refs=["ict-course D1-b"])

# --- M2 — Module 2: Price delivery ---
_m("ict-four-stages-apd", "Four stages of algorithmic price delivery", "M2", 2, is_core=True,
   rep_target="5 sessions", content_slug="four-stages-apd", drill_refs=["ict-course D2-a"])
_m("ict-consolidation", "Consolidation model", "M2", 2, rep_target="Class-2 hw",
   content_slug="module-2-price-delivery-consolidation-model", drill_refs=["ict-course D2-b"])
_m("ict-expansion-retracement", "Expansion & Retracement model", "M2", 2, rep_target="≥10",
   content_slug="expansion-retracement", drill_refs=["ict-course D2-c"])
_m("ict-reversals", "Reversals (three types)", "M2", 2, rep_target="≥10",
   content_slug="reversals", drill_refs=["ict-course D2-d"])

# --- M3 — Module 3: Session context & bias ---
_m("ict-power-of-three", "Power of Three (AMD)", "M3", 3, is_core=True, rep_target="10 days",
   content_slug="power-of-three", drill_refs=["ict-course D3-a"])
_m("ict-kill-zones", "Session kill zones & opening prices", "M3", 3, is_core=True, rep_target="1 week",
   content_slug="session-kill-zones", drill_refs=["ict-course D3-b"])
_m("ict-deviations", "Deviations (Fibonacci targeting)", "M3", 3, rep_target="10 days",
   content_slug="deviations", drill_refs=["ict-course D3-c"])
_m("ict-daily-bias", "Daily bias (day-of-week)", "M3", 3, is_core=True, rep_target="10 days",
   content_slug="daily-bias", drill_refs=["ict-course D3-d"])

# --- M4 — Module 4: Market structure ---
_m("ict-swing-classification", "Swing classification (STH/ITH/LTH)", "M4", 4, is_core=True, rep_target="5 days",
   content_slug="swing-classification", drill_refs=["ict-course D4-a"])
_m("ict-fractality", "Market structure fractality", "M4", 4, rep_target="5 days",
   content_slug="fractality", drill_refs=["ict-course D4-b"])
_m("ict-structure-deviations", "Structure deviations (two-set targeting)", "M4", 4, rep_target="≥10",
   content_slug="structure-deviations", drill_refs=["ict-course D4-c"])
_m("ict-model-2022-ote", "Model 2022, OTE, CSD", "M4", 4, rep_target="≥10",
   content_slug="model-2022-ote-csd", drill_refs=["ict-course D4-d"])

# --- M5 — Module 5: Order flow & SMT ---
_m("ict-order-flow", "HTF/LTF order flow (closing basis)", "M5", 5, is_core=True, rep_target="1 week",
   content_slug="htf-ltf-order-flow", drill_refs=["ict-course D5-a"])
_m("ict-smt-divergence", "SMT divergence", "M5", 5, is_core=True, rep_target="5 days",
   content_slug="smt-divergence", drill_refs=["ict-course D5-b"])
# fmt: on

# ===========================================================================
# Cross-track equivalences → cross_refs ("Also taught in …"). Each group lists
# the equivalent concept slugs ACROSS tracks; a concept's cross_refs = the other
# members whose track differs (display-only, never merges progress). Assigned
# here so they are guaranteed to resolve (a typo raises at build).
# ===========================================================================
EQUIV_GROUPS: list[list[str]] = [
    ["u1-1-liquidity-draw", "aura-swing-points", "ict-liquidity-swings"],
    ["u1-2-range-premium-discount", "aura-ranges", "ict-order-flow"],
    ["u1-3-double-qualified-swing", "ict-swing-classification"],
    ["u1-4-gaps-within", "aura-gaps", "ict-fvg"],
    ["u1-5-delivery-narrative", "ict-four-stages-apd", "ict-power-of-three"],
    ["u2-1-triads-asset-selection", "aura-triads-asset-selection"],
    ["u2-2-triad-smt", "ict-smt-divergence"],
    ["u2-3-sequential-smt", "aura-sequential-smt"],
    ["u2-4-nested-smt-stack", "aura-sequential-skip"],
    ["u2-5-aura-asset", "aura-aura-asset"],
    ["u3-1a-kill-zones", "ict-kill-zones"],
    ["u3-1b-deviations", "ict-deviations"],
    ["u3-1c-daily-bias", "ict-daily-bias"],
    ["u3-2a-consolidation", "ict-consolidation"],
    ["u3-2b-expansion-retracement", "ict-expansion-retracement"],
    ["u3-2c-reversal-raid", "ict-reversals"],
    ["u3-2e-model-2022-ote", "ict-model-2022-ote"],
    ["u3-3-htf-ltf-cascade", "aura-htf-ltf-cascade"],
    ["u4-r-blueprint", "u4-expectancy-math", "u4-evolving-r", "aura-risk-management"],
]


def _assign_cross_refs() -> None:
    by_slug = {c["slug"]: c for c in CONCEPTS}
    for group in EQUIV_GROUPS:
        for s in group:
            if s not in by_slug:
                raise SystemExit(f"EQUIV_GROUPS references unknown concept slug: {s}")
        for s in group:
            track = by_slug[s]["track"]
            refs = sorted(o for o in group if o != s and by_slug[o]["track"] != track)
            by_slug[s]["cross_refs"] = refs or None


_assign_cross_refs()


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(Concept).values(CONCEPTS)
        # Refresh every seeded column on conflict; leave id/created_at intact.
        update_cols = {
            c: getattr(stmt.excluded, c)
            for c in (
                "code", "u_stage", "title", "is_core", "tier", "label", "axis",
                "watch_only", "rep_target", "content_slug", "drill_refs",
                "sort_order", "notes", "track", "stage_code", "stage_order",
                "cross_refs",
            )
        }
        stmt = stmt.on_conflict_do_update(index_elements=["slug"], set_=update_cols)
        await session.execute(stmt)
        await session.commit()

    await engine.dispose()
    by_track: dict[str, int] = {}
    for c in CONCEPTS:
        by_track[c["track"]] = by_track.get(c["track"], 0) + 1
    counts = ", ".join(f"{k}={v}" for k, v in sorted(by_track.items()))
    print(f"Seeded/updated {len(CONCEPTS)} concepts ({counts}).")


if __name__ == "__main__":
    asyncio.run(seed())
