"""The five honesty signals (Phase E6) — pure, DB-free.

`app/services/honesty.py` holds the rules; this file pins the two properties that
make the strip worth showing at all, plus the arithmetic of each signal.

THE PROPERTY THIS FILE EXISTS FOR: **a zero from an instrument that cannot see is
not a measurement.** Every signal must report NOT_MEASURED — with `count` of
`None`, never `0` — when the population it inspects is empty. Rendering "0
back-dated captures" for a user who has asserted no capture times converts a
measurement gap into a claim about that user's behaviour, which is precisely the
substitution the design forbids. E5 established the shape with `accuracy: None`
(tests/test_calibration.py); E6 owes it five times over.

The second property is that NOTHING HERE IS A VERDICT: no signal carries a score,
a threshold-as-judgement, a target or a pass/fail, because §6 (Deci/Koestner/Ryan
1999) forbids rewarding activity over mastery and a green "0 flags" badge is a
point scored for not being caught.
"""

from datetime import datetime, timedelta, timezone

from app.services import honesty

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def cap(
    *,
    subject: str = "drill:aura D1-a",
    label: str = "aura D1-a",
    created: datetime = NOW,
    captured: datetime | None = None,
    reps: int = 1,
    graders: tuple[str, ...] = ("deterministic",),
    grades: int = 1,
    flagged: int = 0,
) -> honesty.Capture:
    return honesty.Capture(
        subject=subject,
        subject_label=label,
        created_at=created,
        captured_at=captured,
        reps_claimed=reps,
        graders=frozenset(graders),
        grade_count=grades,
        flagged_count=flagged,
    )


def by_key(result: honesty.Honesty) -> dict[str, honesty.Signal]:
    return {s.key: s for s in result.signals}


# ---------------------------------------------------------------------------
# THE LOAD-BEARING RULE — not-measured is not zero
# ---------------------------------------------------------------------------

def test_an_empty_record_reports_not_measured_on_every_signal_never_zero():
    """The whole strip, over nothing. Not one signal may report a reassuring 0."""
    result = honesty.compute([])
    assert len(result.signals) == 5
    for s in result.signals:
        assert s.status == honesty.NOT_MEASURED, s.key
        assert s.count is None, f"{s.key} reported {s.count!r} — a zero from an unfed instrument"
        assert s.population == 0
        assert s.detail, s.key
    assert result.measured_count == 0


def test_a_clean_measurement_is_distinguishable_from_an_absent_one():
    """The distinction is the point: both are 'nothing wrong', and only one of them
    is a measurement. A consumer must be able to tell them apart."""
    absent = by_key(honesty.compute([]))["bulk_marking"]
    clean = by_key(honesty.compute([cap(reps=1)]))["bulk_marking"]

    assert absent.status == honesty.NOT_MEASURED and absent.count is None
    assert clean.status == honesty.MEASURED and clean.count == 0
    assert absent.detail != clean.detail


def test_back_dating_excludes_captures_that_assert_no_time_at_all():
    """THE SHARP CASE. `captured_at` is nullable, so a capture asserting no time
    can be neither back-dated nor cleared of it. Counting those as 'not back-dated'
    would credit the user for a reading the instrument never took."""
    result = by_key(honesty.compute([cap(captured=None), cap(captured=None)]))["back_dating"]
    assert result.status == honesty.NOT_MEASURED
    assert result.count is None
    assert result.population == 0
    # And it must SAY so, rather than quietly omitting them.
    assert "no capture time" in result.detail
    assert "2 captures" in result.detail


def test_back_dating_reports_the_undated_alongside_a_real_measurement():
    """With a mix, the measured subset is measured AND the excluded count is stated
    — the population must never be silently equated with the capture count."""
    rows = [
        cap(captured=NOW - timedelta(minutes=5)),          # dated, fine
        cap(captured=None),                                 # excluded
        cap(captured=None),                                 # excluded
    ]
    s = by_key(honesty.compute(rows))["back_dating"]
    assert s.status == honesty.MEASURED
    assert s.count == 0 and s.population == 1
    assert "2 captures assert no capture time" in s.detail


def test_pacing_is_not_measured_until_a_subject_is_captured_twice():
    """One capture per subject means zero intervals. 'No burst detected' would be a
    claim; 'there is no interval to measure' is the truth."""
    rows = [cap(subject="drill:a", label="a"), cap(subject="drill:b", label="b")]
    s = by_key(honesty.compute(rows))["rep_pacing"]
    assert s.status == honesty.NOT_MEASURED
    assert s.count is None and s.population == 0
    assert "not a clean result" in s.detail.lower()


def test_flagged_grades_are_not_measured_until_something_has_been_graded():
    """A capture nobody graded has not been judged. Counting it as unflagged would
    credit silence as a pass."""
    s = by_key(honesty.compute([cap(graders=(), grades=0)]))["flagged_grades"]
    assert s.status == honesty.NOT_MEASURED
    assert s.count is None and s.population == 0


# ---------------------------------------------------------------------------
# Each signal's arithmetic
# ---------------------------------------------------------------------------

def test_bulk_marking_counts_captures_claiming_more_than_one_rep():
    rows = [cap(reps=1), cap(reps=12, label="aura D1-b"), cap(reps=3, label="aura D1-c")]
    s = by_key(honesty.compute(rows))["bulk_marking"]
    assert s.status == honesty.MEASURED
    assert s.count == 2 and s.population == 3
    assert "15 reps from 2 captures" in s.detail
    assert set(s.subjects) == {"aura D1-b", "aura D1-c"}


def test_pacing_measures_gaps_within_a_subject_never_across_subjects():
    """Two different drills captured back to back is normal work, not a burst."""
    rows = [
        cap(subject="drill:a", label="a", created=NOW),
        cap(subject="drill:b", label="b", created=NOW + timedelta(seconds=2)),
    ]
    s = by_key(honesty.compute(rows))["rep_pacing"]
    assert s.status == honesty.NOT_MEASURED, "different subjects share no interval"


def test_pacing_flags_a_burst_on_the_same_subject():
    rows = [
        cap(subject="drill:a", label="a", created=NOW),
        cap(subject="drill:a", label="a", created=NOW + timedelta(seconds=5)),
        cap(subject="drill:a", label="a", created=NOW + timedelta(hours=3)),
    ]
    s = by_key(honesty.compute(rows))["rep_pacing"]
    assert s.status == honesty.MEASURED
    assert s.population == 2, "three captures of one subject give two gaps"
    assert s.count == 1, "only the 5s gap is under the threshold"


def test_pacing_reads_the_server_clock_not_the_asserted_one():
    """A signal about pacing that trusted `captured_at` could be silenced by
    asserting a different one — the same hole E2 closed by deriving `reps`."""
    rows = [
        cap(subject="drill:a", label="a", created=NOW, captured=NOW - timedelta(days=9)),
        cap(subject="drill:a", label="a", created=NOW + timedelta(seconds=3),
            captured=NOW - timedelta(days=4)),
    ]
    s = by_key(honesty.compute(rows))["rep_pacing"]
    assert s.count == 1, "the uploads were 3s apart however the captures were labelled"


def test_back_dating_uses_the_stated_threshold_and_states_it():
    """An unstated threshold is an invented rule wearing a fact's clothes."""
    inside = cap(created=NOW, captured=NOW - timedelta(hours=honesty.BACKDATE_HOURS - 1))
    outside = cap(created=NOW, captured=NOW - timedelta(hours=honesty.BACKDATE_HOURS + 1),
                  label="aura D2-a")
    s = by_key(honesty.compute([inside, outside]))["back_dating"]
    assert s.count == 1 and s.population == 2
    assert s.subjects == ("aura D2-a",)
    assert f"{honesty.BACKDATE_HOURS}h" in s.measured_what


def test_pacing_states_its_threshold_too():
    rows = [cap(subject="drill:a", label="a", created=NOW),
            cap(subject="drill:a", label="a", created=NOW + timedelta(hours=2))]
    s = by_key(honesty.compute(rows))["rep_pacing"]
    assert f"{honesty.BURST_SECONDS}s" in s.measured_what


def test_a_future_captured_at_is_not_reported_as_back_dating():
    """Back-dating is a claim that the work happened EARLIER. A capture time after
    the upload is a different thing entirely and this signal must not claim it."""
    s = by_key(honesty.compute([cap(created=NOW, captured=NOW + timedelta(days=2))]))["back_dating"]
    assert s.status == honesty.MEASURED and s.count == 0


def test_ungraded_backlog_ignores_the_deterministic_pass():
    """`deterministic` runs on every upload, so its presence says nothing about
    whether the work was checked against the drill's bar. Only `self_check` counts."""
    rows = [
        cap(graders=("deterministic",)),
        cap(graders=("deterministic", "ai_vision"), label="aura D1-b"),
        cap(graders=("deterministic", "self_check"), label="aura D1-c"),
    ]
    s = by_key(honesty.compute(rows))["ungraded_backlog"]
    assert s.count == 2, "an AI reading is not a self-check"
    assert set(s.subjects) == {"aura D1-a", "aura D1-b"}


def test_the_backlog_says_the_reps_still_count():
    """E3 decided an unchecked rep STILL COUNTS. The surface must say so, or the
    backlog reads as a threat to progress the user has already earned."""
    s = by_key(honesty.compute([cap(graders=("deterministic",))]))["ungraded_backlog"]
    assert "still count" in s.detail


def test_flagged_grades_count_passes_not_captures():
    rows = [cap(grades=3, flagged=2), cap(grades=2, flagged=0, label="aura D1-b")]
    s = by_key(honesty.compute(rows))["flagged_grades"]
    assert s.count == 2 and s.population == 5
    assert s.subjects == ("aura D1-a",)
    assert "never retracts a rep" in s.detail


# ---------------------------------------------------------------------------
# §6 — nothing here may become a currency
# ---------------------------------------------------------------------------

def test_no_signal_carries_a_score_grade_or_target():
    """§6 forbids XP/badges/points. A signal is a fact placed beside a claim; the
    moment it has a target, someone will farm it."""
    banned = {"score", "grade", "target", "points", "xp", "level", "badge", "streak", "rank"}
    for s in honesty.compute([cap()]).signals:
        assert banned.isdisjoint(vars(s).keys()), s.key


def test_every_signal_states_what_it_measured_and_names_its_subjects():
    """Informational feedback (§6) means actionable. '3 captures were back-dated'
    without saying which three is a scolding, not feedback."""
    rows = [
        cap(subject="drill:a", label="a", created=NOW, captured=NOW - timedelta(days=4),
            reps=5, graders=("deterministic",), grades=2, flagged=1),
        cap(subject="drill:a", label="a", created=NOW + timedelta(seconds=2),
            captured=NOW - timedelta(days=4), reps=5, graders=("deterministic",),
            grades=2, flagged=1),
    ]
    result = honesty.compute(rows)
    for s in result.signals:
        assert s.measured_what.strip(), s.key
        assert s.detail.strip(), s.key
        assert s.status == honesty.MEASURED, s.key
        assert s.count and s.count > 0, s.key
        assert s.subjects, f"{s.key} found something but named no subject"


def test_the_computation_is_order_independent():
    rows = [
        cap(subject="drill:a", label="a", created=NOW, reps=4),
        cap(subject="drill:a", label="a", created=NOW + timedelta(seconds=10)),
        cap(subject="drill:b", label="b", created=NOW + timedelta(days=1), captured=NOW),
    ]
    forward = honesty.compute(rows)
    backward = honesty.compute(list(reversed(rows)))
    assert [(s.key, s.status, s.count, s.population) for s in forward.signals] == \
           [(s.key, s.status, s.count, s.population) for s in backward.signals]


def test_legacy_reps_are_carried_through_as_the_one_unevidenced_number():
    """E2 froze `legacy_reps` and left it visible for exactly this phase — it is the
    part of the rep count that has no evidence behind it and never can."""
    result = honesty.compute([cap()], reps_legacy=7, reps_evidenced=3)
    assert result.reps_legacy == 7
    assert result.reps_evidenced == 3
