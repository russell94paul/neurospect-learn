"""STEP-0 / final no-regression evidence gate for Phase E2 (learning-enforcement).

Repeats the Phase-6 pattern (learning-platform.md §6 as-built, "THE PHASE-6
EVIDENCE GATE"): snapshot `/api/analytics/*` + `/api/gate` for a fixed fixture
user BEFORE the phase's code lands and again AFTER, and prove the two files are
byte-identical. An EVIDENCE LAYER MUST NOT MOVE EXPECTANCY OR THE GATE.

    poetry run python scripts/evidence_baseline.py --seed --out <file>   # step 0
    poetry run python scripts/evidence_baseline.py --out <file>          # after
    poetry run python scripts/evidence_baseline.py --compare a b

`--seed` provisions the fixture user (idempotent: journal entries are only
written when the user has none) so the snapshot is non-trivial — a cleared
London plus a losing live model, mirroring the 5g/6 fixture.
"""

import argparse
import asyncio
import hashlib
import json
import sys

from httpx import ASGITransport, AsyncClient

FIXTURE_DISCORD_ID = "e2-baseline-fixture"

ENDPOINTS = [
    "/api/analytics/expectancy",
    "/api/analytics/summary",
    "/api/analytics/r-distribution",
    "/api/analytics/missed-summary",
    "/api/gate",
]

# A deterministic executed-trade sample: London backtest 3W/2L at 2R planned,
# plus one losing live daily_bias entry (the honesty view).
_ENTRIES = (
    [{"entry_date": "2026-07-01", "instrument": "NQ", "mode": "backtest",
      "entry_model": "london", "r_multiple": r, "rr_planned": 2.0}
     for r in (2.0, 2.0, 2.0, -1.0, -1.0)]
    + [{"entry_date": "2026-07-02", "instrument": "ES", "mode": "live",
        "entry_model": "daily_bias", "r_multiple": -0.5, "rr_planned": 2.0}]
)

_MISSES = [
    {"entry_date": "2026-07-03", "instrument": "NQ", "entry_model": "london",
     "miss_type": "canceled", "hypothetical_r": -1.0,
     "hypothetical_outcome": "would_lose"},
    {"entry_date": "2026-07-04", "instrument": "NQ", "entry_model": "london",
     "miss_type": "hesitated", "hypothetical_r": 2.0,
     "hypothetical_outcome": "would_win"},
]


async def _snapshot(seed: bool) -> str:
    from app.main import app  # imported late so --compare needs no DB

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/auth/debug/token", json={"discord_id": FIXTURE_DISCORD_ID})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        if seed:
            if not (await c.get("/api/journal", headers=h)).json():
                for body in _ENTRIES:
                    assert (await c.post("/api/journal", headers=h, json=body)).status_code == 201
            if not (await c.get("/api/missed-trades", headers=h)).json():
                for body in _MISSES:
                    assert (await c.post("/api/missed-trades", headers=h, json=body)).status_code == 201

        payload = {}
        for path in ENDPOINTS:
            resp = await c.get(path, headers=h)
            resp.raise_for_status()
            payload[path] = resp.json()
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="provision the fixture user first")
    ap.add_argument("--out", help="write the snapshot here")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = ap.parse_args()

    if args.compare:
        before, after = (open(p, encoding="utf-8").read() for p in args.compare)
        db, da = _digest(before), _digest(after)
        print(f"before sha256 {db}\nafter  sha256 {da}")
        if before == after:
            print("IDENTICAL — no regression")
            return 0
        print("DIFFERENT — the evidence layer moved expectancy or the gate")
        return 1

    text = asyncio.run(_snapshot(args.seed))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"sha256 {_digest(text)}  ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
