"""Study-Planner API (Phase 5e-2) — preferences, Today, calendar, regenerate,
and mark-item-done → progress. All endpoints are auth-gated and user-scoped.

Persist-vs-compute hybrid (learning-platform.md §Study Planner): preferences are
PERSISTED; the future schedule is COMPUTED on read by the pure
`app/services/scheduler.py`; past + today are FROZEN into `plan_items`.
`GET /plan/today` materializes the current date's computed items once (idempotent
via the `ux_plan_items_slot` partial-unique index). Marking an item done/partial
feeds `concept_progress`/`drill_progress` (reps + last_practiced), honouring the
existing ladder-advance gate + watch-only cap (this endpoint never advances the
ladder itself — that stays the /api/progress endpoint's job and its gate).

The scheduler is TRACK-SCOPED: it schedules `study_preferences.active_track`.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.concept import Concept
from app.models.concept_progress import ConceptProgress
from app.models.drill import Drill
from app.models.drill_progress import DrillProgress
from app.models.enums import PlanActivity, PlanItemStatus
from app.models.evidence import EvidenceAsset
from app.models.plan_item import PlanItem
from app.models.rest_day import RestDay
from app.models.study_preferences import StudyPreferences
from app.models.track_stage import TrackStage
from app.models.user import User
from app.schemas.planner import (
    AdherenceOut,
    ConsistencyOut,
    PaceOut,
    PlanItemOut,
    PlanItemPatch,
    PlanRangeOut,
    PreferencesIn,
    PreferencesOut,
    RestDayIn,
    RestDayOut,
    TodayOut,
)
from app.routers.learning import load_evidence_reps, load_stage_evidence
from app.services import consistency, scheduler, stages

router = APIRouter(
    prefix="/api",
    tags=["planner"],
    dependencies=[Depends(get_current_user)],
)

# Mirrors the 0002/0004/0006 partial-index predicate for ON CONFLICT inference.
_NOT_DELETED = text("NOT is_deleted")

_WEEKDAY_COLS = (
    "mon_minutes", "tue_minutes", "wed_minutes", "thu_minutes",
    "fri_minutes", "sat_minutes", "sun_minutes",
)


# ---------------------------------------------------------------------------
# Time / prefs helpers
# ---------------------------------------------------------------------------

def _today_in(tz: str) -> date:
    """The current date in the user's timezone (the ONE clock read — the
    scheduler itself is clock-free and deterministic)."""
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        zone = timezone.utc
    return datetime.now(zone).date()


async def _load_prefs(db: AsyncSession, user_id) -> StudyPreferences | None:
    return (
        await db.execute(
            select(StudyPreferences).where(
                StudyPreferences.user_id == user_id,
                StudyPreferences.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()


def _prefs_out(p: StudyPreferences | None) -> PreferencesOut:
    if p is None:
        return PreferencesOut(is_configured=False)  # server defaults
    return PreferencesOut(
        id=p.id, timezone=p.timezone,
        mon_minutes=p.mon_minutes, tue_minutes=p.tue_minutes, wed_minutes=p.wed_minutes,
        thu_minutes=p.thu_minutes, fri_minutes=p.fri_minutes, sat_minutes=p.sat_minutes,
        sun_minutes=p.sun_minutes, max_session_minutes=p.max_session_minutes,
        blackout_dates=list(p.blackout_dates or []),
        target_go_live_date=p.target_go_live_date, active_track=p.active_track,
        plan_version=p.plan_version, generated_at=p.generated_at, is_configured=True,
    )


def _prefs_view(p: StudyPreferences) -> scheduler.PrefsView:
    minutes = tuple(getattr(p, col) for col in _WEEKDAY_COLS)
    return scheduler.PrefsView(
        weekday_minutes=minutes,  # type: ignore[arg-type]
        max_session_minutes=p.max_session_minutes,
        active_track=p.active_track,
        blackout_dates=frozenset(p.blackout_dates or []),
        target_go_live_date=p.target_go_live_date,
        plan_version=p.plan_version,
        timezone=p.timezone,
    )


# ---------------------------------------------------------------------------
# Load the scheduler's inputs for a track (DB → view dataclasses)
# ---------------------------------------------------------------------------

async def _load_inputs(db: AsyncSession, user_id, track: str):
    # Phase E2: the scheduler decides "how many reps are still owed" from the
    # DERIVED count, so an unevidenced drill keeps being prescribed until the
    # work is actually captured.
    ev = await load_evidence_reps(db, user_id)
    metas = (
        await db.execute(
            select(TrackStage).where(TrackStage.track == track).order_by(TrackStage.stage_order)
        )
    ).scalars().all()
    stage_metas = [
        stages.StageMeta(
            track=m.track, stage_code=m.stage_code, stage_order=m.stage_order,
            title=m.title, summary=m.summary, gate_text=m.gate_text,
        )
        for m in metas
    ]

    rows = (
        await db.execute(
            select(Concept, ConceptProgress)
            .outerjoin(
                ConceptProgress,
                and_(
                    ConceptProgress.concept_id == Concept.id,
                    ConceptProgress.user_id == user_id,
                    ConceptProgress.is_deleted.is_(False),
                ),
            )
            .where(Concept.track == track)
            .order_by(Concept.sort_order)
        )
    ).all()

    concepts: list[scheduler.ConceptView] = []
    cprog: dict[str, scheduler.ConceptProgressView] = {}
    concept_meta: dict = {}  # id → (slug, title, content_slug) for enrichment
    for c, pg in rows:
        concepts.append(scheduler.ConceptView(
            concept_id=c.id, slug=c.slug, stage_code=c.stage_code, stage_order=c.stage_order,
            sort_order=c.sort_order, title=c.title, is_core=c.is_core, watch_only=c.watch_only,
            rep_target=c.rep_target, content_slug=c.content_slug,
            drill_refs=tuple(c.drill_refs or ()), code=c.code,
            u_stage=c.u_stage.value if c.u_stage else None,
        ))
        concept_meta[c.id] = (c.slug, c.title, c.content_slug)
        if pg is not None:
            cprog[c.slug] = scheduler.ConceptProgressView(
                pg.ladder_stage, pg.confidence,
                pg.legacy_reps + ev.concept(c.id), pg.last_practiced
            )

    # Drills: load ALL (concept.drill_refs can cross tracks, e.g. unified → "ict-course S7").
    drow = (await db.execute(select(Drill).order_by(Drill.sort_order))).scalars().all()
    drills = [
        scheduler.DrillView(
            drill_ref=d.drill_ref, stage_code=d.stage_code, rep_target=d.rep_target,
            sort_order=d.sort_order, concept_slugs=tuple(d.concept_slugs or ()),
        )
        for d in drow
    ]
    drill_titles = {d.drill_ref: d.title for d in drow}

    dpr = (
        await db.execute(
            select(DrillProgress).where(
                DrillProgress.user_id == user_id, DrillProgress.is_deleted.is_(False)
            )
        )
    ).scalars().all()
    dprog = {
        dp.drill_ref: scheduler.DrillProgressView(
            dp.legacy_reps + ev.drill(dp.drill_ref),
            dp.hand_done, dp.tool_done, dp.last_practiced,
        )
        for dp in dpr
    }
    # A drill with evidence but no drill_progress row yet still counts.
    for drill_ref, evidenced in ev.by_drill.items():
        if drill_ref not in dprog:
            dprog[drill_ref] = scheduler.DrillProgressView(evidenced, False, False, None)
    return stage_metas, concepts, drills, cprog, dprog, concept_meta, drill_titles


async def _load_past_pending(db: AsyncSession, user_id, today: date) -> list[scheduler.PastItemView]:
    rows = (
        await db.execute(
            select(PlanItem).where(
                PlanItem.user_id == user_id,
                PlanItem.is_deleted.is_(False),
                PlanItem.scheduled_date < today,
                PlanItem.status == PlanItemStatus.PENDING,
            )
        )
    ).scalars().all()
    return [
        scheduler.PastItemView(
            scheduled_date=r.scheduled_date, activity=r.activity, status=r.status,
            concept_id=r.concept_id, drill_ref=r.drill_ref, drill_variant=r.drill_variant,
            target_qty=r.target_qty, target_unit=r.target_unit, est_minutes=r.est_minutes,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------

def _item_from_row(r: PlanItem, concept_meta: dict, drill_titles: dict) -> PlanItemOut:
    slug = title = content_slug = None
    if r.concept_id in concept_meta:
        slug, title, content_slug = concept_meta[r.concept_id]
    return PlanItemOut(
        id=r.id, plan_version=r.plan_version, scheduled_date=r.scheduled_date,
        activity=r.activity, concept_id=r.concept_id, concept_slug=slug, concept_title=title,
        content_slug=content_slug, drill_ref=r.drill_ref,
        drill_title=drill_titles.get(r.drill_ref), drill_variant=r.drill_variant,
        target_qty=r.target_qty, target_unit=r.target_unit, est_minutes=r.est_minutes,
        status=r.status, done_qty=r.done_qty, completed_at=r.completed_at,
        sort_order=r.sort_order, frozen=True,
    )


def _item_from_spec(s: scheduler.PlanItemSpec, concept_meta: dict, drill_titles: dict) -> PlanItemOut:
    slug = title = content_slug = None
    if s.concept_id in concept_meta:
        slug, title, content_slug = concept_meta[s.concept_id]
    return PlanItemOut(
        id=None, scheduled_date=s.scheduled_date, activity=s.activity, concept_id=s.concept_id,
        concept_slug=slug, concept_title=title, content_slug=content_slug,
        drill_ref=s.drill_ref, drill_title=drill_titles.get(s.drill_ref),
        drill_variant=s.drill_variant, target_qty=s.target_qty, target_unit=s.target_unit,
        est_minutes=s.est_minutes, status=PlanItemStatus.PENDING, done_qty=0,
        sort_order=s.sort_order, carried_over=s.carried_over, frozen=False,
    )


def _pace_out(prefs_view: scheduler.PrefsView, result: scheduler.ScheduleResult) -> PaceOut:
    return PaceOut(
        target_go_live_date=prefs_view.target_go_live_date,
        projected_go_live=result.projected_go_live,
        on_pace=result.on_pace,
        projected_clear=result.projected_clear,
    )


def _zone(tz: str):
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


async def _consistency(
    db: AsyncSession, user_id, today: date, tz: str, marked_dates: frozenset[date]
) -> ConsistencyOut:
    """The shipped streak, re-derived from EVIDENCE instead of from a click (E6).

    `evidence_assets.created_at` is the server's upload clock and is what the
    streak walks. The user-asserted `captured_at` is deliberately NOT used: a
    streak that read an asserted timestamp could be extended by asserting one,
    which is the same class of hole E2 closed when it stopped `reps` being writable.

    Rest days come from `rest_days` and NEVER from `study_preferences.blackout_dates`.
    Blackout dates are a scheduling input that `PUT /api/preferences` will happily
    accept for a day already past, so honouring them here would build precisely the
    retroactive streak freeze §6 rejects. See Alembic `0012`.
    """
    zone = _zone(tz)
    ev_rows = (
        await db.execute(
            select(EvidenceAsset.created_at).where(
                EvidenceAsset.user_id == user_id,
                EvidenceAsset.is_deleted.is_(False),
            )
        )
    ).all()
    evidence_dates = frozenset(
        ts.astimezone(zone).date() for (ts,) in ev_rows if ts is not None
    )

    rest_rows = (
        await db.execute(select(RestDay.rest_date).where(RestDay.user_id == user_id))
    ).all()
    rest_dates = frozenset(d for (d,) in rest_rows)

    c = consistency.compute(
        today=today,
        evidence_dates=evidence_dates,
        rest_dates=rest_dates,
        marked_dates=marked_dates,
    )
    return ConsistencyOut(
        evidenced_days=c.evidenced_days,
        evidence_streak=c.evidence_streak,
        rest_days_in_streak=c.rest_days_in_streak,
        last_evidence_date=c.last_evidence_date,
        days_marked_without_evidence=c.days_marked_without_evidence,
        rest_days_declared=c.rest_days_declared,
        rest_days_upcoming=c.rest_days_upcoming,
    )


async def _adherence(
    db: AsyncSession,
    user_id,
    today: date,
    result: scheduler.ScheduleResult,
    tz: str = "UTC",
) -> AdherenceOut:
    rows = (
        await db.execute(
            select(PlanItem.scheduled_date, PlanItem.status).where(
                PlanItem.user_id == user_id,
                PlanItem.is_deleted.is_(False),
                PlanItem.scheduled_date <= today,
            )
        )
    ).all()
    counts = defaultdict(int)
    by_date: dict[date, list[PlanItemStatus]] = defaultdict(list)
    for d, st in rows:
        counts[st] += 1
        by_date[d].append(st)

    done = counts[PlanItemStatus.DONE]
    partial = counts[PlanItemStatus.PARTIAL]
    skipped = counts[PlanItemStatus.SKIPPED]
    pending = counts[PlanItemStatus.PENDING]
    total = done + partial + skipped + pending
    pct = round(100 * (done + 0.5 * partial) / total, 1) if total else None

    # Streak: consecutive fully-cleared days ending today. Days with no items
    # (days off) don't break it; today still in-progress (only done/pending) is
    # neutral (doesn't count, doesn't break); a skip/partial or past pending breaks.
    streak = 0
    d = today
    earliest = min(by_date) if by_date else today
    first = True
    while d >= earliest:
        st = by_date.get(d)
        if st is not None:
            if all(s == PlanItemStatus.DONE for s in st):
                streak += 1
            elif first and all(s in (PlanItemStatus.DONE, PlanItemStatus.PENDING) for s in st):
                pass  # today, still in progress — neutral
            else:
                break
        d -= timedelta(days=1)
        first = False

    # E6 — the same consistency, derived from evidence. Published BESIDE the
    # marked figures above, never replacing them: E2's `reps` / `reps_evidenced` /
    # `reps_legacy` idiom, so the gap between the claim and the record is visible
    # rather than folded away. Nothing above is recomputed, so no shipped number moves.
    marked_dates = frozenset(
        d for d, sts in by_date.items()
        if any(s in (PlanItemStatus.DONE, PlanItemStatus.PARTIAL) for s in sts)
    )

    return AdherenceOut(
        total=total, done=done, partial=partial, skipped=skipped, pending=pending,
        adherence_pct=pct, current_streak=streak,
        days_behind=result.days_behind, carried_over=result.carried_over,
        consistency=await _consistency(db, user_id, today, tz, marked_dates),
    )


# ---------------------------------------------------------------------------
# Materialize today's computed items into plan_items (idempotent)
# ---------------------------------------------------------------------------

async def _materialize_today(db: AsyncSession, user_id, today: date, result: scheduler.ScheduleResult, plan_version: int):
    for s in result.items:
        if s.scheduled_date != today:
            continue
        values = dict(
            user_id=user_id, plan_version=plan_version, scheduled_date=today,
            activity=s.activity, concept_id=s.concept_id, drill_ref=s.drill_ref,
            drill_variant=s.drill_variant, target_qty=s.target_qty, target_unit=s.target_unit,
            est_minutes=s.est_minutes, sort_order=s.sort_order,
            status=PlanItemStatus.PENDING, done_qty=0,
        )
        stmt = pg_insert(PlanItem).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                PlanItem.user_id, PlanItem.scheduled_date, PlanItem.activity,
                PlanItem.concept_id, PlanItem.drill_ref, PlanItem.drill_variant,
            ],
            index_where=_NOT_DELETED,
            set_={
                "plan_version": stmt.excluded.plan_version,
                "target_qty": stmt.excluded.target_qty,
                "target_unit": stmt.excluded.target_unit,
                "est_minutes": stmt.excluded.est_minutes,
                "sort_order": stmt.excluded.sort_order,
            },
            # Only refresh untouched (pending) items — never clobber a mark.
            where=PlanItem.status == PlanItemStatus.PENDING,
        )
        await db.execute(stmt)
    await db.commit()


# ===========================================================================
# GET | PUT /api/preferences
# ===========================================================================

@router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return _prefs_out(await _load_prefs(db, current_user.id))


@router.put("/preferences", response_model=PreferencesOut)
async def put_preferences(
    body: PreferencesIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    track = body.normalized_track()
    existing = await _load_prefs(db, current_user.id)
    if existing is None:
        row = StudyPreferences(
            user_id=current_user.id, timezone=body.timezone,
            mon_minutes=body.mon_minutes, tue_minutes=body.tue_minutes, wed_minutes=body.wed_minutes,
            thu_minutes=body.thu_minutes, fri_minutes=body.fri_minutes, sat_minutes=body.sat_minutes,
            sun_minutes=body.sun_minutes, max_session_minutes=body.max_session_minutes,
            blackout_dates=body.blackout_dates or None, target_go_live_date=body.target_go_live_date,
            active_track=track,
        )
        db.add(row)
    else:
        existing.timezone = body.timezone
        for col in _WEEKDAY_COLS:
            setattr(existing, col, getattr(body, col))
        existing.max_session_minutes = body.max_session_minutes
        existing.blackout_dates = body.blackout_dates or None
        existing.target_go_live_date = body.target_go_live_date
        existing.active_track = track
        row = existing
    await db.commit()
    await db.refresh(row)
    return _prefs_out(row)


# ===========================================================================
# GET /api/plan/today
# ===========================================================================

@router.get("/plan/today", response_model=TodayOut)
async def get_plan_today(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _load_prefs(db, current_user.id)
    if prefs is None:
        # No prefs yet — nothing to schedule. Return an empty, honest Today.
        today = _today_in("UTC")
        empty = scheduler.ScheduleResult(items=[])
        return TodayOut(
            date=today, active_track="aura", plan_version=1, items=[],
            adherence=await _adherence(db, current_user.id, today, empty),
            pace=PaceOut(),
        )

    today = _today_in(prefs.timezone)
    pview = _prefs_view(prefs)
    stage_metas, concepts, drills, cprog, dprog, cmeta, dtitles = await _load_inputs(
        db, current_user.id, prefs.active_track
    )
    past = await _load_past_pending(db, current_user.id, today)
    evidence = await load_stage_evidence(db, current_user.id, with_gate=False)
    result = scheduler.schedule(
        today, pview, stage_metas, concepts, drills, cprog, dprog, past,
        horizon_days=1, evidence=evidence,
    )

    await _materialize_today(db, current_user.id, today, result, prefs.plan_version)

    rows = (
        await db.execute(
            select(PlanItem).where(
                PlanItem.user_id == current_user.id,
                PlanItem.is_deleted.is_(False),
                PlanItem.scheduled_date == today,
            ).order_by(PlanItem.sort_order)
        )
    ).scalars().all()
    items = [_item_from_row(r, cmeta, dtitles) for r in rows]

    return TodayOut(
        date=today, active_track=prefs.active_track, plan_version=prefs.plan_version,
        items=items,
        adherence=await _adherence(db, current_user.id, today, result, prefs.timezone),
        pace=_pace_out(pview, result),
    )


# ===========================================================================
# GET /api/plan?from=&to=
# ===========================================================================

@router.get("/plan", response_model=PlanRangeOut)
async def get_plan_range(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _load_prefs(db, current_user.id)
    tz = prefs.timezone if prefs else "UTC"
    today = _today_in(tz)
    date_from = date_from or today
    date_to = date_to or (today + timedelta(days=30))
    if date_to < date_from:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="`to` must be ≥ `from`")

    if prefs is None:
        return PlanRangeOut(
            date_from=date_from, date_to=date_to, active_track="aura", plan_version=1,
            items=[], pace=PaceOut(),
        )

    pview = _prefs_view(prefs)
    stage_metas, concepts, drills, cprog, dprog, cmeta, dtitles = await _load_inputs(
        db, current_user.id, prefs.active_track
    )
    past = await _load_past_pending(db, current_user.id, today)
    evidence = await load_stage_evidence(db, current_user.id, with_gate=False)
    horizon = max(1, (date_to - today).days)
    result = scheduler.schedule(
        today, pview, stage_metas, concepts, drills, cprog, dprog, past,
        horizon_days=horizon, evidence=evidence,
    )

    # Past + today: FROZEN (from plan_items). Future: COMPUTED (from the scheduler).
    frozen_rows = (
        await db.execute(
            select(PlanItem).where(
                PlanItem.user_id == current_user.id,
                PlanItem.is_deleted.is_(False),
                PlanItem.scheduled_date >= date_from,
                PlanItem.scheduled_date <= min(today, date_to),
            ).order_by(PlanItem.scheduled_date, PlanItem.sort_order)
        )
    ).scalars().all()
    items = [_item_from_row(r, cmeta, dtitles) for r in frozen_rows]
    items += [
        _item_from_spec(s, cmeta, dtitles)
        for s in result.items
        if today < s.scheduled_date <= date_to
    ]
    items.sort(key=lambda i: (i.scheduled_date, i.sort_order))

    return PlanRangeOut(
        date_from=date_from, date_to=date_to, active_track=prefs.active_track,
        plan_version=prefs.plan_version, items=items, pace=_pace_out(pview, result),
        unplaced=len(result.unplaced),
    )


# ===========================================================================
# POST /api/plan/regenerate
# ===========================================================================

@router.post("/plan/regenerate", response_model=TodayOut)
async def regenerate_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _load_prefs(db, current_user.id)
    if prefs is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No study preferences set — configure /api/preferences first.",
        )

    today = _today_in(prefs.timezone)
    # Bump the plan version; frozen PAST items keep their original version.
    prefs.plan_version += 1
    prefs.generated_at = datetime.now(timezone.utc)
    new_version = prefs.plan_version

    # Clear today's PENDING items so they re-materialize fresh at the new version;
    # done/partial/skipped items are kept (accountability record).
    await db.execute(
        update(PlanItem)
        .where(
            PlanItem.user_id == current_user.id,
            PlanItem.is_deleted.is_(False),
            PlanItem.scheduled_date == today,
            PlanItem.status == PlanItemStatus.PENDING,
        )
        .values(is_deleted=True, deleted_at=datetime.now(timezone.utc))
    )
    await db.commit()

    pview = _prefs_view(prefs)
    stage_metas, concepts, drills, cprog, dprog, cmeta, dtitles = await _load_inputs(
        db, current_user.id, prefs.active_track
    )
    past = await _load_past_pending(db, current_user.id, today)
    evidence = await load_stage_evidence(db, current_user.id, with_gate=False)
    result = scheduler.schedule(
        today, pview, stage_metas, concepts, drills, cprog, dprog, past,
        horizon_days=1, evidence=evidence,
    )
    await _materialize_today(db, current_user.id, today, result, new_version)

    rows = (
        await db.execute(
            select(PlanItem).where(
                PlanItem.user_id == current_user.id,
                PlanItem.is_deleted.is_(False),
                PlanItem.scheduled_date == today,
            ).order_by(PlanItem.sort_order)
        )
    ).scalars().all()
    items = [_item_from_row(r, cmeta, dtitles) for r in rows]

    return TodayOut(
        date=today, active_track=prefs.active_track, plan_version=new_version, items=items,
        adherence=await _adherence(db, current_user.id, today, result, prefs.timezone),
        pace=_pace_out(pview, result),
    )


# ===========================================================================
# PATCH /api/plan/items/{item_id}  — mark done/partial/skipped → feed progress
# ===========================================================================

async def _feed_concept(db: AsyncSession, user_id, concept_id, today: date):
    """Record that the concept was practised today.

    PHASE E2 — THIS NO LONGER CREDITS REPS. Marking a plan item done used to
    increment `concept_progress.reps`, which made this endpoint a second way to
    mint an unevidenced rep; with `reps` derived from `evidence_assets` there is
    no number here to write. `last_practiced` still moves, because spaced review
    schedules off it and a review IS practice — what it is not, on its own, is
    proof of the work.
    """
    existing = (
        await db.execute(
            select(ConceptProgress).where(
                ConceptProgress.user_id == user_id,
                ConceptProgress.concept_id == concept_id,
                ConceptProgress.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    values = dict(
        user_id=user_id, concept_id=concept_id,
        ladder_stage=existing.ladder_stage if existing else None,
        confidence=existing.confidence if existing else None,
        last_practiced=today,
        notes=existing.notes if existing else None,
    )
    stmt = pg_insert(ConceptProgress).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ConceptProgress.user_id, ConceptProgress.concept_id],
        index_where=_NOT_DELETED,
        set_={"last_practiced": stmt.excluded.last_practiced},
    )
    await db.execute(stmt)


async def _feed_drill(db: AsyncSession, user_id, drill_ref: str, variant: str | None, today: date):
    """As `_feed_concept`: the ✋/🛠 variant mark and `last_practiced` are recorded;
    the rep count is not, because reps come only from evidence (Phase E2)."""
    existing = (
        await db.execute(
            select(DrillProgress).where(
                DrillProgress.user_id == user_id,
                DrillProgress.drill_ref == drill_ref,
                DrillProgress.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    hand = (existing.hand_done if existing else False) or (variant == "hand")
    tool = (existing.tool_done if existing else False) or (variant == "tool")
    values = dict(
        user_id=user_id, drill_ref=drill_ref,
        hand_done=hand, tool_done=tool, last_practiced=today,
        notes=existing.notes if existing else None,
    )
    stmt = pg_insert(DrillProgress).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DrillProgress.user_id, DrillProgress.drill_ref],
        index_where=_NOT_DELETED,
        set_={
            "hand_done": stmt.excluded.hand_done,
            "tool_done": stmt.excluded.tool_done,
            "last_practiced": stmt.excluded.last_practiced,
        },
    )
    await db.execute(stmt)


@router.patch("/plan/items/{item_id}", response_model=PlanItemOut)
async def patch_plan_item(
    item_id: str,
    body: PlanItemPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = (
        await db.execute(
            select(PlanItem).where(
                PlanItem.id == item_id,
                PlanItem.user_id == current_user.id,
                PlanItem.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan item not found")

    prefs = await _load_prefs(db, current_user.id)
    today = _today_in(prefs.timezone if prefs else "UTC")

    completed = body.status in (PlanItemStatus.DONE, PlanItemStatus.PARTIAL)

    item.status = body.status
    item.done_qty = body.done_qty if body.done_qty is not None else (item.done_qty or (1 if body.status == PlanItemStatus.DONE else 0))
    item.completed_at = datetime.now(timezone.utc) if completed else None

    # Record the practice (last_practiced + the ✋/🛠 mark). Phase E2: this no
    # longer credits reps — `done_qty` remains the plan's own record of how much
    # was worked, but the rep count is derived from `evidence_assets`, so marking
    # a plan item done can no longer mint an unevidenced rep. Without this change
    # the planner would be a bypass around the whole evidence layer.
    if completed:
        if item.concept_id is not None and item.activity in (
            PlanActivity.LEARN, PlanActivity.REVIEW, PlanActivity.OBSERVE, PlanActivity.HABIT
        ):
            await _feed_concept(db, current_user.id, item.concept_id, today)
        elif item.drill_ref is not None and item.activity == PlanActivity.DRILL:
            await _feed_drill(db, current_user.id, item.drill_ref, item.drill_variant, today)

    await db.commit()
    await db.refresh(item)

    # Enrichment for the response.
    cmeta: dict = {}
    dtitles: dict = {}
    if item.concept_id is not None:
        c = (await db.execute(select(Concept).where(Concept.id == item.concept_id))).scalar_one_or_none()
        if c is not None:
            cmeta[c.id] = (c.slug, c.title, c.content_slug)
    if item.drill_ref is not None:
        d = (await db.execute(select(Drill).where(Drill.drill_ref == item.drill_ref))).scalar_one_or_none()
        if d is not None:
            dtitles[item.drill_ref] = d.title
    return _item_from_row(item, cmeta, dtitles)


# ===========================================================================
# GET | POST /api/rest-days  — declared rest days (Phase E6)
#
# THERE IS NO PATCH AND NO DELETE, and that is the design rather than an
# omission — the same call `routers/predictions.py` made, for the same reason.
# A rest day's only effect is that it does not BREAK an evidence streak, so the
# record is worth reading only if the declared set is the set actually committed
# to in advance. An editable rest day could be slid onto a day you later turn out
# to have missed, and a deletable one lets the set be curated after the fact.
# Alembic `0012` makes both structurally impossible (a freeze trigger, and no
# `is_deleted` column), so this router cannot regress the property by accident.
# Pinned by a test that fails if either verb is ever added.
# ===========================================================================


def _rest_day_out(row: RestDay) -> RestDayOut:
    return RestDayOut(
        id=row.id,
        rest_date=row.rest_date,
        reason=row.reason,
        declared_at=row.declared_at,
        # Surfaced so a same-day declaration reads as one. The trigger blocks the
        # PAST outright; how far ahead of that is judgement, and §5's rule for
        # judgement-shaped things is to show them, not to gate on them.
        days_declared_ahead=(row.rest_date - row.declared_at.astimezone(timezone.utc).date()).days,
    )


@router.get("/rest-days", response_model=list[RestDayOut])
async def list_rest_days(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(RestDay)
            .where(RestDay.user_id == current_user.id)
            .order_by(RestDay.rest_date.desc())
        )
    ).scalars().all()
    return [_rest_day_out(r) for r in rows]


@router.post("/rest-days", response_model=RestDayOut, status_code=status.HTTP_201_CREATED)
async def declare_rest_day(
    body: RestDayIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Book a day off, ahead of time.

    The in-advance rule is enforced by `trg_rest_days_declared_in_advance`, not
    here — the router only translates the refusal into an HTTP status. Checking it
    in Python as well would be the guard-that-must-be-remembered shape §E2 argued
    against; the value of the DB check is that a future endpoint cannot bypass it.
    """
    today = _today_in((await _load_prefs(db, current_user.id) or StudyPreferences()).timezone or "UTC")
    if body.rest_date < today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"A rest day must be declared in advance — {body.rest_date.isoformat()} has "
                f"already passed (today is {today.isoformat()}). Booking a day off after the "
                "fact is a streak freeze, and the streak is only worth reading because it "
                "cannot be repaired retroactively."
            ),
        )

    existing = (
        await db.execute(
            select(RestDay).where(
                RestDay.user_id == current_user.id,
                RestDay.rest_date == body.rest_date,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{body.rest_date.isoformat()} is already declared a rest day "
                f"(booked {existing.declared_at.date().isoformat()})."
            ),
        )

    row = RestDay(user_id=current_user.id, rest_date=body.rest_date, reason=body.reason)
    db.add(row)
    try:
        await db.commit()
    except DBAPIError as exc:  # the trigger fired (a race, or a clock disagreement)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A rest day must be declared in advance.",
        ) from exc
    await db.refresh(row)
    return _rest_day_out(row)
