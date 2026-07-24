"""Unit tests for the deterministic Study-Planner scheduler (Phase 5e-2).

These run with NO database — the scheduler is a pure function over view
dataclasses. They pin the behaviours the boot prompt's VERIFY step requires:
determinism, per-track gate unlock, locked stages never scheduled, U5
observe-only, blackout / 0-budget skips, max-session cap, spaced-review due
dates, and slippage re-queue.
"""

from datetime import date, timedelta

from app.models.enums import PlanActivity, PlanItemStatus
from app.services import scheduler as S
from app.services import stages

WED = date(2026, 7, 22)  # a Wednesday (weekday() == 2)

# Mon..Sun budget; Sunday (index 6) is 0 to test 0-budget skips.
FULL_WEEK = (60, 60, 60, 60, 60, 120, 0)


def _prefs(**kw):
    base = dict(
        weekday_minutes=FULL_WEEK, max_session_minutes=45, active_track="aura",
        blackout_dates=frozenset(), target_go_live_date=None,
    )
    base.update(kw)
    return S.PrefsView(**base)


def _aura_metas():
    return [
        stages.StageMeta("aura", "A0", 0, "Foundation"),
        stages.StageMeta("aura", "A1", 1, "Structure"),
        stages.StageMeta("aura", "A2", 2, "Advanced"),
    ]


def _concepts():
    return [
        S.ConceptView("f1", "aura-psych", "A0", 0, 0, "Psychology", False, False, "-", "psych", ()),
        S.ConceptView("a1", "aura-swings", "A1", 1, 10, "Swing points", True, False, ">=50 swings", "swings", ("aura D1-a",)),
        S.ConceptView("a2", "aura-liq", "A1", 1, 11, "Liquidity", True, False, "10 days", "liq", ("aura D1-b",)),
        S.ConceptView("adv", "aura-adv", "A2", 2, 20, "Advanced", True, False, ">=20", None, ()),
    ]


def _drills():
    return [
        S.DrillView("aura D1-a", "A1", ">=50 swings", 0),
        S.DrillView("aura D1-b", "A1", "10 days", 1),
    ]


def _run(concept_progress=None, drill_progress=None, past=None, prefs=None, horizon=20):
    return S.schedule(
        WED, prefs or _prefs(), _aura_metas(), _concepts(), _drills(),
        concept_progress or {}, drill_progress or {}, past or [], horizon_days=horizon,
    )


def _sig(result):
    return [(i.scheduled_date, i.activity, i.concept_id, i.drill_ref, i.target_qty) for i in result.items]


# ---------------------------------------------------------------------------

def test_deterministic_same_inputs_identical_plan():
    a = _run()
    b = _run()
    assert _sig(a) == _sig(b)
    assert [i.sort_order for i in a.items] == [i.sort_order for i in b.items]


def test_locked_stages_never_scheduled():
    # No progress → only the foundation stage (A0) is unlocked. A1/A2 concepts
    # and their drills must NOT appear anywhere in the plan.
    res = _run()
    ids = {i.concept_id for i in res.items}
    refs = {i.drill_ref for i in res.items}
    assert "f1" in ids                    # foundation scheduled
    assert "a1" not in ids and "a2" not in ids and "adv" not in ids
    assert "aura D1-a" not in refs and "aura D1-b" not in refs


def test_unlock_after_foundation_met():
    # Mark the foundation concept to Can-mark → A0 auto_met → A1 unlocks.
    prog = {"aura-psych": S.ConceptProgressView(stages.CAN_MARK, 3, 5, WED)}
    res = _run(concept_progress=prog)
    ids = {i.concept_id for i in res.items}
    assert "a1" in ids and "a2" in ids     # A1 concepts now scheduled
    assert "adv" not in ids                # A2 still locked (A1 not auto_met)
    # A1's drills are now scheduled too.
    assert {"aura D1-a", "aura D1-b"} <= {i.drill_ref for i in res.items}


def test_u5_observe_only_and_capped():
    metas = [stages.StageMeta("aura", "A0", 0, "Foundation"),
             stages.StageMeta("aura", "AF", 1, "Frontier")]
    # Foundation met so the frontier stage unlocks.
    concepts = [
        S.ConceptView("f1", "aura-psych", "A0", 0, 0, "Psych", False, False, "-", "psych", ()),
        S.ConceptView("w1", "aura-frontier", "AF", 1, 10, "Frontier idea", False, True, "-", "front", ("aura D1-a",)),
    ]
    prog = {"aura-psych": S.ConceptProgressView(stages.CAN_MARK, 3, 5, WED)}
    res = S.schedule(WED, _prefs(), metas, concepts, _drills(), prog, {}, [], horizon_days=10)
    w_items = [i for i in res.items if i.concept_id == "w1"]
    assert w_items and all(i.activity == PlanActivity.OBSERVE for i in w_items)
    # Never learn/drill a watch-only concept.
    assert all(i.drill_ref != "aura D1-a" for i in res.items)
    # Capped: once observed to Can-mark, no more observe tasks.
    prog["aura-frontier"] = S.ConceptProgressView(stages.CAN_MARK, 3, 1, WED)
    res2 = S.schedule(WED, _prefs(), metas, concepts, _drills(), prog, {}, [], horizon_days=10)
    assert not [i for i in res2.items if i.concept_id == "w1"]


def test_blackout_and_zero_budget_days_skipped():
    blackout = WED + timedelta(days=1)  # Thursday
    res = _run(prefs=_prefs(blackout_dates=frozenset({blackout})))
    dates = {i.scheduled_date for i in res.items}
    assert blackout not in dates                       # blackout skipped
    # Sundays have 0 budget → never scheduled.
    assert not any(d.weekday() == 6 for d in dates)


def test_max_session_caps_est_minutes():
    res = _run(prefs=_prefs(max_session_minutes=10))
    assert res.items
    assert all(i.est_minutes <= 10 for i in res.items)


def test_spaced_review_due_dates():
    # A ≥Can-mark concept, last practiced long ago, conf 3 (~3d interval) → a
    # REVIEW is due immediately (placed today).
    prog = {
        "aura-psych": S.ConceptProgressView(stages.CAN_MARK, 3, 5, WED - timedelta(days=30)),
    }
    res = _run(concept_progress=prog)
    reviews = [i for i in res.items if i.activity == PlanActivity.REVIEW and i.concept_id == "f1"]
    assert reviews and min(i.scheduled_date for i in reviews) == WED

    # Freshly practised today at conf 5 (~21d) → not due within a 5-day horizon.
    prog["aura-psych"] = S.ConceptProgressView(stages.CAN_MARK, 5, 5, WED)
    res2 = _run(concept_progress=prog, horizon=5)
    assert not [i for i in res2.items if i.activity == PlanActivity.REVIEW and i.concept_id == "f1"]


def test_slippage_carry_over_requeued_today():
    past = [
        S.PastItemView(WED - timedelta(days=2), PlanActivity.LEARN, PlanItemStatus.PENDING,
                       concept_id="f1", est_minutes=25),
        S.PastItemView(WED - timedelta(days=1), PlanActivity.DRILL, PlanItemStatus.PENDING,
                       drill_ref="aura D1-a", target_qty=10, target_unit="reps", est_minutes=20),
    ]
    res = _run(past=past)
    assert res.carried_over == 2
    assert res.days_behind == 2
    carried = [i for i in res.items if i.carried_over and i.scheduled_date == WED]
    assert {i.concept_id or i.drill_ref for i in carried} == {"f1", "aura D1-a"}


def test_projection_pacing_only():
    # With the foundation met, A1 work is scheduled; projected_go_live is set and
    # on_pace compares (pacing only — it never changes what is scheduled).
    prog = {"aura-psych": S.ConceptProgressView(stages.CAN_MARK, 3, 5, WED)}
    early = _run(concept_progress=prog, prefs=_prefs(target_go_live_date=WED + timedelta(days=365)))
    late = _run(concept_progress=prog, prefs=_prefs(target_go_live_date=WED))
    assert early.projected_go_live is not None
    assert early.on_pace is True
    assert late.on_pace is False
    # Same schedule regardless of the target date (pacing is not a gate).
    assert _sig(early) == _sig(late)
