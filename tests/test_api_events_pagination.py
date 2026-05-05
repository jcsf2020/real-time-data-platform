from fastapi.testclient import TestClient
from rtdp_api import app

# 15 synthetic rows ordered newest-first, used to simulate DB slicing.
_ALL_ROWS = [
    {
        "event_id": f"evt-{i:03d}",
        "symbol": "BTCUSDT",
        "event_type": "trade",
        "price": 60000.0 + i,
        "quantity": 0.1,
        "event_timestamp": f"2026-05-05T00:{i:02d}:00Z",
        "ingested_at": f"2026-05-05T00:{i:02d}:01Z",
        "source_topic": "market-events",
    }
    for i in range(14, -1, -1)  # indices 14..0 → newest first
]


def _make_fake_fetch_all(expected_limit: int, expected_offset: int):
    def fake_fetch_all(query: str, params: tuple = ()) -> list[dict]:
        assert "FROM bronze.market_events" in query
        assert "ORDER BY ingested_at DESC, event_id DESC" in query
        assert "OFFSET" in query
        assert params == (expected_limit, expected_offset)
        start = expected_offset
        end = start + expected_limit
        return _ALL_ROWS[start:end]

    return fake_fetch_all


def test_events_default_returns_rows(monkeypatch) -> None:
    monkeypatch.setattr("rtdp_api.fetch_all", _make_fake_fetch_all(20, 0))
    client = TestClient(app)
    response = client.get("/events")
    assert response.status_code == 200
    assert response.json()[0]["event_id"] == "evt-014"


def test_events_offset_0_returns_first_page(monkeypatch) -> None:
    monkeypatch.setattr("rtdp_api.fetch_all", _make_fake_fetch_all(5, 0))
    client = TestClient(app)
    response = client.get("/events?limit=5&offset=0")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 5
    assert rows[0]["event_id"] == "evt-014"
    assert rows[4]["event_id"] == "evt-010"


def test_events_offset_5_returns_second_page(monkeypatch) -> None:
    monkeypatch.setattr("rtdp_api.fetch_all", _make_fake_fetch_all(5, 5))
    client = TestClient(app)
    response = client.get("/events?limit=5&offset=5")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 5
    assert rows[0]["event_id"] == "evt-009"
    assert rows[4]["event_id"] == "evt-005"


def test_events_offset_10_returns_third_page(monkeypatch) -> None:
    monkeypatch.setattr("rtdp_api.fetch_all", _make_fake_fetch_all(5, 10))
    client = TestClient(app)
    response = client.get("/events?limit=5&offset=10")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 5
    assert rows[0]["event_id"] == "evt-004"
    assert rows[4]["event_id"] == "evt-000"


def test_events_pages_are_disjoint(monkeypatch) -> None:
    seen = []

    def fake_fetch_all(query: str, params: tuple = ()) -> list[dict]:
        start = params[1]
        end = start + params[0]
        return _ALL_ROWS[start:end]

    monkeypatch.setattr("rtdp_api.fetch_all", fake_fetch_all)
    client = TestClient(app)

    for offset in (0, 5, 10):
        rows = client.get(f"/events?limit=5&offset={offset}").json()
        ids = [r["event_id"] for r in rows]
        assert not any(i in seen for i in ids), f"Duplicate ids at offset={offset}"
        seen.extend(ids)

    assert len(seen) == 15


def test_events_deterministic_ordering(monkeypatch) -> None:
    monkeypatch.setattr("rtdp_api.fetch_all", _make_fake_fetch_all(5, 0))
    client = TestClient(app)
    rows = client.get("/events?limit=5&offset=0").json()
    ingested = [r["ingested_at"] for r in rows]
    assert ingested == sorted(ingested, reverse=True)


def test_events_negative_offset_rejected(monkeypatch) -> None:
    client = TestClient(app)
    response = client.get("/events?offset=-1")
    assert response.status_code == 422


def test_events_limit_capped_at_100(monkeypatch) -> None:
    monkeypatch.setattr("rtdp_api.fetch_all", _make_fake_fetch_all(100, 0))
    client = TestClient(app)
    response = client.get("/events?limit=9999&offset=0")
    assert response.status_code == 200
