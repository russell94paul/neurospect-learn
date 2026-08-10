"""Measure what E4's design ASSERTS but had never proven (Phase E4).

Two claims in `services/ai_grader.py` were argued rather than measured:

  1. the cached system prefix actually CACHES — which needs it to clear Claude
     Sonnet 5's 1024-token minimum cacheable prefix, and to show a non-zero
     `cache_read_input_tokens` on a second call inside the TTL;
  2. a grade costs the design's estimated $0.02-0.04.

A prefix under the minimum caches nothing and reports NO error, so without this
probe the caching claim could sit in the codebase indefinitely being false.

    poetry run python scripts/ai_grader_probe.py

Needs a credential (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or `ant auth login`)
and AI_GRADING_ENABLED is NOT required — the probe calls the grader directly.
"""

import asyncio
import sys

from sqlalchemy import create_engine, text

from app.config import settings
from app.services import ai_grader
from tests.evidence_helpers import chart_png


def _a_real_rubric() -> tuple[str, str, list[dict]]:
    """A genuine seeded rubric, so the token counts are representative."""
    eng = create_engine(settings.sync_database_url)
    with eng.connect() as c:
        row = c.execute(text(
            "select r.slug, r.drill_ref from rubrics r "
            "join rubric_items i on i.rubric_id = r.id "
            "group by r.slug, r.drill_ref having count(i.id) >= 3 "
            "order by r.drill_ref limit 1"
        )).first()
        if row is None:
            raise SystemExit("no seeded rubric with >=3 items — is the DB seeded?")
        slug, drill_ref = row
        items = [
            {"item_key": k, "text": t}
            for k, t in c.execute(text(
                "select i.item_key, i.text from rubric_items i "
                "join rubrics r on r.id = i.rubric_id where r.slug = :s "
                "order by i.ordinal"
            ), {"s": slug})
        ]
    return slug, drill_ref, items


async def main() -> int:
    import anthropic

    client = anthropic.AsyncAnthropic()
    model = settings.ai_grader_model
    slug, drill_ref, items = _a_real_rubric()
    rubric_block = ai_grader.build_rubric_block(slug, drill_ref, items)

    # --- CLAIM 1a: does the cached half clear the 1024-token minimum? ---------
    counted = await client.messages.count_tokens(
        model=model,
        system=[{"type": "text", "text": ai_grader.SYSTEM_INSTRUCTIONS}],
        messages=[{"role": "user", "content": "x"}],
    )
    n = counted.input_tokens
    print(f"\n[1a] cached system prefix = {n} tokens (Sonnet 5 minimum is 1024)")
    print("     ", "PASS — it can cache" if n >= 1024 else
          "*** FAIL — caches NOTHING, silently. Grow the block or drop the claim. ***")

    # --- CLAIM 1b + 2: two real grades, same prefix -------------------------
    print(f"\n[1b/2] two live grades against {drill_ref} ({len(items)} items), model={model}")
    results = []
    for i in (1, 2):
        r = await ai_grader.grade(
            image=chart_png(seed=4000 + i),
            content_type="image/png",
            rubric_block=rubric_block,
            client=client,
        )
        results.append(r)
        u = r.usage
        print(f"  call {i}: in={u.input_tokens} out={u.output_tokens} "
              f"cache_write={u.cache_write_tokens} cache_read={u.cache_read_tokens} "
              f"${r.cost_usd}  {'verdict OK' if r.verdict else 'ERROR: ' + str(r.error)}")

    read2 = results[1].usage.cache_read_tokens
    print("\n[1b]", "PASS — the prefix is being read from cache" if read2 > 0 else
          "*** FAIL — cache_read_input_tokens is 0 on call 2; the prefix is NOT caching. ***")

    costs = [r.cost_usd for r in results]
    print(f"[2] cost/grade: {costs}  — design estimated $0.02-0.04")
    for c in costs:
        if not (0.02 <= float(c) <= 0.04):
            print(f"    NOTE: ${c} is outside the estimate — flag it (Rule #6) in the as-built.")

    if results[0].verdict:
        print("\nverdict (call 1):", results[0].verdict)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
