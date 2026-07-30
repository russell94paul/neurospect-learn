"""Run a reversibility test against a THROWAWAY database — never the working one.

Why this exists: `alembic downgrade base` has been run against the working DB
twice, wiping the 74/23/53/67 seed both times, because exporting `DATABASE_URL`
does NOT redirect Alembic (the `.env` also sets `DATABASE_URL_SYNC`, which wins
for the sync URL Alembic reads). This script creates a scratch DB, drives
Alembic at it with the explicit `-x db_url=` override, and drops it again — so a
reversibility test can never touch the working DB by accident.

    poetry run python scripts/scratch_migrate.py                # full up/down/up
    poetry run python scripts/scratch_migrate.py --keep         # leave it for \\d

The scratch URL is derived from the configured DATABASE_URL and is never printed.
"""

import argparse
import sys

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings

SCRATCH_DB = "neurospect_learn_scratch"


def _urls() -> tuple[str, str]:
    """(maintenance URL on `postgres`, scratch URL) — same server, same creds."""
    base = sa.engine.make_url(settings.sync_database_url)
    # render_as_string(hide_password=False): plain str(URL) masks the password
    # as "***", which fails auth. These strings are never printed.
    return (
        base.set(database="postgres").render_as_string(hide_password=False),
        base.set(database=SCRATCH_DB).render_as_string(hide_password=False),
    )


def _alembic(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.cmd_opts = argparse.Namespace(x=[f"db_url={url}"])  # the explicit override
    return cfg


def _recreate(maintenance_url: str) -> None:
    eng = sa.create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(sa.text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = :d AND pid <> pg_backend_pid()"
        ), {"d": SCRATCH_DB})
        c.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
        c.execute(sa.text(f'CREATE DATABASE "{SCRATCH_DB}"'))
    eng.dispose()


def _drop(maintenance_url: str) -> None:
    eng = sa.create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(sa.text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = :d AND pid <> pg_backend_pid()"
        ), {"d": SCRATCH_DB})
        c.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
    eng.dispose()


# Objects `0009` must create on the way up and remove on the way down.
_TABLES = ("evidence_assets", "evidence_grades")
_TYPES = ("evidence_subject", "evidence_kind", "evidence_grader", "evidence_grade_state")
_INDEXES = (
    "ux_evidence_assets_user_sha256", "ix_evidence_assets_user_drill",
    "ix_evidence_assets_user_concept", "ix_evidence_assets_user_journal",
    "ix_evidence_assets_user_missed", "ix_evidence_assets_user_phash",
    "ix_evidence_grades_evidence", "ix_evidence_grades_user_state",
)
_TRIGGERS = ("trg_evidence_assets_updated_at", "trg_evidence_grades_updated_at")


def _inspect(url: str) -> dict:
    eng = sa.create_engine(url)
    with eng.connect() as c:
        def q(sql, **kw):
            return set(r[0] for r in c.execute(sa.text(sql), kw))
        out = {
            "tables": q("SELECT tablename FROM pg_tables WHERE schemaname='public'"),
            "types": q("SELECT typname FROM pg_type WHERE typtype='e'"),
            "indexes": q("SELECT indexname FROM pg_indexes WHERE schemaname='public'"),
            "triggers": q("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"),
            "cp_cols": q(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='concept_progress'"),
            "dp_cols": q(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='drill_progress'"),
        }
    eng.dispose()
    return out


def _report(label: str, st: dict, *, present: bool) -> bool:
    ok = True
    for name, key in (
        (_TABLES, "tables"), (_TYPES, "types"), (_INDEXES, "indexes"), (_TRIGGERS, "triggers")
    ):
        for obj in name:
            has = obj in st[key]
            if has is not present:
                print(f"  ✗ {label}: {obj} {'missing' if present else 'still present'}")
                ok = False
    reps_col = "legacy_reps" if present else "reps"
    other = "reps" if present else "legacy_reps"
    for tbl, key in (("concept_progress", "cp_cols"), ("drill_progress", "dp_cols")):
        if reps_col not in st[key] or other in st[key]:
            print(f"  ✗ {label}: {tbl} should have {reps_col} and not {other} — got {sorted(st[key])}")
            ok = False
    print(f"  {'✓' if ok else '✗'} {label}: "
          f"{len(_TABLES)} tables · {len(_TYPES)} enums · {len(_INDEXES)} indexes · "
          f"{len(_TRIGGERS)} triggers {'present' if present else 'absent'}; "
          f"progress tables carry `{reps_col}`")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="do not drop the scratch DB at the end")
    args = ap.parse_args()

    maintenance_url, scratch_url = _urls()
    print(f"scratch database: {SCRATCH_DB} (working DB untouched)")
    _recreate(maintenance_url)
    cfg = _alembic(scratch_url)
    ok = True
    try:
        print("→ upgrade head (0001 → 0009)")
        command.upgrade(cfg, "head")
        ok &= _report("after upgrade head", _inspect(scratch_url), present=True)

        print("→ downgrade 0008")
        command.downgrade(cfg, "0008")
        ok &= _report("after downgrade 0008", _inspect(scratch_url), present=False)

        print("→ upgrade head again")
        command.upgrade(cfg, "head")
        ok &= _report("after re-upgrade", _inspect(scratch_url), present=True)

        print("→ downgrade base (full teardown)")
        command.downgrade(cfg, "base")
        left = _inspect(scratch_url)
        remaining = left["tables"] - {"alembic_version"}
        if remaining:
            print(f"  ✗ downgrade base left tables behind: {sorted(remaining)}")
            ok = False
        else:
            print("  ✓ downgrade base: schema fully torn down")
    finally:
        if not args.keep:
            _drop(maintenance_url)

    print("RESULT:", "REVERSIBLE" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
