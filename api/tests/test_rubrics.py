"""Tests for the rubric layer + self-check (Phase E3).

Same harness as test_evidence_api.py: in-process ASGI transport against the real
seeded dev DB with debug JWTs, one throwaway user per test (`e3t-`), hard-cleaned
afterwards.

Four tests carry the phase:

* `test_no_rubric_text_is_authored` — THE NO-DRIFT PROOF. Every one of the
  projected rubric items must appear VERBATIM in a wiki `exercises.md` bullet,
  asserted over the WHOLE seed rather than spot-checked. If this fails, rubric
  text is being authored in the app, which is the exact drift the design forbids.
* `test_reseed_after_a_wiki_edit_bumps_the_version` — the regression test for a
  real bug: replacing a rubric's items via the ORM collection emitted the new
  INSERTs before the orphan DELETEs and collided on `ux_rubric_items_key`.
* `test_a_self_check_never_moves_a_rep` — the phase's load-bearing decision. An
  unchecked (or partially checked) capture keeps every rep it carried, because
  `stages.py` / `gate.py` read `reps` and progress must stay monotonic.
* `test_a_self_check_is_additive_not_destructive` — the deterministic grade E2
  wrote on arrival survives every later grading pass.
"""

import re
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
from app.models.drill_progress import DrillProgress
from app.models.enums import RubricVariant
from app.models.evidence import EvidenceAsset
from app.models.journal_entry import JournalEntry
from app.models.missed_trade import MissedTrade
from app.models.plan_item import PlanItem
from app.models.rubric import Rubric, RubricItem
from app.models.study_preferences import StudyPreferences
from app.models.user import User
from scripts import seed_rubrics
from tests.evidence_helpers import upload_evidence

_test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(bind=_test_engine, expire_on_commit=False)

_PREFIX = "e3t-"


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
            await db.execute(delete(EvidenceAsset).where(EvidenceAsset.user_id == uid))
            await db.execute(delete(PlanItem).where(PlanItem.user_id == uid))
            await db.execute(delete(StudyPreferences).where(StudyPreferences.user_id == uid))
            await db.execute(delete(ConceptProgress).where(ConceptProgress.user_id == uid))
            await db.execute(delete(DrillProgress).where(DrillProgress.user_id == uid))
            await db.execute(delete(JournalEntry).where(JournalEntry.user_id == uid))
            await db.execute(delete(MissedTrade).where(MissedTrade.user_id == uid))
        await db.commit()


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _token(c, discord_id):
    r = await c.post("/auth/debug/token", json={"discord_id": discord_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _a_rubric(track: str = "aura") -> Rubric:
    """A seeded rubric with at least two items (so a partial check is possible)."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Rubric).where(Rubric.track == track).order_by(Rubric.drill_ref)
        )).scalars().all()
        for r in rows:
            if len(r.items) >= 2:
                return r
    raise AssertionError(f"no seeded {track} rubric has ≥2 items")


# ===========================================================================
# The projection — no rubric text may be authored in the app
# ===========================================================================

def test_no_rubric_text_is_authored():
    """THE NO-DRIFT PROOF, over the whole seed.

    Every projected item's text must be a contiguous substring of a bullet in one
    of the two wiki exercise libraries. Asserted programmatically across all
    items, not eyeballed on a sample.
    """
    rubrics, _report = seed_rubrics.build_rubrics()
    assert rubrics, "the projection produced no rubrics at all"
    failures = seed_rubrics.verify_no_drift(rubrics)
    assert not failures, (
        f"{len(failures)} rubric item(s) are NOT verbatim wiki text — the parser is "
        f"authoring rubric text: {failures[:5]}"
    )


def test_every_projected_rubric_is_well_formed():
    """Shape invariants, so a wiki edit cannot silently produce a broken bar."""
    rubrics, _ = seed_rubrics.build_rubrics()
    variants = {v.value for v in RubricVariant}
    for r in rubrics:
        assert r["items"], f"{r['drill_ref']} has no items but was still projected"
        assert r["slug"] == re.sub(r"[^a-z0-9]+", "-", r["drill_ref"].lower()).strip("-")
        # Ordinals are 1..N contiguous, and item_key is positional off the slug.
        assert [i["ordinal"] for i in r["items"]] == list(range(1, len(r["items"]) + 1))
        for item in r["items"]:
            assert item["item_key"] == f"{r['slug']}#{item['ordinal']}"
            assert item["variant"] in variants
            assert item["text"].strip(), f"{item['item_key']} is blank"
            assert item["bullet_ordinal"] >= 1


def test_structural_markers_never_become_rubric_items():
    """`**Advances:**`, trailing `[R…]` refs and wikilink trailers are metadata —
    `drills.advances_to` already carries the first, and none is an assertion the
    user can tick."""
    rubrics, _ = seed_rubrics.build_rubrics()
    for r in rubrics:
        for item in r["items"]:
            text = item["text"]
            assert "**Advances:**" not in text, f"{item['item_key']} carries an Advances marker"
            assert not re.search(r"\[R[^\]]*\]\s*\.?\s*$", text), (
                f"{item['item_key']} ends with a rule ref: {text!r}"
            )
            assert "→ [[" not in text, f"{item['item_key']} carries a wikilink trailer"


def test_semicolons_inside_parentheses_and_quotes_are_not_clause_boundaries():
    """The corpus writes semicolons inside parentheses and inside a quoted bias
    statement, so the split must be depth-aware."""
    assert seed_rubrics.split_top_level(
        "Flag confluence stacks (overlapping gaps; liquidity-left + liquidity-inside; near-EQ gaps)."
    ) == ["Flag confluence stacks (overlapping gaps; liquidity-left + liquidity-inside; near-EQ gaps)."]

    assert seed_rubrics.split_top_level(
        'Each evening write the one-sentence bias ("inside a [bull/bear] 4H FVG; target [level]"); '
        "each morning note opening-price position"
    ) == [
        'Each evening write the one-sentence bias ("inside a [bull/bear] 4H FVG; target [level]")',
        "each morning note opening-price position",
    ]


def test_sentence_boundaries_are_not_clause_boundaries():
    """WHY the split is semicolon-only: this corpus writes "vs." mid-sentence
    followed by a capital, and every sentence heuristic mangled those into
    fragments. A parser that can mangle wiki text is a parser that authors it."""
    for phrase in (
        "over a week track **which KZ sets the HOD vs. LOD**",
        "classify **STL (no gap) vs. ITL (price leg creates/fills an FVG)**",
        "watch the first OB after an LTH/LTL — does it hold on the 1st/2nd return? Tag **LRLR vs. HRLR**",
    ):
        assert seed_rubrics.split_top_level(phrase) == [phrase]

    # And the real projected items keep them whole.
    rubrics, _ = seed_rubrics.build_rubrics()
    texts = [i["text"] for r in rubrics for i in r["items"]]
    assert any("HOD vs. LOD" in t for t in texts)
    assert not any(t.rstrip().endswith("vs") for t in texts)


def test_the_projection_reports_what_it_could_not_project():
    """Nothing is silently skipped. Drills written as a paragraph plus a table
    (aura D4-a/b) have no ✋/🛠 bullet, and the run must SAY so rather than
    inventing one."""
    _rubrics, report = seed_rubrics.build_rubrics()
    unprojectable = report.get("drills with no projectable bullet", [])
    assert "aura D4-a" in unprojectable and "aura D4-b" in unprojectable


async def test_reseed_is_idempotent():
    """Re-projecting unchanged wiki content must not bump a single version."""
    rubrics, _ = seed_rubrics.build_rubrics()
    async with AsyncSessionLocal() as db:
        before = {
            r.slug: r.version for r in (await db.execute(select(Rubric))).scalars().all()
        }
        stats = await seed_rubrics._upsert(db, rubrics)
    assert stats["bumped"] == 0, "an unchanged re-seed bumped a version"
    assert stats["inserted"] == 0 and stats["pruned"] == 0
    async with AsyncSessionLocal() as db:
        after = {
            r.slug: r.version for r in (await db.execute(select(Rubric))).scalars().all()
        }
    assert before == after


async def test_reseed_after_a_wiki_edit_bumps_the_version():
    """A changed bullet is a NEW BAR: version+1 and the items are replaced.

    This is also the regression test for a real bug — assigning the new items to
    the ORM collection emitted this mapper's INSERTs BEFORE its orphan DELETEs, so
    the positional `item_key` (`…#1`) collided on `ux_rubric_items_key` and the
    whole re-seed died with an IntegrityError.
    """
    rubrics, _ = seed_rubrics.build_rubrics()
    target = next(r for r in rubrics if len(r["items"]) >= 2)
    slug = target["slug"]

    async with AsyncSessionLocal() as db:
        original_version = (await db.execute(
            select(Rubric.version).where(Rubric.slug == slug)
        )).scalar_one()

        # Simulate a wiki edit: same bar, one clause fewer.
        edited = dict(target, items=target["items"][:-1])
        edited["content_hash"] = seed_rubrics.content_hash(edited["items"])
        stats = await seed_rubrics._upsert(
            db, [edited] + [r for r in rubrics if r["slug"] != slug]
        )
        assert stats["bumped"] == 1

    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(Rubric).where(Rubric.slug == slug))).scalar_one()
        assert row.version == original_version + 1
        assert len(row.items) == len(target["items"]) - 1
        keys = (await db.execute(
            select(RubricItem.item_key).where(RubricItem.rubric_id == row.id)
        )).scalars().all()
        assert len(keys) == len(set(keys)), "duplicate item_key survived the swap"

        # Restore, so the suite leaves the seed as it found it (bar the version,
        # which is monotonic BY DESIGN — an edit and its revert are two changes).
        await seed_rubrics._upsert(db, rubrics)


# ===========================================================================
# GET /api/rubrics — read-only
# ===========================================================================

async def test_get_rubric_by_drill_ref():
    rubric = await _a_rubric()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}get")
        r = await c.get("/api/rubrics", params={"drill_ref": rubric.drill_ref}, headers=h)
        assert r.status_code == 200, r.text
        [body] = r.json()
        assert body["slug"] == rubric.slug
        assert body["version"] == rubric.version
        assert body["source_path"].startswith("concepts/mastery/")
        assert len(body["items"]) == len(rubric.items)
        assert body["items"][0]["item_key"] == f"{rubric.slug}#1"


async def test_get_rubrics_by_concept_resolves_through_drill_refs():
    """A concept's bar is the union of the bars of the drills that advance it."""
    async with AsyncSessionLocal() as db:
        concepts = (await db.execute(select(Concept).where(Concept.drill_refs.isnot(None)))).scalars().all()
        slugs = {r.drill_ref for r in (await db.execute(select(Rubric))).scalars().all()}
    target = next(c for c in concepts if len(set(c.drill_refs or []) & slugs) >= 1)
    expected = set(target.drill_refs or []) & slugs

    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}concept")
        r = await c.get("/api/rubrics", params={"concept_slug": target.slug}, headers=h)
        assert r.status_code == 200, r.text
        assert {b["drill_ref"] for b in r.json()} == expected

        assert (await c.get(
            "/api/rubrics", params={"concept_slug": "no-such-concept"}, headers=h
        )).status_code == 404


async def test_rubrics_are_read_only_and_auth_gated():
    """No endpoint can author rubric text — the same structural argument as the
    absent `cleared` column and the absent writable `reps`."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}ro")
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            assert (await c.request(method, "/api/rubrics", headers=h)).status_code == 405
        assert (await c.get("/api/rubrics")).status_code == 403


# ===========================================================================
# The self-check — tier 2
# ===========================================================================

async def test_a_full_self_check_passes_and_a_partial_one_flags():
    rubric = await _a_rubric()
    keys = [i.item_key for i in rubric.items]
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}check")
        asset = (await upload_evidence(
            c, h, seed=6101, subject_type="drill", drill_ref=rubric.drill_ref
        )).json()

        r = await c.post(f"/api/evidence/{asset['id']}/self-check", headers=h,
                         json={"rubric_slug": rubric.slug, "checked_item_keys": keys[:1]})
        assert r.status_code == 201, r.text
        partial = next(g for g in r.json()["grades"] if g["grader"] == "self_check")
        assert partial["state"] == "flagged"
        assert partial["score"] == pytest.approx(100 / len(keys), abs=0.01)
        assert partial["rubric_slug"] == rubric.slug
        assert partial["rubric_version"] == rubric.version
        # findings record the WHOLE bar with each item's ticked state and its text.
        assert len(partial["findings"]) == len(keys)
        assert sum(1 for f in partial["findings"] if f["checked"]) == 1
        assert all(f["text"] for f in partial["findings"])

        r = await c.post(f"/api/evidence/{asset['id']}/self-check", headers=h,
                         json={"checked_item_keys": keys})  # slug resolved from the drill
        assert r.status_code == 201, r.text
        full = next(g for g in r.json()["grades"] if g["grader"] == "self_check")
        assert full["state"] == "passed"
        assert full["score"] == pytest.approx(100.0)


async def test_a_self_check_is_additive_not_destructive():
    """Grading is APPEND-ONLY: the `deterministic` row E2 wrote on arrival
    survives, and a re-check adds a row rather than mutating a verdict."""
    rubric = await _a_rubric()
    keys = [i.item_key for i in rubric.items]
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}additive")
        asset = (await upload_evidence(
            c, h, seed=6102, subject_type="drill", drill_ref=rubric.drill_ref
        )).json()
        assert [g["grader"] for g in asset["grades"]] == ["deterministic"]

        for checked in (keys[:1], keys):
            r = await c.post(f"/api/evidence/{asset['id']}/self-check", headers=h,
                             json={"checked_item_keys": checked})
            assert r.status_code == 201, r.text

        grades = r.json()["grades"]
        assert sum(1 for g in grades if g["grader"] == "deterministic") == 1
        assert sum(1 for g in grades if g["grader"] == "self_check") == 2
        # Ordered graded_at DESC, so the newest self-check is the current answer.
        assert next(g for g in grades if g["grader"] == "self_check")["state"] == "passed"


async def test_a_self_check_never_moves_a_rep():
    """THE PHASE'S LOAD-BEARING DECISION.

    A rep counts from the moment evidence exists (E2). A missing, partial or empty
    self-check cannot deduct one, because `services/stages.py` and
    `services/gate.py` read `reps`: retraction would make progress NON-MONOTONIC —
    a met stage exit bar could un-meet and a Gate verdict could flip backwards with
    no user action. Ungraded work is SURFACED as a backlog, never subtracted.
    """
    rubric = await _a_rubric()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}monotonic")
        asset = (await upload_evidence(
            c, h, seed=6103, reps=4, subject_type="drill", drill_ref=rubric.drill_ref
        )).json()

        async def drill_reps() -> tuple[int, int]:
            rows = (await c.get("/api/drills", headers=h)).json()
            d = next(x for x in rows if x["drill_ref"] == rubric.drill_ref)
            return d["reps"], d["reps_evidenced"]

        before = await drill_reps()
        assert before == (4, 4)

        # An EMPTY self-check — the most adversarial case: the user says the
        # capture meets none of the bar.
        r = await c.post(f"/api/evidence/{asset['id']}/self-check", headers=h,
                         json={"checked_item_keys": []})
        assert r.status_code == 201, r.text
        assert next(g for g in r.json()["grades"] if g["grader"] == "self_check")["score"] == 0.0
        assert await drill_reps() == before, "an unchecked self-check moved the rep count"

        # And a full one does not INFLATE it either — a grade is not a rep.
        await c.post(f"/api/evidence/{asset['id']}/self-check", headers=h,
                     json={"checked_item_keys": [i.item_key for i in rubric.items]})
        assert await drill_reps() == before, "a self-check minted a rep"


async def test_a_self_check_refusal_always_says_why():
    rubric = await _a_rubric()
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}refusal")
        asset = (await upload_evidence(
            c, h, seed=6104, subject_type="drill", drill_ref=rubric.drill_ref
        )).json()

        # An item that is not in this rubric — named in the message.
        r = await c.post(f"/api/evidence/{asset['id']}/self-check", headers=h,
                         json={"checked_item_keys": [f"{rubric.slug}#999"]})
        assert r.status_code == 422
        assert f"{rubric.slug}#999" in str(r.json()["detail"])

        # An unknown rubric slug.
        r = await c.post(f"/api/evidence/{asset['id']}/self-check", headers=h,
                         json={"rubric_slug": "not-a-rubric", "checked_item_keys": []})
        assert r.status_code == 404
        assert "not-a-rubric" in str(r.json()["detail"])

        # A drill the wiki writes as a paragraph + table has no bar — honest 404.
        bare = (await upload_evidence(
            c, h, seed=6105, subject_type="drill", drill_ref="aura D4-a"
        )).json()
        r = await c.post(f"/api/evidence/{bare['id']}/self-check", headers=h,
                         json={"checked_item_keys": []})
        assert r.status_code == 404
        assert "aura D4-a" in str(r.json()["detail"])


async def test_a_non_drill_subject_needs_an_explicit_rubric():
    """Journal and missed-trade evidence has no bar of its own, so the server
    refuses to guess one rather than attaching an unrelated drill's rubric."""
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}journal")
        entry = (await c.post("/api/journal", headers=h, json={
            "entry_date": "2026-07-20", "instrument": "NQ",
            "mode": "backtest", "entry_model": "london",
        })).json()
        asset = (await upload_evidence(
            c, h, seed=6106, subject_type="journal_entry", journal_entry_id=entry["id"]
        )).json()

        r = await c.post(f"/api/evidence/{asset['id']}/self-check", headers=h,
                         json={"checked_item_keys": []})
        assert r.status_code == 422
        assert "rubric_slug" in str(r.json()["detail"])


async def test_a_self_check_is_user_scoped():
    rubric = await _a_rubric()
    async with await _client() as c:
        owner = await _token(c, f"{_PREFIX}owner")
        other = await _token(c, f"{_PREFIX}other")
        asset = (await upload_evidence(
            c, owner, seed=6107, subject_type="drill", drill_ref=rubric.drill_ref
        )).json()

        r = await c.post(f"/api/evidence/{asset['id']}/self-check", headers=other,
                         json={"checked_item_keys": []})
        assert r.status_code == 404, "another user could grade this evidence"

        assert (await c.post(
            f"/api/evidence/{uuid.uuid4()}/self-check", headers=owner,
            json={"checked_item_keys": []},
        )).status_code == 404


async def test_the_rubric_layer_never_moves_expectancy_or_the_gate():
    """The Phase-6 evidence-gate pattern, repeated for E3: a rubric is content and
    a self-check is a grade, so neither may touch expectancy or the Gate."""
    rubric = await _a_rubric()
    endpoints = [
        "/api/analytics/expectancy", "/api/analytics/summary",
        "/api/analytics/r-distribution", "/api/analytics/missed-summary", "/api/gate",
    ]
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}gate")
        before = {p: (await c.get(p, headers=h)).json() for p in endpoints}

        asset = (await upload_evidence(
            c, h, seed=6108, reps=2, subject_type="drill", drill_ref=rubric.drill_ref
        )).json()
        assert (await c.post(
            f"/api/evidence/{asset['id']}/self-check", headers=h,
            json={"checked_item_keys": [i.item_key for i in rubric.items]},
        )).status_code == 201

        after = {p: (await c.get(p, headers=h)).json() for p in endpoints}
    assert before == after, "the rubric layer moved expectancy or the Gate"
