import httpx


async def test_index_served(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Li&Chat" in response.text


async def test_static_asset_served(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/app.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
