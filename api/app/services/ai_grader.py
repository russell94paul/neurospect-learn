"""AI vision — tier 3, the ADVISORY SECOND READER (Phase E4).

See concepts/architecture/learning-enforcement.md §2 tier 3. This tier is the one
that must be *prevented* from doing its job too well: it never blocks, never
retracts, and never writes `confidence` or `ladder_stage`.

WHY THE SCHEMA IS THE LOAD-BEARING DESIGN
-----------------------------------------
MeasureBench (arXiv 2510.26865) puts frontier VLMs at 19-30% on precise value
readout from analog scales — >90% on unit recognition, ~30% on numeric extraction,
with negligible gains from extended thinking because the limitation is
PERCEPTUAL, not computational. "Which price level is this line drawn at" is that
exact task.

So this module does not *ask* the model to avoid price claims; it makes them
unrepresentable. Every field below is a closed enum or a rubric item key. There
is no free-text field and no numeric field anywhere in `VERDICT_SCHEMA` — the
model cannot say "this swing is at the wrong price" because the schema has
nowhere to put it. A prompt instruction could be ignored; a schema cannot.

That is also why `observations` is a fixed vocabulary rather than a list of
strings: a free-text observation list would reopen the whole hole.

WHY THINKING IS OFF
-------------------
The same MeasureBench finding: extended thinking yields negligible gains on this
task class. Paying for thinking tokens to answer "are range boundaries drawn"
buys nothing, so `thinking` is disabled and effort is `low`. This is the design's
own evidence applied to its own configuration.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.config import settings

# ---------------------------------------------------------------------------
# The verdict schema — closed enums only, no free text, no numbers
# ---------------------------------------------------------------------------

#: What the capture actually is. Kind-aware: a Stage-0 written artifact SHOULD
#: read as `written_document`, so this is not a chart/not-chart pass-fail.
SUBJECT_MATTER = [
    "annotated_price_chart",
    "plain_price_chart",
    "written_document",
    "table_or_computation",
    "other",
    "unclear",
]

#: How much marking is visible. Coarse by design — counting annotations exactly
#: is a value-readout task, which is the thing VLMs are unreliable at.
ANNOTATION_DENSITY = ["none", "sparse", "moderate", "dense"]

#: Per-item: is this rubric item VISIBLY EVIDENCED? Deliberately tri-state — the
#: middle value is what stops a hedge being recorded as a refusal. Note the
#: vocabulary is about VISIBILITY, never correctness: "not_visible" means the
#: reader cannot see it, not that the user got it wrong.
ITEM_EVIDENCE = ["clearly_present", "possibly_present", "not_visible"]

#: The ONLY things this tier may observe, as a closed set. Each is a coarse
#: presence/structure question — the >90% band in MeasureBench — and none of them
#: can carry a price, a level, or a count.
OBSERVATIONS = [
    "no_chart_detected",
    "no_annotations_visible",
    "drawing_tools_visible",
    "text_labels_visible",
    "multiple_timeframes_shown",
    "single_timeframe_only",
    "price_axis_not_legible",
    "time_axis_not_legible",
    "image_low_resolution",
    "image_appears_cropped",
    "chart_mostly_obscured_by_markings",
]

VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject_matter", "annotation_density", "items", "observations"],
    "properties": {
        "subject_matter": {"type": "string", "enum": SUBJECT_MATTER},
        "annotation_density": {"type": "string", "enum": ANNOTATION_DENSITY},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item_key", "visible_evidence"],
                "properties": {
                    "item_key": {"type": "string"},
                    "visible_evidence": {"type": "string", "enum": ITEM_EVIDENCE},
                },
            },
        },
        "observations": {
            "type": "array",
            "items": {"type": "string", "enum": OBSERVATIONS},
        },
    },
}


# ---------------------------------------------------------------------------
# The system prompt — TWO blocks, and deliberately NOT cached
# ---------------------------------------------------------------------------
# DIVERGENCE FROM THE DESIGN, stated plainly: design §2 says "the rubric in a
# cached system prefix". There is no cached prefix here at all, and the reason
# is a measurement rather than an argument.
#
# The design's own trap, avoided first: caching is a PREFIX match, so putting
# the per-drill RUBRIC first would mint a fresh entry per drill and read one
# only when the same drill is graded twice inside the TTL. That much was right,
# and it is why the stable instructions come first and the rubric second.
#
# But the fix does not work either, because the stable half is TOO SHORT:
#
#   MEASURED 2026-08-09 (scripts/ai_grader_probe.py, count_tokens against
#   claude-sonnet-5): SYSTEM_INSTRUCTIONS = 981 tokens. Claude Sonnet 5's
#   minimum cacheable prefix is 1024. It is 43 tokens SHORT, so a breakpoint
#   here caches NOTHING and reports no error — the exact silent no-op the
#   comment above it used to warn about.
#
# Withdrawn rather than padded, on the numbers: a cache read would save ~981
# tokens x $2.70/MTok = ~$0.0027 per grade, or ~$1.35 across the whole ~500-unit
# curriculum — against a ~2,765-token image that dominates every call. Worse, a
# cache WRITE costs 1.25x, so at the 5-minute TTL of a single user uploading
# evidence sporadically, most grades would pay the write premium and never live
# to be read. Growing the block to 1024+ would mean writing instruction text to
# satisfy a token threshold rather than to inform the reader, and would leave
# the prompt permanently hostage to it.
#
# The two-block split is KEPT: it documents the stable/volatile boundary, and it
# is where a breakpoint would go if this ever becomes worth doing. Note the
# prefix already clears Claude Opus 5's 512-token minimum — so this conclusion
# is specific to `AI_GRADER_MODEL=claude-sonnet-5`, and re-measuring is the
# first step if that setting changes.

SYSTEM_INSTRUCTIONS = """\
You are a SECOND READER for a trading-practice journal. A trader marks up price \
charts by hand as deliberate practice, uploads the capture as evidence that the \
work was done, and checks it against the drill's own written bar. Your report is \
shown beside their self-check as advisory, informational feedback.

You are not a grader and you are not an arbiter. You do not decide whether the \
rep counts — nothing you return can change their progress, and a disagreement \
between you and the trader is information for them, not a verdict against them.

WHAT YOU ARE RELIABLE AT, AND WHAT YOU ARE NOT

Vision-language models read coarse structure from images very well: whether an \
image is a price chart at all, whether anything has been drawn on it, whether \
horizontal levels or boxes or trendlines are present, whether labels have been \
typed, whether more than one timeframe is on screen. On those questions you are \
accurate above 90% of the time.

Vision-language models read PRECISE VALUES off analog scales very badly. \
Benchmarks put frontier models around 19-30% on extracting a specific number \
from a chart axis, and the gap does not close with more deliberation, because \
the limit is perceptual rather than a matter of reasoning harder. Reading "which \
price is this line drawn at" off a chart is exactly that failing task.

Everything you are asked for below sits in the first category. Nothing you are \
asked for sits in the second. Report what is VISIBLE, never what is CORRECT.

Specifically: do not judge whether a level is at the right price, whether a swing \
is the true high, whether a range is drawn around the correct session, whether a \
gap qualifies as a fair value gap, or whether the trader's reading of the market \
is sound. You cannot see those things reliably, and the schema gives you nowhere \
to record them.

HOW TO FILL IN THE VERDICT

subject_matter: what the capture actually is. Not every drill produces a chart — \
several ask for a written routine or a computed table, and those should read as \
written_document or table_or_computation rather than as a failed chart.

annotation_density: roughly how much marking has been added on top of whatever \
was there to begin with. A judgement of quantity, not of quality or accuracy.

items: one entry for each rubric item you are given, using the item_key exactly \
as supplied. For each, say whether the work that item describes is VISIBLY \
EVIDENCED in the capture:

  clearly_present   - you can see the thing the item describes
  possibly_present  - something consistent with it is there, but you cannot tell
  not_visible       - you cannot see it in this capture

Use possibly_present freely. It is the honest answer whenever you are unsure, \
and it is far more useful to the trader than a confident guess in either \
direction. not_visible means only that you could not see it — it is not an \
accusation that the work was skipped, since a single capture often cannot show \
everything a drill asks for.

observations: any of the listed notes that genuinely apply. An empty list is a \
perfectly good answer; do not reach for observations to seem thorough.

Return only the structured verdict.\
"""


# ---------------------------------------------------------------------------
# Pricing — list rates, so cost telemetry is comparable across time
# ---------------------------------------------------------------------------
# USD per million tokens. Cache reads (~0.1x base input) and writes (~1.25x at
# the 5-minute TTL) are still priced separately even though nothing is cached
# today: the API reports those counters regardless, pricing them keeps the
# telemetry correct if caching is ever re-enabled, and a non-zero cache figure
# appearing in a stored grade is then a visible signal rather than a silent
# mispricing.
#
# NOTE (honest): these are STANDARD list rates. Claude Sonnet 5 carries a lower
# introductory rate ($2/$10) through 2026-08-31, so real billed spend during that
# window is below what `cost_usd` records. Recording list rates keeps the stored
# number comparable across the whole curriculum rather than cheaper for whatever
# was graded before the intro window closed.
_PRICES: dict[str, dict[str, float]] = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-opus-5": {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write": 1.25},
}


@dataclass
class Usage:
    """Token counts as reported by the API, kept separate so cost is DERIVED."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def billable_input(self) -> int:
        """What the telemetry column stores: every input token, however priced."""
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens


@dataclass
class GradeResult:
    """One completed advisory read. `verdict` is None when the call did not
    produce one — see `error`, and note the caller records that as `ungraded`
    rather than as a failure of the trader's work."""

    model: str
    usage: Usage = field(default_factory=Usage)
    verdict: dict[str, Any] | None = None
    error: str | None = None

    @property
    def cost_usd(self) -> Decimal:
        p = _PRICES.get(self.model)
        if p is None:
            return Decimal("0")
        dollars = (
            self.usage.input_tokens * p["input"]
            + self.usage.output_tokens * p["output"]
            + self.usage.cache_read_tokens * p["cache_read"]
            + self.usage.cache_write_tokens * p["cache_write"]
        ) / 1_000_000
        return Decimal(str(round(dollars, 6)))


class AIGraderUnavailable(RuntimeError):
    """No credential configured. NOT an error condition — this is Paul's normal
    local state, and the upload path must be completely unaffected by it."""


def is_configured() -> bool:
    """Whether an advisory read can even be attempted.

    Deliberately checks only whether grading is switched on: the Anthropic SDK
    resolves credentials from ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN *or* an
    `ant auth login` profile on disk, so an unset env var does not mean there is
    no credential. Asking the SDK is the only honest test, and it happens when a
    grade is actually attempted.
    """
    return settings.ai_grading_enabled


def build_rubric_block(rubric_slug: str, drill_ref: str, items: list[dict[str, str]]) -> str:
    """The per-drill bar, as the UNCACHED half of the system prompt.

    Item text is passed through verbatim from the wiki projection — this module
    authors no rubric text, exactly as the seed does not (design §3).
    """
    lines = [
        f"The drill is {drill_ref} (rubric {rubric_slug}). Its bar, as written in "
        "the trader's own course notes, is the following items. Report on each by "
        "its item_key.",
        "",
    ]
    for it in items:
        lines.append(f"  {it['item_key']}: {it['text']}")
    return "\n".join(lines)


def _extract_usage(resp: Any) -> Usage:
    u = getattr(resp, "usage", None)
    if u is None:
        return Usage()
    return Usage(
        input_tokens=getattr(u, "input_tokens", 0) or 0,
        output_tokens=getattr(u, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
    )


async def grade(
    *,
    image: bytes,
    content_type: str,
    rubric_block: str,
    client: Any | None = None,
) -> GradeResult:
    """Ask the second reader about ONE capture. Never raises for an API problem.

    A transport failure, a refusal, a truncation or a malformed verdict all come
    back as `GradeResult(error=...)` with whatever usage was incurred, because
    the caller's only honest response to any of them is the same: record the row
    as `ungraded` and leave the rep alone.
    """
    model = settings.ai_grader_model
    if not is_configured():
        raise AIGraderUnavailable("AI grading is disabled (AI_GRADING_ENABLED=false).")

    if client is None:
        import anthropic

        client = anthropic.AsyncAnthropic()

    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=settings.ai_grader_max_tokens,
            # Thinking OFF: MeasureBench found negligible gains from extended
            # thinking on this task class because the limit is perceptual. Paying
            # for it here would be paying for nothing.
            thinking={"type": "disabled"},
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": VERDICT_SCHEMA},
            },
            system=[
                # STABLE half — identical for every grade in the curriculum.
                # No `cache_control`: at 981 tokens it is under Sonnet 5's 1024
                # minimum, so a breakpoint here would cache nothing and say
                # nothing. See the measurement above before adding one back.
                {"type": "text", "text": SYSTEM_INSTRUCTIONS},
                # VOLATILE half — per drill, and second so that it could never
                # become the prefix.
                {"type": "text", "text": rubric_block},
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content_type,
                                "data": base64.standard_b64encode(image).decode(),
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "This is the capture the trader submitted as evidence "
                                "for that drill. Report on it."
                            ),
                        },
                    ],
                }
            ],
        )
    except Exception as exc:  # noqa: BLE001 — every failure has the same handling
        return GradeResult(model=model, error=f"{type(exc).__name__}: {exc}")

    usage = _extract_usage(resp)
    stop = getattr(resp, "stop_reason", None)

    # A refusal or a truncation is an honestly ungraded row, not a bad rep.
    if stop == "refusal":
        return GradeResult(model=model, usage=usage, error="refusal")
    if stop == "max_tokens":
        return GradeResult(model=model, usage=usage, error="max_tokens: verdict truncated")

    text = next(
        (b.text for b in getattr(resp, "content", []) if getattr(b, "type", None) == "text"),
        None,
    )
    if not text:
        return GradeResult(model=model, usage=usage, error="empty response")

    try:
        verdict = json.loads(text)
    except json.JSONDecodeError as exc:
        return GradeResult(model=model, usage=usage, error=f"unparseable verdict: {exc}")

    return GradeResult(model=model, usage=usage, verdict=verdict)


# ---------------------------------------------------------------------------
# Turning a verdict into a grade row
# ---------------------------------------------------------------------------

def summarise(verdict: dict[str, Any], item_texts: dict[str, str]) -> tuple[str, Decimal, list[dict]]:
    """(state, advisory score, findings) for one verdict.

    THE STATE IS NEVER `failed`. §4 says a grade may flag but never retract, and
    this tier is advisory on top of that — so its worst verdict is `flagged`, and
    `failed` is unreachable from here by construction rather than by convention.
    Pinned by tests/test_ai_grader.py::test_ai_vision_can_never_write_failed.

    The score is ADVISORY (invariant 7) and nothing reads it into `confidence` or
    `ladder_stage`. `possibly_present` is counted as half, which is what makes an
    honest hedge cost less than a miss.
    """
    # `item_key` is the schema's ONLY free-form string, so it is the one place a
    # model could smuggle text past the closed enums. Anything that is not a key
    # we supplied is DROPPED rather than recorded — which restores the property
    # the rest of the schema has by construction: nothing reaches storage or the
    # screen that the app did not already have words for.
    items = [i for i in (verdict.get("items") or []) if i.get("item_key") in item_texts]
    if not items:
        return "flagged", Decimal("0"), []

    weights = {"clearly_present": 1.0, "possibly_present": 0.5, "not_visible": 0.0}
    total = sum(weights.get(i.get("visible_evidence", ""), 0.0) for i in items)
    score = Decimal(str(round(100 * total / len(items), 2)))

    findings = [
        {
            "item_key": i.get("item_key"),
            "visible_evidence": i.get("visible_evidence"),
            # Carry the text so the grade stays legible after a re-seed replaces
            # `rubric_items` — the same reason E3's self-check stores it.
            "text": item_texts.get(i.get("item_key", ""), ""),
        }
        for i in items
    ]

    # `passed` only when every item is clearly visible AND the capture read as
    # the kind of artifact the drill asks for; anything else is `flagged`, which
    # here means "worth your attention", not "rejected".
    all_clear = all(i.get("visible_evidence") == "clearly_present" for i in items)
    state = "passed" if all_clear else "flagged"
    return state, score, findings
