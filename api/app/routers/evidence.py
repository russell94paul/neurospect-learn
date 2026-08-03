"""Evidence API (Phase E2) — capture, list, read and remove evidence of the work.

This is the app's FIRST user-supplied-file surface, and the write side of the
layer that makes a rep mean something. Auth-gated, user-scoped, soft-deleted,
mirroring routers/missed_trades.py.

Three properties are load-bearing:

1. **A rep can only be created here.** `PATCH /api/drills`, `PATCH /api/progress`
   and `PATCH /api/plan/items/{id}` cannot mint one — `reps` is DERIVED
   (`legacy_reps + Σ reps_claimed`), so there is no rep-writing endpoint to
   bypass. Same structural property the Gate has with `cleared`.
2. **A refusal always says why.** The deterministic tier blocks only what is
   certain (not an image · already uploaded) and every rejection names the
   reason — a silent refusal is the failure mode this workstream exists to avoid.
3. **The client is never trusted about file type.** The stored `content_type`
   comes from a magic-byte sniff, and no path is ever built from a filename.

The journal's deferred screenshots (5c) and the `missed_trade_screenshots`
omitted from `0008` attach here too, via `subject_type` — one polymorphic layer,
which is the whole reason the design rejected per-owner child tables.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response, status
from fastapi import UploadFile
from fastapi.responses import Response as RawResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_current_user, get_db
from app.models.concept import Concept
from app.models.drill import Drill
from app.models.enums import EvidenceGradeState, EvidenceGrader, EvidenceKind, EvidenceSubject
from app.models.evidence import EvidenceAsset, EvidenceGrade
from app.models.journal_entry import JournalEntry
from app.models.missed_trade import MissedTrade
from app.models.rubric import Rubric
from app.models.user import User
from app.schemas.evidence import EvidenceGradeOut, EvidenceOut
from app.schemas.rubric import SelfCheckIn
from app.services import evidence_checks, storage as storage_service

router = APIRouter(prefix="/api", tags=["evidence"])

# Read the body in bounded chunks so an oversized upload is refused without
# ever materialising the whole thing in memory.
_CHUNK = 256 * 1024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _out(asset: EvidenceAsset, grades: list[EvidenceGrade]) -> EvidenceOut:
    return EvidenceOut(
        id=asset.id,
        subject_type=asset.subject_type,
        subject_drill_ref=asset.subject_drill_ref,
        concept_id=asset.concept_id,
        journal_entry_id=asset.journal_entry_id,
        missed_trade_id=asset.missed_trade_id,
        kind=asset.kind,
        content_type=asset.content_type,
        original_filename=asset.original_filename,
        byte_size=asset.byte_size,
        sha256=asset.sha256,
        perceptual_hash=asset.perceptual_hash,
        captured_at=asset.captured_at,
        reps_claimed=asset.reps_claimed,
        notes=asset.notes,
        created_at=asset.created_at,
        url=storage_service.storage.presign(asset.storage_key),
        grades=[EvidenceGradeOut.model_validate(g) for g in grades],
    )


async def _load_grades(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[EvidenceGrade]]:
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(EvidenceGrade)
            .where(EvidenceGrade.evidence_id.in_(ids), EvidenceGrade.is_deleted.is_(False))
            .order_by(EvidenceGrade.graded_at.desc())
        )
    ).scalars().all()
    out: dict[uuid.UUID, list[EvidenceGrade]] = {}
    for g in rows:
        out.setdefault(g.evidence_id, []).append(g)
    return out


async def _resolve_subject(
    db: AsyncSession,
    user_id: uuid.UUID,
    subject_type: EvidenceSubject,
    drill_ref: str | None,
    concept_id: uuid.UUID | None,
    journal_entry_id: uuid.UUID | None,
    missed_trade_id: uuid.UUID | None,
) -> tuple[dict, str]:
    """Validate the subject and return (column values, the key path segment).

    Fails closed in the same way the DB CHECK does — the API rejects a mismatched
    or ambiguous subject before the row is ever built, and the CHECK is the
    backstop, not the only guard.
    """
    provided = [x is not None for x in (drill_ref, concept_id, journal_entry_id, missed_trade_id)]
    if sum(provided) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide exactly one subject: drill_ref, concept_id, journal_entry_id or missed_trade_id.",
        )

    if subject_type is EvidenceSubject.DRILL:
        if drill_ref is None:
            raise HTTPException(422, "subject_type=drill requires drill_ref.")
        exists = (
            await db.execute(select(Drill.id).where(Drill.drill_ref == drill_ref))
        ).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Drill not found")
        return {"subject_drill_ref": drill_ref}, drill_ref

    if subject_type is EvidenceSubject.CONCEPT:
        if concept_id is None:
            raise HTTPException(422, "subject_type=concept requires concept_id.")
        exists = (
            await db.execute(select(Concept.id).where(Concept.id == concept_id))
        ).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
        return {"concept_id": concept_id}, str(concept_id)

    if subject_type is EvidenceSubject.JOURNAL_ENTRY:
        if journal_entry_id is None:
            raise HTTPException(422, "subject_type=journal_entry requires journal_entry_id.")
        owned = (
            await db.execute(
                select(JournalEntry.id).where(
                    JournalEntry.id == journal_entry_id,
                    JournalEntry.user_id == user_id,
                    JournalEntry.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if owned is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Journal entry not found")
        return {"journal_entry_id": journal_entry_id}, str(journal_entry_id)

    if missed_trade_id is None:
        raise HTTPException(422, "subject_type=missed_trade requires missed_trade_id.")
    owned = (
        await db.execute(
            select(MissedTrade.id).where(
                MissedTrade.id == missed_trade_id,
                MissedTrade.user_id == user_id,
                MissedTrade.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if owned is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Missed trade not found")
    return {"missed_trade_id": missed_trade_id}, str(missed_trade_id)


async def _read_bounded(file: UploadFile) -> bytes:
    """Read the upload, aborting as soon as it exceeds the cap."""
    limit = settings.evidence_max_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"That file is over the {limit / 1_048_576:.0f} MB limit. "
                    "Crop or re-export the capture."
                ),
            )
        chunks.append(chunk)
    return b"".join(chunks)


_REJECTION_STATUS = {
    "not_an_image": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    "too_large": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    "too_small": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "duplicate": status.HTTP_409_CONFLICT,
    "near_duplicate": status.HTTP_409_CONFLICT,
}


# ---------------------------------------------------------------------------
# GET /api/evidence/file?token=  — the LOCAL backend's presigned read
# ---------------------------------------------------------------------------
# Declared BEFORE /evidence/{evidence_id} so the literal segment wins, and
# deliberately NOT behind get_current_user: the token is the authorisation, and
# it is scoped to one storage key with a one-hour expiry — exactly what an R2
# presigned URL is. This lets an <img src> render evidence without the session
# token, identically against either backend.

@router.get("/evidence/file")
async def get_evidence_file(token: str = Query(...)) -> RawResponse:
    backend = storage_service.storage
    if not isinstance(backend, storage_service.LocalBackend):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Object storage is configured — read evidence from its presigned URL.",
        )
    try:
        key = storage_service.verify_key_token(token)
        data = backend.read_bytes(key)
    except storage_service.StorageError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    content_type = evidence_checks.sniff_content_type(data) or "application/octet-stream"
    return RawResponse(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


# ---------------------------------------------------------------------------
# POST /api/evidence — capture (multipart)
# ---------------------------------------------------------------------------

@router.post("/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def create_evidence(
    file: UploadFile,
    subject_type: EvidenceSubject = Form(...),
    kind: EvidenceKind = Form(EvidenceKind.CHART_MARKUP),
    drill_ref: str | None = Form(None),
    concept_id: uuid.UUID | None = Form(None),
    journal_entry_id: uuid.UUID | None = Form(None),
    missed_trade_id: uuid.UUID | None = Form(None),
    reps_claimed: int = Form(1, ge=0, le=100),
    captured_at: datetime | None = Form(None),
    notes: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subject_values, subject_segment = await _resolve_subject(
        db, current_user.id, subject_type, drill_ref, concept_id,
        journal_entry_id, missed_trade_id,
    )

    data = await _read_bounded(file)

    # The deterministic tier — the ONLY tier that blocks (design §2).
    existing = (
        await db.execute(
            select(EvidenceAsset.id, EvidenceAsset.sha256, EvidenceAsset.perceptual_hash).where(
                EvidenceAsset.user_id == current_user.id,
                EvidenceAsset.is_deleted.is_(False),
            )
        )
    ).all()
    verdict = evidence_checks.check(
        data,
        max_bytes=settings.evidence_max_bytes,
        min_bytes=settings.evidence_min_bytes,
        existing_hashes={str(i): h for i, h, _p in existing},
        existing_phashes={str(i): p for i, _h, p in existing if p},
    )
    if isinstance(verdict, evidence_checks.Rejection):
        raise HTTPException(
            status_code=_REJECTION_STATUS.get(verdict.code, status.HTTP_422_UNPROCESSABLE_ENTITY),
            detail={
                "code": verdict.code,
                "message": verdict.message,
                "duplicate_of": verdict.duplicate_of,
                "distance": verdict.distance,
            },
        )

    # Filename is a HINT only — the extension comes from the sniffed type and no
    # path is ever built from user input.
    ext = storage_service.safe_extension(file.filename, verdict.content_type)
    key = storage_service.storage_key(
        current_user.id, subject_type.value, subject_segment, ext
    )
    storage_service.storage.upload_bytes(key, data, verdict.content_type)

    asset = EvidenceAsset(
        user_id=current_user.id,
        subject_type=subject_type,
        kind=kind,
        storage_key=key,
        content_type=verdict.content_type,
        original_filename=(file.filename or None),
        byte_size=verdict.byte_size,
        sha256=verdict.sha256,
        perceptual_hash=verdict.perceptual_hash,
        captured_at=captured_at,
        reps_claimed=reps_claimed,
        notes=notes,
        **subject_values,
    )
    db.add(asset)
    await db.flush()

    # The deterministic PASS is recorded as a grade row, so every asset carries
    # its grading history from the moment it lands (E3/E4 append to it).
    grade = EvidenceGrade(
        evidence_id=asset.id,
        user_id=current_user.id,
        grader=EvidenceGrader.DETERMINISTIC,
        state=EvidenceGradeState.FLAGGED if verdict.flags else EvidenceGradeState.PASSED,
        findings=verdict.flags or None,
    )
    db.add(grade)
    await db.commit()
    await db.refresh(asset)
    await db.refresh(grade)
    return _out(asset, [grade])


# ---------------------------------------------------------------------------
# GET /api/evidence — this user's evidence, filtered by subject
# ---------------------------------------------------------------------------

@router.get("/evidence", response_model=list[EvidenceOut])
async def list_evidence(
    subject_type: EvidenceSubject | None = Query(None),
    drill_ref: str | None = Query(None),
    concept_id: uuid.UUID | None = Query(None),
    journal_entry_id: uuid.UUID | None = Query(None),
    missed_trade_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(EvidenceAsset)
        .where(
            EvidenceAsset.user_id == current_user.id,
            EvidenceAsset.is_deleted.is_(False),
        )
        .order_by(EvidenceAsset.created_at.desc())
    )
    if subject_type is not None:
        stmt = stmt.where(EvidenceAsset.subject_type == subject_type)
    if drill_ref is not None:
        stmt = stmt.where(EvidenceAsset.subject_drill_ref == drill_ref)
    if concept_id is not None:
        stmt = stmt.where(EvidenceAsset.concept_id == concept_id)
    if journal_entry_id is not None:
        stmt = stmt.where(EvidenceAsset.journal_entry_id == journal_entry_id)
    if missed_trade_id is not None:
        stmt = stmt.where(EvidenceAsset.missed_trade_id == missed_trade_id)

    rows = list((await db.execute(stmt)).scalars().all())
    grades = await _load_grades(db, [r.id for r in rows])
    return [_out(r, grades.get(r.id, [])) for r in rows]


# ---------------------------------------------------------------------------
# GET | DELETE /api/evidence/{id}
# ---------------------------------------------------------------------------

async def _get_owned(db: AsyncSession, user_id: uuid.UUID, evidence_id: uuid.UUID) -> EvidenceAsset:
    row = (
        await db.execute(
            select(EvidenceAsset).where(
                EvidenceAsset.id == evidence_id,
                EvidenceAsset.user_id == user_id,
                EvidenceAsset.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return row


@router.get("/evidence/{evidence_id}", response_model=EvidenceOut)
async def get_evidence(
    evidence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await _get_owned(db, current_user.id, evidence_id)
    grades = await _load_grades(db, [asset.id])
    return _out(asset, grades.get(asset.id, []))


# ---------------------------------------------------------------------------
# POST /api/evidence/{id}/self-check — TIER 2, the rep's own bar (Phase E3)
# ---------------------------------------------------------------------------
# Declared BEFORE the DELETE handler is irrelevant (different method), but it is
# grouped here because it is a GRADE WRITE: it appends one more `evidence_grades`
# row beside the `deterministic` row E2 wrote on arrival. Additive, never
# destructive — a re-check appends rather than mutating a verdict, so the grading
# history stays a record.
#
# THE DECISION THIS PHASE HAD TO MAKE: does an UNCHECKED rep still count?
#
# **Yes. A self-check cannot un-count a rep.** `reps` is DERIVED from
# `evidence_assets.reps_claimed` (E2), and `services/stages.py` +
# `services/gate.py` read `reps`. If a missing or partial self-check deducted a
# rep, progress would become NON-MONOTONIC: a met stage exit bar could un-meet and
# a Gate verdict could flip backwards with no user action. That is precisely why
# design §4 makes a grade FLAG rather than RETRACT, and what invariant 5 forbids —
# "`reps` gets strictly harder to satisfy, never easier" means harder to CREATE,
# not revocable after the fact.
#
# So an ungraded rep is SURFACED as an honest backlog, never deducted, and a
# partial check records `flagged` plus the specific unticked items — informational
# feedback, which per design §6 IS the reward. The aggregate honesty strip over
# that backlog belongs to E6; E3 makes the per-asset state visible at the point of
# capture and changes no rep count, no stage bar and no Gate verdict.

async def _resolve_rubric(db: AsyncSession, asset: EvidenceAsset, slug: str | None) -> Rubric:
    """The bar this asset is judged against: an explicit slug, else the drill's."""
    if slug is not None:
        rubric = (
            await db.execute(select(Rubric).where(Rubric.slug == slug))
        ).scalar_one_or_none()
        if rubric is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No rubric {slug!r}.")
        return rubric

    if asset.subject_drill_ref is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "This evidence is not attached to a drill, so its bar is ambiguous — "
                "send `rubric_slug` to say which rubric to check against."
            ),
        )
    rubric = (
        await db.execute(select(Rubric).where(Rubric.drill_ref == asset.subject_drill_ref))
    ).scalar_one_or_none()
    if rubric is None:
        # Honest 404: a few drills are written in the wiki as a paragraph plus a
        # table (aura D4-a/b) and have no ✋/🛠 bullet to project, so they
        # genuinely have no bar yet. Saying so beats inventing one.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No rubric is projected for {asset.subject_drill_ref!r} — its wiki "
                "entry has no ✋/🛠 bullets to check against."
            ),
        )
    return rubric


@router.post(
    "/evidence/{evidence_id}/self-check",
    response_model=EvidenceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_self_check(
    evidence_id: uuid.UUID,
    body: SelfCheckIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record the user's answer to the drill's bar as an ADDITIONAL grade row."""
    asset = await _get_owned(db, current_user.id, evidence_id)
    rubric = await _resolve_rubric(db, asset, body.rubric_slug)

    items = list(rubric.items)
    if not items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Rubric {rubric.slug!r} has no items to check.",
        )

    checked = set(body.checked_item_keys)
    if unknown := sorted(checked - {it.item_key for it in items}):
        # Name the offending keys — a refusal always says why.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"These items are not in rubric {rubric.slug!r} (v{rubric.version}): {unknown}",
        )

    # `findings` records the WHOLE bar with each item's ticked state AND its text,
    # so the grade stays legible after a re-seed replaces `rubric_items` — which is
    # also why `rubric_version` is stored beside it.
    findings = [
        {
            "item_key": it.item_key,
            "ordinal": it.ordinal,
            "variant": it.variant.value,
            "text": it.text,
            "checked": it.item_key in checked,
        }
        for it in items
    ]
    met = len(checked)

    grade = EvidenceGrade(
        evidence_id=asset.id,
        user_id=current_user.id,
        grader=EvidenceGrader.SELF_CHECK,
        # PASSED when the whole bar is met, else FLAGGED — never FAILED, because a
        # self-check describes the rep; it does not retract it.
        state=EvidenceGradeState.PASSED if met == len(items) else EvidenceGradeState.FLAGGED,
        # ADVISORY only (invariant 7). Nothing reads this into `confidence` or
        # `ladder_stage`, which stay written exclusively by PATCH /api/progress.
        score=Decimal(str(round(100 * met / len(items), 2))),
        rubric_slug=rubric.slug,
        rubric_version=rubric.version,
        findings=findings,
    )
    db.add(grade)
    await db.commit()

    grades = await _load_grades(db, [asset.id])
    return _out(asset, grades.get(asset.id, []))


@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_evidence(
    evidence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft delete. The stored object is KEPT — retention is indefinite by design
    (the evidence IS the accountability record). The row leaves the ledger, so
    the derived rep it carried goes with it; re-uploading the same file restores
    exactly that one rep and no more, so this is not a way to inflate a count."""
    asset = await _get_owned(db, current_user.id, evidence_id)
    asset.is_deleted = True
    asset.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
