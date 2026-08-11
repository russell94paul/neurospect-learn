"""Honesty signals (Phase E6) — the record, shown in the face of the claim.

COMPUTED, never stored — the convention `services/gate.py`, `services/stages.py`
and `services/calibration.py` all follow, and here it is load-bearing twice over.
A stored honesty number is a number someone can write; and a signal that lives
outside `GateResult` is a signal `gate.compute_readiness` structurally CANNOT
read, which is how E6 makes "gates nothing" a property rather than a promise.
That is the §E2 argument (derive, don't guard) pointed at a new target: there is
no honesty field in the gate's inputs to forget to ignore.

concepts/architecture/learning-enforcement.md §5 names exactly five things to
surface — implausible rep pacing, back-dated `captured_at`, bulk marking, ungraded
backlog, flagged-grade count — and names the idiom §5g established for them:
"shown in the face of the record, gating nothing on an invented rule."

FOUR RULES THIS MODULE HOLDS ITSELF TO
--------------------------------------

**1. A zero from an instrument that cannot see is not a measurement.** Every
signal reports the POPULATION it could actually inspect, and reports
`NOT_MEASURED` — never `0` — when that population is empty. Back-dating is the
sharp case: `evidence_assets.captured_at` is NULLABLE, so a capture that asserts
no capture time can be neither back-dated nor cleared of it. Counting those as
"0 back-dated" would turn a measurement gap into a claim about the user. This is
E5's `accuracy: None` precedent (`services/calibration.py`), applied five times.

**2. Every threshold is STATED, in the signal itself.** Two of the five need one
(what counts as a burst; how early is "back-dated"), and an unstated threshold is
an invented rule pretending to be a fact. They are published in `measured_what` so
the number can be discounted by anyone reading it. The other three need no
threshold at all and have none — they count a condition that is simply true or not.

**3. Nothing here is a verdict.** No signal is "good" or "bad", none has a target,
and a count of zero is not a win. §6 forbids rewarding activity over mastery, and a
green tick for "0 flags" is a point scored for not being caught. These are facts
placed beside a self-attestation, which is all §5g claims for them.

**4. A signal names its subjects.** Informational feedback (§6, Deci/Koestner/Ryan
1999) means the user can act on it; "3 captures were back-dated" without saying
which three is a scolding, not feedback.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# The two thresholds this module needs, isolated so they are impossible to use
# without seeing them. Both are PUBLISHED in the signal's `measured_what`.
# ---------------------------------------------------------------------------

#: Two captures for the SAME subject landing closer together than this are
#: reported as a burst. Not a rule — 60s is simply short enough that it cannot be
#: two separate reps of chart work, and long enough not to catch a normal
#: paste-then-paste-again correction.
BURST_SECONDS = 60

#: A capture whose ASSERTED capture time precedes its upload by more than this is
#: reported as back-dated. A day of slack, because working through a session and
#: uploading that evening is the normal honest path, not a signal.
BACKDATE_HOURS = 24

MEASURED = "measured"
NOT_MEASURED = "not_measured"

# The grader whose absence is the "ungraded backlog". E3 decided an unchecked rep
# STILL COUNTS (a self-check may flag but never retract), so the backlog is honest
# debt to surface — never a deduction. `deterministic` is excluded because it runs
# on every upload and its presence says nothing about whether the work was checked.
SELF_CHECK = "self_check"

#: `evidence_grades.state` values that mean a pass raised something.
FLAGGED_STATES = frozenset({"flagged", "failed"})


# ---------------------------------------------------------------------------
# Inputs (DB-agnostic views — the router loads them, this module never touches a DB)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Capture:
    """One evidence asset, as the honesty signals need to see it."""

    subject: str            # stable grouping key, e.g. "drill:aura D1-a"
    subject_label: str      # what the user calls it
    created_at: datetime    # SERVER-stamped upload time — the trustworthy one
    captured_at: datetime | None   # USER-asserted capture time — the claim
    reps_claimed: int
    #: Which graders have written a row for this asset.
    graders: frozenset[str] = frozenset()
    #: `evidence_grades` rows on this asset, and how many raised something.
    grade_count: int = 0
    flagged_count: int = 0


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Signal:
    """One honesty signal. Gates nothing, stores nothing, scores nothing.

    `status` is the load-bearing field, not `count`. A caller that reads `count`
    without reading `status` will read `None` and be forced to handle it — which
    is the point: there is no value of `count` that quietly means "nothing to see".
    """

    key: str
    label: str
    status: str                 # MEASURED | NOT_MEASURED
    #: Occurrences found. `None` whenever `status` is NOT_MEASURED — never 0.
    count: int | None
    #: How many rows the instrument could actually inspect.
    population: int
    #: What was looked at, and against what rule — including any threshold.
    measured_what: str
    #: What was found, or why nothing could be looked at.
    detail: str
    #: The subjects implicated, so the signal is actionable rather than a scolding.
    subjects: tuple[str, ...] = ()

    @property
    def measured(self) -> bool:
        return self.status == MEASURED


@dataclass(frozen=True)
class Honesty:
    """The five signals, plus what the whole strip was computed over."""

    signals: tuple[Signal, ...]
    captures: int
    #: Reps claimed before the evidence layer existed (E2's `legacy_reps`). E2 froze
    #: these and left them visible for exactly this phase — they are the one part of
    #: the rep count that never had evidence behind it and never can.
    reps_legacy: int = 0
    reps_evidenced: int = 0

    @property
    def measured_count(self) -> int:
        return sum(1 for s in self.signals if s.measured)


def _plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


def _subjects(rows: list[Capture]) -> tuple[str, ...]:
    """Distinct subject labels, in first-seen order, so the list is stable."""
    seen: dict[str, None] = {}
    for c in rows:
        seen.setdefault(c.subject_label, None)
    return tuple(seen)


# ---------------------------------------------------------------------------
# The five signals
# ---------------------------------------------------------------------------

def _bulk_marking(captures: list[Capture]) -> Signal:
    """One capture, many reps. NO THRESHOLD — `reps_claimed > 1` is a fact.

    Not an accusation: a single chart can legitimately carry a session's worth of
    marked ranges, and §1 chose `reps_claimed` over one-image-per-rep on purpose
    (a "1 week" habit target has no rep to photograph). What it IS is the shortest
    path between an upload and a rep count, so it is the one worth being able to see.
    """
    hits = [c for c in captures if c.reps_claimed > 1]
    claimed = sum(c.reps_claimed for c in hits)
    if not captures:
        return Signal(
            key="bulk_marking",
            label="Reps claimed per capture",
            status=NOT_MEASURED,
            count=None,
            population=0,
            measured_what="captures claiming more than one rep",
            detail="no evidence captured yet — nothing to count.",
        )
    return Signal(
        key="bulk_marking",
        label="Reps claimed per capture",
        status=MEASURED,
        count=len(hits),
        population=len(captures),
        measured_what=(
            f"all {len(captures)} {_plural(len(captures), 'capture')}, "
            "counting those that claim more than one rep"
        ),
        detail=(
            f"every capture claims exactly one rep."
            if not hits
            else f"{len(hits)} {_plural(len(hits), 'capture')} "
            f"{_plural(len(hits), 'claims', 'claim')} more than one rep "
            f"({claimed} reps from {len(hits)} {_plural(len(hits), 'capture')})."
        ),
        subjects=_subjects(hits),
    )


def _rep_pacing(captures: list[Capture]) -> Signal:
    """Captures for the SAME subject landing inside `BURST_SECONDS` of each other.

    Measured on `created_at` (the server's upload clock), never on the asserted
    `captured_at` — a signal about pacing that read a user-supplied timestamp
    could be silenced by supplying a different one.

    The population is NOT the capture count: a subject with one capture has no
    interval at all. Only the gaps are measurable, so the population is
    `captures − subjects`, and with no subject captured twice the honest answer is
    NOT_MEASURED rather than a reassuring zero.
    """
    by_subject: dict[str, list[Capture]] = defaultdict(list)
    for c in captures:
        by_subject[c.subject].append(c)

    gaps = 0
    hits: list[Capture] = []
    for rows in by_subject.values():
        rows = sorted(rows, key=lambda c: c.created_at)
        for prev, cur in zip(rows, rows[1:]):
            gaps += 1
            if cur.created_at - prev.created_at < timedelta(seconds=BURST_SECONDS):
                hits.append(cur)

    if gaps == 0:
        return Signal(
            key="rep_pacing",
            label="Rep pacing",
            status=NOT_MEASURED,
            count=None,
            population=0,
            measured_what=(
                f"the gap between consecutive captures of the same subject "
                f"(a gap under {BURST_SECONDS}s is reported)"
            ),
            detail=(
                "no subject has been captured twice yet, so there is no interval to "
                "measure. This is not a clean result — it is an absent one."
            ),
        )
    return Signal(
        key="rep_pacing",
        label="Rep pacing",
        status=MEASURED,
        count=len(hits),
        population=gaps,
        measured_what=(
            f"{gaps} {_plural(gaps, 'gap')} between consecutive captures of the same "
            f"subject, by server upload time; a gap under {BURST_SECONDS}s is reported"
        ),
        detail=(
            f"no two captures of the same subject landed within {BURST_SECONDS}s."
            if not hits
            else f"{len(hits)} {_plural(len(hits), 'capture')} landed within "
            f"{BURST_SECONDS}s of the previous capture for the same subject."
        ),
        subjects=_subjects(hits),
    )


def _back_dating(captures: list[Capture]) -> Signal:
    """An asserted `captured_at` more than `BACKDATE_HOURS` before the upload.

    THE SHARP CASE for rule 1. `captured_at` is nullable and user-asserted (E2 chose
    that deliberately — `models/evidence.py` says so: "back-dating is SURFACED,
    never blocked"). A capture asserting no time at all cannot be back-dated OR
    cleared, so it is excluded from the population and reported separately. Folding
    those into a zero would convert "the instrument was never given a reading" into
    "the user did nothing wrong", which is the exact substitution this rule exists
    to prevent.
    """
    dated = [c for c in captures if c.captured_at is not None]
    undated = len(captures) - len(dated)
    threshold = timedelta(hours=BACKDATE_HOURS)
    hits = [c for c in dated if c.captured_at is not None and c.created_at - c.captured_at > threshold]

    undated_note = (
        ""
        if not undated
        else f" {undated} {_plural(undated, 'capture')} "
        f"{_plural(undated, 'asserts', 'assert')} no capture time and "
        f"{_plural(undated, 'is', 'are')} outside this measurement entirely."
    )

    if not dated:
        return Signal(
            key="back_dating",
            label="Back-dated captures",
            status=NOT_MEASURED,
            count=None,
            population=0,
            measured_what=(
                f"captures asserting a capture time, against the upload time the "
                f"server recorded (earlier by more than {BACKDATE_HOURS}h is reported)"
            ),
            detail=(
                "no capture asserts a capture time, so there is nothing to compare "
                "against the upload clock. Not clean — unmeasured."
                + undated_note
            ),
        )
    return Signal(
        key="back_dating",
        label="Back-dated captures",
        status=MEASURED,
        count=len(hits),
        population=len(dated),
        measured_what=(
            f"{len(dated)} of {len(captures)} {_plural(len(captures), 'capture')} that "
            f"assert a capture time, against the upload time the server recorded; "
            f"earlier by more than {BACKDATE_HOURS}h is reported"
        ),
        detail=(
            f"every asserted capture time is within {BACKDATE_HOURS}h of its upload."
            if not hits
            else f"{len(hits)} {_plural(len(hits), 'capture')} "
            f"{_plural(len(hits), 'asserts', 'assert')} a capture time more than "
            f"{BACKDATE_HOURS}h before the upload."
        ) + undated_note,
        subjects=_subjects(hits),
    )


def _ungraded_backlog(captures: list[Capture]) -> Signal:
    """Captures carrying no `self_check` grade.

    E3 decided an unchecked rep STILL COUNTS — a self-check may flag but never
    retract — so this is the honest backlog that decision created, and surfacing it
    is what that decision promised in exchange. It is DEBT, not a deduction:
    nothing here reduces a rep, and §5's "surface the rest" is the whole remit.
    """
    if not captures:
        return Signal(
            key="ungraded_backlog",
            label="Unchecked captures",
            status=NOT_MEASURED,
            count=None,
            population=0,
            measured_what="captures carrying a self-check against the drill's own bar",
            detail="no evidence captured yet — nothing to check.",
        )
    hits = [c for c in captures if SELF_CHECK not in c.graders]
    return Signal(
        key="ungraded_backlog",
        label="Unchecked captures",
        status=MEASURED,
        count=len(hits),
        population=len(captures),
        measured_what=(
            f"all {len(captures)} {_plural(len(captures), 'capture')}, counting those "
            "with no self-check against the drill's own bar"
        ),
        detail=(
            "every capture has been checked against its drill's bar."
            if not hits
            else f"{len(hits)} of {len(captures)} {_plural(len(captures), 'capture')} "
            f"{_plural(len(hits), 'has', 'have')} not been checked against the drill's "
            "bar. These reps still count — the backlog is shown, not deducted."
        ),
        subjects=_subjects(hits),
    )


def _flagged_grades(captures: list[Capture]) -> Signal:
    """Grading passes that raised something, across every grader.

    The population is GRADE ROWS, not captures: a capture with no grade has not
    been judged, and counting it as unflagged would credit silence as a pass.
    """
    grades = sum(c.grade_count for c in captures)
    flagged = sum(c.flagged_count for c in captures)
    hits = [c for c in captures if c.flagged_count > 0]
    if grades == 0:
        return Signal(
            key="flagged_grades",
            label="Flagged grades",
            status=NOT_MEASURED,
            count=None,
            population=0,
            measured_what="grading passes whose verdict was flagged or failed",
            detail="no grading pass has run yet, so nothing has been judged either way.",
        )
    return Signal(
        key="flagged_grades",
        label="Flagged grades",
        status=MEASURED,
        count=flagged,
        population=grades,
        measured_what=(
            f"all {grades} grading {_plural(grades, 'pass', 'passes')} written across "
            "your captures, counting those whose verdict was flagged or failed"
        ),
        detail=(
            f"no grading pass has been flagged."
            if not flagged
            else f"{flagged} of {grades} grading {_plural(grades, 'pass', 'passes')} "
            f"{_plural(flagged, 'was', 'were')} flagged, across "
            f"{len(hits)} {_plural(len(hits), 'capture')}. A flag never retracts a rep."
        ),
        subjects=_subjects(hits),
    )


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def compute(
    captures: list[Capture],
    *,
    reps_legacy: int = 0,
    reps_evidenced: int = 0,
) -> Honesty:
    """The five §5 signals over this user's evidence. Pure, total, order-independent."""
    rows = list(captures)
    return Honesty(
        signals=(
            _rep_pacing(rows),
            _back_dating(rows),
            _bulk_marking(rows),
            _ungraded_backlog(rows),
            _flagged_grades(rows),
        ),
        captures=len(rows),
        reps_legacy=reps_legacy,
        reps_evidenced=reps_evidenced,
    )
