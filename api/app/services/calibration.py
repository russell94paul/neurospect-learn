"""Calibration (Phase E5) — how often your pre-committed call matched reality.

COMPUTED, never stored — the same convention `services/stages.py` and
`services/gate.py` follow, and for the same reason: a stored score is a number
someone can write, and this one is only worth anything if it cannot be written.

concepts/architecture/learning-enforcement.md §6 makes two demands of this
mechanic, and they are the whole content of this module:

**1. It must be GOODHART-RESISTANT — "more reps cannot inflate accuracy."**
Three properties deliver that, and all three are tested:

  a. *It is a RATIO, not a count.* Every figure here is correct/resolved. A count
     of correct calls would reward volume; a ratio is indifferent to it.
  b. *It is SCALE-INVARIANT.* Duplicating the whole record k times leaves every
     percentage identical. This is the direct form of "more reps cannot inflate
     it" and is asserted as such in tests/test_calibration.py.
  c. *The denominator cannot shrink.* This one is NOT enforced here — it is
     structural, in Alembic `0011`: `predictions` has no `is_deleted` column and
     the call is frozen by a trigger, so a failure can neither be deleted nor
     edited into a success. A ratio with a shrinkable denominator would be
     trivially gameable, and no amount of arithmetic in this file could fix that.

**2. It is INFORMATIONAL FEEDBACK, not a currency.** Deci, Koestner & Ryan (1999)
find tangible performance-contingent rewards undermine intrinsic motivation
(d ≈ −0.34) while informational feedback does not. So this module deliberately
emits NO grade, NO threshold, NO pass/fail and NO streak, and nothing in the app
gates on its output — `services/stages.py` grades M6 on *whether the calls were
committed before the reveal*, never on whether they were RIGHT. Being wrong in
writing, on the record, is the learning; making it cost something would teach the
user to stop writing things down.

**A zero is not the same as nothing.** With no resolved prediction, every accuracy
here is `None`, never `0.0` — an instrument that has seen nothing cannot report a
zero, and rendering "0%" for "you have not resolved a call yet" would be a claim
about the trader that the data does not support. The surface must say so.
"""

from dataclasses import dataclass

# The four things the wiki asks a tape read to call, in the order it names them:
# "note bias call, DOL, the model used, entry/target" (ict-course/exercises.md
# §Stage 6 method) and, for T-14, "call the read (bias, DOL, model, target)".
# The labels are what the user sees, so they stay the wiki's words.
COMPONENTS: tuple[tuple[str, str], ...] = (
    ("bias", "Directional bias"),
    ("dol", "Draw on liquidity"),
    ("entry_model", "Model used"),
    ("target", "Target"),
)


@dataclass(frozen=True)
class Call:
    """One prediction, as calibration needs to see it. PURE data — the router
    loads it; this module never touches a DB.

    `resolved` is derived from `resolved_at IS NOT NULL` upstream. An unresolved
    call contributes to `committed` and `unresolved` and to NOTHING else: it is a
    commitment whose answer is not in yet, not a wrong answer.
    """

    resolved: bool
    # The call, and what was revealed. `bias_correct` is an equality over the same
    # vocabulary on both sides; the other three are the trader's own report of what
    # happened, which is honest precisely BECAUSE the call was frozen first — there
    # is nothing to gain by lying about an outcome you already committed against.
    bias_correct: bool | None = None
    dol_correct: bool | None = None
    entry_model_correct: bool | None = None
    target_correct: bool | None = None

    def component(self, key: str) -> bool | None:
        return {
            "bias": self.bias_correct,
            "dol": self.dol_correct,
            "entry_model": self.entry_model_correct,
            "target": self.target_correct,
        }[key]


@dataclass(frozen=True)
class ComponentScore:
    key: str
    label: str
    correct: int
    resolved: int

    @property
    def accuracy(self) -> float | None:
        """Fraction correct, or None when nothing has resolved (never 0.0)."""
        if self.resolved == 0:
            return None
        return self.correct / self.resolved


@dataclass(frozen=True)
class Calibration:
    """The whole picture, including what is missing from it."""

    committed: int
    resolved: int
    components: tuple[ComponentScore, ...]

    @property
    def unresolved(self) -> int:
        return self.committed - self.resolved

    @property
    def resolution_rate(self) -> float | None:
        """Published BESIDE the accuracies, always. Resolving only the calls you
        got right is the one way left to bias this measure — the app cannot force a
        resolution, so it shows the gap instead of pretending there isn't one."""
        if self.committed == 0:
            return None
        return self.resolved / self.committed

    @property
    def accuracy(self) -> float | None:
        """Across all four components pooled. None when nothing has resolved."""
        total = sum(c.resolved for c in self.components)
        if total == 0:
            return None
        return sum(c.correct for c in self.components) / total


def compute(calls: list[Call]) -> Calibration:
    """Score a set of committed calls. Pure, total, and order-independent."""
    resolved = [c for c in calls if c.resolved]
    components = tuple(
        ComponentScore(
            key=key,
            label=label,
            # A resolved call whose component is None is not counted in EITHER the
            # numerator or the denominator. The DB makes this unreachable
            # (`ck_predictions_resolution_complete` is all-or-nothing), so this is
            # a fail-closed default rather than a case the UI can produce.
            correct=sum(1 for c in resolved if c.component(key) is True),
            resolved=sum(1 for c in resolved if c.component(key) is not None),
        )
        for key, label in COMPONENTS
    )
    return Calibration(committed=len(calls), resolved=len(resolved), components=components)
