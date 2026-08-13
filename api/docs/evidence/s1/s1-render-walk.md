# S1 — the Aura session runner: probe result + render walk (2026-08-12)

The runner verified at the width it will actually be used at, and the Tradezella boundary probe that
gated its markup step. A green build is not a deployment check; this is the walk it cannot stand in for.

Stack under test: `docker compose` → `db` (:5433), `api` (:8001), `app` (:5174, built bundle behind
nginx). Account: `e2e` / `e2e-evidence` (fixtures). New route: `/runner`.

## Verdict

**PASS.** The runner is usable. Three defects were found during the walk and fixed; one pre-existing
defect was found, measured, and deliberately **not** fixed (see §The one thing left broken).

**The probe's answer is NO** — Tradezella's backtest chart takes no custom indicators, so the markup
step is a hand-drawing protocol, not a tooling spec.

---

## The boundary probe — run in the product, not inferred

| Question | Verdict | Basis |
|---|---|---|
| Custom / Pine indicators on the backtest chart? | **NO** | `Indicators` dialog is one flat list under a single `SCRIPT NAME` header — no Community Scripts tab, no My Scripts tab, no Pine editor. Discriminating search: `smt` → **"No indicators matched your criteria"**. |
| Vendor-authored studies? | **YES** | `session` → **"Sessions Indicator by Tradezella"**. The capability exists; it is not exposed to users. |
| Engine | **TradingView Advanced Charts library** | Built-in study names verbatim from the TV library (`Accumulative Swing Index`, `Arnaud Legoux Moving Average`, `Balance of Power`…); the TV symbol-settings dialog with `Template ▾` + `Apply to all`; the TV drawing toolbar; `auto`/`log`/`%` scale controls. Not `tradingview.com`, not an in-house engine. |
| Drawing tools | **YES — full TV toolbar** | Trend/horizontal lines, fibs, patterns, brush, text, emoji, measure, magnet, lock, hide, cross-chart link, delete-all. |
| Chart-settings template | **YES** | `Template ▾` in the settings dialog footer. |
| Data session / timezone | `Extended trading hours`, `(UTC-4) New York` | Read from the symbol-settings dialog on the live session. |
| Drawing persistence across replay steps / sessions | **NOT MEASURED** | Layout displays `Autosaved`, and lock/hide/delete-all only make sense for persistent drawings. **Evidence, not proof** — a clean before/after was not captured. Recorded as unverified. |

**What this kills.** `neurospect-app` shipped `public/neurospect-coach.pine`, which made Pine look like
a settled in-house capability. It does not work here. More sharply, **`rules.md` R23 cannot be
reproduced inside Tradezella** — R23 describes the Sequential-SMT *indicator* showing only
currently-valid signals, and there is no way to load that indicator. Every SMT read in a Tradezella
backtest is a hand read.

### Create-session click-path — walked, then abandoned without creating

`+ Create session` → `Backtest on your own` (vs `Automated backtest BETA`, which has Zella AI run
hundreds of trades and is not practice) → `Start from scratch` (vs `Pick a scenario`, which pins
someone else's span/symbols/playbook). Form fields: **Session name*** · Description · **Strategy**
(+ `Create new strategy`; warns *"No strategy selected · Add one to track consistency"*) · **Symbols***
(**max 5**) · **Start date*** / **End date*** (`MM/DD/YYYY hh:mm:ss`) · **Start balance***
(`5K/10K/25K/50K/100K/250K`, leverage 1:1). Cancelled — **nothing was created in Paul's account.**

### The rule instrument is richer than the tracker assumed

Strategy → `Rules` tab holds **named, drag-reorderable rule groups** of free-text rules, and reports
per rule: **Follow rate · Net profit/loss · Profit factor · Win rate**. Orders carry
**`Rules followed` (X / N)** and **`Tags`**.

**`0 / 0` is a discriminating read.** `AMD Playbook` already carries **10 rules across 2 groups** (and
0 trades); `Macro Model` — the playbook holding the one real trade — reports `Rules followed 0 / 0` on
all five orders. A zero *denominator* means no rules were attached to that trade, so B1's `ZERO` was a
zero from an instrument with nothing to measure against — a **NOT-RECORDED**, not a `ZERO`.

### A finding about Paul's existing setup

The live session `NQ Macro Po3 - Asia Session` uses symbols **`NQ`, `MNQ`, `ES`, `MES`**. `MNQ` and
`MES` are the **micro contracts** of `NQ` and `ES` — the same instruments at a different multiplier.
Two of four panes are duplicates and a divergence between `NQ` and `MNQ` is impossible by
construction, so the confirmation engine (R18) has nothing to read. Correct set: **`NQ` `ES` `YM` `6S`**
(4 of the 5 allowed). The runner now prints this correction beside the copyable symbol list.

Corroboration of B1's measurement, incidentally: the sessions list reads **2 sessions · 1 trade ·
`Time invested 8m`** — exactly the `2 sessions, 1 trade, 8 minutes` the council recorded.

---

## The render walk — narrow viewport first

Driven by `app/e2e/runner.spec.ts` (**9 tests**), so it is reproducible rather than a one-off
eyeballing. Screenshots in this folder, animations frozen.

**The load-bearing assertion is not "the text is present" but "the page body does not scroll
sideways at 400px"** — `documentElement.scrollWidth - clientWidth <= 0`, asserted at **400 / 620 /
1280** and again on every reference tab, because a runner that only works maximised has failed its
only job and every screenshot at 1568px would still look fine.

| # | Artifact | What it shows |
|---|---|---|
| 01 | `01-declare-{narrow-400,docked-620,wide-1280}.png` | The declaration panel at all three widths; no horizontal overflow at any. |
| 02 | `02-declared-narrow-400.png` | Span → session name + both dates in Tradezella's own format + the symbol correction. |
| 03 | `03-phases-ticked-narrow-400.png` | All 8 phases, per-phase scope badges, hard-gate styling, rule chips, a tick moving `0/5 → 1/5`. |
| 04 | `04-rule-popover-narrow-400.png` | `R54` opening the canonical wiki text **with its hedge intact** — *"Preserved as stated — not hardened."* |
| 05 | `05-open-flags-narrow-400.png` | `rules.md` §Divergences rendered as flags, asserted to contain **zero** checkboxes. |
| 06 | `06-stood-aside-narrow-400.png` | A stood-aside day counting — `0 replayed days` → `1 replayed day counted · 1 stood aside`. |
| 07–10 | `07-tab-setup` · `08-tab-markup` · `09-tab-playbook` · `10-tab-card` | The three authored wiki pages + the per-trade card; wide tables scrolling in their own box. |
| 11 | `11-no-api-traffic-narrow-400.png` | The protocol painting with **zero `/api` requests** recorded. |
| 12 | `12-auth-shell-logs-you-out.png` | The honest negative — see below. |

### Three defects the rendered surface caught

1. **The paste block vanished exactly when it was needed.** Entering the start date flipped the Run
   tab from the declaration panel to the protocol, which collapsed the Tradezella name/date/symbol
   block into a `<details>` — at the precise moment you go and create the session. Extracted into
   `TradezellaPaste` and kept on screen across the transition.
2. **R54 was unreachable.** Phase-level `[R##]` refs were parsed but never rendered (item-level ones
   were). R54 — environment and health as performance inputs — appears **only** in phase 0's heading,
   so it existed in the projection and nowhere in the product. Now rendered as a `Phase rules` row
   inside the collapsible body (not the trigger — a button cannot nest in a button).
3. **Prose rendered as a ransom note.** The projection emitted one paragraph per **physical source
   line**, and the wiki hard-wraps at ~100 columns — so the reference tabs were a column of orphaned
   half-sentences at 400px. Fixed in `_sections()` (join across lines, break on blank lines and
   structural elements) and guarded by a test that fails if the longest paragraph is under 160 chars.

A fourth issue was a **bad artifact, not a bad product**: `TabsTrigger` carries `transition-all` and
`page.screenshot()` defaults to `animations: 'allow'`, so the first captures caught the tab highlight
mid-transition and showed the *previous* tab as selected beside the new tab's content. The DOM was
correct throughout (`aria-selected` is now asserted). Every capture freezes animations.

### The one thing left broken, on purpose

**`app/src/lib/auth.ts:50-53` clears the stored token on ANY `auth/me` failure — network errors
included.** It cannot distinguish "this token is invalid" from "the server is unreachable", so an API
blip, a container restart or a slept laptop **logs you out and discards the session**.

This is pre-existing, wider than the runner, and security-adjacent, so S1 documents rather than
changes it. It matters here because it bounds a claim: the runner's *content* needs no API (asserted —
zero `/api` requests), but the runner is **not** usable offline, because the shell's auth gate is not.
The fix is to clear the token only on a real 401/403 and leave it alone on a transport failure —
flagged in the tracker for Paul's approval, not applied.

### Interactions: which respond, which are inert

Exercised and recorded, because a silent no-op is a finding:

- Span buttons (`1 week` … `1 year`) — **respond**; the replayed-day estimate updates.
- Start date → session name, both Tradezella dates, symbols — **respond**.
- Copy buttons on each paste row — **render and are clickable**; the clipboard write itself was
  **not asserted** (headless clipboard permissions), so treat as **unverified**, not "works".
- Phase expand/collapse, item checkboxes, `0/5 → 1/5` counters — **respond**.
- Rule chips → popover with canonical text — **respond**.
- Day `←`/`→`, `Mark day done`, `Stood aside`, `+ setup`, setup selector — **respond**.
- Tab switching across all five tabs — **responds**, `aria-selected` asserted.
- `Reset runner` — **renders**; deliberately **not clicked** (it clears state behind a `confirm()`).

## No regression

- **Full Playwright suite: 77 passed** (68 pre-existing + 9 new), against the local stack — on **two of
  three** full runs. The other run failed **one** test, and a *different* one each time
  (`planner.spec.ts::regenerate bumps plan_version`, then
  `honesty.spec.ts::no signal paints a tick…`), each passing in isolation immediately afterwards
  (planner 5/5, honesty 11/11) and in the subsequent clean full run. That signature — different victim
  per run, clean in isolation, clean on re-run — is the **pre-existing parallel-load flake** the E6 log
  already records ("a one-off `gate.spec.ts` failure under parallel load that passed 7/7 in isolation");
  it has still **never been diagnosed**, and this session did not diagnose it either. Reported rather
  than rounded up to a clean sweep.
- `tsc -b` + `vite build` clean.
- **No backend code changed.** The only API-side addition is `scripts/project_aura_runner.py`, which
  is not imported by the app or by any test, so the 294-test backend suite is unchanged and was not
  re-run.
- **No migration, no new table, no mutating endpoint.** S1 writes nothing to the database; runner step
  state is `localStorage` only.
- `app/tsconfig.app.json` gained `resolveJsonModule: true` so the bundle can import the projection.

## Residue

None in the database beyond the existing fixture users the e2e suite already used. Nothing was created
in Paul's Tradezella account — the create-session form was walked and abandoned.

**Left in Paul's Tradezella session: NOTHING — checked 2026-08-12, and the earlier warning was wrong.**
The S1 walk flagged that a horizontal-line tool had been selected and clicked once on the `NQ` pane, so
a stray line *might* exist. Enumerated through the chart's own API
(`tradingViewApi.chart(0).getAllShapes()`): **99 shapes, of which 94 rectangles, 3 vertical lines and 2
trend lines — and zero horizontal-line-like shapes of any kind.** The click never created anything. The
99 are Paul's own pre-existing markup, and `MNQ` / `ES` / `MES` carry zero shapes each.

Recorded as a correction rather than quietly dropped: the original flag was appropriately cautious, and
it turned out to be a false alarm once measured.

## Closed after the walk (2026-08-12) — the playbook, and the last unmeasured probe question

- **The Aura playbook is built and saved.** `Aura - Sequential SMT (NQ triad)` — 6 groups, **33 rules**,
  every rule on the `Always` outcome filter. Verified at the **rendered** layer on the strategy's Rules
  tab, not merely reported saved: all 33 rule strings and all 6 group headings read back from the DOM.
  Two rules were added over the original mapping after re-reading the underlying concept pages — **R22**
  (targeting: SMT between two segments implies that segment's extreme is taken) and **R7** (range
  lifecycle) — plus **R23** (read the *current* SMT state; a hand read here, since the probe proved no
  indicator can exist).
- **Drawing persistence — MEASURED, both halves.** Across a replay step: **99 shapes → 99 shapes**.
  Across sessions: the same 99 present after a fresh navigation to the session URL, so they are stored
  server-side. This closes the one probe question S1 recorded as unverified.
- **Engine identity upgraded from inferred to proven.** The chart is a `blob:` iframe exposing
  `TradingViewApi` / `chartWidget` / `ChartApiInstance`, and `tradingViewApi.chart(i)` answers to the
  documented Charting Library surface. S1 inferred this from UI evidence; it is now direct.
- **Automation technique that finally worked**, written up in
  `~/.claude/skills/web-automation/claude-in-chrome-driving.md`: the save button ignored synthetic
  events, ref-clicks, coordinate clicks and keyboard activation, and fired only when React's own
  `onClick` prop was invoked from the element's `__reactProps$` key.

## Not covered, and not claimed
- The `Mistakes`, `Rating` and `Reviewed` fields the tracker assumed — **never observed** in the
  backtesting order surface; only `Rules followed` and `Tags` were seen.
- How a **missed trade** is logged from inside a backtesting session. The Strategies list has a
  `Missed trades` column, so the concept exists; the path was not found.
- The `Notebook` and strategy `Notes` field shapes; the `Templates` and `Backtest Scenarios` tabs.
- Whether the runner is followable **in anger**. Nine passing tests say the surface works. Only Paul
  running a real replayed day says the protocol does.
