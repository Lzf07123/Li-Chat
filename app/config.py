from __future__ import annotations

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LICHAT_", extra="ignore")

    app_name: str = "Li&Chat"
    env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./data/lichat.db"
    redis_url: str | None = None

    oidc_issuer: str = "https://account.lizf.cn"
    oidc_discovery_url: str | None = None
    oidc_client_id: str = "li-chat-local"
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str = "http://localhost:8000/oidc/callback"
    oidc_post_logout_redirect_uri: str = "http://localhost:8000/"
    oidc_scope: str = "openid profile email"

    session_secret: str = "dev-only-change-me"
    session_sliding_ttl: int = 7200
    session_absolute_ttl: int = 604800
    session_cookie_name: str = "lichat_session"

    logout_token_max_skew: int = 120
    discovery_cache_ttl: int = 300
    upload_max_mb: int = 10
    upload_dir: str = "./data/uploads"
    login_rate_limit: int = 10
    login_rate_window: int = 60

    @property
    def discovery_url(self) -> str:
        return self.oidc_discovery_url or f"{self.oidc_issuer}/.well-known/openid-configuration"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @field_validator("session_secret")
    @classmethod
    def _validate_session_secret(cls, value: str, info: ValidationInfo) -> str:
        if info.data.get("env") == "prod" and len(value) < 32:
            raise ValueError("session_secret must be at least 32 characters in prod")
        return value

    @field_validator("upload_max_mb")
    @classmethod
    def _validate_upload_max(cls, value: int) -> int:
        if not 1 <= value <= 20:
            raise ValueError("upload_max_mb must be between 1 and 20")
        return value

    @field_validator("login_rate_limit")
    @classmethod
    def _validate_login_rate_limit(cls, value: int) -> int:
        if not 1 <= value <= 1000:
            raise ValueError("login_rate_limit must be between 1 and 1000")
        return value

    @field_validator("login_rate_window")
    @classmethod
    def _validate_login_rate_window(cls, value: int) -> int:
        if value < 1:
            raise ValueError("login_rate_window must be at least 1 second")
        return value
