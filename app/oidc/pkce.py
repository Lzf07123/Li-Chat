from __future__ import annotations

import base64
import hashlib
import secrets


def generate_pkce_pair() -> tuple[str, str]:
    """生成 PKCE S256 的 (code_verifier, code_challenge)。"""
    verifier = secrets.token_urlsafe(48)
    return verifier, challenge_for_verifier(verifier)


def challenge_for_verifier(verifier: str) -> str:
    """由 verifier 推导 S256 challenge（复用未完成授权状态时用）。"""
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return challenge
