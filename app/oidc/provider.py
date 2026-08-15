from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.logging import get_logger
from app.oidc.discovery import DiscoveryStore, OIDCMetadata

logger = get_logger(__name__)


class TokenExchangeError(RuntimeError):
    def __init__(self, error_code: str, description: str | None = None) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.description = description


class OIDCProvider:
    """Li&Pass 授权码 + PKCE 依赖方客户端。"""

    def __init__(
        self,
        settings: Settings,
        discovery: DiscoveryStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._discovery = discovery
        self._transport = transport

    async def discovery_metadata(self) -> OIDCMetadata:
        return await self._discovery.get()

    async def build_authorize_url(self, state: str, nonce: str, challenge: str) -> str:
        metadata = await self._discovery.get()
        params = {
            "response_type": "code",
            "client_id": self._settings.oidc_client_id,
            "redirect_uri": self._settings.oidc_redirect_uri,
            "scope": self._settings.oidc_scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{metadata.authorization_endpoint}?{urlencode(params)}"

    async def exchange_code(self, code: str, verifier: str) -> dict[str, Any]:
        metadata = await self._discovery.get()
        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._settings.oidc_redirect_uri,
            "client_id": self._settings.oidc_client_id,
            "code_verifier": verifier,
        }
        if self._settings.oidc_client_secret:
            data["client_secret"] = self._settings.oidc_client_secret
        async with httpx.AsyncClient(transport=self._transport, timeout=10) as client:
            response = await client.post(metadata.token_endpoint, data=data)
        if response.status_code >= 400:
            payload = self._safe_json(response)
            error_code = str(payload.get("error") or "")
            if not error_code:
                error_code = (
                    "account_blocked"
                    if response.status_code == 403
                    else "token_exchange_failed"
                )
            raise TokenExchangeError(
                error_code,
                str(payload.get("error_description") or payload.get("detail") or ""),
            )
        return self._safe_json(response)

    async def fetch_userinfo(self, access_token: str) -> dict[str, Any]:
        metadata = await self._discovery.get()
        async with httpx.AsyncClient(transport=self._transport, timeout=10) as client:
            response = await client.get(
                metadata.userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            return cast(dict[str, Any], response.json())
        except ValueError:
            return {}
