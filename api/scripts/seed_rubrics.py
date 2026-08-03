"""Idempotent seed for the `rubrics` / `rubric_items` catalog (Phase E3).

Source of truth: the ✋/🛠 BULLETS under each drill in BOTH wiki exercise
libraries (READ-ONLY — never written back):
  - concepts/mastery/aura/exercises.md
  - concepts/mastery/ict-course/exercises.md

This is a PROJECTION, exactly as scripts/seed_drills.py projects the map tables
at the foot of the same two files. **NO RUBRIC TEXT IS AUTHORED HERE.** Every
`rubric_items.text` is a contiguous substring of a wiki bullet (see
`verify_no_drift`, asserted over the whole seed by
tests/test_rubrics.py::test_no_rubric_text_is_authored). If a bullet does not
make a checkable assertion, that is a WIKI problem to fix in the wiki — never a
sentence to invent in Python.

ONE ITEM PER BULLET, split ONLY on TOP-LEVEL semicolons
-------------------------------------------------------
The design says "one rubric item per bullet". Two measured facts refine that:

* Several bullets are compound, joined by semicolons — the Stage-0 drills most of
  all (aura D0-a is four separate deliverables in one bullet). One checkbox for
  four deliverables forces a DISHONEST tick when three are done, which is exactly
  the self-deception the workstream exists to prevent. So a top-level `;` splits.
* Splitting on SENTENCE boundaries as well was tried and REJECTED on evidence:
  this corpus writes "vs." mid-sentence followed by a capital
  ("**which KZ sets the HOD vs. LOD**", "**STL (no gap) vs. ITL (…)**",
  "Tag **LRLR vs. HRLR**", "tag real vs. **fake retracement**"), and every
  sentence heuristic mangled all four into garbage fragments. A parser that can
  mangle wiki text is a parser that AUTHORS wiki text. A top-level semicolon is
  unambiguous; a sentence boundary is not.

Depth-aware: a `;` inside (), [] or "" is NOT a boundary — the corpus has those
too ("(overlapping gaps; liquidity-left …)", '("inside a [bull/bear] 4H FVG;
target [level]")').

Only STRUCTURAL markers are stripped, each deterministic and edge-anchored so
what remains is still a contiguous substring: the leading `*(source)*:` marker,
a trailing `→ [[wikilink]]…` navigation trailer (required to be `→` + `[[`, since
the corpus also uses a bare mid-sentence `→`), a trailing `**[R8]**` rule ref
(captured into `rule_refs`), and a `**Advances:** …` tail (already carried by
`drills.advances_to`).

Run:  poetry run python -m scripts.seed_rubrics            (from api/)
      poetry run python -m scripts.seed_rubrics --dry-run  (report only, no DB)

Idempotent: UPSERT on `slug`. `version` bumps IF AND ONLY IF `content_hash` —
sha256 over the projected items — changes, so re-running twice is a genuine
no-op and a historical grade's `rubric_version` still names the bar it was judged
against. Provenance (`source_path` / `source_ref`) updates in place WITHOUT a
bump: it is not part of what the user ticks. Rubrics whose slug is no longer
produced are DELETED (authoritative re-seed, mirroring seed_drills.py).

Nothing is silently skipped. The run reports drills with no projectable bullets,
rubrics whose drill the map table does not list, and items carrying a wikilink.
"""

import argparse
import asyncio
import hashlib
import re
from collections import defaultdict
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models.rubric import Rubric, RubricItem
from scripts.seed_drills import build_drills

# (relative path under concepts/, track enum value, drill_ref prefix) — the same
# tuple seed_drills.py uses, so the two projections can never disagree on which
# file is which track.
_TRACKS = [
    ("mastery/aura/exercises.md", "aura", "aura"),
    ("mastery/ict-course/exercises.md", "ict_course", "ict-course"),
]

HAND_GLYPH = "✋"          # ✋ hand-marking — do first, trains the eye
TOOL_GLYPH = "\U0001f6e0"      # 🛠 tool-assisted — for speed once the eye is trained

# A drill CODE is exactly one of the four shapes both libraries use, and the same
# shapes seed_drills._expand() emits: D4-a · T-01 · J-a · S7. Anchoring on that
# is load-bearing, not cosmetic — a looser `[A-Z]…` pattern matched the bolded
# lead-in `**Evolving-R reps:**` inside aura D3-c as an inline drill named
# "Evolving", inventing a phantom rubric AND stealing that bullet from D3-c.
_CODE = r"(?:D\d+-[a-z]|T-\d+|J-[a-z]|S\d+)"
# `### D1-a — Swing points *(aura-06; target ≥50)*`
_DRILL_HEADING = re.compile(
    rf"^#{{3,4}}\s+(?P<code>{_CODE})\s*(?:—|-{{1,2}})\s*(?P<title>.+?)\s*$"
)
# `- **D0-a — Routine & environment build** *(aura-04)*: write your …`
_INLINE_DRILL = re.compile(
    rf"^-\s+\*\*(?P<code>{_CODE})\s*(?:—|-{{1,2}})\s*(?P<title>[^*]*?)\*\*\s*(?P<rest>.*)$"
)
_STAGE_HEADING = re.compile(r"^#{1,2}\s+")
_BULLET = re.compile(r"^-\s+(?P<body>.*)$")
_CONTINUATION = re.compile(r"^\s{2,}(?P<body>\S.*)$")

# Structural markers. All EDGE-ANCHORED so stripping keeps a contiguous substring.
_SOURCE_MARKER = re.compile(r"^\s*(?P<marker>\*\(.*?\)\*)\s*:?\s*")
_LEADING_COLON = re.compile(r"^\s*:\s*")
_WIKILINK_TRAILER = re.compile(r"\s*→\s*\[\[.*$")          # requires → THEN [[
_RULE_REF_TAIL = re.compile(r"\s*\*{0,2}\[R[^\]]*\]\*{0,2}\s*\.?\s*$")
_ADVANCES = re.compile(r"\s*\*\*Advances:\*\*.*$")
_TRAILING_PAREN_NOTE = re.compile(r"\s*\*\((?:proposed|gap-fill)[^)]*\)\*\s*$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Clause splitting
# ---------------------------------------------------------------------------

def split_top_level(text: str, sep: str = ";") -> list[str]:
    """Split on `sep` only at nesting depth 0 and outside double quotes.

    The corpus puts semicolons inside parentheses and inside quoted bias
    statements, so a naive `str.split(";")` would cut mid-phrase.
    """
    out: list[str] = []
    buf: list[str] = []
    depth = 0
    in_quote = False
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch == '"':
            in_quote = not in_quote
        if ch == sep and depth == 0 and not in_quote:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return [c for c in (s.strip() for s in out) if c]


def _strip_markers(body: str) -> tuple[str, list[str]]:
    """Remove structural markers from a bullet body → (text, rule_refs)."""
    rule_refs: list[str] = []
    text = _ADVANCES.sub("", body).strip()
    text = _WIKILINK_TRAILER.sub("", text).strip()
    text = _TRAILING_PAREN_NOTE.sub("", text).strip()
    # A bullet may end with several refs; peel them one at a time.
    while True:
        m = _RULE_REF_TAIL.search(text)
        if not m:
            break
        rule_refs.insert(0, m.group(0).strip().strip("*.").strip())
        text = text[: m.start()].rstrip()
    return text.strip(), rule_refs


# ---------------------------------------------------------------------------
# Parsing one exercises.md
# ---------------------------------------------------------------------------

def _join_continuations(lines: list[str], i: int, body: str) -> tuple[str, int]:
    """Absorb the indented wrapped lines of a markdown bullet."""
    j = i + 1
    while j < len(lines):
        m = _CONTINUATION.match(lines[j])
        if not m:
            break
        body += " " + m.group("body")
        j += 1
    return re.sub(r"\s+", " ", body).strip(), j


def parse_drill_bullets(md: str) -> list[dict]:
    """One entry per drill found in an exercises.md, in document order.

    Each entry is {code, source_ref, bullets: [(variant, text, rule_refs), …]}.
    A drill with an EMPTY bullet list is retained on purpose so the caller can
    report it as unprojectable rather than silently dropping it.
    """
    lines = md.splitlines()
    drills: list[dict] = []
    current: dict | None = None
    i = 0
    while i < len(lines):
        line = lines[i]

        # A stage heading closes the current drill (the next drill re-opens one).
        if _STAGE_HEADING.match(line):
            current = None

        m = _DRILL_HEADING.match(line)
        if m:
            title = m.group("title")
            src = re.search(r"\*\((.*)\)\*", title)
            current = {
                "code": m.group("code"),
                "source_ref": f"({src.group(1)})" if src else None,
                "bullets": [],
            }
            drills.append(current)
            i += 1
            continue

        mi = _INLINE_DRILL.match(line)
        if mi:
            body, i = _join_continuations(lines, i, mi.group("rest"))
            sm = _SOURCE_MARKER.match(body)
            source_ref = None
            if sm:
                source_ref = sm.group("marker").strip("*")
                body = body[sm.end():]
            body = _LEADING_COLON.sub("", body)
            text, refs = _strip_markers(body)
            # An inline-form drill IS one bullet; its clauses are its items.
            drills.append({
                "code": mi.group("code"),
                "source_ref": source_ref,
                "bullets": [("either", text, refs)] if text else [],
            })
            current = None
            continue

        mb = _BULLET.match(line)
        if mb and current is not None:
            body, i = _join_continuations(lines, i, mb.group("body"))
            variant = "either"
            if body.startswith(HAND_GLYPH):
                variant, body = "hand", body[len(HAND_GLYPH):].strip()
            elif body.startswith(TOOL_GLYPH):
                variant, body = "tool", body[len(TOOL_GLYPH):].strip()
            # A bullet that is ONLY the Advances marker carries no assertion —
            # `drills.advances_to` already holds it.
            if not body.startswith("**Advances:**"):
                text, refs = _strip_markers(body)
                if text:
                    current["bullets"].append((variant, text, refs))
            continue

        i += 1
    return drills


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def _slug(drill_ref: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", drill_ref.lower()).strip("-")


def content_hash(items: list[dict]) -> str:
    """sha256 over WHAT THE USER TICKS — variant + text + rule refs, in order.

    Deliberately excludes `source_path` / `source_ref`: those are provenance, and
    a cosmetic marker edit must not bump a version and thereby imply the bar moved.
    """
    payload = "\n".join(
        f"{it['variant']}|{it['text']}|{','.join(it['rule_refs'] or [])}" for it in items
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_rubrics() -> tuple[list[dict], dict[str, list[str]]]:
    """Project both libraries → rubric rows. Returns (rubrics, report)."""
    wiki_root = Path(settings.wiki_content_root) / "concepts"
    rubrics: list[dict] = []
    report: dict[str, list[str]] = defaultdict(list)

    for rel, track, prefix in _TRACKS:
        source_path = f"concepts/{rel}"
        md = (wiki_root / rel).read_text(encoding="utf-8")
        bullets_by_drill = parse_drill_bullets(md)
        seen: set[str] = set()

        for entry in bullets_by_drill:
            drill_ref = f"{prefix} {entry['code']}"
            if drill_ref in seen:
                report["duplicate drill headings"].append(drill_ref)
                continue
            seen.add(drill_ref)

            if not entry["bullets"]:
                # NOT silently skipped: a drill written as a paragraph + table
                # (aura D4-a/b) or as a whole stage (ict Stage 7) has no bullet
                # to project. Inventing one would be authoring rubric text.
                report["drills with no projectable bullet"].append(drill_ref)
                continue

            slug = _slug(drill_ref)
            items: list[dict] = []
            for b_ord, (variant, text, refs) in enumerate(entry["bullets"], start=1):
                for clause in split_top_level(text):
                    clause = clause.strip().strip(";").strip()
                    if not clause:
                        continue
                    items.append({
                        "item_key": f"{slug}#{len(items) + 1}",
                        "ordinal": len(items) + 1,
                        "bullet_ordinal": b_ord,
                        "variant": variant,
                        "text": clause,
                        "rule_refs": refs or None,
                    })
                    if "[[" in clause:
                        report["items carrying a wikilink"].append(f"{drill_ref}#{len(items)}")

            if not items:
                report["drills with no projectable bullet"].append(drill_ref)
                continue

            rubrics.append({
                "slug": slug,
                "drill_ref": drill_ref,
                "track": track,
                "content_hash": content_hash(items),
                "source_path": source_path,
                "source_ref": entry["source_ref"],
                "items": items,
            })

    return rubrics, report


# ---------------------------------------------------------------------------
# The NO-DRIFT proof
# ---------------------------------------------------------------------------

def _normalised_bullets() -> dict[str, list[str]]:
    """Every bullet of both libraries, whitespace-normalised, keyed by file.

    The comparison target for the no-drift proof: a rubric item must be a
    contiguous substring of one of these. Continuations are joined with a single
    space (which is why the raw file text is not the right target).
    """
    wiki_root = Path(settings.wiki_content_root) / "concepts"
    out: dict[str, list[str]] = {}
    for rel, _track, _prefix in _TRACKS:
        lines = (wiki_root / rel).read_text(encoding="utf-8").splitlines()
        bullets: list[str] = []
        i = 0
        while i < len(lines):
            m = _BULLET.match(lines[i])
            if m:
                body, i = _join_continuations(lines, i, m.group("body"))
                bullets.append(body)
                continue
            i += 1
        out[f"concepts/{rel}"] = bullets
    return out


def verify_no_drift(rubrics: list[dict]) -> list[str]:
    """Every item's text must appear VERBATIM in a wiki bullet. Returns failures.

    This is the assertion that makes "no rubric text is authored in the app"
    checkable rather than merely claimed: an item whose text is not a contiguous
    substring of a source bullet is a BUG in this parser.
    """
    bullets = _normalised_bullets()
    failures: list[str] = []
    for r in rubrics:
        haystack = bullets.get(r["source_path"], [])
        for item in r["items"]:
            if not any(item["text"] in b for b in haystack):
                failures.append(f"{item['item_key']}: {item['text'][:90]!r}")
    return failures


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

async def _upsert(session: AsyncSession, rubrics: list[dict]) -> dict[str, int]:
    """UPSERT by slug. Version bumps ONLY on a content_hash change."""
    existing = {
        r.slug: r
        for r in (await session.execute(select(Rubric))).scalars().all()
    }
    stats = {"inserted": 0, "bumped": 0, "unchanged": 0, "pruned": 0}

    for spec in rubrics:
        row = existing.get(spec["slug"])
        if row is None:
            row = Rubric(
                slug=spec["slug"], drill_ref=spec["drill_ref"], track=spec["track"],
                version=1, content_hash=spec["content_hash"],
                source_path=spec["source_path"], source_ref=spec["source_ref"],
            )
            row.items = [RubricItem(**it) for it in spec["items"]]
            session.add(row)
            stats["inserted"] += 1
            continue

        # Provenance refreshes in place — it is not part of the bar.
        row.drill_ref = spec["drill_ref"]
        row.track = spec["track"]
        row.source_path = spec["source_path"]
        row.source_ref = spec["source_ref"]

        if row.content_hash == spec["content_hash"]:
            stats["unchanged"] += 1
            continue

        # The projected text changed → this is a NEW BAR. Bump, then replace the
        # items. Grades already written keep their `rubric_version`, so what they
        # were judged against stays identifiable.
        row.version += 1
        row.content_hash = spec["content_hash"]
        # CLEAR + FLUSH BEFORE re-adding. A plain `row.items = [...]` fails: the
        # unit of work emits this mapper's INSERTs before its DELETEs, so the new
        # items collide with the old ones on `ux_rubric_items_key` (item_key is
        # positional, so #1 always already exists). Proven by
        # tests/test_rubrics.py::test_reseed_after_a_wiki_edit_bumps_the_version.
        row.items.clear()
        await session.flush()
        row.items = [RubricItem(**it) for it in spec["items"]]
        stats["bumped"] += 1

    slugs = [r["slug"] for r in rubrics]
    pruned = await session.execute(delete(Rubric).where(Rubric.slug.notin_(slugs)))
    stats["pruned"] = pruned.rowcount or 0
    await session.commit()
    return stats


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def seed(dry_run: bool = False) -> int:
    rubrics, report = build_rubrics()

    by_track: dict[str, int] = defaultdict(int)
    by_variant: dict[str, int] = defaultdict(int)
    total_items = 0
    for r in rubrics:
        by_track[r["track"]] += 1
        total_items += len(r["items"])
        for it in r["items"]:
            by_variant[it["variant"]] += 1

    print(
        f"Projected {len(rubrics)} rubrics "
        f"({', '.join(f'{k}={v}' for k, v in sorted(by_track.items()))}) "
        f"and {total_items} items "
        f"({', '.join(f'{k}={v}' for k, v in sorted(by_variant.items()))})"
    )

    drift = verify_no_drift(rubrics)
    if drift:
        print(f"NO-DRIFT CHECK FAILED — {len(drift)} item(s) are not verbatim wiki text:")
        for f in drift[:20]:
            print(f"  ✗ {f}")
        return 1
    print(f"No-drift check: all {total_items} item texts appear verbatim in a wiki bullet ✓")

    # BOTH directions of the drill↔rubric asymmetry, reported like
    # seed_drills.py's orphan refs rather than hidden. `build_drills()` is
    # imported in-memory (the idiom seed_drills itself uses for the concept seed),
    # so this needs no DB and can never disagree with what seed_drills produces.
    drill_refs = {d["drill_ref"] for d in build_drills()[0]}
    produced = {r["drill_ref"] for r in rubrics}
    if no_rubric := sorted(drill_refs - produced):
        report["drills the map lists with NO rubric"] = no_rubric
    if no_drill := sorted(produced - drill_refs):
        report["rubrics whose drill the map table omits"] = no_drill

    for label, entries in sorted(report.items()):
        print(f"{label} ({len(entries)}): {entries}")

    if dry_run:
        print("--dry-run: database untouched.")
        return 0

    async with AsyncSessionLocal() as session:
        stats = await _upsert(session, rubrics)
    await engine.dispose()

    print(
        f"Seeded rubrics: {stats['inserted']} inserted · {stats['bumped']} version-bumped · "
        f"{stats['unchanged']} unchanged · {stats['pruned']} pruned."
    )
    return 0


async def show(drill_ref: str) -> int:
    """Print one drill's projected bar — the content pass's before/after view."""
    rubrics, _ = build_rubrics()
    match = next((r for r in rubrics if r["drill_ref"] == drill_ref), None)
    if match is None:
        print(f"No rubric projected for {drill_ref!r}.")
        return 1
    print(f"{match['drill_ref']}  [{match['source_ref'] or 'no source marker'}]  "
          f"hash {match['content_hash'][:12]}")
    for it in match["items"]:
        refs = f"  {it['rule_refs']}" if it["rule_refs"] else ""
        print(f"  {it['ordinal']:>2}. ({it['variant']:<6} b{it['bullet_ordinal']}) {it['text']}{refs}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report the projection, touch no DB")
    ap.add_argument("--show", metavar="DRILL_REF", help='print one rubric, e.g. "aura D1-a"')
    args = ap.parse_args()
    if args.show:
        return asyncio.run(show(args.show))
    return asyncio.run(seed(dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
