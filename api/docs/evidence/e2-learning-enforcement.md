# Phase E2 — evidence layer + capture: validation evidence

Reproducible evidence for the learning-enforcement Phase E2 build (Alembic `0009`,
the evidence layer, and `reps` becoming derived). The durable lesson and the
design rationale live in the wiki; this file is the *how to re-run it* record.

## Scripts

| Script | What it proves |
|---|---|
| `scripts/evidence_baseline.py` | `/api/analytics/*` + `/api/gate` byte-identical before vs after the phase |
| `scripts/scratch_migrate.py` | `0009` up/down/up/base reversible — on a THROWAWAY DB, never the working one |

```bash
# The no-regression evidence gate (repeat of the Phase-6 pattern)
poetry run python scripts/evidence_baseline.py --seed --out docs/evidence/e2-baseline-before.json
# …build…
poetry run python scripts/evidence_baseline.py --out docs/evidence/e2-baseline-after.json
poetry run python scripts/evidence_baseline.py --compare \
    docs/evidence/e2-baseline-before.json docs/evidence/e2-baseline-after.json

# Migration reversibility, pinned to a scratch DB by construction
poetry run python scripts/scratch_migrate.py
```

## Results (2026-07-28)

- **Starting state:** `alembic current` = `0008 (head)`; seeds 74 concepts / 23 track_stages /
  53 drills / 67 content_pages; `pytest` 114 passed; `npx playwright test` 36 passed.
- **Migration:** `0009` reversible on the scratch DB — 2 tables · 4 enums · 8 indexes ·
  2 triggers created and dropped, `reps` ⇄ `legacy_reps` renamed both ways, and
  `downgrade base` tears the schema down completely. Working-DB seeds intact afterwards
  (74/23/53/67).
- **No regression:** both baseline snapshots `sha256
  27ff7157b066018369d66a46a1bde9c33e24df0b0eca1d19a273f1bc723c7c47` (106,425 bytes) —
  **byte-identical**. Also pinned as a durable test
  (`tests/test_evidence_api.py::test_the_evidence_layer_never_moves_expectancy_or_the_gate`).
- **Tests:** `pytest` **142 passed** (114 → +28); `tsc -b` + `vite build` clean;
  `npx playwright test` **45 passed** (36 → +9), stable across three consecutive full runs.
- **The bypass test:** `test_no_endpoint_can_mint_a_rep_without_evidence` attacks all three
  historic rep-writing paths (`PATCH /api/drills`, `PATCH /api/progress`,
  `PATCH /api/plan/items/{id}`) and all three fail to create a rep.
- **Perceptual-hash thresholds** are measured, not guessed — see
  `tests/test_evidence_checks.py::test_measured_phash_separation`.

## Two bugs found by validating at the rendered surface

Both would have passed a query-layer check:

1. **ky v2 consumes the response body** to populate `error.data`, so
   `error.response.json()` throws. Every server `detail` message was being replaced by
   ky's generic "Request failed with status code 4xx" — including, silently since 5e-1,
   the ladder-advance gate's reason. Fixed with `apiErrorDetail()` in `src/lib/api.ts`.
2. **The local backend's signed URL is app-relative**, so `<img src>` resolved it against
   the SPA origin (`:5173`) and every thumbnail rendered broken. The Playwright assertion
   passed because it checked the `src` attribute, not that the image loaded; it now polls
   `naturalWidth > 0`. Fixed with `evidenceSrc()` in `src/lib/evidence.ts`.
