"""Pydantic schemas for the honesty strip (Phase E6).

Note what is ABSENT by design, in the tradition of `schemas/gate.py` (no `cleared`
field, so a model cannot be declared live-ready):

* **There is no request schema here at all.** The strip is read-only. Nothing
  about it can be set, dismissed, acknowledged or cleared, because anything a user
  could switch off is not a record of anything.
* **No signal carries a score, grade, threshold, target or pass/fail.** A signal
  reports what it measured and what it found. §6 forbids rewarding activity over
  mastery, and a green "0 flags" badge is a point scored for not being caught.
* **`count` is nullable and `status` is required.** A consumer cannot read a
  number without being handed the question of whether anything was measured — the
  distinction E5 established with `accuracy: None` and the reason this strip is
  trustworthy at all.
* **This is NOT part of `GateOut`.** It is served separately so that
  `services/gate.py` structurally cannot read it, which is how "gates nothing"
  becomes a property rather than a promise. See app/routers/gate.py.
"""

from pydantic import BaseModel


class HonestySignal(BaseModel):
    """One computed signal. Gates nothing; stored nowhere."""

    key: str
    label: str
    #: "measured" | "not_measured" — READ THIS BEFORE `count`.
    status: str
    #: Occurrences found. `null` whenever `status` is "not_measured" — never 0.
    #: A zero from an instrument that has not been shown able to see is not a
    #: measurement, and rendering one would be a claim about the user.
    count: int | None = None
    #: How many rows the instrument could actually inspect.
    population: int = 0
    #: What was looked at and against what rule — INCLUDING any threshold, so the
    #: figure can be discounted by whoever reads it.
    measured_what: str
    #: What was found, or why nothing could be looked at.
    detail: str
    #: The subjects implicated, so this is feedback rather than a scolding.
    subjects: list[str] = []


class HonestyOut(BaseModel):
    """The five §5 signals, plus the population the strip was computed over."""

    signals: list[HonestySignal]
    captures: int = 0
    #: E2 froze `legacy_reps` and left it visible for exactly this phase: it is the
    #: part of the rep count that never had evidence behind it and never can.
    reps_legacy: int = 0
    reps_evidenced: int = 0
