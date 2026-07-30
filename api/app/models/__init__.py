"""SQLAlchemy models. Importing this package registers every table on
``Base.metadata`` (used by Alembic's ``target_metadata`` and app boot)."""

from app.models.base import Base
from app.models.concept import Concept
from app.models.concept_progress import ConceptProgress
from app.models.content_page import ContentPage
from app.models.drill import Drill
from app.models.drill_progress import DrillProgress
from app.models.evidence import EvidenceAsset, EvidenceGrade
from app.models.gate_attestation import GateAttestation
from app.models.journal_entry import JournalEntry
from app.models.missed_trade import MissedTrade
from app.models.plan_item import PlanItem
from app.models.study_preferences import StudyPreferences
from app.models.track_stage import TrackStage
from app.models.user import User

__all__ = [
    "Base",
    "Concept",
    "ConceptProgress",
    "ContentPage",
    "Drill",
    "DrillProgress",
    "EvidenceAsset",
    "EvidenceGrade",
    "GateAttestation",
    "JournalEntry",
    "MissedTrade",
    "PlanItem",
    "StudyPreferences",
    "TrackStage",
    "User",
]
