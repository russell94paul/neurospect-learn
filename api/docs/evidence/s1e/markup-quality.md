# S1e deliverable 0 — markup quality, measured at the rendered layer

**Date:** 2026-08-14 · **Session:** `831607` · **Engine:** unchanged (`S1d.1`) · Nothing redrawn,
nothing deleted, no geometry altered. All 33 `[S1d]` shapes intact throughout.

> Paul, 2026-08-14: *"The chart mark ups being high quality and accurate is paramount."*

Accuracy was already proved by coordinate readback in S1d. This document is about the half that had
**never been looked at**: what the markup actually looks like on screen.

---

## ⭐ The blocking item, and why three phases were blocked by a wrong diagnosis

The tracker recorded that `Page.captureScreenshot` "times out (30 s, renderer may be frozen)" and
concluded CDP was broken on this page. S1c and S1d both worked around it, and every visual claim in
both phases rested on coordinates rather than an image.

**That diagnosis was wrong.** Measured this session:

| Symptom | Measurement |
|---|---|
| `document.visibilityState` | **`hidden`** |
| Canvas backing stores | **300×150** — the browser default, never sized |
| Non-transparent pixels sampled | **0**, across every canvas |
| Series data at the same moment | **391 bars loaded**, `05-30 14:29 → 20:59 UTC` |

The page was hidden — the Chrome window minimised or fully occluded — so Chrome throttled it and
TradingView never painted. **There were no pixels to capture.** CDP was not broken and no
alternative screenshot API was needed. Restoring the window on screen makes the canvases jump to
`1542×352` with real content, and screenshots succeed immediately.

**`api.takeScreenshot()` does exist** on the widget, but it was deliberately not used: it publishes
the chart image to a snapshot server, which is an outward-facing action. The local route is
sufficient.

### The trap this leaves behind, which caught this session mid-work

Rendering stops whenever the window is occluded — **focus is irrelevant** (`hasFocus: false` renders
fine; `hasFocus: true` while minimised does not). When the window is hidden the capture tool returns
a **stale frame with no error**.

This was caught in the act: hiding **all 33 shapes** produced *zero* change in the canvas pixel
hash, and two consecutive captures across a style change were pixel-identical.

**Guard, now mandatory before trusting any image:**

```js
// prove the renderer is live: change something, confirm the pixels move
const h0 = hashCanvases();
shape.setProperties({ visible: false }); await wait(1000);
const h1 = hashCanvases();            // h0 !== h1  =>  renderer is live
shape.setProperties({ visible: true });
```

Same failure class as the coordinate clamp and the ignored override keys: **an operation that
succeeds, reports success, and gives a wrong result.** That is now four instances in this project.

---

## ⭐ The override keys — measured with a throwaway probe, not recalled

A probe shape of each type was created with a bag containing every candidate key and both casings,
its properties read back, and the shape removed (verified back to exactly 33).

| Shape | Keys **honoured** | Keys **silently dropped** |
|---|---|---|
| `rectangle` | `color`, `backgroundColor`, `transparency`, `linewidth`, `linestyle`, **`textColor`**, **`fontSize`**, `fillBackground` | `linecolor`, **`showLabel`**, `textcolor`, `fontsize` |
| `trend_line` / `ray` | `linecolor`, `linewidth`, `linestyle`, **`textcolor`**, **`fontsize`** | `color`, `backgroundColor`, `transparency`, **`showLabel`**, `textColor`, `fontSize`, `fillBackground` |

### Three corrections to what the boot prompt assumed

1. **The colours DID apply.** The prompt's stated likely cause of poor appearance — overrides
   silently ignored — is wrong for colour. S1d passed one bag containing *both* casings, so each
   shape type picked up its own variant. The readback confirms `#ffffff` boundaries, `#9e9e9e`
   zones, `#ffeb3b` SMT swings, `#2196f3` gaps. The colour convention was on the chart all along.
2. **⛔ `showLabel` does not exist on any of these shapes.** The prompt's own proposed fix — *"set
   `showLabel:false` on the context gaps"* — **would have silently done nothing**, which is the
   exact failure mode it was written to prevent. The working mechanism is **`text: ''`**, verified.
3. **The flat 1px look was not a dropped key — nothing was ever asked for.** `linewidth` and
   `linestyle` are honoured on every shape type, yet all 33 shapes carried `linewidth: 1,
   linestyle: 0`. `chart-shapes-spec.json` records **only a `colour` field per shape** — no width,
   no style, no transparency, no label policy, no z-order. The visual hierarchy was improvised in
   the console at draw time and never specified anywhere.

### Two further findings

- **`createMultipointShape`'s return value is not a usable shape handle.** `getShapeById()` on it
  throws *"There is no such shape"*, while `getAllShapes()` finds the shape fine. S1c established
  the return value *proves* nothing; it cannot even *address* the shape.
- **`isAutoScale` was `false`** — a persisted chart state. The 60m view rendered candles as vertical
  streaks with the HTF shapes entirely off-scale. S1d drew its markup under this condition, which
  alone would have made the result look broken regardless of the shapes.

### The real property vocabulary (read from the chart, not from memory)

```
rectangle           backgroundColor, bold, color, extendLeft, extendRight, fillBackground,
                    fontSize, frozen, horzLabelsAlign, italic, linestyle, linewidth, middleLine,
                    text, textColor, transparency, vertLabelsAlign, visible
trend_line / ray    alwaysShowStats, bold, extendLeft, extendRight, fontsize, frozen,
                    horzLabelsAlign, italic, leftEnd, linecolor, linestyle, linewidth, rightEnd,
                    showAngle, showBarsRange, showDateTimeRange, showDistance, showMiddlePoint,
                    showPercentPriceRange, showPipsPriceRange, showPriceLabels, showPriceRange,
                    statsPosition, text, textcolor, vertLabelsAlign, visible
```

**Z-order is directly settable** — `sendToBack` / `bringToFront` exist on both the chart and each
shape — so hierarchy does not require redrawing in a particular order.

---

## The hierarchy applied (in place — no geometry touched, nothing deleted)

| Tier | Objects | Encoding | Label |
|---|---|---|---|
| Recede | R5 premium/discount zones (4), equilibrium (2) | grey, **transparency 92**, 1px, dashed/dotted, **sent to back** | cleared |
| Context | 14 non-traded iFVG/NDOG gaps, R12 liquidity | blue, **transparency 90**, 1px, **sent to back** | cleared |
| Structural | R4 range boundaries (4), R6 invalidating close | white / red, **2px**, solid (R6 dashed) | kept |
| Filter | R3 SMT-qualified swings (2) | yellow, **3px**, solid, **brought to front** | kept |
| Execution | R30 entry, R33 stop, R35 target, traded iFVG | 2px, target dashed, **brought to front** | kept |

**Labels: 33 → 11.** Verified per shape: **0 style drift across all 33.**

## Verification performed

| Check | Result |
|---|---|
| Renderer proved live before each trusted capture | ✅ pixel-hash changes when a shape is hidden |
| Per-shape style readback vs intent | ✅ **0 drift / 33** |
| Label count after suppression | ✅ 11, enumerated |
| Shape count unchanged throughout | ✅ 33 → 33 |
| Probe shapes removed | ✅ verified back to 33 |
| All shapes `visible: true` at end | ✅ 33 / 33 |
| Replay position | ✅ **untouched — 2025-05-30 20:59 UTC**, confirmed from loaded bars |
| Shape ids snapshotted before label text was cleared | ✅ scoped removal no longer depends on label text |

## ⚠️ Still unresolved — do not record these as done

1. **Label collision is applied but UNSEEN.** `horzLabelsAlign` / `vertLabelsAlign` were set with
   0 property drift, but the capture that would have judged them was the stale frame. Unverified at
   the rendered layer.
2. **The LTF view is vertically squashed.** Auto-scale must span entry (21,341.75) to target
   (20,727.00), compressing the 5m price action into ~15% of the pane. Honest, but hard to read.
3. **The traded gap's label sits away from its box** under `horzLabelsAlign: 'left'`.
4. **Density is judged on one entry.** Whether this hierarchy survives a chart with several entries
   is untested, and that is the case S1e actually needs.

## Images

`markup-before/` — all captured with the renderer proved live:

| File | What it shows |
|---|---|
| `01-ltf-5m-as-drawn.jpg` | LTF **before** — 15 competing labels over 8px boxes |
| `02-htf-60m-pricescale-locked.jpg` | the `isAutoScale: false` failure |
| `03-htf-60m-autoscale-restored.jpg` | HTF **before**, scale fixed |
| `04-htf-60m-AFTER-restyle.jpg` | HTF **after** |
| `05-ltf-5m-AFTER-restyle.jpg` | LTF **after** |
