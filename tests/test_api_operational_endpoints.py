from fastapi.testclient import TestClient
from rtdp_api import app


def test_health_endpoint_reports_service_alive() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "rtdp-api",
    }


def test_version_endpoint_reports_runtime_metadata() -> None:
    client = TestClient(app)

    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "service": "rtdp-api",
        "version": "0.1.0",
        "environment": "local",
    }


def test_readiness_endpoint_reports_database_ready(monkeypatch) -> None:
    def fake_fetch_all(query: str, params: tuple = ()) -> list[dict]:
        assert query == "SELECT 1 AS ok"
        assert params == ()
        return [{"ok": 1}]

    monkeypatch.setattr("rtdp_api.fetch_all", fake_fetch_all)

    client = TestClient(app)

    response = client.get("/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "rtdp-api",
        "database": "reachable",
    }
