# B3-local — render walk + persistence proof (2026-08-12)

The local Docker daily driver, verified at the **rendered surface**. A green health check is not a
deployment check; this document is the walk that a health check cannot stand in for.

Stack under test: `docker-compose.yml` → `db` (:5433, shared with the dev stack), `api` (:8001),
`app` (:5174, built bundle behind nginx). Account used: `e2e-evidence` (a fixture — see §Residue).

## Verdict

**PASS**, with one defect found and fixed during the walk. All eight pages paint. The persistence
claim the stack is built on is now proven rather than asserted.

## The defect the walk found: a healthcheck that had failed 1350 times

`app` had been reporting `unhealthy` for its entire 4-hour life while **serving correctly**.

- **Symptom:** `wget: can't connect to remote host: Connection refused`, `FailingStreak: 1350`,
  while `http://localhost:5174/` returned `HTTP 200` from the host the whole time.
- **Discriminating test** (predicted before running): in-container `wget http://localhost/` →
  refused; `wget http://127.0.0.1/` → **SUCCESS**. `netstat` shows exactly one listening socket,
  `0.0.0.0:80` — no `::`-bound socket at all. musl resolves `localhost` to `::1` first, so the check
  dialled an address nothing was listening on.
- **Fix, and why it went in the Dockerfile rather than nginx.conf:** the tempting repair is
  `listen [::]:80;` in `nginx.conf`. That would have been **worse than the bug** — this container has
  no IPv6 stack, so nginx would fail to bind and refuse to start, converting a cosmetic false alarm
  into a real outage. The check was what was wrong, so the check is what changed.
- **After:** `healthy`, `FailingStreak: 0`, last five probes all exit `0`; on a later forced recreate
  `app` reached `healthy` in **7 seconds**.

Why it mattered even though the site was fine: nothing could ever gate on `app` being healthy
(compose's own `condition: service_healthy` included), and a permanently-red status trains you to
stop reading health output.

## Every page painted

Navigated by **direct URL**, not by clicking the nav — that also exercises the nginx SPA fallback in
`app/nginx.conf`, which is the thing that stops a refresh on `/journal` (or the Discord
`/auth/callback`) from 404ing. All eight deep links resolved.

| Page | Artifact | Painted | Notes |
|---|---|---|---|
| `/today` | `01-today-honesty-strip.jpg` | ✅ | E6 honesty strip live: *"7 days marked done carry no evidence at all… the figure above it is a record and the one at the top is a claim."* Adherence 13%, 7 done / 49 pending. |
| `/path` | `02-path.jpg` | ✅ | Three tracks (Aura / AXL / Unified); A0 open, A1–A6 `Locked`. |
| `/library` | `03-library-67-pages.jpg` | ✅ | **"67 pages"** — matches the seed anchor at the consumer's layer. |
| `/drills` | `04-drills-58-drills.jpg` | ✅ | **"58 drills"** — matches the seed anchor. |
| `/plan` | `05-plan.jpg` | ✅ | August calendar; past frozen, future projected; legend renders. |
| `/journal` | `06-journal.jpg` | ✅ | 42 backtest entries, filters render. |
| `/expectancy` | `07-expectancy.jpg` | ✅ | **Explained** empty state, not a blank: *"42 entries logged, none closed yet — expectancy appears once trades carry a realized R."* |
| `/gate` | `08-gate.jpg` | ✅ | *"No model is cleared to live yet. Every requirement below is earned, not declared — the gate cannot be overridden."* Per-model requirement lists render. |

**Seed anchored at the rendered layer, not just in SQL.** `alembic_version` = `0012`, and
`concepts=74 · track_stages=23 · drills=58 · content_pages=67 · rubrics=44 · rubric_items=104` —
all six match the tracker exactly. Library and Drills print 67 and 58 *on the page*, which is the
source==consumer check rather than an inference from matching values.

**The bundle talks to the right API.** `grep` over the served bundle finds `localhost:8001` twice and
`localhost:8000` **zero** times, so the `VITE_API_URL` build-arg mechanism worked. Had it been passed
as compose `environment:` instead, Vite would have silently baked the `:8000` default and the daily
driver would have been reading the dev API. Login confirmed it live: `OPTIONS 200` → `POST 200` on
`/auth/debug/token`, then `/auth/me` and `/api/tracks` both `200`.

## The persistence proof — the one test this phase exists for

`docker-compose.yml` claims *"This is why R2 is not needed locally: nothing here is ephemeral."*
That is the local analogue of the Render/R2 redeploy test, and it was previously **asserted, never
run**. Run now, end to end:

1. **Before** — `aura D1-a`: `0 / 50 reps · 0 evidenced`, empty capture zone
   (`09-persist-BEFORE-0of50-no-capture.jpg`).
2. **Upload** a labelled capture through the real UI on :5174 →
   `1 / 50 reps · 1 evidenced`, `1 captured · 1 reps · 1 awaiting your check`, thumbnail renders
   (`10-persist-AFTER-upload-1of50-thumbnail.jpg`). Row written:
   `storage_key = 505c7126-…/evidence/drill/aura-d1-a/306a39c7-….png`, `byte_size = 14192`,
   `reps_claimed = 1`.
3. **Destroy and recreate both containers** — `docker compose up -d --force-recreate api app`.
4. **After** — the blob is still on the bind mount (`14192` bytes) and the thumbnail **still renders**
   with the rep intact (`11-persist-AFTER-container-recreate-still-renders.jpg`), zoomed to prove it
   is the real image and not a broken-image placeholder
   (`12-persist-thumbnail-zoom-real-image.png`).

This is the failure mode that made R2 non-optional on Render: there, the blob would have been deleted
while the `evidence_assets` row survived, leaving a rep derived from evidence that no longer exists,
with nothing raising. Locally the host bind mount (`./.evidence-store:/evidence`) is what prevents it,
and it now has a rendered before/after rather than a structural argument.

En route it also exercised two enforcement invariants at the rendered layer: the capture **derived**
the rep (E2 — nothing minted it), and the rep **counts while unchecked** — *"not checked yet — the
reps still count"* (E3).

## Interactions: which respond, which are inert

Recorded because a silent no-op is a finding, not an acceptable default. Exercised:

- Track switcher on `/path` (Aura / AXL / Unified) — **responds**.
- `/journal` tab switch (Trades taken ↔ Missed & canceled) and the three filters — **render**;
  filtering was not driven to a result, so treat as **unverified**, not "works".
- `/plan` month arrows and `Regenerate` — **render**; not clicked (`Regenerate` mutates the plan).
- File-input capture on `/drills` — **responds**, proven above.
- `Check against the bar` — **renders**; deliberately not clicked, so the E3 grade path is
  **unverified at the UI** in this walk.

**Not covered by this walk, and not claimed:** the Discord OAuth login (the local stack runs
`DEBUG=true`, so debug login is the door and the allowlist admits everyone by design — the
fail-closed behaviour that matters is a `DEBUG=false` property and belongs to the hosted path);
`AI_GRADING_ENABLED=false`, so the E4 second reader was not exercised; and nothing here tests the
Render deployment, which remains written, proven-in-config and unprovisioned.

## Residue this walk left in the local DB

One real evidence asset and one derived rep on the **fixture** account `e2e-evidence`, drill
`aura D1-a`: asset `83859b1b-1bb7-4e43-ac98-f1f4b8e1c38a`, `1 rep`, awaiting check. Left in place
deliberately — E5/E2 semantics mean evidence is not retractable, and deleting it by hand would be a
worse precedent than a documented fixture rep. The uploaded image is
`b3-local-persistence-test-capture.png` in this folder and is labelled as a synthetic test capture.

## Not re-run

The only source change in this session is the `HEALTHCHECK` line in `app/Dockerfile`, which no Python
test observes, so the 294-test backend suite was **not re-run** and is unchanged from the B3 session's
measurement.
