from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# E4 — make `.env` reach consumers that are NOT this settings object.
# pydantic-settings reads `.env` into `Settings` and stops there; it never
# populates `os.environ`. The Anthropic SDK resolves its own credential FROM
# `os.environ`, so an ANTHROPIC_API_KEY written to `api/.env` was invisible to
# it — the app read the file, the SDK saw nothing, and grading failed with an
# auth error while the key sat right there. `override=False` keeps a real
# exported variable winning over the file, matching the SDK's own precedence.
_API_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_API_ROOT / ".env", override=False)

# Repo root = neurospect-learn/ (this file is api/app/config.py → parents[2]).
# The wiki is checked out as a sibling of the repo by default.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_WIKI_ROOT = str(_REPO_ROOT.parent / "neurospect-wiki")
# Local evidence blobs live inside the repo but are gitignored — they are user
# data, not source (and chart captures are private by design).
_DEFAULT_EVIDENCE_ROOT = str(_REPO_ROOT / ".evidence-store")


class Settings(BaseSettings):
    # `extra="ignore"` because `.env` is shared with consumers that are NOT this
    # settings object. E4 deliberately declares no api-key setting (the Anthropic
    # SDK resolves ANTHROPIC_API_KEY itself, so a second copy here could only
    # drift from it) — but pydantic-settings defaults to `extra="forbid"`, which
    # made putting that key in `.env` crash the app at import: alembic, uvicorn
    # and pytest all died on `extra_forbidden`. Ignoring unknown keys is what
    # makes "the SDK owns the credential, the app never sees it" actually work.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str
    database_url_sync: str = ""

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql+psycopg2://"):
            return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        # Prefer explicit DATABASE_URL_SYNC; fall back to deriving from DATABASE_URL.
        url = self.database_url_sync or self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg2://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg2://", 1)
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        return url

    # JWT
    jwt_secret: str
    jwt_expire_minutes: int = 43200

    # Discord OAuth
    discord_client_id: str = ""
    discord_client_secret: str = ""

    # CORS — comma-separated / JSON list of allowed origins
    cors_origins: list[str] = ["http://localhost:5173"]

    # Debug mode — enables /auth/debug/token; never true in prod
    debug: bool = False

    # Wiki content root — the neurospect-wiki checkout the content ingest reads
    # (READ-ONLY; ingest never writes back). Defaults to the sibling repo.
    wiki_content_root: str = _DEFAULT_WIKI_ROOT

    # Evidence storage (Phase E2). Cloudflare R2 when R2_ENDPOINT_URL is set,
    # otherwise the local filesystem — localhost needs NO bucket. Names reuse
    # the wider Neurospect stack's verbatim (neurospect-api / render.yaml).
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    evidence_local_root: str = _DEFAULT_EVIDENCE_ROOT

    # Upload bounds for the deterministic tier (the ONLY tier that blocks).
    evidence_max_bytes: int = 12 * 1024 * 1024
    evidence_min_bytes: int = 512

    # AI vision second reader (Phase E4) — tier 3, ADVISORY. Off by default, so
    # the app runs with no LLM dependency at all and the upload path is identical
    # either way. The Anthropic SDK resolves the credential itself (env var or an
    # `ant auth login` profile), so there is deliberately no api-key setting here
    # to get out of sync with it.
    ai_grading_enabled: bool = False
    ai_grader_model: str = "claude-sonnet-5"
    ai_grader_max_tokens: int = 2048
    #: How many queued grades one worker pass drains. Small, because this is a
    #: single-user app and a grade is never urgent.
    ai_grader_batch_size: int = 5


settings = Settings()  # type: ignore[call-arg]
