"""Postgres ENUM definitions for the learning platform (Phase 5c).

These Python enums are the source of truth for the *labels*; the actual
Postgres `CREATE TYPE ... AS ENUM` statements live in the Alembic migrations
(0002_learning_progress, 0003_journal_entries) and are the DDL of record. The
ORM columns reference these types with ``create_type=False`` so SQLAlchemy never
tries to (re)create them — mirroring the raw-SQL migration idiom from 0001.

Values are the *exact* Postgres labels; use ``pg_enum(X)`` in a model to build a
``sa.Enum`` bound to the pre-existing DB type by name.
"""

from enum import Enum

import sqlalchemy as sa


class UStage(str, Enum):
    """Curriculum stage from the unified learning path (U0–U6)."""

    U0 = "U0"
    U1 = "U1"
    U2 = "U2"
    U3 = "U3"
    U4 = "U4"
    U5 = "U5"
    U6 = "U6"


class JournalMode(str, Enum):
    """The discriminator that makes one journal power both axes."""

    BACKTEST = "backtest"
    LIVE = "live"


class EntryModel(str, Enum):
    """The 7 taught entry models + the unified model-agnostic decision flow.

    Enumerated from concepts/entry-models/* (the expectancy-grouping key).
    """

    CONSOLIDATION = "consolidation"
    EXPANSION_RETRACEMENT = "expansion_retracement"
    REVERSAL_RAID_ON_STOPS = "reversal_raid_on_stops"
    LONDON = "london"
    MODEL_2022_OTE = "model_2022_ote"
    DAILY_BIAS = "daily_bias"
    SMT_CONFIRMATION = "smt_confirmation"
    UNIFIED = "unified"


class RangePosition(str, Enum):
    """Where price sits in the dealing range (Aura ranges / R3)."""

    DISCOUNT = "discount"
    EQ = "eq"
    PREMIUM = "premium"


class SessionType(str, Enum):
    """Macro session the entry belongs to."""

    ASIA = "asia"
    LONDON = "london"
    NY_AM = "ny_am"
    NY_PM = "ny_pm"


class EntryPDA(str, Enum):
    """The PD array used for entry. Default fvg per R4 (default FVG/iFVG,
    reach for the richer PDA set only when the structure calls for it)."""

    FVG = "fvg"
    IFVG = "ifvg"
    ORDER_BLOCK = "order_block"
    BREAKER = "breaker"
    REJECTION_BLOCK = "rejection_block"
    OTE_BLOCK = "ote_block"


class Outcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class Grade(str, Enum):
    """Execution-quality grade, independent of outcome."""

    A_PLUS = "a_plus"
    A = "a"
    B = "b"
    C = "c"


class PlanActivity(str, Enum):
    """The kind of work a Study-Planner `plan_item` prescribes (Phase 5e-2).

    learn    read a concept's content (first exposure)
    drill    practise a drill toward its rep target
    review   spaced-repetition review of a ≥Can-mark concept (retention)
    observe  frontier (U5) study-and-watch only — never live-gate-eligible
    habit    a foundation-stage (U0-equivalent) daily discipline task
    backtest a concept-less evidence stage (backtest / journal) placeholder
    """

    LEARN = "learn"
    DRILL = "drill"
    REVIEW = "review"
    OBSERVE = "observe"
    HABIT = "habit"
    BACKTEST = "backtest"


class PlanItemStatus(str, Enum):
    """The lifecycle status of a `plan_item` (Phase 5e-2). Skipping is logged as
    a `skipped` (hurts adherence), never hidden — accountability by design."""

    PENDING = "pending"
    DONE = "done"
    PARTIAL = "partial"
    SKIPPED = "skipped"


def pg_enum(enum_cls: type[Enum], name: str) -> sa.Enum:
    """Build a ``sa.Enum`` bound by name to a Postgres type the migration owns.

    ``create_type=False`` — the migration ran ``CREATE TYPE``; the ORM must not.
    ``values_callable`` emits the ``.value`` labels (not the member names).
    """
    return sa.Enum(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )
