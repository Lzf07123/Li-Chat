"""本地 OIDC IdP 模拟器，仅用于测试，不访问任何真实网络。"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any

import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse


class MockIdP:
    """实现发现文档、授权、令牌、userinfo、JWKS 与 end-session 的最小 IdP。"""

    ISSUER = "http://mock-idp.test"

    def __init__(
        self,
        *,
        client_id: str = "test-client",
        client_secret: str | None = "test-secret",
        user: dict[str, Any] | None = None,
        sid: str = "sid-1",
        acr: str = "urn:lipass:acr:2fa",
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.user = user or {
            "sub": "u-1001",
            "nickname": "Alice",
            "name": "Alice Zhang",
            "picture": "https://mock-idp.test/a.jpg",
            "email": "alice@example.com",
            "email_verified": True,
        }
        self.sid = sid
        self.acr = acr
        self.kid = "mock-rs256-1"
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._public_key = self._private_key.public_key()
        self._codes: dict[str, dict[str, str]] = {}
        self._access_tokens: dict[str, str] = {}
        self.app = self._build_app()

    def _discovery(self) -> dict[str, Any]:
        base = self.ISSUER
        return {
            "issuer": base,
            "authorization_endpoint": f"{base}/oauth2/authorize",
            "token_endpoint": f"{base}/oauth2/token",
            "userinfo_endpoint": f"{base}/oauth2/userinfo",
            "jwks_uri": f"{base}/oauth2/jwks",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "profile", "email"],
            "code_challenge_methods_supported": ["S256"],
            "end_session_endpoint": f"{base}/oauth2/end-session",
            "backchannel_logout_supported": True,
            "frontchannel_logout_supported": False,
        }

    def sign_id_token(self, claims: dict[str, Any]) -> str:
        claims = {
            "iss": self.ISSUER,
            "aud": self.client_id,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            **claims,
        }
        private_pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        return pyjwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": self.kid})

    def sign_logout_token(self, claims: dict[str, Any]) -> str:
        return self.sign_id_token(claims)

    def _jwks(self) -> dict[str, Any]:
        public_pem = self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        jwk = pyjwt.algorithms.RSAAlgorithm.to_jwk(public_pem)
        jwk["kid"] = self.kid
        jwk["use"] = "sig"
        jwk["alg"] = "RS256"
        return {"keys": [jwk]}

    @staticmethod
    def _pkce_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/.well-known/openid-configuration")
        async def discovery() -> JSONResponse:
            return JSONResponse(self._discovery())

        @app.get("/oauth2/authorize")
        async def authorize(request: Request):
            params = request.query_params
            redirect_uri = params.get("redirect_uri", "")
            error_redirect = self._error_redirect(
                redirect_uri, "invalid_request", params.get("state")
            )
            required = (
                "response_type",
                "client_id",
                "redirect_uri",
                "scope",
                "state",
                "nonce",
                "code_challenge",
                "code_challenge_method",
            )
            if any(params.get(k) is None for k in required):
                return error_redirect
            if params["response_type"] != "code" or params["client_id"] != self.client_id:
                return error_redirect
            if "openid" not in params["scope"].split() or params["code_challenge_method"] != "S256":
                return error_redirect
            code = secrets.token_urlsafe(32)
            self._codes[code] = {
                "challenge": params["code_challenge"],
                "nonce": params["nonce"],
                "redirect_uri": params["redirect_uri"],
            }
            location = f"{redirect_uri}?code={code}&state={params['state']}"
            return RedirectResponse(location, status_code=302)

        @app.post("/oauth2/token")
        async def token(request: Request):
            form = await request.form()
            if form.get("client_secret") and form.get("client_secret") != self.client_secret:
                return JSONResponse({"error": "invalid_client"}, status_code=401)
            code = form.get("code")
            record = self._codes.pop(str(code), None) if code else None
            if not record or form.get("grant_type") != "authorization_code":
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            verifier = str(form.get("code_verifier", ""))
            if self._pkce_challenge(verifier) != record["challenge"]:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            if form.get("redirect_uri") != record["redirect_uri"]:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            access_token = secrets.token_urlsafe(32)
            self._access_tokens[access_token] = self.user["sub"]
            id_token = self.sign_id_token(
                {
                    "sub": self.user["sub"],
                    "nonce": record["nonce"],
                    "sid": self.sid,
                    "acr": self.acr,
                    "jti": secrets.token_urlsafe(16),
                }
            )
            return JSONResponse(
                {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": 900,
                    "id_token": id_token,
                }
            )

        @app.get("/oauth2/userinfo")
        async def userinfo(request: Request):
            auth = request.headers.get("authorization", "")
            token = auth.removeprefix("Bearer ").strip()
            if token not in self._access_tokens:
                return JSONResponse({"error": "invalid_token"}, status_code=401)
            return JSONResponse(self.user)

        @app.get("/oauth2/jwks")
        async def jwks() -> JSONResponse:
            return JSONResponse(self._jwks())

        @app.get("/oauth2/end-session")
        async def end_session(request: Request):
            redirect_uri = request.query_params.get("post_logout_redirect_uri", "")
            state = request.query_params.get("state", "")
            return RedirectResponse(f"{redirect_uri}?state={state}", status_code=302)

        return app

    @staticmethod
    def _error_redirect(redirect_uri: str, error: str, state: str | None) -> RedirectResponse:
        location = f"{redirect_uri}?error={error}"
        if state:
            location += f"&state={state}"
        return RedirectResponse(location, status_code=302)
