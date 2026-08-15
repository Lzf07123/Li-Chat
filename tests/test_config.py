from app.config import Settings


def test_defaults_and_derived_discovery_url() -> None:
    settings = Settings(_env_file=None)
    assert settings.oidc_issuer == "https://account.lizf.cn"
    assert settings.discovery_url == "https://account.lizf.cn/.well-known/openid-configuration"
    assert settings.session_sliding_ttl == 7200
    assert settings.session_absolute_ttl == 604800
    assert settings.is_prod is False


def test_env_override_and_explicit_discovery_url() -> None:
    settings = Settings(
        _env_file=None,
        env="prod",
        oidc_issuer="https://x.example",
        oidc_discovery_url="https://meta.example/discovery",
    )
    assert settings.discovery_url == "https://meta.example/discovery"
    assert settings.is_prod is True
