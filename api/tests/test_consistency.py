"""Evidence-backed consistency (Phase E6) — pure, DB-free.

`app/services/consistency.py` re-derives the shipped streak from days that carry
EVIDENCE rather than from days someone clicked "done". The tests that matter are
not the arithmetic but the two design claims:

  * **A declared rest day is NEUTRAL** — it does not break the streak and does not
    count toward it. If it counted, booking days off would be the cheapest way to
    raise the number, which is exactly the score-chase §6 forbids.
  * **The one thing this cannot prevent is SURFACED, not hidden** — a streak held
    up by a long run of booked rest days is reported as such, because no constraint
    can tell planned leave from a pre-emptive excuse.
"""

from datetime import date, timedelta

from app.services import consistency

TODAY = date(2026, 8, 10)


def days(*offsets: int) -> frozenset[date]:
    """Dates relative to TODAY: `days(0, -1)` is today and yesterday."""
    return frozenset(TODAY + timedelta(days=o) for o in offsets)


def run(*, evidence=frozenset(), rest=frozenset(), marked=frozenset(), today=TODAY):
    return consistency.compute(
        today=today, evidence_dates=evidence, rest_dates=rest, marked_dates=marked
    )


# ---------------------------------------------------------------------------
# THE PROPERTY §6 DEMANDS — no number here can be raised without doing the work
# ---------------------------------------------------------------------------

def test_declaring_rest_days_cannot_raise_the_streak():
    """THE SCORE-CHASE TEST. Rest days exist so a planned day off does not destroy
    a real record — not so a streak can be manufactured. Booking ten of them must
    move the streak by exactly zero."""
    worked = run(evidence=days(0))
    rested = run(evidence=days(0), rest=days(-1, -2, -3, -4, -5, -6, -7, -8, -9, -10))
    assert worked.evidence_streak == 1
    assert rested.evidence_streak == 1, "a rest day is neutral, never a credit"


def test_a_rest_day_bridges_a_gap_without_being_counted_as_work():
    """Worked Friday, booked Saturday off, worked Sunday: the streak survives and
    reports 2 worked days plus 1 rest day — never 3."""
    c = run(evidence=days(0, -2), rest=days(-1))
    assert c.evidence_streak == 2
    assert c.rest_days_in_streak == 1


def test_an_undeclared_gap_breaks_the_streak():
    c = run(evidence=days(0, -2))
    assert c.evidence_streak == 1, "yesterday was neither worked nor declared off"


def test_a_streak_made_mostly_of_rest_days_reports_itself_as_one():
    """The gameable edge, surfaced rather than blocked (§5). Nothing can distinguish
    a month of booked leave from a month of excuses — so the composition is
    published and the reader can judge it."""
    c = run(evidence=days(0, -10), rest=days(*range(-9, 0)))
    assert c.evidence_streak == 2
    assert c.rest_days_in_streak == 9, "the strip must be able to say 2 worked, 9 rested"


def test_today_with_nothing_captured_yet_is_neutral_not_a_break():
    """Reading the page at 9am must not report the streak you are still working on
    as already broken — the shipped `_adherence` streak has the same courtesy."""
    c = run(evidence=days(-1, -2))
    assert c.evidence_streak == 2


def test_yesterday_with_nothing_captured_does_break_it():
    c = run(evidence=days(-2, -3))
    assert c.evidence_streak == 0


# ---------------------------------------------------------------------------
# The gap between the claim and the record
# ---------------------------------------------------------------------------

def test_days_marked_without_evidence_is_the_gap_between_claim_and_record():
    """The self-reported surface says four days were worked; evidence exists for
    one. The difference is the number E6 exists to make visible."""
    c = run(evidence=days(0), marked=days(0, -1, -2, -3))
    assert c.days_marked_without_evidence == 3


def test_evidence_without_a_mark_is_not_counted_as_a_gap():
    """Doing the work and not ticking the planner is not dishonesty — the signal is
    about claims exceeding the record, not the reverse."""
    c = run(evidence=days(0, -1, -2), marked=days(0))
    assert c.days_marked_without_evidence == 0


def test_the_marked_streak_is_not_recomputed_here():
    """This module publishes an evidence-backed counterpart; it never overwrites the
    shipped figure. E2's idiom — `reps` ships beside `reps_evidenced`/`reps_legacy`
    — so a user whose marked streak is 12 and evidenced streak is 3 sees both."""
    c = run(evidence=days(0), marked=days(0, -1, -2))
    assert not hasattr(c, "current_streak")
    assert not hasattr(c, "adherence_pct")


# ---------------------------------------------------------------------------
# Counts and bounds
# ---------------------------------------------------------------------------

def test_counts_and_last_evidence_date():
    c = run(evidence=days(0, -1, -5), rest=days(1, 2, -1))
    assert c.evidenced_days == 3
    assert c.last_evidence_date == TODAY
    assert c.rest_days_declared == 3
    assert c.rest_days_upcoming == 2, "only the two future ones are still ahead"


def test_an_empty_record_is_all_zeroes_and_no_last_date():
    c = run()
    assert c.evidence_streak == 0
    assert c.evidenced_days == 0
    assert c.last_evidence_date is None
    assert c.rest_days_in_streak == 0


def test_the_walk_is_bounded_even_against_a_pathological_rest_set():
    """A rest day set spanning years must not make the walk unbounded."""
    huge = frozenset(TODAY - timedelta(days=n) for n in range(1, 3000))
    c = run(evidence=days(0), rest=huge)
    assert c.evidence_streak == 1
    assert c.rest_days_in_streak <= consistency.MAX_LOOKBACK_DAYS
