"""Measure what E4's design ASSERTS but had never proven (Phase E4).

Two claims in `services/ai_grader.py` were argued rather than measured. The
first has now been settled by this probe, and settled AGAINST the design:

  1. "the cached system prefix actually CACHES" — FALSE on Claude Sonnet 5.
     Measured 2026-08-09: the stable instruction block is 981 tokens against a
     1024-token minimum cacheable prefix. A `cache_control` breakpoint there
     caches nothing and reports no error, so the caching claim was withdrawn
     rather than the prompt padded to chase ~$1.35 across the whole curriculum.
     This probe now GUARDS that conclusion instead of asserting the old one: it
     re-measures every run, so if the block grows past the configured model's
     minimum (or the model changes — Claude Opus 5's minimum is 512, which this
     prefix already clears) the question reopens visibly.

  2. a grade costs the design's estimated $0.02-0.04 — measured below.

    AI_GRADING_ENABLED=true poetry run python scripts/ai_grader_probe.py

Needs a credential (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or `ant auth
login`) AND `AI_GRADING_ENABLED=true` — `ai_grader.grade()` refuses to call the
API when grading is switched off, and that check fires here exactly as it does
in the app.

MEASUREMENT SUBTLETY THIS PROBE EXISTS TO GET RIGHT
---------------------------------------------------
`count_tokens` reports the WHOLE request, so system-block tokens are measured as
a DIFFERENCE against the same request minus the system block. Reading the
combined figure against the minimum would count the user turn and per-request
overhead toward a threshold they do not contribute to, and could report a PASS
for a block that is actually under it. (Here: 988 whole-request vs 981 actual.)

The two graded calls deliberately use DIFFERENT drills, so the cost figures are
representative of the curriculum rather than of one rubric measured twice.
"""

import asyncio
import sys

from sqlalchemy import create_engine, text

from app.config import settings
from app.services import ai_grader
from tests.evidence_helpers import chart_png

#: Minimum cacheable prefix per model, in tokens. Not monotonic across
#: generations — Claude Opus 5 halved Opus 4.8's — so it is a lookup, not a
#: constant. Unknown models fall back to the largest common value rather than
#: quietly assuming the prefix is cacheable.
_MIN_CACHEABLE = {
    "claude-opus-5": 512,
    "claude-fable-5": 512,
    "claude-sonnet-5": 1024,
    "claude-opus-4-8": 1024,
    "claude-haiku-4-5": 4096,
}
_MIN_CACHEABLE_FALLBACK = 4096


def _two_real_rubrics() -> list[tuple[str, str, list[dict]]]:
    """Two genuinely different seeded rubrics, so token counts and costs are
    representative of the curriculum rather than of one rubric measured twice."""
    eng = create_engine(settings.sync_database_url)
    out: list[tuple[str, str, list[dict]]] = []
    with eng.connect() as c:
        rows = c.execute(text(
            "select r.slug, r.drill_ref from rubrics r "
            "join rubric_items i on i.rubric_id = r.id "
            "group by r.slug, r.drill_ref having count(i.id) >= 3 "
            "order by r.drill_ref limit 2"
        )).all()
        if len(rows) < 2:
            raise SystemExit("need 2 seeded rubrics with >=3 items — is the DB seeded?")
        for slug, drill_ref in rows:
            items = [
                {"item_key": k, "text": t}
                for k, t in c.execute(text(
                    "select i.item_key, i.text from rubric_items i "
                    "join rubrics r on r.id = i.rubric_id where r.slug = :s "
                    "order by i.ordinal"
                ), {"s": slug})
            ]
            out.append((slug, drill_ref, items))
    return out


async def main() -> int:
    import anthropic

    client = anthropic.AsyncAnthropic()
    model = settings.ai_grader_model
    minimum = _MIN_CACHEABLE.get(model, _MIN_CACHEABLE_FALLBACK)

    # --- GUARD 1: is the stable prefix still too short to cache? -------------
    probe_msg = [{"role": "user", "content": "x"}]
    with_system = (await client.messages.count_tokens(
        model=model,
        system=[{"type": "text", "text": ai_grader.SYSTEM_INSTRUCTIONS}],
        messages=probe_msg,
    )).input_tokens
    without_system = (await client.messages.count_tokens(
        model=model, messages=probe_msg,
    )).input_tokens
    n = with_system - without_system
    print(f"\n[1] stable system prefix = {n} tokens "
          f"({with_system} whole request - {without_system} baseline); "
          f"{model} minimum cacheable prefix = {minimum}")
    if n < minimum:
        print(f"    CONFIRMED UNCACHEABLE ({minimum - n} tokens short) — "
              "`ai_grader.py` correctly ships no cache_control. Nothing to do.")
    else:
        print(f"    ⚠ REOPENED: the prefix now CLEARS the minimum by {n - minimum} tokens. "
              "Caching became viable — re-run the cost maths in ai_grader.py's header "
              "before deciding, and update test_ai_grader.py if you add a breakpoint.")

    # --- CLAIM 2: what does a grade actually cost? --------------------------
    rubrics = _two_real_rubrics()
    print(f"\n[2] two live grades, model={model}")
    results = []
    for i, (slug, drill_ref, items) in enumerate(rubrics, start=1):
        r = await ai_grader.grade(
            image=chart_png(seed=4000 + i),
            content_type="image/png",
            rubric_block=ai_grader.build_rubric_block(slug, drill_ref, items),
            client=client,
        )
        results.append(r)
        u = r.usage
        print(f"  call {i} ({drill_ref}, {len(items)} items): "
              f"in={u.input_tokens} out={u.output_tokens} "
              f"cache_write={u.cache_write_tokens} cache_read={u.cache_read_tokens} "
              f"${r.cost_usd}  {'verdict OK' if r.verdict else 'ERROR: ' + str(r.error)}")

    stray = [r for r in results if r.usage.cache_read_tokens or r.usage.cache_write_tokens]
    if stray:
        print("    NOTE: a non-zero cache counter appeared with no breakpoint set — "
              "investigate before trusting the cost column.")

    costs = [r.cost_usd for r in results]
    print(f"\n[2] cost/grade: {costs}  — design estimated $0.02-0.04")
    for c in costs:
        if not (0.02 <= float(c) <= 0.04):
            print(f"    NOTE: ${c} is outside the estimate — flag it (Rule #6) in the as-built.")

    if results[0].verdict:
        print("\nverdict (call 1):", results[0].verdict)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
