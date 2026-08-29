"""Public corpus counts — the only unauthenticated data endpoint.

WHY THIS EXISTS. The landing page publishes figures ("74 concepts", "58 drills"),
and a published figure should carry a real basis rather than being typed into
JSX where it rots at the next re-seed. Every other content route sits behind
`get_current_user`, so a signed-out page cannot read them.

WHY IT IS SAFE TO LEAVE OPEN. It returns row counts of SEED content — the shared
curriculum projected from the wiki — and nothing user-scoped. No user, progress,
journal, evidence or prediction row is reachable here, and the counts are the
same for everybody. It is deliberately the only exception to the auth rule, and
it must stay counts-only: never add a listing or a filter to this module.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.concept import Concept
from app.models.content_page import ContentPage
from app.models.drill import Drill
from app.models.rubric import Rubric, RubricItem
from app.models.track_stage import TrackStage

router = APIRouter(prefix="/api", tags=["system"])


class CorpusStats(BaseModel):
    concepts: int
    track_stages: int
    drills: int
    content_pages: int
    rubrics: int
    rubric_items: int


@router.get("/stats", response_model=CorpusStats)
async def corpus_stats(db: AsyncSession = Depends(get_db)) -> CorpusStats:
    """Seed-content row counts. Unauthenticated by design; see the module docstring."""

    async def count(model) -> int:
        result = await db.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())

    return CorpusStats(
        concepts=await count(Concept),
        track_stages=await count(TrackStage),
        drills=await count(Drill),
        content_pages=await count(ContentPage),
        rubrics=await count(Rubric),
        rubric_items=await count(RubricItem),
    )
