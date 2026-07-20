"""Drills catalog + drill_progress: drill_variant enum + drills + drill_progress

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-20

Phase 5e-1 — the drill projection of the two wiki exercise libraries + the
per-user drill tracker. `drills` is seed/content (no soft-delete, like
`concepts`); `drill_progress` is user-scoped + soft-deleted (like
`concept_progress`). Reuses the update_updated_at() trigger fn created in 0001
(do NOT recreate it). Raw-SQL op.execute idiom, matching 0002/0003.

The `drill_variant` enum ('hand' | 'tool') is created here per the Phase 5e
design; the hand/tool marks live on drill_progress as two booleans, and the
enum is consumed by plan_items in 0005 (5e-2).
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. ENUM: drill_variant (the ✋ hand-marking / 🛠 tool-assisted split).
    #    Created here (0004); consumed by plan_items in 0005 (5e-2). The
    #    drill_progress marks are two booleans, not this enum.
    # ------------------------------------------------------------------
    op.execute("CREATE TYPE drill_variant AS ENUM ('hand', 'tool')")

    # ------------------------------------------------------------------
    # 2. drills — the drill catalog, seed/content, no soft-delete (like
    #    concepts; re-seed replaces). A projection of the wiki exercise
    #    libraries' "Drill → concept → ladder-stage map" tables.
    #    `track` is a CHECK-constrained VARCHAR (not an enum) — drill_variant
    #    is the only enum this migration owns. `concept_slugs` is a soft
    #    back-link to concepts.slug (matching the concepts.drill_refs convention).
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE drills (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            drill_ref     VARCHAR(64) UNIQUE NOT NULL,
            track         VARCHAR(16) NOT NULL,
            stage_code    VARCHAR(16),
            title         TEXT NOT NULL,
            advances_to   VARCHAR(64),
            rep_target    TEXT,
            concept_slugs TEXT[],
            sort_order    INTEGER NOT NULL DEFAULT 0,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_drills_track CHECK (track IN ('aura', 'ict_course'))
        )
    """)
    op.execute("CREATE INDEX ix_drills_track_stage ON drills (track, stage_code, sort_order)")
    op.execute("CREATE INDEX ix_drills_concept_slugs ON drills USING GIN (concept_slugs)")
    op.execute("""
        CREATE TRIGGER trg_drills_updated_at
            BEFORE UPDATE ON drills
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # ------------------------------------------------------------------
    # 3. drill_progress — the per-user drill tracker (user-scoped, soft-deleted).
    #    `drill_ref` is a TEXT soft ref (matching concepts.drill_refs / drills.
    #    drill_ref) — NOT a hard FK, so a mark can outlive a re-seed. hand_done /
    #    tool_done are the ✋ / 🛠 variant marks.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE drill_progress (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(id),
            drill_ref       TEXT NOT NULL,
            reps            INTEGER NOT NULL DEFAULT 0,
            hand_done       BOOLEAN NOT NULL DEFAULT false,
            tool_done       BOOLEAN NOT NULL DEFAULT false,
            last_practiced  DATE,
            notes           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted      BOOLEAN NOT NULL DEFAULT false,
            deleted_at      TIMESTAMPTZ,
            CONSTRAINT ck_drill_progress_reps CHECK (reps >= 0)
        )
    """)
    # One active progress row per (user, drill_ref); soft-deleted rows excluded.
    op.execute("""
        CREATE UNIQUE INDEX ux_drill_progress_user_drill
            ON drill_progress (user_id, drill_ref)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE INDEX ix_drill_progress_user
            ON drill_progress (user_id)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE TRIGGER trg_drill_progress_updated_at
            BEFORE UPDATE ON drill_progress
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    # Tables (triggers + indexes dropped automatically with the table)
    op.execute("DROP TABLE IF EXISTS drill_progress")
    op.execute("DROP TABLE IF EXISTS drills")
    # ENUM (after the tables that reference it are gone)
    op.execute("DROP TYPE IF EXISTS drill_variant")
