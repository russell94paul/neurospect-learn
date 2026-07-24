"""Multi-track curriculum: per-track concept columns + track_stages

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-20

Phase 5e-1b — turn the single unified `/path` into THREE first-class graded
tracks (aura · ict_course · unified). Extends `concepts` with per-track columns
and adds a `track_stages` metadata table (one row per (track, stage)). The
Study-Planner tables (`study_preferences`, `plan_items`) move to 0006.

Design decision (per learning-platform.md §Multi-track data model — the
contract): a stage's concepts are grouped by `(track, stage_code)` on
`concepts` itself; `track_stages` holds ONLY the stage metadata (title/summary/
gate_text). No denormalised `concept_slugs` array (avoids drift). Raw-SQL
op.execute idiom, matching 0002/0003/0004; reuses update_updated_at() from 0001.
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. concepts — per-track columns.
    #    - track: which of the three graded tracks (the 41 existing rows are
    #      unified; DEFAULT keeps the backfill trivial). CHECK-constrained
    #      VARCHAR (not an enum), matching drills.track's convention.
    #    - stage_code / stage_order: the concept's generic per-track stage
    #      (e.g. A1 / M2 / U1) — the (track, stage_code) grouping key.
    #    - cross_refs: equivalent concept slugs in the OTHER tracks (soft refs,
    #      display-only "Also taught in …"; never merges progress).
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE concepts "
        "ADD COLUMN track VARCHAR(16) NOT NULL DEFAULT 'unified'"
    )
    op.execute(
        "ALTER TABLE concepts "
        "ADD CONSTRAINT ck_concepts_track "
        "CHECK (track IN ('aura', 'ict_course', 'unified'))"
    )
    op.execute("ALTER TABLE concepts ADD COLUMN stage_code VARCHAR(16)")
    op.execute("ALTER TABLE concepts ADD COLUMN stage_order SMALLINT")
    op.execute("ALTER TABLE concepts ADD COLUMN cross_refs TEXT[]")

    # u_stage is now UNIFIED-ONLY (it still drives the frontier CHECK, the
    # content_pages join, and the unified exit bars). Aura/ict_course rows leave
    # it NULL. The pre-existing CHECK (u_stage <> 'U5' OR NOT is_core) is
    # satisfied when u_stage IS NULL (NULL comparison → unknown → CHECK passes).
    op.execute("ALTER TABLE concepts ALTER COLUMN u_stage DROP NOT NULL")

    # Group/browse concepts by their track + stage.
    op.execute(
        "CREATE INDEX ix_concepts_track_stage "
        "ON concepts (track, stage_order, sort_order)"
    )

    # ------------------------------------------------------------------
    # 2. track_stages — per-track stage metadata (seed/content, no soft-delete,
    #    like concepts/drills; re-seed replaces). Holds the title/summary/
    #    gate_text the /path curriculum unit renders. The stage's concepts and
    #    drills are resolved by grouping, not stored here.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE track_stages (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            track         VARCHAR(16) NOT NULL,
            stage_order   SMALLINT NOT NULL,
            stage_code    VARCHAR(16) NOT NULL,
            title         TEXT NOT NULL,
            summary       TEXT,
            gate_text     TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_track_stages_track
                CHECK (track IN ('aura', 'ict_course', 'unified')),
            CONSTRAINT ux_track_stages_track_code UNIQUE (track, stage_code)
        )
    """)
    op.execute("CREATE INDEX ix_track_stages_order ON track_stages (track, stage_order)")
    op.execute("""
        CREATE TRIGGER trg_track_stages_updated_at
            BEFORE UPDATE ON track_stages
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS track_stages")

    # The aura/ict_course rows only exist because of this migration; drop them
    # before restoring u_stage NOT NULL (they carry NULL u_stage). Unified rows
    # keep their u_stage, so NOT NULL can be restored cleanly. Clear any
    # concept_progress that FK-references those rows first (they can only exist
    # post-0005).
    op.execute(
        "DELETE FROM concept_progress WHERE concept_id IN "
        "(SELECT id FROM concepts WHERE track <> 'unified')"
    )
    op.execute("DELETE FROM concepts WHERE track <> 'unified'")
    op.execute("ALTER TABLE concepts ALTER COLUMN u_stage SET NOT NULL")

    op.execute("DROP INDEX IF EXISTS ix_concepts_track_stage")
    op.execute("ALTER TABLE concepts DROP COLUMN IF EXISTS cross_refs")
    op.execute("ALTER TABLE concepts DROP COLUMN IF EXISTS stage_order")
    op.execute("ALTER TABLE concepts DROP COLUMN IF EXISTS stage_code")
    op.execute("ALTER TABLE concepts DROP CONSTRAINT IF EXISTS ck_concepts_track")
    op.execute("ALTER TABLE concepts DROP COLUMN IF EXISTS track")
