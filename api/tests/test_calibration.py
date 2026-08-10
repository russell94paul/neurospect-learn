"""Pure tests for the calibration score (Phase E5). DB-FREE, deliberately.

`services/calibration.py` makes two claims that are the whole reason the mechanic
was allowed into the design, and this file is where they stop being claims:

1. **Goodhart-resistant — "more reps cannot inflate accuracy"** (design §6). The
   direct form of that statement is SCALE INVARIANCE: multiply the whole record by
   k and every percentage is unchanged. That is
   `test_scale_invariance_is_what_makes_more_reps_worthless`, and it is the test to
   read if you want to know whether the property actually holds.
2. **A zero and a nothing are different things.** With no resolved call, every
   accuracy is `None`. Reporting 0% for "you have not scored a call yet" would be a
   claim about the trader that the data does not support.

The third leg of the Goodhart argument — that the DENOMINATOR CANNOT SHRINK —
cannot be tested here, because it is not arithmetic: it is the absence of an
`is_deleted` column and the presence of a freeze trigger in Alembic `0011`. It is
pinned in tests/test_predictions.py instead, at the layer that can actually try to
delete something.
"""

from app.services import calibration


def _call(*, resolved=True, bias=True, dol=True, model=True, target=True) -> calibration.Call:
    if not resolved:
        return calibration.Call(resolved=False)
    return calibration.Call(
        resolved=True,
        bias_correct=bias,
        dol_correct=dol,
        entry_model_correct=model,
        target_correct=target,
    )


def _acc(score: calibration.Calibration) -> dict:
    return {c.key: c.accuracy for c in score.components}


# ---------------------------------------------------------------------------
# The instrument has to be able to see before a zero means anything
# ---------------------------------------------------------------------------

def test_nothing_committed_reports_none_never_zero():
    score = calibration.compute([])
    assert score.committed == 0 and score.resolved == 0 and score.unresolved == 0
    assert score.accuracy is None, "0% would claim the trader was wrong; they have not called yet"
    assert score.resolution_rate is None
    assert all(c.accuracy is None for c in score.components)
    assert all(c.resolved == 0 and c.correct == 0 for c in score.components)


def test_committed_but_unresolved_still_reports_no_accuracy():
    """A commitment whose answer is not in yet is not a wrong answer."""
    score = calibration.compute([_call(resolved=False) for _ in range(5)])
    assert score.committed == 5 and score.resolved == 0 and score.unresolved == 5
    assert score.accuracy is None
    assert score.resolution_rate == 0.0  # 0 of 5 resolved — this ratio IS measured
    assert all(c.accuracy is None for c in score.components)


# ---------------------------------------------------------------------------
# THE GOODHART PROPERTY
# ---------------------------------------------------------------------------

def test_scale_invariance_is_what_makes_more_reps_worthless():
    """Multiply the whole record by k → every percentage identical.

    This is design §6's "more reps cannot inflate accuracy" stated so that it can
    be checked rather than asserted. Volume moves the counts and nothing else.
    """
    base = [
        _call(bias=True, dol=True, model=False, target=False),
        _call(bias=True, dol=False, model=False, target=True),
        _call(bias=False, dol=True, model=True, target=False),
        _call(resolved=False),
    ]
    one = calibration.compute(base)
    for k in (2, 3, 10, 97):
        many = calibration.compute(base * k)
        assert many.accuracy == one.accuracy, f"×{k} moved the pooled accuracy"
        assert many.resolution_rate == one.resolution_rate, f"×{k} moved the resolution rate"
        assert _acc(many) == _acc(one), f"×{k} moved a component accuracy"
        # The counts DO scale — the score is a ratio over them, which is the point.
        assert many.committed == one.committed * k
        assert many.resolved == one.resolved * k


def test_adding_a_wrong_call_can_only_lower_the_score():
    good = [_call() for _ in range(4)]
    before = calibration.compute(good)
    after = calibration.compute([*good, _call(bias=False, dol=False, model=False, target=False)])
    assert before.accuracy == 1.0
    assert after.accuracy is not None and after.accuracy < before.accuracy


def test_adding_an_unresolved_call_moves_no_accuracy_at_all():
    """Committing more calls without resolving them cannot flatter the record —
    it only makes the unresolved backlog bigger, which is surfaced."""
    resolved = [_call(bias=True, dol=False, model=True, target=True) for _ in range(3)]
    before = calibration.compute(resolved)
    after = calibration.compute([*resolved, *[_call(resolved=False) for _ in range(50)]])
    assert after.accuracy == before.accuracy
    assert _acc(after) == _acc(before)
    assert after.unresolved == 50
    assert after.resolution_rate is not None and after.resolution_rate < 0.06


def test_the_resolution_rate_exposes_the_one_remaining_bias():
    """Resolving only the calls you got right is the one way left to bias this, and
    the app cannot force a resolution — so the gap is PUBLISHED beside the score
    rather than pretended away."""
    cherry = [_call() for _ in range(3)] + [_call(resolved=False) for _ in range(17)]
    score = calibration.compute(cherry)
    assert score.accuracy == 1.0, "a cherry-picked record can still read 100%…"
    assert score.resolution_rate == 0.15, "…but only 15% of the calls were ever scored"
    assert score.unresolved == 17


def test_order_independence():
    calls = [
        _call(bias=False),
        _call(resolved=False),
        _call(dol=False, target=False),
        _call(),
    ]
    a = calibration.compute(calls)
    b = calibration.compute(list(reversed(calls)))
    assert (a.accuracy, _acc(a), a.resolution_rate) == (b.accuracy, _acc(b), b.resolution_rate)


# ---------------------------------------------------------------------------
# The components are the wiki's four, and each is scored independently
# ---------------------------------------------------------------------------

def test_components_are_the_four_the_wiki_asks_for():
    """ict-course/exercises.md §Stage 6: "note bias call, DOL, the model used,
    entry/target"; T-14: "call the read (bias, DOL, model, target)"."""
    assert [k for k, _ in calibration.COMPONENTS] == ["bias", "dol", "entry_model", "target"]
    score = calibration.compute([_call()])
    assert [c.key for c in score.components] == ["bias", "dol", "entry_model", "target"]


def test_each_component_is_scored_on_its_own():
    score = calibration.compute([
        _call(bias=True, dol=True, model=False, target=False),
        _call(bias=True, dol=False, model=False, target=False),
    ])
    assert _acc(score) == {"bias": 1.0, "dol": 0.5, "entry_model": 0.0, "target": 0.0}
    # Pooled: 3 of 8 component judgements correct.
    assert score.accuracy == 3 / 8


def test_a_component_the_db_cannot_produce_is_counted_in_neither_half():
    """`ck_predictions_resolution_complete` makes a half-written reveal
    unreachable; if one ever arrived, it must not silently count as a miss."""
    score = calibration.compute([
        calibration.Call(resolved=True, bias_correct=True, dol_correct=None,
                         entry_model_correct=None, target_correct=None),
    ])
    by_key = {c.key: c for c in score.components}
    assert (by_key["bias"].correct, by_key["bias"].resolved) == (1, 1)
    assert (by_key["dol"].correct, by_key["dol"].resolved) == (0, 0)
    assert by_key["dol"].accuracy is None
    assert score.accuracy == 1.0
