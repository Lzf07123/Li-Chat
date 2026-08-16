from __future__ import annotations

import secrets
from typing import Annotated, cast
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_csrf
from app.auth.session import (
    clear_session_cookie,
    create_session,
    delete_all_sessions_for,
    delete_session,
    delete_sessions_for,
    set_session_cookie,
)
from app.config import Settings
from app.db import get_db
from app.logging import get_logger
from app.models import AuthState, Session
from app.oidc.discovery import DiscoveryStore, OIDCMetadata
from app.oidc.pkce import challenge_for_verifier, generate_pkce_pair
from app.oidc.provider import OIDCProvider, TokenExchangeError
from app.oidc.state import create_auth_state, pop_auth_state
from app.oidc.tokens import TokenValidationError, TokenVerifier
from app.oidc.user_sync import upsert_user
from app.redis import publish_logout
from app.sso.ratelimit import SlidingWindowRateLimiter
from app.sso.replay import ReplayCache
from app.sso.signing import sign_state, verify_state
from app.timeutil import utcnow
from app.ws.manager import ConnectionManager

router = APIRouter(prefix="/oidc", tags=["sso"])
logger = get_logger(__name__)


def _check_login_rate(request: Request) -> None:
    limiter = cast(SlidingWindowRateLimiter, request.app.state.login_limiter)
    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = limiter.check(f"auth:{ip}")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="too many login attempts",
            headers={"Retry-After": str(retry_after)},
        )

_AUTH_STATE_COOKIE = "lichat_auth"

def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _transport(request: Request) -> httpx.AsyncBaseTransport | None:
    return cast(httpx.AsyncBaseTransport | None, request.app.state.http_transport)


def _provider(request: Request) -> OIDCProvider:
    discovery = cast(DiscoveryStore, request.app.state.discovery)
    return OIDCProvider(_settings(request), discovery, transport=_transport(request))


def _token_verifier(request: Request, metadata: OIDCMetadata) -> TokenVerifier:
    return TokenVerifier(
        issuer=metadata.issuer,
        client_id=_settings(request).oidc_client_id,
        jwks_uri=metadata.jwks_uri,
        transport=_transport(request),
    )


def _safe_redirect_after(redirect_after: str) -> str:
    if not redirect_after.startswith("/") or redirect_after.startswith("//"):
        return "/"
    return redirect_after


def _error_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(f"/oidc/error?message={quote(message)}", status_code=302)


@router.get("/login")
async def login(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redirect_after: str = "/",
) -> RedirectResponse:
    _check_login_rate(request)
    settings = _settings(request)
    existing_state = request.cookies.get(_AUTH_STATE_COOKIE)
    if existing_state:
        pending = await db.get(AuthState, existing_state)
        if pending is not None and pending.expires_at >= utcnow():
            challenge = challenge_for_verifier(pending.verifier)
            url = await _provider(request).build_authorize_url(
                pending.state, pending.nonce, challenge
            )
            return RedirectResponse(url, status_code=302)
    verifier, challenge = generate_pkce_pair()
    nonce = secrets.token_urlsafe(32)
    safe_redirect = _safe_redirect_after(redirect_after)
    state = await create_auth_state(
        db, verifier=verifier, nonce=nonce, redirect_after=safe_redirect
    )
    url = await _provider(request).build_authorize_url(state, nonce, challenge)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        _AUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.is_prod,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    _check_login_rate(request)
    if error is not None:
        message = (
            "该账号已被此网站限制访问"
            if error_description == "account_blocked"
            else "登录未完成"
        )
        return _error_redirect(message)
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code or state")
    auth_state = await pop_auth_state(db, state)
    if auth_state is None:
        raise HTTPException(status_code=400, detail="invalid or reused state")

    provider = _provider(request)
    try:
        tokens = await provider.exchange_code(code, auth_state.verifier)
    except TokenExchangeError as exc:
        logger.warning("token_exchange_failed", error_code=exc.error_code)
        message = (
            "该账号已被此网站限制访问"
            if exc.error_code in ("account_blocked", "access_denied")
            else "登录凭证已失效，请重新登录"
        )
        return _error_redirect(message)

    id_token = tokens.get("id_token")
    access_token = tokens.get("access_token")
    if not isinstance(id_token, str) or not isinstance(access_token, str):
        raise HTTPException(status_code=502, detail="idp response missing tokens")

    metadata = await provider.discovery_metadata()
    try:
        claims = await _token_verifier(request, metadata).validate_id_token(
            id_token, auth_state.nonce, access_token
        )
    except TokenValidationError as exc:
        logger.warning("id_token_validation_failed", error=str(exc))
        raise HTTPException(status_code=401, detail="id_token validation failed") from exc

    try:
        userinfo = await provider.fetch_userinfo(access_token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 403:
            return _error_redirect("该账号已被此网站限制访问")
        raise HTTPException(status_code=502, detail="userinfo request failed") from exc

    if userinfo.get("sub") != claims.get("sub"):
        logger.warning("userinfo_sub_mismatch")
        raise HTTPException(status_code=401, detail="user identity mismatch")

    user = await upsert_user(db, userinfo)
    settings = _settings(request)
    session = await create_session(
        db,
        user.sub,
        sid=str(claims["sid"]) if claims.get("sid") else None,
        acr=str(claims["acr"]) if claims.get("acr") else None,
        id_token=id_token,
        sliding_ttl=settings.session_sliding_ttl,
        absolute_ttl=settings.session_absolute_ttl,
    )
    response = RedirectResponse(auth_state.redirect_after, status_code=302)
    response.delete_cookie(_AUTH_STATE_COOKIE, path="/")
    set_session_cookie(
        response,
        session.id,
        cookie_name=settings.session_cookie_name,
        max_age=settings.session_absolute_ttl,
        secure=settings.is_prod,
    )
    return response


@router.get("/error")
async def error(message: str = "登录未完成") -> JSONResponse:
    return JSONResponse({"message": message})


async def _clear_local_session(request: Request, db: AsyncSession) -> str | None:
    """删除当前会话并断该用户 WS（Redis 时跨副本广播）；返回 id_token_hint（如有）。"""
    settings = _settings(request)
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None
    session = await db.get(Session, session_id)
    if session is None:
        return None
    id_token_hint = session.id_token
    await delete_session(db, session_id)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    await manager.disconnect_sub(session.user_sub)
    redis = cast(Redis | None, request.app.state.redis)
    if redis is not None:
        await publish_logout(redis, session.user_sub)
    return id_token_hint


@router.post("/logout")
async def logout(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> RedirectResponse:
    settings = _settings(request)
    id_token_hint = await _clear_local_session(request, db)
    metadata = await _provider(request).discovery_metadata()
    signed = sign_state(settings.session_secret, secrets.token_urlsafe(24))
    logout_params = {
        "client_id": settings.oidc_client_id,
        "post_logout_redirect_uri": settings.oidc_post_logout_redirect_uri,
        "state": signed,
    }
    if id_token_hint is not None:
        logout_params = {"id_token_hint": id_token_hint, **logout_params}
    logger.info(
        "rp_logout",
        client_id=settings.oidc_client_id,
        post_logout_redirect_uri=settings.oidc_post_logout_redirect_uri,
        has_id_token_hint=id_token_hint is not None,
    )
    params = urlencode(logout_params)
    response = RedirectResponse(
        f"{metadata.end_session_endpoint}?{params}", status_code=302
    )
    clear_session_cookie(response, cookie_name=settings.session_cookie_name)
    return response


@router.post("/logout-local")
async def logout_local(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> RedirectResponse:
    """仅登出本网站：清本地会话，不发起 SSO 联邦登出。"""
    await _clear_local_session(request, db)
    response = RedirectResponse("/", status_code=302)
    clear_session_cookie(response, cookie_name=_settings(request).session_cookie_name)
    return response


def _finish_post_logout(request: Request, state: str | None) -> RedirectResponse:
    if not state or verify_state(_settings(request).session_secret, state) is None:
        raise HTTPException(status_code=400, detail="invalid logout state")
    return RedirectResponse("/", status_code=302)


@router.get("/post-logout")
async def post_logout(request: Request, state: str | None = None) -> RedirectResponse:
    return _finish_post_logout(request, state)


async def _process_logout_token(
    request: Request, db: AsyncSession, logout_token: str
) -> JSONResponse:
    settings = _settings(request)
    discovery = cast(DiscoveryStore, request.app.state.discovery)
    metadata = await discovery.get()
    try:
        claims = await _token_verifier(request, metadata).validate_logout_token(
            logout_token, max_skew=settings.logout_token_max_skew
        )
    except TokenValidationError as exc:
        logger.warning("logout_token_invalid", error=str(exc))
        raise HTTPException(status_code=400, detail="invalid logout_token") from exc

    jti = claims.get("jti")
    sub = claims.get("sub")
    sid = claims.get("sid")
    if not isinstance(jti, str) or not isinstance(sub, str):
        raise HTTPException(status_code=400, detail="logout token missing claims")

    cache = cast(ReplayCache, request.app.state.replay_cache)
    if await cache.check_and_add(jti):
        return JSONResponse({"status": "ignored"})

    if isinstance(sid, str):
        deleted = await delete_sessions_for(db, sub, sid)
        if deleted == 0:
            deleted = await delete_all_sessions_for(db, sub)
            logger.info(
                "backchannel_logout_sid_miss_fallback",
                sub=sub,
                sid=sid,
                deleted=deleted,
            )
    else:
        deleted = await delete_all_sessions_for(db, sub)
        logger.info("backchannel_logout_sid_missing", sub=sub, deleted=deleted)
    manager = cast(ConnectionManager, request.app.state.ws_manager)
    await manager.disconnect_sub(sub)
    redis = cast(Redis | None, request.app.state.redis)
    if redis is not None:
        await publish_logout(redis, sub)
    return JSONResponse({"status": "ok"})


@router.post("/backchannel-logout")
async def backchannel_logout(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    logout_token: Annotated[str, Form()],
) -> JSONResponse:
    return await _process_logout_token(request, db, logout_token)
