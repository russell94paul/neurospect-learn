"""API tests for the Readiness-to-Live Gate (Phase 5g).

The DB-integration counterpart to test_gate.py's pure-math tests: exercised
against the real (seeded) dev DB via an in-process ASGI transport and debug JWTs
(DEBUG=true), mirroring test_journal_api.py. Each test uses its own debug user
(discord_id prefixed `5gt-`) for per-user isolation; an autouse fixture
hard-deletes every `5gt-` user's gate/journal/progress rows afterwards so the dev
DB is left clean.

The load-bearing test is `test_hand_built_fixture_clears_then_each_flip_blocks`:
it builds a FULLY satisfied London model against the real 74-concept seed, proves
it clears, then flips each of the four inputs in turn and proves the verdict goes
back to blocked with the right reason — the evidence-gated core of Phase 5g.
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
from app.models.concept import Concept
from app.models.concept_progress import ConceptProgress
from app.models.gate_attestation import GateAttestation
from app.models.journal_entry import JournalEntry
from app.models.user import User
from app.services import gate

_test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(bind=_test_engine, expire_on_commit=False)

_PREFIX = "5gt-"
MODEL = "london"
SAMPLE = 50


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
            await db.execute(delete(JournalEntry).where(JournalEntry.user_id == uid))
            await db.execute(delete(ConceptProgress).where(ConceptProgress.user_id == uid))
            await db.execute(delete(GateAttestation).where(GateAttestation.user_id == uid))
        await db.commit()


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


# ---------------------------------------------------------------------------
# Fixture builders — write progress DIRECTLY (the gate reads ladder position; the
# ladder-advance enforcement is the /api/progress endpoint's own tested concern).
# ---------------------------------------------------------------------------

async def _set_ladder(user_id, slugs: dict[str, int]):
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Concept).where(Concept.slug.in_(list(slugs)))
        )).scalars().all()
        found = {c.slug: c for c in rows}
        assert set(found) == set(slugs), f"missing seed concepts: {set(slugs) - set(found)}"
        for slug, ladder in slugs.items():
            c = found[slug]
            existing = (await db.execute(
                select(ConceptProgress).where(
                    ConceptProgress.user_id == user_id,
                    ConceptProgress.concept_id == c.id,
                    ConceptProgress.is_deleted.is_(False),
                )
            )).scalar_one_or_none()
            if existing:
                existing.ladder_stage = ladder
            else:
                db.add(ConceptProgress(
                    user_id=user_id, concept_id=c.id, ladder_stage=ladder,
                    # `legacy_reps` (Phase E2, Alembic 0009): reps claimed before
                    # the evidence layer existed. This fixture inserts a ladder
                    # position directly to test the GATE, not the rep gate — the
                    # evidence-backed path is covered in test_evidence_api.py.
                    confidence=5, legacy_reps=200,
                ))
        await db.commit()


async def _core_slugs() -> list[str]:
    """The real anchor-track core set the gate requires at Backtested+."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Concept.slug).where(
                Concept.track == gate.ANCHOR_TRACK,
                Concept.is_core.is_(True),
                Concept.watch_only.is_(False),
                Concept.u_stage.in_(list(gate.CORE_STAGES)),
            )
        )).scalars().all()
    return list(rows)


async def _satisfy_concepts(user_id) -> list[str]:
    cores = await _core_slugs()
    assert len(cores) >= 5, cores
    ladder = dict.fromkeys(cores, gate.BACKTESTED)
    ladder[gate.ENTRY_MODEL_CONCEPTS[MODEL][0]] = gate.LIVE_READY
    await _set_ladder(user_id, ladder)
    return cores


async def _log_backtests(c, h, *, wins=30, losses=20, model=MODEL, mode="backtest"):
    """Positive-expectancy sample: 60% at +2R / -1R, planned R:R 2 → +0.80R."""
    for i in range(wins + losses):
        win = i < wins
        r = await c.post("/api/journal", headers=h, json={
            "entry_date": "2026-07-20",
            "instrument": "NQ",
            "mode": mode,
            "entry_model": model,
            "r_multiple": 2.0 if win else -1.0,
            "rr_planned": 2.0,
            "outcome": "win" if win else "loss",
        })
        assert r.status_code == 201, r.text


async def _attest_all(c, h, value=True):
    for item in gate.BEHAVIOURAL_KEYS:
        r = await c.patch("/api/gate/attestations", headers=h,
                          json={"item": item, "attested": value})
        assert r.status_code == 200, r.text


def _model(body, name=MODEL):
    return next(m for m in body["models"] if m["entry_model"] == name)


# ---------------------------------------------------------------------------
# Attestations
# ---------------------------------------------------------------------------

async def test_attestation_round_trip_and_revoke():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}attest")

        lst = (await c.get("/api/gate/attestations", headers=h)).json()
        assert [a["item"] for a in lst] == list(gate.BEHAVIOURAL_KEYS)
        assert all(a["attested"] is False for a in lst)  # lazy: unattested reads false

        r = await c.patch("/api/gate/attestations", headers=h, json={
            "item": "risk_precommitted", "attested": True, "note": "Notion risk page",
        })
        assert r.status_code == 200, r.text
        assert r.json()["attested"] is True and r.json()["note"] == "Notion risk page"

        again = (await c.get("/api/gate/attestations", headers=h)).json()
        by_item = {a["item"]: a for a in again}
        assert by_item["risk_precommitted"]["attested"] is True
        assert by_item["risk_precommitted"]["note"] == "Notion risk page"
        assert by_item["circuit_breaker"]["attested"] is False

        # Revocable — and the unique partial index means it updates in place.
        rev = await c.patch("/api/gate/attestations", headers=h, json={
            "item": "risk_precommitted", "attested": False,
        })
        assert rev.status_code == 200 and rev.json()["attested"] is False
        final = (await c.get("/api/gate/attestations", headers=h)).json()
        assert {a["item"]: a["attested"] for a in final}["risk_precommitted"] is False

    async with AsyncSessionLocal() as db:
        uid = await _user_id(f"{_PREFIX}attest")
        rows = (await db.execute(select(GateAttestation).where(
            GateAttestation.user_id == uid, GateAttestation.is_deleted.is_(False)
        ))).scalars().all()
        assert len(rows) == 1  # upserted in place, not duplicated


async def test_unknown_attestation_item_is_rejected():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}baditem")
        r = await c.patch("/api/gate/attestations", headers=h,
                          json={"item": "i_am_ready", "attested": True})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# The gate verdict
# ---------------------------------------------------------------------------

async def test_fresh_user_sees_every_model_blocked():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}fresh")
        body = (await c.get("/api/gate", headers=h)).json()
        assert body["anchor_track"] == "unified" and body["credit_track"] is None
        assert body["sample_target"] == SAMPLE and body["sample_stretch"] == 100
        assert [m["entry_model"] for m in body["models"]] == list(gate.ALL_MODELS)
        assert body["any_cleared"] is False
        assert all(not m["cleared"] for m in body["models"])
        m = _model(body)
        assert m["blocking"], "a blocked model must say what is blocking it"
        assert m["backtest_n"] == 0


async def test_hand_built_fixture_clears_then_each_flip_blocks():
    """THE evidence-gated test: build a fully satisfied model, prove it clears,
    then flip each of (a1) core ladder, (a2) load-bearing ladder, (b) sample,
    (c) attestation and prove each one blocks with the right reason."""
    did = f"{_PREFIX}clear"
    async with await _client() as c:
        h = await _token(c, did)
        uid = await _user_id(did)

        cores = await _satisfy_concepts(uid)
        await _log_backtests(c, h)
        await _attest_all(c, h)

        body = (await c.get("/api/gate", headers=h)).json()
        m = _model(body)
        assert m["cleared"] is True, m["blocking"]
        assert (m["concepts_met"], m["evidence_met"], m["behaviour_met"]) == (True, True, True)
        assert m["blocking"] == []
        assert m["backtest_n"] == SAMPLE
        assert m["backtest_expectancy"] == 0.8
        assert m["backtest_win_rate"] == 0.6
        assert body["any_cleared"] is True
        # Only the model whose own concept is Live-ready clears.
        assert [x["entry_model"] for x in body["models"] if x["cleared"]] == [MODEL]

        # ---- flip (c): revoke one attestation ----------------------------
        await c.patch("/api/gate/attestations", headers=h,
                      json={"item": "circuit_breaker", "attested": False})
        m = _model((await c.get("/api/gate", headers=h)).json())
        assert m["cleared"] is False and m["behaviour_met"] is False
        assert (m["concepts_met"], m["evidence_met"]) == (True, True)
        assert any("not attested" in b for b in m["blocking"])
        await _attest_all(c, h)  # restore

        # ---- flip (b): drop the sample below target ----------------------
        entries = (await c.get("/api/journal", headers=h, params={"mode": "backtest"})).json()
        victim = entries[0]["id"]
        assert (await c.delete(f"/api/journal/{victim}", headers=h)).status_code in (200, 204)
        m = _model((await c.get("/api/gate", headers=h)).json())
        assert m["cleared"] is False and m["evidence_met"] is False
        assert m["backtest_n"] == SAMPLE - 1
        assert any(f"{SAMPLE - 1}/{SAMPLE}" in b for b in m["blocking"])
        await _log_backtests(c, h, wins=1, losses=0)  # restore the sample
        assert _model((await c.get("/api/gate", headers=h)).json())["cleared"] is True

        # ---- flip (a2): the model's own concept below Live-ready ---------
        model_slug = gate.ENTRY_MODEL_CONCEPTS[MODEL][0]
        await _set_ladder(uid, {model_slug: gate.BACKTESTED})
        m = _model((await c.get("/api/gate", headers=h)).json())
        assert m["cleared"] is False and m["concepts_met"] is False
        unmet = [r for r in m["requirements"] if r["source"] == "concepts" and not r["met"]]
        assert [r["concept_slug"] for r in unmet] == [model_slug]
        assert unmet[0]["required_ladder"] == 4 and unmet[0]["actual_ladder"] == 3
        await _set_ladder(uid, {model_slug: gate.LIVE_READY})  # restore

        # ---- flip (a1): a core concept below Backtested ------------------
        await _set_ladder(uid, {cores[0]: gate.CAN_MARK})
        m = _model((await c.get("/api/gate", headers=h)).json())
        assert m["cleared"] is False and m["concepts_met"] is False
        unmet = [r for r in m["requirements"] if r["source"] == "concepts" and not r["met"]]
        assert [r["concept_slug"] for r in unmet] == [cores[0]]
        assert any("concept requirement" in b or "concept requirements" in b
                   for b in m["blocking"])


async def test_attesting_everything_cannot_clear_without_evidence():
    """Non-overridability against the real DB: all four boxes ticked and the full
    concept ladder satisfied still will not clear with no backtest sample."""
    did = f"{_PREFIX}noover"
    async with await _client() as c:
        h = await _token(c, did)
        uid = await _user_id(did)
        await _satisfy_concepts(uid)
        await _attest_all(c, h)

        m = _model((await c.get("/api/gate", headers=h)).json())
        assert (m["concepts_met"], m["behaviour_met"]) == (True, True)
        assert m["evidence_met"] is False and m["cleared"] is False
        assert m["backtest_n"] == 0

        # An unknown `cleared` field in the only write body changes nothing.
        r = await c.patch("/api/gate/attestations", headers=h, json={
            "item": "risk_precommitted", "attested": True, "cleared": True,
        })
        assert r.status_code == 200 and "cleared" not in r.json()
        assert _model((await c.get("/api/gate", headers=h)).json())["cleared"] is False


async def test_negative_expectancy_blocks_despite_a_big_sample():
    did = f"{_PREFIX}negexp"
    async with await _client() as c:
        h = await _token(c, did)
        uid = await _user_id(did)
        await _satisfy_concepts(uid)
        await _attest_all(c, h)
        await _log_backtests(c, h, wins=10, losses=40)  # n=50, −0.40R

        m = _model((await c.get("/api/gate", headers=h)).json())
        assert m["backtest_n"] == SAMPLE and m["backtest_expectancy"] == -0.4
        assert m["evidence_met"] is False and m["cleared"] is False


async def test_frontier_concepts_are_never_requirements():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}frontier")
        body = (await c.get("/api/gate", headers=h)).json()

        assert body["frontier"], "the seeded U5 frontier must be surfaced"
        frontier_slugs = {f["slug"] for f in body["frontier"]}
        assert all(f["u_stage"] == "U5" for f in body["frontier"])

        for m in body["models"]:
            req_slugs = {r["concept_slug"] for r in m["requirements"] if r["concept_slug"]}
            assert not (req_slugs & frontier_slugs), m["entry_model"]


async def test_credit_track_only_tightens():
    """Progress made on the unified track counts by default; restricting credit to
    another track can only remove evidence, never add it."""
    did = f"{_PREFIX}track"
    async with await _client() as c:
        h = await _token(c, did)
        uid = await _user_id(did)
        await _satisfy_concepts(uid)
        await _log_backtests(c, h)
        await _attest_all(c, h)

        assert _model((await c.get("/api/gate", headers=h)).json())["cleared"] is True
        tightened = _model(
            (await c.get("/api/gate", headers=h, params={"track": "aura"})).json()
        )
        assert tightened["cleared"] is False
        assert tightened["concepts_met"] is False

        bad = await c.get("/api/gate", headers=h, params={"track": "nope"})
        assert bad.status_code == 404


async def test_per_user_isolation():
    a_did, b_did = f"{_PREFIX}iso-a", f"{_PREFIX}iso-b"
    async with await _client() as c:
        ha = await _token(c, a_did)
        hb = await _token(c, b_did)
        uid_a = await _user_id(a_did)

        await _satisfy_concepts(uid_a)
        await _log_backtests(c, ha)
        await _attest_all(c, ha)

        assert _model((await c.get("/api/gate", headers=ha)).json())["cleared"] is True

        body_b = (await c.get("/api/gate", headers=hb)).json()
        assert body_b["any_cleared"] is False
        mb = _model(body_b)
        assert mb["backtest_n"] == 0 and mb["concepts_met"] is False
        assert all(a["attested"] is False for a in body_b["attestations"])


async def test_corroboration_reflects_the_journal():
    did = f"{_PREFIX}corrob"
    async with await _client() as c:
        h = await _token(c, did)
        await _log_backtests(c, h, wins=2, losses=1)
        await _log_backtests(c, h, wins=1, losses=0, mode="live")

        corr = (await c.get("/api/gate", headers=h)).json()["corroboration"]
        assert corr["entries_logged"] == 4
        assert corr["entries_closed"] == 4
        assert corr["backtest_entries"] == 3 and corr["live_entries"] == 1
        assert corr["journaling_days"] == 1
        assert corr["last_entry_date"] == "2026-07-20"


async def test_no_token_is_403():
    async with await _client() as c:
        assert (await c.get("/api/gate")).status_code == 403
        assert (await c.get("/api/gate/attestations")).status_code == 403
        assert (await c.patch("/api/gate/attestations",
                              json={"item": "risk_precommitted", "attested": True})).status_code == 403
