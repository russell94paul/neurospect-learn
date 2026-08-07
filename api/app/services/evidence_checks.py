"""The DETERMINISTIC grading tier (Phase E2) — the only tier that BLOCKS.

Design contract (concepts/architecture/learning-enforcement.md §2 + §5): block
only what is certain and zero-false-positive — a non-image upload and an exact
duplicate — and SURFACE everything judgement-shaped. The north star is that the
adversary is self-deception, not an attacker: a wrongly refused honest rep fails
it exactly as hard as a fakeable one, so anything short of certainty is recorded
and shown rather than refused.

Pure and DB-free: it takes bytes and the user's existing hashes, and returns a
verdict. The router does the IO.

Perceptual-hash thresholds are measured, not guessed — see
`tests/test_evidence_checks.py`, which pins the distances that separate a
re-encode/crop of the same chart from two genuinely different charts.
"""

import hashlib
from dataclasses import dataclass, field
from io import BytesIO

# Imported at MODULE level, not inside `perceptual_hash`. Both are hard
# dependencies (pyproject: pillow, imagehash), so there is nothing to guard —
# and a function-level import made the FIRST upload of every server process pay
# the whole PIL+imagehash import ON THE EVENT LOOP: measured 540 ms warm and
# 8.3 s cold, against ~4 ms for the hash itself. That stall serves nothing else,
# and a saturated accept backlog is answered by Windows with an RST, which
# reaches a client as ECONNRESET. Paid at startup now, before serving begins.
import imagehash
from PIL import Image

# Magic-byte signatures. The client's `content_type` header is NEVER trusted:
# it is trivially forged and is not evidence of anything.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)

# Thresholds MEASURED on chart-like captures, not guessed
# (tests/test_evidence_checks.py::test_measured_phash_separation pins them):
#
#   identical bytes · JPEG re-encode q40/q80 · 50% rescale ......  0
#   0.5% crop of the same capture ...............................  2
#   1% crop .....................................................  6
#   SAME chart with ONE new marking drawn on it ................. 8–10
#   2% crop ..................................................... 14
#   a genuinely different chart ................................. 26–34
#
# The load-bearing number is the middle one: re-marking the same chart is a REAL
# extra rep in this curriculum ("≥50 ranges" on one instrument), and it lands at
# 8–10 — i.e. INSIDE the range a 2% crop occupies. pHash therefore cannot
# separate "your own screenshot, cropped" from "the same chart, freshly marked"
# beyond about distance 7, and any threshold that tried would refuse honest work.
#
# So: ≤4 BLOCKS (only a re-encode, rescale or trivial crop of bytes already
# submitted — zero false positives). 5–7 is suspicious but not proof, so it is
# FLAGGED and shown. Past 7 the signal is gone and nothing is claimed, which is
# the honest answer rather than a guess dressed up as a check.
PHASH_BLOCK_DISTANCE = 4
PHASH_FLAG_DISTANCE = 7


@dataclass(frozen=True)
class Rejection:
    """Why an upload was refused. A silent refusal is the failure mode this
    workstream exists to avoid, so every rejection carries a reason."""

    code: str      # not_an_image | too_large | too_small | duplicate | near_duplicate
    message: str
    duplicate_of: str | None = None
    distance: int | None = None


@dataclass(frozen=True)
class Accepted:
    """A passing upload, plus everything the asset row needs."""

    content_type: str
    sha256: str
    perceptual_hash: str | None
    byte_size: int
    # Judgement-shaped observations: recorded on the deterministic grade row and
    # shown, never used to refuse (design §5, "surface the rest").
    flags: list[dict] = field(default_factory=list)


def sniff_content_type(data: bytes) -> str | None:
    """The real image type from magic bytes, or None if this is not an image."""
    for signature, content_type in _SIGNATURES:
        if data.startswith(signature):
            return content_type
    # WEBP: "RIFF" .... "WEBP"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def perceptual_hash(data: bytes) -> str | None:
    """A 64-bit pHash as hex, or None if the bytes will not decode as an image.

    A decode failure is NOT a rejection on its own — the magic-byte sniff has
    already established this is an image, and refusing an odd-but-valid capture
    would be exactly the false negative the north star warns about.
    """
    try:
        with Image.open(BytesIO(data)) as img:
            return str(imagehash.phash(img.convert("RGB")))
    except Exception:
        return None


def hamming(a: str, b: str) -> int:
    """Bit distance between two hex perceptual hashes (max = 4·len)."""
    if not a or not b or len(a) != len(b):
        return 10_000
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def check(
    data: bytes,
    *,
    max_bytes: int,
    min_bytes: int,
    existing_hashes: dict[str, str],
    existing_phashes: dict[str, str],
) -> Accepted | Rejection:
    """Run the deterministic tier.

    `existing_hashes` / `existing_phashes` map an evidence id (as str) to that
    asset's sha256 / perceptual hash, for THIS user only — recycling someone
    else's image is not a thing in a single-user tool, and scoping the check to
    the user keeps it O(their own evidence).
    """
    size = len(data)
    if size > max_bytes:
        return Rejection(
            "too_large",
            f"That file is {size / 1_048_576:.1f} MB — the limit is "
            f"{max_bytes / 1_048_576:.0f} MB. Crop or re-export the capture.",
        )
    if size < min_bytes:
        return Rejection(
            "too_small",
            f"That file is only {size} bytes — too small to be a chart capture.",
        )

    content_type = sniff_content_type(data)
    if content_type is None:
        return Rejection(
            "not_an_image",
            "That is not an image. Evidence is a capture of your marked-up chart "
            "or written artifact (PNG, JPEG, WEBP or GIF).",
        )

    digest = sha256_hex(data)
    for evidence_id, known in existing_hashes.items():
        if known == digest:
            return Rejection(
                "duplicate",
                "You have already uploaded this exact image — the same capture "
                "cannot count twice.",
                duplicate_of=evidence_id,
            )

    phash = perceptual_hash(data)
    flags: list[dict] = []
    if phash:
        nearest_id, nearest_distance = None, 10_000
        for evidence_id, known in existing_phashes.items():
            distance = hamming(phash, known)
            if distance < nearest_distance:
                nearest_id, nearest_distance = evidence_id, distance
        if nearest_id is not None and nearest_distance <= PHASH_BLOCK_DISTANCE:
            return Rejection(
                "near_duplicate",
                "That is the same capture as one you have already uploaded "
                "(re-cropped or re-saved) — it cannot count twice.",
                duplicate_of=nearest_id,
                distance=nearest_distance,
            )
        if nearest_id is not None and nearest_distance <= PHASH_FLAG_DISTANCE:
            flags.append({
                "code": "similar_to_existing",
                "message": (
                    "Visually similar to earlier evidence of yours "
                    f"(distance {nearest_distance}). Recorded, not refused."
                ),
                "evidence_id": nearest_id,
                "distance": nearest_distance,
            })

    return Accepted(
        content_type=content_type,
        sha256=digest,
        perceptual_hash=phash,
        byte_size=size,
        flags=flags,
    )
