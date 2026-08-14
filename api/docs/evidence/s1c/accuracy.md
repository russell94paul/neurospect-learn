# S1c — honest accuracy statement

What the engine finds, what it misses, and where it defers to Paul. Written after the
run, against the run's actual output — not against what the engine was intended to do.

> ## ⚠️ QUARANTINE
> Everything under `api/docs/evidence/s1c/` is **machine-generated**. It is not
> practice, not reps, not evidence. It must never touch `evidence_assets`, rep
> credit, the streak, the calibration score or the Readiness Gate. A tutorial
> artifact is not a training record.

---

## The sample, stated

| | |
|---|---|
| Source | Tradezella backtesting session `831607` (`NQ` `ES` `YM` `CHFUSD`, Aura playbook) |
| Extraction | `tradingViewApi.chart(i).exportData({includeTimeValues:true})` on the live chart |
| Resolutions | `D`, `240`, `60`, `15`, `5` — all four symbols at each |
| Declared span | **2025-05-01 → 2025-05-30 (ET)**, 22 weekdays |
| Result | **1 setup · 21 rejections** |

**Why this span and not the session's own 2025-06-01 → 06-30.** The replay is parked
at 2025-05-30 20:59 UTC and has not been advanced. Advancing it would consume days
Paul intends to replay himself, so the engine was pointed at the real history sitting
*behind* the replay edge instead. **No session state was changed.**

**The span deliberately overruns the 5m data.** 5m bars begin 2025-05-04 22:00 UTC, so
2025-05-01 and 05-02 come back as `DATA` rejections rather than silently vanishing.
The boundary is visible in the output instead of being tidied away.

---

## The positive control passed

`NQ`/`ES`/`YM` share **every** daily timestamp (all stamp 13:30 UTC); `CHFUSD` shares
**none** (21:00 UTC). This independently reproduces the alignment measurement recorded
in the tracker on 2026-08-13, from a fresh export. Had the futures legs disagreed, the
measurement would have been broken — not the market.

Measured tick sizes recovered the contract specs exactly without being told them:
**NQ 0.25 · ES 0.25 · YM 1.0**. That is the check that says `measure_tick` works.

---

## ⭐ Five defects were found and fixed, and each one changed the numbers

The audit trail is what caught them. A less auditable engine would have shipped all
five, and every one produces output that *looks* like analysis.

| # | Defect | Effect | How it surfaced |
|---|---|---|---|
| 1 | **R6 never implemented** — a range was used long after price closed through it | Entries scored at `1.22 of range`; a five-week-old 3,584-pt "range" | Reading the rendered log |
| 2 | **`abs()` in the reward calc** hid a sign error | A target the trade had already passed rendered as `0.7R` | Reading the rendered log |
| 3 | **One stale daily SMT drove every day** (R7/R23) | Same 05-02 signal reused for a week | Reading the rendered log |
| 4 | **⭐ Lookahead** — `known_at` computed as `pivot + N days` | Ignored weekends/holidays; dated a signal **4 days early** and traded it on the session that produced it | The independent audit |
| 5 | **⭐ Tick measured as float noise** on CHFUSD (`5.98e-09`) | That leg's noise floor collapsed to ~zero — reintroducing the phantom-SMT bug on the one leg too small to eyeball | Reading the tick column |

**Setup count across the fixes: 17 → 4 → 1.**

Defect 4 alone removed **three of four** surviving setups. That is the headline number
of this phase: before the lookahead fix, **75% of the setups were contaminated** by
information that did not exist when the engine claimed to act on it. Any accuracy
statistic computed before that fix would have been fiction, and it would have looked
entirely reasonable.

Defects 1–3 were caught by reading the output like a trader rather than checking that
the code ran. Defects 4–5 needed an instrument: an independent re-derivation, and a
column that printed a measured value instead of an assumed one.

---

## Verification

`api/scripts/aura_verify_record.py` re-derives the surviving record straight from the
exported JSON, importing **nothing** from the engine, and asserts each engine claim.
Twelve checks, all passing: pivot validity, level, primary margin, both leg verdicts
and margins, bar-derived `known_at`, the no-lookahead relation, stop arithmetic, and
signed R:R. It exits non-zero on disagreement, so it is a gate and not a printout.

---

## What the engine genuinely computes

R1/R2 pivots · R3/R18/R20 SMT qualification with a two-sided noise floor and a
reported margin on every leg · R4/R7 range by expansive move, anchored on the driving
SMT · R6 range invalidation by close · R5/R32 discount/EQ/premium position ·
R11 FVG/iFVG detection · R12/R13 liquidity nested inside a gap · R24 Sequential Skip ·
R27 the cascade · R29/R33 stop at the qualifying SMT's swept extreme · R35 target at
the range extreme, sign-checked · R39/R43/R44 risk and R:R.

## What it does NOT do — and will not pretend to

- **R9 (range ambiguity)** is never resolved. Two candidates within 15% emit
  `UNRESOLVED` with both. When the largest candidate is dead but a smaller one is
  alive, the engine says so and **refuses to switch to the one that yields a trade**.
- **R8's false-sweep tiebreak** is not implemented at all.
- **R31 (pre-09:30)** is reported as a branch, never as a gate. The entry window opens
  at 08:00 ET specifically so the branch stays visible rather than defined away.
- **NWOG / NDOG** are declared in R11 but **not implemented** — only FVG and iFVG are.
  Session/week opening gaps need a session-boundary definition per symbol, and CHFUSD's
  boundaries do not match the futures'. Stated rather than approximated.
- **R21 cross-cycle gap-pairing** is not implemented as a distinct confirmation.
- **R22** (extreme-of-the-larger-segment targeting) is not implemented; R35's range
  extreme is used instead.
- **Weekly and monthly cycles** are absent. The export's deepest usable cycle is daily,
  so R27's Monthly→Weekly rungs are simply not present. Nothing was aggregated to fake
  them.

## Known weaknesses — read these before trusting a number

1. **CHFUSD's tick is not reliably measurable.** It came back `1e-06` intraday and
   `5.2e-06` daily; a real CHF quote is conventionally `1e-05`. Its measured tick
   varying *by resolution* is itself the tell. Its noise floor is therefore the
   softest of the four, and the one surviving setup's Sequential Skip **diverges on
   CHFUSD alone**. The record carries that warning on its face.
2. **n = 1.** One setup over 22 days supports **no** hit-rate, expectancy or win-rate
   claim whatsoever. This run demonstrates that the rules can be computed; it measures
   nothing about whether they are profitable. Do not quote a percentage from it.
3. **No outcome simulation.** The engine does not walk price forward to see whether
   the stop or the target was hit first. Every `R` figure is *planned*, not realised.
4. **The forward windows are chosen, not derived.** 5 daily / 6×4H / 8×15m / 8×5m bars
   are declared constants. A different window changes which pivots qualify — this is
   exactly the sensitivity that produced the corrected MNQ finding on 2026-08-13.
5. **The daily bar closes intraday.** A daily bar stamped 09:30 ET is not final until
   its session ends; `known_at` adds a full bar duration to be safe. This is
   conservative and may retire a signal later than a live trader would.

---

## Deliverable 3 (drawing computed levels on the chart) — NOT DONE

`createShape` / `createMultipointShape` are available and the mechanism is proven, but
drawing writes shapes into **Paul's live session `831607`**, which he would then have
to clean up. The boot prompt marks this optional. Left undone pending his say-so rather
than mutating his practice environment unasked.

## What was touched, and what was not

- **Added:** `api/scripts/aura_setup_engine.py`, `api/scripts/aura_verify_record.py`,
  and this evidence folder.
- **Not touched:** no migration, no new table, no endpoint, no app code, no backend
  module. The evidence layer is untouched and the backend suite was not re-run because
  nothing it covers changed.
- **Paul's Tradezella session:** chart resolution was stepped D→240→60→15→5 to export
  each cycle and **restored to `1m`**. No drawings created, no orders, no replay
  advance, no playbook edits.
