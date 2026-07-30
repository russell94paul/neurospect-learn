"""Shared helpers for tests that need REPS (Phase E2).

Since E2 a rep exists only as evidence of the work: no endpoint writes `reps`,
so a test that needs a concept or drill at its rep target must upload evidence
for it, exactly as the user would. That is the point — the fixtures had to change
because the bypass they used no longer exists.

Every generated image is visually distinct, because the deterministic tier
refuses an exact or near duplicate.
"""

import random
from io import BytesIO

from PIL import Image, ImageDraw


def chart_png(seed: int, width: int = 900, height: int = 520) -> bytes:
    """A deterministic, visually distinct fake chart capture."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (width, height), (18, 20, 26))
    draw = ImageDraw.Draw(img)
    for gx in range(0, width, 60):
        draw.line([(gx, 0), (gx, height)], fill=(32, 36, 44))
    y = height // 2
    for x in range(10, width - 10, 8):
        y = max(40, min(height - 40, y + rnd.randint(-24, 24)))
        up = rnd.random() > 0.5
        colour = (38, 166, 154) if up else (239, 83, 80)
        draw.line([(x + 2, y - rnd.randint(4, 22)), (x + 2, y + rnd.randint(4, 22))], fill=colour)
        draw.rectangle([x, y, x + 5, y + 8], fill=colour)
    # A per-seed marking block, so two seeds are never near-duplicates.
    draw.rectangle([40, 40 + (seed % 5) * 40, width - 40, 90 + (seed % 5) * 40],
                   outline=(250, 204, 21), width=4)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _files(seed: int) -> dict:
    return {"file": (f"chart-{seed}.png", BytesIO(chart_png(seed)), "image/png")}


async def upload_evidence(client, headers, *, seed: int, reps: int = 1, **subject):
    """POST one evidence asset. `subject` is one of drill_ref / concept_id /
    journal_entry_id / missed_trade_id plus `subject_type`."""
    data = {"reps_claimed": str(reps), **{k: str(v) for k, v in subject.items()}}
    return await client.post("/api/evidence", headers=headers, files=_files(seed), data=data)


# One asset may claim at most this many reps (the DB CHECK + the Form bound).
MAX_CLAIM = 100


def _chunks(reps: int) -> list[int]:
    """Split a rep count across assets, since one asset claims ≤ MAX_CLAIM."""
    full, rest = divmod(reps, MAX_CLAIM)
    return [MAX_CLAIM] * full + ([rest] if rest else [])


async def give_concept_reps(client, headers, concept_id, reps: int, *, seed: int) -> None:
    for i, claim in enumerate(_chunks(reps)):
        r = await upload_evidence(
            client, headers, seed=seed * 1000 + i, reps=claim,
            subject_type="concept", concept_id=concept_id,
        )
        assert r.status_code == 201, r.text


async def give_drill_reps(client, headers, drill_ref: str, reps: int, *, seed: int) -> None:
    for i, claim in enumerate(_chunks(reps)):
        r = await upload_evidence(
            client, headers, seed=seed * 1000 + i, reps=claim,
            subject_type="drill", drill_ref=drill_ref,
        )
        assert r.status_code == 201, r.text
