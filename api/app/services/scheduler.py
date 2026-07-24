"""Study-Planner scheduling engine (Phase 5e-2) — DETERMINISTIC, gate-aware,
retention-aware. COMPUTES the schedule; it NEVER restates or forks the
curriculum (concepts, drill_refs, freetext rep targets, and the learning-path
stage gates are consumed/linked, not duplicated).

`schedule(...)` is a PURE function: same inputs → identical plan (strict
ordering, no randomness, no clock reads). It is DB-agnostic — it operates on the
plain view dataclasses below, so it is unit-testable with NO database. The
planner router (`app/routers/planner.py`) loads the ORM rows, projects them into
these views, calls `schedule`, then materializes / projects the result.

Multi-track reconciliation (5e-1b): the planner schedules ONE chosen track
(`prefs.active_track` ∈ aura|ict_course|unified). Unlock reuses the generalized
`stages.compute_stages(track, stage_metas, concepts, progress)`; the backlog
iterates THAT track's concepts (stage_order, sort_order) + their drill_refs.
Because `compute_stages` needs the track's stage metadata, `schedule` takes an
extra `stage_metas` argument beyond the design's original signature
(`schedule(today, prefs, concepts, drills, concept_progress, drill_progress,
past_items)`) — the design predates multi-track and is reconciled here.

Pipeline (learning-platform.md §Scheduling algorithm):
  1. Unlock            — highest unlocked stage via compute_stages; locked
                         stages are NEVER scheduled.
  2. Backlog           — per schedulable concept: untracked → Learn; each drill
                         below its rep target → Drill; watch_only (U5) → Observe
                         (capped at Can-mark); foundation (stage_order 0) →
                         recurring daily Habit; concept-less evidence stage →
                         a single Backtest placeholder.
  3. Rep-target parse  — reuse rep_targets.parse/meets (never invent a target).
  4. Spaced review     — MANDATORY (no off switch): ≥Can-mark concepts get a
                         Leitner due date from confidence + last_practiced.
  5. Daily packing     — tz-aware date walk; skip blackout + 0-budget days;
                         fill order habits → due reviews → backlog; day-based
                         drills get one slot/day; blocks ≤ max_session_minutes;
                         overflow rolls to the next eligible day.
  6. Projection / ETA  — pacing-only vs target_go_live_date; NEVER gates.
  7. Slippage / carry  — past pending backlog re-queued at the FRONT of today;
                         days-behind surfaced (accountability), never hidden.

North star — discipline & accountability BY DESIGN: prescriptive ordered plan;
locked stages never scheduled; rep targets enforced; spaced review mandatory;
U0 habits recur daily; missed work re-queued; frontier watch-only; the target
date is pacing-only.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Hashable

from app.models.enums import PlanActivity, PlanItemStatus
from app.services import rep_targets, stages

CAN_MARK = stages.CAN_MARK

# Estimated minutes per activity type (deterministic; the packer uses these).
# Each is capped at `max_session_minutes` at emit time so no item exceeds a block.
EST_MINUTES: dict[PlanActivity, int] = {
    PlanActivity.LEARN: 25,
    PlanActivity.DRILL: 20,
    PlanActivity.REVIEW: 10,
    PlanActivity.OBSERVE: 20,
    PlanActivity.HABIT: 10,
    PlanActivity.BACKTEST: 45,
}

# Leitner-style spaced-review interval by confidence (days): higher confidence →
# longer interval (conf 3 ≈ 3d, 4 ≈ 7d, 5 ≈ 21d). mastery/README §confidence.
REVIEW_INTERVAL_DAYS: dict[int, int] = {1: 1, 2: 2, 3: 3, 4: 7, 5: 21}
_DEFAULT_REVIEW_DAYS = 3  # ladder ≥ Can-mark but confidence unset → review soon

# Backlog activities eligible for slippage carry-over (habits recur daily and
# reviews re-become-due on their own, so they are not re-queued as carry-over).
_CARRYABLE = {PlanActivity.LEARN, PlanActivity.DRILL, PlanActivity.OBSERVE, PlanActivity.BACKTEST}


# ---------------------------------------------------------------------------
# Input views (DB-agnostic — the router projects ORM rows into these)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrefsView:
    """Availability + pacing prefs. `weekday_minutes` is Mon..Sun (7 ints,
    indexed by `date.weekday()`); 0 = day off. `target_go_live_date` is
    pacing-only. `active_track` names the track to schedule."""

    weekday_minutes: tuple[int, int, int, int, int, int, int]
    max_session_minutes: int
    active_track: str
    blackout_dates: frozenset[date] = frozenset()
    target_go_live_date: date | None = None
    plan_version: int = 1
    timezone: str = "UTC"


@dataclass(frozen=True)
class ConceptView:
    """One gradable concept on the scheduled track (superset of the fields the
    exit-bar service reads — adds id/sort_order/content_slug/drill_refs)."""

    concept_id: Hashable
    slug: str
    stage_code: str | None
    stage_order: int | None
    sort_order: int
    title: str
    is_core: bool
    watch_only: bool
    rep_target: str | None
    content_slug: str | None
    drill_refs: tuple[str, ...] = ()
    code: str | None = None
    u_stage: str | None = None


@dataclass(frozen=True)
class DrillView:
    drill_ref: str
    stage_code: str | None
    rep_target: str | None
    sort_order: int
    concept_slugs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConceptProgressView:
    ladder_stage: int | None
    confidence: int | None
    reps: int
    last_practiced: date | None = None


@dataclass(frozen=True)
class DrillProgressView:
    reps: int
    hand_done: bool = False
    tool_done: bool = False
    last_practiced: date | None = None


@dataclass(frozen=True)
class PastItemView:
    """A previously-frozen plan_item, for slippage carry-over."""

    scheduled_date: date
    activity: PlanActivity
    status: PlanItemStatus
    concept_id: Hashable | None = None
    drill_ref: str | None = None
    drill_variant: str | None = None
    target_qty: int | None = None
    target_unit: str | None = None
    est_minutes: int = 0


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


@dataclass
class PlanItemSpec:
    """One computed, dated plan item. `slot_key` mirrors the DB partial-unique
    index tuple (activity, concept_id, drill_ref, drill_variant) so the router
    materializes idempotently and the packer de-duplicates."""

    scheduled_date: date
    activity: PlanActivity
    concept_id: Hashable | None = None
    drill_ref: str | None = None
    drill_variant: str | None = None
    target_qty: int | None = None
    target_unit: str | None = None
    est_minutes: int = 0
    sort_order: int = 0
    carried_over: bool = False

    @property
    def slot_key(self) -> tuple:
        return (self.activity, self.concept_id, self.drill_ref, self.drill_variant)


@dataclass
class ScheduleResult:
    items: list[PlanItemSpec]                       # whole horizon, dated & ordered
    projected_clear: dict[str, date] = field(default_factory=dict)  # stage_code → date
    projected_go_live: date | None = None
    on_pace: bool | None = None
    days_behind: int = 0
    carried_over: int = 0
    unplaced: list[PlanItemSpec] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Backlog task (undated) — packed into days during step 5
# ---------------------------------------------------------------------------


@dataclass
class _Task:
    activity: PlanActivity
    est_minutes: int
    concept_id: Hashable | None = None
    drill_ref: str | None = None
    drill_variant: str | None = None
    target_qty: int | None = None
    target_unit: str | None = None
    stage_order: int = 0
    sort_order: int = 0
    carried_over: bool = False

    @property
    def slot_key(self) -> tuple:
        return (self.activity, self.concept_id, self.drill_ref, self.drill_variant)


def _est(activity: PlanActivity, max_session: int) -> int:
    """Estimated minutes for an activity, capped at one session block."""
    return min(EST_MINUTES[activity], max_session)


# ---------------------------------------------------------------------------
# The scheduler
# ---------------------------------------------------------------------------


def schedule(
    today: date,
    prefs: PrefsView,
    stage_metas: list[stages.StageMeta],
    concepts: list[ConceptView],
    drills: list[DrillView],
    concept_progress: dict[str, ConceptProgressView],
    drill_progress: dict[str, DrillProgressView],
    past_items: list[PastItemView],
    *,
    horizon_days: int = 120,
) -> ScheduleResult:
    max_session = max(1, prefs.max_session_minutes)
    drill_by_ref = {d.drill_ref: d for d in drills}

    # --- 1. Unlock ---------------------------------------------------------
    cviews = [
        stages.ConceptView(
            slug=c.slug, code=c.code, stage_code=c.stage_code, title=c.title,
            is_core=c.is_core, watch_only=c.watch_only, rep_target=c.rep_target,
            u_stage=c.u_stage,
        )
        for c in concepts
    ]
    sprog = {
        slug: stages.ProgressView(p.ladder_stage, p.confidence, p.reps)
        for slug, p in concept_progress.items()
    }
    statuses = stages.compute_stages(prefs.active_track, stage_metas, cviews, sprog)
    status_by_code = {s.stage_code: s for s in statuses}
    schedulable = {s.stage_code for s in statuses if not s.locked}

    # --- 2. Backlog + foundation/concept-less collection -------------------
    ordered = sorted(concepts, key=lambda c: (c.stage_order or 0, c.sort_order))
    backlog: list[_Task] = []
    foundation_concepts: list[ConceptView] = []
    seq = 0

    for c in ordered:
        if c.stage_code not in schedulable:
            continue  # locked stage — NEVER scheduled
        st = status_by_code.get(c.stage_code)
        pg = concept_progress.get(c.slug)
        reached = pg is not None and pg.ladder_stage is not None and pg.ladder_stage >= CAN_MARK

        # Frontier (watch_only / U5): observe-only, capped at Can-mark. Never learn/drill.
        if c.watch_only:
            if not reached:
                backlog.append(_Task(
                    PlanActivity.OBSERVE, _est(PlanActivity.OBSERVE, max_session),
                    concept_id=c.concept_id, stage_order=c.stage_order or 0, sort_order=seq,
                ))
                seq += 1
            continue

        # Foundation stage (psychology/discipline): the concept still earns its
        # one-time Learn/Drill backlog (below), AND a recurring daily Habit (the
        # discipline overlay, emitted during packing until the gate holds).
        if st is not None and st.stage_order == 0:
            foundation_concepts.append(c)

        # Learn (if untracked) + its Drills (each below its parsed rep target).
        if pg is None or pg.ladder_stage is None:
            backlog.append(_Task(
                PlanActivity.LEARN, _est(PlanActivity.LEARN, max_session),
                concept_id=c.concept_id, stage_order=c.stage_order or 0, sort_order=seq,
            ))
            seq += 1

        for ref in (c.drill_refs or ()):
            d = drill_by_ref.get(ref)
            if d is None:
                continue  # orphan ref (faithful wiki asymmetry) — nothing to schedule
            tgt = rep_targets.parse(d.rep_target)
            done = drill_progress[ref].reps if ref in drill_progress else 0
            est = _est(PlanActivity.DRILL, max_session)
            if tgt.has_floor:
                remaining = (tgt.count or 0) - done
                if remaining <= 0:
                    continue  # rep target already met
                if tgt.kind == "reps":
                    # count-y: one practice task carrying the remaining reps.
                    backlog.append(_Task(
                        PlanActivity.DRILL, est, drill_ref=ref, target_qty=remaining,
                        target_unit="reps", stage_order=c.stage_order or 0, sort_order=seq,
                    ))
                    seq += 1
                else:
                    # longitudinal (days/sessions): one session PER DAY, spread out.
                    for _ in range(remaining):
                        backlog.append(_Task(
                            PlanActivity.DRILL, est, drill_ref=ref, target_qty=1,
                            target_unit=tgt.kind, stage_order=c.stage_order or 0, sort_order=seq,
                        ))
                        seq += 1
            elif done == 0:
                # qualitative/habit target (no numeric floor) — practise once.
                backlog.append(_Task(
                    PlanActivity.DRILL, est, drill_ref=ref, target_unit=tgt.kind,
                    stage_order=c.stage_order or 0, sort_order=seq,
                ))
                seq += 1

    # Concept-less evidence stage (backtest/journal): the LOWEST unlocked such
    # stage gets a single Backtest placeholder (gated behind the concept work;
    # only one to keep the plan focused and the null-ref slot key unambiguous).
    for st in sorted(statuses, key=lambda s: s.stage_order):
        if st.stage_code in schedulable and st.total == 0:
            backlog.append(_Task(
                PlanActivity.BACKTEST, _est(PlanActivity.BACKTEST, max_session),
                stage_order=st.stage_order, sort_order=seq,
            ))
            seq += 1
            break

    # --- 3/4. Spaced review (mandatory) ------------------------------------
    # Every concept at ladder ≥ Can-mark earns a Leitner-interval review.
    reviews: list[tuple[date, int, _Task]] = []  # (desired_date, sort_key, task)
    for c in ordered:
        if c.watch_only:
            continue
        pg = concept_progress.get(c.slug)
        if pg is None or pg.ladder_stage is None or pg.ladder_stage < CAN_MARK:
            continue
        interval = REVIEW_INTERVAL_DAYS.get(pg.confidence or 0, _DEFAULT_REVIEW_DAYS)
        due = (pg.last_practiced + timedelta(days=interval)) if pg.last_practiced else today
        desired = max(due, today)
        if desired > today + timedelta(days=horizon_days):
            continue  # not due within the horizon
        reviews.append((desired, c.sort_order, _Task(
            PlanActivity.REVIEW, _est(PlanActivity.REVIEW, max_session),
            concept_id=c.concept_id, stage_order=c.stage_order or 0,
        )))
    reviews.sort(key=lambda r: (r[0], r[1]))

    # --- 7. Slippage / carry-over ------------------------------------------
    past_pending = [
        pi for pi in past_items
        if pi.status == PlanItemStatus.PENDING and pi.scheduled_date < today
    ]
    days_behind = len({pi.scheduled_date for pi in past_pending})
    carried_over = len(past_pending)

    carried_tasks: list[_Task] = []
    for pi in past_pending:
        if pi.activity not in _CARRYABLE:
            continue  # habits/reviews regenerate on their own
        carried_tasks.append(_Task(
            pi.activity, pi.est_minutes or _est(pi.activity, max_session),
            concept_id=pi.concept_id, drill_ref=pi.drill_ref, drill_variant=pi.drill_variant,
            target_qty=pi.target_qty, target_unit=pi.target_unit,
            stage_order=-1, sort_order=-1, carried_over=True,
        ))
    # De-dupe: carried tasks jump to the FRONT; drop any normal task with the
    # same slot (it would collide on the partial-unique index anyway).
    carried_keys = {t.slot_key for t in carried_tasks}
    backlog = carried_tasks + [t for t in backlog if t.slot_key not in carried_keys]

    # --- 5. Daily packing --------------------------------------------------
    foundation_met = all(
        status_by_code[c.stage_code].met
        for c in foundation_concepts
        if c.stage_code in status_by_code
    ) if foundation_concepts else True

    placed: list[PlanItemSpec] = []
    queue = deque(backlog)
    review_idx = 0

    for offset in range(horizon_days + 1):
        day = today + timedelta(days=offset)
        wd_minutes = prefs.weekday_minutes[day.weekday()]
        if day in prefs.blackout_dates or wd_minutes <= 0:
            continue  # skip blackout + 0-budget days
        budget = wd_minutes
        day_seq = 0

        # (a) Habits — foundation-stage daily discipline. MANDATORY: emitted
        #     even if they drive the day's budget negative (discipline by design).
        if not foundation_met:
            for fc in foundation_concepts:
                placed.append(PlanItemSpec(
                    day, PlanActivity.HABIT, concept_id=fc.concept_id,
                    est_minutes=_est(PlanActivity.HABIT, max_session), sort_order=day_seq,
                ))
                budget -= _est(PlanActivity.HABIT, max_session)
                day_seq += 1

        # (b) Due reviews (retention guardrail) — before backlog.
        while review_idx < len(reviews) and reviews[review_idx][0] <= day:
            _, _, rt = reviews[review_idx]
            if budget < rt.est_minutes:
                break  # roll remaining due reviews to the next eligible day
            placed.append(PlanItemSpec(
                day, rt.activity, concept_id=rt.concept_id,
                est_minutes=rt.est_minutes, sort_order=day_seq,
            ))
            budget -= rt.est_minutes
            day_seq += 1
            review_idx += 1

        # (c/d) Backlog in curriculum order; day-based drills one slot/day;
        #       stop at the first item that overflows the budget (roll the rest).
        if budget > 0 and queue:
            drills_today: set[str] = set()
            deferred: deque[_Task] = deque()
            stopped = False
            while queue:
                t = queue.popleft()
                if stopped:
                    deferred.append(t)
                    continue
                if t.drill_ref is not None and t.drill_ref in drills_today:
                    deferred.append(t)  # one slot per drill per day
                    continue
                if budget >= t.est_minutes:
                    placed.append(PlanItemSpec(
                        day, t.activity, concept_id=t.concept_id, drill_ref=t.drill_ref,
                        drill_variant=t.drill_variant, target_qty=t.target_qty,
                        target_unit=t.target_unit, est_minutes=t.est_minutes,
                        sort_order=day_seq, carried_over=t.carried_over,
                    ))
                    budget -= t.est_minutes
                    day_seq += 1
                    if t.drill_ref is not None:
                        drills_today.add(t.drill_ref)
                else:
                    stopped = True
                    deferred.append(t)
            queue = deferred

    # Anything still queued / any review past the horizon is UNPLACED — surfaced,
    # never silently dropped (accountability).
    unplaced = [
        PlanItemSpec(
            today, t.activity, concept_id=t.concept_id, drill_ref=t.drill_ref,
            drill_variant=t.drill_variant, target_qty=t.target_qty,
            target_unit=t.target_unit, est_minutes=t.est_minutes, carried_over=t.carried_over,
        )
        for t in queue
    ]
    unplaced += [
        PlanItemSpec(today, rt.activity, concept_id=rt.concept_id, est_minutes=rt.est_minutes)
        for _, _, rt in reviews[review_idx:]
    ]

    # --- 6. Projection / ETA (pacing-only — NEVER gates) -------------------
    # Bucket each placed learn/drill item's date by its stage; a stage's
    # projected-clear date is the last date work for it is scheduled.
    concept_stage = {c.concept_id: c.stage_code for c in concepts}
    stage_dates: dict[str, list[date]] = {}
    for it in placed:
        if it.activity == PlanActivity.LEARN:
            sc = concept_stage.get(it.concept_id)
        elif it.activity == PlanActivity.DRILL:
            d = drill_by_ref.get(it.drill_ref) if it.drill_ref else None
            sc = d.stage_code if d else None
        else:
            continue
        if sc is not None:
            stage_dates.setdefault(sc, []).append(it.scheduled_date)

    projected_clear: dict[str, date] = {}
    for st in statuses:
        if st.stage_code not in schedulable or st.total == 0 or st.watch_only or st.stage_order == 0:
            continue
        if st.stage_code in stage_dates:
            projected_clear[st.stage_code] = max(stage_dates[st.stage_code])
        elif st.met:
            projected_clear[st.stage_code] = today  # already cleared, no work needed

    projected_go_live = max(projected_clear.values()) if projected_clear else None
    on_pace: bool | None = None
    if prefs.target_go_live_date is not None and projected_go_live is not None:
        on_pace = projected_go_live <= prefs.target_go_live_date

    return ScheduleResult(
        items=placed,
        projected_clear=projected_clear,
        projected_go_live=projected_go_live,
        on_pace=on_pace,
        days_behind=days_behind,
        carried_over=carried_over,
        unplaced=unplaced,
    )
