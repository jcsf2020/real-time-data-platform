from fastapi.testclient import TestClient
from rtdp_api import app


def test_daily_aggregates_endpoint_returns_gold_rows(monkeypatch) -> None:
    def fake_fetch_all(query: str, params: tuple = ()) -> list[dict]:
        assert "FROM gold.market_event_daily_aggregates" in query
        assert params == (3,)
        return [
            {
                "symbol": "BTCUSDT",
                "event_date": "2026-05-03",
                "event_count": 42,
                "avg_price": 66388.12345678,
                "min_price": 66100.0,
                "max_price": 66750.0,
                "total_quantity": 123.456789,
                "first_event_timestamp": "2026-05-03T00:00:01Z",
                "last_event_timestamp": "2026-05-03T23:59:59Z",
                "updated_at": "2026-05-04T00:00:00Z",
            }
        ]

    monkeypatch.setattr("rtdp_api.fetch_all", fake_fetch_all)

    client = TestClient(app)
    response = client.get("/aggregates/daily?limit=3")

    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "BTCUSDT"
    assert response.json()[0]["event_count"] == 42
    assert response.json()[0]["avg_price"] == 66388.12345678
    assert response.json()[0]["min_price"] == 66100.0
    assert response.json()[0]["max_price"] == 66750.0
    assert response.json()[0]["total_quantity"] == 123.456789
