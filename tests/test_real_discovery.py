import json
from pathlib import Path

import httpx

from app.oidc.discovery import DiscoveryStore

_DATA = json.loads(
    (Path(__file__).parent / "fixtures" / "real_discovery.json").read_text()
)


def test_real_discovery_document_parses() -> None:
    metadata = DiscoveryStore.build_metadata(_DATA)
    assert metadata.issuer == "http://account.lizf.cn"
    assert metadata.authorization_endpoint == "http://account.lizf.cn/oauth2/authorize"
    assert metadata.token_endpoint == "http://account.lizf.cn/oauth2/token"
    assert metadata.userinfo_endpoint == "http://account.lizf.cn/oauth2/userinfo"
    assert metadata.jwks_uri == "http://account.lizf.cn/oauth2/jwks"
    assert metadata.end_session_endpoint == "http://account.lizf.cn/oauth2/end-session"
    assert "openid" in metadata.scopes_supported
    assert metadata.backchannel_logout_supported is True


async def test_transport_endpoints_upgraded_to_https() -> None:
    async def discovery_app(scope, receive, send) -> None:
        assert scope["type"] == "http"
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": json.dumps(_DATA).encode(),
            }
        )

    store = DiscoveryStore(
        "https://account.lizf.cn/.well-known/openid-configuration",
        transport=httpx.ASGITransport(app=discovery_app),
    )
    metadata = await store.get()
    # iss 校验必须按发现文档原文，不改写
    assert metadata.issuer == "http://account.lizf.cn"
    # 传输端点跟随发现请求的 https 通道
    assert metadata.authorization_endpoint == "https://account.lizf.cn/oauth2/authorize"
    assert metadata.token_endpoint == "https://account.lizf.cn/oauth2/token"
    assert metadata.userinfo_endpoint == "https://account.lizf.cn/oauth2/userinfo"
    assert metadata.jwks_uri == "https://account.lizf.cn/oauth2/jwks"
    assert metadata.end_session_endpoint == "https://account.lizf.cn/oauth2/end-session"
