from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = neurospect-learn/ (this file is api/app/config.py → parents[2]).
# The wiki is checked out as a sibling of the repo by default.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_WIKI_ROOT = str(_REPO_ROOT.parent / "neurospect-wiki")
# Local evidence blobs live inside the repo but are gitignored — they are user
# data, not source (and chart captures are private by design).
_DEFAULT_EVIDENCE_ROOT = str(_REPO_ROOT / ".evidence-store")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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


settings = Settings()  # type: ignore[call-arg]
