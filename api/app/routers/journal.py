"""Model-aligned journal API (Phase 5f) — CRUD over `journal_entries`.

All endpoints are auth-gated and user-scoped: a user sees and edits only their
own entries. Rows are SOFT-deleted (`is_deleted` + `deleted_at`), mirroring the
0003 table + the drill_progress idiom. `mode` (backtest|live) + `entry_model`
are required on create (the axis discriminator + the expectancy-grouping key);
the rest is optional so a setup can be logged before it closes.

This is the write side of the proof-of-edge loop; the read/aggregate side is
app/routers/analytics.py. No gate verdict here (that is Phase 5g).
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.enums import EntryModel, JournalMode
from app.models.journal_entry import JournalEntry
from app.models.user import User
from app.schemas.journal import JournalEntryIn, JournalEntryOut, JournalEntryUpdate

router = APIRouter(
    prefix="/api",
    tags=["journal"],
    dependencies=[Depends(get_current_user)],
)


async def _get_owned(db: AsyncSession, user_id, entry_id: str) -> JournalEntry:
    entry = (
        await db.execute(
            select(JournalEntry).where(
                JournalEntry.id == entry_id,
                JournalEntry.user_id == user_id,
                JournalEntry.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return entry


# ---------------------------------------------------------------------------
# POST /api/journal — create
# ---------------------------------------------------------------------------

@router.post("/journal", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: JournalEntryIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = JournalEntry(user_id=current_user.id, **body.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# GET /api/journal — this user's entries, newest first, with filters
# ---------------------------------------------------------------------------

@router.get("/journal", response_model=list[JournalEntryOut])
async def list_entries(
    mode: JournalMode | None = Query(None),
    entry_model: EntryModel | None = Query(None),
    instrument: str | None = Query(None),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(JournalEntry)
        .where(
            JournalEntry.user_id == current_user.id,
            JournalEntry.is_deleted.is_(False),
        )
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
    )
    if mode is not None:
        stmt = stmt.where(JournalEntry.mode == mode)
    if entry_model is not None:
        stmt = stmt.where(JournalEntry.entry_model == entry_model)
    if instrument:
        stmt = stmt.where(JournalEntry.instrument == instrument)
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# GET /api/journal/{id}
# ---------------------------------------------------------------------------

@router.get("/journal/{entry_id}", response_model=JournalEntryOut)
async def get_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_owned(db, current_user.id, entry_id)


# ---------------------------------------------------------------------------
# PATCH /api/journal/{id} — partial update
# ---------------------------------------------------------------------------

@router.patch("/journal/{entry_id}", response_model=JournalEntryOut)
async def update_entry(
    entry_id: str,
    body: JournalEntryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await _get_owned(db, current_user.id, entry_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    await db.commit()
    await db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# DELETE /api/journal/{id} — soft delete
# ---------------------------------------------------------------------------

@router.delete("/journal/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await _get_owned(db, current_user.id, entry_id)
    entry.is_deleted = True
    entry.deleted_at = datetime.now(timezone.utc)
    await db.commit()
