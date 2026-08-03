"""Rubric layer (+1 enum) — the projected bar a self-check is judged against

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-29

Phase E3 of the learning-enforcement workstream. E2 made a rep require
EVIDENCE; E3 makes it require evidence the user has checked against the drill's
own bar. These two tables hold that bar.

THEY HOLD NO AUTHORED CONTENT. Every `rubric_items.text` is a verbatim clause of
a ✋/🛠 bullet in one of the two wiki exercise libraries
(concepts/mastery/{aura,ict-course}/exercises.md), projected by
scripts/seed_rubrics.py exactly as scripts/seed_drills.py projects the map
tables. The wiki stays canonical; a re-seed propagates an edit; there is no
second copy to drift. `content_hash` is what makes that mechanical — the version
bumps if and only if the projected text changed, so re-seeding unchanged content
is a no-op and a historical grade's `rubric_version` still names the bar it was
judged against.

SEED CONTENT, so NO SOFT-DELETE and no user scoping — mirroring `drills` and
`concepts`, where a re-seed replaces rows outright. Nothing here is user data:
the user's answer to a rubric lands in `evidence_grades` (grader='self_check'),
which 0009 already created — E3 adds NO grading table.

Raw-SQL op.execute, matching 0002–0009; reuses update_updated_at() from 0001
(do NOT recreate it).
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- enum ---------------------------------------------------------------
    # Which drill variant an item belongs to, tagged by the wiki's own glyph:
    # ✋ hand-marking (do first — trains the eye) · 🛠 tool-assisted. `either` is
    # NOT a default-when-unsure: it means the wiki bullet carries NO glyph, which
    # is how the corpus writes items that are neither (a computation, a written
    # artifact, a procedure). Recording that faithfully beats guessing a variant.
    op.execute("CREATE TYPE rubric_variant AS ENUM ('hand', 'tool', 'either')")

    # --- rubrics ------------------------------------------------------------
    # `drill_ref` is a TEXT soft ref to `drills.drill_ref` (the same convention
    # as `drill_progress.drill_ref` and `evidence_assets.subject_drill_ref`) —
    # NOT a hard FK, so a rubric survives a `drills` re-seed and a rubric can
    # exist for a drill the map table has not yet listed.
    op.execute("""
        CREATE TABLE rubrics (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),

            slug          TEXT NOT NULL,
            drill_ref     TEXT NOT NULL,
            track         VARCHAR(16) NOT NULL,

            -- Bumps ONLY when content_hash changes, so a historical grade's
            -- rubric_version identifies the exact bar it was judged against.
            version       INTEGER NOT NULL DEFAULT 1,
            content_hash  CHAR(64) NOT NULL,

            -- Provenance: which wiki file, and the drill's own source marker
            -- (e.g. "(aura-06; target ≥50)") copied verbatim, never parsed into
            -- a number here — `drills.rep_target` already owns the target.
            source_path   TEXT NOT NULL,
            source_ref    TEXT,

            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT ck_rubrics_track CHECK (track IN ('aura', 'ict_course')),
            CONSTRAINT ck_rubrics_version CHECK (version >= 1)
        )
    """)
    op.execute("CREATE UNIQUE INDEX ux_rubrics_slug ON rubrics (slug)")
    op.execute("CREATE UNIQUE INDEX ux_rubrics_drill_ref ON rubrics (drill_ref)")
    op.execute("CREATE INDEX ix_rubrics_track ON rubrics (track)")
    op.execute("""
        CREATE TRIGGER trg_rubrics_updated_at
            BEFORE UPDATE ON rubrics
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # --- rubric_items -------------------------------------------------------
    # ONE ROW PER PROJECTED CLAUSE. `item_key` ("aura-d1-a#3") is the stable
    # handle a self-check records in evidence_grades.findings — a TEXT key rather
    # than the row UUID on purpose: findings must stay readable after a re-seed
    # replaces these rows, and the grade also stores the item text, so an old
    # grade remains legible even if the wiki bullet later changed.
    op.execute("""
        CREATE TABLE rubric_items (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            rubric_id       UUID NOT NULL REFERENCES rubrics(id) ON DELETE CASCADE,

            item_key        TEXT NOT NULL,
            ordinal         SMALLINT NOT NULL,
            -- Which source bullet this clause came from, so the UI can group a
            -- bullet's clauses the way the wiki reads.
            bullet_ordinal  SMALLINT NOT NULL,

            variant         rubric_variant NOT NULL,
            -- VERBATIM wiki text (raw markdown kept, so the no-drift assertion
            -- is a literal substring check against the source bullet).
            text            TEXT NOT NULL,
            -- Rule cross-refs ([R8], [R15–R16]) lifted out of the clause: they
            -- are provenance, not part of the assertion being checked.
            rule_refs       TEXT[],

            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT ck_rubric_items_ordinal CHECK (ordinal >= 1),
            CONSTRAINT ck_rubric_items_bullet_ordinal CHECK (bullet_ordinal >= 1),
            CONSTRAINT ck_rubric_items_text CHECK (length(btrim(text)) > 0)
        )
    """)
    op.execute("CREATE UNIQUE INDEX ux_rubric_items_key ON rubric_items (item_key)")
    op.execute("""
        CREATE UNIQUE INDEX ux_rubric_items_rubric_ordinal
            ON rubric_items (rubric_id, ordinal)
    """)
    op.execute("""
        CREATE TRIGGER trg_rubric_items_updated_at
            BEFORE UPDATE ON rubric_items
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    # rubric_items first — it FKs rubrics (ON DELETE CASCADE covers rows, not
    # the table dependency).
    op.execute("DROP TABLE IF EXISTS rubric_items")
    op.execute("DROP TABLE IF EXISTS rubrics")
    op.execute("DROP TYPE IF EXISTS rubric_variant")
