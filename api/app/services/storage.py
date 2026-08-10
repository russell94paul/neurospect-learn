"""Object storage for evidence assets (Phase E2) — R2 or the local filesystem.

The R2 half is lifted from the proven `neurospect-api/app/services/r2.py`
(`storage_key` / `upload_bytes` / `delete` / `presign`, a module-level sentinel,
and the same `R2_*` env-var names, canonical in
concepts/architecture/phase2-project-structure.md §R2 Client). The local half is
new and is the PRIMARY path here, not a stopgap: every drill's stated tooling is
desktop TradingView bar-replay, so capture is paste-from-clipboard on localhost
and hosting is deliberately not a prerequisite (design decision #4). Pointing
`R2_ENDPOINT_URL` at a bucket later is a config flip, not a code change.

Both backends expose the SAME interface, including `presign()` — the local
backend signs a short-lived, key-scoped JWT so the frontend can render evidence
with a plain `<img src>` exactly as it would against R2. The signed token
carries only the storage key and an expiry; it is not the session token.

This module does IO but never touches the DB, so `app/services/*` stays
DB-free (the convention §6a records).
"""

import hashlib
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Protocol

from jose import JWTError, jwt

from app.config import settings

# Short-lived read URLs, matching the neurospect-api presign default.
PRESIGN_EXPIRES = 3600
_TOKEN_AUDIENCE = "evidence-file"


class StorageError(RuntimeError):
    """Raised when the backend cannot serve a request (bad key, missing object)."""


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

_SAFE = "abcdefghijklmnopqrstuvwxyz0123456789-_"


def slugify_subject(value: str) -> str:
    """Make a subject safe for a storage key.

    Drill refs are freetext from the wiki ("aura D1-b", "ict-course T-01"), and a
    filename or ref must NEVER be interpolated into a path unsanitised. Anything
    outside [a-z0-9-_] collapses to '-'; an empty result falls back to a hash so
    a key is always well-formed.
    """
    norm = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    out = "".join(ch if ch in _SAFE else "-" for ch in norm).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:80] or hashlib.sha256(value.encode()).hexdigest()[:16]


def safe_extension(filename: str | None, content_type: str) -> str:
    """The file extension to store under — derived from the SNIFFED content type,
    with the client filename used only as a hint and never as a path."""
    by_type = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    if content_type in by_type:
        return by_type[content_type]
    suffix = PurePosixPath(filename or "").suffix.lstrip(".").lower()
    return "".join(ch for ch in suffix if ch.isalnum())[:8] or "bin"


def storage_key(user_id: uuid.UUID, subject_type: str, subject: str, ext: str) -> str:
    """`{user_id}/evidence/{subject_type}/{subject}/{uuid4}.{ext}` — extending the
    `{user_id}/{trade_id}/{phase}/{uuid4}.{ext}` convention canonical in
    concepts/architecture/phase2-project-structure.md §R2 Client."""
    return (
        f"{user_id}/evidence/{slugify_subject(subject_type)}/"
        f"{slugify_subject(subject)}/{uuid.uuid4()}.{ext}"
    )


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

class StorageBackend(Protocol):
    name: str

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None: ...
    def delete(self, key: str) -> None: ...
    def presign(self, key: str, expires: int = PRESIGN_EXPIRES) -> str: ...


class R2Backend:
    """Cloudflare R2 (S3-compatible) via boto3 — the shape proven in
    `neurospect-api/app/services/r2.py`, unchanged."""

    name = "r2"

    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
        self._bucket = settings.r2_bucket

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presign(self, key: str, expires: int = PRESIGN_EXPIRES) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )


class LocalBackend:
    """The filesystem under `EVIDENCE_LOCAL_ROOT` — localhost needs NO bucket.

    `presign()` returns an app-relative URL carrying a short-lived JWT bound to
    the exact storage key, so `GET /api/evidence/file?token=…` can stream it to
    an `<img>` without the session token. Every key is resolved against the root
    and rejected if it escapes (path traversal).
    """

    name = "local"

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.evidence_local_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or key.startswith("/") or "\\" in key:
            raise StorageError("Invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise StorageError("Invalid storage key")
        return path

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except StorageError:
            pass

    def read_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StorageError("Object not found")
        return path.read_bytes()

    def presign(self, key: str, expires: int = PRESIGN_EXPIRES) -> str:
        return f"/api/evidence/file?token={sign_key(key, expires)}"


# ---------------------------------------------------------------------------
# Local read tokens
# ---------------------------------------------------------------------------

def sign_key(key: str, expires: int = PRESIGN_EXPIRES) -> str:
    """A short-lived token authorising a read of EXACTLY this storage key."""
    return jwt.encode(
        {
            "k": key,
            "aud": _TOKEN_AUDIENCE,
            "exp": datetime.now(timezone.utc) + timedelta(seconds=expires),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def verify_key_token(token: str) -> str:
    """The storage key a read token authorises, or raise `StorageError`."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=["HS256"], audience=_TOKEN_AUDIENCE
        )
    except JWTError as exc:
        raise StorageError("Invalid or expired read token") from exc
    key = payload.get("k")
    if not isinstance(key, str) or not key:
        raise StorageError("Invalid read token")
    return key


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def make_backend() -> StorageBackend:
    """R2 when it is configured, the local filesystem otherwise. Unlike
    `neurospect-api`'s `r2 is None` sentinel there is NO 503 path: evidence
    capture must work on localhost with nothing provisioned."""
    if settings.r2_endpoint_url:
        return R2Backend()
    return LocalBackend()


# Module-level singleton; tests may monkeypatch `app.services.storage.storage`.
storage: StorageBackend = make_backend()


def storage_read_bytes(key: str) -> bytes:
    """Read a stored object back, whichever backend is configured (Phase E4).

    `LocalBackend` reads from disk; `R2Backend` has no `read_bytes` of its own
    (E2 only ever needed to WRITE to R2, since reads there go straight to a
    presigned URL in the browser). The AI reader is the first server-side
    consumer of the bytes, so the S3 GET lives here rather than widening the
    backend Protocol for one caller.

    Blocking on both paths — callers must run it off the event loop.
    """
    backend = storage
    if isinstance(backend, LocalBackend):
        return backend.read_bytes(key)
    if isinstance(backend, R2Backend):
        obj = backend._client.get_object(Bucket=backend._bucket, Key=key)
        return obj["Body"].read()
    raise StorageError(f"Backend {getattr(backend, 'name', '?')} cannot read objects")
