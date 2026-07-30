"""Gate attestations (+ the gate_attestation_item enum)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-24

Phase 5g — the ONLY new persistence the Readiness-to-Live Gate needs. Sources
(a) and (b) of the gate already exist (`concept_progress` from 5e-1,
`journal_entries` from 5c/5f) and the verdict itself is COMPUTED on every read,
never stored — so there is deliberately no `gate_status` / `cleared` column
anywhere: nothing can be written to declare a model live-ready.

`gate_attestations` stores source (c): the four behavioural checklist items of
concepts/mastery/README §Gate that no data can prove (risk precommitted in
writing · demo/sim track record · journaling habit · circuit-breaker
demonstrated). Per-user (behaviour is a property of the trader, not of a model),
one active row per (user, item), revocable (`attested` back to false), with an
optional `note` pointing at where the written evidence lives.

User-scoped + soft-deleted with the partial unique index, exactly the
`concept_progress` (0002) / `drill_progress` (0004) idiom. Raw-SQL op.execute,
matching 0002–0006; reuses update_updated_at() from 0001 (do NOT recreate it).
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE gate_attestation_item AS ENUM "
        "('risk_precommitted', 'sim_track_record', 'journaling_habit', 'circuit_breaker')"
    )

    op.execute("""
        CREATE TABLE gate_attestations (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      UUID NOT NULL REFERENCES users(id),
            item         gate_attestation_item NOT NULL,
            attested     BOOLEAN NOT NULL DEFAULT false,
            attested_at  TIMESTAMPTZ,
            note         TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted   BOOLEAN NOT NULL DEFAULT false,
            deleted_at   TIMESTAMPTZ
        )
    """)
    # One active attestation per (user, item) — the lazy-upsert target.
    op.execute("""
        CREATE UNIQUE INDEX ux_gate_attest_user_item
            ON gate_attestations (user_id, item)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE TRIGGER trg_gate_attest_updated_at
            BEFORE UPDATE ON gate_attestations
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS gate_attestations")
    op.execute("DROP TYPE IF EXISTS gate_attestation_item")
