"""Project the Aura session-runner content from the wiki into the app (Phase S1).

Source of truth: the neurospect-wiki checkout at ``settings.wiki_content_root``
(READ-ONLY — this job NEVER writes back to the wiki).

Run:  poetry run python -m scripts.project_aura_runner          (from api/)
      poetry run python -m scripts.project_aura_runner --check  (fail if stale)

WHY A FILE AND NOT THE DATABASE
-------------------------------
S1 ships a **read-only** runner: no migration, no new table, no mutating
endpoint. So this is a *projection to a build artifact*, not a seed. The output
lands at ``app/src/data/aura-runner.json`` and is imported by the bundle, which
means the runner has **no API dependency at all** — it renders with the backend
down, which is exactly what you want from a screen you keep open beside another
application for an hour at a time.

It mirrors the projection convention the rubric layer already established
(``scripts/seed_rubrics.py``): the wiki stays canonical, a re-run propagates
edits, and there is no second copy of the model content to drift. The ONLY
difference is the sink.

⚠️ Re-running does not touch ``content_pages``. The three new wiki pages will
additionally appear in the Library the next time ``scripts.ingest_content`` is
run (they sit under ``concepts/mastery/``, which that job globs) — additive and
harmless, but it is a DB write and therefore NOT part of S1.
"""

import argparse
import json
import re
from pathlib import Path

import frontmatter

from app.config import settings

# Repo root = neurospect-learn/ (api/scripts/x.py -> parents[2]).
_OUT = Path(__file__).resolve().parents[2] / "app" / "src" / "data" / "aura-runner.json"

CHECKLIST = "concepts/mastery/aura/checklist.md"
RULES = "concepts/mastery/aura/rules.md"
SETUP = "concepts/mastery/aura/tradezella-setup.md"
MAPPING = "concepts/mastery/aura/tradezella-rule-mapping.md"
MARKUP = "concepts/mastery/aura/chart-markup.md"

_H2 = re.compile(r"^##\s+(?!#)(.+?)\s*$")
_H3 = re.compile(r"^###\s+(?!#)(.+?)\s*$")
_TASK = re.compile(r"^-\s+\[[ xX]\]\s+(.*)$")
_NUMBERED = re.compile(r"^(\d+)\.\s+(.*)$")
_BULLET = re.compile(r"^-\s+(?!\[[ xX]\])(.*)$")
# A phase heading: "## 3. Entry [R30–R34]"
_PHASE = re.compile(r"^(\d+)\.\s+(.*?)(?:\s*\[([^\]]*)\])?$")
# Inline rule refs, e.g. **[R47–48, R54]** or **[R30, R33]**
_REFS = re.compile(r"\*\*\[([^\]]+)\]\*\*")
_FENCE = re.compile(r"^```")

# Which checklist phases repeat per setup vs. run once per replayed day. This is
# the split the tracker's open question Q5 asked for, and it is declared here
# (not inferred in the UI) so one answer serves the runner and the docs.
PHASE_SCOPE = {
    0: "day",    # pre-market readiness
    1: "day",    # HTF framing
    2: "day",    # confirmation — the bias is a day-level read
    3: "setup",  # entry
    4: "setup",  # in-trade management
    5: "setup",  # exit
    6: "any",    # circuit breakers — checkable at any moment
    7: "day",    # post-market review
}


def _read(rel: str) -> str:
    p = Path(settings.wiki_content_root) / rel
    if not p.is_file():
        raise SystemExit(f"Missing wiki source: {p}")
    return frontmatter.load(p).content


# ---------------------------------------------------------------------------
# Rule-reference expansion
# ---------------------------------------------------------------------------

def _expand_refs(raw: str) -> list[str]:
    """"R47–48, R54" -> ["R47","R48","R54"]; "R18–R25" -> R18..R25.

    The corpus writes ranges with an en-dash and drops the repeated ``R`` on the
    right-hand side about half the time, so both forms have to work. Anything
    unparseable is dropped rather than guessed — a wrong rule reference on a
    checklist item is worse than a missing one.
    """
    out: list[str] = []
    for part in re.split(r"[,·]", raw):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"R?(\d+)\s*[–—-]\s*R?(\d+)", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo <= hi and hi - lo < 40:
                out += [f"R{n}" for n in range(lo, hi + 1)]
            continue
        m = re.fullmatch(r"R(\d+)", part)
        if m:
            out.append(f"R{m.group(1)}")
    # de-dupe, preserve order
    seen: set[str] = set()
    return [r for r in out if not (r in seen or seen.add(r))]


def _item(text: str) -> dict:
    refs: list[str] = []
    for m in _REFS.finditer(text):
        refs += _expand_refs(m.group(1))
    hard = "hard gate" in text.lower()
    seen: set[str] = set()
    return {
        "text": text.strip(),
        "ruleRefs": [r for r in refs if not (r in seen or seen.add(r))],
        "hardGate": hard,
    }


# ---------------------------------------------------------------------------
# Generic section parser (used for setup / markup / mapping)
# ---------------------------------------------------------------------------

def _table(lines: list[str], i: int) -> tuple[dict | None, int]:
    """Parse a GFM table starting at lines[i]; returns (table, next_index)."""
    if not lines[i].lstrip().startswith("|"):
        return None, i
    if i + 1 >= len(lines) or not re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
        return None, i

    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    headers = cells(lines[i])
    rows: list[list[str]] = []
    j = i + 2
    while j < len(lines) and lines[j].lstrip().startswith("|"):
        rows.append(cells(lines[j]))
        j += 1
    return {"headers": headers, "rows": rows}, j


def _sections(body: str) -> list[dict]:
    """Split a page into ## sections carrying items, tables and paragraphs.

    ⚠️ Paragraphs are joined across SOURCE LINES and broken only on a blank line
    or a structural element. The wiki hard-wraps its prose at ~100 columns, so
    treating each physical line as its own paragraph renders the page as a
    column of orphaned fragments — which is exactly what the first render walk
    showed at 400px, and a defect no assertion about text content would catch.
    """
    lines = body.splitlines()
    sections: list[dict] = []
    cur: dict | None = None
    buf: list[str] = []
    in_fence = False
    i = 0

    def flush() -> None:
        if cur is not None and buf:
            cur["paras"].append(" ".join(buf))
        buf.clear()

    while i < len(lines):
        line = lines[i]
        if _FENCE.match(line.strip()):
            flush()
            in_fence = not in_fence
            i += 1
            continue
        if not in_fence:
            h = _H2.match(line)
            if h:
                flush()
                cur = {"title": h.group(1), "items": [], "tables": [], "paras": []}
                sections.append(cur)
                i += 1
                continue
            if cur is not None:
                tbl, nxt = _table(lines, i)
                if tbl:
                    flush()
                    cur["tables"].append(tbl)
                    i = nxt
                    continue
                t = _TASK.match(line)
                if t:
                    flush()
                    text = t.group(1)
                    # absorb indented continuation lines
                    while i + 1 < len(lines) and re.match(r"^\s{2,}\S", lines[i + 1]):
                        i += 1
                        text += " " + lines[i].strip()
                    cur["items"].append(_item(text))
                    i += 1
                    continue
                stripped = line.strip()
                if not stripped or stripped.startswith(("|", "#", ">", "---")):
                    flush()
                else:
                    buf.append(stripped)
        i += 1
    flush()
    return sections


# ---------------------------------------------------------------------------
# checklist.md — the runner's spine
# ---------------------------------------------------------------------------

def _parse_checklist(body: str) -> dict:
    lines = body.splitlines()
    phases: list[dict] = []
    cur: dict | None = None
    card: list[str] = []
    in_card = False
    in_fence = False

    for i, line in enumerate(lines):
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
            if in_card and not in_fence:
                in_card = False
            continue
        if in_fence:
            if in_card:
                card.append(line)
            continue

        h = _H2.match(line)
        if h:
            m = _PHASE.match(h.group(1))
            if m:
                idx = int(m.group(1))
                cur = {
                    "index": idx,
                    "title": m.group(2).strip(),
                    "ruleRefs": _expand_refs(m.group(3) or ""),
                    "scope": PHASE_SCOPE.get(idx, "day"),
                    "items": [],
                }
                phases.append(cur)
            else:
                cur = None
                if h.group(1).lower().startswith("per-trade card"):
                    in_card = True
            continue

        if cur is not None:
            t = _TASK.match(line)
            if t:
                text = t.group(1)
                j = i
                while j + 1 < len(lines) and re.match(r"^\s{2,}\S", lines[j + 1]):
                    j += 1
                    text += " " + lines[j].strip()
                cur["items"].append(_item(text))

    if not phases:
        raise SystemExit("checklist.md: parsed 0 phases — the heading shape changed.")
    return {"phases": phases, "perTradeCard": "\n".join(card).strip()}


# ---------------------------------------------------------------------------
# rules.md — the R## lookup + the divergences
# ---------------------------------------------------------------------------

def _parse_rules(body: str) -> tuple[list[dict], list[dict]]:
    lines = body.splitlines()
    rules: list[dict] = []
    divergences: list[dict] = []
    section = ""
    group = ""
    in_div = False
    in_fence = False
    i = 0

    while i < len(lines):
        line = lines[i]
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue

        h2 = _H2.match(line)
        if h2:
            title = h2.group(1)
            in_div = title.lower().startswith("divergences")
            if not in_div and re.match(r"^[A-E]\.\s", title):
                section = title
            i += 1
            continue

        h3 = _H3.match(line)
        if h3:
            group = h3.group(1)
            i += 1
            continue

        if in_div:
            b = _BULLET.match(line)
            if b:
                text = b.group(1)
                while i + 1 < len(lines) and re.match(r"^\s{2,}\S", lines[i + 1]):
                    i += 1
                    text += " " + lines[i].strip()
                lm = re.match(r"^\*\*(.+?):\*\*\s*(.*)$", text)
                divergences.append(
                    {"label": lm.group(1), "text": lm.group(2)} if lm
                    else {"label": "", "text": text}
                )
            i += 1
            continue

        n = _NUMBERED.match(line)
        if n:
            text = n.group(2)
            while i + 1 < len(lines) and re.match(r"^\s{2,}\S", lines[i + 1]):
                i += 1
                text += " " + lines[i].strip()
            rules.append(
                {
                    "id": f"R{n.group(1)}",
                    "n": int(n.group(1)),
                    "section": section,
                    "group": group,
                    "text": text.strip(),
                    # dOoMeR's own hedges, preserved rather than hardened
                    "soft": "*(soft" in text,
                    "flagged": "*(flagged" in text,
                }
            )
        i += 1

    if len(rules) < 50:
        raise SystemExit(f"rules.md: parsed only {len(rules)} rules — expected 54.")
    if not divergences:
        raise SystemExit("rules.md: parsed 0 divergences — §Divergences must surface in the runner.")
    return rules, divergences


# ---------------------------------------------------------------------------

def build() -> dict:
    checklist = _parse_checklist(_read(CHECKLIST))
    rules, divergences = _parse_rules(_read(RULES))

    # Every rule a checklist item cites must resolve, or the runner would render
    # a dead reference. Fail loudly here rather than silently in the browser.
    known = {r["id"] for r in rules}
    cited = {
        ref
        for p in checklist["phases"]
        for src in [p["ruleRefs"], *[it["ruleRefs"] for it in p["items"]]]
        for ref in src
    }
    if missing := sorted(cited - known, key=lambda s: int(s[1:])):
        raise SystemExit(f"checklist cites rules that rules.md does not define: {missing}")

    return {
        "generated": {
            "sources": [CHECKLIST, RULES, SETUP, MAPPING, MARKUP],
            "note": (
                "GENERATED by api/scripts/project_aura_runner.py from the wiki. "
                "Do not edit by hand — edit the wiki page and re-run."
            ),
        },
        "checklist": checklist,
        "rules": rules,
        "divergences": divergences,
        "setup": {"sections": _sections(_read(SETUP))},
        "mapping": {"sections": _sections(_read(MAPPING))},
        "markup": {"sections": _sections(_read(MARKUP))},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Project wiki Aura content -> app JSON.")
    ap.add_argument("--check", action="store_true", help="fail if the committed file is stale")
    args = ap.parse_args()

    data = build()
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not _OUT.is_file() or _OUT.read_text(encoding="utf-8") != text:
            raise SystemExit(f"STALE: {_OUT} does not match the wiki. Re-run without --check.")
        print(f"OK: {_OUT.name} matches the wiki.")
        return

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(text, encoding="utf-8")

    phases = data["checklist"]["phases"]
    print(f"Wiki root: {settings.wiki_content_root}")
    print(f"  phases       {len(phases)}  ({sum(len(p['items']) for p in phases)} items)")
    print(f"  rules        {len(data['rules'])}")
    print(f"  divergences  {len(data['divergences'])}")
    for key in ("setup", "mapping", "markup"):
        secs = data[key]["sections"]
        print(f"  {key:12} {len(secs)} sections, "
              f"{sum(len(s['items']) for s in secs)} steps, "
              f"{sum(len(s['tables']) for s in secs)} tables")
    print(f"Wrote {_OUT}")


if __name__ == "__main__":
    main()
