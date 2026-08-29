# S1d — one replayed week, marked up: `2025-05-26 → 05-30` (NY session)

> ## ⛔ HOW THIS WEEK WAS CHOSEN — read this before reading any number
>
> **SELECTED, not sampled.** This week was picked *because it contains the one known
> qualifying setup* (the 05-30 SHORT) that S1c found over 2025-05-01 → 05-30. At a base
> rate of 1 setup per 22 weekdays, a randomly chosen week yields **zero** entries as the
> overwhelmingly likely outcome, so a week with an entry in it had to be chosen
> deliberately for this artifact to teach anything about an entry at all.
>
> **This week therefore carries ZERO information about how often setups occur.** No
> frequency, hit rate, win rate or expectancy can be computed from it, and none appears
> anywhere below. If you form an impression of "how often this happens" from these five
> days, that impression came from the selection, not from the market.

> ## ⚠️ MACHINE-GENERATED — NOT A TRAINING RECORD
> Computed by `api/scripts/aura_setup_engine.py` (engine `S1d.1`) from exported bars.
> Not reps, not practice, not evidence. Must never touch `evidence_assets`, rep credit,
> the streak, the calibration score or the Readiness Gate.

---

## The week at a glance

| Day | Verdict | Bias | Failing rule | Marked-up shapes |
|---|---|---|---|---:|
| Mon 26 May (Memorial Day) | STAND ASIDE | LONG | R6 | 7 |
| Tue 27 May | STAND ASIDE | LONG | R6 | 7 |
| Wed 28 May | STAND ASIDE | LONG | R6 | 7 |
| Thu 29 May | STAND ASIDE | LONG | R6 | 7 |
| **Fri 30 May** | **SETUP — SHORT entry taken** | SHORT | — | 26 |

**1 entry · 4 stand-asides.** Four days of the five are the model telling you to sit on
your hands, and that is the honest shape of a real week — *"a real session is mostly
markup and sitting on your hands."*

---

## ⭐ The single most important fact about this week

**Four of the five stand-asides are the same finding, restated.** Every one of
26–29 May rejects at **R6** against the *same dead range* (`19,103.75–20,276.75`), which
was killed on **2025-05-12** when a daily candle **closed above** `20,948.75`.

So the week does not contain four independent lessons. It contains **one**: after
2025-05-12 there was no live range to trade, and the model says wait for the next
Sequential SMT to anchor a new one (R7). The 05-20 SMT is what eventually anchored the
range that produced Friday's trade.

⚠️ **This is the finding your review is most needed on.** S1c stood aside on 21 of 22
days and R6 alone accounted for 13. Nothing available can tell us whether that is
correct — re-reading the rulebook cannot settle it, and running unmarked days cannot
settle it. **Your judgement on whether these R6 stand-asides are right reads is the only
calibration instrument that exists.** If R6 is being applied too strictly, this is where
it shows.

### Memorial Day (Mon 26 May) — the teaching point, kept rather than filtered

The holiday session was real but truncated: **48 five-minute bars in 09:00–16:00 ET**
versus 84 on each normal day (an early 13:00 ET close). The engine's data guard
(≥ 12 bars) passed, so Memorial Day was evaluated as an ordinary session and rejected at
R6 exactly like the others.

**The holiday made no difference to the verdict** — the range was already dead, so the
short session never got a chance to matter. That is worth seeing: a shortened day is not
automatically a "no-trade day" by rule, it just happened to be one here.

---

## Friday 30 May — the one entry, in full

| Field | Value | Rule |
|---|---|---|
| Bias | **SHORT** | R18 |
| Framing range | `20,727.00 – 21,562.25` (835.25 pts, move 05-20 → 05-23) | R4 |
| Driving SMT | swing high `21,562.25` @ 05-20 09:30 ET; NQ took it by 21 ticks, **ES missed by 141 ticks, YM by 234** | R3 |
| Knowable from | **2025-05-29 09:30 ET** (bar-derived, not calendar) | R18 |
| Confirmation | **Sequential SKIP** — 4H did *not* confirm; 15m did @ 05-29 14:45 ET | R24 |
| Paired-cycle support | 4H bearish gap `21,447.25–21,485.25` formed 05-29 10:00 ET | R21 |
| Opening gap | **NDOG** `21,371.25–21,385.00` formed 05-29 18:00, mitigated 18:05 | R11 |
| Entry | **`21,341.75`** @ **08:05 ET**, retest of a 5m iFVG (`21,341.75–21,343.25`, inverted 05-29 20:30) | R30 |
| Position in range | **PREMIUM**, 0.74 of range — correct side for a short | R5/R32 |
| Target liquidity | `21,342.00` inside the gap, found *inside* (no zoom-in needed) | R12 |
| Stop | **`21,567.50`** — the swept high extreme of the qualifying daily SMT · risk **225.75 pts** | R33 |
| Target | **`20,727.00`** (range extreme) · **2.7R PLANNED** | R35 |

### ⛔ The outcome is NOT a result — and this is the phase's hardest limitation

| | |
|---|---|
| Verdict | **`UNRESOLVED-AT-DATA-EDGE`** |
| Realised R | **none** |
| MFE | **1.20R** in favour |
| MAE | **0.41R** against |
| Walked | **534 × 1m bars**, entry → data edge |

**Neither the stop nor the target was reached before the bars ran out.** The replay is
parked at **2025-05-30 16:59 ET** and that edge was confirmed at 1-minute resolution on
all three futures legs — there is no later bar on this chart to walk to. Advancing the
replay would consume days Paul intends to replay himself, and this phase forbids it.

So the trade went **1.20R in favour** and **0.41R against**, and then the instrument
stopped. That is a **measurement gap, not a breakeven and not a loss.** It must not enter
any win rate.

*Cross-check:* the walk was run at both 1m and 5m and produced **identical** MFE/MAE
(1.1971R / 0.4064R), which is the expected result since 5m bars aggregate 1m bars — a
small positive control on the outcome walker itself.

### What the record flags on its own face (10 branches, 3 unresolved)

Reported, never resolved into a clean answer:

- **R8 (unresolved, ×2)** — neither range extreme was swept on every triad leg, and a
  materially different all-legs-swept candidate exists for each. R8 prefers the
  all-legs-swept extreme; the engine reports both and does **not** re-anchor.
- **R30** — **this is not the first retest of the inverted zone.** Price first returned
  at 05-29 **20:40**, *outside* the 08:00–16:00 ET entry window, so the 08:05 touch taken
  here is a **later** one. R30 does not say whether a re-tested iFVG is still valid.
  The entry window is what made the earlier touch invisible to the scan.
- **R31 (soft)** — entry 08:05 is **before** 09:30. dOoMeR prefers waiting for the open,
  particularly for traders still building consistency. A strict 09:30 filter would
  **delete this trade entirely.**
- **R17 (flagged)** — the 15m confirmation diverges on **CHFUSD alone**, with no index leg
  agreeing, on the leg whose tick size is the least reliably measurable of the four. The
  weakest link in the chain.
- **R34** — the stop is 225.75 pts, **27% of the range**, over the declared 25% flag. R34's
  answer is the same idea on a correlated leg with a tighter gap; not taken automatically.
- **R22** — the weekly-segment extreme is the **same price** as R35's target
  (`20,727.00`), so R22 adds **no independent target** here.
- **R18** — **no weekly-cycle SMT** in the 12-week lookback, so this read does *not* have
  R18's canonical weekly-with-daily-inside structure. Daily→4H still satisfies R18, but
  this is the weaker of the two forms. *(This is a measured `ZERO`, not a blind spot —
  see below.)*
- **R11** — 9 further bearish iFVGs in premium inverted *after* the 08:05 entry and are
  deliberately not drawn; 4 candidate FVGs were excluded under the 4-tick size floor.

---

## What was hardened in S1d, and what it cost

| Gap from `s1c/accuracy.md` | Status |
|---|---|
| Bounded markup primitives (Paul's rejection) | ✅ **done** — 33 bounded shapes, zero `horizontal_line` |
| NWOG / NDOG (R11) | ✅ **done**, on a **measured** per-symbol session boundary |
| Weekly cycle | ✅ **done** — exported natively, never aggregated from daily |
| R21 cross-cycle gap-pairing | ✅ **done** — reported as supporting confirmation |
| R22 extreme-of-larger-segment | ✅ **done** — reported *alongside* R35, never swapped in |
| R13 look-left / zoom-in | ✅ **done** — both routes computed, source recorded |
| R8 false-sweep tiebreak | ⚠️ **measured, deliberately not resolved** (see accuracy.md) |
| Outcome simulation | ✅ **done** — and it revealed the trade cannot be scored |
| Deeper 5m history | ➖ not needed at one week; blocking if the span grows |

**Regression evidence:** re-running S1c's original span (2025-05-01 → 05-30) with the
hardened engine reproduces **all 22 day-verdicts identically**, the same setup on the same
day with the same bias, and the same entry gap. Every S1d change is additive. The
independent audit `aura_verify_record.py` still passes all 12 checks including the
no-lookahead assertion.

---

## Six defects this phase found — all of which produced confident-looking output

The pattern S1c established held: the engine was wrong in ways that read as competent.

1. **Rectangles whose end preceded their start** (15 shapes). `attach_mitigation`
   searched from the original FVG formation, but for an iFVG the inversion *is* price
   closing through the zone — so it found the inverting move and dated mitigation before
   inversion. Now guarded: `shape()` raises on a non-increasing time extent.
2. **⭐ The chart silently clamps shape coordinates to the loaded data window.** 13 of 33
   shapes were wrong on the first drawing pass — 7 collapsed to zero width — while
   `createMultipointShape` threw nothing, the promise resolved, and `getAllShapes()`
   returned the correct **count**. Counting is not verifying.
3. **My own session-boundary measurement mis-classified CHFUSD's weekend break as its
   daily boundary** (75% "support" on 3 observations), because the filter excluded only
   gaps longer than three days. Daily and weekly breaks are now separated by *calendar
   days skipped*. CHFUSD's correct verdict is **NOT-MEASURABLE** — no daily halt exists —
   which is precisely why S1c refused to implement NWOG/NDOG at all.
4. **R8 fired on every single setup.** The check ran on the driving SMT pivot, and an SMT
   is *by construction* a level the other legs did not take — so "not swept on all legs"
   was the definition of the signal, not a warning about it. A check that can never pass
   trains you to skip the UNRESOLVED lines. Now applied to the range anchors, where R8
   actually bites: 3 distinct findings across 22 days instead of 16 restatements.
5. **R22 double-counted the same price** as an independent second target.
6. **The outcome walk misreported its own instrument** — it claimed 5m while 1m data was
   loaded and had already been walked, because each coarser attempt overwrote the finer
   one's verdict.

**No FVG size floor existed at all** before this phase, so a **one-tick** gap was an entry
candidate on equal footing with a six-tick one — the same defect class as phantom SMT.
A 4-tick floor is now declared, its exclusions are counted per day rather than dropped
silently, and it is **proved not to change S1c's result** (that entry gap is 6 ticks).

---

## Instruments proved live (a zero from an unproven instrument is not a measurement)

- **Weekly SMT detector:** finds **13 events** across full history (6 high / 7 low, e.g.
  2020-06-08, 2024-06-24, 2025-01-20) with plausible dates and divergences. So the
  12-week lookback returning **0** for this week is a genuine `ZERO`, not a blind
  instrument. Note the nearest prior weekly SMT (2025-01-20, knowable 02-17) falls ~14
  weeks out — **just outside** the declared 12-week lookback, which is a real sensitivity
  to a declared constant.
- **Weekly alignment positive control:** NQ/ES/YM share **every** weekly timestamp
  (Mon 09:30 ET); CHFUSD shares **none** (Sun 17:00). Independently reproduces the daily
  alignment result at a new resolution, and confirms CHFUSD must stay refused above 4H.
- **Measured tick sizes** still recover the contract specs unaided: NQ 0.25 · ES 0.25 ·
  YM 1.0.

---

## What this week does and does not support

**Does:**
- The rules compute end-to-end on real bars, from weekly framing down to a 5m entry.
- Every level drawn on the chart is bounded to where the rule says it applies.
- A stand-aside is a first-class record with a reason you can argue with.
- One entry exists, fully specified, with every soft branch and weak link on its face.

**Does not:**
- ❌ No hit rate, win rate or expectancy — the week was selected, and n = 1 regardless.
- ❌ **No realised outcome for the one entry.** It is unresolved at the data edge.
- ❌ Nothing about how often setups occur.
- ❌ No claim that the R6 stand-asides are correct. That is the open question, and it is
  the one thing this artifact exists to put in front of you.

---

## See also

- `computed-setups.md` — the full per-day rule log, stand-aside reasons, and outcomes
- `computed-setups.json` — machine-readable, including every shape
- `chart-shapes-drawn.md` — the 33 drawn shapes, the clamping defect, and the **removal snippet**
- `chart-shapes-spec.json` — bounded shape spec with both endpoints per shape
- `accuracy.md` — what the engine does, does not do, and defers
- `bars/` — the native weekly export and the 1m week
