"""Missed-trade opportunity cost in R (Phase 6b) — "how much is hesitation
costing you?"

PURE and DB-agnostic (no DB, no I/O), like services/expectancy.py and
services/gate.py, so the math is unit-tested against hand-built fixtures with
known answers. The router loads `missed_trades` rows, maps them to `MissView`,
and calls `compute`.

Provenance (concepts/aura/journaling-system, aura-05 — REUSED by reference, not
restated): missed and canceled trades are a distinct, high-value journaling
category. Tom Dante found one of his biggest edges only because a student tracked
his CANCELED orders — he was pulling working orders when price went vertical into
his levels and had no idea until the data showed him.

The point is not record-keeping, it is one number: what your hesitation cost, in
R. So the split matters in BOTH directions —

    forgone_r    Σ hypothetical_r over misses that WOULD have won  (r > 0)
    saved_r      Σ |hypothetical_r| over misses that WOULD have lost (r < 0)
    net_r        Σ hypothetical_r  — positive = hesitation is costing you;
                 NEGATIVE = your instinct to stand down was PROTECTIVE

THIS IS NOT EXPECTANCY AND NEVER FEEDS IT. These trades were never taken: no
figure here is read by services/expectancy.py or services/gate.py, and no
live-eligibility verdict depends on them. Keeping them in their own table (and
their own math) is exactly what stops executed-trade expectancy being diluted.
"""

from dataclasses import dataclass, field

# `hypothetical_outcome` is the user's post-hoc read; the R SIGN is what the math
# uses (mirroring expectancy.py, where win/loss is the sign of `r_multiple`, not
# the `outcome` enum) so the numbers can never disagree with themselves.
UNRESOLVED = "unknown"


@dataclass(frozen=True)
class MissView:
    """The only fields the opportunity-cost math needs from a `missed_trades` row."""

    miss_type: str
    entry_model: str
    hypothetical_r: float | None
    hesitation_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Bucket:
    """One slice of the log (by miss_type, by hesitation tag, or by entry model)."""

    key: str
    logged: int
    resolved: int  # rows carrying a hypothetical R (the only ones in the sums)
    would_win: int
    would_lose: int
    would_breakeven: int
    forgone_r: float | None  # Σ positive R — what NOT taking them cost
    saved_r: float | None  # Σ |negative R| — what standing down protected
    net_r: float | None  # forgone − saved; negative = protective
    avg_r: float | None  # mean hypothetical R over resolved rows


@dataclass
class OpportunityCost:
    total: Bucket
    by_miss_type: list[Bucket] = field(default_factory=list)
    by_hesitation_tag: list[Bucket] = field(default_factory=list)
    by_entry_model: list[Bucket] = field(default_factory=list)


def _round(x: float | None, places: int = 2) -> float | None:
    return None if x is None else round(x, places)


def _bucket(key: str, rows: list[MissView]) -> Bucket:
    resolved = [float(r.hypothetical_r) for r in rows if r.hypothetical_r is not None]
    wins = [r for r in resolved if r > 0]
    losses = [r for r in resolved if r < 0]
    bes = [r for r in resolved if r == 0]
    forgone = sum(wins) if resolved else None
    saved = abs(sum(losses)) if resolved else None
    net = sum(resolved) if resolved else None
    return Bucket(
        key=key,
        logged=len(rows),
        resolved=len(resolved),
        would_win=len(wins),
        would_lose=len(losses),
        would_breakeven=len(bes),
        forgone_r=_round(forgone),
        saved_r=_round(saved),
        net_r=_round(net),
        avg_r=_round(net / len(resolved), 3) if resolved else None,
    )


def compute(misses: list[MissView]) -> OpportunityCost:
    """Total + per-slice opportunity cost. Deterministic ordering: miss types and
    entry models by descending |net R| then key; hesitation tags by descending
    count then key (the recurring hesitation to attack first sorts to the top).

    A miss with no `hypothetical_r` is counted in `logged` but never in the sums —
    an unresolved miss is surfaced honestly, never guessed at.
    """
    total = _bucket("total", misses)

    by_type: dict[str, list[MissView]] = {}
    by_model: dict[str, list[MissView]] = {}
    by_tag: dict[str, list[MissView]] = {}
    for m in misses:
        by_type.setdefault(m.miss_type, []).append(m)
        by_model.setdefault(m.entry_model, []).append(m)
        for tag in m.hesitation_tags or ():
            by_tag.setdefault(tag, []).append(m)

    def by_impact(buckets: list[Bucket]) -> list[Bucket]:
        return sorted(buckets, key=lambda b: (-abs(b.net_r or 0.0), b.key))

    return OpportunityCost(
        total=total,
        by_miss_type=by_impact([_bucket(k, v) for k, v in by_type.items()]),
        by_entry_model=by_impact([_bucket(k, v) for k, v in by_model.items()]),
        by_hesitation_tag=sorted(
            [_bucket(k, v) for k, v in by_tag.items()],
            key=lambda b: (-b.logged, b.key),
        ),
    )
