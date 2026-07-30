"""Readiness-to-Live Gate API (Phase 5g) — the north-star payoff.

Auth-gated + user-scoped. COMBINES the three sources that already exist rather
than adding new evidence of its own:

  (a) `concepts` × `concept_progress`  (5e-1) — the ladder position
  (b) `journal_entries` → the PURE, ALREADY-SHIPPED app/services/expectancy.py
      (5f) — the backtest sample + expectancy in R. Reused verbatim: this router
      calls `expectancy.compute_groups`, exactly as the analytics router does.
  (c) `gate_attestations` (0007) — the four behavioural checklist items

and delegates the verdict to the pure app/services/gate.py.

NON-OVERRIDABLE: no endpoint here writes a verdict. `GET /api/gate` recomputes it
every time; the only write is PATCH-ing one (c) attestation, which cannot satisfy
(a) or (b). Frontier (watch-only) concepts are never requirements and never
supply credit. Confluence tags are study-only and unread here.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.gate_attestation import GateAttestation
from app.models.journal_entry import JournalEntry
from app.models.user import User
from app.schemas.gate import (
    Attestation,
    AttestationPatch,
    Corroboration,
    FrontierConcept,
    GateOut,
    GateRequirement,
    ModelReadiness,
)
from app.services import expectancy, gate
from app.routers.learning import TRACK_LABELS, load_concepts_and_ladder

router = APIRouter(
    prefix="/api",
    tags=["gate"],
    dependencies=[Depends(get_current_user)],
)

# Mirrors the partial unique index predicate (`WHERE NOT is_deleted`) textually —
# ON CONFLICT inference requires that, see learning.py / §5e-1 as-built.
_NOT_DELETED = text("NOT is_deleted")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

async def _load_trades_and_corroboration(
    db: AsyncSession, user_id
) -> tuple[list[expectancy.TradeR], Corroboration]:
    """This user's non-deleted journal rows → expectancy inputs + the objective
    journal facts shown beside the (c) attestations (not gating)."""
    rows = (
        await db.execute(
            select(
                JournalEntry.entry_model,
                JournalEntry.mode,
                JournalEntry.r_multiple,
                JournalEntry.rr_planned,
                JournalEntry.entry_date,
            ).where(
                JournalEntry.user_id == user_id,
                JournalEntry.is_deleted.is_(False),
            )
        )
    ).all()

    trades = [
        expectancy.TradeR(
            entry_model=em.value if hasattr(em, "value") else str(em),
            mode=md.value if hasattr(md, "value") else str(md),
            r_multiple=float(r) if r is not None else None,
            rr_planned=float(rr) if rr is not None else None,
        )
        for em, md, r, rr, _d in rows
    ]

    dates = sorted({d for *_rest, d in rows if d is not None})
    modes = [t.mode for t in trades]
    corr = Corroboration(
        entries_logged=len(trades),
        entries_closed=sum(1 for t in trades if t.r_multiple is not None),
        journaling_days=len(dates),
        live_entries=sum(1 for m in modes if m == "live"),
        backtest_entries=sum(1 for m in modes if m == "backtest"),
        last_entry_date=dates[-1].isoformat() if dates else None,
    )
    return trades, corr


async def _load_attestations(
    db: AsyncSession, user_id
) -> tuple[dict[str, bool], dict[str, str | None]]:
    rows = (
        await db.execute(
            select(GateAttestation).where(
                GateAttestation.user_id == user_id,
                GateAttestation.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    attested = {r.item.value if hasattr(r.item, "value") else str(r.item): r.attested for r in rows}
    notes = {r.item.value if hasattr(r.item, "value") else str(r.item): r.note for r in rows}
    return attested, notes


def _out(result: gate.GateResult) -> GateOut:
    return GateOut(
        anchor_track=result.anchor_track,
        credit_track=result.credit_track,
        sample_target=result.sample_target,
        sample_stretch=result.sample_stretch,
        any_cleared=result.any_cleared,
        models=[
            ModelReadiness(
                **{k: v for k, v in m.__dict__.items() if k != "requirements"},
                requirements=[GateRequirement(**r.__dict__) for r in m.requirements],
            )
            for m in result.models
        ],
        attestations=[Attestation(**a.__dict__) for a in result.attestations],
        corroboration=result.corroboration
        if isinstance(result.corroboration, Corroboration)
        else Corroboration(**result.corroboration.__dict__),
        frontier=[FrontierConcept(**f.__dict__) for f in result.frontier],
    )


# ---------------------------------------------------------------------------
# GET /api/gate — the computed per-model "cleared to live?" verdict
# ---------------------------------------------------------------------------

@router.get("/gate", response_model=GateOut)
async def get_gate(
    track: str | None = Query(
        None,
        description=(
            "Restrict which track's progress may satisfy a requirement "
            "(aura | ict_course | unified). Omit to credit any track. "
            "This can only TIGHTEN the verdict, never loosen it."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if track is not None and track not in TRACK_LABELS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown track")

    concepts, ladder = await load_concepts_and_ladder(db, current_user.id)
    trades, corr = await _load_trades_and_corroboration(db, current_user.id)
    attested, notes = await _load_attestations(db, current_user.id)

    # (b) — the SHIPPED 5f math, reused (not reimplemented).
    groups = expectancy.compute_groups(trades)

    result = gate.compute_readiness(
        concepts=concepts,
        ladder=ladder,
        groups=groups,
        attested=attested,
        notes=notes,
        corroboration=gate.Corroboration(**corr.model_dump()),
        credit_track=track,
    )
    return _out(result)


# ---------------------------------------------------------------------------
# GET /api/gate/attestations — the (c) checklist (lazy: unattested reads false)
# ---------------------------------------------------------------------------

@router.get("/gate/attestations", response_model=list[Attestation])
async def get_attestations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attested, notes = await _load_attestations(db, current_user.id)
    return [
        Attestation(
            item=item, label=label, attested=bool(attested.get(item)), note=notes.get(item)
        )
        for item, label in gate.BEHAVIOURAL_ITEMS
    ]


# ---------------------------------------------------------------------------
# PATCH /api/gate/attestations — attest or revoke ONE behavioural item
# ---------------------------------------------------------------------------

@router.patch("/gate/attestations", response_model=Attestation)
async def patch_attestation(
    body: AttestationPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lazy upsert of one (c) item (the concept_progress idiom). Revocable —
    `attested: false` clears it. This is the ONLY write on the gate surface, and
    it cannot satisfy (a) or (b): a model with all four attested and no backtest
    sample stays blocked."""
    item = body.item.value
    values = {
        "user_id": current_user.id,
        "item": item,
        "attested": body.attested,
        "attested_at": datetime.now(timezone.utc) if body.attested else None,
        "note": body.note,
    }
    stmt = pg_insert(GateAttestation).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[GateAttestation.user_id, GateAttestation.item],
        index_where=_NOT_DELETED,
        set_={
            "attested": stmt.excluded.attested,
            "attested_at": stmt.excluded.attested_at,
            "note": stmt.excluded.note,
        },
    )
    await db.execute(stmt)
    await db.commit()

    # Respond from the committed values (§5e-1 as-built: an ORM re-read returns
    # the stale identity-map row under expire_on_commit=False).
    label = dict(gate.BEHAVIOURAL_ITEMS)[item]
    return Attestation(item=item, label=label, attested=body.attested, note=body.note)
