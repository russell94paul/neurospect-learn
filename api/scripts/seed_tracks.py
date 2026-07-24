"""Idempotent seed for the `track_stages` table (Phase 5e-1b).

Source of truth (READ-ONLY wiki pages — consumed/linked, never restated):
  - unified U0–U6   concepts/mastery/unified/learning-path.md
  - aura    A0–A6   concepts/mastery/aura/learning-path.md
  - ict_course M0–M8 concepts/course/README.md + mastery/ict-course/exercises.md

`track_stages` is per-track stage metadata — the title/summary/gate_text the
`/path/:track/:stage` curriculum unit renders. The stage's concepts and drills
are resolved by grouping on `concepts.(track, stage_code)` — NOT stored here.
`gate_text` is the descriptive exit bar from the learning-path page (the
objective, computed gate lives in app/services/stages.py).

Run:  poetry run python -m scripts.seed_tracks          (from api/)

Idempotent: UPSERT on (track, stage_code); prunes rows no longer produced.
"""

import asyncio
from collections import defaultdict

from sqlalchemy import delete, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import AsyncSessionLocal, engine
from app.models.track_stage import TrackStage

STAGES: list[dict] = []


def _s(track, order, code, title, summary, gate_text):
    STAGES.append(dict(
        track=track, stage_order=order, stage_code=code,
        title=title, summary=summary, gate_text=gate_text,
    ))


# --- unified (U0–U6) ------------------------------------------------------
_s("unified", 0, "U0", "Psychology & discipline",
   "Foundation — build the discipline layer first and keep it running under every later stage.",
   "Pre-market routine + written circuit-breakers actually followed for one week; journal live, logging every trade incl. misses.")
_s("unified", 1, "U1", "Structural primitives",
   "The eye-training core — read the chart by hand (liquidity, ranges, swing, gaps, delivery narrative).",
   "All five primitives at Can-mark, reps ≥ target, conf ≥3, markable by hand on an unlabelled chart.")
_s("unified", 2, "U2", "Nested SMT stack",
   "SMT used twice, at two altitudes — the reconciliation's key synthesis (R1).",
   "Sequential SMT + triad SMT at Can-mark, conf ≥3; build the nested stack read by hand before the indicator.")
_s("unified", 3, "U3", "Execution",
   "Time → entry → levels: execute with the entry-model library once U1–U2 align (R4).",
   "Run a full framing → entry → stop → target plan end-to-end; entry models at Can-mark → Backtested.")
_s("unified", 4, "U4", "Risk",
   "The R-multiple blueprint (R5) — 1–2% per trade, 2–3R daily stop, 10R circuit-breaker.",
   "Compute a trade's expectancy in R; risk rules precommitted in writing; no sizing up in a drawdown.")
_s("unified", 5, "U5", "Frontier confluence-stacking",
   "Extra independent filters on a setup you can already read — deliberately last. Study-and-watch only.",
   "Frontier concepts reach Learned → Can-mark (observation only); never live-gate-eligible.")
_s("unified", 6, "U6", "Readiness arc",
   "Backtest → live → journal (by reference; backtesting is a separate workstream).",
   "Run the full Readiness-to-Live Gate (Phase 5g).")

# --- aura (A0–A6) ---------------------------------------------------------
_s("aura", 0, "A0", "Foundation: psychology & discipline",
   "The mentorship spends its first five sessions here before any chart concept. So do you.",
   "Pre-market 3-question routine + circuit breakers written and actually followed for one week; journal live.")
_s("aura", 1, "A1", "The three structural primitives",
   "The heart of the eye-training — swing points → ranges → gaps, by hand.",
   "Each primitive at Can-mark, reps ≥50 each, confidence ≥3; mark all three by hand on an unlabelled chart.")
_s("aura", 2, "A2", "The confirmation engine",
   "Where the model becomes a decision system — triads, Aura Asset, Sequential SMT & Skip.",
   "Sequential SMT + Skip at Can-mark, confidence ≥3; state a swing's SMT-qualification before the indicator.")
_s("aura", 3, "A3", "Putting it together: the cascade & risk",
   "The HTF→LTF cascade, Time Sum (awareness only), and R / expectancy / break-even math.",
   "Run a full framing → entry → stop → target plan end to end; compute the trade's expectancy contribution in R.")
_s("aura", 4, "A4", "Backtest in bar-replay",
   "Transition from 'can mark' to 'has an edge on evidence' — worked-review replay + blind forward-replay.",
   "≥50 setups (ideally ≥100 executed trades) logged with positive expectancy in R; every core concept at Backtested.")
_s("aura", 5, "A5", "Live tape reading",
   "Reading price as it forms, real-time, no capital — the skill replay can't fully teach.",
   "A demo/sim track record showing the plan + circuit-breaker discipline hold under live pressure; core concepts at Live-ready.")
_s("aura", 6, "A6", "Journal-driven refinement",
   "Runs alongside Stages 4–5 and never stops.",
   "Journaling habit established (every trade incl. missed); at least one concrete rule change made from your own logged data.")

# --- ict_course / AXL (M0–M8) --------------------------------------------
_s("ict_course", 0, "M0", "Discipline & journal setup",
   "The ICT track's discipline canon — loss limits, set-and-forget, self-audit, bad-conditions recognition.",
   "Loss-limit precommitment written & honoured; set-and-forget contract; three-requirements self-audit; bad-conditions log.")
_s("ict_course", 1, "M1", "Module 1 — Foundations",
   "Liquidity = where price goes; inefficiency = where price enters. Unlocks everything else.",
   "Clear the Module-1 Readiness Check (7 boxes); liquidity/swings + FVG at Can-mark.")
_s("ict_course", 2, "M2", "Module 2 — Price delivery",
   "The four stages that structure every price run; the consolidation / E&R / reversal models.",
   "Four-stages read + consolidation + expansion-retracement + reversals at Can-mark.")
_s("ict_course", 3, "M3", "Module 3 — Session context & bias",
   "Adds time and session context — Power of Three, kill zones, deviations, daily bias.",
   "PO3 (10 days) + kill zones (1 wk) + deviations (10 days) + daily bias (10 days) at Can-mark.")
_s("ict_course", 4, "M4", "Module 4 — Market structure",
   "Multi-timeframe structure and the Model 2022 entry.",
   "Swing classification + fractality + structure deviations + Model 2022/OTE/CSD at Can-mark.")
_s("ict_course", 5, "M5", "Module 5 — Order flow & SMT",
   "The highest-timeframe filter (order flow) and the intermarket confluence tool (SMT).",
   "Order flow (1 wk) + SMT divergence (5 days) at Can-mark.")
_s("ict_course", 6, "M6", "Tape reading",
   "Study-then-replicate the candle-by-candle NQ/ES/YM reads from the stream + YouTube corpus.",
   "13 tape studies (T-01…13) + a blind live-read (T-14); whole-model read at Learned → Can-mark.")
_s("ict_course", 7, "M7", "Backtest in bar-replay",
   "Run each of the 7 entry models' canonical checklist blind in replay; log every trade in R.",
   "≥50 setups / ≥100 executed backtest trades across the 7 models with positive expectancy in R.")
_s("ict_course", 8, "M8", "Journal-driven refinement",
   "Weekly review, set-and-forget audit, missed/canceled log — continuous.",
   "Weekly review + set-and-forget audit + missed/canceled log habit established.")


async def seed() -> None:
    keys = [(s["track"], s["stage_code"]) for s in STAGES]
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(TrackStage).values(STAGES)
        update_cols = {
            c: getattr(stmt.excluded, c)
            for c in ("stage_order", "title", "summary", "gate_text")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["track", "stage_code"], set_=update_cols
        )
        await session.execute(stmt)
        # Authoritative: drop rows no longer produced.
        await session.execute(
            delete(TrackStage).where(
                tuple_(TrackStage.track, TrackStage.stage_code).notin_(keys)
            )
        )
        await session.commit()
    await engine.dispose()

    by_track: dict[str, int] = defaultdict(int)
    for s in STAGES:
        by_track[s["track"]] += 1
    counts = ", ".join(f"{k}={v}" for k, v in sorted(by_track.items()))
    print(f"Seeded/updated {len(STAGES)} track stages ({counts}).")


if __name__ == "__main__":
    asyncio.run(seed())
