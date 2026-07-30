"""Missed / canceled trade log API (Phase 6b) — CRUD over `missed_trades`.

Auth-gated + user-scoped + soft-deleted, mirroring routers/journal.py exactly
(same `_get_owned` guard, same partial PATCH, same 204 soft DELETE).

The north star says the journal covers EVERY trade including the ones you didn't
take: this is the surface for those. It is deliberately a separate table from
`journal_entries`, and — critically — **nothing here enters expectancy or the
Readiness-to-Live Gate**. `services/expectancy.py` and `services/gate.py` read
`journal_entries` only, so executed-trade expectancy can never be diluted by a
trade that was never taken (asserted in tests/test_missed_trades_api.py, which
pins /api/analytics/expectancy + /api/gate byte-identical across a missed-trade
write).

The analytic this table exists FOR — opportunity cost in R — lives on the
analytics router (`GET /api/analytics/missed-summary`) over the pure
app/services/opportunity_cost.py, alongside the executed-trade aggregates.
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.enums import EntryModel, HypotheticalOutcome, MissType
from app.models.missed_trade import MissedTrade
from app.models.user import User
from app.schemas.missed_trade import MissedTradeIn, MissedTradeOut, MissedTradeUpdate

router = APIRouter(
    prefix="/api",
    tags=["missed-trades"],
    dependencies=[Depends(get_current_user)],
)


async def _get_owned(db: AsyncSession, user_id, miss_id: str) -> MissedTrade:
    row = (
        await db.execute(
            select(MissedTrade).where(
                MissedTrade.id == miss_id,
                MissedTrade.user_id == user_id,
                MissedTrade.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Missed trade not found")
    return row


# ---------------------------------------------------------------------------
# POST /api/missed-trades — log a missed / hesitated / canceled setup
# ---------------------------------------------------------------------------

@router.post("/missed-trades", response_model=MissedTradeOut, status_code=status.HTTP_201_CREATED)
async def create_missed_trade(
    body: MissedTradeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = MissedTrade(user_id=current_user.id, **body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# GET /api/missed-trades — this user's log, newest first, with filters
# ---------------------------------------------------------------------------

@router.get("/missed-trades", response_model=list[MissedTradeOut])
async def list_missed_trades(
    miss_type: MissType | None = Query(None),
    entry_model: EntryModel | None = Query(None),
    hypothetical_outcome: HypotheticalOutcome | None = Query(None),
    instrument: str | None = Query(None),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MissedTrade)
        .where(
            MissedTrade.user_id == current_user.id,
            MissedTrade.is_deleted.is_(False),
        )
        .order_by(MissedTrade.entry_date.desc(), MissedTrade.created_at.desc())
    )
    if miss_type is not None:
        stmt = stmt.where(MissedTrade.miss_type == miss_type)
    if entry_model is not None:
        stmt = stmt.where(MissedTrade.entry_model == entry_model)
    if hypothetical_outcome is not None:
        stmt = stmt.where(MissedTrade.hypothetical_outcome == hypothetical_outcome)
    if instrument:
        stmt = stmt.where(MissedTrade.instrument == instrument)
    if date_from is not None:
        stmt = stmt.where(MissedTrade.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(MissedTrade.entry_date <= date_to)
    return list((await db.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# GET /api/missed-trades/{id}
# ---------------------------------------------------------------------------

@router.get("/missed-trades/{miss_id}", response_model=MissedTradeOut)
async def get_missed_trade(
    miss_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned(db, current_user.id, miss_id)


# ---------------------------------------------------------------------------
# PATCH /api/missed-trades/{id} — partial (e.g. resolve the hypothetical later)
# ---------------------------------------------------------------------------

@router.patch("/missed-trades/{miss_id}", response_model=MissedTradeOut)
async def update_missed_trade(
    miss_id: str,
    body: MissedTradeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_owned(db, current_user.id, miss_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# DELETE /api/missed-trades/{id} — soft delete
# ---------------------------------------------------------------------------

@router.delete("/missed-trades/{miss_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_missed_trade(
    miss_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_owned(db, current_user.id, miss_id)
    row.is_deleted = True
    row.deleted_at = datetime.now(timezone.utc)
    await db.commit()
