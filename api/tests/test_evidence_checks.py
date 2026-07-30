"""Pure unit tests for the DETERMINISTIC grading tier (Phase E2).

No DB, no HTTP — `app/services/evidence_checks.py` takes bytes and the user's
existing hashes and returns a verdict, so it is testable exactly like
`expectancy.py` / `scheduler.py`.

The load-bearing test here is `test_measured_phash_separation`: it pins the
distances the block/flag thresholds were CHOSEN from. If a future change makes a
re-marked chart collide with its own earlier capture, that test fails — which is
the point, because a wrongly refused honest rep fails the north star exactly as
hard as a fakeable one.
"""

from io import BytesIO

from PIL import Image

from app.services import evidence_checks as ec
from tests.evidence_helpers import chart_png

_BOUNDS = {"max_bytes": 12 * 1024 * 1024, "min_bytes": 512}


def _check(data, hashes=None, phashes=None):
    return ec.check(
        data, existing_hashes=hashes or {}, existing_phashes=phashes or {}, **_BOUNDS
    )


def _as(data: bytes, fmt: str, **kw) -> bytes:
    with Image.open(BytesIO(data)) as img:
        buf = BytesIO()
        img.convert("RGB").save(buf, format=fmt, **kw)
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Magic-byte sniffing — the client's content_type is never trusted
# ---------------------------------------------------------------------------

def test_sniffs_real_image_types():
    png = chart_png(1)
    assert ec.sniff_content_type(png) == "image/png"
    assert ec.sniff_content_type(_as(png, "JPEG")) == "image/jpeg"
    assert ec.sniff_content_type(_as(png, "WEBP")) == "image/webp"
    assert ec.sniff_content_type(_as(png, "GIF")) == "image/gif"


def test_a_non_image_is_refused_with_a_reason():
    payload = b"#!/bin/sh\nrm -rf /\n" + b"x" * 2000
    verdict = _check(payload)
    assert isinstance(verdict, ec.Rejection)
    assert verdict.code == "not_an_image"
    assert "not an image" in verdict.message.lower()


def test_a_forged_content_type_does_not_help():
    """A PDF renamed .png with content_type image/png is still refused: the
    verdict comes from the BYTES, and `check()` is never told what the client
    claimed."""
    assert isinstance(_check(b"%PDF-1.7\n" + b"0" * 4000), ec.Rejection)


def test_size_bounds_block_with_a_reason():
    too_small = _check(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
    assert isinstance(too_small, ec.Rejection) and too_small.code == "too_small"

    big = ec.check(
        chart_png(2), existing_hashes={}, existing_phashes={},
        max_bytes=1024, min_bytes=1,
    )
    assert isinstance(big, ec.Rejection) and big.code == "too_large"
    assert "MB" in big.message


# ---------------------------------------------------------------------------
# Duplicates — the only judgement-free block besides "not an image"
# ---------------------------------------------------------------------------

def test_exact_duplicate_is_blocked_and_names_the_original():
    data = chart_png(3)
    first = _check(data)
    assert isinstance(first, ec.Accepted)

    again = _check(data, hashes={"abc": first.sha256})
    assert isinstance(again, ec.Rejection)
    assert again.code == "duplicate" and again.duplicate_of == "abc"


def test_a_re_encode_of_the_same_capture_is_caught_by_the_perceptual_hash():
    """Different bytes (so sha256 misses) but the same image — the case the
    perceptual hash exists for."""
    original = chart_png(4)
    accepted = _check(original)
    assert isinstance(accepted, ec.Accepted)

    recycled = _as(original, "JPEG", quality=70)
    assert ec.sha256_hex(recycled) != accepted.sha256  # sha256 alone would let it in
    verdict = _check(recycled, phashes={"orig": accepted.perceptual_hash})
    assert isinstance(verdict, ec.Rejection) and verdict.code == "near_duplicate"
    assert verdict.duplicate_of == "orig"


def test_a_different_chart_is_accepted():
    a = _check(chart_png(5))
    b = _check(chart_png(6), hashes={"a": a.sha256}, phashes={"a": a.perceptual_hash})
    assert isinstance(b, ec.Accepted) and not b.flags


def _crop(data: bytes, pct: float) -> bytes:
    with Image.open(BytesIO(data)) as img:
        dx, dy = int(img.width * pct / 100), int(img.height * pct / 100)
        buf = BytesIO()
        img.crop((dx, dy, img.width - dx, img.height - dy)).save(buf, format="PNG")
        return buf.getvalue()


def test_a_trivial_crop_of_your_own_capture_is_blocked():
    original = chart_png(7)
    base = _check(original)
    verdict = _check(_crop(original, 0.5), phashes={"orig": base.perceptual_hash})
    assert isinstance(verdict, ec.Rejection) and verdict.code == "near_duplicate"


def test_a_soft_similar_capture_is_FLAGGED_not_refused():
    """"Block the certain, surface the rest": a crop just past the block band is
    suspicious but not proof, so it is recorded and shown, never refused."""
    original = chart_png(7)
    base = _check(original)
    verdict = _check(_crop(original, 1), phashes={"orig": base.perceptual_hash})
    assert isinstance(verdict, ec.Accepted), "a crop must not be refused"
    assert verdict.flags and verdict.flags[0]["code"] == "similar_to_existing"
    assert verdict.flags[0]["evidence_id"] == "orig"


# ---------------------------------------------------------------------------
# The measurements the thresholds were chosen from
# ---------------------------------------------------------------------------

def test_measured_phash_separation():
    """Pins the numbers in the module's threshold comment.

    The decisive one is `re-marked`: drawing NEW markings on the same chart is a
    REAL extra rep in this curriculum ("≥50 ranges" on one instrument), and it
    must land clear of the block threshold.
    """
    base = chart_png(11)
    ref = ec.perceptual_hash(base)

    def d(data):
        return ec.hamming(ref, ec.perceptual_hash(data))

    with Image.open(BytesIO(base)) as img:
        rescaled = BytesIO()
        img.resize((img.width // 2, img.height // 2)).save(rescaled, format="PNG")

    # What the BLOCK threshold must catch: the same capture, re-encoded or
    # rescaled or trivially cropped. All measure at or below it, on every seed.
    assert d(base) == 0
    for seed in (11, 12, 13):
        img_bytes = chart_png(seed)
        own = ec.perceptual_hash(img_bytes)
        assert ec.hamming(own, ec.perceptual_hash(_as(img_bytes, "JPEG", quality=40))) \
            <= ec.PHASH_BLOCK_DISTANCE
        assert ec.hamming(own, ec.perceptual_hash(_crop(img_bytes, 0.5))) \
            <= ec.PHASH_BLOCK_DISTANCE
    assert d(rescaled.getvalue()) <= ec.PHASH_BLOCK_DISTANCE

    # What NEITHER threshold may catch: two genuinely different captures.
    assert d(chart_png(12)) > ec.PHASH_FLAG_DISTANCE
    assert d(chart_png(13)) > ec.PHASH_FLAG_DISTANCE

    # And the reason the flag band stops where it does: by a 2% crop the signal
    # has already decayed past it, into the range honest re-marked work occupies.
    # A threshold reaching further would refuse real reps.
    assert d(_crop(base, 2)) > ec.PHASH_FLAG_DISTANCE
    assert ec.PHASH_BLOCK_DISTANCE < ec.PHASH_FLAG_DISTANCE


def test_a_decode_failure_is_not_a_rejection():
    """A file whose magic bytes say PNG but that Pillow cannot decode is still
    accepted (with no perceptual hash). Refusing an odd-but-valid capture is the
    false negative the north star forbids; the sniff has already done its job."""
    broken = b"\x89PNG\r\n\x1a\n" + b"\x11" * 4000
    verdict = _check(broken)
    assert isinstance(verdict, ec.Accepted)
    assert verdict.perceptual_hash is None
    assert verdict.content_type == "image/png"
