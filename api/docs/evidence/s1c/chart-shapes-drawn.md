# S1c — computed levels drawn on the chart (deliverable 3)

Drawn 2026-08-13 at Paul's explicit request onto **Tradezella session `831607`, NQ pane
(chart 0)**. Every shape carries its rule ID and an **`[S1c]`** suffix, so a level on this
chart can never be mistaken for a hand read.

> ## ⚠️ THESE ARE MACHINE-GENERATED
> They are the output of `api/scripts/aura_setup_engine.py`, not Paul's markup. They are
> **not** reps, not evidence, and must never feed the evidence layer. The `[S1c]` marker is
> on every label for exactly this reason. **Delete them before marking this day by hand** —
> pre-drawn levels would turn a markup rep into a tracing exercise.

## The record they depict

`2025-05-30 · NQ · bias SHORT` — the single setup from the 22-day run.

| Rule | Level | Shape | Colour (per `chart-markup.md` §Colour convention) |
|---|---:|---|---|
| R4 | 21,562.25 | range high | white |
| R4 | 20,727.00 | range low | white |
| R5 | 21,144.63 | equilibrium — entry sits at 0.74, in PREMIUM | grey, dashed |
| R3 | 21,562.25 | SMT-qualified high @ 05-20, ES/YM did NOT take | yellow |
| R33 | 21,567.50 | stop — risk 225.75 pts | red |
| R30 | 21,341.75 | entry — 5m iFVG retest 08:05 | green |
| R35 | 20,727.00 | target — 2.7R | green, dashed |
| R30 | 21,341.75–21,343.25 | the 5m iFVG itself | blue box |

R3 and R4-high coincide at 21,562.25, and R35 and R4-low coincide at 20,727.00 — that is
correct, not duplication: the qualifying swing **is** the range boundary, and the target
**is** the range extreme (R35).

## Verified at the consumer layer

Shapes were not trusted on creation. Each was read back through `getShapeById().getPoints()`
and `getProperties()`, and every price matched the engine's record exactly. `createShape`
returns a **Promise** in this build, so the returned value is useless as confirmation —
enumeration is the only honest check.

Final state: **8 shapes on NQ** (7 `horizontal_line` + 1 `rectangle`). ES / YM / CHFUSD panes
were not touched and carry **0** shapes.

**Persistence proved, not assumed:** after a full page navigation the NQ pane still returns
`8` shapes, all 8 still carrying `[S1c]`, with ES/YM/CHFUSD still at `0`. They are stored
server-side, matching the S1 probe finding.

Rendered capture: `chart-levels-drawn.jpg` (NQ 1h, 2025-05-17 → 05-31).

### Two things the rendered view showed that the API did not

1. **The EQ line snapped to the tick grid.** R5's equilibrium is a computed midpoint —
   `(21,562.25 + 20,727.00) / 2 = 21,144.625` — which is **not on NQ's 0.25 grid**. The chart
   renders it at **21,144.75**, one tick above. Harmless for reading premium-vs-discount, but
   worth knowing that a computed midpoint is the one level here that is *not* exactly where
   the arithmetic put it. The engine's own number remains 21,144.63; only the drawing snapped.
2. **Three labels overlap at the top of the pane.** R33 (21,567.50), R4-high and R3
   (both 21,562.25) sit within 5.25 points of each other, so their text collides at this zoom.
   The levels themselves are distinct and correct; only the labels are cramped. Zooming the
   price axis separates them.

## Shape IDs — to remove them

| Rule | ID |
|---|---|
| R4 range high | `HN3BMm` |
| R4 range low | `meBJ7b` |
| R5 EQ | `PsqPLq` |
| R3 SMT high | `OOIb9g` |
| R33 stop | `965Mm9` |
| R30 entry | `HexJJP` |
| R35 target | `nrlFBE` |
| R30 iFVG box | `inUTjd` |

Run this in the page console on the session to remove **only** these, leaving any of Paul's
own markup untouched:

```js
const f = [...document.querySelectorAll('iframe')]
  .find(f => { try { return f.contentWindow && f.contentWindow.tradingViewApi } catch (e) { return false } });
const c = f.contentWindow.tradingViewApi.chart(0);
['HN3BMm','meBJ7b','PsqPLq','OOIb9g','965Mm9','HexJJP','nrlFBE','inUTjd']
  .forEach(id => { try { c.removeEntity(id) } catch (e) {} });
c.getAllShapes().length;   // expect 0 if nothing else was drawn
```

Safer alternative if the IDs have rotated: delete by label instead — every shape this session
created has `[S1c]` in its `text`, and nothing else on the chart does.

```js
c.getAllShapes()
  .filter(s => ((c.getShapeById(s.id).getProperties().text) || '').includes('[S1c]'))
  .forEach(s => c.removeEntity(s.id));
```
