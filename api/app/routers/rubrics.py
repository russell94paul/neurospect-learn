"""Rubric API (Phase E3) — the drill's own bar, READ-ONLY.

E2 made a rep require EVIDENCE. E3 makes it require evidence the user has checked
against the drill's own bar — tier 2 of the design's three tiers, and the tier
that defines what "graded" MEANS for a rep.

**There is no POST/PATCH/DELETE here, on purpose.** Rubrics are seed content
projected from the wiki by `scripts/seed_rubrics.py`, for the same structural
reason there is no writable `reps` and no `cleared` column: if the app could
author rubric text, the wiki would stop being canonical and the bar would drift
from the curriculum it exists to enforce. Editing a bar means editing the wiki and
re-seeding.

The WRITE side — the self-check itself — lives in `routers/evidence.py` beside
the other grade writes, since it appends to `evidence_grades` rather than touching
a rubric. The decision about whether an unchecked rep still counts is documented
there.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.concept import Concept
from app.models.rubric import Rubric
from app.models.user import User
from app.schemas.rubric import RubricOut

router = APIRouter(prefix="/api", tags=["rubrics"])


# ---------------------------------------------------------------------------
# GET /api/rubrics — the projected bar (read-only)
# ---------------------------------------------------------------------------

@router.get("/rubrics", response_model=list[RubricOut])
async def list_rubrics(
    drill_ref: str | None = Query(None, description="Exact drill_ref, e.g. 'aura D1-a'"),
    concept_id: uuid.UUID | None = Query(None, description="All rubrics for this concept's drills"),
    concept_slug: str | None = Query(None, description="Same, by concept slug"),
    track: str | None = Query(None, description="aura | ict_course"),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The rubrics matching the filter, each with its items in wiki order.

    The concept lookup goes through `concepts.drill_refs` — the same soft
    back-link `seed_drills.py` derives `concept_slugs` from — so a concept's bar
    is the union of the bars of the drills that advance it. A concept whose
    drills have no projectable bullets returns `[]` honestly rather than 404.
    """
    stmt = select(Rubric).order_by(Rubric.track, Rubric.drill_ref)

    if drill_ref is not None:
        stmt = stmt.where(Rubric.drill_ref == drill_ref)
    if track is not None:
        stmt = stmt.where(Rubric.track == track)

    if concept_id is not None or concept_slug is not None:
        cstmt = select(Concept.drill_refs)
        cstmt = (
            cstmt.where(Concept.id == concept_id)
            if concept_id is not None
            else cstmt.where(Concept.slug == concept_slug)
        )
        refs = (await db.execute(cstmt)).scalar_one_or_none()
        if refs is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
        if not refs:
            return []
        stmt = stmt.where(Rubric.drill_ref.in_(refs))

    return list((await db.execute(stmt)).scalars().all())
