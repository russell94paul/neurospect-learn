"""Pre-commitment ledger — a call that is worthless unless it precedes the reveal

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-10

Phase E5 of the learning-enforcement workstream. E2 made a rep require EVIDENCE,
E3 made it require the drill's own bar, E4 added an advisory second reader. E5
adds the one primitive none of them can supply: proof that a judgement was made
BEFORE the outcome was known.

concepts/architecture/learning-enforcement.md §9 owns the design; this file owns
the DDL. `ict_course` M6's bar is T-01…T-13 ("study the mentor's read, then
replicate blind on a comparable session") plus T-14 (a blind live read), and
their honest form REQUIRES commitment before the reveal — so the call itself
(bias · DOL · model · target) is the evidence, timestamped by the SERVER.

THREE STRUCTURAL PROPERTIES, each enforced here rather than in application code
(the §E2 argument: a guard has to be remembered at every new write path; a
structural property cannot be forgotten):

1. **The call is FROZEN at commit.** `trg_predictions_freeze_the_call` raises if
   bias / dol / entry_model / target / drill_ref / committed_at ever change. So a
   prediction cannot be edited into a win after the fact — the strongest form of
   "cannot be back-dated" this layer can actually enforce.
2. **The reveal is written ONCE, and strictly later.**
   `ck_predictions_reveal_follows_commit` puts the ordering in the schema, and the
   same trigger refuses a second resolution — otherwise a call could be re-scored
   until it landed.
3. **THERE IS NO `is_deleted` COLUMN — deliberately.** This DIVERGES from the
   soft-delete convention every other user table here follows (`evidence_assets`,
   `journal_entries`, `missed_trades`), and the divergence is the point: the
   calibration score is a RATIO, so the way to game it is not to add volume but
   to make failures disappear. With no delete path and no edit path the
   denominator can only ever GROW, which is what makes the score
   Goodhart-resistant *structurally* rather than by policy. A mistyped call is
   answered by committing a fresh one; the mistake stays in the record as
   unresolved, and the unresolved count is surfaced.

Reads `entry_model` (0003) rather than minting a second vocabulary of models, and
reuses `update_updated_at()` (0001 — do NOT recreate it). Raw-SQL `op.execute`,
matching 0002–0010.
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- enum ---------------------------------------------------------------
    # A directional call. `neutral` is first-class, not a fallback: "no directional
    # conviction, stand aside" IS the correct read on several of the tape sessions
    # (T-04's Fed-speaker day names "standing aside" explicitly), and forcing a
    # long/short call there would train the opposite of the lesson.
    op.execute("CREATE TYPE prediction_bias AS ENUM ('long', 'short', 'neutral')")

    # --- predictions --------------------------------------------------------
    # `drill_ref` is a TEXT soft ref to `drills.drill_ref` — the same convention as
    # `drill_progress.drill_ref`, `evidence_assets.subject_drill_ref` and
    # `rubrics.drill_ref` — so a commitment survives a `drills` re-seed.
    #
    # `evidence_id` is NULLABLE and is the marked chart captured WITH the call. It
    # is a link, never a rep: reps come only from `evidence_assets.reps_claimed`
    # (E2), and nothing here writes one. Invariant 5 holds — `reps` gains no path.
    op.execute("""
        CREATE TABLE predictions (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id           UUID NOT NULL REFERENCES users(id),

            drill_ref         TEXT NOT NULL,
            -- WHICH session is being called (the wiki's method step: "find a
            -- matching session by the news tag"). Free text because the corpus
            -- identifies sessions by news context, not by a key we own.
            session_label     TEXT NOT NULL,
            instrument        TEXT,

            -- ================= THE CALL — frozen at commit =================
            -- The four things the wiki itself names, for both T-01…13 ("note bias
            -- call, DOL, the model used, entry/target") and T-14 ("call the read
            -- (bias, DOL, model, target) before it resolves").
            bias              prediction_bias NOT NULL,
            dol               TEXT NOT NULL,
            entry_model       entry_model NOT NULL,
            target            TEXT NOT NULL,

            -- SERVER-STAMPED, never client-supplied, never updatable. The whole
            -- anti-cheat value of this table is in this column being trustworthy.
            committed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

            -- ================= THE REVEAL — a strictly later write =========
            resolved_at       TIMESTAMPTZ,
            outcome_bias      prediction_bias,
            dol_hit           BOOLEAN,
            model_played_out  BOOLEAN,
            target_hit        BOOLEAN,
            resolution_notes  TEXT,

            evidence_id       UUID REFERENCES evidence_assets(id),

            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

            -- The ordering property, in the schema: a reveal can never precede
            -- the commitment it is scored against.
            CONSTRAINT ck_predictions_reveal_follows_commit
                CHECK (resolved_at IS NULL OR resolved_at >= committed_at),

            -- Resolution is ALL-OR-NOTHING, and FAILS CLOSED — the same shape as
            -- 0009's exactly-one-subject CHECK. A half-written reveal would make
            -- the calibration denominator ambiguous.
            CONSTRAINT ck_predictions_resolution_complete CHECK (
                (
                    resolved_at IS NULL
                    AND outcome_bias IS NULL AND dol_hit IS NULL
                    AND model_played_out IS NULL AND target_hit IS NULL
                )
                OR
                (
                    resolved_at IS NOT NULL
                    AND outcome_bias IS NOT NULL AND dol_hit IS NOT NULL
                    AND model_played_out IS NOT NULL AND target_hit IS NOT NULL
                )
            ),

            CONSTRAINT ck_predictions_session_label CHECK (length(btrim(session_label)) > 0),
            CONSTRAINT ck_predictions_dol CHECK (length(btrim(dol)) > 0),
            CONSTRAINT ck_predictions_target CHECK (length(btrim(target)) > 0)
        )
    """)
    # No partial `WHERE NOT is_deleted` predicate on these indexes, because there
    # is no such column (see the module docstring — that absence is the design).
    op.execute("CREATE INDEX ix_predictions_user_drill ON predictions (user_id, drill_ref)")
    op.execute(
        "CREATE INDEX ix_predictions_user_committed ON predictions (user_id, committed_at)"
    )

    # --- the call is frozen -------------------------------------------------
    # This is E5's load-bearing guarantee, and it lives at the DB so that no
    # future endpoint can bypass it — the same reasoning that made `reps` derived
    # rather than guarded (§E2 as-built, THE LOAD-BEARING CALL).
    op.execute("""
        CREATE OR REPLACE FUNCTION predictions_freeze_the_call() RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.user_id     IS DISTINCT FROM OLD.user_id
            OR NEW.drill_ref   IS DISTINCT FROM OLD.drill_ref
            OR NEW.bias        IS DISTINCT FROM OLD.bias
            OR NEW.dol         IS DISTINCT FROM OLD.dol
            OR NEW.entry_model IS DISTINCT FROM OLD.entry_model
            OR NEW.target      IS DISTINCT FROM OLD.target
            OR NEW.committed_at IS DISTINCT FROM OLD.committed_at
            THEN
                RAISE EXCEPTION
                    'a committed prediction is frozen: user_id, drill_ref, bias, dol, '
                    'entry_model, target and committed_at cannot change after commit';
            END IF;

            IF OLD.resolved_at IS NOT NULL AND (
                   NEW.resolved_at      IS DISTINCT FROM OLD.resolved_at
                OR NEW.outcome_bias     IS DISTINCT FROM OLD.outcome_bias
                OR NEW.dol_hit          IS DISTINCT FROM OLD.dol_hit
                OR NEW.model_played_out IS DISTINCT FROM OLD.model_played_out
                OR NEW.target_hit       IS DISTINCT FROM OLD.target_hit
            ) THEN
                RAISE EXCEPTION
                    'this prediction is already resolved: its outcome is a record, not a draft';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_predictions_freeze_the_call
            BEFORE UPDATE ON predictions
            FOR EACH ROW
            EXECUTE FUNCTION predictions_freeze_the_call()
    """)
    op.execute("""
        CREATE TRIGGER trg_predictions_updated_at
            BEFORE UPDATE ON predictions
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    # The table's triggers go with it; the FUNCTION is E5's own (unlike
    # update_updated_at(), which 0001 owns and this migration must never drop).
    op.execute("DROP TABLE IF EXISTS predictions")
    op.execute("DROP FUNCTION IF EXISTS predictions_freeze_the_call")
    op.execute("DROP TYPE IF EXISTS prediction_bias")
