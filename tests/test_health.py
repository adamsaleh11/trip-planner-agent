from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_200_without_auth():
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
