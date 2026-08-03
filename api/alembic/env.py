from logging.config import fileConfig

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import engine_from_config, pool

from alembic import context

# Load model metadata so Alembic can detect schema changes
from app.models.base import Base  # noqa: F401 — registers metadata
import app.models.user  # noqa: F401
import app.models.concept  # noqa: F401
import app.models.concept_progress  # noqa: F401
import app.models.content_page  # noqa: F401
import app.models.drill  # noqa: F401
import app.models.drill_progress  # noqa: F401
import app.models.evidence  # noqa: F401
import app.models.gate_attestation  # noqa: F401
import app.models.journal_entry  # noqa: F401
import app.models.missed_trade  # noqa: F401
import app.models.plan_item  # noqa: F401
import app.models.rubric  # noqa: F401
import app.models.study_preferences  # noqa: F401
import app.models.track_stage  # noqa: F401
from app.config import settings as app_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# The working DB by default. A scratch/throwaway DB must be named EXPLICITLY:
#     alembic -x db_url=postgresql+psycopg2://…/scratch downgrade base
# Exporting DATABASE_URL does NOT redirect Alembic (the .env also sets
# DATABASE_URL_SYNC, which wins for the sync URL) — that footgun ran a
# `downgrade base` against the working DB twice and wiped the seed. `-x db_url`
# is explicit, per-invocation, and cannot be triggered by a stray export.
_x_args = context.get_x_argument(as_dictionary=True)
config.set_main_option("sqlalchemy.url", _x_args.get("db_url") or app_settings.sync_database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
