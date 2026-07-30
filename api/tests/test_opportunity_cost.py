"""Unit tests for the pure missed-trade opportunity-cost math (Phase 6b).

NO database — hand-built fixtures with BY-HAND answers, mirroring
test_analytics.py's expectancy tests. The point of the analytic is one number in
R, in both directions: what hesitation cost you, and what standing down saved.
"""

from app.services import opportunity_cost as oc


def _m(miss_type, r, *, model="london", tags=()):
    return oc.MissView(miss_type=miss_type, entry_model=model, hypothetical_r=r,
                       hesitation_tags=tuple(tags))


# ---------------------------------------------------------------------------
# Totals — computed by hand
# ---------------------------------------------------------------------------

def test_totals_by_hand():
    # +2.0 and +1.5 missed winners; -1.0 and -0.5 missed losers; one breakeven.
    # forgone = 3.5 · saved = 1.5 · net = +2.0 · avg = 2.0/5 = 0.4
    misses = [
        _m("hesitated", 2.0), _m("hesitated", 1.5),
        _m("canceled", -1.0), _m("canceled", -0.5),
        _m("almost_took", 0.0),
    ]
    t = oc.compute(misses).total
    assert t.logged == 5 and t.resolved == 5
    assert t.would_win == 2 and t.would_lose == 2 and t.would_breakeven == 1
    assert t.forgone_r == 3.5
    assert t.saved_r == 1.5
    assert t.net_r == 2.0
    assert t.avg_r == 0.4


def test_negative_net_reads_as_protective_dante_case():
    """Dante's finding: the canceled orders would have LOST. Net R must come out
    NEGATIVE — pulling them was protective — and the sign is never abs()'d away."""
    misses = [_m("canceled", -2.0), _m("canceled", -1.0), _m("canceled", 0.5)]
    result = oc.compute(misses)
    assert result.total.net_r == -2.5
    assert result.total.saved_r == 3.0 and result.total.forgone_r == 0.5
    canceled = {b.key: b for b in result.by_miss_type}["canceled"]
    assert canceled.net_r == -2.5


def test_unresolved_misses_are_logged_but_never_summed():
    misses = [_m("hesitated", 2.0), _m("hesitated", None), _m("almost_took", None)]
    t = oc.compute(misses).total
    assert t.logged == 3 and t.resolved == 1
    assert t.net_r == 2.0 and t.avg_r == 2.0  # the two unresolved contribute nothing


def test_empty_log_is_all_none_never_zero_edge():
    t = oc.compute([]).total
    assert t.logged == 0 and t.resolved == 0
    assert t.forgone_r is None and t.saved_r is None and t.net_r is None and t.avg_r is None


# ---------------------------------------------------------------------------
# Slices
# ---------------------------------------------------------------------------

def test_split_by_miss_type():
    misses = [
        _m("canceled", -1.0), _m("canceled", -1.0),
        _m("hesitated", 3.0),
        _m("almost_took", 0.5),
    ]
    by_type = {b.key: b for b in oc.compute(misses).by_miss_type}
    assert by_type["canceled"].logged == 2 and by_type["canceled"].net_r == -2.0
    assert by_type["hesitated"].net_r == 3.0
    assert by_type["almost_took"].net_r == 0.5
    # Ordered by |net R| desc → hesitated (3.0), canceled (2.0), almost_took (0.5)
    assert [b.key for b in oc.compute(misses).by_miss_type] == [
        "hesitated", "canceled", "almost_took"
    ]


def test_split_by_hesitation_tag_ranks_the_recurring_one_first():
    misses = [
        _m("canceled", 1.0, tags=["pulled_on_spike", "size_fear"]),
        _m("canceled", 2.0, tags=["pulled_on_spike"]),
        _m("hesitated", 0.5, tags=["distracted"]),
    ]
    tags = oc.compute(misses).by_hesitation_tag
    assert [t.key for t in tags][0] == "pulled_on_spike"  # most frequent first
    top = tags[0]
    assert top.logged == 2 and top.net_r == 3.0
    # A miss with two tags counts in BOTH slices (they are not a partition).
    assert {t.key for t in tags} == {"pulled_on_spike", "size_fear", "distracted"}


def test_split_by_entry_model():
    misses = [_m("hesitated", 2.0, model="london"), _m("canceled", -1.0, model="daily_bias")]
    by_model = {b.key: b for b in oc.compute(misses).by_entry_model}
    assert by_model["london"].net_r == 2.0
    assert by_model["daily_bias"].net_r == -1.0


def test_deterministic_ordering():
    misses = [_m("hesitated", 1.0, tags=["a"]), _m("canceled", -1.0, tags=["b"])]
    a, b = oc.compute(misses), oc.compute(misses)
    assert [x.key for x in a.by_miss_type] == [x.key for x in b.by_miss_type]
    assert [x.key for x in a.by_hesitation_tag] == [x.key for x in b.by_hesitation_tag]


def test_net_equals_forgone_minus_saved_identity():
    misses = [_m("hesitated", 2.25), _m("canceled", -0.75), _m("almost_took", 1.5)]
    t = oc.compute(misses).total
    assert round(t.forgone_r - t.saved_r, 2) == t.net_r
