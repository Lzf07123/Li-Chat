from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.config import Settings
from app.oidc.discovery import DiscoveryStore
from app.oidc.provider import OIDCProvider, TokenExchangeError
from app.oidc.tokens import TokenValidationError, TokenVerifier
from tests.fixtures.mock_idp import MockIdP


def _pkce_challenge(verifier: str) -> str:
    import base64
    import hashlib

    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )


async def _provider(
    settings: Settings, mock_idp: MockIdP, mock_transport: httpx.ASGITransport
) -> OIDCProvider:
    discovery = DiscoveryStore(settings.discovery_url, transport=mock_transport)
    return OIDCProvider(settings, discovery, transport=mock_transport)


async def test_build_authorize_url_has_required_params(
    settings: Settings, mock_idp: MockIdP, mock_transport: httpx.ASGITransport
) -> None:
    provider = await _provider(settings, mock_idp, mock_transport)
    url = await provider.build_authorize_url("state-1", "nonce-1", "challenge-1")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.path == "/oauth2/authorize"
    assert query["response_type"] == ["code"]
    assert query["client_id"] == [settings.oidc_client_id]
    assert query["scope"] == ["openid profile email"]
    assert query["state"] == ["state-1"]
    assert query["nonce"] == ["nonce-1"]
    assert query["code_challenge"] == ["challenge-1"]
    assert query["code_challenge_method"] == ["S256"]


async def test_exchange_code_and_fetch_userinfo(
    settings: Settings, mock_idp: MockIdP, mock_transport: httpx.ASGITransport
) -> None:
    provider = await _provider(settings, mock_idp, mock_transport)
    verifier = "v" * 60
    code = mock_idp.issue_code(
        challenge=_pkce_challenge(verifier),
        nonce="nonce-1",
        redirect_uri=settings.oidc_redirect_uri,
    )
    tokens = await provider.exchange_code(code, verifier)
    assert tokens["token_type"] == "Bearer"
    user = await provider.fetch_userinfo(tokens["access_token"])
    assert user["sub"] == "u-1001"
    assert user["nickname"] == "Alice"


async def test_exchange_code_with_wrong_verifier_raises(
    settings: Settings, mock_idp: MockIdP, mock_transport: httpx.ASGITransport
) -> None:
    provider = await _provider(settings, mock_idp, mock_transport)
    code = mock_idp.issue_code(
        challenge=_pkce_challenge("right-verifier"),
        nonce="n",
        redirect_uri=settings.oidc_redirect_uri,
    )
    with pytest.raises(TokenExchangeError) as exc_info:
        await provider.exchange_code(code, "wrong-verifier")
    assert exc_info.value.error_code == "invalid_grant"


async def test_id_token_validation(
    settings: Settings, mock_idp: MockIdP, mock_transport: httpx.ASGITransport
) -> None:
    verifier = TokenVerifier(
        issuer=mock_idp.ISSUER,
        client_id=settings.oidc_client_id,
        jwks_uri=f"{mock_idp.ISSUER}/oauth2/jwks",
        transport=mock_transport,
    )
    token = mock_idp.sign_id_token({"sub": "u-1001", "nonce": "nonce-1"})
    claims = await verifier.validate_id_token(token, "nonce-1")
    assert claims["sub"] == "u-1001"


async def test_id_token_wrong_nonce_rejected(
    settings: Settings, mock_idp: MockIdP, mock_transport: httpx.ASGITransport
) -> None:
    verifier = TokenVerifier(
        issuer=mock_idp.ISSUER,
        client_id=settings.oidc_client_id,
        jwks_uri=f"{mock_idp.ISSUER}/oauth2/jwks",
        transport=mock_transport,
    )
    token = mock_idp.sign_id_token({"sub": "u-1001", "nonce": "nonce-1"})
    with pytest.raises(TokenValidationError, match="nonce"):
        await verifier.validate_id_token(token, "other-nonce")


async def test_id_token_wrong_audience_rejected(
    settings: Settings, mock_idp: MockIdP, mock_transport: httpx.ASGITransport
) -> None:
    verifier = TokenVerifier(
        issuer=mock_idp.ISSUER,
        client_id=settings.oidc_client_id,
        jwks_uri=f"{mock_idp.ISSUER}/oauth2/jwks",
        transport=mock_transport,
    )
    token = mock_idp.sign_id_token({"sub": "u-1001", "nonce": "n", "aud": "other-client"})
    with pytest.raises(TokenValidationError, match="invalid token"):
        await verifier.validate_id_token(token, "n")
