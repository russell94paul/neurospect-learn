"""Unit tests for the stage exit-bar service, focused on the Phase 6a wiring.

NO database — `stages.compute_stages` is pure over view dataclasses, so every
case below is a hand-built fixture with a known answer (mirroring test_gate.py
and test_scheduler.py).

The load-bearing assertions the boot prompt's VERIFY step requires:
  * each wired attestation FLIPS with its `gate_attestations` evidence and stays
    unmet without it;
  * each derived (journal / gate-verdict) row flips with its evidence, and encodes
    the bar the learning-path page NAMES — U4 is COMPUTABILITY, A4/M7 are
    sample + positive + above-break-even;
  * THE LOCK CHAIN DOES NOT REGRESS: `locked` (and `auto_met`) are byte-identical
    with and without evidence, for every track and every progress state tried;
  * omitting the bundle reproduces the pre-6a result exactly.
"""

from app.services import expectancy, gate, stages

# --- fixtures ---------------------------------------------------------------

CAN, BT, LR = stages.CAN_MARK, stages.BACKTESTED, stages.LIVE_READY


def _c(slug, stage_code, *, code=None, core=False, watch=False, rep="-", u=None):
    return stages.ConceptView(
        slug=slug, code=code, stage_code=stage_code, title=slug.replace("-", " ").title(),
        is_core=core, watch_only=watch, rep_target=rep, u_stage=u,
    )


def _p(ladder, conf=3, reps=99):
    return stages.ProgressView(ladder, conf, reps)


def _unified_metas():
    return [
        stages.StageMeta("unified", code, i, code)
        for i, code in enumerate(("U0", "U1", "U2", "U3", "U4", "U5", "U6"))
    ]


def _unified_concepts():
    return [
        _c("u0-1-psych", "U0", code="U0.1", u="U0"),
        _c("u1-1-liquidity", "U1", code="U1.1", core=True, rep=">=50 swings", u="U1"),
        _c("u2-2-triad-smt", "U2", code="U2.2", core=True, u="U2"),
        _c("u2-3-sequential-smt", "U2", code="U2.3", core=True, u="U2"),
        _c("u3-1-time", "U3", code="U3.1", core=True, u="U3"),
        _c("u3-2d-london", "U3", code="U3.2d", u="U3"),
        _c("u4-1-risk", "U4", code="U4.1", u="U4"),
        _c("u5-1-frontier", "U5", code="U5.1", watch=True, u="U5"),
    ]


def _aura_metas():
    return [
        stages.StageMeta("aura", code, i, code, gate_text=f"{code} bar")
        for i, code in enumerate(("A0", "A1", "A4", "A5", "A6"))
    ]


def _aura_concepts():
    return [_c("aura-psych", "A0"), _c("aura-swings", "A1", core=True, rep=">=50 swings")]


def _ict_metas():
    return [
        stages.StageMeta("ict_course", code, i, code, gate_text=f"{code} bar")
        for i, code in enumerate(("M0", "M1", "M6", "M7", "M8"))
    ]


def _ict_concepts():
    return [_c("ict-discipline", "M0"), _c("ict-liquidity", "M1", core=True)]


def _bt_group(n, *, expectancy_r, win_rate=None, break_even=None, above=None):
    """A hand-built pooled backtest Group (what expectancy.compute_pooled returns)."""
    return expectancy.Group(
        entry_model=expectancy.POOLED, mode="backtest", logged=n, n=n,
        wins=0, losses=0, breakevens=0, win_rate=win_rate,
        avg_win_r=None, avg_loss_r=None, expectancy=expectancy_r,
        avg_rr_planned=2.0, break_even=break_even, above_break_even=above,
        sample_target=expectancy.SAMPLE_TARGET, sample_met=n >= expectancy.SAMPLE_TARGET,
    )


def _stages(track, metas, concepts, progress=None, evidence=None):
    return {
        s.stage_code: s
        for s in stages.compute_stages(track, metas, concepts, progress or {}, evidence)
    }


def _row(stage, *, attest_item=None, derived=False):
    for r in stage.requirements:
        if attest_item is not None and r.attest_item == attest_item:
            return r
        if attest_item is None and derived and r.derived:
            return r
    raise AssertionError(f"no matching row in {stage.stage_code}: {stage.requirements}")


# ---------------------------------------------------------------------------
# The no-regression guarantee: evidence NEVER moves auto_met or the lock chain
# ---------------------------------------------------------------------------

def _lock_signature(track, metas, concepts, progress, evidence):
    st = _stages(track, metas, concepts, progress, evidence)
    return {c: (s.locked, s.auto_met) for c, s in st.items()}


def test_lock_chain_and_auto_met_identical_with_and_without_evidence():
    """The 6a wiring must not touch the curriculum's lock chain. Checked across
    every track and four progress states, with the richest possible evidence."""
    full = stages.Evidence(
        attested=dict.fromkeys(gate.BEHAVIOURAL_KEYS, True),
        backtest=_bt_group(120, expectancy_r=0.8, win_rate=0.6, break_even=0.33, above=True),
        live_logged=40, journaling_days=90, missed_logged=12,
        cleared_models=("london", "unified"), gate_computed=True,
    )
    cases = [
        ("unified", _unified_metas(), _unified_concepts(), [
            {},
            {"u0-1-psych": _p(CAN)},
            {"u0-1-psych": _p(CAN), "u1-1-liquidity": _p(CAN)},
            {c.slug: _p(LR) for c in _unified_concepts() if not c.watch_only},
        ]),
        ("aura", _aura_metas(), _aura_concepts(), [
            {}, {"aura-psych": _p(CAN)}, {"aura-psych": _p(CAN), "aura-swings": _p(BT)},
        ]),
        ("ict_course", _ict_metas(), _ict_concepts(), [
            {}, {"ict-discipline": _p(CAN)}, {"ict-discipline": _p(CAN), "ict-liquidity": _p(BT)},
        ]),
    ]
    for track, metas, concepts, progresses in cases:
        for prog in progresses:
            bare = _lock_signature(track, metas, concepts, prog, None)
            wired = _lock_signature(track, metas, concepts, prog, full)
            assert bare == wired, f"{track} lock/auto_met moved for {prog}"


def test_no_evidence_leaves_every_wired_row_unmet():
    """Pre-6a behaviour is the `evidence=None` default: nothing can be met."""
    for track, metas, concepts in (
        ("unified", _unified_metas(), _unified_concepts()),
        ("aura", _aura_metas(), _aura_concepts()),
        ("ict_course", _ict_metas(), _ict_concepts()),
    ):
        for s in _stages(track, metas, concepts).values():
            for r in s.requirements:
                if r.attest or r.derived:
                    assert not r.met, f"{track}/{s.stage_code}: {r.label}"


def test_empty_evidence_bundle_equals_omitting_it():
    a = _stages("unified", _unified_metas(), _unified_concepts(), {}, None)
    b = _stages("unified", _unified_metas(), _unified_concepts(), {}, stages.Evidence())
    assert {k: v.requirements for k, v in a.items()} == {k: v.requirements for k, v in b.items()}


# ---------------------------------------------------------------------------
# (c) behavioural bars — wired to the shipped 5g gate_attestations store
# ---------------------------------------------------------------------------

def test_unified_u0_reflects_the_two_gate_attestations_it_names():
    metas, concepts = _unified_metas(), _unified_concepts()
    prog = {"u0-1-psych": _p(CAN)}

    none = _stages("unified", metas, concepts, prog, stages.Evidence())["U0"]
    assert not none.met and none.attest_pending
    assert not _row(none, attest_item="circuit_breaker").met
    assert not _row(none, attest_item="journaling_habit").met

    half = _stages("unified", metas, concepts, prog, stages.Evidence(
        attested={"circuit_breaker": True}))["U0"]
    assert _row(half, attest_item="circuit_breaker").met
    assert not _row(half, attest_item="journaling_habit").met
    assert not half.met and half.attest_pending  # one still missing

    both = _stages("unified", metas, concepts, prog, stages.Evidence(
        attested={"circuit_breaker": True, "journaling_habit": True}))["U0"]
    assert both.met and not both.attest_pending
    assert both.auto_met  # the concept side was already satisfied


def test_attestation_rows_point_at_the_gate_and_carry_no_second_checkbox():
    st = _stages("unified", _unified_metas(), _unified_concepts(), {}, stages.Evidence())
    attest_rows = [r for s in st.values() for r in s.requirements if r.attest]
    assert attest_rows
    for r in attest_rows:
        assert r.link == "/gate" and r.attest_item in gate.BEHAVIOURAL_KEYS
        assert not r.derived


def test_revoking_an_attestation_unmakes_the_bar():
    metas, concepts = _aura_metas(), _aura_concepts()
    on = _stages("aura", metas, concepts, {}, stages.Evidence(
        attested={"sim_track_record": True}))["A5"]
    off = _stages("aura", metas, concepts, {}, stages.Evidence(
        attested={"sim_track_record": False}))["A5"]
    assert on.met and not off.met


def test_ict_m0_maps_onto_both_items_its_bar_names():
    prog = {"ict-discipline": _p(CAN)}
    st = _stages("ict_course", _ict_metas(), _ict_concepts(), prog, stages.Evidence(
        attested={"risk_precommitted": True}))["M0"]
    assert _row(st, attest_item="risk_precommitted").met
    assert not _row(st, attest_item="circuit_breaker").met
    assert not st.met


def test_corroboration_is_shown_but_never_gates():
    """Journal facts appear beside a self-attest (the 5g idiom) and change no verdict."""
    ev_rich = stages.Evidence(journaling_days=90, missed_logged=12)
    ev_bare = stages.Evidence()
    rich = _stages("aura", _aura_metas(), _aura_concepts(), {}, ev_rich)["A6"]
    bare = _stages("aura", _aura_metas(), _aura_concepts(), {}, ev_bare)["A6"]
    assert "90 journaling days" in _row(rich, attest_item="journaling_habit").detail
    assert "12 misses logged" in _row(rich, attest_item="journaling_habit").detail
    assert rich.met is bare.met is False  # corroboration alone satisfies nothing


# ---------------------------------------------------------------------------
# (b) empirical bars — derived from the shipped 5f expectancy service
# ---------------------------------------------------------------------------

def test_u4_expectancy_row_is_computability_not_positivity():
    """The unified U4 page bar is "CAN COMPUTE a trade's expectancy contribution
    in R" — a NEGATIVE expectancy still satisfies it (positivity is A4/M7's bar)."""
    metas, concepts = _unified_metas(), _unified_concepts()

    nothing = _stages("unified", metas, concepts, {}, stages.Evidence())["U4"]
    assert not _row(nothing, derived=True).met

    negative = _stages("unified", metas, concepts, {}, stages.Evidence(
        backtest=_bt_group(3, expectancy_r=-0.4)))["U4"]
    row = _row(negative, derived=True)
    assert row.met and row.derived and not row.attest
    assert "-0.40R" in row.detail and "3 closed backtest trades" in row.detail

    # An empty sample is not computable, even if a group exists.
    empty = _stages("unified", metas, concepts, {}, stages.Evidence(
        backtest=_bt_group(0, expectancy_r=None)))["U4"]
    assert not _row(empty, derived=True).met


def test_a4_backtest_edge_needs_all_three_conditions():
    metas, concepts = _aura_metas(), _aura_concepts()

    def a4(group):
        return _stages("aura", metas, concepts, {}, stages.Evidence(backtest=group))["A4"]

    ok = _bt_group(50, expectancy_r=0.2, win_rate=0.4, break_even=0.3333, above=True)
    assert a4(ok).met

    # sample short
    assert not a4(_bt_group(49, expectancy_r=0.2, win_rate=0.4, break_even=0.3333, above=True)).met
    # expectancy not positive (exactly zero is not > 0)
    assert not a4(_bt_group(50, expectancy_r=0.0, win_rate=0.4, break_even=0.3333, above=True)).met
    assert not a4(_bt_group(50, expectancy_r=-0.1, win_rate=0.3, break_even=0.3333, above=False)).met
    # positive expectancy but win rate BELOW break-even (the 5g edge case)
    assert not a4(_bt_group(50, expectancy_r=0.2, win_rate=0.3, break_even=0.3333, above=False)).met
    # unknown planned R:R → break-even unknowable → unmet, and said so
    unknown = a4(_bt_group(50, expectancy_r=0.2, win_rate=0.4, break_even=None, above=None))
    assert not unknown.met
    assert "no planned R:R" in _row(unknown, derived=True).detail


def test_m7_uses_the_same_bar_as_a4():
    ev = stages.Evidence(
        backtest=_bt_group(50, expectancy_r=0.2, win_rate=0.4, break_even=0.3333, above=True))
    assert _stages("ict_course", _ict_metas(), _ict_concepts(), {}, ev)["M7"].met


def test_sample_target_comes_from_the_shipped_expectancy_service():
    """The ≥50 bar is `expectancy.SAMPLE_TARGET` — not a number invented here."""
    assert stages.Evidence().sample_target == expectancy.SAMPLE_TARGET
    row = _row(_stages("aura", _aura_metas(), _aura_concepts(), {}, stages.Evidence())["A4"],
               derived=True)
    assert f"≥{expectancy.SAMPLE_TARGET} backtest setups" in row.label


# ---------------------------------------------------------------------------
# The unified U6 readiness arc — the shipped 5g verdict, rolled up
# ---------------------------------------------------------------------------

def test_u6_reflects_the_gate_verdict():
    metas, concepts = _unified_metas(), _unified_concepts()

    nothing_cleared = _stages("unified", metas, concepts, {}, stages.Evidence(
        gate_computed=True))["U6"]
    assert not nothing_cleared.met
    assert "no entry model is cleared" in _row(nothing_cleared, derived=True).detail

    cleared = _stages("unified", metas, concepts, {}, stages.Evidence(
        cleared_models=("london",), gate_computed=True))["U6"]
    row = _row(cleared, derived=True)
    assert cleared.met and row.met and row.link == "/gate"
    assert "london" in row.detail


def test_u6_never_guesses_when_the_verdict_was_not_loaded():
    """`gate_computed=False` (e.g. the planner's cheaper bundle) must read unmet
    rather than infer a verdict from a stale/absent input."""
    st = _stages("unified", _unified_metas(), _unified_concepts(), {}, stages.Evidence(
        cleared_models=("london",), gate_computed=False))["U6"]
    assert not st.met


# ---------------------------------------------------------------------------
# Honest un-wired rows + drift guards
# ---------------------------------------------------------------------------

def test_unwired_bar_stays_self_attested_and_says_so():
    """ict_course M6's bar is drill completion; no shipped evidence source covers
    it, so it stays self-attested with an honest note — never a fake threshold."""
    full = stages.Evidence(
        attested=dict.fromkeys(gate.BEHAVIOURAL_KEYS, True),
        backtest=_bt_group(500, expectancy_r=5.0, win_rate=0.9, break_even=0.33, above=True),
        cleared_models=("london",), gate_computed=True,
    )
    m6 = _stages("ict_course", _ict_metas(), _ict_concepts(), {}, full)["M6"]
    assert not m6.met and m6.attest_pending
    row = m6.requirements[0]
    assert row.attest and row.attest_item is None and row.link == "/drills"
    assert "no gate attestation covers this bar" in row.detail


def test_every_mapped_attestation_item_exists_in_the_gate_store():
    """Drift guard: STAGE_ATTESTATIONS may only name real `gate_attestation_item`
    labels, so a /path row can never reference a checkbox /gate does not have."""
    named = {item for items in stages.STAGE_ATTESTATIONS.values() for item, _ in items}
    assert named
    assert named <= set(gate.BEHAVIOURAL_KEYS)


def test_evidence_and_attestation_maps_do_not_double_book_a_row():
    """A stage may carry both a derived row and attestations (U4 does), but the
    same bar must never be graded twice by the same item."""
    for key, items in stages.STAGE_ATTESTATIONS.items():
        names = [i for i, _ in items]
        assert len(names) == len(set(names)), key


def test_met_is_every_requirement_and_auto_met_is_concepts_only():
    metas, concepts = _unified_metas(), _unified_concepts()
    prog = {"u0-1-psych": _p(CAN)}
    st = _stages("unified", metas, concepts, prog, stages.Evidence(
        attested={"circuit_breaker": True, "journaling_habit": True}))["U0"]
    assert st.auto_met and st.met and st.met == all(r.met for r in st.requirements)

    # Concept side incomplete → auto_met False → met False even with both ticks.
    st2 = _stages("unified", metas, concepts, {}, stages.Evidence(
        attested={"circuit_breaker": True, "journaling_habit": True}))["U0"]
    assert not st2.auto_met and not st2.met and not st2.attest_pending
