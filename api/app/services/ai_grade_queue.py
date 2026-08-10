"""The asynchronous half of tier 3 (Phase E4) — a DURABLE queue, not a fire-and-forget task.

WHY A QUEUE ROW RATHER THAN `BackgroundTasks`, AND WHY NOT THE BATCH API
-----------------------------------------------------------------------
Design §2 says the advisory tier runs "through the Batch API". Built as written
that would be wrong here, and the reason is the design's own §6:

  · The Batch API's benefit is a 50% discount. §"Why tiered" already establishes
    that the WHOLE curriculum costs ~$15-25, so batching saves single-digit
    dollars across the life of the project. Cost is explicitly not the binding
    constraint — §2 says so in as many words.
  · Its cost is latency: most batches land within an hour, the ceiling is 24.
  · §6 makes informational feedback THE reward mechanism, on Deci/Koestner/Ryan
    1999 — praise and specific feedback sustain intrinsic motivation where
    tangible rewards undermine it. A reward delivered up to a day after the work
    is a much weaker reinforcer than one delivered in seconds. Batching would
    save ~$10 by blunting the exact mechanism the phase exists to deliver.

So the grade is requested synchronously and lands in seconds. What is kept from
the Batch design is the part that actually mattered — the work is QUEUED, not
awaited on the upload path, so upload latency is unchanged whatever the API does.

`BackgroundTasks` would give that too, but nothing else: a task lost to a restart
leaves no trace, and `--reload` restarts constantly in dev. Instead the queue IS
a row — `evidence_grades(grader='ai_vision', state='pending')` — written in the
same transaction as the upload. That gives, for free:

  · restart safety: a `pending` row that never completed is still there, and the
    startup sweep picks it up
  · honest state: `pending` and `ungraded` are already first-class enum values
    from `0009`, so E4 needs NO migration
  · visibility: "awaiting the second reader" is queryable rather than implicit
  · and the Batch API stays a later swap — the queue is the right primitive for
    it too, if per-grade volume ever makes the discount matter.

INVARIANTS THIS MODULE MUST NOT BREAK
-------------------------------------
It writes exactly one thing: the `ai_vision` row it created. It never touches
`evidence_assets` (so `reps` cannot move), never touches `concept_progress` or
`drill_progress` (so `confidence` / `ladder_stage` cannot move), and never writes
state `failed`. Every failure path lands on `ungraded`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.enums import EvidenceGradeState, EvidenceGrader
from app.models.evidence import EvidenceAsset, EvidenceGrade
from app.models.rubric import Rubric
from app.services import ai_grader, storage as storage_service

log = logging.getLogger("neurospect.ai_grader")

#: One worker pass at a time per process. A grade is never urgent, and serialising
#: keeps the single-user app from opening a fan of concurrent API calls.
_lock = asyncio.Lock()


def enqueue_row(evidence_id: uuid.UUID, user_id: uuid.UUID) -> EvidenceGrade:
    """The `pending` row, to be added in the SAME transaction as the upload.

    Returned rather than committed so the caller owns the transaction — if the
    upload rolls back, so does the queue entry.
    """
    return EvidenceGrade(
        evidence_id=evidence_id,
        user_id=user_id,
        grader=EvidenceGrader.AI_VISION,
        state=EvidenceGradeState.PENDING,
    )


async def _resolve_rubric(db: AsyncSession, asset: EvidenceAsset) -> Rubric | None:
    """The bar to report against, or None when the drill has none.

    Journal and missed-trade evidence have no bar at all, and a handful of drills
    are written in the wiki as prose plus a table with no ✋/🛠 bullets to
    project. In both cases there is genuinely nothing to report against, so the
    row resolves to `ungraded` rather than being judged against an unrelated bar
    — the same refusal-to-guess `_resolve_rubric` makes in routers/evidence.py.
    """
    if asset.subject_drill_ref is None:
        return None
    return (
        await db.execute(select(Rubric).where(Rubric.drill_ref == asset.subject_drill_ref))
    ).scalar_one_or_none()


def _finish(grade: EvidenceGrade, *, state: EvidenceGradeState, result, findings=None, score=None) -> None:
    grade.state = state
    grade.findings = findings
    grade.score = score
    grade.model = result.model
    grade.input_tokens = result.usage.billable_input
    grade.output_tokens = result.usage.output_tokens
    grade.cost_usd = result.cost_usd
    grade.graded_at = datetime.now(timezone.utc)


async def _grade_one(db: AsyncSession, grade: EvidenceGrade) -> None:
    """Resolve ONE pending row. Never raises — every outcome is a recorded state."""
    asset = (
        await db.execute(select(EvidenceAsset).where(EvidenceAsset.id == grade.evidence_id))
    ).scalar_one_or_none()

    if asset is None or asset.is_deleted:
        # The capture was removed before the reader got to it. Nothing to report.
        grade.state = EvidenceGradeState.UNGRADED
        grade.findings = [{"error": "evidence removed before grading"}]
        return

    rubric = await _resolve_rubric(db, asset)
    if rubric is None or not rubric.items:
        grade.state = EvidenceGradeState.UNGRADED
        grade.findings = [{"error": "no projected bar for this subject"}]
        return

    items = [{"item_key": it.item_key, "text": it.text} for it in rubric.items]

    try:
        data = await run_in_threadpool(storage_service.storage_read_bytes, asset.storage_key)
    except Exception as exc:  # noqa: BLE001
        grade.state = EvidenceGradeState.UNGRADED
        grade.findings = [{"error": f"could not read stored capture: {exc}"}]
        return

    result = await ai_grader.grade(
        image=data,
        content_type=asset.content_type,
        rubric_block=ai_grader.build_rubric_block(rubric.slug, rubric.drill_ref, items),
    )

    grade.rubric_slug = rubric.slug
    grade.rubric_version = rubric.version

    if result.verdict is None:
        # API down, refused, truncated, unparseable — all honestly `ungraded`.
        # NEVER `failed`: this tier does not get to fail a trader's rep.
        _finish(
            grade,
            state=EvidenceGradeState.UNGRADED,
            result=result,
            findings=[{"error": result.error or "no verdict"}],
        )
        log.warning("ai_vision grade %s ungraded: %s", grade.id, result.error)
        return

    item_texts = {it["item_key"]: it["text"] for it in items}
    state, score, findings = ai_grader.summarise(result.verdict, item_texts)
    _finish(
        grade,
        state=EvidenceGradeState(state),
        result=result,
        findings={
            "subject_matter": result.verdict.get("subject_matter"),
            "annotation_density": result.verdict.get("annotation_density"),
            "observations": result.verdict.get("observations") or [],
            "items": findings,
        },
        score=score,
    )


async def drain(limit: int | None = None) -> int:
    """Resolve up to `limit` pending rows. Returns how many were handled.

    Safe to call concurrently — the lock serialises passes, and a second caller
    simply finds an empty queue.
    """
    if not ai_grader.is_configured():
        return 0

    limit = limit or settings.ai_grader_batch_size
    handled = 0
    async with _lock:
        async with AsyncSessionLocal() as db:
            rows = (
                await db.execute(
                    select(EvidenceGrade)
                    .where(
                        EvidenceGrade.grader == EvidenceGrader.AI_VISION,
                        EvidenceGrade.state == EvidenceGradeState.PENDING,
                        EvidenceGrade.is_deleted.is_(False),
                    )
                    .order_by(EvidenceGrade.created_at)
                    .limit(limit)
                )
            ).scalars().all()

            for grade in rows:
                try:
                    await _grade_one(db, grade)
                except Exception as exc:  # noqa: BLE001 — a worker must not die
                    log.exception("ai_vision grade %s crashed", grade.id)
                    grade.state = EvidenceGradeState.UNGRADED
                    grade.findings = [{"error": f"grader crashed: {exc}"}]
                handled += 1

            await db.commit()
    return handled


def kick() -> None:
    """Nudge the worker without awaiting it — the upload path's only involvement.

    Fire-and-forget by design: the durable `pending` row is what makes the work
    survive, so a dropped task costs at most a delay until the next kick or the
    startup sweep.
    """
    if not ai_grader.is_configured():
        return
    try:
        task = asyncio.get_running_loop().create_task(drain())
        # Hold a reference so the task is not garbage-collected mid-flight.
        _background.add(task)
        task.add_done_callback(_background.discard)
    except RuntimeError:
        pass  # no running loop (sync test context) — the sweep will catch it


_background: set[asyncio.Task] = set()


async def sweep_on_startup() -> int:
    """Pick up rows orphaned by a restart. Bounded, so boot is never slow."""
    if not ai_grader.is_configured():
        return 0
    try:
        return await drain(limit=settings.ai_grader_batch_size)
    except Exception:  # noqa: BLE001 — a bad sweep must never stop the app booting
        log.exception("ai_vision startup sweep failed")
        return 0
