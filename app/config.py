from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LICHAT_", extra="ignore")

    app_name: str = "Li&Chat"
    env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./data/lichat.db"

    oidc_issuer: str = "https://account.lizf.cn"
    oidc_discovery_url: str | None = None
    oidc_client_id: str = "li-chat-local"
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str = "http://localhost:8000/oidc/callback"
    oidc_post_logout_redirect_uri: str = "http://localhost:8000/"
    oidc_scope: str = "openid profile"

    session_secret: str = "dev-only-change-me"
    session_sliding_ttl: int = 7200
    session_absolute_ttl: int = 604800
    session_cookie_name: str = "lichat_session"

    logout_token_max_skew: int = 120
    discovery_cache_ttl: int = 300

    @property
    def discovery_url(self) -> str:
        return self.oidc_discovery_url or f"{self.oidc_issuer}/.well-known/openid-configuration"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"
