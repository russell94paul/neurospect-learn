"""Expectancy / analytics API (Phase 5f) — the empirical proof-of-edge VIEW.

Auth-gated + user-scoped, read-only aggregation over the current user's
`journal_entries`. All three endpoints load the user's non-deleted entries once,
map them to `expectancy.TradeR`, and delegate to the pure math in
app/services/expectancy.py (unit-tested against hand-built fixtures).

`GET /api/analytics/expectancy` — per `entry_model` × `mode`.
`GET /api/analytics/summary`    — top-line per mode (backtest vs live).
`GET /api/analytics/r-distribution` — realized-R histogram, split by mode.

Backtest and live are NEVER conflated (mode is always a grouping key). No gate
verdict is emitted — the Readiness-to-Live decision is Phase 5g.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.journal_entry import JournalEntry
from app.models.user import User
from app.schemas.analytics import (
    ExpectancyGroup,
    ExpectancyOut,
    ModeSummary,
    RDistributionBucket,
    RDistributionOut,
    SummaryOut,
)
from app.services import expectancy

router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
    dependencies=[Depends(get_current_user)],
)


async def _load_trades(db: AsyncSession, user_id) -> list[expectancy.TradeR]:
    rows = (
        await db.execute(
            select(
                JournalEntry.entry_model,
                JournalEntry.mode,
                JournalEntry.r_multiple,
                JournalEntry.rr_planned,
            ).where(
                JournalEntry.user_id == user_id,
                JournalEntry.is_deleted.is_(False),
            )
        )
    ).all()
    return [
        expectancy.TradeR(
            entry_model=em.value if hasattr(em, "value") else str(em),
            mode=md.value if hasattr(md, "value") else str(md),
            r_multiple=float(r) if r is not None else None,
            rr_planned=float(rr) if rr is not None else None,
        )
        for em, md, r, rr in rows
    ]


@router.get("/expectancy", response_model=ExpectancyOut)
async def get_expectancy(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trades = await _load_trades(db, current_user.id)
    groups = expectancy.compute_groups(trades)
    return ExpectancyOut(
        sample_target=expectancy.SAMPLE_TARGET,
        groups=[ExpectancyGroup(**g.__dict__) for g in groups],
    )


@router.get("/summary", response_model=SummaryOut)
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trades = await _load_trades(db, current_user.id)
    modes = expectancy.compute_mode_summaries(trades)
    return SummaryOut(modes=[ModeSummary(**m.__dict__) for m in modes])


@router.get("/r-distribution", response_model=RDistributionOut)
async def get_r_distribution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trades = await _load_trades(db, current_user.id)
    buckets = expectancy.compute_r_distribution(trades)
    return RDistributionOut(buckets=[RDistributionBucket(**b) for b in buckets])
