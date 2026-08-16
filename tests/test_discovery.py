import httpx
import pytest

from app.oidc.discovery import DiscoveryError, DiscoveryStore
from tests.fixtures.mock_idp import MockIdP


async def test_get_returns_metadata(mock_idp: MockIdP, mock_transport: httpx.ASGITransport) -> None:
    store = DiscoveryStore(
        f"{mock_idp.ISSUER}/.well-known/openid-configuration", transport=mock_transport
    )
    meta = await store.get()
    assert meta.issuer == mock_idp.ISSUER
    assert meta.jwks_uri == f"{mock_idp.ISSUER}/oauth2/jwks"
    assert meta.authorization_endpoint == f"{mock_idp.ISSUER}/oauth2/authorize"
    assert "openid" in meta.scopes_supported
    assert meta.backchannel_logout_supported is True
    assert meta.frontchannel_logout_supported is False


async def test_cached_within_ttl(mock_idp: MockIdP, mock_transport: httpx.ASGITransport) -> None:
    store = DiscoveryStore(
        f"{mock_idp.ISSUER}/.well-known/openid-configuration",
        transport=mock_transport,
        ttl=60,
    )
    first = await store.get()
    second = await store.get()
    assert first is second


async def test_cache_expires(mock_idp: MockIdP, mock_transport: httpx.ASGITransport) -> None:
    store = DiscoveryStore(
        f"{mock_idp.ISSUER}/.well-known/openid-configuration", transport=mock_transport, ttl=-1
    )
    first = await store.get()
    second = await store.get()
    assert first is not second
    assert first == second


async def test_missing_required_field_raises() -> None:
    async def bad_app(scope, receive, send) -> None:
        assert scope["type"] == "http"
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"issuer":"http://x"}'})

    store = DiscoveryStore("http://x/discovery", transport=httpx.ASGITransport(app=bad_app))
    with pytest.raises(DiscoveryError, match="missing"):
        await store.get()
