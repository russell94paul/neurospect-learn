"""Evidence-backed consistency (Phase E6) — the streak, answerable to the record.

COMPUTED, never stored, and it mints NO NEW CURRENCY. concepts/architecture/
learning-enforcement.md §6 is explicit that the already-shipped surfaces (streak ·
adherence % · days-behind · pace, all in `routers/planner.py::_adherence`) should
become EVIDENCE-BACKED rather than self-reported, and equally explicit that E6
must not add XP, badges or points — so this module invents no new number. It
re-derives one that already exists from a source that cannot be typed in.

WHAT WAS WRONG WITH THE SHIPPED STREAK, precisely: `_adherence` walks
`plan_items.status`, and a status is written by clicking "done". E2 already removed
that click's ability to mint a REP (reps became derived from evidence), but the
streak still runs on it. So the platform's most motivating number was the one
number left that a click could still move. This module walks days that carry
EVIDENCE instead.

BOTH NUMBERS ARE PUBLISHED, not one replaced by the other — E2's own idiom, where
`reps` ships beside `reps_evidenced` and `reps_legacy` so the pre-evidence gap is
visible rather than folded away. A user whose marked streak is 12 and whose
evidenced streak is 3 has learned something true; being silently shown only the 3
would read as the app losing their work.

A DECLARED REST DAY IS NEUTRAL: it does not count toward the streak and does not
break it. It must have been declared IN ADVANCE — `rest_days` (Alembic `0012`)
enforces that with a trigger, and the enforcement is the entire reason rest days
can be allowed to touch a streak at all. §6 rejects the retroactive streak freeze
for exactly this reason: a day off you book after failing is not a day off.

WHAT THIS DELIBERATELY DOES NOT DO: it does not cap, penalise or judge a long run
of declared rest days. A month of booked leave and a month of pre-emptive excuses
are indistinguishable rows, and no constraint can separate them. So the count of
rest days inside the current streak is SURFACED alongside it (§5, "block the
certain, surface the rest") — a streak that is mostly rest days reads as one.
"""

from dataclasses import dataclass
from datetime import date, timedelta

#: How far back the streak walk will look before giving up. The walk normally
#: stops at the earliest day it has any record for; this is a hard stop so a
#: pathological rest-day set cannot make the loop unbounded.
MAX_LOOKBACK_DAYS = 366


@dataclass(frozen=True)
class Consistency:
    """The evidence-backed counterparts of the shipped adherence surfaces.

    Every field is a count of something that happened, never a score. There is no
    target here, nothing to fill, and no threshold — §6 forbids a currency, and a
    streak with a goal attached is a currency.
    """

    #: Distinct days on which at least one piece of evidence was captured.
    evidenced_days: int
    #: Consecutive days ending today that carry evidence. Declared rest days are
    #: neutral; today with nothing captured yet is neutral (still in progress).
    evidence_streak: int
    #: How many days of that streak were declared rest days rather than worked.
    #: PUBLISHED BESIDE the streak — an unqualified streak built mostly of booked
    #: days off would flatter, and the app cannot tell leave from an excuse.
    rest_days_in_streak: int
    last_evidence_date: date | None
    #: Days marked done in the planner that carry no evidence at all. The gap
    #: between the self-reported surface and the record — surfaced, never deducted.
    days_marked_without_evidence: int
    #: Declared rest days: all of them, and the ones still ahead.
    rest_days_declared: int
    rest_days_upcoming: int

    @property
    def worked_days_in_streak(self) -> int:
        return self.evidence_streak


def compute(
    *,
    today: date,
    evidence_dates: frozenset[date],
    rest_dates: frozenset[date],
    marked_dates: frozenset[date] = frozenset(),
) -> Consistency:
    """Re-derive the streak from days that carry evidence.

    `evidence_dates` — days with ≥1 `evidence_assets` row (server `created_at`,
    never the user-asserted `captured_at`: a streak that read an asserted timestamp
    could be extended by asserting one).
    `rest_dates` — days declared off IN ADVANCE (`rest_days`, trigger-enforced).
    `marked_dates` — days with ≥1 plan item marked done/partial, i.e. the
    self-reported surface, used only to report the gap.
    """
    streak = 0
    rest_in_streak = 0
    horizon = min(evidence_dates | rest_dates, default=today)
    day = today
    first = True
    steps = 0

    while day >= horizon and steps <= MAX_LOOKBACK_DAYS:
        if day in evidence_dates:
            streak += 1
        elif day in rest_dates:
            rest_in_streak += 1          # neutral: neither counts nor breaks
        elif first:
            pass                          # today, still in progress — neutral
        else:
            break
        day -= timedelta(days=1)
        first = False
        steps += 1

    return Consistency(
        evidenced_days=len(evidence_dates),
        evidence_streak=streak,
        rest_days_in_streak=rest_in_streak,
        last_evidence_date=max(evidence_dates) if evidence_dates else None,
        days_marked_without_evidence=len(marked_dates - evidence_dates),
        rest_days_declared=len(rest_dates),
        rest_days_upcoming=sum(1 for d in rest_dates if d > today),
    )
