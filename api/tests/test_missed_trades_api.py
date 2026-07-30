"""API tests for the missed-trade log + opportunity cost + 6c position_size.

Same harness as test_journal_api.py: in-process ASGI transport against the real
seeded dev DB with debug JWTs (DEBUG=true), one throwaway debug user per test
(discord_id prefixed `6ft-`), hard-cleaned afterwards.

The load-bearing test here is the PHASE-6 EVIDENCE GATE:
`test_missed_trades_and_position_size_never_move_expectancy_or_the_gate` snapshots
/api/analytics/expectancy + /api/gate, writes missed trades and a `position_size`,
and asserts both responses are byte-identical. These are trades that were never
taken and a record-keeping field — neither may ever move the proof of edge or the
live-eligibility verdict.
"""

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.deps import get_db
from app.main import app
from app.models.journal_entry import JournalEntry
from app.models.missed_trade import MissedTrade
from app.models.user import User

_test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(bind=_test_engine, expire_on_commit=False)


async def _override_get_db():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _use_test_db():
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


_PREFIX = "6ft-"


def _miss(**over):
    body = {
        "entry_date": "2026-07-20",
        "instrument": "NQ",
        "entry_model": "london",
        "miss_type": "canceled",
    }
    body.update(over)
    return body


def _entry(**over):
    body = {
        "entry_date": "2026-07-20",
        "instrument": "NQ",
        "mode": "backtest",
        "entry_model": "london",
    }
    body.update(over)
    return body


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _token(c, discord_id):
    r = await c.post("/auth/debug/token", json={"discord_id": discord_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(
            select(User.id).where(User.discord_id.like(f"{_PREFIX}%"))
        )).scalars().all()
        for uid in ids:
            await db.execute(delete(MissedTrade).where(MissedTrade.user_id == uid))
            await db.execute(delete(JournalEntry).where(JournalEntry.user_id == uid))
        await db.commit()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def test_create_then_get_and_list():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}mt-crud")
        r = await c.post("/api/missed-trades", headers=h, json=_miss(
            reason="pulled the order when it went vertical",
            hesitation_tags=["pulled_on_spike", "size_fear"],
            planned_entry=20100.25, planned_stop=20080.0, planned_target=20160.5,
            rr_planned=3.0, hypothetical_outcome="would_win", hypothetical_r=2.5,
            narrative="SSL raid into the FVG", session="london",
        ))
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["miss_type"] == "canceled" and created["entry_model"] == "london"
        assert created["hypothetical_r"] == 2.5
        assert created["hesitation_tags"] == ["pulled_on_spike", "size_fear"]
        mid = created["id"]

        assert (await c.get(f"/api/missed-trades/{mid}", headers=h)).json()["id"] == mid
        assert mid in {m["id"] for m in (await c.get("/api/missed-trades", headers=h)).json()}


async def test_filters_narrow():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}mt-filter")
        await c.post("/api/missed-trades", headers=h, json=_miss(
            miss_type="canceled", entry_model="london", hypothetical_outcome="would_lose"))
        await c.post("/api/missed-trades", headers=h, json=_miss(
            miss_type="hesitated", entry_model="daily_bias", instrument="ES",
            hypothetical_outcome="would_win"))

        by_type = await c.get("/api/missed-trades", headers=h, params={"miss_type": "hesitated"})
        assert {m["miss_type"] for m in by_type.json()} == {"hesitated"}

        by_model = await c.get("/api/missed-trades", headers=h, params={"entry_model": "london"})
        assert {m["entry_model"] for m in by_model.json()} == {"london"}

        by_outcome = await c.get("/api/missed-trades", headers=h,
                                 params={"hypothetical_outcome": "would_win"})
        assert {m["hypothetical_outcome"] for m in by_outcome.json()} == {"would_win"}

        by_instr = await c.get("/api/missed-trades", headers=h, params={"instrument": "ES"})
        assert {m["instrument"] for m in by_instr.json()} == {"ES"}


async def test_patch_resolves_the_hypothetical_later():
    """The point of PATCH: log the miss in the moment, resolve what price did after."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}mt-patch")
        mid = (await c.post("/api/missed-trades", headers=h, json=_miss())).json()["id"]
        r = await c.patch(f"/api/missed-trades/{mid}", headers=h,
                          json={"hypothetical_outcome": "would_lose", "hypothetical_r": -1.0,
                                "notes": "instinct was right"})
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["hypothetical_outcome"] == "would_lose" and got["hypothetical_r"] == -1.0
        assert got["miss_type"] == "canceled" and got["entry_model"] == "london"  # preserved


async def test_delete_soft_deletes():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}mt-del")
        mid = (await c.post("/api/missed-trades", headers=h, json=_miss())).json()["id"]
        assert (await c.delete(f"/api/missed-trades/{mid}", headers=h)).status_code == 204
        assert (await c.get(f"/api/missed-trades/{mid}", headers=h)).status_code == 404
        assert mid not in {m["id"] for m in (await c.get("/api/missed-trades", headers=h)).json()}

    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(MissedTrade).where(MissedTrade.id == uuid.UUID(mid))
        )).scalar_one()
    assert row.is_deleted is True and row.deleted_at is not None


async def test_per_user_isolation():
    async with await _client() as c:
        ha = await _token(c, f"{_PREFIX}mt-isoA")
        mid = (await c.post("/api/missed-trades", headers=ha, json=_miss())).json()["id"]

        hb = await _token(c, f"{_PREFIX}mt-isoB")
        assert (await c.get("/api/missed-trades", headers=hb)).json() == []
        assert (await c.get(f"/api/missed-trades/{mid}", headers=hb)).status_code == 404
        assert (await c.delete(f"/api/missed-trades/{mid}", headers=hb)).status_code == 404
        summary = (await c.get("/api/analytics/missed-summary", headers=hb)).json()
        assert summary["total"]["logged"] == 0


async def test_enum_validation_and_auth():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}mt-valid")
        assert (await c.post("/api/missed-trades", headers=h,
                             json=_miss(miss_type="chickened_out"))).status_code == 422
        assert (await c.post("/api/missed-trades", headers=h,
                             json=_miss(entry_model="scalp"))).status_code == 422
        assert (await c.post("/api/missed-trades", headers=h,
                             json=_miss(hypothetical_outcome="maybe"))).status_code == 422
        bad = _miss()
        del bad["miss_type"]
        assert (await c.post("/api/missed-trades", headers=h, json=bad)).status_code == 422

    async with await _client() as c:
        assert (await c.get("/api/missed-trades")).status_code == 403
        assert (await c.get("/api/analytics/missed-summary")).status_code == 403


# ---------------------------------------------------------------------------
# The opportunity-cost analytic over the DB (by-hand answer)
# ---------------------------------------------------------------------------

async def test_opportunity_cost_over_created_rows_by_hand():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}mt-oc")
        # 2 missed winners (+2.5, +1.0) and 2 protective cancels (-1.0, -0.5),
        # plus one unresolved. forgone 3.5 · saved 1.5 · net +2.0 · avg 0.5
        for r, mt, tags in (
            (2.5, "hesitated", ["fear_of_loss"]),
            (1.0, "almost_took", ["unclear_bias"]),
            (-1.0, "canceled", ["pulled_on_spike"]),
            (-0.5, "canceled", ["pulled_on_spike"]),
        ):
            await c.post("/api/missed-trades", headers=h, json=_miss(
                miss_type=mt, hypothetical_r=r, hesitation_tags=tags))
        await c.post("/api/missed-trades", headers=h, json=_miss(miss_type="hesitated"))

        s = (await c.get("/api/analytics/missed-summary", headers=h)).json()
        t = s["total"]
        assert t["logged"] == 5 and t["resolved"] == 4
        assert t["would_win"] == 2 and t["would_lose"] == 2
        assert t["forgone_r"] == 3.5 and t["saved_r"] == 1.5 and t["net_r"] == 2.0
        assert t["avg_r"] == 0.5

        by_type = {b["key"]: b for b in s["by_miss_type"]}
        # Pulling the order was PROTECTIVE — canceled nets negative.
        assert by_type["canceled"]["net_r"] == -1.5
        assert by_type["hesitated"]["net_r"] == 2.5

        tags = s["by_hesitation_tag"]
        assert tags[0]["key"] == "pulled_on_spike" and tags[0]["logged"] == 2


# ---------------------------------------------------------------------------
# THE PHASE-6 EVIDENCE GATE — 6b/6c must not move the numbers
# ---------------------------------------------------------------------------

async def test_missed_trades_and_position_size_never_move_expectancy_or_the_gate():
    """Byte-identical /api/analytics/expectancy + /api/gate across a missed-trade
    write and a `position_size` write. Missed trades were never taken; position
    size is record-keeping. Neither may reach the proof of edge or the verdict."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}mt-gate")

        # A real executed-trade sample so the snapshot is non-trivial.
        ids = []
        for r in (2.0, 2.0, -1.0, -1.0, -1.0):
            ids.append((await c.post("/api/journal", headers=h, json=_entry(
                r_multiple=r, rr_planned=2.0))).json()["id"])
        await c.post("/api/journal", headers=h,
                     json=_entry(mode="live", entry_model="daily_bias",
                                 r_multiple=-0.5, rr_planned=2.0))

        async def snapshot():
            exp = (await c.get("/api/analytics/expectancy", headers=h)).json()
            summ = (await c.get("/api/analytics/summary", headers=h)).json()
            dist = (await c.get("/api/analytics/r-distribution", headers=h)).json()
            g = (await c.get("/api/gate", headers=h)).json()
            return json.dumps([exp, summ, dist, g], sort_keys=True)

        before = snapshot_before = await snapshot()
        assert '"expectancy": 0.2' in before  # the sample is really in there

        # 1. Write missed trades — including a big "would have won" number that
        #    would visibly inflate expectancy if it ever leaked in.
        for r, mt in ((9.9, "hesitated"), (-4.0, "canceled"), (None, "almost_took")):
            body = _miss(miss_type=mt, hesitation_tags=["pulled_on_spike"])
            if r is not None:
                body["hypothetical_r"] = r
                body["hypothetical_outcome"] = "would_win" if r > 0 else "would_lose"
            assert (await c.post("/api/missed-trades", headers=h, json=body)).status_code == 201
        assert (await c.get("/api/analytics/missed-summary", headers=h)).json()["total"]["logged"] == 3
        assert await snapshot() == snapshot_before, "missed trades moved expectancy or the gate"

        # 2. Write 6c position_size onto every executed entry.
        for i, eid in enumerate(ids, start=1):
            r = await c.patch(f"/api/journal/{eid}", headers=h, json={"position_size": i * 2})
            assert r.status_code == 200 and r.json()["position_size"] == i * 2
        assert await snapshot() == snapshot_before, "position_size moved expectancy or the gate"

        # 3. And it round-trips on read (it is recorded, just never computed on).
        entries = (await c.get("/api/journal", headers=h)).json()
        assert {e["position_size"] for e in entries if e["position_size"] is not None} == {
            2.0, 4.0, 6.0, 8.0, 10.0
        }
