"""Pydantic response schemas for the Content API (Phase 5d).

Content is shared (not user-scoped) but the endpoints require a valid Bearer
token for parity with the protected SPA. See app/routers/content.py.
"""

from pydantic import BaseModel

from app.models.enums import UStage


class ContentPageSummary(BaseModel):
    """List/tree item — enough for the /library browser + the frontend's
    wikilink resolution maps (slug + source_path)."""

    slug: str
    title: str
    category: str | None = None
    u_stage: UStage | None = None
    tier: str | None = None
    label: str | None = None
    source_path: str | None = None

    model_config = {"from_attributes": True}


class ConceptBadge(BaseModel):
    """The TIER/label badge shown on a reader page, sourced from the concept(s)
    that reference this page (frontier concepts carry tier/label + watch_only).
    Only emitted when a referencing concept carries a label."""

    code: str | None = None
    tier: str | None = None
    label: str | None = None
    watch_only: bool = False


class ContentPageDetail(ContentPageSummary):
    """Full page — adds the markdown body, tags, and resolved wikilink targets."""

    body: str
    tags: list[str] | None = None
    wikilink_targets: list[str] | None = None
    badge: ConceptBadge | None = None
