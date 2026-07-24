"""API tests for the model-aligned journal + analytics endpoints (Phase 5f).

Exercised against the real (seeded) dev DB via an in-process ASGI transport and
debug JWTs (DEBUG=true), mirroring test_planner_api.py. Each test uses its own
debug user (discord_id prefixed `5ft-`) for per-user isolation; an autouse
fixture hard-deletes every `5ft-` user's journal rows afterwards so the dev DB
is left clean.

Pins the boot prompt's VERIFY step: journal CRUD (create → GET; filter narrows;
PATCH in place; DELETE soft-deletes), per-user isolation, enum/CHECK validation,
no-token 403, and the expectancy VIEW computed correctly over a hand-built set of
entries (the DB-integration counterpart to test_analytics.py's pure-math tests).
"""

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


_PREFIX = "5ft-"


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


async def _user_id(discord_id) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        u = (await db.execute(select(User).where(User.discord_id == discord_id))).scalar_one()
        return u.id


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(
            select(User.id).where(User.discord_id.like(f"{_PREFIX}%"))
        )).scalars().all()
        for uid in ids:
            await db.execute(delete(JournalEntry).where(JournalEntry.user_id == uid))
        await db.commit()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def test_create_then_get_and_list():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}crud")
        r = await c.post("/api/journal", headers=h,
                         json=_entry(r_multiple=2.0, rr_planned=2.0, outcome="win"))
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["mode"] == "backtest" and created["entry_model"] == "london"
        assert created["entry_pda"] == "fvg"  # R4 default applied
        eid = created["id"]

        # GET by id
        g = await c.get(f"/api/journal/{eid}", headers=h)
        assert g.status_code == 200 and g.json()["id"] == eid

        # list returns it
        lst = await c.get("/api/journal", headers=h)
        assert lst.status_code == 200
        assert eid in {e["id"] for e in lst.json()}


async def test_filters_narrow():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}filter")
        await c.post("/api/journal", headers=h, json=_entry(mode="backtest", entry_model="london", instrument="NQ"))
        await c.post("/api/journal", headers=h, json=_entry(mode="live", entry_model="daily_bias", instrument="ES"))

        by_mode = await c.get("/api/journal", headers=h, params={"mode": "live"})
        assert {e["mode"] for e in by_mode.json()} == {"live"}

        by_model = await c.get("/api/journal", headers=h, params={"entry_model": "london"})
        assert {e["entry_model"] for e in by_model.json()} == {"london"}

        by_instr = await c.get("/api/journal", headers=h, params={"instrument": "ES"})
        assert {e["instrument"] for e in by_instr.json()} == {"ES"}


async def test_patch_updates_in_place():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}patch")
        eid = (await c.post("/api/journal", headers=h, json=_entry())).json()["id"]
        r = await c.patch(f"/api/journal/{eid}", headers=h,
                          json={"r_multiple": -1.0, "outcome": "loss", "grade": "b"})
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["id"] == eid and got["r_multiple"] == -1.0
        assert got["outcome"] == "loss" and got["grade"] == "b"
        # unchanged fields preserved
        assert got["entry_model"] == "london" and got["mode"] == "backtest"


async def test_delete_soft_deletes():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}del")
        eid = (await c.post("/api/journal", headers=h, json=_entry())).json()["id"]
        d = await c.delete(f"/api/journal/{eid}", headers=h)
        assert d.status_code == 204
        # gone from the API
        assert (await c.get(f"/api/journal/{eid}", headers=h)).status_code == 404
        assert eid not in {e["id"] for e in (await c.get("/api/journal", headers=h)).json()}

    # still present in the DB (soft delete), flagged
    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(JournalEntry).where(JournalEntry.id == uuid.UUID(eid)))).scalar_one()
    assert row.is_deleted is True and row.deleted_at is not None


# ---------------------------------------------------------------------------
# Isolation + validation + auth
# ---------------------------------------------------------------------------

async def test_per_user_isolation():
    async with await _client() as c:
        ha = await _token(c, f"{_PREFIX}isoA")
        eid = (await c.post("/api/journal", headers=ha, json=_entry())).json()["id"]

        hb = await _token(c, f"{_PREFIX}isoB")
        # B sees none of A's entries, and cannot fetch A's by id.
        assert (await c.get("/api/journal", headers=hb)).json() == []
        assert (await c.get(f"/api/journal/{eid}", headers=hb)).status_code == 404
        # B cannot delete A's entry either.
        assert (await c.delete(f"/api/journal/{eid}", headers=hb)).status_code == 404


async def test_enum_and_check_validation():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}valid")
        # bad mode enum
        assert (await c.post("/api/journal", headers=h, json=_entry(mode="paper"))).status_code == 422
        # bad entry_model enum
        assert (await c.post("/api/journal", headers=h, json=_entry(entry_model="scalp"))).status_code == 422
        # swing_qualification out of 0..2
        assert (await c.post("/api/journal", headers=h, json=_entry(swing_qualification=5))).status_code == 422
        # missing required entry_model
        bad = _entry()
        del bad["entry_model"]
        assert (await c.post("/api/journal", headers=h, json=bad)).status_code == 422


async def test_no_token_is_403():
    async with await _client() as c:
        assert (await c.get("/api/journal")).status_code == 403
        assert (await c.get("/api/analytics/expectancy")).status_code == 403


# ---------------------------------------------------------------------------
# Analytics VIEW over the DB (integration counterpart to test_analytics.py)
# ---------------------------------------------------------------------------

async def test_expectancy_view_over_created_entries():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}expy")
        # london/backtest: +2,+2,-1,-1,-1 @ 2R → expectancy 0.2, win% 0.4, be 0.3333
        for r in (2.0, 2.0, -1.0, -1.0, -1.0):
            await c.post("/api/journal", headers=h,
                         json=_entry(entry_model="london", mode="backtest",
                                     r_multiple=r, rr_planned=2.0))
        # one still-open london/backtest (no r_multiple) → logged but not in n
        await c.post("/api/journal", headers=h, json=_entry(entry_model="london", mode="backtest"))
        # a single live trade in a different model — must be its own group
        await c.post("/api/journal", headers=h,
                     json=_entry(entry_model="daily_bias", mode="live", r_multiple=3.0, rr_planned=3.0))

        exp = (await c.get("/api/analytics/expectancy", headers=h)).json()
        groups = {(g["entry_model"], g["mode"]): g for g in exp["groups"]}

        lon = groups[("london", "backtest")]
        assert lon["logged"] == 6 and lon["n"] == 5
        assert lon["win_rate"] == 0.4 and lon["avg_win_r"] == 2.0 and lon["avg_loss_r"] == 1.0
        assert lon["expectancy"] == 0.2
        assert lon["break_even"] == round(1 / 3, 4) and lon["above_break_even"] is True

        db_ = groups[("daily_bias", "live")]
        assert db_["n"] == 1 and db_["expectancy"] == 3.0

        # summary: both modes present, backtest pooled expectancy == 0.2
        summary = {m["mode"]: m for m in (await c.get("/api/analytics/summary", headers=h)).json()["modes"]}
        assert summary["backtest"]["n"] == 5 and summary["backtest"]["expectancy"] == 0.2
        assert summary["live"]["n"] == 1

        # r-distribution (half-open [lo,hi)): 3 losers in [-1,0), 2 winners of +2R
        # in [2,3), and the +3R live trade in [3,∞).
        dist = {b["label"]: b for b in (await c.get("/api/analytics/r-distribution", headers=h)).json()["buckets"]}
        assert dist["-1 to 0R"]["backtest"] == 3
        assert dist["2 to 3R"]["backtest"] == 2
        assert dist["≥ 3R"]["live"] == 1
