import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import UStage, pg_enum


class ContentPage(Base):
    """A rendered wiki page served by the Content API.

    Created EMPTY in 5c; the 5d ingest job populates it (wiki markdown →
    content_pages, preserving TIER/label/tags + U-stage mapping + wikilink
    targets). Seed/content, not user-editable — no soft-delete (re-ingest
    replaces rows). The 5d ingest owns the slug scheme; `concepts.content_slug`
    soft-references `slug` here.
    """

    __tablename__ = "content_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # the markdown source

    # Frontmatter-preserved metadata (nullable — not every page maps to a stage).
    u_stage: Mapped[UStage | None] = mapped_column(pg_enum(UStage, "u_stage"))
    tier: Mapped[str | None] = mapped_column(String(32))
    label: Mapped[str | None] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(String(64))  # course / entry-models / mastery / advanced
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    wikilink_targets: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # internal link slugs
    source_path: Mapped[str | None] = mapped_column(Text)  # wiki file the row was ingested from

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
