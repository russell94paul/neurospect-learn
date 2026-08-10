"""The pre-commitment ledger + the M6 wiring (Phase E5), against the REAL seed.

Same harness as test_stages_api.py: in-process ASGI transport, debug JWTs, one
throwaway user per test (`e5p-`), hard-cleaned afterwards.

The pure calibration arithmetic is pinned DB-free in tests/test_calibration.py.
What only this layer can prove is the part the whole phase rests on:

  * **A prediction cannot be back-dated into a win.** Not "the API does not offer
    it" — there is no PATCH route, no DELETE route, no `is_deleted` column, and the
    `0011` freeze trigger refuses an UPDATE even from raw SQL. Four independent
    attempts, each expected to fail for a different reason.
  * **`STAGE_UNWIRED` is empty and M6 is earned rather than declared** — E1's
    acceptance test for the whole workstream, asserted through the real
    `/api/stages` response rather than by reading the map.
  * **M6 is met even when every single call was WRONG.** The bar is commitment, not
    correctness (design §6): making a losing call cost a stage would teach the user
    to stop writing calls down, which is the opposite of the point.
  * **No rep is minted anywhere in here** (invariant 5).
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.deps import get_db
from app.main import app
from app.models.concept_progress import ConceptProgress
from app.models.evidence import EvidenceAsset
from app.models.prediction import Prediction
from app.models.user import User
from app.services import stages

_test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(bind=_test_engine, expire_on_commit=False)

_PREFIX = "e5p-"
_T1 = stages.TAPE_STUDY_DRILLS[0]


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
            await db.execute(delete(Prediction).where(Prediction.user_id == uid))
            await db.execute(delete(ConceptProgress).where(ConceptProgress.user_id == uid))
            await db.execute(delete(EvidenceAsset).where(EvidenceAsset.user_id == uid))
        await db.commit()


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _token(c, discord_id):
    r = await c.post("/auth/debug/token", json={"discord_id": discord_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _call_body(drill_ref: str = _T1, **over) -> dict:
    body = {
        "drill_ref": drill_ref,
        "session_label": "comparable no-news Monday",
        "instrument": "NQ",
        "bias": "long",
        "dol": "PDH 20134.50",
        "entry_model": "consolidation",
        "target": "20180.00",
    }
    body.update(over)
    return body


def _reveal(**over) -> dict:
    body = {
        "outcome_bias": "long",
        "dol_hit": True,
        "model_played_out": True,
        "target_hit": True,
    }
    body.update(over)
    return body


async def _commit(c, h, drill_ref: str = _T1, **over) -> dict:
    r = await c.post("/api/predictions", headers=h, json=_call_body(drill_ref, **over))
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# The commitment is the server's, not the client's
# ---------------------------------------------------------------------------

async def test_the_server_stamps_the_commitment():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}stamp")
        row = await _commit(c, h)
        assert row["committed_at"], "a commitment with no timestamp proves nothing"
        assert row["resolved_at"] is None and row["resolved"] is False
        assert row["seconds_to_reveal"] is None
        # Nothing is scored before the reveal — not even as a zero.
        assert row["bias_correct"] is None and row["target_correct"] is None


@pytest.mark.parametrize("field", ["committed_at", "resolved_at"])
async def test_a_client_supplied_timestamp_is_refused_BY_NAME(field):
    """A 422 that says "extra inputs are not permitted" teaches nothing. This one
    has to say why the server owns the clock — the same courtesy E2 extends to a
    `reps` write."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}clock")
        r = await c.post(
            "/api/predictions", headers=h,
            json=_call_body(**{field: "2020-01-01T00:00:00Z"}),
        )
        assert r.status_code == 422, r.text
        assert field in r.text
        assert "server" in r.text.lower()


# ---------------------------------------------------------------------------
# THE HEADLINE: a prediction cannot be back-dated into a win
# ---------------------------------------------------------------------------

async def test_no_route_can_edit_or_delete_a_committed_call():
    """Attempt 1 — through the API surface. There must be no PATCH/PUT/DELETE on a
    prediction at all, so a future session cannot "add the missing endpoint"
    without deliberately removing this test."""
    offenders = [
        (r.path, sorted(m for m in r.methods if m not in {"HEAD", "OPTIONS"}))
        for r in app.routes
        if getattr(r, "path", "").startswith("/api/predictions")
        and {"PATCH", "PUT", "DELETE"} & getattr(r, "methods", set())
    ]
    assert offenders == [], f"a committed call must be immutable, found: {offenders}"


async def test_the_database_refuses_to_edit_the_call_after_commit():
    """Attempt 2 — under the API, in raw SQL, which is the only attempt that proves
    the property is STRUCTURAL rather than a matter of router discipline."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}freeze")
        row = await _commit(c, h)

    for column, value in (
        ("bias", "'short'::prediction_bias"),
        ("target", "'19000.00'"),
        ("dol", "'PDL 19000.00'"),
        ("entry_model", "'london'::entry_model"),
        ("drill_ref", f"'{stages.TAPE_STUDY_DRILLS[1]}'"),
        ("committed_at", "now() - interval '30 days'"),
    ):
        async with AsyncSessionLocal() as db:
            with pytest.raises(Exception) as exc:
                await db.execute(text(
                    f"UPDATE predictions SET {column} = {value} WHERE id = :id"
                ), {"id": row["id"]})
                await db.commit()
            assert "frozen" in str(exc.value), f"{column} was editable after commit"
            await db.rollback()


async def test_the_database_refuses_a_reveal_that_precedes_the_commitment():
    """Attempt 3 — the ordering property itself, as a schema CHECK."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}order")
        row = await _commit(c, h)

    async with AsyncSessionLocal() as db:
        with pytest.raises(Exception) as exc:
            await db.execute(text("""
                UPDATE predictions SET
                    resolved_at = committed_at - interval '1 hour',
                    outcome_bias = 'long', dol_hit = true,
                    model_played_out = true, target_hit = true
                WHERE id = :id
            """), {"id": row["id"]})
            await db.commit()
        assert "ck_predictions_reveal_follows_commit" in str(exc.value)
        await db.rollback()


async def test_a_reveal_is_accepted_exactly_once():
    """Attempt 4 — re-resolving until it lands. A second reveal is a 409, and the
    DB trigger refuses it too even if the router ever forgot."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}once")
        row = await _commit(c, h)
        first = await c.post(f"/api/predictions/{row['id']}/resolve", headers=h,
                             json=_reveal(outcome_bias="short", target_hit=False))
        assert first.status_code == 200, first.text
        assert first.json()["bias_correct"] is False

        again = await c.post(f"/api/predictions/{row['id']}/resolve", headers=h,
                             json=_reveal())
        assert again.status_code == 409, again.text
        assert "already resolved" in again.text

    async with AsyncSessionLocal() as db:
        with pytest.raises(Exception) as exc:
            await db.execute(text(
                "UPDATE predictions SET outcome_bias = 'long', target_hit = true WHERE id = :id"
            ), {"id": row["id"]})
            await db.commit()
        assert "already resolved" in str(exc.value)
        await db.rollback()


async def test_a_committed_call_has_no_soft_delete_to_hide_it_with():
    """The denominator of a ratio must not be shrinkable — so unlike every other
    user table here, `predictions` has NO `is_deleted` column. This asserts the
    absence, because adding one back would silently reopen the hole."""
    async with AsyncSessionLocal() as db:
        cols = set((await db.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='predictions'"
        ))).scalars().all())
    assert "is_deleted" not in cols and "deleted_at" not in cols, (
        "a deletable failure makes the calibration ratio gameable"
    )


async def test_a_half_written_reveal_is_refused_at_the_database():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}partial")
        row = await _commit(c, h)

    async with AsyncSessionLocal() as db:
        with pytest.raises(Exception) as exc:
            await db.execute(text(
                "UPDATE predictions SET resolved_at = now(), outcome_bias = 'long' WHERE id = :id"
            ), {"id": row["id"]})
            await db.commit()
        assert "ck_predictions_resolution_complete" in str(exc.value)
        await db.rollback()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

async def test_a_neutral_call_is_scored_not_excused():
    """"Stand aside" is a real call (T-04 names it), so it is graded like any
    other — right when nothing trended, wrong when something did."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}neutral")
        held = await _commit(c, h, bias="neutral")
        r = await c.post(f"/api/predictions/{held['id']}/resolve", headers=h,
                         json=_reveal(outcome_bias="neutral"))
        assert r.json()["bias_correct"] is True

        missed = await _commit(c, h, stages.TAPE_STUDY_DRILLS[1], bias="neutral")
        r = await c.post(f"/api/predictions/{missed['id']}/resolve", headers=h,
                         json=_reveal(outcome_bias="long"))
        assert r.json()["bias_correct"] is False, "declining to commit is not a free pass"


async def test_calibration_reports_the_ledger_and_its_gaps():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}calib")
        empty = (await c.get("/api/calibration", headers=h)).json()
        assert empty["committed"] == 0
        assert empty["accuracy"] is None, "0% would be a claim, not a measurement"
        assert empty["tape_drills_total"] == 14 and empty["tape_drills_resolved"] == 0

        a = await _commit(c, h, stages.TAPE_STUDY_DRILLS[0])
        await c.post(f"/api/predictions/{a['id']}/resolve", headers=h,
                     json=_reveal(dol_hit=False, target_hit=False))
        await _commit(c, h, stages.TAPE_STUDY_DRILLS[1])  # left unresolved on purpose

        score = (await c.get("/api/calibration", headers=h)).json()
        assert (score["committed"], score["resolved"], score["unresolved"]) == (2, 1, 1)
        assert score["resolution_rate"] == 0.5
        assert score["accuracy"] == 0.5  # 2 of 4 component judgements
        by_key = {comp["key"]: comp for comp in score["components"]}
        assert by_key["bias"]["accuracy"] == 1.0
        assert by_key["target"]["accuracy"] == 0.0
        assert score["tape_drills_committed"] == 2 and score["tape_drills_resolved"] == 1


async def test_predictions_are_per_user_and_need_a_token():
    async with await _client() as c:
        mine = await _token(c, f"{_PREFIX}mine")
        theirs = await _token(c, f"{_PREFIX}theirs")
        row = await _commit(c, mine)

        assert (await c.get("/api/predictions", headers=theirs)).json() == []
        assert (await c.get("/api/calibration", headers=theirs)).json()["committed"] == 0
        stolen = await c.post(f"/api/predictions/{row['id']}/resolve", headers=theirs,
                              json=_reveal())
        assert stolen.status_code == 404

        assert (await c.get("/api/predictions")).status_code == 403
        assert (await c.get("/api/calibration")).status_code == 403
        assert (await c.post("/api/predictions", json=_call_body())).status_code == 403


async def test_an_unknown_drill_is_refused():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}nodrill")
        r = await c.post("/api/predictions", headers=h,
                         json=_call_body("ict-course T-99"))
        assert r.status_code == 404 and "T-99" in r.text


# ---------------------------------------------------------------------------
# Invariant 5 — this whole table mints no reps
# ---------------------------------------------------------------------------

async def test_committing_and_resolving_a_call_mints_no_rep():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}norep")

        async def drill_reps() -> dict:
            r = await c.get("/api/drills", headers=h, params={"track": "ict_course"})
            assert r.status_code == 200, r.text
            return {d["drill_ref"]: d["reps"] for d in r.json()}

        before = await drill_reps()
        for ref in stages.TAPE_STUDY_DRILLS[:3]:
            row = await _commit(c, h, ref)
            await c.post(f"/api/predictions/{row['id']}/resolve", headers=h, json=_reveal())
        assert await drill_reps() == before, "a prediction is not a rep"


# ---------------------------------------------------------------------------
# E1's ACCEPTANCE TEST — M6 is earned, and STAGE_UNWIRED is empty
# ---------------------------------------------------------------------------

async def _m6(c, h) -> dict:
    r = await c.get("/api/stages", headers=h, params={"track": "ict_course"})
    assert r.status_code == 200, r.text
    return next(s for s in r.json() if s["stage_code"] == "M6")


async def test_m6_is_no_longer_a_dead_checkbox():
    """Before E5 this row was `attest=True, met=False` and could NEVER become met —
    STAGE_UNWIRED said so honestly. It is now derived from the ledger."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}m6dead")
        st = await _m6(c, h)
        rows = st["requirements"]
        assert len(rows) == 1
        row = rows[0]
        assert row["derived"] is True, "M6's bar must be earned, not attested"
        assert row["attest"] is False and row["attest_item"] is None
        assert row["met"] is False
        assert "0/14" in row["detail"]
        assert "T-01" in row["detail"], "the detail must say what is still uncalled"


async def test_m6_becomes_met_only_when_all_fourteen_were_called_before_the_reveal():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}m6earn")

        # Commit all 14 but resolve only 13 — the bar is commitment AND reveal.
        ids = {ref: (await _commit(c, h, ref))["id"] for ref in stages.TAPE_STUDY_DRILLS}
        st = await _m6(c, h)
        assert st["requirements"][0]["met"] is False
        assert "14 calls committed and awaiting" in st["requirements"][0]["detail"]

        for ref in stages.TAPE_STUDY_DRILLS[:-1]:
            r = await c.post(f"/api/predictions/{ids[ref]}/resolve", headers=h, json=_reveal())
            assert r.status_code == 200, r.text
        st = await _m6(c, h)
        assert st["requirements"][0]["met"] is False
        assert "13/14" in st["requirements"][0]["detail"]
        assert "T-14" in st["requirements"][0]["detail"]

        last = stages.TAPE_STUDY_DRILLS[-1]
        await c.post(f"/api/predictions/{ids[last]}/resolve", headers=h, json=_reveal())
        st = await _m6(c, h)
        assert st["requirements"][0]["met"] is True
        assert "14/14" in st["requirements"][0]["detail"]


async def test_m6_is_met_even_when_every_single_call_was_wrong():
    """THE §6 DISCIPLINE. The bar is that you committed and then scored honestly —
    not that you were right. Gating a stage on accuracy would make the calibration
    score a currency and teach the user to stop writing down calls they might lose
    (Deci, Koestner & Ryan 1999)."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}m6wrong")
        for ref in stages.TAPE_STUDY_DRILLS:
            row = await _commit(c, h, ref, bias="long")
            r = await c.post(f"/api/predictions/{row['id']}/resolve", headers=h, json=_reveal(
                outcome_bias="short", dol_hit=False, model_played_out=False, target_hit=False,
            ))
            assert r.status_code == 200, r.text

        st = await _m6(c, h)
        assert st["requirements"][0]["met"] is True, "an honest wrong call is still the work"
        score = (await c.get("/api/calibration", headers=h)).json()
        assert score["accuracy"] == 0.0, "…and the calibration score says so, plainly"
        assert score["resolution_rate"] == 1.0


async def test_wiring_m6_moves_met_only_never_auto_met_or_the_lock_chain():
    """M6 is concept-less, so `auto_met` stays False and the ict_course lock chain
    is byte-identical — invariant 6. Behavioural evidence must never be able to
    freeze or advance a track."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}m6lock")

        async def chain() -> dict:
            r = await c.get("/api/stages", headers=h, params={"track": "ict_course"})
            return {s["stage_code"]: (s["auto_met"], s["locked"]) for s in r.json()}

        before = await chain()
        for ref in stages.TAPE_STUDY_DRILLS:
            row = await _commit(c, h, ref)
            await c.post(f"/api/predictions/{row['id']}/resolve", headers=h, json=_reveal())
        after = await chain()
        assert after == before, "the lock chain moved on prediction evidence"
        assert before["M6"][0] is False, "M6 is concept-less: auto_met must stay False"


async def test_stage_unwired_is_empty_which_is_the_workstreams_acceptance_test():
    """learning-enforcement.md §9: "`STAGE_UNWIRED` becomes empty — E1's acceptance
    test". Asserted here rather than eyeballed, and paired with the live check that
    no concept-less stage is left silently dead."""
    assert stages.STAGE_UNWIRED == {}, (
        f"still unwired: {sorted(stages.STAGE_UNWIRED)} — E1's acceptance test is unmet"
    )
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}unwired")
        for track in ("unified", "aura", "ict_course"):
            r = await c.get("/api/stages", headers=h, params={"track": track})
            for s in r.json():
                if s["total"] != 0:
                    continue
                rows = s["requirements"]
                assert rows, f"{track}/{s['stage_code']} has an empty checklist"
                assert any(x["derived"] or x["attest_item"] for x in rows), (
                    f"{track}/{s['stage_code']} is a dead checkbox with STAGE_UNWIRED empty"
                )
