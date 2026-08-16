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


async def test_v24_image_viewer(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "function openImageViewer(" in text
    assert "image-viewer" in text
    assert "attachment-image" in text
    assert '"Escape"' in text
    css = await _style_css(api_client)
    assert ".image-viewer" in css
    assert ".image-viewer-img" in css


async def test_v25_paste_drop_and_multi_upload(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "function sendFiles(" in text
    assert '"paste"' in text
    assert '"dragover"' in text
    assert '"drop"' in text
    assert "dataTransfer" in text
    assert "multiple" in text


async def test_v26_upload_progress(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "XMLHttpRequest" in text
    assert "xhr.upload" in text
    assert '"progress"' in text
    assert "upload-progress" in text
    assert "uploadCancel" in text
    css = await _style_css(api_client)
    assert ".upload-progress" in css
    assert ".upload-progress-fill" in css


async def test_v27_search_hit_locate_and_highlight(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "function locateMessage(" in text
    assert "function scrollToMessage(" in text
    assert "data-message-id" in text
    assert "scrollIntoView" in text
    assert "data-message=" in text
    css = await _style_css(api_client)
    assert ".message-flash" in css


async def test_v28_conversation_filter_and_skeleton(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "conv-filter" in text
    assert "convFilter" in text
    assert "skeleton" in text
    assert "sidebarLoading" in text
    css = await _style_css(api_client)
    assert ".skeleton" in css
    assert "shimmer" in css


async def test_v29_title_badge_and_desktop_notifications(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "function updateTitleBadge(" in text
    assert "document.title" in text
    assert "Notification" in text
    assert "lichat-desktop-notify" in text
    assert "open-notify-settings" in text


async def test_v30_keyboard_shortcuts_and_help(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "function onGlobalKeydown(" in text
    assert "function openShortcutsModal(" in text
    assert "event.metaKey" in text
    assert "event.ctrlKey" in text
    assert '"?"' in text
    assert "open-shortcuts" in text


async def test_v31_friend_remark(api_client: httpx.AsyncClient) -> None:
    text = await _app_js(api_client)
    assert "function openRemarkModal(" in text
    assert "friend-remark" in text
    assert "/remark" in text
    assert "user.remark" in text
