import base64
import hashlib

from app.oidc.pkce import generate_pkce_pair


def test_pair_meets_s256_spec() -> None:
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == expected
