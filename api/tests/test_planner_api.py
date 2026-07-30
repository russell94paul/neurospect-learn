"""API tests for the Study-Planner endpoints (Phase 5e-2).

Exercised against the real (seeded) dev DB via an in-process ASGI transport and
debug JWTs (DEBUG=true). Each test uses its own debug user (discord_id prefixed
`5e2t-`) for per-user isolation; an autouse fixture hard-deletes every `5e2t-`
user's planner/progress rows afterwards so the dev DB is left clean.

Pins the boot prompt's API VERIFY step: preferences round-trip, /plan/today
idempotent materialization, PATCH-item-done feeding progress, regenerate bumping
plan_version (frozen done items preserved), per-user isolation, and a 5e-1b
no-regression check.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.deps import get_db
from app.main import app
from app.models.concept import Concept
from app.models.concept_progress import ConceptProgress
from app.models.drill_progress import DrillProgress
from app.models.evidence import EvidenceAsset
from app.models.plan_item import PlanItem
from app.models.study_preferences import StudyPreferences
from app.models.user import User
from tests.evidence_helpers import give_concept_reps, give_drill_reps

# Dedicated test engine with NullPool: no connection is pooled across pytest's
# per-test event loops (which otherwise reuse a connection bound to a closed
# loop → "Event loop is closed"). The app's get_db is overridden to use it.
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


_PREFIX = "5e2t-"
_ALL_DAYS = {f"{d}_minutes": 120 for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


def _prefs_body(**over):
    body = {"timezone": "UTC", "max_session_minutes": 60, "active_track": "aura", **_ALL_DAYS}
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


async def _mark_stage_canmark(user_id, track, stage_code):
    """Test setup: mark every concept of (track, stage_code) to Can-mark so the
    next stage unlocks — inserted directly (bypasses the /progress gate)."""
    async with AsyncSessionLocal() as db:
        cs = (await db.execute(
            select(Concept).where(Concept.track == track, Concept.stage_code == stage_code)
        )).scalars().all()
        for c in cs:
            db.add(ConceptProgress(user_id=user_id, concept_id=c.id, ladder_stage=2,
                                   confidence=3, legacy_reps=10))
        await db.commit()


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(
            select(User.id).where(User.discord_id.like(f"{_PREFIX}%"))
        )).scalars().all()
        for uid in ids:
            await db.execute(delete(PlanItem).where(PlanItem.user_id == uid))
            await db.execute(delete(StudyPreferences).where(StudyPreferences.user_id == uid))
            await db.execute(delete(ConceptProgress).where(ConceptProgress.user_id == uid))
            await db.execute(delete(DrillProgress).where(DrillProgress.user_id == uid))
            await db.execute(delete(EvidenceAsset).where(EvidenceAsset.user_id == uid))
        await db.commit()


# ---------------------------------------------------------------------------

async def test_preferences_roundtrip():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}prefs")
        # No prefs yet → defaults, is_configured False.
        r = await c.get("/api/preferences", headers=h)
        assert r.status_code == 200 and r.json()["is_configured"] is False

        body = _prefs_body(mon_minutes=30, active_track="ict_course", target_go_live_date="2027-01-01")
        r = await c.put("/api/preferences", headers=h, json=body)
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["is_configured"] is True and got["active_track"] == "ict_course"
        assert got["mon_minutes"] == 30 and got["target_go_live_date"] == "2027-01-01"

        r2 = await c.get("/api/preferences", headers=h)
        assert r2.json()["active_track"] == "ict_course" and r2.json()["mon_minutes"] == 30


async def test_plan_today_materializes_idempotently():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}today")
        await c.put("/api/preferences", headers=h, json=_prefs_body())
        r1 = await c.get("/api/plan/today", headers=h)
        assert r1.status_code == 200, r1.text
        n1 = len(r1.json()["items"])
        assert n1 > 0  # a fresh aura user gets foundation habits + learn tasks

        r2 = await c.get("/api/plan/today", headers=h)
        n2 = len(r2.json()["items"])
        assert n1 == n2  # second call must not duplicate

    uid = await _user_id(f"{_PREFIX}today")
    async with AsyncSessionLocal() as db:
        cnt = (await db.execute(
            select(func.count()).select_from(PlanItem).where(
                PlanItem.user_id == uid, PlanItem.is_deleted.is_(False)
            )
        )).scalar()
    assert cnt == n1  # exactly one row per computed slot — idempotent


async def test_patch_item_records_practice_but_mints_no_concept_rep():
    """THE PLANNER BYPASS, closed (Phase E2).

    Marking a plan item done used to increment `concept_progress.reps`, so the
    planner was a second way to mint a rep with no evidence — which would have
    made the whole evidence layer theatre. It now records the practice
    (`last_practiced`, so spaced review still works) and credits NOTHING; the
    count moves only when evidence is uploaded.
    """
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}cfeed")
        await c.put("/api/preferences", headers=h, json=_prefs_body())
        today = (await c.get("/api/plan/today", headers=h)).json()
        learn = next(i for i in today["items"] if i["activity"] == "learn" and i["concept_id"])
        r = await c.patch(f"/api/plan/items/{learn['id']}", headers=h,
                          json={"status": "done", "done_qty": 2})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "done"

        # The plan's own record of the work still says 2 …
        assert r.json()["done_qty"] == 2
        # … but no rep was created.
        row = next(p for p in (await c.get("/api/progress", headers=h)).json()
                   if p["concept_id"] == learn["concept_id"])
        assert row["reps"] == 0 and row["reps_evidenced"] == 0
        assert row["last_practiced"] is not None

        # Upload evidence for the same concept: NOW the rep exists.
        await give_concept_reps(c, h, learn["concept_id"], 2, seed=4101)
        row = next(p for p in (await c.get("/api/progress", headers=h)).json()
                   if p["concept_id"] == learn["concept_id"])
        assert row["reps"] == 2 and row["reps_evidenced"] == 2

    uid = await _user_id(f"{_PREFIX}cfeed")
    async with AsyncSessionLocal() as db:
        cp = (await db.execute(select(ConceptProgress).where(
            ConceptProgress.user_id == uid,
            ConceptProgress.concept_id == uuid.UUID(learn["concept_id"]),
        ))).scalar_one()
    # The stored column stays frozen at its pre-evidence value: nothing writes it.
    assert cp.legacy_reps == 0 and cp.last_practiced is not None


async def test_patch_item_records_practice_but_mints_no_drill_rep():
    uid_discord = f"{_PREFIX}dfeed"
    async with await _client() as c:
        h = await _token(c, uid_discord)
        uid = await _user_id(uid_discord)
        await _mark_stage_canmark(uid, "aura", "A0")  # unlock A1 (which has real drills)
        # Big daily budget + session cap so a drill packs onto TODAY (with a
        # small budget it would legitimately roll behind habits/reviews/learn).
        big = {f"{d}_minutes": 480 for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
        await c.put("/api/preferences", headers=h,
                    json=_prefs_body(max_session_minutes=120, **big))
        today = (await c.get("/api/plan/today", headers=h)).json()
        drill = next((i for i in today["items"] if i["activity"] == "drill" and i["drill_ref"]), None)
        assert drill is not None, "expected a drill item once A1 is unlocked"
        r = await c.patch(f"/api/plan/items/{drill['id']}", headers=h,
                          json={"status": "done", "done_qty": 7})
        assert r.status_code == 200, r.text

        # The ✋/🛠 mark and last_practiced are recorded; the rep count is not.
        row = next(d for d in (await c.get("/api/drills", headers=h)).json()
                   if d["drill_ref"] == drill["drill_ref"])
        assert row["reps"] == 0 and row["last_practiced"] is not None

        await give_drill_reps(c, h, drill["drill_ref"], 7, seed=4102)
        row = next(d for d in (await c.get("/api/drills", headers=h)).json()
                   if d["drill_ref"] == drill["drill_ref"])
        assert row["reps"] == 7 and row["reps_evidenced"] == 7

    async with AsyncSessionLocal() as db:
        dp = (await db.execute(select(DrillProgress).where(
            DrillProgress.user_id == uid, DrillProgress.drill_ref == drill["drill_ref"]
        ))).scalar_one()
    assert dp.legacy_reps == 0 and dp.last_practiced is not None


async def test_regenerate_bumps_version_and_preserves_done():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}regen")
        await c.put("/api/preferences", headers=h, json=_prefs_body())
        today = (await c.get("/api/plan/today", headers=h)).json()
        assert today["plan_version"] == 1
        # Mark one item done — it must survive regeneration (frozen accountability).
        done_item = today["items"][0]
        await c.patch(f"/api/plan/items/{done_item['id']}", headers=h, json={"status": "done"})

        r = await c.post("/api/plan/regenerate", headers=h)
        assert r.status_code == 200, r.text
        regen = r.json()
        assert regen["plan_version"] == 2
        # The done item is preserved (same id, still done) — kept at its version.
        kept = [i for i in regen["items"] if i["id"] == done_item["id"]]
        assert kept and kept[0]["status"] == "done"
        # Pending items were recomputed at the new version.
        pend = [i for i in regen["items"] if i["status"] == "pending"]
        assert pend and all(i["plan_version"] == 2 for i in pend)


async def test_per_user_isolation():
    async with await _client() as c:
        ha = await _token(c, f"{_PREFIX}isoA")
        await c.put("/api/preferences", headers=ha, json=_prefs_body())
        ta = (await c.get("/api/plan/today", headers=ha)).json()
        assert len(ta["items"]) > 0
        a_ids = {i["id"] for i in ta["items"]}

        hb = await _token(c, f"{_PREFIX}isoB")
        # B has no prefs → empty plan, and none of A's items.
        tb = (await c.get("/api/plan/today", headers=hb)).json()
        assert tb["items"] == []
        # B configured on a different track still never sees A's items.
        await c.put("/api/preferences", headers=hb, json=_prefs_body(active_track="unified"))
        tb2 = (await c.get("/api/plan/today", headers=hb)).json()
        assert a_ids.isdisjoint({i["id"] for i in tb2["items"]})


async def test_5e1b_endpoints_no_regression():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}regr")
        tracks = (await c.get("/api/tracks", headers=h)).json()
        assert {t["track"] for t in tracks} == {"aura", "ict_course", "unified"}
        aura = (await c.get("/api/stages?track=aura", headers=h)).json()
        assert [s["stage_code"] for s in aura] == ["A0", "A1", "A2", "A3", "A4", "A5", "A6"]
