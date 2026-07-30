import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import GateAttestationItem, pg_enum


class GateAttestation(Base):
    """One behavioural-checklist attestation for the Readiness-to-Live Gate (5g).

    Source (c) of the gate — the four items of concepts/mastery/README §Gate that
    no data can prove. Per-user (behaviour belongs to the trader, not to a
    model), one active row per (user, item), user-scoped + soft-deleted like
    `concept_progress` / `drill_progress`. `attested` is revocable; `note` is
    where the user points at the written evidence.

    There is NO `cleared` column here or anywhere else: the gate verdict is
    computed by app/services/gate.py on every read and is not writable.
    """

    __tablename__ = "gate_attestations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    item: Mapped[GateAttestationItem] = mapped_column(
        pg_enum(GateAttestationItem, "gate_attestation_item"), nullable=False
    )

    attested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    attested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
