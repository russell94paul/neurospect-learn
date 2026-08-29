# S1d — honest accuracy statement (engine `S1d.1`)

What the engine now finds, what it still misses, and where it defers to Paul. Written
after the run, against the run's actual output — not against what it was intended to do.

**Supersedes `../s1c/accuracy.md` as the current statement.** That file stays as the
frozen record of the S1c run and should not be edited to match this one.

> ## ⚠️ QUARANTINE
> Everything under `api/docs/evidence/s1d/` is **machine-generated**. Not practice, not
> reps, not evidence. It must never touch `evidence_assets`, rep credit, the streak, the
> calibration score or the Readiness Gate. A tutorial artifact is not a training record.

---

## The sample, stated

| | |
|---|---|
| Source | Tradezella backtesting session `831607` (`NQ` `ES` `YM` `CHFUSD`, Aura playbook) |
| Resolutions | `W` (native), `D`, `240`, `60`, `15`, `5`, `1` |
| Declared span | **2025-05-26 → 2025-05-30 (ET)**, 5 weekdays, NY session 08:00–16:00 ET |
| Selection | ⛔ **SELECTED, not sampled** — chosen *because* it contains the one known setup |
| Result | **1 setup · 4 stand-asides** |

**The selection basis is now a required-in-practice CLI input** (`--selection-basis`).
Omitting it prints a visible warning at the top of the report instead of quietly
producing a span whose provenance the reader cannot see.

---

## ✅ What S1c deferred and S1d implemented

| Gap | How it was closed |
|---|---|
| **Bounded markup primitives** | Rectangles / rays / bounded segments with computed start **and** end. `horizontal_line` is not emitted at all, and `shape()` asserts the tool is a bounded one. |
| **Weekly cycle (R18/R27)** | Exported **natively** from the chart (436 NQ weekly bars back to 2017). Nothing aggregated from daily bars — a synthesised week is not a week the market traded. |
| **NWOG / NDOG (R11)** | Implemented against a **measured** per-symbol session boundary. |
| **R21 cross-cycle gap-pairing** | Weekly→daily, daily→4H, 4H→15m, 15m→5m. Reported as supporting confirmation; its absence is reportable, not disqualifying (R20 lists other routes). |
| **R22 extreme-of-larger-segment** | Computed and reported **alongside** R35's range extreme, never substituted. Detects and states the case where the two are the same price. |
| **R13 look-left / zoom-in** | Both routes computed — zoom in to 1m inside the gap, then look left for a **resting untaken** level. Which route supplied the answer is recorded. |
| **Outcome simulation** | Walks 1m (falling back to 5m) for stop-first / target-first with the bar it happened on. |
| **FVG size floor** | New in S1d — S1c had **none** (see below). |

---

## ⚠️ What it still does NOT do — and will not pretend to

- **R8's false-sweep tiebreak is measured but NOT resolved.** The engine reports, for each
  range anchor, whether that extreme was swept on every triad leg, and names a materially
  different all-legs-swept alternative when one exists. It never re-anchors.
  **There is a genuine contradiction in the rulebook here and it must not be papered
  over:** rule 8's first sentence says anchor extremes only on **SMT-qualified** swings
  (which by definition diverge), while its second says prefer the extreme swept on **all**
  triad assets (which by definition does not). No single swing satisfies both. Resolving
  that is a judgement for Paul, not arithmetic.
- **R9 (range ambiguity)** is never resolved. Two candidates within 15% emit `UNRESOLVED`
  with both. When the largest candidate is dead but a smaller one is alive, the engine says
  so and **refuses to switch to the one that yields a trade**.
- **R31 (pre-09:30)** is a reported branch, never a gate. The entry window opens at 08:00
  specifically so the branch stays visible — and note a strict 09:30 filter would delete
  the one entry in this week.
- **R23 cannot be reproduced in Tradezella at all** — the backtest chart takes no custom
  indicators, so every SMT read there is a hand read.
- **Weekly confirmation is NOT a gate** (`WEEKLY_IS_A_GATE = False`). R18 is satisfied by
  any two adjacent cycles, so daily→4H remains legitimate. Whether weekly should become a
  gate is a **calibration question only Paul's review can answer**, and the engine declines
  to answer it for him.
- **1m bars are never scanned for signals** (`FINE_RES_IS_SIGNAL_CYCLE = False`). R28 makes
  a 1-minute microcycle divergence explicitly low-influence, so using 1m as a signal cycle
  would contradict the rulebook. It is used for outcome sequencing and R13 zoom-in only.
- **R22's "between two segments" condition is not verified.** The engine locates the
  larger-cycle bar *containing* the SMT; "segment" is not defined precisely enough in the
  rulebook to test. The level is R22-**shaped**, not R22-**proven**, and the report says so.
- **Monthly cycle** is still absent. Weekly is now the deepest rung.

---

## ⛔ The limitation that matters most: outcomes cannot be realised here

**The replay is parked at 2025-05-30 16:59 ET**, confirmed at 1-minute resolution on all
three futures legs. There is no later bar on this chart. Advancing the replay would consume
days Paul intends to replay himself, and this phase forbids it.

Consequence: **the one entry in the declared week has no realised R.** It ran 1.20R in
favour and 0.41R against, then the bars ran out — verdict `UNRESOLVED-AT-DATA-EDGE`.

The engine distinguishes four outcome verdicts and will not collapse them:

| Verdict | Meaning |
|---|---|
| `TARGET` / `STOP` | resolved, with the bar it happened on and a realised R |
| `UNRESOLVED-AT-RESOLUTION` | one bar's range spans **both** stop and target — sequence genuinely unknowable. Retried at a finer resolution first; never guessed. |
| `UNRESOLVED-AT-DATA-EDGE` | ran out of bars. **Not** a breakeven, **not** a loss, and must not enter a win rate. |

**Any future expectancy work needs bars past the replay edge**, which needs either a new
session or Paul's own replay — a decision for him, not the engine.

---

## Declared thresholds that are choices, not facts

Each is printed in the run header. An unstated threshold is an invented rule wearing a
fact's clothes.

| Constant | Value | Sensitivity |
|---|---|---|
| `NOISE_FLOOR_TICKS` | 2.0, both sides | Without it, zero-margin near-misses manufacture phantom SMT |
| `FORWARD_BARS` | W→3, D→5, 4H→6, 60m/15m/5m→8, 1m→10 | **A different window changes which pivots qualify.** The weekly 3 means a weekly signal is not knowable for ~a month — conservative by construction |
| `FRAMING_LOOKBACK_BARS` | 60 daily bars | Weekly SMT is searched over 12 weeks — and the nearest prior weekly SMT (2025-01-20) falls **~14 weeks out, just outside it** |
| `FVG_MIN_TICKS` | **4.0 — new in S1d** | See below |
| `OPENING_GAP_MIN_TICKS` | 2.0 | Below this, every session break emits a "gap" of float noise |
| `R9_AMBIGUITY_TOLERANCE` | 15% | Inside this the engine refuses to pick a range |
| `R8_MATERIAL_GAP_FRACTION` | 10% of range | What counts as "a large gap between candidates" |
| `STOP_OVERSIZE_FRACTION` | 25% of range | Flag only. The one entry is at 27% |
| `ENTRY_WINDOW_ET` | 08:00–16:00 | Opens before 09:30 deliberately so R31's branch stays visible. **It also hid an earlier retest of the entry gap** — see below |

### ⭐ The FVG size floor did not exist before S1d

S1c detected FVGs with **no minimum size**, so a **one-tick** gap (NQ `21,348.75–21,349.00`)
was an entry candidate on equal footing with a six-tick one. Two problems, the second
being the serious one:

1. Drawing them produced 27 rectangles on a single session — the "wall of lines" Paul
   rejected, where the ink hides the structure.
2. It is the **same defect class as the phantom-SMT bug**: a measurement at the resolution
   of the instrument's own granularity, treated as a real feature of the market.

R11 names no minimum, so 4 ticks is a **declared choice**. Exclusions are **counted and
reported per day**, never silently dropped. **Verified not to change S1c's result** —
identical verdicts on all 22 days and the same entry gap, which is 6 ticks wide.

---

## Measured, not assumed

### Session boundaries (what R11 needs)

| Symbol | Daily close→open (ET) | Support | Weekly close→open (ET) |
|---|---|---:|---|
| NQ | 16:55 → 18:00 | 83% | 16:55 → 18:00 |
| ES | 16:55 → 18:00 | 88% | 16:55 → 18:00 |
| YM | 16:55 → 18:00 | 83% | 16:55 → 18:00 |
| **CHFUSD** | **NOT-MEASURABLE** | — | 16:55 → 17:00 |

`NOT-MEASURABLE` is a **result**, not a hole. Forex trades near-continuously, so CHFUSD has
no daily opening gap and therefore gets **no NDOGs** rather than invented ones. This
vindicates S1c's refusal to implement R11 without the measurement.

⚠️ **My first version of this measurement was wrong in a way that looked right.** It
excluded only gaps longer than three days, so CHFUSD's **Friday→Sunday weekend** break was
classified as its **daily** boundary, at 75% "support" over 3 observations. Every CHFUSD
NDOG would have been placed at the wrong boundary. Daily and weekly breaks are now
separated by **calendar days skipped**, not by gap length.

### Instruments proved live

- **Weekly SMT detector: 13 events** across full history (6 high / 7 low). So the 12-week
  lookback returning 0 for this week is a genuine `ZERO`, not a blind instrument.
- **Weekly alignment:** NQ/ES/YM share **every** weekly timestamp; CHFUSD shares **none**.
- **Tick sizes** recover the contract specs unaided: NQ 0.25 · ES 0.25 · YM 1.0.
- **Outcome walker cross-check:** 1m and 5m walks give **identical** MFE/MAE
  (1.1971R / 0.4064R), as they must if 5m aggregates 1m.

---

## Known weaknesses — read before trusting a number

1. **n = 1, and the week was selected.** No hit rate, win rate or expectancy exists. Do not
   quote a percentage.
2. **The one entry has no realised outcome.** See above.
3. **CHFUSD's tick is not reliably measurable** — `1e-06` intraday vs `5.2e-06` daily vs a
   conventional `1e-05`; its measured tick varying *by resolution* is the tell. Its noise
   floor is the softest of the four, and **the one entry's Sequential Skip diverges on
   CHFUSD alone.** The weakest link in the chain, flagged on the record's face.
4. **⚠️ The entry window can hide an earlier retest.** On 05-30 the traded iFVG had already
   been re-entered at **20:40 the previous evening**, outside 08:00–16:00, so the 08:05
   touch is a **later** one. R30 does not say whether a re-tested iFVG is still a valid
   entry. Now reported as a branch; previously invisible.
5. **The daily bar closes intraday**, so `known_at` adds a full bar duration to be safe.
   Conservative; may retire a signal later than a live trader would.
6. **Four of five stand-asides are one finding restated** — the same range, dead since
   2025-05-12. The week is thinner in independent lessons than "4 stand-asides" suggests.
7. **The engine does not draw shapes; a separate pass does**, and that pass has its own
   failure mode — the chart **silently clamps coordinates to the loaded data window**. See
   `chart-shapes-drawn.md`. Shape geometry must be verified by comparing requested against
   read-back coordinates, per shape. Counting shapes proves nothing.

---

## Regression evidence

Re-running **S1c's original span** (2025-05-01 → 05-30) with the hardened engine:

- **all 22 day-verdicts identical** (kind + failing rule);
- same setup, same day, same bias, **same entry gap**;
- every difference is an **addition** (weekly rung, NDOG, R21, R22, R8, outcome, R13
  source tag), never a changed value.

`aura_verify_record.py` — which imports nothing from the engine and re-derives the record
straight from the JSON — still passes **all 12 checks**, including the no-lookahead
assertion (`known_at` 2025-05-29 09:30 ≤ session open 05-30; naive calendar arithmetic
still dates it 05-25, four days early).

---

## What was touched, and what was not

- **Added:** `api/scripts/aura_bar_receiver.py`, `api/docs/evidence/s1d/`.
- **Modified:** `api/scripts/aura_setup_engine.py` (S1c's version is in git history; S1c's
  evidence folder is the frozen record of that run).
- **Not touched:** no migration, no new table, no endpoint, no app code, no backend module.
  The evidence layer is untouched. `app/` is unchanged.
- **Paul's Tradezella session:** resolutions stepped W → 1m → 60m → 5m for export and
  drawing, and **left on 5m** (R30's entry cycle) rather than the 1m it was found at — Paul
  confirmed in-session that changing timeframes is fine. **Replay position untouched** at
  2025-05-30 20:59 UTC. No orders, no playbook edits. **33 `[S1d]`-marked shapes left on
  the NQ pane for review, with a tested removal snippet** — they must be removed before the
  week is marked by hand.
