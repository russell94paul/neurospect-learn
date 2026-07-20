"""Idempotent seed for the `concepts` table.

Source of truth: concepts/mastery/unified/learning-path.md + tracker.md (the
U0–U6 taxonomy). Seeds `concepts` ONLY — `concept_progress` rows are created
per-user at runtime in later phases.

Run:  poetry run python -m scripts.seed_concepts     (from api/)

Idempotent: UPSERT on `slug` (ON CONFLICT DO UPDATE). Re-running refreshes the
seeded columns without creating duplicates.

Notes on the data:
- `is_core` follows the tracker's explicit **core** annotations (U1.1–U1.5,
  U2.2–U2.4, U3.1a, U3.1c). NOT invented — traceable to tracker.md.
- `watch_only` is true for every frontier (U5) row (study-and-watch only; never
  gate-eligible). The DB also enforces `u_stage <> 'U5' OR NOT is_core`.
- `content_slug` values are PROVISIONAL soft refs (the wiki page basename). The
  5d ingest owns the real `content_pages` slug scheme; reconcile then. Nullable
  by design — no hard FK.
- U6 has no discrete gradable concept rows (backtest/live/journal by reference);
  the journal itself is the U6 artifact.
"""

import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import AsyncSessionLocal, engine
from app.models.concept import Concept

# fmt: off
# Each tuple: (slug, code, u_stage, title, is_core, tier, label, axis,
#              watch_only, rep_target, content_slug, drill_refs, notes)
CONCEPTS: list[dict] = []


def _c(slug, code, u_stage, title, is_core=False, tier=None, label=None, axis=None,
       watch_only=False, rep_target=None, content_slug=None, drill_refs=None, notes=None):
    CONCEPTS.append(dict(
        slug=slug, code=code, u_stage=u_stage, title=title, is_core=is_core,
        tier=tier, label=label, axis=axis, watch_only=watch_only,
        rep_target=rep_target, content_slug=content_slug,
        drill_refs=drill_refs or [], notes=notes, sort_order=len(CONCEPTS),
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
# fmt: on


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(Concept).values(CONCEPTS)
        # Refresh every seeded column on conflict; leave id/created_at intact.
        update_cols = {
            c: getattr(stmt.excluded, c)
            for c in (
                "code", "u_stage", "title", "is_core", "tier", "label", "axis",
                "watch_only", "rep_target", "content_slug", "drill_refs",
                "sort_order", "notes",
            )
        }
        stmt = stmt.on_conflict_do_update(index_elements=["slug"], set_=update_cols)
        await session.execute(stmt)
        await session.commit()

    await engine.dispose()
    print(f"Seeded/updated {len(CONCEPTS)} concepts.")


if __name__ == "__main__":
    asyncio.run(seed())
