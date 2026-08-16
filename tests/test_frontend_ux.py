"""阶段一（v21–v30）前端体验优化的内容契约测试。"""

from __future__ import annotations

import httpx


async def _app_js(api_client: httpx.AsyncClient) -> str:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    return response.text


async def _style_css(api_client: httpx.AsyncClient) -> str:
    response = await api_client.get("/style.css")
    assert response.status_code == 200
    return response.text


async def test_v21_toast_system_present(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "function toast(" in text
    assert 'aria-live="polite"' in text
    assert '"toast-close"' in text
    assert "friendlyError" in text
    assert "window.alert" not in text


async def test_v21_toast_styles_present(api_client: httpx.AsyncClient) -> None:
    text = await _style_css(api_client)
    assert ".toast-region" in text
    assert ".toast-error" in text
    assert ".toast-success" in text


async def test_v22_websocket_auto_reconnect(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "function scheduleReconnect(" in text
    assert "state.wsReconnectTimer" in text
    assert "state.wsRetry" in text
    assert "Math.min(30000" in text
    assert '"visibilitychange"' in text
    assert "已重新连接" in text
    assert "state.loggingOut" in text


async def test_v23_day_grouping_and_merged_messages(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "function dayLabel(" in text
    assert "message-day" in text
    assert "message-merged" in text
    assert "message-sender" in text
    assert '"今天"' in text
    css = await _style_css(api_client)
    assert ".message-day" in css
    assert ".message-merged" in css
    assert ".message-sender" in css
