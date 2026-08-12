"""The list-valued settings parse the things a human will actually type (B3).

Why this file exists at all: `CORS_ORIGINS` and `ALLOWED_DISCORD_IDS` are the two
settings a deploy sets BY HAND in the Render dashboard, and both are `list[str]`.
pydantic-settings JSON-decodes such a field inside the settings *source*, before
any validator runs — so a plain origin, a comma-separated pair, or an EMPTY box
each raised at import and produced a process that never served a request. That is
a blank white page and a crash loop, not a helpful error, and `render.yaml`
declares both vars as `sync: false`, which Render presents as an empty field.

So the accepted forms are pinned here rather than trusted to a comment. Each case
below was a MEASURED failure before `_tolerant_list` existed.
"""

import importlib
import sys

import pytest


def _settings_with(monkeypatch, **env):
    """A fresh Settings with these env vars, importing app.config from scratch."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    for mod in [m for m in list(sys.modules) if m.startswith("app.config")]:
        del sys.modules[mod]
    cfg = importlib.import_module("app.config")
    return cfg.Settings()  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "raw,expected",
    [
        # The JSON form the checked-in .env / .env.example already use.
        ('["111","222"]', ["111", "222"]),
        ('["111"]', ["111"]),
        ("[]", []),
        # The form a human types into a dashboard box.
        ("111,222", ["111", "222"]),
        ("111", ["111"]),
        ("111, 222 , 333", ["111", "222", "333"]),
        # Blank means unset, and must NOT be a crash — this is the one that
        # would have hit the very first deploy.
        ("", []),
        ("   ", []),
        # No empty members from sloppy separators.
        ("111,,222,", ["111", "222"]),
    ],
)
def test_allowlist_accepts_every_form_a_human_types(monkeypatch, raw, expected):
    s = _settings_with(monkeypatch, ALLOWED_DISCORD_IDS=raw)
    assert s.allowed_discord_ids == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('["https://x.pages.dev"]', ["https://x.pages.dev"]),
        ("https://x.pages.dev", ["https://x.pages.dev"]),
        (
            "https://x.pages.dev,http://localhost:5173",
            ["https://x.pages.dev", "http://localhost:5173"],
        ),
        ("", []),
    ],
)
def test_cors_origins_shares_the_same_tolerance(monkeypatch, raw, expected):
    """The same validator guards both; a URL with `//` in it must not be mistaken
    for anything clever."""
    s = _settings_with(monkeypatch, CORS_ORIGINS=raw)
    assert s.cors_origins == expected


def test_the_default_is_untouched_when_the_var_is_absent(monkeypatch):
    """Deleting the var must leave the shipped localhost default, not blank it."""
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("ALLOWED_DISCORD_IDS", raising=False)
    s = _settings_with(monkeypatch)
    assert s.cors_origins == ["http://localhost:5173"]
    assert s.allowed_discord_ids == []


def test_malformed_json_fails_loudly_and_says_what_was_wanted(monkeypatch):
    """Tolerance is not silence: a half-typed JSON list is still an error, and the
    message names both accepted forms."""
    with pytest.raises(Exception) as exc:
        _settings_with(monkeypatch, ALLOWED_DISCORD_IDS='["111"')
    assert "comma-separated" in str(exc.value)
