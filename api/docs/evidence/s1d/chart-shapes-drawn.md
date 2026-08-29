# S1d — bounded markup drawn on session `831607`

**33 shapes on the NQ pane**, all bounded (rectangles / rays / bounded segments), each
labelled with its rule ID and an `[S1d]` marker. **Zero `horizontal_line`.**

> ## ⚠️ MACHINE-GENERATED — DELETE BEFORE MARKING THIS WEEK BY HAND
> These are computed tutorial levels, not Paul's reads. Pre-drawn levels turn a markup
> rep into a tracing exercise, so **run the removal snippet below before you mark
> 2025-05-26 → 05-30 yourself.** Removal has been tested in this session (33 → 0).
> They are left in place *only* so the read can be reviewed first, which is the whole
> point of S1d's worked-examples-first ordering.

---

## What Paul rejected, and what changed

S1c drew its computed levels as **infinite horizontal lines**. Paul rejected that
outright — *"you drew horizontal lines across the whole chart, not just in the area
where the FVG was."* He was right for a structural reason, now canonical in
[[concepts/mastery/aura/chart-markup]] §0b: an infinite line asserts *"this level
applies at all times"*, which **contradicts R6** (a range dies at a close beyond it)
and **R7** (follow the current range only until the next Sequential SMT).

Every shape below therefore carries a computed **start and end**:

| Object | Primitive | Time extent | Count |
|---|---|---|---:|
| Range boundary, dead (R4/R6) | bounded segment | anchoring pivot → **the invalidating close** | 2 |
| Range boundary, live (R4) | ray | anchoring pivot → current data edge | 2 |
| Discount / premium (R5) | rectangle | the range's span | 4 |
| Equilibrium (R5) | bounded segment | the range's span | 2 |
| SMT-qualified swing (R3) | bounded segment | pivot → the bar that swept it | 2 |
| Invalidating close (R6) | bounded segment | the killing close, marked | 1 |
| PD arrays — iFVG / NDOG (R11) | rectangle | inversion/formation → mitigation | 15 |
| Liquidity inside the gap (R12) | bounded segment | the gap's own extent | 1 |
| Entry / stop / target (R30/R33/R35) | bounded segment | the trade's lifetime | 3 |
| Invalidation note (R29) | bounded segment + text | the trade's lifetime | 1 |

The engine emits a `chart-shapes-spec.json` with both endpoints per shape, and
`shape()` now **raises** on a non-increasing time extent — see §The two defects.

---

## ⭐ The two defects this pass found, both of which produced confident-looking output

### 1. Rectangles whose end preceded their start (15 of them)

`attach_mitigation` searched forward from the **original FVG formation**. For an
**iFVG**, inversion *is* price closing through the zone — so the search found the
inverting move itself and reported the gap mitigated **before it inverted**. Every
iFVG box came out with `t2 < t1`.

Nothing downstream would have objected. The chart would simply have drawn something
wrong. Caught only by printing the emitted coordinates and reading them.

- **Fix:** anchor the search at `max(formed_time, inverted_time)`.
- **Guard:** `shape()` raises `ValueError` on a non-increasing extent, so this class of
  bug cannot ship rather than merely being unlikely.

### 2. ⭐⭐ The chart SILENTLY CLAMPS shape coordinates to the loaded data window

This is the more dangerous one, and it is a new instance of S1c's lesson.

The first drawing pass ran with the chart on **1m**, whose loaded series covered only
`2025-05-22 20:00 → 05-30 16:59`. Shapes whose computed extent fell outside that window
were **silently clamped**:

- the 7 HTF shapes for the dead range (`04-30 → 05-12`) collapsed to **zero width**,
  both endpoints pinned to the first loaded 1m bar;
- the 6 live-range shapes were clamped at both ends.

**Every success signal passed.** `createMultipointShape` threw nothing. The promise
resolved. `getAllShapes()` returned the right **count** (33). A screenshot would have
looked broadly plausible. 13 of 33 shapes were wrong.

Only a **per-shape comparison of requested vs read-back coordinates** caught it.
Counting is not verifying — S1c already established that `createShape`'s return value
proves nothing; this adds that *enumeration by count* proves nothing either.

**Root cause is real, not a glitch:** one chart resolution cannot faithfully hold both a
month-long range and a five-minute gap box. The fix follows R27's own cascade:

| Set | Drawn at | Loaded span | Snap error |
|---|---|---|---|
| 13 HTF shapes (ranges, zones, SMT swings, invalidating close) | **60m** | 04-25 → 05-30 | **−30 min** (daily bars stamp 13:30 UTC; nearest 60m bar is 13:00) |
| 20 LTF shapes (iFVG, NDOG, liquidity, entry/stop/target) | **5m** | 05-28 → 05-30 | **0 min** (exact bar matches) |

The live rays' ends snap −480 min because the computed end lies past the data edge; that
is the **intended** behaviour for a still-live level (§0b: *"if still live, to the
current edge only"*), recorded rather than hidden.

---

## Verification — what was actually proved

| Check | Result |
|---|---|
| Baseline before drawing | **0** shapes on all four panes |
| Requested vs read-back coordinates, HTF set | **0 drift** across 13 shapes |
| Requested vs read-back coordinates, LTF set | **0 drift** across 20 shapes |
| HTF geometry re-checked after switching 60m → 5m | **0 drift** (resolution change does not re-clamp) |
| `horizontal_line` present | **0** — enumerated, not assumed |
| Every shape carries the `[S1d]` marker | **true**, checked per shape |
| Other panes (ES / CHFUSD / YM) | **0** shapes — nothing drawn where it should not be |
| Persistence across a full page navigation | **33 → 33**, all still marked |
| Removal | tested this session: **33 → 0** |

⚠️ **Screenshots time out on this page** (`Page.captureScreenshot` 30 s, "renderer may be
frozen") while the DOM and chart API answer instantly — the documented failure mode. Not
retried. The coordinate readback above is stronger evidence than an image, because an
image cannot show that a box's end precedes its start.

⚠️ **S1c's tick-grid observation did not reproduce at the API layer.** S1c recorded that
R5's equilibrium `21,144.625` (not on NQ's 0.25 grid) was snapped by the chart to
`21,144.75`. Read back through `getPoints()` the drawn value is **exactly
`21144.625`**. So either that snap was a rendering/display effect rather than a stored
one, or the two passes differ. Flagged rather than restated as fact.

---

## Chart state left behind

| | |
|---|---|
| Resolution | **5m** — changed from the `1m` it was found at. 5m is R30's entry cycle and the resolution the LTF markup reads at. |
| Visible range | parked on the 05-30 entry session |
| Replay position | **untouched** — still 2025-05-30 20:59 UTC. No advance, no orders, no playbook edits. |
| Shapes | **33 on NQ**, 0 elsewhere |

---

## Removal snippet — scoped, deletes only `[S1d]` shapes

Paste in the browser console on the session page. It removes **only** shapes whose label
starts with `[S1d]`, so nothing of Paul's is touched. It **discovers the iframe** rather
than hardcoding its id — the id changes between page loads (`tradingview_a53ee` became
`tradingview_34d9e` after one navigation), so a hardcoded id silently matches nothing.

```js
(() => {
  const f = [...document.querySelectorAll('iframe')]
    .find(x => x.contentWindow && x.contentWindow.tradingViewApi);
  if (!f) return 'chart api not found';
  const api = f.contentWindow.tradingViewApi;
  let removed = 0, kept = 0;
  for (let i = 0; i < 4; i++) {
    const c = api.chart(i);
    for (const s of c.getAllShapes()) {
      const t = (c.getShapeById(s.id).getProperties().text || '');
      if (t.startsWith('[S1d]')) { c.removeEntity(s.id); removed++; } else { kept++; }
    }
  }
  const left = [0,1,2,3].map(i => api.chart(i).getAllShapes().length);
  return { removed, keptNotMine: kept, shapesRemainingPerPane: left };
})()
```

Expect `{ removed: 33, keptNotMine: 0, shapesRemainingPerPane: [0,0,0,0] }`.
**Re-run it after a page reload and confirm the count is still 0** — these shapes are
stored server-side, so a local removal that has not persisted would reappear.

To redraw later, the full spec with both endpoints per shape is in
`chart-shapes-spec.json` (`draw` array — 33 de-duplicated shapes, each carrying the days
it applies to).
