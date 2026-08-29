# S1e — the declared span and counting basis

**Written 2026-08-14, BEFORE any entry was computed and BEFORE any outcome was simulated.**
This file exists so the span cannot be quietly adjusted once results are visible.

---

## The span

**`2023-01-03` → `2025-04-30`** (inclusive), NY session, NQ triad + CHFUSD.

Chosen by Paul from three options with the measured history bound in front of him.

- **~600 weekdays.**
- Ends **~1 month before the data edge** (last futures bar `2025-05-30 20:55 UTC`) so entries near
  the end of the span still have forward bars to resolve against.
- **Not extended, not trimmed, not cherry-picked after seeing results.** If the tally is ugly, the
  tally is ugly.

## Why this span was available at all — STEP 0, measured 2026-08-14

5m history, probed by forcing `setVisibleRange` progressively earlier until the request stopped
being honoured. It never stopped being honoured; probing was stopped at 2023-01.

| Leg | 5m bars | Earliest 5m bar |
|---|---|---|
| NQ | 170,711 | 2023-01-02 |
| ES | 170,712 | 2023-01-02 |
| YM | 170,709 | 2023-01-02 |
| CHFUSD | 177,074 | 2023-01-01 |

CHFUSD daily reaches **2010-10-11** (3,804 bars).

⚠️ **CHFUSD 5m first read returned 678 bars covering 4 days.** That was **lazy loading, not a
limit** — after repeated `setVisibleRange` nudges the same query returned 177,074 bars. A single
read after a fixed wait would have published a false "CHFUSD has no intraday history" finding and
wrongly bounded this phase. **Instrument artefact, not a measurement.**

**This retires the boot prompt's central worry.** It estimated ~10–11 months of intraday history
would be needed and made that bound the gate on the phase. ~2.4 years are available — ~2.9× the
requirement. **History is not the binding constraint.**

## The counting basis — declared before any number is produced

- **One unit = one entry the engine took**, inside the declared span.
- **Every entry in the span is reported.** No dropping, no early stopping.
- **Outcome verdicts stay four-way:** `TARGET` / `STOP` / `UNRESOLVED-AT-RESOLUTION` /
  `UNRESOLVED-AT-DATA-EDGE`. Unresolved trades are reported separately and **never folded into a
  win rate**. An unresolved trade is a measurement gap, not a breakeven.
- **Ratios never travel alone.** `win%`, `avg win R`, `avg loss R` and
  `expectancy = (win% × avg win R) − (loss% × avg loss R)` publish together or not at all.
- **Every ratio carries its sample size.**
- **The rejection census ships beside the tally.** R6 rejected 13/21 days in S1c and 4/5 in S1d;
  a win rate drawn from survivors of an unvalidated filter is a number about the filter.

### ⛔ The clustering problem — both counts get published

The gate census measured that entry-stage days are **not independent**: 28 entry-stage days over
107 weekdays collapsed to **7 driving episodes** from **5 SMT pivots**, with 17 of 28 hanging off a
single pivot (2024-12-11) and 26 of 28 SHORT.

So the artifact reports **both**:

- **entry-day basis** — the raw count of entries, and
- **episode basis** — entries grouped by driving SMT pivot + range.

and **states which basis every ratio uses**. Quoting a win rate over correlated entry-days as if
they were independent samples would overstate the sample size ~4× — the FU92-420 failure exactly.

## What is NOT predicted

The step from *entry-stage day* to an actual **R30 entry** has been measured on **two days**
(S1c: 2 entry-stage days → 1 setup). That is `n = 2`. **No entry count is forecast from it.**
Estimates below are for entry-*stage* days only, which the census measured directly:

| Quantity | Value | Basis |
|---|---|---|
| Weekdays in span | ~600 | DERIVED |
| Entry-stage days | ~157 | DERIVED from a MEASURED 26.2% rate |
| Driving episodes | ~39 | DERIVED from a MEASURED 7-per-107-weekdays rate |
| **Entries** | **UNKNOWN** | to be **counted**, never extrapolated |

## Standing constraints

- **Do not advance Paul's replay** (session clock: Sun 2025-06-01 17:00 ET).
- `QUARANTINE` holds — machine trades never touch `evidence_assets`, rep credit, the streak,
  calibration or the Readiness Gate.
- Judgement rules (R8, R9, R31) stay UNRESOLVED or render as soft branches; they are never
  silently resolved.
- **No edge is claimed.** N machine trades on one instrument is not a validated edge, and S1c/S1d
  found eleven defects that each produced confident-looking output. Assume a twelfth.
