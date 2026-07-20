"""Initial schema: update_updated_at() trigger fn + users table + trigger

Revision ID: 0001
Revises:
Create Date: 2026-07-19
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. updated_at trigger function (must exist before tables reference it)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    # ------------------------------------------------------------------
    # 2. users table + updated_at trigger
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE users (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            discord_id          VARCHAR(32) UNIQUE NOT NULL,
            discord_username    VARCHAR(128),
            discord_avatar_url  TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TRIGGER trg_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    # Table (trigger dropped automatically with the table)
    op.execute("DROP TABLE IF EXISTS users")
    # Trigger function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at")
