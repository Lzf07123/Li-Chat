import pytest
from pydantic import ValidationError

from app.config import Settings


def test_defaults_and_derived_discovery_url() -> None:
    settings = Settings(_env_file=None)
    assert settings.oidc_issuer == "https://account.lizf.cn"
    assert settings.discovery_url == "https://account.lizf.cn/.well-known/openid-configuration"
    assert settings.oidc_scope == "openid profile email"
    assert settings.session_sliding_ttl == 7200
    assert settings.session_absolute_ttl == 604800
    assert settings.is_prod is False


def test_env_override_and_explicit_discovery_url() -> None:
    settings = Settings(
        _env_file=None,
        env="prod",
        oidc_issuer="https://x.example",
        oidc_discovery_url="https://meta.example/discovery",
        session_secret="x" * 40,
    )
    assert settings.discovery_url == "https://meta.example/discovery"
    assert settings.is_prod is True


def test_prod_requires_strong_session_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="prod", session_secret="short")


def test_redis_url_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LICHAT_REDIS_URL", "redis://redis:6379/0")
    settings = Settings(_env_file=None)
    assert settings.redis_url == "redis://redis:6379/0"


def test_redis_url_defaults_to_none() -> None:
    settings = Settings(_env_file=None, session_secret="x" * 32)
    assert settings.redis_url is None


def test_rtc_ice_servers_parsed_from_json() -> None:
    settings = Settings(
        _env_file=None,
        rtc_ice_servers='[{"urls": "stun:stun.example.com:3478"}, '
        '{"urls": ["turn:turn.example.com:3478", "turns:turn.example.com:5349"], '
        '"username": "u", "credential": "p"}]',
    )
    assert settings.rtc_ice_servers == [
        {"urls": "stun:stun.example.com:3478"},
        {
            "urls": ["turn:turn.example.com:3478", "turns:turn.example.com:5349"],
            "username": "u",
            "credential": "p",
        },
    ]


def test_rtc_ice_servers_defaults_to_empty() -> None:
    settings = Settings(_env_file=None)
    assert settings.rtc_ice_servers == []


def test_rtc_ice_servers_rejects_invalid_scheme() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, rtc_ice_servers='[{"urls": "http://evil.example"}]'
        )


def test_rtc_ice_servers_rejects_bad_json() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rtc_ice_servers="not-json")


def test_rtc_ice_servers_rejects_too_many() -> None:
    many = [{"urls": f"stun:server-{i}.example.com"} for i in range(9)]
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rtc_ice_servers=many)
