"""Tests for the GCP Pub/Sub worker."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from rtdp_contracts import MarketEvent
from rtdp_pubsub_worker import decode_message, insert_bronze_event, process_message, validate_event


# --- helpers ---


def _make_payload(**overrides) -> dict:
    defaults = {
        "schema_version": "1.0",
        "event_id": "test-evt-001",
        "symbol": "BTCUSDT",
        "event_type": "trade",
        "price": "67500.00",
        "quantity": "0.01",
        "event_timestamp": "2024-01-01T00:00:00+00:00",
    }
    return {**defaults, **overrides}


def _make_event(**overrides) -> MarketEvent:
    defaults = {
        "event_id": "test-evt-001",
        "symbol": "BTCUSDT",
        "price": Decimal("67500.00"),
        "quantity": Decimal("0.01"),
        "event_timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }
    return MarketEvent(**{**defaults, **overrides})


def _mock_conn():
    mock_cur = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cur


# --- decode_message ---


def test_decode_message_returns_dict_from_valid_json():
    payload = {"event_id": "x", "price": "100"}
    assert decode_message(json.dumps(payload).encode("utf-8")) == payload


def test_decode_message_raises_on_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        decode_message(b"not-json")


def test_decode_message_raises_on_empty_bytes():
    with pytest.raises(json.JSONDecodeError):
        decode_message(b"")


# --- validate_event ---


def test_validate_event_returns_market_event():
    event = validate_event(_make_payload())
    assert isinstance(event, MarketEvent)
    assert event.event_id == "test-evt-001"
    assert event.symbol == "BTCUSDT"


def test_validate_event_rejects_negative_price():
    with pytest.raises(ValidationError):
        validate_event(_make_payload(price="-1"))


def test_validate_event_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        validate_event(_make_payload(quantity="0"))


def test_validate_event_rejects_missing_event_id():
    payload = _make_payload()
    del payload["event_id"]
    with pytest.raises(ValidationError):
        validate_event(payload)


# --- insert_bronze_event ---


def test_insert_bronze_event_executes_insert_sql():
    mock_conn, mock_cur = _mock_conn()
    event = _make_event()
    payload = _make_payload()

    with patch("rtdp_pubsub_worker.psycopg.connect", return_value=mock_conn):
        insert_bronze_event(event, payload, "postgresql://test")

    mock_cur.execute.assert_called_once()
    sql, params = mock_cur.execute.call_args.args
    assert "ON CONFLICT" in sql
    assert "bronze.market_events" in sql
    assert params["event_id"] == "test-evt-001"


def test_insert_bronze_event_sets_source_topic_to_pubsub():
    mock_conn, mock_cur = _mock_conn()

    with patch("rtdp_pubsub_worker.psycopg.connect", return_value=mock_conn):
        insert_bronze_event(_make_event(), _make_payload(), "postgresql://test")

    params = mock_cur.execute.call_args.args[1]
    assert params["source_topic"] == "market-events-raw"


def test_insert_bronze_event_stores_raw_payload_as_json_string():
    mock_conn, mock_cur = _mock_conn()
    payload = _make_payload()

    with patch("rtdp_pubsub_worker.psycopg.connect", return_value=mock_conn):
        insert_bronze_event(_make_event(), payload, "postgresql://test")

    params = mock_cur.execute.call_args.args[1]
    decoded = json.loads(params["raw_payload"])
    assert decoded["event_id"] == "test-evt-001"


# --- process_message (end-to-end) ---


def test_process_message_returns_ok_on_valid_input():
    mock_conn, _ = _mock_conn()
    data = json.dumps(_make_payload()).encode("utf-8")

    with patch("rtdp_pubsub_worker.psycopg.connect", return_value=mock_conn):
        result = process_message(data, "postgresql://test")

    assert result["status"] == "ok"
    assert result["event_id"] == "test-evt-001"


def test_process_message_returns_error_on_invalid_json():
    result = process_message(b"not-json", "postgresql://test")
    assert result["status"] == "error"
    assert "error" in result


def test_process_message_returns_error_on_validation_failure():
    data = json.dumps(_make_payload(price="-1")).encode("utf-8")
    result = process_message(data, "postgresql://test")
    assert result["status"] == "error"


def test_process_message_returns_error_on_db_failure():
    data = json.dumps(_make_payload()).encode("utf-8")

    with patch("rtdp_pubsub_worker.psycopg.connect", side_effect=Exception("connection refused")):
        result = process_message(data, "postgresql://test")

    assert result["status"] == "error"
    assert "connection refused" in result["error"]


def test_process_message_duplicate_event_id_does_not_raise():
    """ON CONFLICT DO NOTHING means re-processing the same event_id must succeed."""
    mock_conn, _ = _mock_conn()
    data = json.dumps(_make_payload()).encode("utf-8")

    with patch("rtdp_pubsub_worker.psycopg.connect", return_value=mock_conn):
        result1 = process_message(data, "postgresql://test")
        result2 = process_message(data, "postgresql://test")

    assert result1["status"] == "ok"
    assert result2["status"] == "ok"


@pytest.mark.parametrize(
    "symbol",
    ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
)
def test_process_message_accepts_various_symbols(symbol):
    mock_conn, _ = _mock_conn()
    data = json.dumps(_make_payload(event_id=f"evt-{symbol}", symbol=symbol)).encode("utf-8")

    with patch("rtdp_pubsub_worker.psycopg.connect", return_value=mock_conn):
        result = process_message(data, "postgresql://test")

    assert result["status"] == "ok"
    assert result["event_id"] == f"evt-{symbol}"


# --- process_message structured logging ---


def _capture_log(capsys) -> dict:
    """Read the single JSON log line emitted to stdout."""
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected 1 log line, got {len(lines)}: {lines}"
    return json.loads(lines[0])


def test_log_valid_message_emits_one_line(capsys):
    mock_conn, _ = _mock_conn()
    data = json.dumps(_make_payload()).encode("utf-8")

    with patch("rtdp_pubsub_worker.psycopg.connect", return_value=mock_conn):
        process_message(data, "postgresql://test")

    log = _capture_log(capsys)
    assert log["status"] == "ok"
    assert log["event_id"] == "test-evt-001"
    assert log["symbol"] == "BTCUSDT"
    assert log["service"] == "rtdp-pubsub-worker"
    assert log["component"] == "pubsub-worker"
    assert log["operation"] == "process_message"
    assert log["source_topic"] == "market-events-raw"
    assert log["processing_time_ms"] >= 0
    assert "timestamp_utc" in log


def test_log_invalid_json_emits_error_line(capsys):
    process_message(b"not-json", "postgresql://test")

    log = _capture_log(capsys)
    assert log["status"] == "error"
    assert "error_type" in log
    assert log["service"] == "rtdp-pubsub-worker"


def test_log_validation_failure_emits_error_line(capsys):
    data = json.dumps(_make_payload(price="-1")).encode("utf-8")
    process_message(data, "postgresql://test")

    log = _capture_log(capsys)
    assert log["status"] == "error"
    assert "error_type" in log


def test_log_db_failure_emits_error_line(capsys):
    data = json.dumps(_make_payload()).encode("utf-8")

    with patch("rtdp_pubsub_worker.psycopg.connect", side_effect=Exception("connection refused")):
        process_message(data, "postgresql://test")

    log = _capture_log(capsys)
    assert log["status"] == "error"
    assert log["error_type"] == "Exception"
    assert "connection refused" in log["error_message"]


def test_log_does_not_contain_raw_payload(capsys):
    mock_conn, _ = _mock_conn()
    data = json.dumps(_make_payload()).encode("utf-8")

    with patch("rtdp_pubsub_worker.psycopg.connect", return_value=mock_conn):
        process_message(data, "postgresql://test")

    log = _capture_log(capsys)
    assert "payload" not in log
    assert "raw_payload" not in log
    assert "data" not in log


def test_process_message_return_values_unchanged_by_logging(capsys):
    mock_conn, _ = _mock_conn()
    data = json.dumps(_make_payload()).encode("utf-8")

    with patch("rtdp_pubsub_worker.psycopg.connect", return_value=mock_conn):
        result = process_message(data, "postgresql://test")

    assert result == {"status": "ok", "event_id": "test-evt-001"}


def test_process_message_error_return_value_unchanged_by_logging(capsys):
    result = process_message(b"not-json", "postgresql://test")

    assert result["status"] == "error"
    assert "error" in result
