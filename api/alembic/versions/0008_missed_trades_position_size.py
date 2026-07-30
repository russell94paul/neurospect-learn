"""Missed-trade log (+ 2 enums) and journal_entries.position_size

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-25

Phase 6 (Phase-5 debt) — the two remaining journal gaps, in ONE reversible
migration because they land together and are a single unit of rollback.

6b — `missed_trades`. A SEPARATE lightweight table, deliberately NOT columns on
`journal_entries`, so executed-trade analytics (win rate, avg R, MAE/MFE,
expectancy) are never diluted by trades that were never taken. Adapted from
concepts/architecture/trade-schema.md §Missed Trades to THIS app's model-aligned
conventions: `entry_model` (the learn app's grouping key) replaces that doc's
`setup_type`, and `entry_date` matches `journal_entries` rather than its
`trade_date`. Provenance is canonical in concepts/aura/journaling-system.md
(aura-05): missed/canceled trades are a distinct journaling category, and the
analytic the table exists FOR is opportunity cost in R — a negative
`hypothetical_r` means the instinct to pull the order was PROTECTIVE.

`missed_trade_screenshots` is DELIBERATELY OMITTED. User-uploaded evidence is the
same primitive verified drill grading needs, and it is owned by the
learning-enforcement workstream — building it for the journal alone would
pre-commit its shape (what it attaches to, grading state, who verifies).

6c — `journal_entries.position_size` (nullable contracts/lots). RECORD-KEEPING
ONLY: expectancy stays R-based (`r_multiple` / `rr_planned` / `risk_pct`), and no
expectancy, analytics or gate computation reads this column.

Raw-SQL op.execute, matching 0002–0007; reuses update_updated_at() from 0001
(do NOT recreate it) and the `session_type` / `entry_model` enums from 0003.
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 6c: position_size on the executed-trade journal ---------------------
    op.execute("ALTER TABLE journal_entries ADD COLUMN position_size NUMERIC(10,2)")

    # --- 6b: the missed-trade log -------------------------------------------
    op.execute(
        "CREATE TYPE miss_type AS ENUM ('almost_took', 'hesitated', 'canceled')"
    )
    op.execute(
        "CREATE TYPE hypothetical_outcome AS ENUM "
        "('would_win', 'would_lose', 'would_breakeven', 'unknown')"
    )

    op.execute("""
        CREATE TABLE missed_trades (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id               UUID NOT NULL REFERENCES users(id),

            entry_date            DATE NOT NULL,
            instrument            VARCHAR(20) NOT NULL,
            session               session_type,
            entry_model           entry_model NOT NULL,

            miss_type             miss_type NOT NULL,
            reason                TEXT,
            hesitation_tags       TEXT[],

            planned_entry         NUMERIC(12,4),
            planned_stop          NUMERIC(12,4),
            planned_target        NUMERIC(12,4),
            rr_planned            NUMERIC(6,2),

            hypothetical_outcome  hypothetical_outcome,
            hypothetical_r        NUMERIC(6,2),

            narrative             TEXT,
            notes                 TEXT,

            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted            BOOLEAN NOT NULL DEFAULT false,
            deleted_at            TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE INDEX ix_missed_trades_user_date
            ON missed_trades (user_id, entry_date DESC)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE INDEX ix_missed_trades_user_model
            ON missed_trades (user_id, entry_model)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE INDEX ix_missed_trades_user_miss_type
            ON missed_trades (user_id, miss_type)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE INDEX ix_missed_trades_hesitation_tags
            ON missed_trades USING GIN (hesitation_tags)
    """)
    op.execute("""
        CREATE TRIGGER trg_missed_trades_updated_at
            BEFORE UPDATE ON missed_trades
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS missed_trades")
    op.execute("DROP TYPE IF EXISTS hypothetical_outcome")
    op.execute("DROP TYPE IF EXISTS miss_type")
    op.execute("ALTER TABLE journal_entries DROP COLUMN IF EXISTS position_size")
