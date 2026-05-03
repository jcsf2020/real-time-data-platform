from fastapi.testclient import TestClient
from rtdp_api import app


def test_minute_aggregates_endpoint_returns_silver_rows(monkeypatch) -> None:
    def fake_fetch_all(query: str, params: tuple = ()) -> list[dict]:
        assert "FROM silver.market_event_minute_aggregates" in query
        assert params == (3,)
        return [
            {
                "symbol": "BTCUSDT",
                "window_start": "2026-05-03T16:46:00Z",
                "event_count": 7,
                "avg_price": 66388.04857143,
                "total_quantity": 11.159923,
                "first_event_timestamp": "2026-05-03T16:46:01Z",
                "last_event_timestamp": "2026-05-03T16:46:59Z",
                "updated_at": "2026-05-03T16:47:00Z",
            }
        ]

    monkeypatch.setattr("rtdp_api.fetch_all", fake_fetch_all)

    client = TestClient(app)
    response = client.get("/aggregates/minute?limit=3")

    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "BTCUSDT"
    assert response.json()[0]["event_count"] == 7
    assert response.json()[0]["avg_price"] == 66388.04857143
