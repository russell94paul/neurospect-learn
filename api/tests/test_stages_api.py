"""API tests for the Phase-6a evidence wiring, against the REAL seeded curriculum.

Same harness as test_gate_api.py / test_journal_api.py: in-process ASGI transport,
debug JWTs (DEBUG=true), one throwaway debug user per test (discord_id prefixed
`6st-`), hard-cleaned afterwards.

The pure logic is pinned in tests/test_stages.py; this file pins the parts that
only the live seed + routers can prove:
  * a row that was PERMANENTLY UNMET before 6a now reflects a /gate tick, through
    the real `/api/stages` response;
  * the lock chain on all three real tracks is unchanged by that tick;
  * every (track, stage_code) key in the 6a maps exists in the seeded curriculum,
    and no seeded stage is left with an empty checklist;
  * `/path` and `/today` AGREE: once the foundation stage's bar really is met, the
    planner stops prescribing its daily habit overlay.
"""

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.deps import get_db
from app.main import app
from app.models.concept import Concept
from app.models.concept_progress import ConceptProgress
from app.models.evidence import EvidenceAsset
from app.models.gate_attestation import GateAttestation
from app.models.plan_item import PlanItem
from app.models.study_preferences import StudyPreferences
from app.models.track_stage import TrackStage
from app.models.user import User
from app.services import stages
from tests.evidence_helpers import give_concept_reps

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


_PREFIX = "6st-"


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
            await db.execute(delete(PlanItem).where(PlanItem.user_id == uid))
            await db.execute(delete(StudyPreferences).where(StudyPreferences.user_id == uid))
            await db.execute(delete(ConceptProgress).where(ConceptProgress.user_id == uid))
            await db.execute(delete(GateAttestation).where(GateAttestation.user_id == uid))
            await db.execute(delete(EvidenceAsset).where(EvidenceAsset.user_id == uid))
        await db.commit()


async def _stage_map(c, h, track):
    r = await c.get("/api/stages", headers=h, params={"track": track})
    assert r.status_code == 200, r.text
    return {s["stage_code"]: s for s in r.json()}


async def _attest(c, h, item, value=True):
    r = await c.patch("/api/gate/attestations", headers=h, json={"item": item, "attested": value})
    assert r.status_code == 200, r.text


async def _stage_concepts(track, stage_code):
    async with AsyncSessionLocal() as db:
        return (await db.execute(
            select(Concept).where(Concept.track == track, Concept.stage_code == stage_code)
            .order_by(Concept.sort_order)
        )).scalars().all()


# ---------------------------------------------------------------------------
# The dead checkbox is dead: a /gate tick now shows up on /path
# ---------------------------------------------------------------------------

async def test_gate_tick_flips_the_previously_permanent_unmet_row_on_path():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}flip")

        before = (await _stage_map(c, h, "unified"))["U0"]
        cb = [r for r in before["requirements"] if r["attest_item"] == "circuit_breaker"]
        jh = [r for r in before["requirements"] if r["attest_item"] == "journaling_habit"]
        assert len(cb) == 1 and len(jh) == 1, "U0 must map onto the two items it names"
        assert not cb[0]["met"] and not jh[0]["met"]
        assert cb[0]["link"] == "/gate" and before["attest_pending"] is True

        await _attest(c, h, "circuit_breaker")
        mid = (await _stage_map(c, h, "unified"))["U0"]
        assert [r["met"] for r in mid["requirements"] if r["attest_item"] == "circuit_breaker"] == [True]
        assert mid["attest_pending"] is True  # journaling_habit still open

        await _attest(c, h, "journaling_habit")
        after = (await _stage_map(c, h, "unified"))["U0"]
        assert after["attest_pending"] is False
        assert all(r["met"] for r in after["requirements"] if r["attest"])

        # Revoking it on /gate un-meets the /path row — one source of truth.
        await _attest(c, h, "circuit_breaker", False)
        revoked = (await _stage_map(c, h, "unified"))["U0"]
        assert revoked["attest_pending"] is True


async def test_u4_expectancy_row_is_earned_from_the_journal_not_attested():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}u4")
        before = (await _stage_map(c, h, "unified"))["U4"]
        derived = [r for r in before["requirements"] if r["derived"]]
        assert len(derived) == 1 and not derived[0]["met"]
        assert derived[0]["attest"] is False and derived[0]["link"] == "/expectancy"

        await c.post("/api/journal", headers=h, json={
            "entry_date": "2026-07-20", "instrument": "NQ", "mode": "backtest",
            "entry_model": "london", "r_multiple": -0.5, "rr_planned": 2.0,
        })
        after = (await _stage_map(c, h, "unified"))["U4"]
        row = [r for r in after["requirements"] if r["derived"]][0]
        # A NEGATIVE expectancy still satisfies "can compute" — U4's actual bar.
        assert row["met"] and "-0.50R" in row["detail"]

    async with AsyncSessionLocal() as db:
        from app.models.journal_entry import JournalEntry
        uid = (await db.execute(
            select(User.id).where(User.discord_id == f"{_PREFIX}u4"))).scalar_one()
        await db.execute(delete(JournalEntry).where(JournalEntry.user_id == uid))
        await db.commit()


# ---------------------------------------------------------------------------
# No regression: the real lock chain does not move
# ---------------------------------------------------------------------------

async def test_lock_chain_on_the_real_seed_is_unchanged_by_attesting():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}locks")
        tracks = ("unified", "aura", "ict_course")
        before = {
            t: {code: (s["locked"], s["auto_met"]) for code, s in (await _stage_map(c, h, t)).items()}
            for t in tracks
        }
        for item in ("risk_precommitted", "sim_track_record", "journaling_habit", "circuit_breaker"):
            await _attest(c, h, item)
        after = {
            t: {code: (s["locked"], s["auto_met"]) for code, s in (await _stage_map(c, h, t)).items()}
            for t in tracks
        }
        assert before == after


# ---------------------------------------------------------------------------
# Drift guards against the seeded curriculum
# ---------------------------------------------------------------------------

async def test_every_6a_map_key_exists_in_the_seeded_curriculum():
    async with AsyncSessionLocal() as db:
        seeded = {
            (t.track, t.stage_code)
            for t in (await db.execute(select(TrackStage))).scalars().all()
        }
    keys = (
        set(stages.STAGE_ATTESTATIONS)
        | set(stages.STAGE_EVIDENCE)
        | set(stages.STAGE_UNWIRED)
    )
    assert keys, "the 6a maps must not be empty"
    assert keys <= seeded, f"6a maps reference unseeded stages: {keys - seeded}"


async def test_no_seeded_stage_is_left_with_an_empty_checklist():
    """A stage with no requirements would make `all()` read vacuously — every
    seeded stage must emit at least one row (the fail-closed rule from 5g)."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}nonempty")
        for track in ("unified", "aura", "ict_course"):
            for code, s in (await _stage_map(c, h, track)).items():
                assert s["requirements"], f"{track}/{code} has an empty checklist"


async def test_concept_less_stages_are_all_wired_or_explicitly_unwired():
    """Every stage with no concepts of its own carries either derived evidence, a
    mapped /gate attestation, or an explicit STAGE_UNWIRED note — never a silent
    placeholder."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}conceptless")
        for track in ("unified", "aura", "ict_course"):
            for code, s in (await _stage_map(c, h, track)).items():
                if s["total"] != 0:
                    continue
                rows = s["requirements"]
                wired = any(r["derived"] or r["attest_item"] for r in rows)
                declared = (track, code) in stages.STAGE_UNWIRED
                assert wired or declared, f"{track}/{code} is an undeclared dead checkbox"


# ---------------------------------------------------------------------------
# /path and /today agree (the planner reads the same evidence)
# ---------------------------------------------------------------------------

async def test_foundation_habit_overlay_stops_once_the_foundation_bar_is_really_met():
    """The scheduler already intended the discipline overlay to run "until the gate
    holds" — before 6a that gate could never hold, so habits recurred forever. The
    COMPUTED (future) plan is read here, since today's items are deliberately
    FROZEN once materialized (the 5e-2 persist-vs-compute hybrid keeps the
    adherence record); `regenerate` is what rebuilds today."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}habits")
        await c.put("/api/preferences", headers=h, json={
            "timezone": "UTC", "mon_minutes": 60, "tue_minutes": 60, "wed_minutes": 60,
            "thu_minutes": 60, "fri_minutes": 60, "sat_minutes": 60, "sun_minutes": 60,
            "max_session_minutes": 45, "blackout_dates": [], "target_go_live_date": None,
            "active_track": "aura",
        })

        def habits(payload):
            return [i for i in payload["items"] if i["activity"] == "habit"]

        async def computed_future():
            """A future window — COMPUTED by the scheduler, never frozen."""
            today = date.fromisoformat((await c.get("/api/plan/today", headers=h)).json()["date"])
            day = (today + timedelta(days=3)).isoformat()
            return (await c.get("/api/plan", headers=h,
                                params={"from": day, "to": day})).json()

        # 1. Nothing done → the discipline overlay is prescribed, today and ahead.
        assert habits((await c.get("/api/plan/today", headers=h)).json())
        assert habits(await computed_future())

        # 2. Bring every A0 concept to Can-mark (the objective half of the bar).
        #    Phase E2: reps are no longer a field on this PATCH — the concept has
        #    to carry EVIDENCE before the ladder will advance.
        for i, concept in enumerate(await _stage_concepts("aura", "A0")):
            await give_concept_reps(c, h, concept.id, 999, seed=6100 + i)
            r = await c.patch("/api/progress", headers=h, json={
                "concept_id": str(concept.id), "ladder_stage": 2, "confidence": 3,
            })
            assert r.status_code == 200, r.text

        a0 = (await _stage_map(c, h, "aura"))["A0"]
        assert a0["auto_met"] is True and a0["met"] is False  # attestations still open
        assert habits(await computed_future()), \
            "habits must continue while the behavioural half is unmet"

        # 3. Tick the two /gate attestations A0's bar names → /path says met …
        await _attest(c, h, "circuit_breaker")
        await _attest(c, h, "journaling_habit")
        a0 = (await _stage_map(c, h, "aura"))["A0"]
        assert a0["met"] is True and a0["attest_pending"] is False

        # … and the planner agrees: the overlay stops (it never could before 6a).
        assert not habits(await computed_future()), \
            "the computed plan must stop prescribing habits once A0 is met"

        # Regenerating rebuilds today from the same evidence — habits gone there too.
        regen = (await c.post("/api/plan/regenerate", headers=h)).json()
        assert not habits(regen)
