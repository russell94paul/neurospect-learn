# neurospect-learn · api

Backend for the Neurospect Learning Platform. FastAPI · SQLAlchemy 2.0 async (`asyncpg`) · Alembic · Postgres ·
Discord OAuth2 + JWT (python-jose) · Poetry.

Mirrors the proven `neurospect-api` layout (`config`/`database`/`deps`/`auth`/`models`/`schemas`) as a **separate
codebase** with its own DB and secrets — no runtime dependency on `neurospect-api`.

## Phase 5b surface

- `GET /health` → `{"status": "ok"}`
- `POST /auth/discord/token` — exchange a Discord OAuth code → app JWT (upserts the user)
- `GET /auth/me` — the current user (Bearer JWT)
- `POST /auth/debug/token` — DEBUG-only; mints a JWT for any `discord_id` (local dev)

Alembic `0001_initial_users` creates the `update_updated_at()` trigger fn + `users` table + trigger.

## Local dev

```bash
poetry install
cp .env.example .env    # DATABASE_URL[_SYNC], JWT_SECRET, DEBUG=true
alembic upgrade head
uvicorn app.main:app --reload
```
