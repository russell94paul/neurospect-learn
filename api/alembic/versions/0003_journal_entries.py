"""Model-aligned journal: journal_entries + its enums + trigger + GIN indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-19

The model-aligned journal (NOT the generic trades schema). Enums defined FRESH
here. Reuses update_updated_at() from 0001. Raw-SQL op.execute idiom.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. ENUMs (fresh — the model-aligned journal, not neurospect-api's)
    # ------------------------------------------------------------------
    op.execute("CREATE TYPE journal_mode AS ENUM ('backtest', 'live')")
    op.execute("""
        CREATE TYPE entry_model AS ENUM (
            'consolidation', 'expansion_retracement', 'reversal_raid_on_stops',
            'london', 'model_2022_ote', 'daily_bias', 'smt_confirmation', 'unified'
        )
    """)
    op.execute("CREATE TYPE range_position AS ENUM ('discount', 'eq', 'premium')")
    op.execute("CREATE TYPE session_type AS ENUM ('asia', 'london', 'ny_am', 'ny_pm')")
    op.execute("""
        CREATE TYPE entry_pda AS ENUM (
            'fvg', 'ifvg', 'order_block', 'breaker', 'rejection_block', 'ote_block'
        )
    """)
    op.execute("CREATE TYPE outcome AS ENUM ('win', 'loss', 'breakeven')")
    op.execute("CREATE TYPE grade AS ENUM ('a_plus', 'a', 'b', 'c')")

    # ------------------------------------------------------------------
    # 2. journal_entries — user-scoped + soft-deleted.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE journal_entries (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id               UUID NOT NULL REFERENCES users(id),

            -- Identity / context
            entry_date            DATE NOT NULL,
            instrument            VARCHAR(20) NOT NULL,
            session               session_type,
            mode                  journal_mode NOT NULL,

            -- Model (expectancy-grouping key)
            entry_model           entry_model NOT NULL,

            -- Decision-flow capture (model-aligned)
            draw_on_liquidity     TEXT,
            range_position        range_position,
            swing_qualification   SMALLINT,
            seq_smt_confirmed     BOOLEAN,
            triad_smt_confirmed   BOOLEAN,
            aura_asset_leg        BOOLEAN,
            time_window_valid     BOOLEAN,
            entry_pda             entry_pda DEFAULT 'fvg',

            -- Execution / risk
            entry_price           DECIMAL(12,4),
            stop_price            DECIMAL(12,4),
            target_price          DECIMAL(12,4),
            rr_planned            DECIMAL(6,2),
            risk_pct              DECIMAL(5,2),
            exit_price            DECIMAL(12,4),
            r_multiple            DECIMAL(6,2),
            outcome               outcome,
            mae                   DECIMAL(12,4),
            mfe                   DECIMAL(12,4),

            -- Frontier stack (watch-only — NEVER gate-eligible)
            confluence_tags       TEXT[],

            -- Review
            plan_followed         BOOLEAN,
            mistake_tags          TEXT[],
            grade                 grade,
            notes                 TEXT,

            -- Metadata
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted            BOOLEAN NOT NULL DEFAULT false,
            deleted_at            TIMESTAMPTZ,

            CONSTRAINT ck_journal_swing_qualification CHECK (swing_qualification BETWEEN 0 AND 2)
        )
    """)

    # ------------------------------------------------------------------
    # 3. Indexes — per-user + per-grouping-key (entry_model, mode); GIN on TEXT[]
    # ------------------------------------------------------------------
    op.execute("CREATE INDEX ix_journal_user_date ON journal_entries (user_id, entry_date DESC)")
    op.execute("CREATE INDEX ix_journal_user_model ON journal_entries (user_id, entry_model) WHERE NOT is_deleted")
    op.execute("CREATE INDEX ix_journal_user_mode ON journal_entries (user_id, mode) WHERE NOT is_deleted")
    op.execute("CREATE INDEX ix_journal_user_outcome ON journal_entries (user_id, outcome) WHERE NOT is_deleted")
    op.execute("CREATE INDEX ix_journal_mistake_tags ON journal_entries USING GIN (mistake_tags) WHERE NOT is_deleted")
    op.execute("CREATE INDEX ix_journal_confluence_tags ON journal_entries USING GIN (confluence_tags) WHERE NOT is_deleted")

    op.execute("""
        CREATE TRIGGER trg_journal_entries_updated_at
            BEFORE UPDATE ON journal_entries
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    # Table (triggers + indexes dropped automatically with the table)
    op.execute("DROP TABLE IF EXISTS journal_entries")
    # ENUMs (after the table that uses them is gone)
    op.execute("DROP TYPE IF EXISTS grade")
    op.execute("DROP TYPE IF EXISTS outcome")
    op.execute("DROP TYPE IF EXISTS entry_pda")
    op.execute("DROP TYPE IF EXISTS session_type")
    op.execute("DROP TYPE IF EXISTS range_position")
    op.execute("DROP TYPE IF EXISTS entry_model")
    op.execute("DROP TYPE IF EXISTS journal_mode")
