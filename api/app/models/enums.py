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


class MissType(str, Enum):
    """How a logged setup came to be missed (Phase 6b).

    Provenance: concepts/aura/journaling-system (aura-05) treats missed/canceled
    trades as a distinct, high-value journaling category. `canceled` is Dante's
    category — you had a working order and pulled it.
    """

    ALMOST_TOOK = "almost_took"  # considered it, never entered
    HESITATED = "hesitated"  # planned it, froze at the trigger
    CANCELED = "canceled"  # had a working order and pulled it


class HypotheticalOutcome(str, Enum):
    """What the missed setup WOULD have done, resolved after watching price.

    `unknown` is a first-class value: an unresolved miss is logged honestly rather
    than left out of the record.
    """

    WOULD_WIN = "would_win"
    WOULD_LOSE = "would_lose"
    WOULD_BREAKEVEN = "would_breakeven"
    UNKNOWN = "unknown"


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


class GateAttestationItem(str, Enum):
    """The behavioural checklist items of the Readiness-to-Live Gate (Phase 5g).

    These are the four items of concepts/mastery/README §Gate that no data can
    prove — they are USER-ATTESTED. Attesting them is an INPUT to the gate, never
    an override: it cannot satisfy the concept-ladder or expectancy requirements.
    Labels are also the keys of app/services/gate.BEHAVIOURAL_ITEMS.
    """

    RISK_PRECOMMITTED = "risk_precommitted"
    SIM_TRACK_RECORD = "sim_track_record"
    JOURNALING_HABIT = "journaling_habit"
    CIRCUIT_BREAKER = "circuit_breaker"


class EvidenceSubject(str, Enum):
    """What a piece of evidence is attached to (Phase E2).

    ONE polymorphic evidence layer serves all four: drill evidence, concept
    evidence, the journal's deferred screenshots (5c) and the missed-trade
    screenshots deliberately omitted from 0008. Exactly one subject column is
    populated per row, agreeing with this discriminator — enforced by a DB CHECK
    that fails closed.
    """

    DRILL = "drill"
    CONCEPT = "concept"
    JOURNAL_ENTRY = "journal_entry"
    MISSED_TRADE = "missed_trade"


class EvidenceKind(str, Enum):
    """The five kinds of evidence the curriculum actually produces
    (concepts/architecture/learning-enforcement.md §1 — the table there maps each
    kind to the drills it serves; not restated here).

    Deliberately NOT "one screenshot per rep": `services/rep_targets.py` already
    distinguishes reps/days/sessions/qualitative/habit, and a "1 week" habit
    target has no rep to photograph.
    """

    CHART_MARKUP = "chart_markup"       # a marked-up chart capture
    WRITTEN_ARTIFACT = "written_artifact"  # routine, identity statements, contracts
    COMPUTATION = "computation"         # a computed number or table
    PREDICTION = "prediction"           # a call committed BEFORE the reveal (E5)
    TAPE_READ = "tape_read"             # a narrated live/delayed session read


class EvidenceGrader(str, Enum):
    """Which of the three tiers produced a grade. Only `deterministic` BLOCKS;
    it is also the only tier E2 builds (`self_check` = E3, `ai_vision` = E4)."""

    DETERMINISTIC = "deterministic"
    SELF_CHECK = "self_check"
    AI_VISION = "ai_vision"


class EvidenceGradeState(str, Enum):
    """A grading pass's verdict. A grade may FLAG, never retract — retraction
    would make progress non-monotonic, since stages.py and gate.py read reps."""

    UNGRADED = "ungraded"
    PENDING = "pending"
    PASSED = "passed"
    FLAGGED = "flagged"
    FAILED = "failed"


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
