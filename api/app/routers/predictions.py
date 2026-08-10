"""Pre-commitment API (Phase E5) — commit a call, then record what happened.

The anti-cheat value of this whole surface is in ONE property: the call was
recorded before the outcome was known. So the endpoints are deliberately
asymmetric —

* `POST /api/predictions` writes the call and NOTHING else. The server stamps
  `committed_at`; the client cannot supply it (422 naming the field).
* `POST /api/predictions/{id}/resolve` writes the reveal and NOTHING else. It is a
  separate, strictly later request, accepted exactly once (409 on a second try).
* **There is no PATCH and no DELETE.** Not "not built yet" — there must not be
  one. An editable call could be turned into a win after the fact, and a deletable
  one lets a ratio be inflated by dropping failures. Alembic `0011` makes both
  structurally impossible (a freeze trigger, and no `is_deleted` column), so this
  router cannot regress the property even by accident.

WHAT THIS CANNOT PROVE, stated plainly because the alternative is a false claim:
the app cannot see the user's TradingView replay, so it cannot know whether they
peeked before committing. What it CAN prove is that the record is honest — a call
cannot be back-dated, edited, re-resolved or removed. `seconds_to_reveal` is
surfaced so a suspiciously instant "reveal" is visible, in the §5 idiom: block the
certain, surface the rest. §9's own argument is the rest of the answer — faking a
prediction means fabricating a call that then gets scored against reality, which is
self-defeating.

NO REPS ARE MINTED HERE. `reps` stays derived from `evidence_assets.reps_claimed`
(E2). Invariant 5 gains no write path.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.drill import Drill
from app.models.evidence import EvidenceAsset
from app.models.prediction import Prediction
from app.models.user import User
from app.schemas.prediction import (
    CalibrationOut,
    ComponentScoreOut,
    PredictionCommit,
    PredictionOut,
    PredictionResolve,
)
from app.services import calibration, stages

router = APIRouter(prefix="/api", tags=["predictions"])


# ---------------------------------------------------------------------------
# Correctness — COMPUTED per read, never stored
# ---------------------------------------------------------------------------

def _as_call(p: Prediction) -> calibration.Call:
    """Map one row onto the pure calibration view.

    `bias` is scored as an EQUALITY over one vocabulary (so `neutral` called and
    `neutral` delivered is a hit, and `neutral` called into a trend is a miss — no
    free pass for declining to commit). The other three are the trader's own report
    of what happened, which is trustworthy here precisely BECAUSE the call was
    frozen first: there is nothing to gain by misreporting an outcome you already
    committed against.
    """
    if p.resolved_at is None:
        return calibration.Call(resolved=False)
    return calibration.Call(
        resolved=True,
        bias_correct=(p.outcome_bias == p.bias),
        dol_correct=p.dol_hit,
        entry_model_correct=p.model_played_out,
        target_correct=p.target_hit,
    )


def _out(p: Prediction) -> PredictionOut:
    call = _as_call(p)
    return PredictionOut(
        id=p.id,
        drill_ref=p.drill_ref,
        session_label=p.session_label,
        instrument=p.instrument,
        bias=p.bias,
        dol=p.dol,
        entry_model=p.entry_model,
        target=p.target,
        committed_at=p.committed_at,
        resolved_at=p.resolved_at,
        outcome_bias=p.outcome_bias,
        dol_hit=p.dol_hit,
        model_played_out=p.model_played_out,
        target_hit=p.target_hit,
        resolution_notes=p.resolution_notes,
        evidence_id=p.evidence_id,
        resolved=call.resolved,
        bias_correct=call.bias_correct,
        dol_correct=call.dol_correct,
        entry_model_correct=call.entry_model_correct,
        target_correct=call.target_correct,
        seconds_to_reveal=(
            int((p.resolved_at - p.committed_at).total_seconds())
            if p.resolved_at is not None
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Shared loader — the M6 bar reads this too (services/stages.py grades on it)
# ---------------------------------------------------------------------------

async def load_tape_coverage(db: AsyncSession, user_id) -> stages.TapeReads:
    """Which of the 14 tape drills carry a committed-before-the-reveal call.

    The bar is COMMITMENT AND RESOLUTION, never correctness — see
    `stages.TapeReads`. Being wrong in writing is the learning; making it cost a
    stage would teach the user to stop writing things down (§6).
    """
    rows = (
        await db.execute(
            select(Prediction.drill_ref, Prediction.resolved_at).where(
                Prediction.user_id == user_id,
                Prediction.drill_ref.in_(stages.TAPE_STUDY_DRILLS),
            )
        )
    ).all()
    committed = {ref for ref, _ in rows}
    resolved = {ref for ref, resolved_at in rows if resolved_at is not None}
    return stages.TapeReads(
        committed=frozenset(committed), resolved=frozenset(resolved), loaded=True
    )


# ---------------------------------------------------------------------------
# POST /api/predictions — commit the call
# ---------------------------------------------------------------------------

@router.post("/predictions", response_model=PredictionOut, status_code=status.HTTP_201_CREATED)
async def commit_prediction(
    body: PredictionCommit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a call. `committed_at` comes from the DB default, so it is the
    server's clock, not the client's."""
    drill = (
        await db.execute(select(Drill.id).where(Drill.drill_ref == body.drill_ref))
    ).scalar_one_or_none()
    if drill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No drill {body.drill_ref!r}.")

    if body.evidence_id is not None:
        owned = (
            await db.execute(
                select(EvidenceAsset.id).where(
                    EvidenceAsset.id == body.evidence_id,
                    EvidenceAsset.user_id == current_user.id,
                    EvidenceAsset.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if owned is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")

    row = Prediction(
        user_id=current_user.id,
        drill_ref=body.drill_ref,
        session_label=body.session_label,
        instrument=body.instrument,
        bias=body.bias,
        dol=body.dol,
        entry_model=body.entry_model,
        target=body.target,
        evidence_id=body.evidence_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _out(row)


# ---------------------------------------------------------------------------
# GET /api/predictions — this user's ledger
# ---------------------------------------------------------------------------

@router.get("/predictions", response_model=list[PredictionOut])
async def list_predictions(
    drill_ref: str | None = Query(None),
    resolved: bool | None = Query(None, description="Filter to resolved / unresolved"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Prediction)
        .where(Prediction.user_id == current_user.id)
        .order_by(Prediction.committed_at.desc())
    )
    if drill_ref is not None:
        stmt = stmt.where(Prediction.drill_ref == drill_ref)
    if resolved is True:
        stmt = stmt.where(Prediction.resolved_at.is_not(None))
    elif resolved is False:
        stmt = stmt.where(Prediction.resolved_at.is_(None))
    rows = (await db.execute(stmt)).scalars().all()
    return [_out(p) for p in rows]


# ---------------------------------------------------------------------------
# POST /api/predictions/{id}/resolve — the reveal, once
# ---------------------------------------------------------------------------

@router.post("/predictions/{prediction_id}/resolve", response_model=PredictionOut)
async def resolve_prediction(
    prediction_id: uuid.UUID,
    body: PredictionResolve,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record what actually happened. Accepted exactly once — a re-resolve would
    let one call be scored repeatedly until it landed, which is the same
    non-monotonicity §4 forbids, pointed the other way."""
    row = (
        await db.execute(
            select(Prediction).where(
                Prediction.id == prediction_id,
                Prediction.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prediction not found")

    if row.resolved_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This call was already resolved at "
                f"{row.resolved_at.isoformat()} — its outcome is a record, not a draft. "
                "Commit a new prediction for the next session."
            ),
        )

    row.resolved_at = datetime.now(timezone.utc)
    row.outcome_bias = body.outcome_bias
    row.dol_hit = body.dol_hit
    row.model_played_out = body.model_played_out
    row.target_hit = body.target_hit
    row.resolution_notes = body.resolution_notes
    await db.commit()
    await db.refresh(row)
    return _out(row)


# ---------------------------------------------------------------------------
# GET /api/calibration — computed, informational, gates nothing
# ---------------------------------------------------------------------------

@router.get("/calibration", response_model=CalibrationOut)
async def get_calibration(
    drill_ref: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Your pre-committed calls versus what happened.

    Every figure is a ratio and the whole thing is scale-invariant, so more reps
    cannot inflate it (services/calibration.py states and tests the property). It
    is informational feedback per §6: nothing in the app reads it, and in
    particular M6's exit bar grades COMMITMENT, not accuracy.
    """
    stmt = select(Prediction).where(Prediction.user_id == current_user.id)
    if drill_ref is not None:
        stmt = stmt.where(Prediction.drill_ref == drill_ref)
    rows = (await db.execute(stmt)).scalars().all()

    score = calibration.compute([_as_call(p) for p in rows])
    coverage = await load_tape_coverage(db, current_user.id)
    return CalibrationOut(
        committed=score.committed,
        resolved=score.resolved,
        unresolved=score.unresolved,
        resolution_rate=score.resolution_rate,
        accuracy=score.accuracy,
        components=[
            ComponentScoreOut(
                key=c.key, label=c.label, correct=c.correct,
                resolved=c.resolved, accuracy=c.accuracy,
            )
            for c in score.components
        ],
        tape_drills_total=len(stages.TAPE_STUDY_DRILLS),
        tape_drills_committed=len(coverage.committed),
        tape_drills_resolved=len(coverage.resolved),
    )
