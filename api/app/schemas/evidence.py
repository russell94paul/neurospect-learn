"""Pydantic schemas for the evidence API (Phase E2).

Mirrored on the frontend in app/src/types/api.ts. The upload itself is multipart
(`UploadFile` + form fields), so there is no request body model — only the
response shapes and the subject selector.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EvidenceGradeState, EvidenceGrader, EvidenceKind, EvidenceSubject


class EvidenceGradeOut(BaseModel):
    """One grading pass. E2 only ever emits the `deterministic` grader; the
    `score` is advisory in every tier and never writes confidence or ladder."""

    id: uuid.UUID
    grader: EvidenceGrader
    state: EvidenceGradeState
    score: float | None = None
    rubric_slug: str | None = None
    rubric_version: int | None = None
    findings: list | dict | None = None
    model: str | None = None
    graded_at: datetime

    model_config = {"from_attributes": True}


class EvidenceOut(BaseModel):
    """One evidence asset + its grading history + a short-lived read URL."""

    id: uuid.UUID
    subject_type: EvidenceSubject
    subject_drill_ref: str | None = None
    concept_id: uuid.UUID | None = None
    journal_entry_id: uuid.UUID | None = None
    missed_trade_id: uuid.UUID | None = None

    kind: EvidenceKind
    content_type: str
    original_filename: str | None = None
    byte_size: int
    sha256: str
    perceptual_hash: str | None = None

    captured_at: datetime | None = None
    reps_claimed: int
    notes: str | None = None
    created_at: datetime

    #: Presigned (R2) or signed local URL — renderable directly in an <img>.
    url: str
    grades: list[EvidenceGradeOut] = []


class EvidenceRepsOut(BaseModel):
    """The declared-vs-derived split for one subject, so the pre-evidence gap is
    VISIBLE rather than quietly folded into a single number."""

    reps: int            # what the app counts = legacy + evidenced
    reps_evidenced: int  # Σ reps_claimed over this subject's live evidence
    reps_legacy: int     # claimed before the evidence layer existed (frozen)
