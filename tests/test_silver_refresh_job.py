"""Tests for the silver refresh job."""

import json
from unittest.mock import MagicMock, patch

import pytest

from rtdp_silver_refresh_job import main, run_refresh

_SQL = "SELECT silver.refresh_market_event_minute_aggregates();"


# --- helpers ---


def _mock_conn():
    mock_cur = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cur


def _capture_log(capsys) -> dict:
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected 1 log line, got {len(lines)}: {lines}"
    return json.loads(lines[0])


# --- missing DATABASE_URL ---


def test_missing_database_url_exits_nonzero(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_missing_database_url_emits_status_error(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit):
        main()
    log = _capture_log(capsys)
    assert log["status"] == "error"
    assert log["service"] == "rtdp-silver-refresh-job"


# --- successful refresh ---


def test_successful_refresh_calls_connect_with_database_url(capsys):
    mock_conn, _ = _mock_conn()
    with patch("rtdp_silver_refresh_job.psycopg.connect", return_value=mock_conn) as mock_connect:
        run_refresh("postgresql://test")
    mock_connect.assert_called_once_with("postgresql://test")


def test_successful_refresh_executes_correct_sql(capsys):
    mock_conn, mock_cur = _mock_conn()
    with patch("rtdp_silver_refresh_job.psycopg.connect", return_value=mock_conn):
        run_refresh("postgresql://test")
    mock_cur.execute.assert_called_once_with(_SQL)


def test_successful_refresh_emits_ok_log(capsys):
    mock_conn, _ = _mock_conn()
    with patch("rtdp_silver_refresh_job.psycopg.connect", return_value=mock_conn):
        run_refresh("postgresql://test")
    log = _capture_log(capsys)
    assert log["status"] == "ok"
    assert log["service"] == "rtdp-silver-refresh-job"
    assert log["component"] == "silver-refresh"
    assert log["operation"] == "refresh_market_event_minute_aggregates"
    assert log["processing_time_ms"] >= 0
    assert "timestamp_utc" in log


def test_successful_refresh_returns_zero(capsys):
    mock_conn, _ = _mock_conn()
    with patch("rtdp_silver_refresh_job.psycopg.connect", return_value=mock_conn):
        result = run_refresh("postgresql://test")
    assert result == 0


# --- DB failure ---


def test_db_failure_returns_one(capsys):
    with patch("rtdp_silver_refresh_job.psycopg.connect", side_effect=Exception("connection refused")):
        result = run_refresh("postgresql://test")
    assert result == 1


def test_db_failure_emits_error_log_with_error_type(capsys):
    with patch("rtdp_silver_refresh_job.psycopg.connect", side_effect=Exception("connection refused")):
        run_refresh("postgresql://test")
    log = _capture_log(capsys)
    assert log["status"] == "error"
    assert log["error_type"] == "Exception"
    assert "connection refused" in log["error_message"]


# --- no secrets in log ---


def test_log_does_not_contain_database_url(capsys):
    mock_conn, _ = _mock_conn()
    db_url = "postgresql://user:secret@host/db"
    with patch("rtdp_silver_refresh_job.psycopg.connect", return_value=mock_conn):
        run_refresh(db_url)
    log_str = capsys.readouterr().out
    assert "secret" not in log_str
    assert db_url not in log_str


# --- CLI main ---


def test_main_exits_zero_on_success(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    mock_conn, _ = _mock_conn()
    with patch("rtdp_silver_refresh_job.psycopg.connect", return_value=mock_conn):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0


def test_main_exits_one_on_db_failure(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    with patch("rtdp_silver_refresh_job.psycopg.connect", side_effect=Exception("boom")):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
