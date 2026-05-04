from contextlib import contextmanager
from collections.abc import Generator
from typing import Any

import psycopg
import pytest

import rtdp_api
from rtdp_api import fetch_all


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def execute(self, query: str, params: Any = None) -> None:
        pass

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        pass


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def cursor(self, **kwargs: object) -> _FakeCursor:
        return _FakeCursor(self._rows)

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *args: object) -> None:
        pass


def test_fetch_all_uses_pool_not_psycopg_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    rows: list[dict[str, Any]] = [{"event_id": 1, "symbol": "BTCUSDT"}]
    fake_conn = _FakeConn(rows)

    @contextmanager
    def fake_pool_connection() -> Generator[_FakeConn, None, None]:
        yield fake_conn

    monkeypatch.setattr(rtdp_api.DB_POOL, "connection", fake_pool_connection)

    connect_called = False

    def fail_on_connect(*args: object, **kwargs: object) -> None:
        nonlocal connect_called
        connect_called = True
        raise AssertionError("psycopg.connect must not be called when pool is active")

    monkeypatch.setattr(psycopg, "connect", fail_on_connect)

    result = fetch_all("SELECT event_id, symbol FROM bronze.market_events LIMIT 1")

    assert result == rows
    assert not connect_called
