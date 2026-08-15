from __future__ import annotations

import time
from typing import Any

import httpx
import jwt as pyjwt
from jwt import PyJWKSet
from jwt.exceptions import InvalidTokenError

from app.logging import get_logger

logger = get_logger(__name__)

_BACKCHANNEL_LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"


class TokenValidationError(RuntimeError):
    pass


class TokenVerifier:
    """按 kid 从 JWKS 选钥校验令牌；密钥轮换期间自动刷新一次。"""

    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        jwks_uri: str,
        transport: httpx.AsyncBaseTransport | None = None,
        cache_ttl: int = 300,
    ) -> None:
        self._issuer = issuer
        self._client_id = client_id
        self._jwks_uri = jwks_uri
        self._transport = transport
        self._cache_ttl = cache_ttl
        self._key_set: PyJWKSet | None = None
        self._fetched_at = 0.0

    async def validate_id_token(self, token: str, nonce: str) -> dict[str, Any]:
        claims = await self._decode(token, audience=self._client_id)
        if claims.get("nonce") != nonce:
            raise TokenValidationError("nonce mismatch")
        return claims

    async def validate_logout_token(self, token: str, *, max_skew: int) -> dict[str, Any]:
        claims = await self._decode(token, audience=self._client_id)
        iat = claims.get("iat")
        now = int(time.time())
        if not isinstance(iat, int) or now - iat > max_skew:
            raise TokenValidationError("stale logout token")
        events = claims.get("events")
        if not isinstance(events, dict) or _BACKCHANNEL_LOGOUT_EVENT not in events:
            raise TokenValidationError("missing backchannel logout event")
        return claims

    async def _decode(self, token: str, *, audience: str) -> dict[str, Any]:
        try:
            header = pyjwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise TokenValidationError(f"malformed token: {exc}") from exc
        if header.get("alg") != "RS256":
            raise TokenValidationError(f"unsupported algorithm: {header.get('alg')}")
        kid = header.get("kid")
        if not isinstance(kid, str):
            raise TokenValidationError("missing kid header")
        key_set = await self._get_key_set()
        try:
            key = key_set[kid]
        except KeyError:
            logger.info("jwks_kid_miss_refetch", kid=kid)
            key_set = await self._get_key_set(refresh=True)
            try:
                key = key_set[kid]
            except KeyError as exc:
                raise TokenValidationError(f"unknown kid: {kid}") from exc
        try:
            claims = pyjwt.decode(
                token,
                key=key.key,
                algorithms=["RS256"],
                audience=audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "aud"]},
            )
        except InvalidTokenError as exc:
            raise TokenValidationError(f"invalid token: {exc}") from exc
        return claims

    async def _get_key_set(self, *, refresh: bool = False) -> PyJWKSet:
        now = time.monotonic()
        if (
            not refresh
            and self._key_set is not None
            and now - self._fetched_at < self._cache_ttl
        ):
            return self._key_set
        async with httpx.AsyncClient(transport=self._transport, timeout=10) as client:
            response = await client.get(self._jwks_uri)
            response.raise_for_status()
            key_set = PyJWKSet.from_dict(response.json())
        self._key_set = key_set
        self._fetched_at = now
        return key_set
