"""Study Planner: study_preferences + plan_items (+ plan_activity / plan_item_status enums)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-22

Phase 5e-2 — the adaptive, gate-aware, retention-aware Study-Planner engine's
persistence layer. `study_preferences` is user-scoped + soft-deleted, ONE active
row per user (the availability + pacing prefs the `/plan/setup` UI edits, 5e-3).
`plan_items` is user-scoped + soft-deleted — the FROZEN past/today schedule (the
future is computed on read, never frozen until its date arrives; see
learning-platform.md §Study Planner persist-vs-compute).

The `drill_variant` enum ('hand' | 'tool') was created in 0004 and is CONSUMED
here (plan_items.drill_variant) — do NOT recreate it. Two NEW enums are created
here: `plan_activity` and `plan_item_status`. Raw-SQL op.execute idiom, matching
0002–0005; reuses update_updated_at() from 0001 (do NOT recreate it).

Multi-track reconciliation (5e-1b): `study_preferences.active_track` names which
of the three graded tracks the planner schedules (default 'aura', matching the
frontend's default track).

Idempotency note: `plan_items`' partial-unique index uses NULLS NOT DISTINCT
(Postgres 15+) so a concept-less item (concept_id + drill_ref both NULL, e.g. a
backtest-stage placeholder) still de-duplicates on re-materialization — without
it, Postgres would treat every NULL-ref row as distinct and daily materialize
would insert duplicates.
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. ENUMs: plan_activity + plan_item_status. drill_variant already exists
    #    (created in 0004) and is reused by plan_items — not recreated.
    # ------------------------------------------------------------------
    op.execute(
        "CREATE TYPE plan_activity AS ENUM "
        "('learn', 'drill', 'review', 'observe', 'habit', 'backtest')"
    )
    op.execute(
        "CREATE TYPE plan_item_status AS ENUM "
        "('pending', 'done', 'partial', 'skipped')"
    )

    # ------------------------------------------------------------------
    # 2. study_preferences — availability + pacing prefs, user-scoped +
    #    soft-deleted, ONE active row per user. Per-weekday minute budget
    #    (0 = day off); max single-session cap splits a day into blocks;
    #    timezone is load-bearing ("today"/day-of-week matter to the ICT
    #    curriculum). target_go_live_date is PACING-ONLY (drives the ETA /
    #    on-pace flag — NEVER advances a gate or unlocks a stage).
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE study_preferences (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id              UUID NOT NULL REFERENCES users(id),
            timezone             TEXT NOT NULL DEFAULT 'UTC',
            mon_minutes          SMALLINT NOT NULL DEFAULT 0,
            tue_minutes          SMALLINT NOT NULL DEFAULT 0,
            wed_minutes          SMALLINT NOT NULL DEFAULT 0,
            thu_minutes          SMALLINT NOT NULL DEFAULT 0,
            fri_minutes          SMALLINT NOT NULL DEFAULT 0,
            sat_minutes          SMALLINT NOT NULL DEFAULT 0,
            sun_minutes          SMALLINT NOT NULL DEFAULT 0,
            max_session_minutes  SMALLINT NOT NULL DEFAULT 60,
            blackout_dates       DATE[],
            target_go_live_date  DATE,
            active_track         VARCHAR(16) NOT NULL DEFAULT 'aura',
            plan_version         INTEGER NOT NULL DEFAULT 1,
            generated_at         TIMESTAMPTZ,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted           BOOLEAN NOT NULL DEFAULT false,
            deleted_at           TIMESTAMPTZ,
            CONSTRAINT ck_study_prefs_active_track
                CHECK (active_track IN ('aura', 'ict_course', 'unified')),
            CONSTRAINT ck_study_prefs_max_session
                CHECK (max_session_minutes > 0),
            CONSTRAINT ck_study_prefs_minutes CHECK (
                mon_minutes >= 0 AND tue_minutes >= 0 AND wed_minutes >= 0
                AND thu_minutes >= 0 AND fri_minutes >= 0 AND sat_minutes >= 0
                AND sun_minutes >= 0
            )
        )
    """)
    # One active prefs row per user (soft-deleted rows excluded).
    op.execute("""
        CREATE UNIQUE INDEX ux_study_prefs_user
            ON study_preferences (user_id)
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE TRIGGER trg_study_prefs_updated_at
            BEFORE UPDATE ON study_preferences
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    # ------------------------------------------------------------------
    # 3. plan_items — the frozen past/today schedule (user-scoped, soft-deleted).
    #    concept_id is a NULLABLE hard FK (learn/review/observe/habit items);
    #    drill_ref is a NULLABLE soft ref (drill items — matches the
    #    concepts.drill_refs / drill_progress.drill_ref convention). A concept-less
    #    evidence item (backtest) carries both NULL. done_qty feeds
    #    concept_progress/drill_progress reps when the item is marked done.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE plan_items (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(id),
            plan_version    INTEGER NOT NULL DEFAULT 1,
            scheduled_date  DATE NOT NULL,
            activity        plan_activity NOT NULL,
            concept_id      UUID REFERENCES concepts(id),
            drill_ref       TEXT,
            drill_variant   drill_variant,
            target_qty      INTEGER,
            target_unit     VARCHAR(16),
            est_minutes     SMALLINT NOT NULL DEFAULT 0,
            status          plan_item_status NOT NULL DEFAULT 'pending',
            done_qty        INTEGER NOT NULL DEFAULT 0,
            completed_at    TIMESTAMPTZ,
            sort_order      INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted      BOOLEAN NOT NULL DEFAULT false,
            deleted_at      TIMESTAMPTZ,
            CONSTRAINT ck_plan_items_done_qty CHECK (done_qty >= 0),
            CONSTRAINT ck_plan_items_est_minutes CHECK (est_minutes >= 0)
        )
    """)
    op.execute("""
        CREATE INDEX ix_plan_items_user_date
            ON plan_items (user_id, scheduled_date)
            WHERE NOT is_deleted
    """)
    # Keep daily materialization idempotent: one active item per
    # (user, date, activity, concept, drill, variant). NULLS NOT DISTINCT so a
    # concept-less (all-NULL-ref) item still de-duplicates (PG 15+).
    op.execute("""
        CREATE UNIQUE INDEX ux_plan_items_slot
            ON plan_items (user_id, scheduled_date, activity, concept_id,
                           drill_ref, drill_variant)
            NULLS NOT DISTINCT
            WHERE NOT is_deleted
    """)
    op.execute("""
        CREATE TRIGGER trg_plan_items_updated_at
            BEFORE UPDATE ON plan_items
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    # Tables first (indexes + triggers drop with the table), then the enums the
    # tables reference. drill_variant is NOT dropped here — it is owned by 0004.
    op.execute("DROP TABLE IF EXISTS plan_items")
    op.execute("DROP TABLE IF EXISTS study_preferences")
    op.execute("DROP TYPE IF EXISTS plan_item_status")
    op.execute("DROP TYPE IF EXISTS plan_activity")
