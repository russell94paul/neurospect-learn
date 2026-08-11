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
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.concept import Concept
from app.models.concept_progress import ConceptProgress
from app.models.drill_progress import DrillProgress
from app.models.evidence import EvidenceAsset, EvidenceGrade
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
from app.schemas.honesty import HonestyOut, HonestySignal
from app.services import expectancy, gate, honesty
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
# GET /api/gate/honesty — the E6 honesty strip
#
# A SEPARATE RESOURCE, NOT A FIELD ON `GateOut`, and that is the design rather
# than a routing convenience. `GET /api/gate` builds its verdict from exactly
# three inputs (concepts · expectancy · attestations); keeping the signals out of
# that payload means `services/gate.py` has no honesty value in scope to read, so
# "these gate nothing" is enforced by what is reachable rather than by a rule
# someone has to remember. It is the §E2 argument (`reps` DERIVED, not guarded)
# and the §E5 argument (a trigger, not router discipline) applied once more.
#
# It also keeps `/api/gate` byte-identical to the STEP-0 baseline (sha256
# `27ff7157…`, unchanged across E2 · E3 · E4 · E5), which is the workstream's
# loudest no-regression signal and is worth more than a nested field.
#
# §5 asks for these to RENDER as a strip on `/gate` — the page does that; see
# app/src/pages/gate.tsx.
# ---------------------------------------------------------------------------

_SUBJECT_LABELS = {"journal_entry": "journal entry", "missed_trade": "missed trade"}


async def _load_captures(db: AsyncSession, user_id) -> list[honesty.Capture]:
    """This user's live evidence, plus every grading pass written over it.

    `created_at` (the server's upload clock) is loaded alongside the user-asserted
    `captured_at` on purpose: the pacing signal must measure the former, or a
    signal about pacing could be silenced by asserting a different capture time.
    """
    rows = (
        await db.execute(
            select(
                EvidenceAsset.id,
                EvidenceAsset.subject_type,
                EvidenceAsset.subject_drill_ref,
                EvidenceAsset.concept_id,
                EvidenceAsset.journal_entry_id,
                EvidenceAsset.missed_trade_id,
                EvidenceAsset.created_at,
                EvidenceAsset.captured_at,
                EvidenceAsset.reps_claimed,
                Concept.title,
            )
            .outerjoin(Concept, Concept.id == EvidenceAsset.concept_id)
            .where(
                EvidenceAsset.user_id == user_id,
                EvidenceAsset.is_deleted.is_(False),
            )
        )
    ).all()

    grade_rows = (
        await db.execute(
            select(EvidenceGrade.evidence_id, EvidenceGrade.grader, EvidenceGrade.state).where(
                EvidenceGrade.user_id == user_id,
                EvidenceGrade.is_deleted.is_(False),
            )
        )
    ).all()

    graders: dict = {}
    grade_count: dict = {}
    flagged_count: dict = {}
    for evidence_id, grader, state in grade_rows:
        g = grader.value if hasattr(grader, "value") else str(grader)
        s = state.value if hasattr(state, "value") else str(state)
        graders.setdefault(evidence_id, set()).add(g)
        grade_count[evidence_id] = grade_count.get(evidence_id, 0) + 1
        if s in honesty.FLAGGED_STATES:
            flagged_count[evidence_id] = flagged_count.get(evidence_id, 0) + 1

    out: list[honesty.Capture] = []
    for (
        ev_id, subject_type, drill_ref, concept_id, journal_id, missed_id,
        created_at, captured_at, reps_claimed, concept_title,
    ) in rows:
        st = subject_type.value if hasattr(subject_type, "value") else str(subject_type)
        key_part = drill_ref or concept_id or journal_id or missed_id
        label = (
            drill_ref
            or concept_title
            or _SUBJECT_LABELS.get(st, st)
        )
        out.append(
            honesty.Capture(
                subject=f"{st}:{key_part}",
                subject_label=str(label),
                created_at=created_at,
                captured_at=captured_at,
                reps_claimed=reps_claimed,
                graders=frozenset(graders.get(ev_id, ())),
                grade_count=grade_count.get(ev_id, 0),
                flagged_count=flagged_count.get(ev_id, 0),
            )
        )
    return out


async def _load_rep_split(db: AsyncSession, user_id) -> tuple[int, int]:
    """(reps_legacy, reps_evidenced) across every subject.

    `legacy_reps` is what was claimed BEFORE the evidence layer existed; `0009`
    froze it and E2 kept it visible precisely so this phase could report it. It is
    the one part of the rep count that has no evidence behind it and never will.
    """
    legacy_concept = (
        await db.execute(
            select(func.coalesce(func.sum(ConceptProgress.legacy_reps), 0)).where(
                ConceptProgress.user_id == user_id,
                ConceptProgress.is_deleted.is_(False),
            )
        )
    ).scalar_one()
    legacy_drill = (
        await db.execute(
            select(func.coalesce(func.sum(DrillProgress.legacy_reps), 0)).where(
                DrillProgress.user_id == user_id,
                DrillProgress.is_deleted.is_(False),
            )
        )
    ).scalar_one()
    evidenced = (
        await db.execute(
            select(func.coalesce(func.sum(EvidenceAsset.reps_claimed), 0)).where(
                EvidenceAsset.user_id == user_id,
                EvidenceAsset.is_deleted.is_(False),
            )
        )
    ).scalar_one()
    return int(legacy_concept) + int(legacy_drill), int(evidenced)


@router.get("/gate/honesty", response_model=HonestyOut)
async def get_honesty(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The five §5 signals, computed on every read and stored nowhere.

    READ-ONLY BY CONSTRUCTION: there is no companion write endpoint, nothing to
    dismiss and nothing to acknowledge, because a signal a user can switch off is
    not a record of anything. None of these figures reaches `compute_readiness` —
    the gate's verdict is unchanged and unchangeable by anything here.
    """
    captures = await _load_captures(db, current_user.id)
    reps_legacy, reps_evidenced = await _load_rep_split(db, current_user.id)
    result = honesty.compute(
        captures, reps_legacy=reps_legacy, reps_evidenced=reps_evidenced
    )
    return HonestyOut(
        signals=[
            HonestySignal(
                key=s.key,
                label=s.label,
                status=s.status,
                count=s.count,
                population=s.population,
                measured_what=s.measured_what,
                detail=s.detail,
                subjects=list(s.subjects),
            )
            for s in result.signals
        ],
        captures=result.captures,
        reps_legacy=result.reps_legacy,
        reps_evidenced=result.reps_evidenced,
    )


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
