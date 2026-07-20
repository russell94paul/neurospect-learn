"""Content API — serves the ingested wiki corpus (Phase 5d).

Read-only. Content is shared across users; every endpoint still requires a valid
Bearer token (get_current_user) for parity with the protected SPA. Populate the
table with `poetry run python -m scripts.ingest_content`.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.concept import Concept
from app.models.content_page import ContentPage
from app.models.user import User
from app.schemas.content import ConceptBadge, ContentPageDetail, ContentPageSummary

router = APIRouter(
    prefix="/api/content",
    tags=["content"],
    dependencies=[Depends(get_current_user)],
)

_SUMMARY_COLS = (
    ContentPage.slug,
    ContentPage.title,
    ContentPage.category,
    ContentPage.u_stage,
    ContentPage.tier,
    ContentPage.label,
    ContentPage.source_path,
)


# ---------------------------------------------------------------------------
# GET /api/content/pages — flat list of summaries (frontend groups by category)
# ---------------------------------------------------------------------------

@router.get("/pages", response_model=list[ContentPageSummary])
async def list_pages(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(*_SUMMARY_COLS).order_by(ContentPage.category, ContentPage.title)
    )
    return [ContentPageSummary.model_validate(row) for row in result.mappings()]


# ---------------------------------------------------------------------------
# GET /api/content/search?q= — simple ILIKE over title + body
# ---------------------------------------------------------------------------

@router.get("/search", response_model=list[ContentPageSummary])
async def search_pages(
    q: str = Query(..., min_length=2, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    like = f"%{q.strip()}%"
    result = await db.execute(
        select(*_SUMMARY_COLS)
        .where(or_(ContentPage.title.ilike(like), ContentPage.body.ilike(like)))
        .order_by(ContentPage.category, ContentPage.title)
        .limit(50)
    )
    return [ContentPageSummary.model_validate(row) for row in result.mappings()]


# ---------------------------------------------------------------------------
# GET /api/content/pages/{slug} — full page + the referencing concept's badge
# ---------------------------------------------------------------------------

@router.get("/pages/{slug}", response_model=ContentPageDetail)
async def get_page(slug: str, db: AsyncSession = Depends(get_db)):
    page = (
        await db.execute(select(ContentPage).where(ContentPage.slug == slug))
    ).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    # Badge: prefer a referencing concept that carries a label (frontier);
    # otherwise fall back to the first referencing concept. watch_only is true
    # if ANY referencing concept is watch-only (never let a watch-only concept
    # read as gate-eligible in the UI).
    concepts = (
        await db.execute(select(Concept).where(Concept.content_slug == slug))
    ).scalars().all()
    badge: ConceptBadge | None = None
    if concepts:
        primary = next((c for c in concepts if c.label), concepts[0])
        if primary.tier or primary.label or any(c.watch_only for c in concepts):
            badge = ConceptBadge(
                code=primary.code,
                tier=primary.tier,
                label=primary.label,
                watch_only=any(c.watch_only for c in concepts),
            )

    detail = ContentPageDetail.model_validate(page)
    detail.badge = badge
    return detail
