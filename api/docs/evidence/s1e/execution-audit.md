# S1e — Aura execution audit: what the engine actually traded, rule by rule

**Date:** 2026-08-14 · **Span:** `2023-01-03 → 2025-04-30` (declared before any outcome was
computed — see `declared-span.md`) · **Engine:** `S1d.1`, unchanged during this run.

> Paul, 2026-08-14: *"I want to become an expert in executing it and understanding its nuances."*

This document exists to be **checked against the videos and the rulebook**, not believed. Every
claim is a count over the 128 entries the engine took, and every count is reproducible from
`computed-setups.json`.

---

## ⭐ The headline, stated plainly

**The strategy in `rules.md` has never actually been backtested.**

What was backtested is a **loose superset** of Aura in which every one of the model's quality
preferences is switched off. When the preferences are switched back on, **no trade in 2.4 years
satisfies all of them** — the sample goes to zero before the filters run out.

So the correct reading of "expectancy +0.038R" is **not** "Aura has no edge". It is
**"this measurement was never about Aura"**.

---

## The tally as run — the number, with its basis

| | Entry-day basis | Episode basis |
|---|---:|---:|
| n | **128** | **32** |
| Win rate | 40.6% | 34.4% |
| Avg win / avg loss | +1.56R / −1.00R | — |
| **Expectancy** | **+0.038R** | +0.151R / episode |
| Total | **+4.84R** | +4.84R |
| Median | **−1.00R** | −1.00R |

**Fragility:** remove the single best trade → **−7.57R**. Remove the top three → **−25.75R**.
Two episodes (+29.1R, +27.6R) carry the entire result. `n = 32` is the honest sample size;
`n = 128` overstates it ~4× because the engine re-enters the same live idea daily (once 25×).

**Rejection census (479 rejections):** R6 335 · R3 81 · R29 56 · R35 3 · R30 2 · DATA 2.
R6 alone rejects 55% of days, so all 128 entries are survivors of a filter nobody has validated.

---

## ⛔ How much of Aura was switched off

Each row is a preference the rulebook states and the engine **reports but does not gate**.

| Rule | What the rulebook asks for | Entries violating it |
|---|---|---:|
| **R17** | the **Aura Asset (6S)** as a 4th leg on *every* triad | **128 / 128 (100%)** |
| **R18** | Sequential SMT **nested across ≥2 adjacent cycles** (weekly-with-daily) | **116 / 128 (91%)** |
| **R30** | entry on the **iFVG retest** | **115 / 128 (90%)** — not the first retest |
| **R30/R32** | long in **discount**, short in **premium** | **72 / 128 (56%)** |
| **R34** | stop not oversized vs the range | 69 / 128 (54%) |
| **R31** | prefer waiting for the **09:30 NY open** | 67 / 128 (52%) |
| **R45** | maintain **at least 1:1** | 49 / 128 (38%) |

### R17 — the Aura Asset never participated, on any trade

Every record carries:

> `R17  CHFUSD REFUSED at D — cycles do not correspond (different exchange…)`

CHFUSD's daily cycle does not line up with the futures' session calendar, so the 4th leg is
**refused at the daily cycle on 100% of entries**. Rule 17 adds 6S to *every* triad and says it is
**most respected on indices**. Every confirmation in this run is therefore **3-leg**.

This was a known substitution (6S is unavailable in Tradezella; CHFUSD was the stand-in), but its
consequence has not been stated before: **no trade in the tally has the model's fourth leg.**

### R18 — 91% have no weekly-cycle SMT

Rule 18's canonical form is *weekly-cycle SMT with daily-cycle SMT inside it*. 116 of 128 entries
raise `no weekly-cycle SMT on this side in the 12-week lookback`. The nesting actually traded is
daily+4H.

⚠️ **The 12-week lookback is a declared constant, not a measured one**, and S1d already flagged
that the nearest prior weekly SMT fell at **~14 weeks — just outside it**. A constant that
excludes the nearest real signal is a prime suspect, not a settled parameter.

### R30 — 90% are not the first retest

`this is NOT the first retest of the inverted zone`. The engine's entry window is 08:00–16:00 ET,
so when price first re-enters the iFVG **overnight**, the entry taken is a later, worse touch.
S1d found this on its single trade; over 2.4 years it is **the normal case, not the exception**.

### R30/R32 — 56% are on the wrong side of equilibrium

49 SHORTs entered in **discount**; 23 LONGs entered in **premium**. The engine's own line for one:

> `R5: entry in PREMIUM (0.99 of range)` · `R35: target 18,144.75 (range extreme) · 0.0R PLANNED`

— a LONG risking **310.5 points to make 9.5**, entered at the very top of the range.

⚠️ **Open question for the videos:** rule 30 says discount/premium **"of the LTF range"**. The
engine measures against the driving (HTF) range. If that reference is wrong, this entire row is
mis-measured.

### R44 demonstrated exactly

| Planned R:R | n | Win rate | Per trade |
|---|---:|---:|---:|
| **0 – 0.5R** | 24 | **70.8%** | **−0.150R** |
| 0.5 – 1R | 25 | 56.0% | −0.059R |
| 1 – 2R | 22 | 54.5% | +0.327R |
| 2 – 5R | 24 | 20.8% | −0.168R |
| 5R+ | 33 | 12.1% | +0.204R |

**The highest win rate is the worst-performing bucket.** *"A win rate without its R:R is
meaningless"* — R44, measured.

---

## ⭐⭐ What happens when the preferences are honoured

This is the test that matters, and it **fails in the direction nobody wanted**.

| Filter applied cumulatively | n | Win% | Total | Expectancy |
|---|---:|---:|---:|---:|
| ALL (as run) | 128 | 40.6% | +4.84R | +0.038R |
| + first retest only (R30) | 13 | 30.8% | −4.98R | −0.383R |
| + right side of equilibrium (R30/R32) | 8 | 25.0% | −2.46R | −0.307R |
| + planned R:R ≥ 1 (R45) | 7 | 28.6% | −1.46R | −0.208R |
| + entry at/after 09:30 (R31) | 6 | 33.3% | −0.46R | −0.076R |
| + weekly-cycle nesting (R18) | **0** | — | — | — |

**Honouring Aura's stated preferences does not improve the result — it destroys the sample.**

⛔ **No conclusion about Aura may be drawn from this table.** At n = 6 the numbers carry no
information, and at n = 0 there is nothing to measure. What the table actually demonstrates is
that **the engine cannot produce a trade satisfying the model's own stated conditions
simultaneously** — which is a statement about the engine, not about the model.

### The three candidate explanations, none yet eliminated

1. **The detectors are mis-specified** (most likely). The Aura Asset is refused at daily on 100%
   of trades; weekly SMT is found on 9%; "first retest" is decided inside an 08:00–16:00 window
   that cannot see an overnight touch. Each of those is a coded assumption, not a measured fact.
2. **The conditions are genuinely rarer** than the rulebook implies, and Aura is a handful of
   trades per year rather than 128.
3. **The preferences are meant to be applied with judgement**, not as simultaneous hard gates —
   rules 30/31 are explicitly marked *soft*, and stacking soft preferences as AND-filters may be
   a misreading of the model.

---

## The four questions the videos can settle, and the engine cannot

Ranked by how much of the result they move:

1. **The Aura Asset.** Is 6S/CHFUSD meant to be evaluated on its own session calendar rather than
   the futures'? Right now it is refused on every trade, so the model's 4th leg has never voted.
2. **Weekly nesting.** What lookback defines "the current weekly cycle"? 12 weeks is this engine's
   invention, and the nearest real signal sat at 14.
3. **The retest.** Does "entry on the iFVG" mean the *first* retest only, and does an overnight
   retest consume it — or does the NY session get its own first touch?
4. **The reference range.** Is discount/premium measured against the **LTF** range (rule 30's
   words) or the driving HTF range (what the engine does)?

Two more worth checking while there: **is Aura directional-neutral?** The engine was SHORT 77% of
the time (100% in 2025) while NQ rose **+79.6%** over the span. And **should the same live SMT and
range be re-entered daily** (R7), which is what turned 32 ideas into 128 trades?

---

## What was verified in producing this

| Check | Result |
|---|---|
| Declared span written before any outcome computed | ✅ `declared-span.md` |
| S1c regression through the new export pipeline | ✅ 20/22 days identical; the 2 differences are the days S1c reported `DATA` for lack of lookback |
| NQ 15m derivation (native cap at 2025-03-23) | ✅ 4,489 overlapping buckets, **0 mismatches**; derived count equals ES/YM natives exactly |
| CHFUSD 5m depth | ⚠️ first read 678 bars was **lazy loading**, not a limit — 177,074 after nudges |
| Outcome resolution | ✅ 128/128 resolved; 0 `UNRESOLVED` |
| Counting basis published both ways | ✅ entry-day (128) and episode (32) |
| Every ratio carries its sample size | ✅ |

## What this audit does NOT claim

- **No edge is claimed or denied for Aura.** The faithful subset is empty; there is nothing to
  judge the model on.
- **No filter here should be adopted because it improved a number.** The cumulative table exists
  to show the sample collapsing, not to select a profitable subset.
- **R8, R9, R31 remain UNRESOLVED**, as they must.
- The engine remains `QUARANTINE` — nothing here touches `evidence_assets`, rep credit, the
  streak, calibration or the Readiness Gate.
