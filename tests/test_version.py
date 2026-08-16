from __future__ import annotations

import httpx

from app.main import FRONTEND_VERSION


async def test_api_version_exposes_frontend_version(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/api/version")
    assert response.status_code == 200
    assert response.json() == {"frontend_version": FRONTEND_VERSION}
    assert response.headers.get("cache-control") == "no-store"
