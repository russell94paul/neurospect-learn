"""The Discord allowlist that makes a public deployment single-user (Phase B3).

Same harness as the other API tests: in-process ASGI transport, debug JWTs, one
throwaway user per test (`b3a-`), hard-cleaned afterwards.

What only this file can prove, and what each claim in `app/auth/allowlist.py`
would cost if it were wrong:

  * **It fails CLOSED in prod.** An unset `ALLOWED_DISCORD_IDS` admits everyone
    on localhost and NOBODY when `DEBUG=false`. The inverse — the "forgiving"
    default — is a silently-open deployment, which is the failure this phase
    exists to prevent.
  * **A refused login leaves no `users` row.** Asserted against the DB after a
    403, with Discord's two network calls stubbed. A door that records everyone
    who was turned away is not closed, it is just polite.
  * **Enforcement survives the token.** A JWT minted while allowed stops working
    once the holder leaves the allowlist, WITHOUT waiting out its 30-day life.
    This is the claim that distinguishes a per-request check from a signup gate,
    so it is proven by moving the allowlist under a live token.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth import allowlist
from app.config import settings
from app.deps import get_db
from app.main import app
from app.models.user import User

_test_engine = create_async_engine(settings.async_database_url, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(bind=_test_engine, expire_on_commit=False)

_PREFIX = "b3a-"


async def _override_get_db():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _use_test_db():
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    async with AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.discord_id.like(f"{_PREFIX}%")))
        await db.commit()


@pytest.fixture(autouse=True)
def _restore_settings():
    """Every test here mutates global settings; put them back whatever happens,
    or one failure silently locks out every later test in the session."""
    ids, debug = settings.allowed_discord_ids, settings.debug
    yield
    settings.allowed_discord_ids, settings.debug = ids, debug


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _token(c, discord_id):
    r = await c.post("/auth/debug/token", json={"discord_id": discord_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# The decision table, unit level
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "allowed,debug,discord_id,expected",
    [
        # Unset: open on localhost, SHUT in prod. The asymmetry is the point.
        ([], True, "anyone", True),
        ([], False, "anyone", False),
        ([], False, None, False),
        # Set: membership decides, and `debug` stops mattering in both directions.
        (["a"], True, "a", True),
        (["a"], True, "b", False),
        (["a"], False, "a", True),
        (["a"], False, "b", False),
        (["a", "b"], False, "b", True),
        # No accidental substring or falsy matching.
        (["12345"], False, "1234", False),
        (["12345"], False, None, False),
    ],
)
def test_is_allowed_decision_table(allowed, debug, discord_id, expected):
    settings.allowed_discord_ids = allowed
    settings.debug = debug
    assert allowlist.is_allowed(discord_id) is expected


def test_an_empty_allowlist_in_prod_admits_nobody_at_all():
    """The fail-closed claim, stated as its own test because it is the one a
    future 'simplification' would most plausibly reverse."""
    settings.allowed_discord_ids = []
    settings.debug = False
    for candidate in ["", "0", "1", "paul", "999999999999999999", None]:
        assert allowlist.is_allowed(candidate) is False


# ---------------------------------------------------------------------------
# The API surface
# ---------------------------------------------------------------------------

async def test_a_refused_oauth_login_creates_no_user_row(monkeypatch):
    """403 at `/auth/discord/token`, and NOTHING written. Discord's two network
    calls are stubbed so this exercises the real handler, not a mock of it."""
    stranger = f"{_PREFIX}stranger"

    async def _fake_exchange(code, redirect_uri):
        return "fake-discord-access-token"

    async def _fake_user(token):
        return {"id": stranger, "username": "stranger", "avatar": None}

    monkeypatch.setattr("app.auth.router.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.auth.router.get_discord_user", _fake_user)

    settings.allowed_discord_ids = [f"{_PREFIX}resident"]
    settings.debug = False

    async with await _client() as c:
        r = await c.post(
            "/auth/discord/token",
            json={"code": "x", "redirect_uri": "http://t/auth/callback"},
        )
    assert r.status_code == 403, r.text

    async with AsyncSessionLocal() as db:
        found = (
            await db.execute(select(User).where(User.discord_id == stranger))
        ).scalar_one_or_none()
    assert found is None, "a refused login must not leave a users row behind"


async def test_an_allowlisted_oauth_login_still_works(monkeypatch):
    """The other half — the allowlist must not break the flow it guards."""
    resident = f"{_PREFIX}resident-ok"

    async def _fake_exchange(code, redirect_uri):
        return "fake-discord-access-token"

    async def _fake_user(token):
        return {"id": resident, "username": "resident", "avatar": None}

    monkeypatch.setattr("app.auth.router.exchange_code", _fake_exchange)
    monkeypatch.setattr("app.auth.router.get_discord_user", _fake_user)

    settings.allowed_discord_ids = [resident]
    settings.debug = False

    async with await _client() as c:
        r = await c.post(
            "/auth/discord/token",
            json={"code": "x", "redirect_uri": "http://t/auth/callback"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


async def test_removal_from_the_allowlist_kills_a_live_token_immediately():
    """The claim a signup-only gate cannot make. Mint a token while allowed, use
    it successfully, then remove the holder — the SAME token must stop working
    on the very next request rather than at its 30-day expiry."""
    holder = f"{_PREFIX}evicted"

    async with await _client() as c:
        settings.allowed_discord_ids = []
        settings.debug = True
        h = await _token(c, holder)

        settings.allowed_discord_ids = [holder]
        ok = await c.get("/auth/me", headers=h)
        assert ok.status_code == 200, ok.text
        assert ok.json()["discord_id"] == holder

        # Evict. Same token, next request.
        settings.allowed_discord_ids = [f"{_PREFIX}somebody-else"]
        after = await c.get("/auth/me", headers=h)
        assert after.status_code == 403, after.text


async def test_the_guard_is_what_produces_the_403():
    """Prove the refusal comes from the allowlist and not from some unrelated
    401/404 path: the identical request succeeds once the holder is readmitted."""
    holder = f"{_PREFIX}readmitted"

    async with await _client() as c:
        settings.allowed_discord_ids = []
        settings.debug = True
        h = await _token(c, holder)

        settings.allowed_discord_ids = ["someone-else"]
        assert (await c.get("/auth/me", headers=h)).status_code == 403

        settings.allowed_discord_ids = ["someone-else", holder]
        assert (await c.get("/auth/me", headers=h)).status_code == 200


async def test_an_unset_allowlist_leaves_localhost_exactly_as_it_was():
    """The regression guard for the other 263 tests: with the shipped local
    config (`DEBUG=true`, no allowlist) an arbitrary debug user still works."""
    settings.allowed_discord_ids = []
    settings.debug = True
    async with await _client() as c:
        h = await _token(c, f"{_PREFIX}localhost")
        r = await c.get("/auth/me", headers=h)
    assert r.status_code == 200, r.text
