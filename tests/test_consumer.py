from unittest.mock import MagicMock, patch

import pytest
from rtdp_consumer import parse_silver_refresh_interval, refresh_silver_minute_aggregates


def test_parse_silver_refresh_interval_default(monkeypatch) -> None:
    monkeypatch.delenv("SILVER_REFRESH_EVERY_N_EVENTS", raising=False)
    assert parse_silver_refresh_interval() == 25


def test_parse_silver_refresh_interval_valid(monkeypatch) -> None:
    monkeypatch.setenv("SILVER_REFRESH_EVERY_N_EVENTS", "10")
    assert parse_silver_refresh_interval() == 10


@pytest.mark.parametrize("bad_value", ["0", "-5", "abc", ""])
def test_parse_silver_refresh_interval_invalid_falls_back_to_default(
    monkeypatch, bad_value
) -> None:
    monkeypatch.setenv("SILVER_REFRESH_EVERY_N_EVENTS", bad_value)
    assert parse_silver_refresh_interval() == 25


def test_refresh_silver_minute_aggregates_returns_row_count() -> None:
    mock_row = (42,)
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = mock_row
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("rtdp_consumer.psycopg.connect", return_value=mock_conn):
        result = refresh_silver_minute_aggregates()

    assert result == 42


def test_refresh_silver_minute_aggregates_returns_zero_on_null() -> None:
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (None,)
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("rtdp_consumer.psycopg.connect", return_value=mock_conn):
        result = refresh_silver_minute_aggregates()

    assert result == 0
