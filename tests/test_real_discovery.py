import json
from pathlib import Path

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
