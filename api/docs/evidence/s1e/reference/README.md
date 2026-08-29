# Reference — the QT[✦] Pine indicators, and what they correct in our engine

**Received from Paul 2026-08-15**, pasted into chat. Three scripts by *Enigma / ENIGMA_001*,
importing `ENIGMA_001/AssetCorrelationUtils/8`.

| File | Script | State |
|---|---|---|
| `qt-ultimate-quad.pine` | 1 — `QT[✦]Ultimate++` **with the 4th asset (quad)** | ⚠️ **TRUNCATED in chat** (~90 KB missing, cut mid-QCISD). Paul re-sending. |
| `qt-ultimate.pine` | 2 — `QT[✦]Ultimate++`, no quad leg | complete |
| `qt-pro.pine` | 3 — `QT[✦]Pro` — HTF candles, sweeps, midpoints, FVG, NWOG/NDOG, pD/W/M levels | complete |

⚠️ **The raw `.pine` files are to be pasted in by Paul, not transcribed by Claude.** Re-typing
100 KB from chat risks a silent transcription error in a *reference source* — the same
"succeeds, reports success, wrong result" failure class as the coordinate clamp, the ignored
override keys, the stale screenshot and the lazy-loaded bars. Excerpts below are quoted exactly.

⛔ **STATUS: EVIDENCE, NOT GROUND TRUTH.** This is Enigma's Quarterly-Theory tooling, not
dOoMeR's own code. It settles **mechanics**; it cannot settle what an Aura rule *means*. Where it
contradicts `rules.md`, that is a finding for Paul — never a silent adoption.

---

## ⭐ CORRECTION 1 — the cycles are Quarterly-Theory SEGMENTS, not timeframes

Our engine mapped Aura's cycles onto chart timeframes: `W / D / 240 / 60 / 15 / 5`.
**The indicator does nothing of the kind.** Verbatim:

```pine
dayStartHour = input.int(18, "Day Start Hour (TZ)")   // tz default 'UTC-4' (NY)
qDay   = int(math.floor(minsFromDayStart / 360)) + 1  // 1..4  — four 6h quarters of the day
minsIn6H = minsFromDayStart % 360
q90    = int(math.floor(minsIn6H / 90)) + 1           // 1..4  — four 90m within each 6h
msMicro = 1350000                                     // 22.5 minutes
qMicro = int(math.floor(msInto90 / msMicro)) + 1      // 1..4  — four 22.5m within each 90m
qWeek  = dow_c == sunday ? 1 : monday ? 2 : ...       // 1..7  — day-of-week
qMonth = ((curr_week - 1) % 4) + 1                    // 1..5  — week-of-month
q2Month = ((mo_c - 1) % 3) + 1                        // 1..4  — month-in-quarter
qYear  = mo_c <= 3 ? 1 : mo_c <= 6 ? 2 : ...          // 1..4  — quarter-of-year
```

and the cycles are then run as:

```pine
f_allrun(tf_ok    , ..., val_ses , "90m",   ...)
f_allrun(tf_ok_mic, ..., val_sesm, "Micro", ...)
f_allrun(tf_okD   , ..., val_sesD, "Daily", ...)
f_allrun(tf_okW   , ..., val_sesW, "Weekly",...)
f_allrun(tf_okMo  , ..., val_sesMo,"Monthly",...)
```

**So the cycle's NAME is the container and the comparison is between its SEGMENTS:**

| Cycle name | What is actually compared |
|---|---|
| **Daily** | consecutive **6-hour quarters within the day** (18:00 Asia · 00:00 London · 06:00 NY AM · 12:00 NY PM) |
| **Weekly** | consecutive **days within the week** |
| **Monthly** | consecutive **weeks within the month** |
| **90m** | consecutive **90-minute quarters** within a 6h session |
| **Micro** | consecutive **22.5-minute quarters** within a 90m |

This is **rule 22** read literally — *"if SMT occurred **between two segments** of a larger cycle,
expect the extreme of that larger segment to be taken."* We read "segments" as timeframe bars.

⭐ **This alone likely explains S1e's `R18 91% — no weekly-cycle SMT`.** We hunted 3-candle pivots
on **weekly bars** across a 12-week lookback. Under this definition a weekly-cycle SMT is available
*every week* — it is the days inside it.

---

## ⭐ CORRECTION 2 — SMT is segment-extreme divergence, not pivot sweeping

```pine
_bear0 = ((ah1 >= ah0 and bh1 <= bh0) or (ah1 <= ah0 and bh1 >= bh0)) and not(ah1 == ah0 and bh1 == bh0)
_bull0 = ((al1 <= al0 and bl1 >= bl0) or (al1 >= al0 and bl1 <= bl0)) and not(al1 == al0 and bl1 == bl0)
```

`ah1`/`ah0` are the **highest high of the previous vs the current cycle segment** on the primary
asset; `bh1`/`bh0` the same on the comparison asset — tracked by `f_main_process`, which simply
carries a running `hmax`/`lmin` per segment bucket and rolls it at the segment boundary.

So SMT = *one asset made a higher high while the other made a lower high, segment over segment.*

**Our engine instead required a 3-candle pivot and then asked whether each leg SWEPT it inside a
forward window, against a measured tick floor.** Different detector → different signals, different
dates, different bias. Script 3 agrees with script 1 candle-to-candle:

```pine
if c1_l < c2_l and a2_l > a2_pl      // primary made a lower low, asset2 did not
    a2_bull_smt := true
if c1_h > c2_h and a2_h < a2_ph      // primary made a higher high, asset2 did not
    a2_bear_smt := true
```

Script 3 also keeps an **invalidation target** per SMT (`smt_bull_target_*`) and deletes the SMT
when the lagging asset's level is taken — matching rule 23 ("only currently-valid SMTs; never read
a stale signal").

---

## CORRECTION 3 — the Aura Asset is wired in as the default 4th leg (R17 confirmed)

```pine
enable_quad = input.bool(true, "Enable 4th Asset", ...)
quad_sym    = input.symbol("CME:6S1!", "Symbol", ...)
inv_quad    = input.bool(false, "Inverse", ...)
```

**6S is the default**, enabled by default, added *alongside* the existing 2-asset comparison, with a
per-leg **Inverse** flag. That is rule 17 exactly, and it supports S1e's session-date join — the leg
is meant to vote, and ours never did (it read `NOT-VISIBLE` on 100% of setups).

---

## Other mechanics it pins down

| Object | Indicator's definition (verbatim) | Ours |
|---|---|---|
| **Sweep** | `high > prev_candle.h and close < prev_candle.h` — took it **and closed back inside** | extreme exceeded by a tick floor; no close condition |
| **Day boundary** | forced **18:00 NY** (`dayStartHour = 18`, `force1800`) | measured per symbol |
| **Midpoint / CE** | `midpoint_price = (prev_candle.h + prev_candle.l) / 2` | not implemented |
| **NWOG** | Friday close → Monday open, classified Void/Overlap × Bull/Bear | Friday close → Monday open ✓ |
| **NDOG** | prev-day close → **18:00** open | measured session boundary |
| **FVG (chart)** | `low > high[2]` (bullish) / `high < low[2]` (bearish), optional ATR size filter | 3-bar gap + declared 4-tick floor ✓ close |
| **9:30 gap** | prev-day **16:14** close → 09:30 open, with 50/25/75 levels | not implemented |
| **pD/W/M levels** | previous day/week/month H+L, drawn until **broken**, with EQ and quadrants | not implemented |

### ⚠️ Divergence to flag, NOT to adopt

The indicator draws **quadrants (0.25 / 0.75)** on previous D/W/M ranges and on NWOG/NDOG.
`rules.md` **rule 5** says Aura uses **discount / EQ / premium only** and names quadrants as an
explicit ICT divergence. The tool does not overrule the rulebook — Paul decides.

---

## What it does NOT settle

It is a **marking** tool, not an execution model. It says nothing about:
R30's iFVG entry trigger · R32's premium/discount entry gate · R45's 1:1 minimum ·
target selection · re-entry (R7) · position management.

Those remain questions for the videos and for Paul.
