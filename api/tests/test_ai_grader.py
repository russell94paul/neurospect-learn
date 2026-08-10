"""Phase E4 — the AI vision second reader, at the unit layer.

These tests deliberately need NO database and NO network. They cover the part of
E4 whose correctness is structural rather than integrational:

  · the verdict schema physically cannot carry a price (design §"Why tiered")
  · `summarise()` can never return `failed` (design §4 — flag, never retract)
  · an `item_key` the app did not supply is dropped, not stored
  · the request puts the cache breakpoint on the INSTRUCTIONS, not the rubric
  · every API failure mode comes back as a recorded error, never an exception

The API-shaped tests use a fake transport, so the suite never needs a network,
a credential, or `AI_GRADING_ENABLED`. That matters beyond speed: Paul's normal
local state has no key at all, and a suite that quietly depended on one would
fail for the wrong reason.
"""

import itertools
import json
from decimal import Decimal

import pytest

from app.models.enums import EvidenceGradeState
from app.services import ai_grader
from app.services.ai_grader import (
    ITEM_EVIDENCE,
    VERDICT_SCHEMA,
    AIGraderUnavailable,
    GradeResult,
    Usage,
    build_rubric_block,
    summarise,
)

ITEMS = [
    {"item_key": "aura-d1-a#1", "text": "circle **≥50 swing points** — highs/lows only"},
    {"item_key": "aura-d1-a#2", "text": "re-anchor each range's extremes onto SMT-qualified swings"},
]
ITEM_TEXTS = {i["item_key"]: i["text"] for i in ITEMS}


# ---------------------------------------------------------------------------
# A fake Anthropic transport — no network, no credential
# ---------------------------------------------------------------------------

class _Usage:
    def __init__(self, i=0, o=0, r=0, w=0):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = r
        self.cache_creation_input_tokens = w


class _TextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, *, text=None, stop_reason="end_turn", usage=None, content=None):
        self.stop_reason = stop_reason
        self.usage = usage or _Usage()
        if content is not None:
            self.content = content
        else:
            self.content = [_TextBlock(text)] if text is not None else []


class _FakeMessages:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    async def count_tokens(self, **kwargs):  # pragma: no cover - not used here
        raise NotImplementedError

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc is not None:
            raise self._exc
        return self._response


class FakeClient:
    """Stands in for `anthropic.AsyncAnthropic`."""

    def __init__(self, response=None, exc=None):
        self.messages = _FakeMessages(response, exc)


@pytest.fixture
def enabled(monkeypatch):
    """Grading switched on. Off is the default and is its own test below."""
    monkeypatch.setattr(ai_grader.settings, "ai_grading_enabled", True)


def _verdict(*evidence, subject="annotated_price_chart"):
    return {
        "subject_matter": subject,
        "annotation_density": "moderate",
        "items": [
            {"item_key": ITEMS[n]["item_key"], "visible_evidence": e}
            for n, e in enumerate(evidence)
        ],
        "observations": [],
    }


# ---------------------------------------------------------------------------
# The schema is the enforcement
# ---------------------------------------------------------------------------

def _walk(node, path="$"):
    """Every subschema in the tree, with a readable path."""
    if not isinstance(node, dict):
        return
    yield path, node
    for key, sub in (node.get("properties") or {}).items():
        yield from _walk(sub, f"{path}.{key}")
    if "items" in node:
        yield from _walk(node["items"], f"{path}[]")


def test_the_schema_cannot_carry_a_number_anywhere():
    """MeasureBench puts VLMs at ~19-30% on precise value readout, so a price or
    a count must be UNREPRESENTABLE rather than merely discouraged. A prompt
    instruction can be ignored; a schema with nowhere to put a number cannot."""
    numeric = [
        path for path, sub in _walk(VERDICT_SCHEMA)
        if sub.get("type") in ("number", "integer")
    ]
    assert numeric == [], f"numeric field(s) reachable in the verdict: {numeric}"


def test_item_key_is_the_only_unconstrained_string():
    """Every other string is a closed enum. This is the test that would fail if
    someone later added a free-text `notes` or `comment` field — which is
    exactly how "this swing is at the wrong price" would get back in."""
    unconstrained = [
        path for path, sub in _walk(VERDICT_SCHEMA)
        if sub.get("type") == "string" and "enum" not in sub
    ]
    assert unconstrained == ["$.items[].item_key"]


def test_every_object_in_the_schema_is_closed():
    """`additionalProperties: false` everywhere — otherwise the model could add
    a field the schema never described, which is the same hole by another name."""
    for path, sub in _walk(VERDICT_SCHEMA):
        if sub.get("type") == "object":
            assert sub.get("additionalProperties") is False, path


# ---------------------------------------------------------------------------
# summarise() — never `failed`, and never words the app did not supply
# ---------------------------------------------------------------------------

def test_ai_vision_can_never_write_failed():
    """Design §4: a grade may flag, never retract. This tier is advisory on top
    of that, so `failed` must be unreachable BY CONSTRUCTION — walked over every
    combination of the item vocabulary rather than asserted on one example."""
    for combo in itertools.product(ITEM_EVIDENCE, repeat=len(ITEMS)):
        state, _, _ = summarise(_verdict(*combo), ITEM_TEXTS)
        assert state != EvidenceGradeState.FAILED.value
        assert state in {EvidenceGradeState.PASSED.value, EvidenceGradeState.FLAGGED.value}
        # The string must also be a real enum member, since the queue does
        # EvidenceGradeState(state) and would raise on anything else.
        EvidenceGradeState(state)


def test_an_unknown_item_key_is_dropped_not_stored():
    """`item_key` is the schema's one free-form string — the single place a model
    could smuggle text past the closed enums. Anything the app did not itself
    supply must not reach storage or the screen."""
    verdict = _verdict("clearly_present")
    verdict["items"].append(
        {"item_key": "'; DROP TABLE evidence_grades; --", "visible_evidence": "clearly_present"}
    )
    _, _, findings = summarise(verdict, ITEM_TEXTS)
    assert [f["item_key"] for f in findings] == ["aura-d1-a#1"]


def test_a_verdict_of_only_unknown_keys_flags_rather_than_passing():
    """The degenerate case: nothing the app recognises. It must not read as a
    clean pass, and it must not blow up."""
    verdict = _verdict()
    verdict["items"] = [{"item_key": "invented", "visible_evidence": "clearly_present"}]
    state, score, findings = summarise(verdict, ITEM_TEXTS)
    assert (state, score, findings) == (EvidenceGradeState.FLAGGED.value, Decimal("0"), [])


def test_passed_needs_every_item_clearly_visible():
    assert summarise(_verdict("clearly_present", "clearly_present"), ITEM_TEXTS)[0] == "passed"
    assert summarise(_verdict("clearly_present", "possibly_present"), ITEM_TEXTS)[0] == "flagged"
    assert summarise(_verdict("clearly_present", "not_visible"), ITEM_TEXTS)[0] == "flagged"


def test_an_honest_hedge_costs_less_than_a_miss():
    """`possibly_present` counts half — the scoring reason the reader is told to
    use it freely instead of guessing in either direction."""
    score = lambda *e: summarise(_verdict(*e), ITEM_TEXTS)[1]  # noqa: E731
    assert score("clearly_present", "clearly_present") == Decimal("100")
    assert score("clearly_present", "possibly_present") == Decimal("75")
    assert score("possibly_present", "possibly_present") == Decimal("50")
    assert score("not_visible", "not_visible") == Decimal("0")


def test_findings_carry_the_item_text_so_a_reseed_cannot_orphan_them():
    """A re-seed replaces `rubric_items`, so a stored grade that referenced only
    the positional key would become illegible. Same reason E3's self-check
    stores the text alongside the key."""
    _, _, findings = summarise(_verdict("clearly_present", "not_visible"), ITEM_TEXTS)
    assert [f["text"] for f in findings] == [ITEMS[0]["text"], ITEMS[1]["text"]]


# ---------------------------------------------------------------------------
# The rubric block authors nothing
# ---------------------------------------------------------------------------

def test_the_rubric_block_passes_wiki_text_through_verbatim():
    """The wiki is canonical (design §3). This module must not paraphrase a bar
    any more than the seed does."""
    block = build_rubric_block("aura-d1-a", "aura D1-a", ITEMS)
    for item in ITEMS:
        assert item["text"] in block
        assert item["item_key"] in block
    assert "aura D1-a" in block


# ---------------------------------------------------------------------------
# The call itself
# ---------------------------------------------------------------------------

async def test_grading_disabled_refuses_before_any_call():
    """Off is the default, so the app runs with no LLM dependency at all."""
    assert ai_grader.is_configured() is False
    client = FakeClient(_Response(text="{}"))
    with pytest.raises(AIGraderUnavailable):
        await ai_grader.grade(
            image=b"x", content_type="image/png", rubric_block="b", client=client
        )
    assert client.messages.calls == [], "a disabled grader must not reach the API"


async def test_the_system_prompt_is_stable_first_and_is_NOT_cached(enabled):
    """Two invariants, both the result of a measurement rather than an argument.

    ORDER: the stable instructions come first and the per-drill rubric second, so
    the volatile half can never become the prefix.

    NO CACHING: `SYSTEM_INSTRUCTIONS` measured 981 tokens against Sonnet 5's
    1024-token minimum cacheable prefix (2026-08-09), so a `cache_control`
    breakpoint here would cache NOTHING and report no error. This test is the
    alarm for someone re-adding one on the strength of the design doc without
    re-running `scripts/ai_grader_probe.py` — if the block has since grown past
    the configured model's minimum, change the probe's verdict first, then this.
    """
    client = FakeClient(_Response(text=json.dumps(_verdict("clearly_present"))))
    await ai_grader.grade(
        image=b"img", content_type="image/png", rubric_block="RUBRIC-HERE", client=client
    )
    sent = client.messages.calls[0]
    system = sent["system"]

    assert system[0]["text"] == ai_grader.SYSTEM_INSTRUCTIONS
    assert system[1]["text"] == "RUBRIC-HERE"
    assert not any("cache_control" in block for block in system), (
        "the prefix is under the model's minimum cacheable size — a breakpoint "
        "here is a silent no-op, which is the failure mode this phase exists to "
        "prevent. Re-measure before re-adding."
    )
    assert "cache_control" not in sent, "no top-level auto-caching either"

    # Thinking off / effort low: MeasureBench found negligible gains from extended
    # thinking here, because the limit is perceptual rather than computational.
    assert sent["thinking"] == {"type": "disabled"}
    assert sent["output_config"]["effort"] == "low"
    assert sent["output_config"]["format"]["schema"] is VERDICT_SCHEMA


async def test_a_transport_failure_is_recorded_never_raised(enabled):
    """The caller's only honest response to any failure is the same — record
    `ungraded` and leave the rep alone — so `grade()` must not raise."""
    client = FakeClient(exc=RuntimeError("connection reset"))
    result = await ai_grader.grade(
        image=b"x", content_type="image/png", rubric_block="b", client=client
    )
    assert result.verdict is None
    assert "RuntimeError" in result.error and "connection reset" in result.error


@pytest.mark.parametrize(
    "response,expected",
    [
        (_Response(stop_reason="refusal"), "refusal"),
        (_Response(stop_reason="max_tokens", text="{"), "max_tokens"),
        (_Response(text="not json at all"), "unparseable verdict"),
        (_Response(content=[]), "empty response"),
    ],
)
async def test_every_bad_outcome_is_an_honest_error_not_a_bad_rep(enabled, response, expected):
    """A refusal, a truncation, an unparseable verdict and an empty response are
    all ungraded — none of them is a judgement about the trader's work."""
    result = await ai_grader.grade(
        image=b"x", content_type="image/png", rubric_block="b", client=FakeClient(response)
    )
    assert result.verdict is None
    assert expected in result.error


async def test_a_good_verdict_comes_back_parsed_with_its_usage(enabled):
    verdict = _verdict("clearly_present", "possibly_present")
    client = FakeClient(_Response(text=json.dumps(verdict), usage=_Usage(i=2800, o=180, r=1500, w=0)))
    result = await ai_grader.grade(
        image=b"x", content_type="image/png", rubric_block="b", client=client
    )
    assert result.verdict == verdict
    assert result.error is None
    assert (result.usage.input_tokens, result.usage.output_tokens) == (2800, 180)
    assert result.usage.cache_read_tokens == 1500


# ---------------------------------------------------------------------------
# Cost telemetry is DERIVED, over all four token classes
# ---------------------------------------------------------------------------

def test_cost_prices_all_four_token_classes():
    """Cache reads (~0.1x) and writes (~1.25x) are priced separately — without
    that the telemetry could not show the cache working at all."""
    result = GradeResult(
        model="claude-sonnet-5", usage=Usage(input_tokens=1000, output_tokens=500,
                                             cache_read_tokens=2000, cache_write_tokens=1000)
    )
    # 1000*3.00 + 500*15.00 + 2000*0.30 + 1000*3.75, per million
    assert result.cost_usd == Decimal("0.01485")


def test_billable_input_counts_every_input_token_however_priced():
    usage = Usage(input_tokens=100, output_tokens=7, cache_read_tokens=20, cache_write_tokens=3)
    assert usage.billable_input == 123


def test_an_unpriced_model_reports_zero_rather_than_guessing():
    """Better a visible zero than an invented number in the cost column."""
    result = GradeResult(model="some-future-model", usage=Usage(input_tokens=10_000))
    assert result.cost_usd == Decimal("0")
