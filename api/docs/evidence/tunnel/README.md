# Remote access via Cloudflare quick tunnel — evidence (2026-08-20)

Reverses the 2026-08-12 "hosting is premature" decision **only for reach**, not for hosting: the app
still runs from the local `docker compose` stack against the local Postgres, and a Cloudflare quick
tunnel makes that stack reachable from off the desk. Nothing is deployed and no Render/R2/Pages
resource was provisioned.

## What changed

| File | Change |
|---|---|
| `app/nginx-common.conf` | **New.** The bundle + a same-origin `/_api/` reverse proxy to the api container. Included by both listeners so they cannot drift. |
| `app/nginx.conf` | Two listeners: `:80` (the desk, unauthenticated, unchanged) and `:8080` (the tunnel, HTTP Basic). |
| `app/Dockerfile` | Copies the shared snippet to `/etc/nginx/snippets/app-common.conf`. |
| `docker-compose.yml` | `VITE_API_URL: /_api` (was `http://localhost:8001`), new `127.0.0.1:5175:8080`, htpasswd bind mount. |
| `.tunnel-htpasswd`, `.tunnel-auth.txt` | Gitignored credential + its plaintext copy. |

**Why the API URL is relative.** A quick tunnel's hostname is random and changes on every restart. An
absolute `VITE_API_URL` would have to be rebaked into the bundle *and* added to `CORS_ORIGINS` each
time; a same-origin `/_api` proxy makes one build work on localhost, on the LAN, and behind any
tunnel hostname, and removes CORS from the picture entirely.

## The two traps this sprang

1. **`if` clobbers nginx's positional captures.** `location ~ ^/_api/(.*)$` with a `proxy_pass` using
   `$1` sent *every* request upstream as `/`, because an `if (...)` regex elsewhere in the location
   resets `$1..$9` — even when it does not match. FastAPI answered a perfectly plausible
   `404 {"detail":"Not Found"}`, which reads as "wrong path" rather than "proxy is broken". Fixed with
   the named capture `(?<api_path>.*)`.
2. **Basic auth cannot simply cover the API.** Basic and Bearer share the `Authorization` header, and a
   browser attaches its cached Basic credential only to requests that do not already carry that header
   — so every SPA API call (explicit `Bearer`) would arrive without it and 401, which the SPA reads as
   an expired token and bounces to `/login`, which cannot mint one either. A login loop on every
   request. Resolved by turning the realm off for requests that already present a Bearer (nginx accepts
   a variable as the `auth_basic` value), leaving the password mandatory for everything that could mint
   a session.

## Gate matrix — MEASURED through the public Cloudflare edge

`https://<random>.trycloudflare.com`, 2026-08-20:

| Request | Expected | Got |
|---|---|---|
| `GET /` no credentials | 401 | **401** |
| `GET /` with credentials | 200 | **200** |
| `GET /journal` (SPA deep route) with credentials | 200 | **200** |
| `GET /_api/health` with credentials | 200 `{"status":"ok"}` | **200** |
| `POST /_api/auth/debug/token` **no credentials** | 401 — no account may be minted | **401** |
| `GET /_api/api/tracks` with a valid Bearer | 200 | **200** |
| `GET /_api/api/tracks` with `Bearer garbage` | 401 from FastAPI | **401** |

And on `:5174`, the desk listener, unchanged and password-free: index 200, `/_api/health` 200, authed
`/api/tracks` 200.

## Rendered-surface check — MEASURED

`app/scripts/tunnel-render-check.mjs` drives headless Chromium through the **public hostname**: Basic
auth → debug login → three authed pages. Screenshots in this folder.

- `01-login.png` — the login page behind the password.
- `02-after-login.png` — redirected to `/path`, authenticated as `debug_tunnel-smoke`.
- `03-path.png` — three tracks (Aura/AXL/Unified) and stages A0–A6 with progress rings. Real data.
- `04-journal.png`, `05-gate.png` — the Gate paints all four entry models with computed
  requirement lists. No error or empty states.

One `net::ERR_ABORTED` on `/_api/api/tracks` was logged: a request cancelled by navigating away
mid-flight, not a failure — the same endpoint's data is visibly rendered in `03-path.png`.

## What this does NOT claim

- **Not a deployment.** Render + Cloudflare Pages remain unprovisioned; `render.yaml` is untouched.
- **The tunnel hostname is ephemeral** — a new one on every `cloudflared` restart. No rebuild is
  needed (that is what the relative `/_api` buys), but the link must be re-shared.
- **`DEBUG=true` still.** The password is the only thing standing between the internet and a mintable
  account, so it is the whole security boundary. `/openapi.json` is readable by anyone who sends a
  syntactically valid Bearer; a *session* is not obtainable without the password.
- **The fail-closed allowlist is still untested** — it is a property of the hosted path only.
