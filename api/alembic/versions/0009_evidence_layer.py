"""Evidence layer (+ 4 enums) and reps becoming DERIVED

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-28

Phase E2 of the learning-enforcement workstream. ONE migration because the two
halves are a single unit of rollback: the evidence ledger only means anything if
`reps` stops being a self-reported integer at the same moment.

`evidence_assets` — the ONE polymorphic evidence layer, deliberately not the
per-owner child tables neurospect-api used (`trade_screenshots` +
`missed_trade_screenshots`). Three consumers were waiting on the same unbuilt
primitive on purpose — drill evidence, the journal's deferred screenshots (5c),
and `missed_trade_screenshots` (omitted from 0008) — and one table serves all
four subject kinds. A `subject_type` discriminator plus EXACTLY ONE subject
column, enforced by a CHECK that FAILS CLOSED: a row with zero subjects, two
subjects, or a subject that disagrees with its discriminator is rejected by the
DATABASE, not merely by Pydantic.

`evidence_grades` — child, ONE ROW PER GRADING PASS so a re-grade is additive
rather than destructive (concepts/architecture/learning-enforcement.md §7). E2
writes only the `deterministic` grader; `self_check` is E3 and `ai_vision` is E4.

REPS BECOME DERIVED. `concept_progress.reps` and `drill_progress.reps` are
RENAMED to `legacy_reps` and frozen at their pre-0009 values. No endpoint writes
them ever again; the API's `reps` is computed as
`legacy_reps + SUM(evidence_assets.reps_claimed)`. The rename is the point: any
code still writing `.reps` fails loudly instead of silently minting an
unevidenced rep. This is the same STRUCTURAL non-overridability the Gate has
(no `cleared` column ⇒ nothing can declare a model live-ready; no writable
`reps` ⇒ nothing can declare a rep done). The rename is non-destructive and
fully reversible, so no already-met stage un-meets — progress stays monotonic,
per the design's lifecycle decision.

Raw-SQL op.execute, matching 0002–0008; reuses update_updated_at() from 0001
(do NOT recreate it).
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- enums --------------------------------------------------------------
    op.execute(
        "CREATE TYPE evidence_subject AS ENUM "
        "('drill', 'concept', 'journal_entry', 'missed_trade')"
    )
    op.execute(
        "CREATE TYPE evidence_kind AS ENUM "
        "('chart_markup', 'written_artifact', 'computation', 'prediction', 'tape_read')"
    )
    op.execute(
        "CREATE TYPE evidence_grader AS ENUM "
        "('deterministic', 'self_check', 'ai_vision')"
    )
    op.execute(
        "CREATE TYPE evidence_grade_state AS ENUM "
        "('ungraded', 'pending', 'passed', 'flagged', 'failed')"
    )

    # --- evidence_assets ----------------------------------------------------
    # `subject_drill_ref` is a TEXT soft ref matching the drill_progress.drill_ref
    # convention (NOT a hard FK) so evidence outlives a re-seed. The other three
    # subjects are real FKs — those rows are user data, not seed content.
    op.execute("""
        CREATE TABLE evidence_assets (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id            UUID NOT NULL REFERENCES users(id),

            subject_type       evidence_subject NOT NULL,
            subject_drill_ref  TEXT,
            concept_id         UUID REFERENCES concepts(id),
            journal_entry_id   UUID REFERENCES journal_entries(id),
            missed_trade_id    UUID REFERENCES missed_trades(id),

            kind               evidence_kind NOT NULL,

            storage_key        TEXT NOT NULL,
            content_type       VARCHAR(100) NOT NULL,
            original_filename  TEXT,
            byte_size          BIGINT NOT NULL,
            sha256             CHAR(64) NOT NULL,
            perceptual_hash    VARCHAR(64),

            captured_at        TIMESTAMPTZ,
            reps_claimed       SMALLINT NOT NULL DEFAULT 1,
            notes              TEXT,

            created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted         BOOLEAN NOT NULL DEFAULT false,
            deleted_at         TIMESTAMPTZ,

            CONSTRAINT ck_evidence_reps_claimed CHECK (reps_claimed >= 0 AND reps_claimed <= 100),
            CONSTRAINT ck_evidence_byte_size CHECK (byte_size > 0),

            -- FAILS CLOSED. Exactly one subject column is populated AND it is
            -- the one `subject_type` names. Zero subjects, two subjects, or a
            -- concept_id under subject_type='drill' are all rejected here — the
            -- DB is the enforcement point, not the request schema.
            CONSTRAINT ck_evidence_subject_exactly_one CHECK (
                (
                    (subject_drill_ref IS NOT NULL)::int
                  + (concept_id       IS NOT NULL)::int
                  + (journal_entry_id IS NOT NULL)::int
                  + (missed_trade_id  IS NOT NULL)::int
                ) = 1
                AND CASE subject_type
                        WHEN 'drill'         THEN subject_drill_ref IS NOT NULL
                        WHEN 'concept'       THEN concept_id        IS NOT NULL
                        WHEN 'journal_entry' THEN journal_entry_id  IS NOT NULL
                        WHEN 'missed_trade'  THEN missed_trade_id   IS NOT NULL
                        ELSE false
                    END
            )
        )
    """)

    # The exact-duplicate BLOCK (design §5, "block the certain"): the same bytes
    # can never count twice for one user. Partial so a soft-deleted asset frees
    # its hash for an honest re-upload (which still yields the same one rep).
    op.execute("""
        CREATE UNIQUE INDEX ux_evidence_assets_user_sha256
            ON evidence_assets (user_id, sha256)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE INDEX ix_evidence_assets_user_drill
            ON evidence_assets (user_id, subject_drill_ref)
            WHERE NOT is_deleted AND subject_drill_ref IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_evidence_assets_user_concept
            ON evidence_assets (user_id, concept_id)
            WHERE NOT is_deleted AND concept_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_evidence_assets_user_journal
            ON evidence_assets (user_id, journal_entry_id)
            WHERE NOT is_deleted AND journal_entry_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_evidence_assets_user_missed
            ON evidence_assets (user_id, missed_trade_id)
            WHERE NOT is_deleted AND missed_trade_id IS NOT NULL
    """)
    # Near-duplicate lookup (perceptual hash) — scanned per user on upload.
    op.execute("""
        CREATE INDEX ix_evidence_assets_user_phash
            ON evidence_assets (user_id, perceptual_hash)
            WHERE NOT is_deleted AND perceptual_hash IS NOT NULL
    """)
    op.execute("""
        CREATE TRIGGER trg_evidence_assets_updated_at
            BEFORE UPDATE ON evidence_assets
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # --- evidence_grades ----------------------------------------------------
    # One row per grading PASS. There is deliberately NO unique constraint on
    # (evidence_id, grader): re-grading appends, so the grading history is an
    # append-only record rather than a mutable verdict.
    op.execute("""
        CREATE TABLE evidence_grades (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            evidence_id     UUID NOT NULL REFERENCES evidence_assets(id) ON DELETE CASCADE,
            user_id         UUID NOT NULL REFERENCES users(id),

            grader          evidence_grader NOT NULL,
            state           evidence_grade_state NOT NULL,
            score           NUMERIC(5,2),
            rubric_slug     TEXT,
            rubric_version  INTEGER,
            findings        JSONB,

            model           TEXT,
            input_tokens    INTEGER,
            output_tokens   INTEGER,
            cost_usd        NUMERIC(10,6),

            graded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted      BOOLEAN NOT NULL DEFAULT false,
            deleted_at      TIMESTAMPTZ,

            CONSTRAINT ck_evidence_grade_score CHECK (score IS NULL OR (score >= 0 AND score <= 100))
        )
    """)
    op.execute("""
        CREATE INDEX ix_evidence_grades_evidence
            ON evidence_grades (evidence_id, graded_at DESC)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE INDEX ix_evidence_grades_user_state
            ON evidence_grades (user_id, state)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE TRIGGER trg_evidence_grades_updated_at
            BEFORE UPDATE ON evidence_grades
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # --- reps become DERIVED ------------------------------------------------
    # Freeze what was claimed before evidence existed. Nothing writes these
    # columns after this migration; the API's `reps` = legacy_reps + Σ claimed.
    op.execute("ALTER TABLE concept_progress RENAME COLUMN reps TO legacy_reps")
    op.execute("ALTER TABLE drill_progress  RENAME COLUMN reps TO legacy_reps")


def downgrade() -> None:
    op.execute("ALTER TABLE drill_progress  RENAME COLUMN legacy_reps TO reps")
    op.execute("ALTER TABLE concept_progress RENAME COLUMN legacy_reps TO reps")

    op.execute("DROP TABLE IF EXISTS evidence_grades")
    op.execute("DROP TABLE IF EXISTS evidence_assets")

    op.execute("DROP TYPE IF EXISTS evidence_grade_state")
    op.execute("DROP TYPE IF EXISTS evidence_grader")
    op.execute("DROP TYPE IF EXISTS evidence_kind")
    op.execute("DROP TYPE IF EXISTS evidence_subject")
