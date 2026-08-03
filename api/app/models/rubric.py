"""The rubric layer (Phase E3) — `rubrics` + `rubric_items`.

A rubric is a PROJECTION of one drill's ✋/🛠 bullets from the wiki exercise
libraries, not content authored here. See the Alembic `0010` docstring (the DDL
of record) and concepts/architecture/learning-enforcement.md §3.

Seed/content shape, mirroring `drills` and `concepts`: no soft-delete, no user
scoping — a re-seed replaces. The user's ANSWER to a rubric is not stored here;
it is an `evidence_grades` row with `grader='self_check'`, which `0009` already
created.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import RubricVariant, pg_enum


class Rubric(Base):
    """The bar for ONE drill, as projected from the wiki.

    `drill_ref` is a TEXT soft ref to `drills.drill_ref` (never a hard FK), so a
    rubric outlives a `drills` re-seed and may exist for a drill the map table
    has not yet listed.

    `version` bumps if and only if `content_hash` changes, so re-seeding
    unchanged content is a genuine no-op and a historical grade's stored
    `rubric_version` names the exact bar it was judged against.
    """

    __tablename__ = "rubrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    drill_ref: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    track: Mapped[str] = mapped_column(String(16), nullable=False)  # aura | ict_course

    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["RubricItem"]] = relationship(
        back_populates="rubric",
        cascade="all, delete-orphan",
        order_by="RubricItem.ordinal",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("track IN ('aura', 'ict_course')", name="ck_rubrics_track"),
        CheckConstraint("version >= 1", name="ck_rubrics_version"),
    )


class RubricItem(Base):
    """One checkable assertion — a verbatim clause of a wiki bullet.

    `text` keeps the raw markdown so the no-drift proof is a literal substring
    check against the source bullet; the UI strips the markers for display.

    `item_key` (e.g. "aura-d1-a#3") is the stable handle a self-check records,
    deliberately a TEXT key rather than this row's UUID: a re-seed replaces these
    rows, and a grade must stay legible afterwards (it also stores the item text).
    """

    __tablename__ = "rubric_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rubric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rubrics.id", ondelete="CASCADE"), nullable=False
    )

    item_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    bullet_ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    variant: Mapped[RubricVariant] = mapped_column(
        pg_enum(RubricVariant, "rubric_variant"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rule_refs: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rubric: Mapped[Rubric] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("ordinal >= 1", name="ck_rubric_items_ordinal"),
        CheckConstraint("bullet_ordinal >= 1", name="ck_rubric_items_bullet_ordinal"),
        CheckConstraint("length(btrim(text)) > 0", name="ck_rubric_items_text"),
    )
