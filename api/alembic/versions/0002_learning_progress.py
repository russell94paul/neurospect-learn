"""Learning progress: u_stage enum + concepts + concept_progress + content_pages

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19

Reuses the update_updated_at() trigger fn created in 0001 (do NOT recreate it).
Raw-SQL op.execute idiom, matching 0001.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. ENUM: u_stage (shared by concepts + content_pages)
    # ------------------------------------------------------------------
    op.execute("CREATE TYPE u_stage AS ENUM ('U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6')")

    # ------------------------------------------------------------------
    # 2. concepts — seed/content, not user-editable, no soft-delete.
    #    content_slug + drill_refs are SOFT refs (nullable slug + TEXT[]),
    #    NOT hard FKs (content_pages is empty until 5d; drill IDs live in wiki).
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE concepts (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug          VARCHAR(128) UNIQUE NOT NULL,
            code          VARCHAR(16),
            u_stage       u_stage NOT NULL,
            title         TEXT NOT NULL,
            is_core       BOOLEAN NOT NULL DEFAULT false,
            tier          VARCHAR(32),
            label         VARCHAR(32),
            axis          VARCHAR(16),
            watch_only    BOOLEAN NOT NULL DEFAULT false,
            rep_target    TEXT,
            content_slug  VARCHAR(128),
            drill_refs    TEXT[],
            sort_order    INTEGER NOT NULL DEFAULT 0,
            notes         TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            -- Invariant: no frontier (U5) concept is ever core.
            CONSTRAINT ck_concepts_frontier_not_core CHECK (u_stage <> 'U5' OR NOT is_core)
        )
    """)
    op.execute("CREATE INDEX ix_concepts_u_stage ON concepts (u_stage, sort_order)")
    op.execute("""
        CREATE TRIGGER trg_concepts_updated_at
            BEFORE UPDATE ON concepts
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # ------------------------------------------------------------------
    # 3. concept_progress — the live tracker grid (user-scoped, soft-deleted).
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE concept_progress (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(id),
            concept_id      UUID NOT NULL REFERENCES concepts(id),
            ladder_stage    SMALLINT,
            confidence      SMALLINT,
            reps            INTEGER NOT NULL DEFAULT 0,
            last_practiced  DATE,
            notes           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted      BOOLEAN NOT NULL DEFAULT false,
            deleted_at      TIMESTAMPTZ,
            CONSTRAINT ck_concept_progress_ladder CHECK (ladder_stage BETWEEN 1 AND 4),
            CONSTRAINT ck_concept_progress_confidence CHECK (confidence BETWEEN 1 AND 5)
        )
    """)
    # One active progress row per (user, concept); soft-deleted rows excluded.
    op.execute("""
        CREATE UNIQUE INDEX ux_concept_progress_user_concept
            ON concept_progress (user_id, concept_id)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE INDEX ix_concept_progress_user
            ON concept_progress (user_id)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE TRIGGER trg_concept_progress_updated_at
            BEFORE UPDATE ON concept_progress
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # ------------------------------------------------------------------
    # 4. content_pages — created EMPTY here; the 5d ingest populates it.
    #    Seed/content, not user-editable, no soft-delete (re-ingest replaces).
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE content_pages (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug              VARCHAR(128) UNIQUE NOT NULL,
            title             TEXT NOT NULL,
            body              TEXT NOT NULL,
            u_stage           u_stage,
            tier              VARCHAR(32),
            label             VARCHAR(32),
            category          VARCHAR(64),
            tags              TEXT[],
            wikilink_targets  TEXT[],
            source_path       TEXT,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_content_pages_u_stage ON content_pages (u_stage)")
    op.execute("CREATE INDEX ix_content_pages_tags ON content_pages USING GIN (tags)")
    op.execute("""
        CREATE TRIGGER trg_content_pages_updated_at
            BEFORE UPDATE ON content_pages
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    # Tables (triggers + indexes dropped automatically with the table)
    op.execute("DROP TABLE IF EXISTS content_pages")
    op.execute("DROP TABLE IF EXISTS concept_progress")
    op.execute("DROP TABLE IF EXISTS concepts")
    # ENUM (after the tables that use it are gone)
    op.execute("DROP TYPE IF EXISTS u_stage")
