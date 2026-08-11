"""The honesty strip + declared rest days against the real DB (Phase E6).

Same harness as test_predictions.py: in-process ASGI transport, debug JWTs, one
throwaway user per test (`e6h-`), hard-cleaned afterwards.

The pure arithmetic is pinned DB-free in test_honesty.py / test_consistency.py.
What only this layer can prove is the set of claims E6 makes about itself:

  * **The signals gate NOTHING.** Not "no code path reads them" by inspection —
    `/api/gate` is captured byte-for-byte, then evidence that makes every single
    signal fire is created, then it is captured again and must be IDENTICAL.
  * **No signal is stored.** Structurally: no table in the schema has a column for
    one, so there is nothing to write even by accident.
  * **A rest day cannot be declared for a day that has passed** — and the trigger
    is proven to be what stops it, by disabling the trigger and watching the same
    insert succeed (E5's "prove the guard is what makes the test pass" precedent).
  * **There is no PATCH and no DELETE on a rest day**, pinned so adding one fails.
  * **`STAGE_UNWIRED` stays empty** — E5 emptied it; a regression here would be a
    regression of the whole workstream.
"""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.deps import get_db
from app.main import app
from app.models.base import Base
from app.models.concept_progress import ConceptProgress
from app.models.drill_progress import DrillProgress
from app.models.evidence import EvidenceAsset, EvidenceGrade
from app.models.plan_item import PlanItem
from app.models.rest_day import RestDay
from app.models.study_preferences import StudyPreferences
from app.models.user import User
from app.services import honesty, stages
from tests.evidence_helpers import chart_png, upload_evidence

_test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(bind=_test_engine, expire_on_commit=False)

_PREFIX = "e6h-"
_DRILL = "aura D1-a"
_DRILL2 = "aura D1-b"


async def _override_get_db():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _use_test_db():
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(
            select(User.id).where(User.discord_id.like(f"{_PREFIX}%"))
        )).scalars().all()
        for uid in ids:
            await db.execute(delete(EvidenceGrade).where(EvidenceGrade.user_id == uid))
            await db.execute(delete(EvidenceAsset).where(EvidenceAsset.user_id == uid))
            await db.execute(delete(RestDay).where(RestDay.user_id == uid))
            await db.execute(delete(PlanItem).where(PlanItem.user_id == uid))
            await db.execute(delete(ConceptProgress).where(ConceptProgress.user_id == uid))
            await db.execute(delete(DrillProgress).where(DrillProgress.user_id == uid))
            await db.execute(delete(StudyPreferences).where(StudyPreferences.user_id == uid))
        await db.commit()


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _token(c, discord_id):
    r = await c.post("/auth/debug/token", json={"discord_id": discord_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sig(payload: dict) -> dict:
    return {s["key"]: s for s in payload["signals"]}


# ---------------------------------------------------------------------------
# THE CLAIM THE WHOLE PHASE RESTS ON — these signals gate nothing
# ---------------------------------------------------------------------------

async def test_making_every_signal_fire_leaves_the_gate_byte_identical():
    """E6's load-bearing assertion, and it is deliberately NOT an inspection of the
    call graph. Capture `/api/gate`, then produce evidence that trips all five
    signals at once — bulk claims, a burst, a back-dated capture, an unchecked
    backlog, a flagged grade — and capture it again. If a single byte moves, an
    honesty signal has reached the verdict, and the design has failed.

    It holds structurally rather than by discipline: the signals are served from a
    SEPARATE resource, so `services/gate.py` has no honesty value in scope to read.
    """
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}gate-identical")
        before = (await c.get("/api/gate", headers=h)).json()

        # Trip every signal.
        backdated = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
        r1 = await upload_evidence(c, h, seed=6101, reps=25,
                                   subject_type="drill", drill_ref=_DRILL)
        assert r1.status_code == 201, r1.text
        r2 = await c.post(
            "/api/evidence", headers=h,
            files={"file": ("c.png", BytesIO(chart_png(6102)), "image/png")},
            data={"subject_type": "drill", "drill_ref": _DRILL,
                  "reps_claimed": "9", "captured_at": backdated},
        )
        assert r2.status_code == 201, r2.text

        after = (await c.get("/api/gate", headers=h)).json()
        assert after == before, "an honesty signal moved the Readiness-to-Live Gate"

        # …and prove the signals really did fire, so the assertion above is not
        # vacuously passing over an unchanged record.
        strip = _sig((await c.get("/api/gate/honesty", headers=h)).json())
        assert strip["bulk_marking"]["count"] == 2
        assert strip["rep_pacing"]["count"] == 1
        assert strip["back_dating"]["count"] == 1
        assert strip["ungraded_backlog"]["count"] == 2
        assert strip["flagged_grades"]["status"] == honesty.MEASURED


async def test_no_honesty_signal_is_stored_anywhere_in_the_schema():
    """Structural: there is no column to write, so nothing can be persisted even by
    a future accident. The strip is recomputed on every read, like the Gate itself."""
    keys = {s.key for s in honesty.compute([]).signals}
    assert keys == {
        "rep_pacing", "back_dating", "bulk_marking", "ungraded_backlog", "flagged_grades",
    }
    columns = {
        f"{table.name}.{col.name}"
        for table in Base.metadata.tables.values()
        for col in table.columns
    }
    assert "rest_days" in {t.name for t in Base.metadata.tables.values()}
    for key in keys | {"honesty", "evidence_streak", "streak"}:
        offenders = [c for c in columns if key in c.split(".")[-1]]
        assert not offenders, f"an honesty signal appears to be stored: {offenders}"


async def test_the_strip_is_recomputed_not_cached():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}recompute")
        first = _sig((await c.get("/api/gate/honesty", headers=h)).json())
        assert first["bulk_marking"]["status"] == honesty.NOT_MEASURED

        assert (await upload_evidence(
            c, h, seed=6110, reps=4, subject_type="drill", drill_ref=_DRILL
        )).status_code == 201

        second = _sig((await c.get("/api/gate/honesty", headers=h)).json())
        assert second["bulk_marking"]["status"] == honesty.MEASURED
        assert second["bulk_marking"]["count"] == 1


async def test_a_user_with_no_evidence_gets_five_not_measured_signals_never_zeroes():
    """The rendered surface must be able to say 'not measured'. A fresh user seeing
    five reassuring zeroes would be told they are clean by an instrument that has
    never been fed."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}empty")
        body = (await c.get("/api/gate/honesty", headers=h)).json()
        assert body["captures"] == 0
        assert len(body["signals"]) == 5
        for s in body["signals"]:
            assert s["status"] == honesty.NOT_MEASURED, s["key"]
            assert s["count"] is None, s["key"]


async def test_the_strip_is_read_only_there_is_nothing_to_dismiss():
    """A signal a user can switch off is not a record of anything."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}readonly")
        for verb in ("POST", "PATCH", "PUT", "DELETE"):
            r = await c.request(verb, "/api/gate/honesty", headers=h)
            assert r.status_code == 405, f"{verb} /api/gate/honesty must not exist"


async def test_the_strip_is_user_scoped():
    async with await _client() as c:
        mine = await _token(c, f"{_PREFIX}mine")
        theirs = await _token(c, f"{_PREFIX}theirs")
        assert (await upload_evidence(
            c, mine, seed=6120, reps=6, subject_type="drill", drill_ref=_DRILL
        )).status_code == 201
        other = _sig((await c.get("/api/gate/honesty", headers=theirs)).json())
        assert other["bulk_marking"]["status"] == honesty.NOT_MEASURED


async def test_legacy_reps_are_reported_as_the_unevidenced_remainder():
    """E2 froze `legacy_reps` for exactly this phase. It is the only part of a rep
    count with no evidence behind it, so the strip has to be able to say so."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}legacy")
        uid = (await c.get("/api/gate/honesty", headers=h)).status_code
        assert uid == 200
        async with AsyncSessionLocal() as db:
            user_id = (await db.execute(
                select(User.id).where(User.discord_id == f"{_PREFIX}legacy")
            )).scalar_one()
            db.add(DrillProgress(user_id=user_id, drill_ref=_DRILL, legacy_reps=11))
            await db.commit()

        assert (await upload_evidence(
            c, h, seed=6130, reps=3, subject_type="drill", drill_ref=_DRILL
        )).status_code == 201

        body = (await c.get("/api/gate/honesty", headers=h)).json()
        assert body["reps_legacy"] == 11
        assert body["reps_evidenced"] == 3


# ---------------------------------------------------------------------------
# Declared rest days — in advance, or not at all
# ---------------------------------------------------------------------------

async def test_a_rest_day_can_be_declared_for_tomorrow():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}rest-ok")
        tomorrow = date.today() + timedelta(days=1)
        r = await c.post("/api/rest-days", headers=h,
                         json={"rest_date": tomorrow.isoformat(), "reason": "travelling"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["rest_date"] == tomorrow.isoformat()
        assert body["days_declared_ahead"] == 1
        assert body["declared_at"], "the server stamps when it was booked"


async def test_a_rest_day_for_yesterday_is_refused():
    """§6's whole point: a day off booked after you missed a day is a retroactive
    streak freeze, and the streak is only readable because it cannot be repaired."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}rest-past")
        yesterday = date.today() - timedelta(days=1)
        r = await c.post("/api/rest-days", headers=h,
                         json={"rest_date": yesterday.isoformat()})
        assert r.status_code == 422, r.text
        assert "in advance" in r.json()["detail"]


async def test_the_client_cannot_supply_declared_at():
    """The server owns this clock, exactly as it owns `predictions.committed_at`."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}rest-clock")
        r = await c.post("/api/rest-days", headers=h, json={
            "rest_date": (date.today() + timedelta(days=2)).isoformat(),
            "declared_at": "2020-01-01T00:00:00Z",
        })
        # Either refused outright, or accepted with the SERVER's timestamp — never
        # the client's. Both are correct; silently trusting the client is not.
        if r.status_code == 201:
            assert r.json()["declared_at"][:4] != "2020"


async def test_declaring_the_same_day_twice_is_a_conflict_not_a_duplicate():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}rest-dupe")
        day = (date.today() + timedelta(days=3)).isoformat()
        assert (await c.post("/api/rest-days", headers=h, json={"rest_date": day})).status_code == 201
        again = await c.post("/api/rest-days", headers=h, json={"rest_date": day})
        assert again.status_code == 409


async def test_there_is_no_patch_and_no_delete_for_a_rest_day():
    """Not "not built yet" — there must not be one. An editable rest day could be
    slid onto a day you later turn out to have missed."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}rest-verbs")
        day = (date.today() + timedelta(days=4)).isoformat()
        created = await c.post("/api/rest-days", headers=h, json={"rest_date": day})
        assert created.status_code == 201
        rid = created.json()["id"]
        for verb in ("PATCH", "DELETE", "PUT"):
            r = await c.request(verb, f"/api/rest-days/{rid}", headers=h)
            assert r.status_code in (404, 405), f"{verb} /api/rest-days/:id must not exist"


async def test_the_trigger_is_what_blocks_a_back_dated_rest_day():
    """PROVE THE GUARD IS THE THING (E3/E5 precedent). Raw SQL, bypassing the
    router entirely: with the trigger enabled the insert raises; with it disabled
    the very same insert succeeds. Without this, the router check alone could be
    passing the test and the DB could be wide open."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}rest-trigger")
        assert (await c.get("/api/rest-days", headers=h)).status_code == 200

    async with AsyncSessionLocal() as db:
        user_id = (await db.execute(
            select(User.id).where(User.discord_id == f"{_PREFIX}rest-trigger")
        )).scalar_one()
        past = date.today() - timedelta(days=5)
        insert = text(
            "INSERT INTO rest_days (user_id, rest_date) VALUES (:u, :d)"
        ).bindparams(u=user_id, d=past)

        # 1. Enabled — the DB refuses it.
        with pytest.raises(Exception) as exc:
            await db.execute(insert)
            await db.commit()
        assert "in advance" in str(exc.value)
        await db.rollback()

        # 2. Disabled — the SAME insert lands, proving the trigger is the mechanism.
        await db.execute(text("ALTER TABLE rest_days DISABLE TRIGGER trg_rest_days_declared_in_advance"))
        await db.execute(insert)
        await db.commit()
        got = (await db.execute(
            select(RestDay.rest_date).where(RestDay.user_id == user_id)
        )).scalars().all()
        assert got == [past], "with the trigger off the back-dated row inserts"

        # 3. Restore, and clean up.
        await db.execute(text("ALTER TABLE rest_days ENABLE TRIGGER trg_rest_days_declared_in_advance"))
        await db.execute(delete(RestDay).where(RestDay.user_id == user_id))
        await db.commit()


async def test_a_declared_rest_day_is_frozen_after_it_is_booked():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}rest-frozen")
        day = date.today() + timedelta(days=6)
        assert (await c.post(
            "/api/rest-days", headers=h, json={"rest_date": day.isoformat()}
        )).status_code == 201

    async with AsyncSessionLocal() as db:
        user_id = (await db.execute(
            select(User.id).where(User.discord_id == f"{_PREFIX}rest-frozen")
        )).scalar_one()
        with pytest.raises(Exception) as exc:
            await db.execute(
                text("UPDATE rest_days SET rest_date = :d WHERE user_id = :u")
                .bindparams(d=date.today() - timedelta(days=1), u=user_id)
            )
            await db.commit()
        assert "frozen" in str(exc.value)
        await db.rollback()


# ---------------------------------------------------------------------------
# Evidence-backed consistency, through the real planner surface
# ---------------------------------------------------------------------------

async def test_today_reports_the_evidence_backed_streak_beside_the_marked_one():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}streak")
        assert (await upload_evidence(
            c, h, seed=6140, subject_type="drill", drill_ref=_DRILL
        )).status_code == 201

        adherence = (await c.get("/api/plan/today", headers=h)).json()["adherence"]
        assert "current_streak" in adherence, "the shipped figure is not replaced"
        con = adherence["consistency"]
        assert con["evidence_streak"] == 1
        assert con["evidenced_days"] == 1
        assert con["rest_days_in_streak"] == 0


async def test_declaring_rest_days_does_not_raise_the_evidence_streak_end_to_end():
    """The score-chase test, through the real API rather than the pure function."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}no-chase")
        assert (await upload_evidence(
            c, h, seed=6150, subject_type="drill", drill_ref=_DRILL
        )).status_code == 201
        before = (await c.get("/api/plan/today", headers=h)).json()["adherence"]["consistency"]

        for n in range(1, 6):
            r = await c.post("/api/rest-days", headers=h, json={
                "rest_date": (date.today() + timedelta(days=n)).isoformat()
            })
            assert r.status_code == 201, r.text

        after = (await c.get("/api/plan/today", headers=h)).json()["adherence"]["consistency"]
        assert after["evidence_streak"] == before["evidence_streak"]
        assert after["rest_days_declared"] == 5
        assert after["rest_days_upcoming"] == 5


async def test_blackout_dates_never_touch_the_evidence_streak():
    """`study_preferences.blackout_dates` accepts ANY date, including yesterday's,
    so honouring it here would be the retroactive streak freeze §6 rejects. Rest
    days are a separate, trigger-guarded table for exactly this reason."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}blackout")
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        r = await c.put("/api/preferences", headers=h, json={
            "timezone": "UTC", "mon_minutes": 60, "tue_minutes": 60, "wed_minutes": 60,
            "thu_minutes": 60, "fri_minutes": 60, "sat_minutes": 60, "sun_minutes": 60,
            "max_session_minutes": 45, "blackout_dates": [yesterday],
            "target_go_live_date": None, "active_track": "aura",
        })
        assert r.status_code == 200, r.text
        # A back-dated blackout is accepted by preferences (it is a scheduling
        # input) and must be invisible to the streak.
        con = (await c.get("/api/plan/today", headers=h)).json()["adherence"]["consistency"]
        assert con["rest_days_declared"] == 0
        assert con["rest_days_in_streak"] == 0


# ---------------------------------------------------------------------------
# The workstream's acceptance test must not regress
# ---------------------------------------------------------------------------

async def test_stage_unwired_is_still_empty_after_e6():
    """E5 emptied it. E6 adds surfaces, so a regression here would mean a stage
    quietly stopped being derived from evidence."""
    assert stages.STAGE_UNWIRED == {}
