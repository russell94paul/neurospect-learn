import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

import sqlalchemy as sa

from app.models.base import Base
from app.models.enums import PlanActivity, PlanItemStatus, pg_enum

# drill_variant is owned by migration 0004 (5e-1); bind by name, never (re)create.
_DRILL_VARIANT = sa.Enum("hand", "tool", name="drill_variant", create_type=False)


class PlanItem(Base):
    """One prescribed Study-Planner task on a date (Phase 5e-2).

    User-scoped + soft-deleted. plan_items are the FROZEN past/today schedule —
    the future is computed on read (pure function of curriculum + progress +
    prefs + today) and only materialized into rows once its date is `today`
    (idempotent via the `ux_plan_items_slot` partial-unique index).

    `concept_id` is a nullable hard FK (learn / review / observe / habit items);
    `drill_ref` is a nullable soft ref (drill items — matches the
    `concepts.drill_refs` / `drill_progress.drill_ref` convention). A concept-less
    evidence item (a `backtest` stage placeholder) carries both NULL.

    Marking an item done/partial (with `done_qty`) feeds
    `concept_progress`/`drill_progress` (reps + last_practiced) — see the planner
    router — honouring the existing ladder-advance gate and watch-only cap.
    """

    __tablename__ = "plan_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)

    activity: Mapped[PlanActivity] = mapped_column(
        pg_enum(PlanActivity, "plan_activity"), nullable=False
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id")
    )
    drill_ref: Mapped[str | None] = mapped_column(Text)  # soft ref → drills.drill_ref
    drill_variant: Mapped[str | None] = mapped_column(_DRILL_VARIANT)  # 'hand' | 'tool'

    target_qty: Mapped[int | None] = mapped_column(Integer)
    target_unit: Mapped[str | None] = mapped_column(String(16))  # reps | days | sessions | ...
    est_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")

    status: Mapped[PlanItemStatus] = mapped_column(
        pg_enum(PlanItemStatus, "plan_item_status"), nullable=False, server_default="pending"
    )
    done_qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
