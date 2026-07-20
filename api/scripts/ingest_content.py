"""Ingest curated wiki markdown into the `content_pages` table (Phase 5d).

Source of truth: the neurospect-wiki checkout at ``settings.wiki_content_root``
(READ-ONLY — this job NEVER writes back to the wiki, and never reads outside the
curated ``concepts/`` dirs below; ``sources/`` and ``vault/`` are never touched).

Run:  poetry run python -m scripts.ingest_content        (from api/)
      poetry run python -m scripts.ingest_content --dry-run   (parse + report, no DB)

Idempotent: UPSERT on `slug` (ON CONFLICT DO UPDATE); after upserting the current
corpus it DELETES any content_pages rows whose slug is no longer produced, so a
re-run is authoritative (re-ingest replaces).

Slug scheme (the load-bearing 5d decision — see learning-platform.md §Content
delivery §5d as-built):
  - Take the file's path relative to ``concepts/``, drop ``.md``.
  - Slug = the last path segment, lowercased, with a leading ``NN-`` lesson
    prefix stripped (so ``course/.../04-daily-bias`` → ``daily-bias``).
  - ``README.md`` is represented by its parent directory name
    (``advanced/README`` → ``advanced``; ``mastery/unified/README`` → ``unified``).
  - De-collision: where two files would produce the same slug (the mastery
    ``tracker``/``learning-path``/``rules``/``exercises`` meta-files), extend each
    colliding slug leftward one path segment at a time until unique
    (``mastery/aura/tracker`` → ``aura-tracker``). Deterministic, order-independent.

This scheme makes every non-null ``concepts.content_slug`` seeded in 5c resolve
against a real ``content_pages.slug`` with NO change to the seed — 25 are plain
wiki basenames, and ``daily-bias`` / ``session-kill-zones`` are the numeric-prefix-
stripped course-lesson basenames. Verified by the reconciliation SQL post-ingest.

Wikilink resolution: each internal ``[[target]]`` / ``[[target|display]]`` in the
body is resolved to a content-page slug and stored (deduped) in
``wikilink_targets`` — only targets that resolve to an ingested page are kept
(out-of-corpus refs like ``[[CLAUDE]]`` or ``[[entities/...]]`` and anchor-only
``[[#Section]]`` links are dropped). The backend owns slug derivation; the
frontend resolves the raw ``[[...]]`` tokens in the body by *lookup* against the
page list (slug + source_path), never by re-deriving the scheme.
"""

import argparse
import asyncio
import re
from collections import defaultdict
from pathlib import Path

import frontmatter
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models.content_page import ContentPage

# Curated top-level content dirs under concepts/ (category = the dir name).
CONTENT_DIRS = ["course", "entry-models", "mastery", "advanced", "business-logic", "aura"]

_NUM_PREFIX = re.compile(r"^\d+[-_]")
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
# A leading YAML frontmatter block (--- … ---), for the tolerant fallback.
_FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)

# Files whose frontmatter YAML was malformed and got body-only parsing.
_yaml_fallbacks: list[str] = []


def _load(f: Path) -> tuple[dict, str]:
    """(metadata, body) — tolerant of malformed frontmatter YAML.

    We never edit sources (wiki Rule #1), so a page with un-parseable
    frontmatter (e.g. an alias list with unquoted parens) falls back to
    body-only: strip the leading ``---…---`` block and use empty metadata. The
    title still resolves from the H1; only secondary frontmatter (tags) is lost.
    """
    try:
        post = frontmatter.load(f)
        return post.metadata, post.content
    except Exception:
        _yaml_fallbacks.append(f.name)
        text = f.read_text(encoding="utf-8")
        return {}, _FRONTMATTER.sub("", text, count=1)


# ---------------------------------------------------------------------------
# Pure slug / wikilink helpers (mirrored — as lookups only — on the frontend)
# ---------------------------------------------------------------------------

def _norm_segments(rel_no_ext: str) -> list[str]:
    """Path segments under concepts/, numeric-prefix-stripped + lowercased.

    A trailing ``README`` segment is dropped so the file is represented by its
    parent dir (``advanced/README`` → ``['advanced']``).
    """
    parts = rel_no_ext.split("/")
    if parts[-1].lower() == "readme":
        parts = parts[:-1]
    return [_NUM_PREFIX.sub("", p).lower() for p in parts]


def _derive_slugs(rel_paths: list[str]) -> dict[str, str]:
    """Deterministic slug per file (relative path under concepts/, no .md).

    Minimal disambiguation: start from the last segment and extend leftward one
    path segment at a time only for files that still collide. When files collide,
    the **unique shallowest** file keeps the shorter slug (a depth tiebreak: a
    canonical top-level concept page like ``entry-models/consolidation-model``
    beats the nested course lesson ``course/…/02-consolidation-model``, so the
    5c-seeded ``content_slug='consolidation-model'`` resolves to the model page).
    If several colliders share the min depth (e.g. the three ``mastery/*/tracker``
    files), all of them extend. Order-independent; iterates to a fixpoint.
    """
    segs = {rel: _norm_segments(rel) for rel in rel_paths}
    depth = {rel: rel.count("/") + 1 for rel in rel_paths}
    level = {rel: 1 for rel in rel_paths}

    def make(rel: str) -> str:
        s = segs[rel]
        return "-".join(s[-min(level[rel], len(s)):])

    while True:
        current = {rel: make(rel) for rel in rel_paths}
        groups: dict[str, list[str]] = defaultdict(list)
        for rel, slug in current.items():
            groups[slug].append(rel)
        to_extend: list[str] = []
        for rels in groups.values():
            if len(rels) <= 1:
                continue
            min_depth = min(depth[r] for r in rels)
            winners = [r for r in rels if depth[r] == min_depth]
            losers = rels if len(winners) > 1 else [r for r in rels if r not in winners]
            to_extend += [r for r in losers if level[r] < len(segs[r])]
        if not to_extend:
            return current
        for rel in to_extend:
            level[rel] += 1


def _normalize_target(raw: str) -> str | None:
    """A raw ``[[...]]`` inner string → a path/basename token, or None.

    Strips a ``|display`` alias and a ``#anchor``; drops a leading ``concepts/``
    and a trailing ``.md``. Anchor-only links (``[[#Section]]``) return None.
    """
    t = raw.split("|", 1)[0].split("#", 1)[0].strip()
    if not t:
        return None
    if t.lower().endswith(".md"):
        t = t[:-3]
    if t.lower().startswith("concepts/"):
        t = t[len("concepts/"):]
    t = t.strip("/")
    return t or None


def _resolve_target(
    token: str, path_to_slug: dict[str, str], basename_to_slug: dict[str, str]
) -> str | None:
    """Resolve a normalized wikilink token to a content-page slug (or None)."""
    key = token.lower()
    if "/" in key:
        return path_to_slug.get(key)
    return basename_to_slug.get(_NUM_PREFIX.sub("", key))


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def _parse_pages(wiki_root: Path) -> list[dict]:
    concepts_root = wiki_root / "concepts"
    if not concepts_root.is_dir():
        raise SystemExit(f"Wiki concepts dir not found: {concepts_root}")

    files: list[Path] = []
    for d in CONTENT_DIRS:
        files.extend(sorted((concepts_root / d).rglob("*.md")))

    # rel path under concepts/, forward slashes, no extension
    rel_no_ext = {f: f.relative_to(concepts_root).with_suffix("").as_posix() for f in files}
    slugs = _derive_slugs(list(rel_no_ext.values()))

    # Resolution indexes
    path_to_slug = {rel.lower(): slugs[rel] for rel in rel_no_ext.values()}
    basename_to_slug: dict[str, str] = {}
    basename_dupes: set[str] = set()
    for rel in rel_no_ext.values():
        base = _NUM_PREFIX.sub("", rel.split("/")[-1]).lower()
        if base == "readme":
            continue
        if base in basename_to_slug and basename_to_slug[base] != slugs[rel]:
            basename_dupes.add(base)
        basename_to_slug[base] = slugs[rel]
    for dup in basename_dupes:  # ambiguous bare basenames are not resolvable
        basename_to_slug.pop(dup, None)

    pages: list[dict] = []
    for f in files:
        rel = rel_no_ext[f]
        meta, body = _load(f)

        h1 = _H1.search(body)
        title = (
            (h1.group(1).strip() if h1 else None)
            or (meta.get("aliases") or [None])[0]
            or slugs[rel]
        )

        tags = meta.get("tags")
        if isinstance(tags, str):
            tags = [tags]

        raw_targets = {_normalize_target(m) for m in _WIKILINK.findall(body)}
        resolved = sorted(
            {
                s
                for t in raw_targets
                if t and (s := _resolve_target(t, path_to_slug, basename_to_slug))
            }
        )

        pages.append(
            {
                "slug": slugs[rel],
                "title": title,
                "body": body,
                "u_stage": None,  # not load-bearing; no frontmatter carries it
                "tier": meta.get("tier"),  # nearly always None in this corpus
                "label": meta.get("label"),
                "category": rel.split("/")[0],
                "tags": list(tags) if tags else None,
                "wikilink_targets": resolved or None,
                "source_path": f.relative_to(wiki_root).as_posix(),
            }
        )
    return pages


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

async def _upsert(pages: list[dict]) -> None:
    slugs = [p["slug"] for p in pages]
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(ContentPage).values(pages)
        update_cols = {
            c: getattr(stmt.excluded, c)
            for c in (
                "title", "body", "u_stage", "tier", "label", "category",
                "tags", "wikilink_targets", "source_path",
            )
        }
        stmt = stmt.on_conflict_do_update(index_elements=["slug"], set_=update_cols)
        await session.execute(stmt)
        # Authoritative: drop rows for pages no longer in the corpus.
        await session.execute(delete(ContentPage).where(ContentPage.slug.notin_(slugs)))
        await session.commit()
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest wiki markdown → content_pages.")
    parser.add_argument("--dry-run", action="store_true", help="parse + report, no DB write")
    args = parser.parse_args()

    wiki_root = Path(settings.wiki_content_root)
    pages = _parse_pages(wiki_root)

    # Report
    dupe_slugs = [s for s, n in _count(p["slug"] for p in pages).items() if n > 1]
    print(f"Wiki root: {wiki_root}")
    print(f"Parsed {len(pages)} pages across {len(CONTENT_DIRS)} categories.")
    by_cat = _count(p["category"] for p in pages)
    for cat in CONTENT_DIRS:
        print(f"  {cat:16} {by_cat.get(cat, 0)}")
    # A slug is "de-collided" when it differs from its file's own level-1 candidate.
    disambiguated = sorted(
        f"{p['slug']}  ←  {p['source_path']}"
        for p in pages
        if p["slug"] != "-".join(_norm_segments(
            p["source_path"].removeprefix("concepts/").removesuffix(".md")
        )[-1:])
    )
    if disambiguated:
        print("De-collided slugs:")
        for line in disambiguated:
            print(f"  {line}")
    if _yaml_fallbacks:
        print(f"Body-only fallback (malformed frontmatter): {sorted(set(_yaml_fallbacks))}")
    if dupe_slugs:
        raise SystemExit(f"FATAL: duplicate slugs produced: {dupe_slugs}")

    if args.dry_run:
        print("[dry-run] no DB write.")
        return

    asyncio.run(_upsert(pages))
    print(f"Ingested/updated {len(pages)} content pages (stale rows pruned).")


def _count(it) -> dict:
    d: dict = defaultdict(int)
    for x in it:
        d[x] += 1
    return d


if __name__ == "__main__":
    main()
