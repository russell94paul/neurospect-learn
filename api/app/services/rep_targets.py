"""Freetext rep-target parser (Phase 5e-1).

The wiki's rep targets are freetext — "≥50 ranges", "1 week", "10 days",
"5 sessions", "score by hand", "—". This pure module normalizes one such string
into a `(kind, count)` pair so the stage exit-bar service (`stages.py`) and the
ladder-advance enforcement in the progress API can compare a user's rep count
against a numeric floor.

Design contract (learning-platform.md §Stage exit-bar derivation, step 3):
  - reps=N       count-y targets ("≥50", "≥20 gaps", "~50")
  - days=N       longitudinal drills ("10 days", "1 week" → 7)
  - sessions=N   ("5 sessions")
  - qualitative  a target with no numeric floor ("score by hand", "per entry") —
                 gate on ladder + confidence, NOT on reps
  - habit        U0 / behavioural, no target ("—", "(habit)", None)

It **defaults conservatively and never invents a target**: a string with no
parseable number becomes `qualitative` (no floor), never a made-up count. Where
a string carries several numbers (e.g. "≥5 + ≥50 swings", "5 sessions / 10
days") the **largest** resolved floor binds — the stricter, safer gate.

The freetext stays canonical in the seed; this is a read-time interpretation of
it, not a rewrite (no-drift).
"""

import re
from dataclasses import dataclass

# A standalone quantity, optionally followed by a time/session unit. The
# lookbehinds reject a number embedded in an identifier ("Class-2 hw", "Model
# 2022", "M2") — those are references, not rep counts, so treating them as a
# floor would invent a target. A leading ≥/~/> or "(" is fine (not A-Za-z0-9/-).
_TOKEN = re.compile(r"(?<![A-Za-z0-9])(?<!-)(\d+)\s*(weeks?|days?|sessions?)?", re.IGNORECASE)
_HABIT = re.compile(r"habit|behaviou?ral", re.IGNORECASE)
_NULLISH = {"", "-", "—", "–", "n/a", "none", "(habit)", "tbd"}

_FLOOR_KINDS = ("reps", "days", "sessions")


@dataclass(frozen=True)
class RepTarget:
    """A parsed rep target. `count` is None for qualitative/habit targets."""

    kind: str  # "reps" | "days" | "sessions" | "qualitative" | "habit"
    count: int | None
    raw: str  # the original freetext (canonical)

    @property
    def has_floor(self) -> bool:
        """True iff this target imposes a numeric rep floor to clear."""
        return self.count is not None and self.kind in _FLOOR_KINDS


def parse(text: str | None) -> RepTarget:
    """Normalize a freetext rep target into a `RepTarget`."""
    raw = text or ""
    t = raw.strip().lower().replace("*", "")
    if t in _NULLISH:
        return RepTarget("habit", None, raw)
    if _HABIT.search(t):
        return RepTarget("habit", None, raw)

    candidates: list[tuple[str, int]] = []
    for m in _TOKEN.finditer(t):
        n = int(m.group(1))
        unit = (m.group(2) or "").lower()
        if unit.startswith("week"):
            candidates.append(("days", n * 7))
        elif unit.startswith("day"):
            candidates.append(("days", n))
        elif unit.startswith("session"):
            candidates.append(("sessions", n))
        else:
            candidates.append(("reps", n))

    if not candidates:
        # A named target with no number → qualitative (gate on ladder+conf).
        return RepTarget("qualitative", None, raw)

    kind, count = max(candidates, key=lambda kc: kc[1])
    return RepTarget(kind, count, raw)


def meets(reps: int, target: RepTarget) -> bool:
    """Does `reps` clear this target's floor? Qualitative/habit → always True
    (no numeric floor; those gate on ladder + confidence instead)."""
    if not target.has_floor:
        return True
    return reps >= (target.count or 0)
