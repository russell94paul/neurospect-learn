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


# Objects each migration must create on the way up and remove on the way down,
# kept as SEPARATE groups so a single-step reversibility test can assert that
# `downgrade 0009` removes E3's objects and leaves E2's ALONE — a stricter proof
# than only checking the full teardown to 0008.
_E2: dict[str, tuple[str, ...]] = {
    "tables": ("evidence_assets", "evidence_grades"),
    "types": ("evidence_subject", "evidence_kind", "evidence_grader", "evidence_grade_state"),
    "indexes": (
        "ux_evidence_assets_user_sha256", "ix_evidence_assets_user_drill",
        "ix_evidence_assets_user_concept", "ix_evidence_assets_user_journal",
        "ix_evidence_assets_user_missed", "ix_evidence_assets_user_phash",
        "ix_evidence_grades_evidence", "ix_evidence_grades_user_state",
    ),
    "triggers": ("trg_evidence_assets_updated_at", "trg_evidence_grades_updated_at"),
    "functions": (),
}
_E3 = {
    "tables": ("rubrics", "rubric_items"),
    "types": ("rubric_variant",),
    "indexes": (
        "ux_rubrics_slug", "ux_rubrics_drill_ref", "ix_rubrics_track",
        "ux_rubric_items_key", "ux_rubric_items_rubric_ordinal",
    ),
    "triggers": ("trg_rubrics_updated_at", "trg_rubric_items_updated_at"),
    "functions": (),
}
# E5 (`0011`) — the pre-commitment ledger. It is the FIRST migration here to own a
# trigger FUNCTION of its own, so the group tracks functions too: `0011` must drop
# `predictions_freeze_the_call` and must NOT drop `update_updated_at()`, which
# `0001` owns and every other table's trigger depends on.
_E5 = {
    "tables": ("predictions",),
    "types": ("prediction_bias",),
    "indexes": ("ix_predictions_user_drill", "ix_predictions_user_committed"),
    "triggers": ("trg_predictions_freeze_the_call", "trg_predictions_updated_at"),
    "functions": ("predictions_freeze_the_call",),
}


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
            "functions": q(
                "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public'"),
            "cp_cols": q(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='concept_progress'"),
            "dp_cols": q(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='drill_progress'"),
        }
    eng.dispose()
    return out


def _objects(label: str, st: dict, group: dict, *, present: bool, tag: str) -> bool:
    """Assert every object in one migration's group is present (or absent)."""
    ok = True
    for key in ("tables", "types", "indexes", "triggers", "functions"):
        for obj in group.get(key, ()):
            if (obj in st[key]) is not present:
                print(f"  ✗ {label}: {obj} {'missing' if present else 'still present'}")
                ok = False
    fns = group.get("functions", ())
    print(f"  {'✓' if ok else '✗'} {label}: {tag} "
          f"{len(group['tables'])} tables · {len(group['types'])} enums · "
          f"{len(group['indexes'])} indexes · {len(group['triggers'])} triggers"
          f"{f' · {len(fns)} functions' if fns else ''} "
          f"{'present' if present else 'absent'}")
    return ok


def _shared_trigger_fn_survives(label: str, st: dict) -> bool:
    """`update_updated_at()` is 0001's and EVERY table's trigger depends on it.
    0011 drops a function of its own, so this asserts it dropped only its own."""
    ok = "update_updated_at" in st["functions"]
    print(f"  {'✓' if ok else '✗'} {label}: 0001's update_updated_at() still present")
    return ok


def _reps_columns(label: str, st: dict, *, derived: bool) -> bool:
    """`0009` renames reps → legacy_reps; `0010` must not touch either."""
    ok = True
    reps_col = "legacy_reps" if derived else "reps"
    other = "reps" if derived else "legacy_reps"
    for tbl, key in (("concept_progress", "cp_cols"), ("drill_progress", "dp_cols")):
        if reps_col not in st[key] or other in st[key]:
            print(f"  ✗ {label}: {tbl} should have {reps_col} and not {other} — got {sorted(st[key])}")
            ok = False
    print(f"  {'✓' if ok else '✗'} {label}: progress tables carry `{reps_col}`")
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
        print("→ upgrade head (0001 → 0011)")
        command.upgrade(cfg, "head")
        st = _inspect(scratch_url)
        ok &= _objects("after upgrade head", st, _E2, present=True, tag="E2")
        ok &= _objects("after upgrade head", st, _E3, present=True, tag="E3")
        ok &= _objects("after upgrade head", st, _E5, present=True, tag="E5")
        ok &= _reps_columns("after upgrade head", st, derived=True)

        # SINGLE-STEP reversibility of the migration under test (E3's precedent):
        # 0011 must remove exactly its own objects — including its own trigger
        # FUNCTION — and leave E3's rubric layer and E2's evidence layer alone.
        print("→ downgrade 0010 (0011 only)")
        command.downgrade(cfg, "0010")
        st = _inspect(scratch_url)
        ok &= _objects("after downgrade 0010", st, _E5, present=False, tag="E5")
        ok &= _objects("after downgrade 0010", st, _E3, present=True, tag="E3 untouched")
        ok &= _objects("after downgrade 0010", st, _E2, present=True, tag="E2 untouched")
        ok &= _shared_trigger_fn_survives("after downgrade 0010", st)

        print("→ upgrade head again (0011 re-applies)")
        command.upgrade(cfg, "head")
        st = _inspect(scratch_url)
        ok &= _objects("after re-upgrade", st, _E5, present=True, tag="E5")

        # SINGLE-STEP reversibility of 0010, still asserted (E3's own proof).
        print("→ downgrade 0009 (0011 + 0010)")
        command.downgrade(cfg, "0009")
        st = _inspect(scratch_url)
        ok &= _objects("after downgrade 0009", st, _E5, present=False, tag="E5")
        ok &= _objects("after downgrade 0009", st, _E3, present=False, tag="E3")
        ok &= _objects("after downgrade 0009", st, _E2, present=True, tag="E2 untouched")
        ok &= _reps_columns("after downgrade 0009", st, derived=True)

        print("→ upgrade head again (0010 + 0011 re-apply)")
        command.upgrade(cfg, "head")
        st = _inspect(scratch_url)
        ok &= _objects("after re-upgrade", st, _E3, present=True, tag="E3")
        ok &= _objects("after re-upgrade", st, _E5, present=True, tag="E5")

        print("→ downgrade 0008 (0011 + 0010 + 0009)")
        command.downgrade(cfg, "0008")
        st = _inspect(scratch_url)
        ok &= _objects("after downgrade 0008", st, _E2, present=False, tag="E2")
        ok &= _objects("after downgrade 0008", st, _E3, present=False, tag="E3")
        ok &= _objects("after downgrade 0008", st, _E5, present=False, tag="E5")
        ok &= _reps_columns("after downgrade 0008", st, derived=False)

        print("→ upgrade head again")
        command.upgrade(cfg, "head")
        st = _inspect(scratch_url)
        ok &= _objects("after re-upgrade", st, _E2, present=True, tag="E2")
        ok &= _objects("after re-upgrade", st, _E3, present=True, tag="E3")
        ok &= _objects("after re-upgrade", st, _E5, present=True, tag="E5")
        ok &= _reps_columns("after re-upgrade", st, derived=True)

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
