"""SQLAlchemy models. Importing this package registers every table on
``Base.metadata`` (used by Alembic's ``target_metadata`` and app boot)."""

from app.models.base import Base
from app.models.concept import Concept
from app.models.concept_progress import ConceptProgress
from app.models.content_page import ContentPage
from app.models.journal_entry import JournalEntry
from app.models.user import User

__all__ = [
    "Base",
    "Concept",
    "ConceptProgress",
    "ContentPage",
    "JournalEntry",
    "User",
]
