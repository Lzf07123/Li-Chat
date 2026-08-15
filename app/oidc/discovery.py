from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.logging import get_logger

logger = get_logger(__name__)

_REQUIRED_FIELDS = (
    "issuer",
    "authorization_endpoint",
    "token_endpoint",
    "userinfo_endpoint",
    "jwks_uri",
    "end_session_endpoint",
)


class DiscoveryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OIDCMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    end_session_endpoint: str
    scopes_supported: tuple[str, ...]
    backchannel_logout_supported: bool


class DiscoveryStore:
    def __init__(
        self,
        discovery_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        ttl: int = 300,
    ) -> None:
        self._url = discovery_url
        self._transport = transport
        self._ttl = ttl
        self._cached: tuple[float, OIDCMetadata] | None = None

    async def get(self) -> OIDCMetadata:
        now = time.monotonic()
        if self._cached is not None and now - self._cached[0] < self._ttl:
            return self._cached[1]
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=10) as client:
                response = await client.get(self._url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("oidc_discovery_failed", url=self._url, error=str(exc))
            raise DiscoveryError(f"discovery fetch failed: {exc}") from exc
        metadata = self._parse(data)
        self._cached = (now, metadata)
        return metadata

    @classmethod
    def _parse(cls, data: dict[str, Any]) -> OIDCMetadata:
        missing = [field for field in _REQUIRED_FIELDS if field not in data]
        if missing:
            raise DiscoveryError(f"missing required fields: {missing}")
        return cls.build_metadata(data)

    @staticmethod
    def build_metadata(data: dict[str, Any]) -> OIDCMetadata:
        return OIDCMetadata(
            issuer=data["issuer"],
            authorization_endpoint=data["authorization_endpoint"],
            token_endpoint=data["token_endpoint"],
            userinfo_endpoint=data["userinfo_endpoint"],
            jwks_uri=data["jwks_uri"],
            end_session_endpoint=data["end_session_endpoint"],
            scopes_supported=tuple(data.get("scopes_supported", [])),
            backchannel_logout_supported=bool(data.get("backchannel_logout_supported", False)),
        )
