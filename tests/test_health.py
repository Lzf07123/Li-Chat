import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import APP_VERSION, create_app


async def test_healthz(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "version": APP_VERSION,
    }


def test_startup_creates_missing_database_directory(tmp_path) -> None:
    db_dir = tmp_path / "nested" / "data"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{db_dir / 'app.db'}",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
    assert (db_dir / "app.db").exists()
