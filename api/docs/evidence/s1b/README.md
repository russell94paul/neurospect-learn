# S1b — the guided walkthrough, as a standalone page (2026-08-29)

A first draft of the S1b walkthrough built **as an Artifact rather than in the app**, so the design
could be judged before a session is spent wiring React. Paul chose this route explicitly
("Artifact first, then port"). **The app is untouched** — no route, no component, no migration.

Published: `https://claude.ai/code/artifact/2da34972-c89e-4a23-b064-a02e1df302b9`

## What it contains

| § | Deliverable | S1b prompt item |
|---|---|---|
| 01 | The eight checklist phases, tickable, per-phase progress, hard gates marked, ticks in `localStorage` | deliverable 1 |
| 02 | **D0 — the live entry decision tree**, path-building, with a full-map toggle | deliverable 4 |
| 03 | Markup figures — the §0b primitive before/after on real bars, a gap's life FVG→iFVG, range anatomy, the gap family, M1→M12 as a dependency chain | deliverable 2 |
| 04 | The per-trade card, five tiers, marked for who fills each | deliverable 3 |

## Where the content comes from — nothing is re-decided here

- **Rules** — 41 rules parsed out of `concepts/mastery/aura/rules.md`, text preserved verbatim.
  `soft` (R9, R31, R39, R54) and `flagged` (R5, R17, R37) are read from the source's own
  `*(soft)*` / `*(flagged)*` markers, not assigned by judgement.
- **Phases** — `concepts/mastery/aura/checklist.md`, all eight, in order.
- **The tree's spine** — `api/scripts/aura_setup_engine.py`'s declared `HARD_GATES` list, in its
  evaluation order (R3 → R18 → R6 → R7 → R30 → R35 → R29), and `SOFT_BRANCHES` for the soft nodes.
  Taken from code, per the S1b prompt's instruction not to re-derive the tree.
- **Bars** — `s1e/bars/tradezella-831607-NQ-5m-span.json`, session 831607, verbatim.

## The diagram rule was held

**No price data is fabricated.** Two classes of figure, marked differently on the page:

- `MEASURED BARS` — real exported OHLC. Gaps overlaid on them are **definitional arithmetic**
  (3-candle: bar 1 high vs bar 3 low, ≥4 ticks), reproducible from the same export by anyone.
- `SCHEMATIC · NOT A CHART` — range anatomy and the gap taxonomy. These are drawn as schematics
  **specifically because** the range / SMT / bias / target detectors were found wrong on
  2026-08-15 and are still gated on the TradingView SSMT validation. No detector output is
  rendered anywhere as a claim about a real day.

The page's own honesty strip states all four constraints up front, including `n = 0` when the
model's quality rules are enforced.

## Generator

`api/scripts/aura_figure_pack.py` (extended this session) slices real bars + computes definitional
gaps into `figure-pack.json`, then renders the charts to **inline SVG at build time**. Two reasons
not to use a charting library: the Artifact CSP does not admit TradingView's widget host, and a
CDN library that half-loads reproduces exactly the S1d failure mode — every success signal passing
while the drawing is wrong. Self-rendered SVG can be counted:

```
candles in fig 1: 96 (expect 96)     # == bar count
gap lines fig 1 : 30 (expect 30)     # == 2 x gap count
gap boxes fig 2 : 15 (expect 15)     # == gap count
```

That requested-vs-rendered count is the S1d lesson applied: enumeration by count is the *minimum*,
and the build fails loudly if a placeholder is left unsubstituted.

Rebuild with `python build_artifact.py` (needs `rules-subset.json`, regenerated from `rules.md`).

## Verified — at the rendered layer, over CDP

`verify.mjs` and `verify-leaves.mjs` drive headless Chrome through the DevTools protocol.

| Check | Result |
|---|---|
| Horizontal overflow @ 1280 | `scrollWidth 1280` — none |
| Horizontal overflow @ 400 | `scrollWidth 400` — none |
| Console errors / warnings | **none** |
| JS parses (`node --check`) | clean |
| HTML tag balance | div/section/figure/svg/button/ul all matched |
| Light theme | renders, all tokens resolve |
| Dark theme | renders, all tokens resolve |
| Checklist persistence | tick → reload → still ticked → clear → 0/39 |
| Rule popover | shows real rule text from `rules.md` |
| Tree — stand aside | reachable from R3; renders as an **outcome**, not a dead end |
| Tree — all six entry leaves | standard · skip down-cycle · skip cross-asset · alt-asset R34 · pre-9:30 R31 · plus FVG-fallback and zone modifiers |
| **Tree never auto-ticks a rule** | 13 rules highlighted, **0 boxes checked** — the invariant holds |

### One instrument lied, and it is worth recording

The first 400px check used `chrome --headless --window-size=400,2600 --screenshot`, and the
image showed text clipped on the right. That was read as a CSS grid overflow bug and a
`min-width:0` fix was applied. **Measuring over CDP showed `scrollWidth` was 385 against a 400px
viewport — there was never any overflow.** `--window-size` does not set the layout viewport, so
the screenshot was a 400px-wide crop of a wider layout. The `min-width:0` rule is harmless and
defensively correct, but it fixed nothing.

Same shape as S1c/S1d: **a confident-looking artifact produced by an instrument nobody had
checked.** Device metrics must be set through `Emulation.setDeviceMetricsOverride`, not the
window size, before any narrow-viewport claim is believed.

## What this draft does NOT do

- **It is not in the app.** `/runner` is unchanged; the port is the remaining S1b work.
- **No Playwright coverage** — the app's `e2e/runner.spec.ts` is untouched, so none of this is
  guarded by the suite.
- **The S1b prompt's STEP 0 questions are still open**: Paul has not reviewed the S1d week, and
  the four R6 stand-asides remain uncalibrated. The tree therefore teaches R6 as the engine
  states it. The 33 `[S1d]` shapes are also still on NQ session 831607.
- **No capture surface** — that is S2, and S2 stays gated.

---

# Update — §04 Worked examples added (2026-08-29)

Paul asked for *"more detailed examples with marked levels and entries. sample trades."*
Four marked-up charts and four corpus trades were added. **No new analysis was run** — every
level drawn is the geometry the S1d engine already emitted.

## The four marked-up figures

Drawn from `s1d/chart-shapes-spec.json` (33 recorded shapes with exact time+price coordinates,
tool type and rule attribution) over real NQ bars from `s1e/bars/`.

| Figure | Bars | Shapes | What it shows |
|---|---:|---:|---|
| The dead range | 23 daily | 7 | Range `19,103.75–20,276.75` as **bounded segments stopping on 12 May**, its zones, the SMT-qualified low, and the **daily close at `20,948.75` that killed it** |
| Friday HTF | 220 × 60m | 9 | Live range `20,727.00–21,562.25` as **rays**, premium/discount, the qualifying swing high, entry/stop/target |
| Friday LTF | 276 × 5m | 17 | All 15 boxed iFVGs in premium, the traded one highlighted |
| Entry magnified | 180 × 5m | 10 | The traded zone `21,341.75–21,343.25` — **1.5 points, six ticks** — from formation (29 May 20:30) to retest and entry (30 May 08:05) |

The bounded-vs-ray contrast between figures 1 and 2 is §03's whole argument shown on two real
charts: the dead range's boundaries **stop where R6 killed them**; the live range's **run on**.

## Deliberate exclusions, stated on the page rather than quietly cropped

- **The stop (`21,567.50`) and target (`20,727.00`) are absent from both 5-minute figures.** The
  stop alone is 225.75 pts — **wider than that whole day's range** — so including either flattens
  every iFVG box to a hairline. That is R27's cascade problem, and it is the same fact the
  27%-of-range R34 flag points at. The page says so.
- **A shape whose anchor or end falls outside a window is reported in a visible note**, never
  silently clamped — the S1d defect where 13 of 33 shapes were wrong while every success signal
  passed. Only the HTF figure trips it (three R5 zone rectangles end 31 May 00:00, past the last
  60m bar); duplicate notes are de-duplicated.

## dOoMeR's own trades — and why no chart is drawn for them

`aura-18`, `aura-19`, `aura-24`, `aura-25` are walked through the decision tree, each landing on a
different leaf (pre-session override · standard · skip down-cycle · cross-asset). **No price levels
are drawn, because the corpus does not record any.** `concepts/aura/trade-reviews.md` documents the
read, the execution logic and the takeaway in prose; it contains no numeric entries, stops or
targets. Inventing them to fill a chart is precisely the fabrication the diagram rule forbids, so
the page states the absence instead.

`aura-18` earns its place: dOoMeR entered inside an Asia-session gap, **violating his own
"wait for New York" rule**, said so, and it worked anyway. That is the clearest available argument
for why R31 renders as a soft branch rather than a gate.

## What these examples are NOT

⚠️ **The levels come from detectors that were subsequently found wrong.** S1d predates the
2026-08-15 finding that the SMT layer conflated two distinct objects, that cycles are
quarterly-theory segments rather than timeframes, and that the target was the wrong object. The
range anchor and the bias both sit on top of that layer.

They are therefore published as **the engine's read, awaiting Paul's calibration** — which is what
S1d exists for and matches his standing ask: *"I want to review a backtest session and see what
trades you take to see if you are reading the chart and concepts correctly."* Each card is labelled
`Machine-generated · your review is the instrument`. **They are not worked examples of correct
play, and the page never presents them as such.**

The four R6 stand-asides remain the single most valuable thing to review: the same gate accounted
for 13 of 21 stand-asides in the wider month, and **no instrument other than Paul's judgement can
settle whether it is too strict.**

## Re-verified after the addition

| Check | Result |
|---|---|
| Horizontal overflow @ 1280 / 400 | `scrollWidth` 1280 / 400 — none (page is now 12,338 / 19,657 px tall) |
| Console errors / warnings | **none** |
| Worked figures rendered | 4 |
| Decision-path strips | 17 steps across two examples |
| Corpus trade rows | 4 |
| Rule chips expanded in prose | 19 |
| Traded-iFVG highlight | present in both 5m figures |
| Light + dark themes | both render; captions reworded to avoid naming a theme-specific colour |
| Checklist persistence / tree invariants | unchanged and still green |

---

# Update — §01 "Work a session", the guided run (2026-08-29)

Paul: *"can the walkthrough be step by step so the user can mark, i want guidance through whole
strategy"*, invoking `/living-systems-ui`. The page's spine is now a **19-step guided run** and the
reference sections sit behind it (§02 checklist · §03 tree · §04 primitives · §05 worked examples ·
§06 card).

## What it does

Each step names **what to draw and which primitive to draw it with**, cites its rules, and shows
that step performed on a real session. The chart beside the rail **builds up as you advance** —
every level revealed is a recorded S1d shape, never generated at runtime — and switches between the
60-minute and 5-minute views as the cascade demands. Tick, move on. Progress persists per browser.

Steps span the whole protocol, not just the markup: `SET · PRE · M1–M12 · D0 · SIZE · MAN · EXIT · REV`.

## The grammar that keeps it honest

`living-systems-ui` rule 2 — built, recommended and rejected must never look alike. Applied here to
what the *engine recorded*, because a blank chart at a step is ambiguous otherwise:

| State | Meaning | Steps |
|---|---|---|
| **Drawn** | the engine emitted this shape; it appears on the chart | M2, M3, M5, M6, M7, M8, M11, M12 |
| **Not recorded** | a real step of the protocol the engine emitted nothing for | M1 (only the *qualified* swing was kept, never the raw candidates), M9 (pairing is reported, confluence was never scored) |
| **Unresolved** | the rulebook contradicts itself and the engine refused to pick | M4 (R8's two sentences cannot both be satisfied by one swing) |
| **Action** | you do it; there is nothing to draw | SET, PRE, M10, D0, SIZE, MAN, EXIT, REV |

Every one of those states is legended on the page. **A blank chart at a NOT-RECORDED step is a
measurement gap, not a trivial instruction**, and the card says which.

## The failure path is a first-class path

The skill's sharpest note is that a visualiser showing only the happy path is a brochure. Here the
failure path is the *common* path — four of the five days in the recorded week ended in it.

**D0 branches.** The run refuses to advance until you say how the gates ended. Choosing *stand
aside* marks `SIZE`, `MAN` and `EXIT` struck-through and not-applicable in the rail and goes to the
review, with R51 cited: a day correctly stood aside is a record, not a blank. Choosing *taken*
continues to sizing.

## One state machine

`run = {i, done, view, aside}` drives the rail, the chart reveal, the step card, the caption, the
controls and the progress line. No second timer; nothing derived twice. The chart is static SVG with
per-step `<g data-mi>` layers toggled by class, so per-frame work is zero.

## Two defects found and fixed while building it

1. **Labels at the same price collided.** The guided views were first rendered once per step, so the
   gutter de-collided labels only *within* a step — and R4 range-high and R3 SMT-qualified-high are
   both `21,562.25`, in different steps. They printed on top of each other. Fixed by moving the step
   tag *inside* `svg_markup`, so all labels lay out in one global pass. Also made the pack 45% smaller
   (135KB → 74KB) by no longer re-rendering the bars per step.
2. **A referenced rule that is not shipped degrades silently to plain text.** `chip()` falls back to
   a bare string when a rule is missing, and R14 at M9 rendered as text rather than a chip with no
   error anywhere. The subset shipped 41 of 54 rules. **Now all 54 ship**, and the check asserts
   every declared rule on every step renders as a real chip.

## Verified over CDP

| Check | Result |
|---|---|
| All 19 steps walked | every step has a primitive, a rule set and a session note |
| Chart reveal tracks the step | shapes accumulate `[2] → [2,3] → [2,3,5] → …` and never run ahead |
| Artifact states | NOT-RECORDED and UNRESOLVED steps both carry a why-nothing-appears panel |
| Rule chips | every declared rule on every step renders as a chip; **0 bare `R##`** |
| Branch gate | Mark is disabled and labelled "Choose an outcome first" until answered |
| Stand-aside path | stays on D0 to explain, cites R51, marks SIZE/MAN/EXIT n/a, then goes to REV |
| Taken path | continues to SIZE, nothing marked n/a |
| Persistence | progress survives reload; reset clears state, view and revealed shapes |
| Horizontal overflow | none at 1280 (13,708px tall) or 400 (22,308px tall) |
| Console | no errors, no warnings |
| Reduced motion | all sections at full opacity, nothing hidden |
| Light + dark | both render |

## Still not done

- **The browser extension is not connected**, so this was verified through headless Chrome over the
  DevTools protocol rather than Paul's own browser. That is a stronger instrument for measurement
  (it reads `scrollWidth` rather than cropping a screenshot) but it is not his environment.
- **Not in the app.** `/runner` is still untouched; the port is still the remaining S1b work, and it
  is now a bigger port than it was this morning.
- **`impeccable`'s detector has not been run** over the finished page — the skill lists it as an
  optional additive static pass and it needs `htmlparser2`/`css-select`/`css-tree`/`domutils`
  installed to avoid a degraded regex fallback.

---

# Update — §06 Tools (2026-08-29)

Paul: *"Can you add more in app tools traders might want to know or asks a specific steps?"*

Six calculators, each implementing a rule that was otherwise just a sentence. They appear in the
standalone §06 **and** inside the guided run at the step that reaches for them
(`PRE → breakers`, `M5 → zone`, `M11 → stoprange, rr`, `D0 → zone, rr`,
`SIZE → size, breakers, rr`, `MAN/EXIT → fromhere`).

| Tool | Rules | What it makes operational |
|---|---|---|
| Position sizer | R39 R43 R33 | Sizes off **total capital, broker + savings** — not the broker balance. That is the trap R39 exists to name. |
| R:R + break-even win rate | R44 R32 | `1 ÷ (1 + R:R)`. Optional win-rate input computes R44's expectancy in full. |
| Where in the range | R5 R32 | Only 0 / 0.5 / 1. It will not print the 0.25 / 0.75 quadrants. |
| Risk from here | R45 | "Free trade" is a lie — recomputed from **current price**, never entry. |
| Is the stop too wide? | R34 R33 | Stop as a share of range, flagged over 25%. |
| Circuit breakers & drawdown | R40 R41 R42 R49 | **R42's computable test**: ten straight losses, compounded — over 20% means per-trade risk is too high. |

## Why this closes part of the measured gap

`risk-management.md` is the **largest page in the corpus** (3,411 words) and the guided run reduced
it to a single tick. **R38, R42, R44 and R46 were cited nowhere.** Three of the four are now
implemented rather than merely quoted; R38 and R46 remain uncovered.

## Verified — the strongest check available

Three tools **independently reproduce numbers the S1d engine published weeks ago**, from inputs
typed into the form rather than read from its output:

| Tool | Computes | Tracker published |
|---|---|---|
| R:R | **2.72 : 1** | "2.7R PLANNED" |
| Where in the range | **73.6%** | "PREMIUM, 0.74 of range" |
| Stop vs range | **27.0%** | "27% of the range, over the declared 25% flag" |
| Position sizer | **225.75 pts** | "risk 225.75 pts" |

Expectancy arithmetic checked at two points and is internally consistent with its own break-even:
`40% → +0.489R`, `20% → −0.255R`, break-even `26.9%` — the sign flips either side of it. With the
win-rate field blank the tool emits **five rows and no expectancy at all**.

Warnings fire only when they should: stop >25% (yes at 27.0%), one contract exceeding 1R, risk %
outside 1–2, wrong half of the range for the direction, daily stop outside 2–3R, and R42's ten-loss
test (**2.5% → −22.4% warns; 2.0% → −18.3% does not**).

`verify-tools.mjs` and `verify-expectancy.mjs` in this folder. No console errors; no horizontal
overflow.

## The honesty line these tools must not cross

They are **arithmetic on this page's own rulebook, not advice and not evidence.** The expectancy
tool is the one that could mislead, so it: only appears when *you* supply a win rate, prints the
formula it used, states that it assumes every win lands at target and every loss at stop, and says
explicitly that **no win rate has been established for this model**. It computes from your number;
it never supplies one.
