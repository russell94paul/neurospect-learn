# Aura object inventory — the exhaustive list, and what we actually implement

**Built 2026-08-15 from the canonical concept pages**, at Paul's direction ("refer to aura
information for exhaustive list of concepts pd arrays"), not from memory or from my own ordering.

Sources: `neurospect-wiki/concepts/aura/{swing-points,ranges,gaps,sequential-smt,triads-asset-selection,aura-asset,htf-ltf-application}.md`
and `concepts/mastery/aura/rules.md`. Indicator column from `s1e/reference/*.pine`.

Legend — **US** = `aura_setup_engine.py` (S1d.1) · **QT** = `aura_qt_smt.py` (new) ·
**IND** = the QT[✦] Pine indicators.

---

## ⭐⭐ THE CORRECTION THIS DOCUMENT EXISTS TO RECORD: there are TWO SMT objects, not one

We have been treating "SMT" as one thing. The corpus describes **two distinct objects** that do
**different jobs**, and conflating them is why the engine and the indicator disagreed:

| | **Swing-point SMT** | **Cycle (Sequential) SMT** |
|---|---|---|
| Unit compared | a **3-candle pivot** | a **cycle SEGMENT's extreme** |
| Source | `swing-points.md` (aura-06) — *"candle 2 failed to take out … candle 3 failed to take out the high … however on YM it took it out"* | `sequential-smt.md` (aura-07/12) — *"Wednesday failed to take out Tuesday's high … SMT within the weekly cycle at the day level"* |
| Job | **qualifies swing points** → which are valid **range anchors** (rule 3, rule 8) | **sets bias / context** across nested cycles (rule 18) |
| Implemented in | **US** (pivot + sweep + forward window) | **QT** (segment-extreme divergence) · **IND** |

**Neither implementation was complete.** `aura_setup_engine.py` built only the swing-point object and
then used it for the cycle job. `aura_qt_smt.py` builds only the cycle object. **The model needs both.**

⭐ **The segment reading is confirmed by the corpus, not just the indicator.** Rule 22's own wording:
*"if SMT occurred between two segments of a larger cycle — **between quarters within a week, between
days within a session, between hours** — expect the extreme of that larger segment to be taken."*

⚠️ **Naming convention (aura-07):** *"mark swing points on the weekly time frame and filter for the
ones carrying SMT, and what you're looking at is **monthly cycle SMT**"* — the cycle label is **one
level above** the chart you read it on. Our engine's cycle labels are therefore **off by one rung**
against the corpus, independently of the segment question.

---

## A. Structural primitives

| # | Object | Definition (source) | US | QT | IND | Status |
|---|---|---|---|---|---|---|
| A1 | **Swing point** | 3-candle pivot; candle 2 is the pivot. **Fractal** across all TFs | ✅ | — | ✅ (`ta.pivothigh/low(1,1)`) | OK |
| A2 | **SMT-qualified swing point** | a swing confirmed by triad divergence "has a higher chance of holding" — **the load-bearing filter** | ✅ | — | ✅ | OK |
| A3 | **Range** | the **largest expansive move** between two swing points *is* the range. **Not** time-based | ✅ | ❌ | ❌ | **QT gap** |
| A4 | **New-range trigger** | HTF Sequential SMT **+ expansive move away**; follow it until an **opposing** or **same-cycle** SMT | ✅ | ❌ | ❌ | **QT gap** |
| A5 | **Range invalidation** | a candle **CLOSE** beyond the boundary; a wick through is not a break | ✅ | ❌ | ❌ | OK in US |
| A6 | **Discount / EQ / Premium** | three zones only. **No quadrants** (explicit divergence from ICT) | ✅ | ❌ | ⚠️ **draws quadrants** | **conflict — see D** |
| A7 | **Range nesting** ("a range within a range") | smaller ranges inside larger; an inner range's low stays an attraction level | ❌ | ❌ | ❌ | **NOT IMPLEMENTED** |
| A8 | **Range ambiguity is allowed** | two defensible ranges may be tracked at once; do not force one | ⚠️ `R9_AMBIGUITY_TOLERANCE` refuses instead | ❌ | ❌ | partial |
| A9 | **"Zoom out until obvious"** | fallback: most recent obvious low + most prominent obvious high | ❌ | ❌ | ❌ | not implemented |

## B. PD arrays — the gaps. **Exactly four. No others.**

> *"The only gaps I care about are… fair value gaps, inverse fair value gaps, or new week opening
> gaps and new day opening gaps."* (aura-09). No BPR, no volume imbalance.

| # | Object | Definition | US | QT | IND | Status |
|---|---|---|---|---|---|---|
| B1 | **FVG** | 3-candle gap; `low > high[2]` (bull) / `high < low[2]` (bear) | ✅ (+4-tick floor) | ❌ | ✅ (+ATR filter) | OK |
| B2 | **iFVG** | an FVG that price has **closed through**, inverting its polarity | ✅ | ❌ | ❌ **absent — 0 matches in all 3 scripts** | **US only** |
| B3 | **NWOG** | Friday close → Monday open | ✅ | ❌ | ✅ (+Void/Overlap × Bull/Bear classes) | OK |
| B4 | **NDOG** | previous day close → new day open (**18:00 NY**) | ✅ (measured boundary) | ❌ | ✅ (forced 18:00) | minor divergence |
| B5 | ⭐ **"What lies within" — liquidity nested INSIDE a gap** | **the precise target is the swing high/low sitting inside the gap, NOT the gap boundary** | ⚠️ R12 partial | ❌ | ❌ | **UNDER-BUILT — this is Paul's "nearest IRL"** |
| B6 | **Fallbacks when no internal liquidity** | **look left** (resting untaken level at similar price) **or zoom in** (lower-TF swing inside the same gap) | ❌ | ❌ | ❌ | **NOT IMPLEMENTED** |
| B7 | **Confluence stacking (additive)** | overlapping gaps (NWOG/NDOG × FVG) · liquidity **left of** the gap **plus** inside it · **near-equilibrium** gaps still count | ❌ | ❌ | ❌ | **NOT IMPLEMENTED** |

## C. The confirmation engine

| # | Object | Definition | US | QT | IND | Status |
|---|---|---|---|---|---|---|
| C1 | **Triad, math-first** | Pearson on daily returns, 2–3yr, "sweet spot" | ⚠️ assumed | ⚠️ **measured 2026-08-15**: ES +0.93 · YM +0.83 · **CHFUSD +0.04** | ✅ (AC library) | **CHFUSD fails the premise** |
| C2 | **Aura Asset (6S)** as 4th leg on **every** triad | read "exactly like a normal divergence leg" *(flagged rule)* | ❌ refused at D/W | ✅ (session-bucket) | ✅ default `CME:6S1!` | **open question** |
| C3 | **Sequential SMT = nesting across ≥2 adjacent cycles** | the *sequence* is the signal | ⚠️ co-formation | ✅ **activity overlap** | ✅ (`f_alert` on 2 cycles) | QT correct |
| C4 | **SMT lifecycle** | only **currently-valid** SMTs count; invalidated ones disappear | ❌ | ✅ | ✅ (line deleted when extreme taken) | QT correct |
| C5 | **Confirmation route (a) cross-cycle** | HTF confirmed by LTF or vice versa | ✅ | ✅ | ✅ | OK |
| C6 | **(b) gap SMT-fill / SMT-fail** | one triad asset retraces **into a shared gap** while another does not | ⚠️ R21 partial | ❌ | ❌ | **UNDER-BUILT** |
| C7 | **(c) candle-level** | the swing candle *also* makes SMT vs the immediately prior candle on that TF | ❌ | ❌ | ✅ (PSP) | **NOT IMPLEMENTED** |
| C8 | **(d) Sequential Skip** | HTF SMT unconfirmed by the adjacent cycle → a cycle **further down** confirms it | ⚠️ reported | ❌ | ❌ | partial |
| C9 | **Cross-cycle gap pairing** | Weekly→**daily gaps** · Daily/session→**4H gaps** · Micro→**15m–1H gaps** | ✅ R21 | ❌ | ❌ | OK |
| C10 | **Cross-asset Skip variant** | bias set but primary won't offer an entry → same setup on another triad member | ❌ | ❌ | ❌ | not implemented |

## D. Execution

| # | Object | Definition | US | Status |
|---|---|---|---|---|
| D1 | **Entry: 5m iFVG** (3m allowed, 5m preferred); plain FVG is the fallback | ✅ | OK |
| D2 | ⭐ **Entry zone** | *"wait for a session-cycle Sequential SMT **within discount** (long) / premium (short) **of this LTF range**"* | ⚠️ measured vs **HTF** range | **WRONG REFERENCE RANGE — corpus says LTF** |
| D3 | **Stop** | the level whose respect invalidates the trade — the qualifying daily/4H SMT extreme | ✅ | OK |
| D4 | ⭐ **Target** | **TP1 = equilibrium of the HTF range**; **TP2 = liquidity within discount/premium** (B5), or the range extreme | ❌ **range extreme only** | **WRONG — and this produced the `0.0R PLANNED` trades** |
| D5 | **Paul's actual management** (2026-08-15) | half off at **nearest IRL**, rest to final TP, SL to breakeven | ❌ single target | **engine models a trade Paul never takes** |
| D6 | **Premium/discount sets the R:R ceiling** | entering in premium ⇒ target a lower R:R | ⚠️ reported | partial |
| D7 | **Prefer the 09:30 open** on Skip/news setups *(soft)* | ⚠️ branch | OK as soft |
| D8 | **Patience rule** | don't scalp a gap-liquidity reversal before price reaches the deeper discount/premium | ❌ | not implemented |

---

## ⛔ Conflicts to put to Paul — NOT to resolve silently

1. **Quadrants.** `IND` draws 0.25/0.75 on pD/W/M ranges and on NWOG/NDOG. **Rule 5 / `ranges.md`
   say Aura uses discount/EQ/premium only** and names quadrants an explicit ICT divergence.
2. **The Aura Asset.** Rule 17 mandates it on every triad; measured Pearson vs NQ is **+0.04**, so
   rule 15's premise ("correlated enough that agreement is expected") fails. Under the indicator's
   **OR** of legs it can only *add* signals — it roughly **doubles** the Sequential count.
3. **Flat-leg divergence.** `IND` counts a leg that did not move at all as diverging (it excludes
   only the case where *both* are flat). Faithful in QT, but a real noise source.
4. **Cycle labels off by one rung** (aura-07's naming convention) — independent of the segment fix.
5. **Micro cycle.** dOoMeR "explicitly skips the micro cycle" (aura-07) yet `IND` ships it and pairs
   Daily+Micro in a default alert.

## What is missing everywhere (nobody implements these)

**A7** range nesting · **B5/B6** liquidity-within-gap and its look-left/zoom-in fallbacks ·
**B7** confluence stacking · **C7** candle-level confirmation · **C10** cross-asset skip ·
**D8** the patience rule.

**B5 is the most valuable of these** — it is simultaneously rule 12's "precise target", the
`gaps.md` core thesis, and Paul's **TP1 (nearest IRL)**.
