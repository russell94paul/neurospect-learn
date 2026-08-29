# UI system — visual overhaul, landing page, settings (2026-08-20)

Brand system, dark mode, motion layer, semantic-token sweep, public landing page
and a Settings section. Screenshots in this folder are the rendered artifacts.

## What shipped

| | |
|---|---|
| Brand | NeuroSpect cyan `#06b6d4` / violet `#8b5cf6` on `#020617`, **dark-first**, light via toggle. Palette ported from the suite marketing site (`repos/neurospect/neurospect-ui/ns-styles.css`) rather than invented. |
| Design system | 4 runtime axes on `<html>` — `.dark` · `data-brand` (5 presets) · `data-density` · `data-font`, plus `--radius` inline. Settings → Appearance drives all of them, persisted to `localStorage`. |
| Motion | `tw-animate-css` installed; `data-motion` gates `system \| full \| subtle \| none`. |
| Landing | New public `/` with the full feature overview; signed-in visitors still redirect into the app. |
| Settings | `/settings` — Appearance · Motion · Study · Account. `/plan/setup` now serves the Study tab. |
| Sweep | 166 hard-coded palette classes across 25 files promoted to semantic tokens. |

## Three defects found and fixed on the way

1. **Dark mode was built but unreachable.** The `.dark` token block and ~30 components' `dark:`
   variants existed; nothing ever wrote `dark` onto `<html>`.
2. **Every Radix overlay animated nothing.** Six primitives carried `animate-in` classes from
   `tailwindcss-animate`, which was never installed — 16 dead class sites.
3. **The favicon was Vite starter residue**, not a NeuroSpect asset. Replaced, along with
   `App.css`, `assets/*` and `icons.svg` (all unreferenced).

Also fixed, all latent until the dark re-skin: `--card` was identical to `--background`
(every Card would have been invisible on near-black); `--radius-sm: calc(var(--radius) - 4px)`
went negative at radius 0, silently dropping `rounded-sm`; `bg-black/80` overlays were
invisible on a near-black base; and `bg-emerald-600 text-white` was already failing AA.

## Verification

| Check | Result |
|---|---|
| `npx tsc -b` | clean |
| `npm run build` | clean |
| `npm run check:tokens` | **OK — 54 token classes emitted, 23 tokens defined in both modes** |
| `npx playwright test` | **78/78 passed**, unchanged and unedited |
| `npm run render:walk` | **OK — 28 renders clean** (14 routes × light/dark, public routes walked signed-out) |
| `npm run check:contrast` | **OK — 250 pairs pass** across 5 brands × 2 modes |
| `GET /api/stats` (unauthenticated) | `concepts=74 · track_stages=23 · drills=58 · content_pages=67 · rubrics=44 · rubric_items=104` |

The stat counts match the anchor in `../b3-local/b3-local-render-walk.md` exactly, and the
landing page reads them live rather than hard-coding them.

### Two instruments, both proved able to fail

A gate that has never failed is not a measurement.

- **`check-tokens`** caught two genuinely unemitted classes on its first run.
- **`check-contrast`** was deliberately broken (`--success` set to near-white) and correctly
  reported **20 of 250** failures — including `--ladder-4`, which aliases `--success` — then
  returned to 250/250 when restored.

### What the Playwright suite does NOT cover

It holds **zero** `toHaveClass` / `toHaveCSS` assertions and selects by role and text, so a
contrast regression or an invisible element is completely invisible to it. `render-walk.mjs`
and `check-contrast.mjs` exist for exactly that gap — and earned their place immediately:
the render walk screenshotted the landing page **blank below the fold**, because `Reveal`
hid content and only unhid it on intersection, so with motion disabled nothing ever revealed
it. The text-content probe scored that page as "painted" (3187 chars). Only the screenshot
caught it.

### Running the e2e suite locally

The suite needs an API whose CORS admits `http://localhost:5173` (Playwright's dev server).
The docker daily driver sets `CORS_ORIGINS: http://localhost:5174`, so pointing the suite at
it fails 16 specs with what looks like a data bug but is a preflight rejection — confirmed
with an `OPTIONS` probe: origin `:5173` → **400**, origin `:5174` → **200**. Run a second API
alongside it instead:

```bash
docker compose run --rm -d --name nsl-e2e-api -p 8000:8000 \
  -e CORS_ORIGINS=http://localhost:5173 api
```

## Rebuild button (Settings → Developer)

`scripts/dev-rebuild.mjs` + `components/settings/rebuild-button.tsx`. Rebuilds the `app` and
`api` containers and reloads once the new bundle is actually live.

A restart would not do: `app/Dockerfile` runs `npm run build` at *image build* time and copies
`dist/` into nginx, and there is no source bind mount — so `docker compose restart app`
re-serves the byte-identical old files. The helper runs `up -d --build`.

**It runs on the HOST, not in a container, and that is the whole security argument.** Driving
Docker from inside a container means mounting `/var/run/docker.sock`, which is root on this
machine — into a service that is published through a Cloudflare tunnel and runs with
`DEBUG=true` (so `POST /auth/debug/token` accepts anyone past the one Basic-auth password).
The API keeps no ability to execute anything.

Why the tunnel cannot reach it, strongest first:

1. **Structural.** The button fetches `http://127.0.0.1:5199` *from the browser*. Loaded through
   the tunnel that address resolves on the **visitor's** machine — the packets never leave their
   laptop. Not a check that can be argued past.
2. **Network.** The listener binds `127.0.0.1` explicitly.
3. **Proxy.** `nginx-common.conf` proxies only `/_api/` and static assets; there is no route to
   the helper, and `5199` appears nowhere in the nginx config or compose file. **Keep it that way.**

`isLocal()` in the component is cosmetic — it hides a control that would not have worked anyway.
It is not the boundary.

### Guards, each tested

| Probe | Result |
|---|---|
| Preflight from `http://localhost:5174` | `204` + CORS header |
| Preflight from `https://evil.example.com` | **`403`, no CORS header** — browser never sends the POST |
| `POST` from a hostile origin | `{"error":"origin not allowed"}` |
| Forged `Host:` header (DNS rebinding) | **`403`** |
| `{"services":["db"]}` | `{"error":"no valid services"}` — fixed allowlist, `app`/`api` only |

Mutating routes require `Content-Type: application/json`, which is what forces the preflight to
happen at all. `spawn` runs with `shell: false`; no caller string ever reaches a shell.

### Proved end to end

Triggered through the helper exactly as the button does:

- bundle hash `index-BDEQnwAt.js` → `index-CgpTWX9P.js` (so the button's reload detection fires
  on a real change rather than reloading into the old bundle)
- `docker` exited `0`, log tail `✓ rebuild complete`
- served `index.html` now carries `class="dark" data-brand="cyan"`
- `GET /_api/api/stats` through the app's own proxy, unauthenticated →
  `concepts=74 · track_stages=23 · drills=58 · content_pages=67 · rubrics=44 · rubric_items=104`
- render walk against **`:5174`** (the deployed container, not the dev server): 28 renders clean

Start it from the repo root — it is not started by compose:

```bash
node scripts/dev-rebuild.mjs      # or: .\scripts\dev-rebuild.ps1
```

## Two things the page states carefully

- **Mentorship is announced, not shipped.** Nothing in the repo supports multi-user: `config.py`
  says "this is a single-user app", `render.yaml` pins `--workers 1`, and the prod allowlist is
  fail-closed (empty `ALLOWED_DISCORD_IDS` admits *nobody*). The landing copy says so.
- **"Powered by the NeuroSpect Suite" is a brand claim, not an integration.** This backend mints
  its own JWTs against its own `users` table and has no runtime dependency on `neurospect-api`.
  The page never implies data moves between products.

Every feature line was written from what the code does. Nothing claims flashcards, quizzes,
courses, video, community, mobile, team features, AI tutoring or hosted SaaS — none exist. The
AI second reader is labelled optional because `ai_grading_enabled = False` in every shipped config.
