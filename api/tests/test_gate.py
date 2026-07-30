"""Pure unit tests for the Readiness-to-Live Gate logic (Phase 5g) — NO DB.

app/services/gate.py is DB-agnostic, so the verdict is pinned here against
hand-built fixtures with known answers (mirroring test_scheduler.py and
test_analytics.py). This is the evidence-gated core of the phase: the gate's job
is to be RIGHT about "cleared to live?", and to fail closed when it cannot be.

The (b) numbers are produced by running the SHIPPED 5f expectancy service over
hand-built trades — so these tests also pin the reuse contract between the two
pure services rather than re-deriving expectancy here.
"""

from app.models.enums import EntryModel
from app.services import gate
from app.services.expectancy import TradeR, compute_groups

BACKTESTED, LIVE_READY, CAN_MARK = gate.BACKTESTED, gate.LIVE_READY, gate.CAN_MARK
ALL_ATTESTED = dict.fromkeys(gate.BEHAVIOURAL_KEYS, True)

LONDON_SLUG = "u3-2d-london"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _concepts(extra: list[gate.ConceptGateView] | None = None) -> list[gate.ConceptGateView]:
    """Two unified core concepts + the London entry-model concept. Small on
    purpose — the real curriculum has 10 cores; the rule is what's under test."""
    base = [
        gate.ConceptGateView(
            slug="u1-1", track="unified", title="Liquidity & draw", is_core=True,
            watch_only=False, code="U1.1", u_stage="U1",
        ),
        gate.ConceptGateView(
            slug="u1-2", track="unified", title="Range & premium/discount", is_core=True,
            watch_only=False, code="U1.2", u_stage="U1",
        ),
        gate.ConceptGateView(
            slug=LONDON_SLUG, track="unified", title="London model", is_core=False,
            watch_only=False, code="U3.2d", u_stage="U3",
        ),
    ]
    return base + (extra or [])


def _ladder(**over) -> dict[str, int | None]:
    """Everything at the bar by default: cores Backtested, London Live-ready."""
    d = {"u1-1": BACKTESTED, "u1-2": BACKTESTED, LONDON_SLUG: LIVE_READY}
    d.update(over)
    return d


def _trades(wins: int, losses: int, *, win_r=2.0, loss_r=-1.0, rr=2.0, model="london", mode="backtest"):
    return [TradeR(model, mode, win_r, rr) for _ in range(wins)] + [
        TradeR(model, mode, loss_r, rr) for _ in range(losses)
    ]


def _good_trades(model="london"):
    """50 closed backtest trades: win 60% at +2R / -1R, planned R:R 2 →
    expectancy +0.80R, break-even 33% — comfortably clear on (b)."""
    return _trades(30, 20, model=model)


def _run(*, concepts=None, ladder=None, trades=None, attested=None, credit_track=None,
         models=("london",)) -> gate.ModelReadiness:
    result = gate.compute_readiness(
        concepts=_concepts() if concepts is None else concepts,
        ladder=_ladder() if ladder is None else ladder,
        groups=compute_groups(_good_trades() if trades is None else trades),
        attested=ALL_ATTESTED if attested is None else attested,
        credit_track=credit_track,
        models=models,
    )
    return result.models[0]


def _keys(m: gate.ModelReadiness, source: str, met: bool | None = None) -> list[str]:
    return [
        r.key for r in m.requirements
        if r.source == source and (met is None or r.met is met)
    ]


# ---------------------------------------------------------------------------
# The cleared case — every source satisfied
# ---------------------------------------------------------------------------

def test_fully_satisfied_model_is_cleared():
    m = _run()
    assert m.cleared is True
    assert (m.concepts_met, m.evidence_met, m.behaviour_met) == (True, True, True)
    assert m.blocking == []
    # (b) headlines come straight from the 5f service.
    assert m.backtest_n == 50
    assert m.backtest_expectancy == 0.8
    assert m.backtest_win_rate == 0.6
    assert m.backtest_break_even == 0.3333
    # README's "ideally ≥100" is a stretch marker, not a gate: 50 clears.
    assert m.sample_target == 50 and m.sample_stretch == 100 and m.stretch_met is False


# ---------------------------------------------------------------------------
# Flip each of the four inputs → blocked, with the right reason
# ---------------------------------------------------------------------------

def test_core_concept_below_backtested_blocks():
    m = _run(ladder=_ladder(**{"u1-2": CAN_MARK}))
    assert m.cleared is False
    assert m.concepts_met is False
    assert (m.evidence_met, m.behaviour_met) == (True, True)
    assert _keys(m, "concepts", met=False) == ["a1:u1-2"]
    assert "U1.2" in m.blocking[0]
    req = next(r for r in m.requirements if r.key == "a1:u1-2")
    assert req.required_ladder == BACKTESTED and req.actual_ladder == CAN_MARK
    assert "needs Backtested" in (req.detail or "")


def test_untracked_core_concept_blocks():
    """A concept with no progress row at all reads as not started, not as met."""
    m = _run(ladder={LONDON_SLUG: LIVE_READY})
    assert m.cleared is False and m.concepts_met is False
    assert sorted(_keys(m, "concepts", met=False)) == ["a1:u1-1", "a1:u1-2"]


def test_load_bearing_model_concept_must_be_live_ready():
    """Backtested is enough for a core primitive but NOT for the model you are
    about to trade live — its own concept must reach Live-ready."""
    m = _run(ladder=_ladder(**{LONDON_SLUG: BACKTESTED}))
    assert m.cleared is False and m.concepts_met is False
    assert _keys(m, "concepts", met=False) == [f"a2:{LONDON_SLUG}"]


def test_sample_below_target_blocks():
    m = _run(trades=_trades(29, 20))  # n=49
    assert m.cleared is False and m.evidence_met is False
    assert m.backtest_n == 49
    assert _keys(m, "evidence", met=False) == ["b1:london"]
    assert any("49/50 closed backtest trades" in b for b in m.blocking)


def test_negative_expectancy_blocks():
    m = _run(trades=_trades(10, 40))  # win 20% at +2R / -1R → −0.40R
    assert m.cleared is False and m.evidence_met is False
    assert m.backtest_expectancy == -0.4
    unmet = _keys(m, "evidence", met=False)
    assert "b2:london" in unmet
    assert any("must be positive" in (r.detail or "") for r in m.requirements if r.key == "b2:london")


def test_positive_expectancy_below_break_even_still_blocks():
    """A win rate without its R:R is meaningless — 30% at +3R/-1R is +0.20R but
    sits under the 33% break-even for a planned 2:1, so (b) is not satisfied."""
    m = _run(trades=_trades(15, 35, win_r=3.0, loss_r=-1.0, rr=2.0))
    assert m.backtest_n == 50
    assert m.backtest_expectancy == 0.2          # positive…
    assert m.backtest_win_rate == 0.3            # …but under break-even
    assert m.backtest_break_even == 0.3333
    assert m.cleared is False and m.evidence_met is False
    assert _keys(m, "evidence", met=False) == ["b3:london"]


def test_unknown_rr_blocks_break_even_check():
    trades = [TradeR("london", "backtest", 2.0, None) for _ in range(30)] + [
        TradeR("london", "backtest", -1.0, None) for _ in range(20)
    ]
    m = _run(trades=trades)
    assert m.cleared is False
    req = next(r for r in m.requirements if r.key == "b3:london")
    assert req.met is False and "meaningless" in (req.detail or "")


def test_unattested_behaviour_blocks():
    for missing in gate.BEHAVIOURAL_KEYS:
        attested = {k: (k != missing) for k in gate.BEHAVIOURAL_KEYS}
        m = _run(attested=attested)
        assert m.cleared is False, missing
        assert m.behaviour_met is False
        assert (m.concepts_met, m.evidence_met) == (True, True)
        assert _keys(m, "behaviour", met=False) == [f"c:{missing}:london"]
        assert any("behavioural checks not attested" in b for b in m.blocking)


def test_all_four_behavioural_items_are_required():
    m = _run(attested={})
    assert len(_keys(m, "behaviour", met=False)) == 4
    assert m.cleared is False


# ---------------------------------------------------------------------------
# Non-overridability — attestation is an input, never an override
# ---------------------------------------------------------------------------

def test_attesting_everything_cannot_substitute_for_evidence():
    m = _run(trades=[], attested=ALL_ATTESTED)
    assert m.behaviour_met is True
    assert m.evidence_met is False
    assert m.cleared is False
    assert m.backtest_n == 0


def test_attesting_everything_cannot_substitute_for_concepts():
    m = _run(ladder={}, attested=ALL_ATTESTED)
    assert m.behaviour_met is True and m.concepts_met is False and m.cleared is False


def test_cleared_is_exactly_the_conjunction_of_the_three_sources():
    """No fourth input, no override path: the verdict is (a) ∧ (b) ∧ (c)."""
    for ladder, trades, att in [
        (_ladder(), _good_trades(), ALL_ATTESTED),
        (_ladder(**{"u1-1": CAN_MARK}), _good_trades(), ALL_ATTESTED),
        (_ladder(), _trades(1, 1), ALL_ATTESTED),
        (_ladder(), _good_trades(), {}),
    ]:
        m = _run(ladder=ladder, trades=trades, attested=att)
        assert m.cleared == (m.concepts_met and m.evidence_met and m.behaviour_met)


# ---------------------------------------------------------------------------
# Frontier (U5) is never gate-eligible
# ---------------------------------------------------------------------------

def test_frontier_concept_is_never_a_requirement_and_never_credits():
    """A watch-only concept flagged core and cross-linked from a core concept at
    Live-ready must not appear as a requirement NOR satisfy one."""
    frontier = gate.ConceptGateView(
        slug="u5-x", track="unified", title="Frontier thing", is_core=True,
        watch_only=True, code="U5.1", u_stage="U5", tier="Tier 2", label="EMERGING",
    )
    concepts = _concepts([frontier])
    # u1-2 is untracked, but cross-refs the (maxed-out) frontier concept.
    concepts = [
        gate.ConceptGateView(**{**c.__dict__, "cross_refs": ("u5-x",)}) if c.slug == "u1-2" else c
        for c in concepts
    ]
    result = gate.compute_readiness(
        concepts=concepts,
        ladder={"u1-1": BACKTESTED, LONDON_SLUG: LIVE_READY, "u5-x": LIVE_READY},
        groups=compute_groups(_good_trades()),
        attested=ALL_ATTESTED,
        models=("london",),
    )
    m = result.models[0]
    slugs = {r.concept_slug for r in m.requirements}
    assert "u5-x" not in slugs                      # never a requirement
    assert _keys(m, "concepts", met=False) == ["a1:u1-2"]  # never supplies credit
    assert m.cleared is False
    # …but it IS surfaced as explicitly never-eligible.
    assert [f.slug for f in result.frontier] == ["u5-x"]
    assert result.frontier[0].label == "EMERGING"


# ---------------------------------------------------------------------------
# Cross-track credit + the credit_track restriction (may only tighten)
# ---------------------------------------------------------------------------

def _with_aura_equivalent(aura_ladder: int):
    aura = gate.ConceptGateView(
        slug="aura-ranges", track="aura", title="Ranges", is_core=True, watch_only=False,
    )
    concepts = [
        gate.ConceptGateView(**{**c.__dict__, "cross_refs": ("aura-ranges",)})
        if c.slug == "u1-2" else c
        for c in _concepts([aura])
    ]
    ladder = {"u1-1": BACKTESTED, LONDON_SLUG: LIVE_READY, "aura-ranges": aura_ladder}
    return concepts, ladder


def test_cross_track_equivalent_supplies_credit():
    """Studying the same primitive on the Aura track is real evidence for it."""
    concepts, ladder = _with_aura_equivalent(BACKTESTED)
    m = _run(concepts=concepts, ladder=ladder)
    req = next(r for r in m.requirements if r.key == "a1:u1-2")
    assert req.met is True
    assert (req.credited_slug, req.credited_track) == ("aura-ranges", "aura")
    assert "via Ranges (aura)" in (req.detail or "")
    assert m.cleared is True


def test_cross_track_credit_still_respects_the_bar():
    concepts, ladder = _with_aura_equivalent(CAN_MARK)
    m = _run(concepts=concepts, ladder=ladder)
    assert next(r for r in m.requirements if r.key == "a1:u1-2").met is False
    assert m.cleared is False


def test_credit_track_can_only_tighten():
    concepts, ladder = _with_aura_equivalent(BACKTESTED)
    assert _run(concepts=concepts, ladder=ladder).cleared is True
    # Restricting credit to the unified track drops the aura evidence → blocked.
    tightened = _run(concepts=concepts, ladder=ladder, credit_track="unified")
    assert tightened.cleared is False
    assert _keys(tightened, "concepts", met=False) == ["a1:u1-2"]
    # …and restricting to aura drops the unified-only evidence → also blocked.
    aura_only = _run(concepts=concepts, ladder=ladder, credit_track="aura")
    assert aura_only.cleared is False
    assert "a1:u1-1" in _keys(aura_only, "concepts", met=False)


# ---------------------------------------------------------------------------
# Model coverage + fail-closed behaviour
# ---------------------------------------------------------------------------

def test_all_models_matches_the_entry_model_enum():
    """Drift guard: every journal-able model gets a verdict, and no phantom one."""
    assert set(gate.ALL_MODELS) == {m.value for m in EntryModel}
    assert len(gate.ALL_MODELS) == 8


def test_unified_model_requires_all_seven_entry_models_live_ready():
    """The unified flow routes into every model, so it carries the hardest bar."""
    concepts = _concepts([
        gate.ConceptGateView(
            slug=s, track="unified", title=s, is_core=False, watch_only=False, u_stage="U3",
        )
        for slugs in gate.ENTRY_MODEL_CONCEPTS.values() for s in slugs if s != LONDON_SLUG
    ])
    all_seven = {s for slugs in gate.ENTRY_MODEL_CONCEPTS.values() for s in slugs}
    result = gate.compute_readiness(
        concepts=concepts,
        ladder={**_ladder(), **dict.fromkeys(all_seven, LIVE_READY)},
        groups=compute_groups(_good_trades(model="unified")),
        attested=ALL_ATTESTED,
        models=("unified",),
    )
    m = result.models[0]
    assert {r.concept_slug for r in m.requirements if r.key.startswith("a2:")} == all_seven
    assert m.cleared is True
    # One of the seven short of Live-ready blocks the unified flow.
    blocked = gate.compute_readiness(
        concepts=concepts,
        ladder={**_ladder(), **dict.fromkeys(all_seven, LIVE_READY), LONDON_SLUG: BACKTESTED},
        groups=compute_groups(_good_trades(model="unified")),
        attested=ALL_ATTESTED,
        models=("unified",),
    ).models[0]
    assert blocked.cleared is False


def test_missing_curriculum_concept_never_clears_vacuously():
    """A seed gap must fail closed, not silently drop the requirement."""
    concepts = [c for c in _concepts() if c.slug != LONDON_SLUG]
    m = _run(concepts=concepts, ladder=_ladder())
    assert m.cleared is False
    req = next(r for r in m.requirements if r.key == f"a2:{LONDON_SLUG}")
    assert req.met is False and "seed_concepts" in (req.detail or "")


def test_empty_curriculum_never_clears_vacuously():
    m = _run(concepts=[], ladder={})
    assert m.cleared is False and m.concepts_met is False
    assert "a1:unseeded" in _keys(m, "concepts", met=False)


def test_every_model_is_reported_and_defaults_to_blocked():
    result = gate.compute_readiness(
        concepts=_concepts(), ladder={}, groups=[], attested={},
    )
    assert [m.entry_model for m in result.models] == list(gate.ALL_MODELS)
    assert all(not m.cleared for m in result.models)
    assert result.any_cleared is False


def test_live_activity_is_reported_but_never_gates():
    """A losing live record is shown for honesty; the gate reads BACKTEST only."""
    trades = _good_trades() + _trades(0, 5, mode="live")
    m = _run(trades=trades)
    assert m.live_n == 5 and m.live_expectancy == -1.0
    assert m.cleared is True  # live losses do not block; backtest evidence governs
    assert all(r.source != "evidence" or "live" not in r.label.lower() for r in m.requirements)


def test_attestations_and_corroboration_are_returned():
    result = gate.compute_readiness(
        concepts=_concepts(), ladder=_ladder(), groups=[],
        attested={"journaling_habit": True},
        notes={"journaling_habit": "Notion weekly review"},
        corroboration=gate.Corroboration(entries_logged=12, journaling_days=6),
    )
    by_item = {a.item: a for a in result.attestations}
    assert set(by_item) == set(gate.BEHAVIOURAL_KEYS)
    assert by_item["journaling_habit"].attested is True
    assert by_item["journaling_habit"].note == "Notion weekly review"
    assert by_item["risk_precommitted"].attested is False
    assert result.corroboration.entries_logged == 12
