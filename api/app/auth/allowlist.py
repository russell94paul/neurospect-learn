"""Who is allowed to hold an account on this instance (Phase B3 — deployment).

Until B3 the app only ever ran on localhost, so "any Discord user may sign in"
cost nothing: no stranger could reach :8000. A public URL changes that — the
Discord app is Public by design, so without this module anybody who finds the
host can mint themselves an account, and (once `AI_GRADING_ENABLED` is on) spend
Paul's Anthropic credit doing it.

TWO DECISIONS WORTH THE COMMENT
-------------------------------
**It fails CLOSED in production, not open.** An empty `ALLOWED_DISCORD_IDS` means
"everyone" when `DEBUG=true` (localhost, the test suite, the debug-token flow)
and "nobody" when `DEBUG=false`. The fail-open version reads more forgiving and
is worse: forgetting one env var would silently leave the deployment open, and
nothing would ever surface it. Forgetting it here produces an immediate, obvious
403 on the first login attempt, with a detail string that names the fix. `debug`
is already this codebase's prod/dev discriminator (`POST /auth/debug/token` is
404 when it is false), so this adds no new concept.

**It is enforced on every authenticated request, not only at token issue.** JWTs
live 30 days (`JWT_EXPIRE_MINUTES=43200`). Checking only in
`POST /auth/discord/token` would mean removing someone from the allowlist leaves
them a working session for up to a month. `get_current_user` has already loaded
the `User` row, so the check there is one string comparison and no extra query —
and revocation takes effect on the user's next request.

This module is pure and DB-free; it reads settings and answers a question.
"""

from app.config import settings


def is_allowed(discord_id: str | None) -> bool:
    """May this Discord account hold an account on this instance?

    - allowlist set  → membership decides, in every mode.
    - allowlist empty and `DEBUG=true`  → yes (localhost / tests / debug tokens).
    - allowlist empty and `DEBUG=false` → **no** (see the fail-closed note above).
    """
    allowed = settings.allowed_discord_ids
    if allowed:
        return discord_id in allowed
    return settings.debug


#: The 403 detail. It names the env var deliberately: the single most likely
#: cause of seeing this is a deploy where `ALLOWED_DISCORD_IDS` was never set,
#: and a message that does not say so costs an hour.
FORBIDDEN_DETAIL = (
    "This instance is restricted to allowlisted Discord accounts. "
    "Set ALLOWED_DISCORD_IDS to admit one."
)
