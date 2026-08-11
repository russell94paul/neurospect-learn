"""Declared rest days — a day off you booked BEFORE it happened

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-10

Phase E6 of the learning-enforcement workstream, and the only table it needs.

concepts/architecture/learning-enforcement.md §6 asks for "declared rest days in
`study_preferences` — declared *in advance*, unlike a retroactive streak freeze,
which keeps the streak honest." The whole mechanic is in those three words *in
advance*: a rest day you can add after a day you missed is a streak freeze with
extra steps, and §6 rejects streak freezes precisely because they let the number
survive the behaviour it is supposed to measure.

WHY THIS IS NOT `study_preferences.blackout_dates` (which already exists).
`blackout_dates` is a `DATE[]` on a mutable row, rewritten wholesale by
`PUT /api/preferences`. It therefore accepts ANY date, including yesterday's, and
it records nothing about WHEN a date was added. It cannot answer "was this
declared in advance?" even in principle — the column has no room to store the
answer. It is also a different concept: it tells the SCHEDULER not to plan work,
which is a pacing input (Phase 5e-2), not a claim about a streak. E6 therefore
leaves it entirely alone and adds a table that can carry the property, rather than
overloading a column that would silently become the retroactive freeze §6 forbids.
Flagged in the doc's §Contradiction flags so the overlap is not rediscovered.

TWO STRUCTURAL PROPERTIES, both in the DB rather than the router — the §E2/§E5
argument, that a guard has to be remembered at every new write path while a
structural property cannot be forgotten:

1. **A rest day cannot be declared for a day that has already passed.**
   `trg_rest_days_declared_in_advance` raises when `rest_date` is before the
   server's current UTC date. Not a CHECK constraint: Postgres refuses non-
   IMMUTABLE expressions in CHECK, and every form of "today" (`now()::date`,
   `declared_at::date`, `AT TIME ZONE`) is STABLE at best. A trigger is the only
   place this rule can actually live, and it is where `0011` put the equivalent.
2. **`declared_at` and `rest_date` are frozen after insert**, so a booked day
   cannot be slid onto a day you later turn out to have missed.

THERE IS NO `is_deleted` COLUMN — the same deliberate divergence `0011` made, for
a related reason. A rest day's only effect is that it does not BREAK a streak, so
the record is only trustworthy if the set of declared days is the set you actually
committed to in advance. Append-only keeps "what did you book, and when" answerable
forever. A rest day you end up working through costs nothing: evidence captured on
that day counts exactly as it always would.

WHAT THIS STILL CANNOT PREVENT, stated plainly: declaring a long run of future
days as rest days keeps a streak alive without doing any work. That is not fixable
by a constraint — a genuine month of planned leave and a month of pre-emptive
excuses are the same rows. So it is SURFACED instead: the adherence surface reports
how many days of the current streak were declared rest days, which makes a mostly-
rest streak read as one. "Block the certain, surface the rest" (§5).

Reuses `update_updated_at()` (0001 — do NOT recreate it). Raw-SQL `op.execute`,
matching 0002–0011.
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `reason` is free text and OPTIONAL. It is deliberately not an enum: the
    # point of a declared rest day is that you booked it, not that you justified
    # it to the app, and a required reason is friction on the honest path (the
    # north star's own test — a design that frustrates honest work fails it as
    # hard as one that can be faked).
    op.execute("""
        CREATE TABLE rest_days (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id),

            rest_date   DATE NOT NULL,
            reason      TEXT,

            -- SERVER-STAMPED, never client-supplied, never updatable. The whole
            -- value of this table is that this column and `rest_date` can be
            -- compared later and the comparison means something.
            declared_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT ck_rest_days_reason
                CHECK (reason IS NULL OR length(btrim(reason)) > 0)
        )
    """)
    # One declaration per user per day. No partial `WHERE NOT is_deleted`
    # predicate, because there is no such column (see the module docstring —
    # that absence is the design), so ON CONFLICT infers this index directly.
    op.execute("CREATE UNIQUE INDEX ux_rest_days_user_date ON rest_days (user_id, rest_date)")

    # --- declared in advance, and frozen afterwards --------------------------
    # E6's load-bearing guarantee. It lives at the DB so no future endpoint can
    # bypass it, exactly as `0011` did for the frozen call.
    op.execute("""
        CREATE OR REPLACE FUNCTION rest_days_declared_in_advance() RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                -- The server's clock decides what "already happened" means. A
                -- client-supplied date for a past day is refused outright: that
                -- row would be a retroactive streak freeze, which §6 rejects.
                IF NEW.rest_date < (now() AT TIME ZONE 'UTC')::date THEN
                    RAISE EXCEPTION
                        'a rest day must be declared in advance: % has already passed '
                        '(server date %). A day off booked after the fact is a streak '
                        'freeze, and the streak is only worth reading if it cannot be '
                        'repaired retroactively.', NEW.rest_date, (now() AT TIME ZONE 'UTC')::date;
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.user_id     IS DISTINCT FROM OLD.user_id
            OR NEW.rest_date   IS DISTINCT FROM OLD.rest_date
            OR NEW.declared_at IS DISTINCT FROM OLD.declared_at
            THEN
                RAISE EXCEPTION
                    'a declared rest day is frozen: user_id, rest_date and declared_at '
                    'cannot change after it is booked';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_rest_days_declared_in_advance
            BEFORE INSERT OR UPDATE ON rest_days
            FOR EACH ROW
            EXECUTE FUNCTION rest_days_declared_in_advance()
    """)
    op.execute("""
        CREATE TRIGGER trg_rest_days_updated_at
            BEFORE UPDATE ON rest_days
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    # The table's triggers go with it; the FUNCTION is E6's own (unlike
    # update_updated_at(), which 0001 owns and this migration must never drop).
    op.execute("DROP TABLE IF EXISTS rest_days")
    op.execute("DROP FUNCTION IF EXISTS rest_days_declared_in_advance")
