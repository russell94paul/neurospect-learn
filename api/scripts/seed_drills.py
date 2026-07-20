"""Idempotent seed for the `drills` catalog (Phase 5e-1).

Source of truth: the "## Drill → concept → ladder-stage map" table at the foot of
BOTH wiki exercise libraries (READ-ONLY — never written back):
  - concepts/mastery/aura/exercises.md
  - concepts/mastery/ict-course/exercises.md

Each already-tabular row is `| Drill | Concept | Advances to | Rep target |`.
The `drills` table is a **projection** of these tables — the drill *definitions*
stay canonical in the wiki. Compound drill cells are expanded to atomic refs so
each row's `drill_ref` matches the convention in `concepts.drill_refs`:
  - "D4-a/b"     → D4-a, D4-b            (slash suffixes)
  - "D6-a/b/c"   → D6-a, D6-b, D6-c
  - "D0-a…e"     → D0-a … D0-e           (letter ellipsis range)
  - "T-01…14"    → T-01 … T-14           (numeric ellipsis range, zero-padded)
  - "Stage 7"    → S7                    (matches concepts' "ict-course S7")

`drill_ref` = f"{'aura'|'ict-course'} {code}" (hyphen prefix, matching the
concept seed). `track` = the enum-ish value `aura|ict_course` (underscore).
`concept_slugs` is a soft back-link derived from the concept seed's `drill_refs`
(single source of truth — imported in-memory, no DB round-trip), so it always
agrees with `concepts.drill_refs`.

Run:  poetry run python -m scripts.seed_drills          (from api/)

Idempotent: UPSERT on `drill_ref` (ON CONFLICT DO UPDATE); after upserting the
current corpus it DELETES any `drills` rows whose drill_ref is no longer produced
(authoritative re-seed, mirroring ingest_content.py).
"""

import asyncio
import re
from collections import defaultdict
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models.drill import Drill
from scripts.seed_concepts import CONCEPTS as SEED_CONCEPTS

# (relative path under concepts/, track enum value, drill_ref prefix)
_TRACKS = [
    ("mastery/aura/exercises.md", "aura", "aura"),
    ("mastery/ict-course/exercises.md", "ict_course", "ict-course"),
]

_MAP_HEADING = re.compile(r"^#{1,6}\s+Drill\s*→\s*concept\s*→\s*ladder-stage map", re.IGNORECASE)
_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_SEP_ROW = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
_ELLIPSIS = ("…", "...")


def _clean(cell: str) -> str:
    """Strip markdown emphasis/backticks from a table cell, collapse spaces."""
    c = cell.replace("*", "").replace("`", "").strip()
    return re.sub(r"\s+", " ", c)


def _expand(cell: str) -> list[str]:
    """A Drill-column cell → the list of atomic drill codes it denotes."""
    c = _clean(cell)

    m = re.match(r"stage\s+(\d+)", c, re.IGNORECASE)
    if m:
        return [f"S{m.group(1)}"]

    for ell in _ELLIPSIS:
        if ell in c:
            left, right = (s.strip() for s in c.split(ell, 1))
            m2 = re.match(r"(.*?)([A-Za-z0-9]+)$", left)
            if not m2:
                return [c]
            prefix, start = m2.group(1), m2.group(2)
            if start.isdigit():
                width = len(start)
                return [f"{prefix}{str(i).zfill(width)}" for i in range(int(start), int(right) + 1)]
            return [f"{prefix}{chr(o)}" for o in range(ord(start.lower()), ord(right.lower()) + 1)]

    if "/" in c:
        parts = [p.strip() for p in c.split("/")]
        head = parts[0]
        m3 = re.match(r"(.*-)([A-Za-z0-9]+)$", head)
        if not m3:
            return [c]
        prefix = m3.group(1)
        return [head] + [f"{prefix}{p}" for p in parts[1:]]

    return [c]


def _stage_code(code: str) -> str | None:
    """The track's own stage number for a drill code (for /drills grouping)."""
    m = re.match(r"D(\d+)", code)
    if m:
        return m.group(1)
    if code.startswith("T"):
        return "6"  # ict-course tape reading is Stage 6
    m = re.match(r"S(\d+)", code)
    if m:
        return m.group(1)
    return None


def _parse_map_table(md: str) -> list[dict]:
    """Extract the drill-map table rows from one exercises.md body."""
    lines = md.splitlines()
    # Find the map heading, then the first table under it.
    i = next((k for k, ln in enumerate(lines) if _MAP_HEADING.match(ln)), None)
    if i is None:
        raise SystemExit("Drill-map heading not found in exercises file")

    rows: list[list[str]] = []
    in_table = False
    for ln in lines[i + 1:]:
        if _TABLE_ROW.match(ln):
            in_table = True
            if _SEP_ROW.match(ln):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows.append(cells)
        elif in_table:
            break  # table ended
    if not rows:
        raise SystemExit("Drill-map table has no rows")

    # First row is the header (Drill | Concept | Advances to | Rep target).
    return [
        {"drill": r[0], "concept": r[1], "advances": r[2], "rep_target": r[3]}
        for r in rows[1:]
        if len(r) >= 4
    ]


def _build_ref_to_slugs() -> dict[str, list[str]]:
    """Reverse the concept seed's drill_refs → {drill_ref: [concept slug, ...]}."""
    out: dict[str, list[str]] = defaultdict(list)
    for c in SEED_CONCEPTS:
        for ref in c.get("drill_refs") or []:
            out[ref].append(c["slug"])
    return out


def build_drills() -> tuple[list[dict], list[str]]:
    """Parse both exercise libraries → drill rows. Returns (drills, orphan_refs)
    where orphan_refs are concept.drill_refs with no drill row (transparency)."""
    wiki_root = Path(settings.wiki_content_root) / "concepts"
    ref_to_slugs = _build_ref_to_slugs()

    drills: list[dict] = []
    seen: set[str] = set()
    order = 0
    for rel, track, prefix in _TRACKS:
        md = (wiki_root / rel).read_text(encoding="utf-8")
        for row in _parse_map_table(md):
            title = _clean(row["concept"])
            advances = _clean(row["advances"])
            rep_target = _clean(row["rep_target"]) or None
            for code in _expand(row["drill"]):
                drill_ref = f"{prefix} {code}"
                if drill_ref in seen:
                    continue
                seen.add(drill_ref)
                drills.append({
                    "drill_ref": drill_ref,
                    "track": track,
                    "stage_code": _stage_code(code),
                    "title": title,
                    "advances_to": advances or None,
                    "rep_target": rep_target,
                    "concept_slugs": sorted(ref_to_slugs.get(drill_ref, [])) or None,
                    "sort_order": order,
                })
                order += 1

    produced = {d["drill_ref"] for d in drills}
    orphans = sorted(ref for ref in ref_to_slugs if ref not in produced)
    return drills, orphans


async def _upsert(drills: list[dict]) -> None:
    refs = [d["drill_ref"] for d in drills]
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(Drill).values(drills)
        update_cols = {
            c: getattr(stmt.excluded, c)
            for c in (
                "track", "stage_code", "title", "advances_to",
                "rep_target", "concept_slugs", "sort_order",
            )
        }
        stmt = stmt.on_conflict_do_update(index_elements=["drill_ref"], set_=update_cols)
        await session.execute(stmt)
        # Authoritative: drop rows for drills no longer produced.
        await session.execute(delete(Drill).where(Drill.drill_ref.notin_(refs)))
        await session.commit()
    await engine.dispose()


async def seed() -> None:
    drills, orphans = build_drills()
    by_track = defaultdict(int)
    for d in drills:
        by_track[d["track"]] += 1
    print(f"Parsed {len(drills)} drills: " + ", ".join(f"{k}={v}" for k, v in sorted(by_track.items())))
    if orphans:
        # Concept drill_refs with no drill row — e.g. the aura Stage-0 drills the
        # aura map table omits. Transparent, not invented (no-drift).
        print(f"Concept refs with no drill row ({len(orphans)}): {orphans}")

    await _upsert(drills)
    print(f"Seeded/updated {len(drills)} drills (stale rows pruned).")


if __name__ == "__main__":
    asyncio.run(seed())
