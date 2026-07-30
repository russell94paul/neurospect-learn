"""API tests for the evidence layer (Phase E2) — capture, the derived reps, and
the bypasses that must not exist.

Same harness as test_missed_trades_api.py: in-process ASGI transport against the
real seeded dev DB with debug JWTs, one throwaway user per test (`e2t-`),
hard-cleaned afterwards.

Two tests carry the phase:

* `test_no_endpoint_can_mint_a_rep_without_evidence` — THE BYPASS TEST. All
  three historic rep-writing paths (`PATCH /api/drills`, `PATCH /api/progress`,
  `PATCH /api/plan/items/{id}`) are attacked and all three fail. If this ever
  passes only two of three, the workstream is theatre.
* `test_the_evidence_layer_never_moves_expectancy_or_the_gate` — the Phase-6
  evidence-gate pattern repeated: byte-identical `/api/analytics/*` + `/api/gate`
  across a full evidence write.
"""

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.deps import get_db
from app.main import app
from app.models.concept import Concept
from app.models.concept_progress import ConceptProgress
from app.models.drill import Drill
from app.models.drill_progress import DrillProgress
from app.models.evidence import EvidenceAsset
from app.models.journal_entry import JournalEntry
from app.models.missed_trade import MissedTrade
from app.models.plan_item import PlanItem
from app.models.study_preferences import StudyPreferences
from app.models.user import User
from app.services import storage as storage_service
from tests.evidence_helpers import chart_png, upload_evidence

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


_PREFIX = "e2t-"


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _token(c, discord_id):
    r = await c.post("/auth/debug/token", json={"discord_id": discord_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _user_id(discord_id) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        return (await db.execute(
            select(User.id).where(User.discord_id == discord_id)
        )).scalar_one()


async def _a_drill() -> Drill:
    async with AsyncSessionLocal() as db:
        return (await db.execute(
            select(Drill).where(Drill.track == "aura").order_by(Drill.sort_order)
        )).scalars().first()


async def _a_concept(slug: str | None = None) -> Concept:
    async with AsyncSessionLocal() as db:
        stmt = select(Concept).order_by(Concept.sort_order)
        if slug:
            stmt = stmt.where(Concept.slug == slug)
        return (await db.execute(stmt)).scalars().first()


async def _concept_with_a_rep_floor() -> Concept:
    """A seeded concept whose rep target parses to a real numeric floor — the
    only concepts where the ladder gate actually bites."""
    from app.services import rep_targets

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Concept).order_by(Concept.sort_order))).scalars().all()
    for c in rows:
        t = rep_targets.parse(c.rep_target)
        if t.has_floor and not c.watch_only and 1 < (t.count or 0) <= 200:
            return c
    raise AssertionError("no seeded concept carries a small numeric rep floor")


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(
            select(User.id).where(User.discord_id.like(f"{_PREFIX}%"))
        )).scalars().all()
        for uid in ids:
            await db.execute(delete(EvidenceAsset).where(EvidenceAsset.user_id == uid))
            await db.execute(delete(PlanItem).where(PlanItem.user_id == uid))
            await db.execute(delete(StudyPreferences).where(StudyPreferences.user_id == uid))
            await db.execute(delete(ConceptProgress).where(ConceptProgress.user_id == uid))
            await db.execute(delete(DrillProgress).where(DrillProgress.user_id == uid))
            await db.execute(delete(JournalEntry).where(JournalEntry.user_id == uid))
            await db.execute(delete(MissedTrade).where(MissedTrade.user_id == uid))
        await db.commit()


# ===========================================================================
# Capture
# ===========================================================================

async def test_upload_then_list_get_and_delete():
    drill = await _a_drill()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}crud")
        r = await upload_evidence(c, h, seed=1, reps=3,
                                  subject_type="drill", drill_ref=drill.drill_ref)
        assert r.status_code == 201, r.text
        got = r.json()
        assert got["subject_type"] == "drill" and got["subject_drill_ref"] == drill.drill_ref
        assert got["kind"] == "chart_markup"           # the default
        assert got["content_type"] == "image/png"       # SNIFFED, not claimed
        assert got["reps_claimed"] == 3 and got["url"]
        # Every asset lands with its deterministic grade already recorded.
        assert [g["grader"] for g in got["grades"]] == ["deterministic"]
        assert got["grades"][0]["state"] == "passed"
        eid = got["id"]

        assert (await c.get(f"/api/evidence/{eid}", headers=h)).json()["id"] == eid
        listed = (await c.get("/api/evidence", headers=h,
                              params={"drill_ref": drill.drill_ref})).json()
        assert [e["id"] for e in listed] == [eid]

        assert (await c.delete(f"/api/evidence/{eid}", headers=h)).status_code == 204
        assert (await c.get(f"/api/evidence/{eid}", headers=h)).status_code == 404
        assert (await c.get("/api/evidence", headers=h)).json() == []


async def test_the_content_type_comes_from_the_bytes_not_the_client():
    """A shell script announced as image/png is refused — the sniff decides."""
    drill = await _a_drill()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}sniff")
        r = await c.post(
            "/api/evidence", headers=h,
            files={"file": ("chart.png", b"#!/bin/sh\n" + b"x" * 3000, "image/png")},
            data={"subject_type": "drill", "drill_ref": drill.drill_ref},
        )
        assert r.status_code == 415
        assert r.json()["detail"]["code"] == "not_an_image"
        assert "not an image" in r.json()["detail"]["message"].lower()


async def test_duplicates_are_refused_WITH_A_REASON():
    drill = await _a_drill()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}dup")
        first = await upload_evidence(c, h, seed=2, subject_type="drill",
                                      drill_ref=drill.drill_ref)
        assert first.status_code == 201

        again = await upload_evidence(c, h, seed=2, subject_type="drill",
                                      drill_ref=drill.drill_ref)
        assert again.status_code == 409
        detail = again.json()["detail"]
        assert detail["code"] == "duplicate"
        assert detail["duplicate_of"] == first.json()["id"]
        assert "already uploaded" in detail["message"]

        # And it did not silently count: still exactly one rep.
        row = next(d for d in (await c.get("/api/drills", headers=h)).json()
                   if d["drill_ref"] == drill.drill_ref)
        assert row["reps"] == 1


async def test_a_near_identical_recrop_is_refused_by_the_perceptual_hash():
    """Different bytes, same capture — sha256 would let it through."""
    from io import BytesIO

    from PIL import Image

    drill = await _a_drill()
    original = chart_png(3)
    with Image.open(BytesIO(original)) as img:
        buf = BytesIO()
        img.crop((4, 2, img.width - 4, img.height - 2)).save(buf, format="PNG")
    recrop = buf.getvalue()
    assert recrop != original

    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}near")
        assert (await c.post(
            "/api/evidence", headers=h,
            files={"file": ("a.png", BytesIO(original), "image/png")},
            data={"subject_type": "drill", "drill_ref": drill.drill_ref},
        )).status_code == 201
        r = await c.post(
            "/api/evidence", headers=h,
            files={"file": ("b.png", BytesIO(recrop), "image/png")},
            data={"subject_type": "drill", "drill_ref": drill.drill_ref},
        )
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "near_duplicate"
        assert r.json()["detail"]["distance"] is not None


async def test_a_deleted_asset_frees_its_hash_but_cannot_inflate_the_count():
    """Delete + re-upload restores exactly the one rep it carried — the ledger
    is not a way to double-count."""
    drill = await _a_drill()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}redo")
        first = await upload_evidence(c, h, seed=4, reps=2, subject_type="drill",
                                      drill_ref=drill.drill_ref)
        assert first.status_code == 201

        async def reps():
            return next(d for d in (await c.get("/api/drills", headers=h)).json()
                        if d["drill_ref"] == drill.drill_ref)["reps"]

        assert await reps() == 2
        await c.delete(f"/api/evidence/{first.json()['id']}", headers=h)
        assert await reps() == 0
        again = await upload_evidence(c, h, seed=4, reps=2, subject_type="drill",
                                      drill_ref=drill.drill_ref)
        assert again.status_code == 201
        assert await reps() == 2


# ===========================================================================
# The DB CHECK fails closed — proven at the DATABASE, not just in Pydantic
# ===========================================================================

_INSERT = text("""
    INSERT INTO evidence_assets
        (user_id, subject_type, subject_drill_ref, concept_id, kind, storage_key,
         content_type, byte_size, sha256)
    VALUES
        (:uid, :st, :dref, :cid, 'chart_markup', 'k/1.png', 'image/png', 10, :sha)
""")


async def test_the_subject_check_fails_closed_in_the_database():
    """Zero subjects, two subjects, and a subject that disagrees with its
    discriminator are all rejected by the DB — the API guard is not the only one."""
    async with await _client() as c:
        await _token(c, f"{_PREFIX}chk")
    uid = await _user_id(f"{_PREFIX}chk")
    concept = await _a_concept()

    cases = {
        "zero subjects": dict(st="drill", dref=None, cid=None),
        "two subjects": dict(st="drill", dref="aura D1-a", cid=concept.id),
        "discriminator disagrees": dict(st="concept", dref="aura D1-a", cid=None),
    }
    for label, params in cases.items():
        async with AsyncSessionLocal() as db:
            with pytest.raises(IntegrityError) as exc:
                await db.execute(_INSERT, {
                    "uid": uid, "sha": f"{abs(hash(label)):064d}"[:64], **params
                })
                await db.commit()
            assert "ck_evidence_subject_exactly_one" in str(exc.value), label
            await db.rollback()

    # …and the valid shape is accepted, so the CHECK is not simply refusing all.
    async with AsyncSessionLocal() as db:
        await db.execute(_INSERT, {
            "uid": uid, "st": "drill", "dref": "aura D1-a", "cid": None,
            "sha": "f" * 64,
        })
        await db.commit()
        await db.execute(delete(EvidenceAsset).where(EvidenceAsset.user_id == uid))
        await db.commit()


async def test_the_api_refuses_an_ambiguous_or_mismatched_subject():
    concept = await _a_concept()
    drill = await _a_drill()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}subj")
        both = await upload_evidence(c, h, seed=5, subject_type="drill",
                                     drill_ref=drill.drill_ref, concept_id=concept.id)
        assert both.status_code == 422 and "exactly one" in both.json()["detail"]

        none = await upload_evidence(c, h, seed=6, subject_type="drill")
        assert none.status_code == 422

        mismatch = await upload_evidence(c, h, seed=7, subject_type="concept",
                                         drill_ref=drill.drill_ref)
        assert mismatch.status_code == 422

        unknown = await upload_evidence(c, h, seed=8, subject_type="drill",
                                        drill_ref="aura D9-zzz")
        assert unknown.status_code == 404


# ===========================================================================
# THE BYPASS TEST — no endpoint may mint a rep
# ===========================================================================

async def test_no_endpoint_can_mint_a_rep_without_evidence():
    """All three historic rep-writing paths, attacked.

    Before E2, `PATCH /api/drills` and `PATCH /api/progress` set `reps` outright
    and `PATCH /api/plan/items/{id}` incremented it on mark-done. Gating only the
    learning router would have left the planner as a rep-minting bypass and made
    the whole layer theatre — so `reps` was made DERIVED instead, and there is no
    write path left to guard.
    """
    drill = await _a_drill()
    concept = await _a_concept()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}bypass")

        # (1) PATCH /api/drills
        r = await c.patch("/api/drills", headers=h,
                          json={"drill_ref": drill.drill_ref, "reps": 50})
        assert r.status_code == 422, r.text
        assert "evidence" in json.dumps(r.json()).lower()

        # (2) PATCH /api/progress
        r = await c.patch("/api/progress", headers=h,
                          json={"concept_id": str(concept.id), "reps": 50})
        assert r.status_code == 422, r.text
        assert "/api/evidence" in json.dumps(r.json())

        # (3) PATCH /api/plan/items/{id} — mark-done, the sneaky one.
        await c.put("/api/preferences", headers=h, json={
            "timezone": "UTC", "max_session_minutes": 60, "active_track": "aura",
            **{f"{d}_minutes": 120 for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        })
        today = (await c.get("/api/plan/today", headers=h)).json()
        item = next(i for i in today["items"] if i["concept_id"])
        done = await c.patch(f"/api/plan/items/{item['id']}", headers=h,
                             json={"status": "done", "done_qty": 40})
        assert done.status_code == 200, done.text  # marking done still works …

        rows = (await c.get("/api/progress", headers=h)).json()
        assert all(p["reps"] == 0 for p in rows), "a rep was minted with no evidence"
        drills = (await c.get("/api/drills", headers=h)).json()
        assert all(d["reps"] == 0 for d in drills)

        # And the ONLY path that does work: evidence.
        await upload_evidence(c, h, seed=9, reps=4, subject_type="concept",
                              concept_id=concept.id)
        row = next(p for p in (await c.get("/api/progress", headers=h)).json()
                   if p["concept_id"] == str(concept.id))
        assert row["reps"] == 4 and row["reps_evidenced"] == 4 and row["reps_legacy"] == 0


async def test_the_ladder_gate_now_grades_on_evidence():
    concept = await _concept_with_a_rep_floor()
    from app.services import rep_targets
    floor = rep_targets.parse(concept.rep_target).count

    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}ladder")
        blocked = await c.patch("/api/progress", headers=h, json={
            "concept_id": str(concept.id), "ladder_stage": 2, "confidence": 3,
        })
        assert blocked.status_code == 422
        assert "evidenced" in blocked.json()["detail"]

        # Evidence up to the floor, then the same request succeeds.
        for i in range(0, floor, 100):
            await upload_evidence(c, h, seed=900 + i, reps=min(100, floor - i),
                                  subject_type="concept", concept_id=concept.id)
        ok = await c.patch("/api/progress", headers=h, json={
            "concept_id": str(concept.id), "ladder_stage": 2, "confidence": 3,
        })
        assert ok.status_code == 200, ok.text
        assert ok.json()["ladder_stage"] == 2 and ok.json()["reps_evidenced"] == floor


async def test_legacy_reps_are_preserved_and_reported_separately():
    """Alembic 0009 froze pre-evidence claims rather than deleting them, so no
    already-met stage un-meets — and the gap is VISIBLE, not folded away."""
    concept = await _a_concept()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}legacy")
        uid = await _user_id(f"{_PREFIX}legacy")
        async with AsyncSessionLocal() as db:
            db.add(ConceptProgress(user_id=uid, concept_id=concept.id,
                                   ladder_stage=2, confidence=3, legacy_reps=12))
            await db.commit()

        row = next(p for p in (await c.get("/api/progress", headers=h)).json()
                   if p["concept_id"] == str(concept.id))
        assert row == {**row, "reps": 12, "reps_legacy": 12, "reps_evidenced": 0}

        await upload_evidence(c, h, seed=10, reps=5, subject_type="concept",
                              concept_id=concept.id)
        row = next(p for p in (await c.get("/api/progress", headers=h)).json()
                   if p["concept_id"] == str(concept.id))
        assert (row["reps"], row["reps_legacy"], row["reps_evidenced"]) == (17, 12, 5)


# ===========================================================================
# The inherited debts — journal + missed trade attach to the SAME layer
# ===========================================================================

async def test_journal_and_missed_trade_evidence_attach_to_the_same_table():
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}debts")
        entry = (await c.post("/api/journal", headers=h, json={
            "entry_date": "2026-07-20", "instrument": "NQ",
            "mode": "backtest", "entry_model": "london",
        })).json()
        miss = (await c.post("/api/missed-trades", headers=h, json={
            "entry_date": "2026-07-20", "instrument": "NQ",
            "entry_model": "london", "miss_type": "canceled",
        })).json()

        je = await upload_evidence(c, h, seed=21, subject_type="journal_entry",
                                   journal_entry_id=entry["id"])
        assert je.status_code == 201, je.text
        mt = await upload_evidence(c, h, seed=22, subject_type="missed_trade",
                                   missed_trade_id=miss["id"])
        assert mt.status_code == 201, mt.text

        assert [e["id"] for e in (await c.get(
            "/api/evidence", headers=h, params={"journal_entry_id": entry["id"]}
        )).json()] == [je.json()["id"]]
        assert [e["id"] for e in (await c.get(
            "/api/evidence", headers=h, params={"missed_trade_id": miss["id"]}
        )).json()] == [mt.json()["id"]]

        # ONE polymorphic table serves all four subjects.
        async with AsyncSessionLocal() as db:
            kinds = (await db.execute(
                select(EvidenceAsset.subject_type).where(
                    EvidenceAsset.user_id == await _user_id(f"{_PREFIX}debts")
                )
            )).scalars().all()
        assert {k.value for k in kinds} == {"journal_entry", "missed_trade"}

        # Journal evidence is NOT a rep — a trade is not a drill.
        assert all(p["reps"] == 0 for p in (await c.get("/api/progress", headers=h)).json())


async def test_another_users_journal_entry_cannot_be_attached_to():
    async with await _client() as c:
        ha = await _token(c, f"{_PREFIX}ownA")
        entry = (await c.post("/api/journal", headers=ha, json={
            "entry_date": "2026-07-20", "instrument": "NQ",
            "mode": "backtest", "entry_model": "london",
        })).json()

        hb = await _token(c, f"{_PREFIX}ownB")
        r = await upload_evidence(c, hb, seed=23, subject_type="journal_entry",
                                  journal_entry_id=entry["id"])
        assert r.status_code == 404


# ===========================================================================
# Isolation, auth, storage
# ===========================================================================

async def test_per_user_isolation_and_auth():
    drill = await _a_drill()
    async with await _client() as c:
        ha = await _token(c, f"{_PREFIX}isoA")
        mine = (await upload_evidence(c, ha, seed=31, subject_type="drill",
                                      drill_ref=drill.drill_ref)).json()

        hb = await _token(c, f"{_PREFIX}isoB")
        assert (await c.get("/api/evidence", headers=hb)).json() == []
        assert (await c.get(f"/api/evidence/{mine['id']}", headers=hb)).status_code == 404
        assert (await c.delete(f"/api/evidence/{mine['id']}", headers=hb)).status_code == 404
        # B sees no reps from A's evidence.
        assert all(d["reps"] == 0 for d in (await c.get("/api/drills", headers=hb)).json())
        # And B may upload the SAME image — the duplicate block is per user.
        assert (await upload_evidence(c, hb, seed=31, subject_type="drill",
                                      drill_ref=drill.drill_ref)).status_code == 201

    async with await _client() as c:
        assert (await c.get("/api/evidence")).status_code == 403
        assert (await c.post("/api/evidence")).status_code == 403


async def test_the_local_backend_works_with_no_r2_configured():
    """Paul's decision #4: localhost is the PRIMARY path, not a stopgap. With no
    bucket provisioned the upload must succeed and the image must render."""
    assert not settings.r2_endpoint_url, "this dev env should have no R2 configured"
    assert storage_service.storage.name == "local"

    drill = await _a_drill()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}local")
        got = (await upload_evidence(c, h, seed=41, subject_type="drill",
                                     drill_ref=drill.drill_ref)).json()
        assert got["url"].startswith("/api/evidence/file?token=")

        # The signed URL streams the real bytes back, with no Bearer header.
        served = await c.get(got["url"])
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/png"
        assert served.content == chart_png(41)

        # A bad or absent token is refused.
        assert (await c.get("/api/evidence/file?token=nonsense")).status_code == 404
        assert (await c.get("/api/evidence/file")).status_code == 422


async def test_a_read_token_authorises_exactly_one_key():
    """The token is key-scoped, so holding one does not grant a directory."""
    from app.services.storage import StorageError, sign_key, verify_key_token

    assert verify_key_token(sign_key("a/b/c.png")) == "a/b/c.png"
    with pytest.raises(StorageError):
        verify_key_token("not-a-token")


async def test_a_filename_can_never_escape_the_storage_root():
    """No path is ever built from user input — the filename is a hint only."""
    from app.services.storage import LocalBackend, StorageError, slugify_subject

    assert slugify_subject("../../etc/passwd") == "etc-passwd"
    assert slugify_subject("aura D1-b") == "aura-d1-b"

    backend = LocalBackend()
    for bad in ("../escape.png", "/etc/passwd", "a\\b.png"):
        with pytest.raises(StorageError):
            backend.read_bytes(bad)

    drill = await _a_drill()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}path")
        got = (await c.post(
            "/api/evidence", headers=h,
            files={"file": ("../../../evil.php", chart_png(51), "image/png")},
            data={"subject_type": "drill", "drill_ref": drill.drill_ref},
        )).json()
        assert ".." not in got["storage_key"] if "storage_key" in got else True
        # The extension follows the SNIFFED type, not the claimed one.
        async with AsyncSessionLocal() as db:
            key = (await db.execute(
                select(EvidenceAsset.storage_key).where(
                    EvidenceAsset.id == uuid.UUID(got["id"])
                )
            )).scalar_one()
        assert key.endswith(".png") and ".." not in key


# ===========================================================================
# THE NO-REGRESSION EVIDENCE GATE (the Phase-6 pattern, repeated)
# ===========================================================================

async def test_the_evidence_layer_never_moves_expectancy_or_the_gate():
    """An evidence layer must not touch the proof of edge or the live verdict.

    Byte-identical `/api/analytics/*` + `/api/gate` across drill, concept,
    journal and missed-trade evidence writes. Mirrors
    `test_missed_trades_and_position_size_never_move_expectancy_or_the_gate`.
    """
    drill = await _a_drill()
    concept = await _a_concept()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}nogate")

        ids = []
        for r in (2.0, 2.0, -1.0, -1.0, -1.0):
            ids.append((await c.post("/api/journal", headers=h, json={
                "entry_date": "2026-07-20", "instrument": "NQ", "mode": "backtest",
                "entry_model": "london", "r_multiple": r, "rr_planned": 2.0,
            })).json()["id"])
        miss = (await c.post("/api/missed-trades", headers=h, json={
            "entry_date": "2026-07-20", "instrument": "NQ",
            "entry_model": "london", "miss_type": "canceled", "hypothetical_r": -1.0,
        })).json()

        async def snapshot():
            out = []
            for path in ("/api/analytics/expectancy", "/api/analytics/summary",
                         "/api/analytics/r-distribution", "/api/analytics/missed-summary",
                         "/api/gate"):
                out.append((await c.get(path, headers=h)).json())
            return json.dumps(out, sort_keys=True)

        before = await snapshot()
        assert '"expectancy": 0.2' in before  # the sample is really in there

        await upload_evidence(c, h, seed=61, reps=25, subject_type="drill",
                              drill_ref=drill.drill_ref)
        await upload_evidence(c, h, seed=62, reps=25, subject_type="concept",
                              concept_id=concept.id)
        await upload_evidence(c, h, seed=63, subject_type="journal_entry",
                              journal_entry_id=ids[0])
        await upload_evidence(c, h, seed=64, subject_type="missed_trade",
                              missed_trade_id=miss["id"])

        assert len((await c.get("/api/evidence", headers=h)).json()) == 4
        assert await snapshot() == before, "the evidence layer moved expectancy or the gate"
