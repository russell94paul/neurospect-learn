"""Learning API — per-user progress, derived stage exit-bars, and drills (5e-1).

All endpoints are auth-gated and user-scoped: a user sees and edits only their
own concept_progress / drill_progress. `concepts` + `drills` are shared seed
content. Stage status is COMPUTED by app/services/stages.py (never stored).

Progress rows are created LAZILY: GET /progress LEFT JOINs so untracked concepts
read null; PATCH /progress upserts exactly one row on demand — never pre-seeds.
Advancing ladder to Can-mark+ is gated (reps ≥ parsed target AND confidence set)
per the north star — no self-declared skips.
"""

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.concept import Concept
from app.models.concept_progress import ConceptProgress
from app.models.drill import Drill
from app.models.drill_progress import DrillProgress
from app.models.user import User
from app.schemas.learning import (
    ConceptOut,
    DrillOut,
    DrillPatch,
    ProgressPatch,
    ProgressRow,
    StageOut,
)
from app.services import rep_targets, stages

router = APIRouter(
    prefix="/api",
    tags=["learning"],
    dependencies=[Depends(get_current_user)],
)

CAN_MARK = stages.CAN_MARK

# The exact predicate of the partial unique indexes (mirrors the 0002/0004 DDL:
# `WHERE NOT is_deleted`). ON CONFLICT index inference requires the predicate to
# match the index's textually — `is_deleted IS false` does NOT match.
_NOT_DELETED = text("NOT is_deleted")


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _concept_out(c: Concept) -> ConceptOut:
    t = rep_targets.parse(c.rep_target)
    return ConceptOut(
        id=c.id, slug=c.slug, code=c.code, u_stage=c.u_stage, title=c.title,
        is_core=c.is_core, tier=c.tier, label=c.label, axis=c.axis,
        watch_only=c.watch_only, rep_target=c.rep_target,
        rep_target_kind=t.kind, rep_target_count=t.count,
        content_slug=c.content_slug, drill_refs=c.drill_refs,
        sort_order=c.sort_order, notes=c.notes,
    )


def _progress_row(c: Concept, pg: ConceptProgress | None) -> ProgressRow:
    t = rep_targets.parse(c.rep_target)
    return ProgressRow(
        concept_id=c.id, slug=c.slug, code=c.code, u_stage=c.u_stage, title=c.title,
        is_core=c.is_core, watch_only=c.watch_only, content_slug=c.content_slug,
        drill_refs=c.drill_refs, rep_target=c.rep_target,
        rep_target_kind=t.kind, rep_target_count=t.count, sort_order=c.sort_order,
        ladder_stage=pg.ladder_stage if pg else None,
        confidence=pg.confidence if pg else None,
        reps=pg.reps if pg else 0,
        last_practiced=pg.last_practiced if pg else None,
        notes=pg.notes if pg else None,
    )


def _drill_out(d: Drill, dp: DrillProgress | None) -> DrillOut:
    t = rep_targets.parse(d.rep_target)
    return DrillOut(
        id=d.id, drill_ref=d.drill_ref, track=d.track, stage_code=d.stage_code,
        title=d.title, advances_to=d.advances_to, rep_target=d.rep_target,
        rep_target_count=t.count, concept_slugs=d.concept_slugs, sort_order=d.sort_order,
        reps=dp.reps if dp else 0,
        hand_done=dp.hand_done if dp else False,
        tool_done=dp.tool_done if dp else False,
        last_practiced=dp.last_practiced if dp else None,
        notes=dp.notes if dp else None,
    )


# ---------------------------------------------------------------------------
# GET /api/concepts — the seed catalog (optionally by stage)
# ---------------------------------------------------------------------------

@router.get("/concepts", response_model=list[ConceptOut])
async def list_concepts(
    stage: str | None = Query(None, description="Filter by U-stage, e.g. U1"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Concept).order_by(Concept.sort_order)
    if stage:
        stmt = stmt.where(Concept.u_stage == stage)
    rows = (await db.execute(stmt)).scalars().all()
    return [_concept_out(c) for c in rows]


# ---------------------------------------------------------------------------
# GET /api/progress — LEFT JOIN concepts × this user's concept_progress
# ---------------------------------------------------------------------------

@router.get("/progress", response_model=list[ProgressRow])
async def get_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Concept, ConceptProgress)
        .outerjoin(
            ConceptProgress,
            and_(
                ConceptProgress.concept_id == Concept.id,
                ConceptProgress.user_id == current_user.id,
                ConceptProgress.is_deleted.is_(False),
            ),
        )
        .order_by(Concept.sort_order)
    )
    rows = (await db.execute(stmt)).all()
    return [_progress_row(c, pg) for c, pg in rows]


# ---------------------------------------------------------------------------
# PATCH /api/progress — lazy upsert one concept's progress (gated advance)
# ---------------------------------------------------------------------------

@router.patch("/progress", response_model=ProgressRow)
async def patch_progress(
    body: ProgressPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    concept = (
        await db.execute(select(Concept).where(Concept.id == body.concept_id))
    ).scalar_one_or_none()
    if concept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found")

    existing = (
        await db.execute(
            select(ConceptProgress).where(
                ConceptProgress.user_id == current_user.id,
                ConceptProgress.concept_id == body.concept_id,
                ConceptProgress.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()

    provided = body.model_dump(exclude_unset=True)

    def resolved(field: str, default):
        if field in provided:
            return provided[field]
        return getattr(existing, field) if existing else default

    final_ladder = resolved("ladder_stage", None)
    final_conf = resolved("confidence", None)
    final_reps = resolved("reps", 0) or 0

    # Frontier invariant: watch-only (U5) concepts are observation-only and may
    # never advance past Can-mark (never live-gate-eligible).
    if concept.watch_only and final_ladder is not None and final_ladder > CAN_MARK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Watch-only (frontier) concepts are observation-only — capped at Can-mark.",
        )

    # North-star enforcement: no Can-mark+ without reps ≥ target AND confidence.
    if final_ladder is not None and final_ladder >= CAN_MARK:
        target = rep_targets.parse(concept.rep_target)
        if final_conf is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot advance to Can-mark+ without a confidence rating.",
            )
        if not rep_targets.meets(final_reps, target):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot advance to Can-mark+ until reps ≥ target "
                    f"({final_reps}/{target.count} for '{target.raw}')."
                ),
            )

    values = {
        "user_id": current_user.id,
        "concept_id": body.concept_id,
        "ladder_stage": final_ladder,
        "confidence": final_conf,
        "reps": final_reps,
        "last_practiced": resolved("last_practiced", None),
        "notes": resolved("notes", None),
    }
    stmt = pg_insert(ConceptProgress).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ConceptProgress.user_id, ConceptProgress.concept_id],
        index_where=_NOT_DELETED,
        set_={
            "ladder_stage": stmt.excluded.ladder_stage,
            "confidence": stmt.excluded.confidence,
            "reps": stmt.excluded.reps,
            "last_practiced": stmt.excluded.last_practiced,
            "notes": stmt.excluded.notes,
        },
    )
    await db.execute(stmt)
    await db.commit()

    # Build the response from the values just committed. Re-SELECTing through
    # the ORM would return the stale identity-map row loaded above (session has
    # expire_on_commit=False); this reflects exactly what was written.
    written = SimpleNamespace(
        ladder_stage=final_ladder, confidence=final_conf, reps=final_reps,
        last_practiced=values["last_practiced"], notes=values["notes"],
    )
    return _progress_row(concept, written)


# ---------------------------------------------------------------------------
# GET /api/stages — the derived exit-bar status per U-stage
# ---------------------------------------------------------------------------

@router.get("/stages", response_model=list[StageOut])
async def get_stages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Concept, ConceptProgress)
            .outerjoin(
                ConceptProgress,
                and_(
                    ConceptProgress.concept_id == Concept.id,
                    ConceptProgress.user_id == current_user.id,
                    ConceptProgress.is_deleted.is_(False),
                ),
            )
            .order_by(Concept.sort_order)
        )
    ).all()

    views = [
        stages.ConceptView(
            slug=c.slug, code=c.code, u_stage=c.u_stage.value, title=c.title,
            is_core=c.is_core, watch_only=c.watch_only, rep_target=c.rep_target,
        )
        for c, _ in rows
    ]
    progress = {
        c.slug: stages.ProgressView(pg.ladder_stage, pg.confidence, pg.reps)
        for c, pg in rows
        if pg is not None
    }
    return [
        StageOut(
            u_stage=s.u_stage, title=s.title, watch_only=s.watch_only,
            never_gate_eligible=s.never_gate_eligible, locked=s.locked, met=s.met,
            auto_met=s.auto_met, attest_pending=s.attest_pending,
            total=s.total, reached=s.reached,
            requirements=[
                {
                    "label": r.label, "met": r.met, "attest": r.attest,
                    "concept_slug": r.concept_slug, "concept_code": r.concept_code,
                }
                for r in s.requirements
            ],
        )
        for s in stages.compute_stages(views, progress)
    ]


# ---------------------------------------------------------------------------
# GET /api/drills — the catalog + this user's drill_progress
# ---------------------------------------------------------------------------

@router.get("/drills", response_model=list[DrillOut])
async def get_drills(
    track: str | None = Query(None, description="aura | ict_course"),
    stage: str | None = Query(None, description="track stage_code, e.g. 1"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Drill, DrillProgress)
        .outerjoin(
            DrillProgress,
            and_(
                DrillProgress.drill_ref == Drill.drill_ref,
                DrillProgress.user_id == current_user.id,
                DrillProgress.is_deleted.is_(False),
            ),
        )
        .order_by(Drill.sort_order)
    )
    if track:
        stmt = stmt.where(Drill.track == track)
    if stage:
        stmt = stmt.where(Drill.stage_code == stage)
    rows = (await db.execute(stmt)).all()
    return [_drill_out(d, dp) for d, dp in rows]


# ---------------------------------------------------------------------------
# PATCH /api/drills — lazy upsert one drill_progress
# ---------------------------------------------------------------------------

@router.patch("/drills", response_model=DrillOut)
async def patch_drill(
    body: DrillPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    drill = (
        await db.execute(select(Drill).where(Drill.drill_ref == body.drill_ref))
    ).scalar_one_or_none()
    if drill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drill not found")

    existing = (
        await db.execute(
            select(DrillProgress).where(
                DrillProgress.user_id == current_user.id,
                DrillProgress.drill_ref == body.drill_ref,
                DrillProgress.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()

    provided = body.model_dump(exclude_unset=True)

    def resolved(field: str, default):
        if field in provided:
            return provided[field]
        return getattr(existing, field) if existing else default

    values = {
        "user_id": current_user.id,
        "drill_ref": body.drill_ref,
        "reps": resolved("reps", 0) or 0,
        "hand_done": bool(resolved("hand_done", False)),
        "tool_done": bool(resolved("tool_done", False)),
        "last_practiced": resolved("last_practiced", None),
        "notes": resolved("notes", None),
    }
    stmt = pg_insert(DrillProgress).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[DrillProgress.user_id, DrillProgress.drill_ref],
        index_where=_NOT_DELETED,
        set_={
            "reps": stmt.excluded.reps,
            "hand_done": stmt.excluded.hand_done,
            "tool_done": stmt.excluded.tool_done,
            "last_practiced": stmt.excluded.last_practiced,
            "notes": stmt.excluded.notes,
        },
    )
    await db.execute(stmt)
    await db.commit()

    written = SimpleNamespace(
        reps=values["reps"], hand_done=values["hand_done"], tool_done=values["tool_done"],
        last_practiced=values["last_practiced"], notes=values["notes"],
    )
    return _drill_out(drill, written)
