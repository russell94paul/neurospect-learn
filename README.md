# neurospect-learn

The **Neurospect Learning Platform** — a standalone app that surfaces all Neurospect ICT/Smart-Money course
content in a navigable layout and tracks progress across three axes (learning exercises → backtesting → live
trading) against the mastery ladder / confidence scale / Readiness-to-Live Gate.

Two independently-installable packages:

- **`app/`** — frontend (React 19 · Vite 8 · TS 6 · React Router 7 · TanStack Query 5 · shadcn/ui · Tailwind v4).
- **`api/`** — backend (FastAPI · SQLAlchemy 2 async · Alembic · Postgres · Discord OAuth2 + JWT · Poetry).

Canonical design doc:
`C:\Users\PaulRussell\repos\neurospect-wiki\concepts\architecture\learning-platform.md`
(once code exists, **the code is ground truth** — the doc describes it as implemented).

No runtime dependency on `neurospect-api`; this backend mints its own JWTs against its own `users` table.

## Phase status

Scaffold (Phase 5b) complete: repo, lifted frontend spine, app shell + sidebar nav + protected routes with
stub pages for the full route taxonomy, and Discord OAuth (real wiring + debug-login) end-to-end. Data model,
content ingest, journal, expectancy, and gate arrive in Phases 5c–5g.

## Quickstart

### Backend (`api/`)

```bash
cd api
poetry install
cp .env.example .env          # set DATABASE_URL[_SYNC], JWT_SECRET, DEBUG=true for local
alembic upgrade head          # creates the users table
uvicorn app.main:app --reload # http://localhost:8000  (/docs, /health)
```

### Frontend (`app/`)

```bash
cd app
npm install
cp .env.example .env          # VITE_DEBUG=true, VITE_API_URL=http://localhost:8000
npm run dev                   # http://localhost:5173
```
