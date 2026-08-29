# S1e — configuration sweep, PRE-REGISTERED

**Written 2026-08-14, BEFORE the sweep was run.** Paul, 2026-08-14: *"To all 4 yes. We need to
exhaust all configurations then review."*

This file fixes the grid, the metrics and the reporting rule in advance so the sweep cannot be
reshaped around its own results. Anything not listed here was not planned.

---

## Why a sweep rather than a fix

The S1e audit found the engine violated every Aura preference (R17 100%, R18 91%, R30 90%,
R30/R32 56%, R45 38%) and that enforcing them collapsed the sample to **zero**. Each violation
traces to a **coded assumption presented as a fact**. We do not know which assumptions are right,
so we vary them all and report the whole surface.

## ⛔ The reporting rule, fixed in advance

1. **Every cell is published.** No cell is omitted for being uninteresting or embarrassing.
2. **No cell is adopted because it has the best expectancy.** With ~32 independent episodes,
   sweeping 384 result cells will produce a flattering winner **by chance alone**. Treat the best
   cell as noise until it is validated out-of-sample.
3. **The primary output is a SENSITIVITY map** — which assumptions move the result and by how
   much — not a ranking.
4. **Sample size travels with every ratio**, and cells below **n = 20 entries** are reported as
   `UNDERPOWERED` and excluded from any comparison of expectancy.
5. **Both counting bases** (entry-day and episode) are reported for every cell.
6. The **declared span is unchanged**: `2023-01-03 → 2025-04-30`. It is not re-declared,
   re-chosen, or trimmed for any cell.

## ⚠️ AMENDMENT 1 — 2026-08-15, after run 1, before run 2

**An axis was added after the first sweep had been run. This is recorded because amending a
pre-registration mid-experiment is exactly the move that needs to be visible.**

**What happened:** run 1's Aura-Asset axis was **inert**. Setting `aura_asset_all_cycles=true`
removed the refusal note and changed **not one trade** — identical entries, episodes and
expectancy in all 24 affected cells.

**Why:** measured — **CHFUSD shares 0 of NQ's 3,794 daily timestamps** (ES 3,794/3,794, YM
3,792/3,794). The Aura Asset's daily bars sit on a different session boundary, so the exact
timestamp join can never match and the leg reads `NOT-VISIBLE` even once admitted. **Admission was
necessary but not sufficient.**

**The amendment:** a second Aura-Asset axis, `aura_asset_join ∈ {timestamp, session_date}`, where
`session_date` joins on the ET session bucket each bar belongs to — R17's *"read it exactly like a
normal divergence leg"*. Verified in a half-year probe: the leg went from `NOT-VISIBLE` on 100% of
setups to `TOOK 4 · DID-NOT-TAKE 44 · WITHIN-NOISE 1`.

**This amendment adds a capability, it does not change any target.** The span, the metrics, the
`n < 20` underpowered rule and the reporting rule are all unchanged, and no cell from run 1 is
withdrawn. **Run 1's conclusion stands: question 1 was never tested**, and run 2 is what tests it.

`off × session_date` is skipped — with the leg unadmitted at D/W the join is a no-op, so those
cells would duplicate `off × timestamp`.

---

## The grid — 4 detector axes, 48 engine runs (RUN 1) → 72 runs (RUN 2, amended)

Each axis is one of the four questions Paul answered "yes" to. Defaults (marked ▸) reproduce the
pre-S1e behaviour exactly; that was verified by re-running S1c's window with **0 differences**.

| Axis | Rule | Values | n |
|---|---|---|---:|
| Aura Asset admitted at all cycles | R17 | ▸`false`, `true` | 2 |
| Weekly-cycle SMT lookback (weeks) | R18 | ▸`12`, `16`, `20`, `26` | 4 |
| Retest handling | R30 | ▸`report`, `require_first`, `session_first` | 3 |
| Discount/premium reference range | R30/R32 | ▸`htf`, `ltf` | 2 |

**2 × 4 × 3 × 2 = 48 engine runs.**

## The enforcement layer — applied post-hoc, 8 per cell

Enforcement only ever *removes* entries from a run's output and every input it needs is recorded
per record, so it is applied in analysis rather than by re-running the engine. This is exact, not
an approximation.

| Filter | Rule | Values |
|---|---|---|
| Gate on discount/premium | R30/R32 | off, on |
| Minimum planned reward:risk | R45 | `0`, `1.0` |
| Require canonical weekly nesting | R18 | off, on |

**48 × 8 = 384 result cells.**

## Metrics recorded for every cell

`entries` · `episodes` · `win%` · `avg win R` · `avg loss R` · `expectancy` · `total R` ·
`median R` · `total R excluding the single best trade` · `rejection census by rule` ·
`% violating each preference`.

**`total R excluding the best trade` is recorded for every cell deliberately**: the baseline run
was +4.84R total and **−7.57R without its single best trade**. Any cell whose result depends on
one trade must show it.

## What would make a cell interesting (stated before seeing any)

- It **raises n** while keeping expectancy — i.e. the assumption was suppressing valid setups.
- It **survives the drop-the-best-trade test**.
- It is **stable across neighbouring cells** — a lone spike surrounded by poor neighbours is
  noise, not a discovery.
- It **reduces the violation rates** that the audit found, since those measure whether the engine
  is trading the model at all.

## What this sweep cannot do

- It cannot validate an edge. 32 episodes is too few, and the sweep spends that sample many times.
- It cannot settle what the rules *mean*. Only the videos and Paul can do that; the sweep shows
  what each reading would have produced.
- It does not touch `QUARANTINE`: no result here reaches `evidence_assets`, rep credit, the
  streak, calibration or the Readiness Gate.
