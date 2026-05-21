"""Tests for the GCP Pub/Sub publisher."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from rtdp_contracts import MarketEvent
from rtdp_pubsub_publisher import _parse_args, build_sample_event, publish_event, serialize_event


# --- Contract validation ---


def test_contract_rejects_non_positive_price():
    with pytest.raises(ValidationError):
        MarketEvent(
            event_id="bad",
            symbol="BTCUSDT",
            price=Decimal("-1"),
            quantity=Decimal("1"),
            event_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


def test_contract_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        MarketEvent(
            event_id="bad",
            symbol="BTCUSDT",
            price=Decimal("100"),
            quantity=Decimal("0"),
            event_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


# --- Serialization ---


def test_serialize_event_produces_utf8_json():
    event = MarketEvent(
        event_id="test-001",
        symbol="ETHUSDT",
        price=Decimal("3200.50"),
        quantity=Decimal("1.5"),
        event_timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    data = serialize_event(event)
    assert isinstance(data, bytes)
    payload = json.loads(data.decode("utf-8"))
    assert payload["event_id"] == "test-001"
    assert payload["symbol"] == "ETHUSDT"
    assert payload["schema_version"] == "1.0"
    assert payload["event_type"] == "trade"


def test_serialize_event_includes_all_required_fields():
    event = MarketEvent(
        event_id="test-002",
        symbol="BTCUSDT",
        price=Decimal("67500.00"),
        quantity=Decimal("0.001"),
        event_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    payload = json.loads(serialize_event(event).decode("utf-8"))
    for field in ("event_id", "symbol", "price", "quantity", "event_timestamp", "schema_version"):
        assert field in payload, f"missing field: {field}"


def test_serialize_event_without_extra_fields_is_backward_compatible():
    event = MarketEvent(
        event_id="test-bc",
        symbol="BTCUSDT",
        price=Decimal("100.00"),
        quantity=Decimal("1.0"),
        event_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    assert serialize_event(event) == serialize_event(event, None)
    assert serialize_event(event) == event.model_dump_json().encode("utf-8")


def test_serialize_event_with_extra_fields_merges_into_payload():
    event = MarketEvent(
        event_id="test-extra",
        symbol="ETHUSDT",
        price=Decimal("3000.00"),
        quantity=Decimal("0.5"),
        event_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    extra = {"producer_created_at": "2024-01-01T00:00:00+00:00"}
    payload = json.loads(serialize_event(event, extra_fields=extra).decode("utf-8"))
    assert payload["producer_created_at"] == "2024-01-01T00:00:00+00:00"
    assert payload["event_id"] == "test-extra"
    assert payload["symbol"] == "ETHUSDT"


def test_serialize_event_extra_fields_do_not_appear_without_them():
    event = MarketEvent(
        event_id="test-noextra",
        symbol="BTCUSDT",
        price=Decimal("100.00"),
        quantity=Decimal("1.0"),
        event_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    payload = json.loads(serialize_event(event).decode("utf-8"))
    assert "producer_created_at" not in payload


def test_build_sample_event_returns_valid_market_event():
    event = build_sample_event()
    assert isinstance(event, MarketEvent)
    assert event.schema_version == "1.0"
    assert event.symbol == "BTCUSDT"
    assert event.price > 0
    assert event.quantity > 0
    assert event.event_id  # non-empty UUID string


# --- Publisher / topic path ---


def test_publish_event_calls_publisher_with_correct_topic_path():
    publisher = MagicMock()
    publisher.topic_path.return_value = "projects/my-project/topics/market-events-raw"
    mock_future = MagicMock()
    mock_future.result.return_value = "msg-id-123"
    publisher.publish.return_value = mock_future

    event = MarketEvent(
        event_id="test-003",
        symbol="SOLUSDT",
        price=Decimal("150.00"),
        quantity=Decimal("10.0"),
        event_timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )

    message_id = publish_event(publisher, "my-project", "market-events-raw", event)

    publisher.topic_path.assert_called_once_with("my-project", "market-events-raw")
    publisher.publish.assert_called_once()
    publish_call = publisher.publish.call_args
    assert publish_call.args[0] == "projects/my-project/topics/market-events-raw"
    assert publish_call.kwargs["data"] == serialize_event(event)
    assert message_id == "msg-id-123"


def test_publish_event_returns_message_id_from_future():
    publisher = MagicMock()
    publisher.topic_path.return_value = "projects/p/topics/t"
    mock_future = MagicMock()
    mock_future.result.return_value = "unique-msg-id"
    publisher.publish.return_value = mock_future

    message_id = publish_event(publisher, "p", "t", build_sample_event())
    assert message_id == "unique-msg-id"


def test_publish_event_with_extra_fields_includes_them_in_payload():
    publisher = MagicMock()
    publisher.topic_path.return_value = "projects/p/topics/t"
    mock_future = MagicMock()
    mock_future.result.return_value = "msg-extra"
    publisher.publish.return_value = mock_future

    event = MarketEvent(
        event_id="test-extra-pub",
        symbol="BTCUSDT",
        price=Decimal("100.00"),
        quantity=Decimal("1.0"),
        event_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    extra = {"producer_created_at": "2024-01-01T00:00:00+00:00"}

    publish_event(publisher, "p", "t", event, extra_fields=extra)

    publish_call = publisher.publish.call_args
    payload = json.loads(publish_call.kwargs["data"].decode("utf-8"))
    assert payload["producer_created_at"] == "2024-01-01T00:00:00+00:00"


# --- Latency artifact ---


def test_latency_artifact_writes_one_jsonl_line(tmp_path, capsys):
    artifact_path = tmp_path / "artifact.jsonl"

    mock_publisher = MagicMock()
    mock_publisher.topic_path.return_value = "projects/test-project/topics/market-events-raw"
    mock_future = MagicMock()
    mock_future.result.return_value = "msg-artifact-id"
    mock_publisher.publish.return_value = mock_future

    with patch("rtdp_pubsub_publisher.pubsub_v1.PublisherClient", return_value=mock_publisher):
        from rtdp_pubsub_publisher import main
        main([
            "--project-id", "test-project",
            "--latency-artifact-path", str(artifact_path),
            "--include-latency-metadata",
        ])

    lines = artifact_path.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["status"] == "published"
    assert "event_id" in row
    assert row["message_id"] == "msg-artifact-id"
    assert "symbol" in row
    assert "topic" in row
    assert "producer_created_at" in row
    assert row["producer_created_at"] is not None
    assert "pubsub_publish_ack_at" in row


def test_latency_artifact_without_metadata_has_null_producer_created_at(tmp_path, capsys):
    artifact_path = tmp_path / "artifact_nometa.jsonl"

    mock_publisher = MagicMock()
    mock_publisher.topic_path.return_value = "projects/p/topics/t"
    mock_future = MagicMock()
    mock_future.result.return_value = "msg-no-meta"
    mock_publisher.publish.return_value = mock_future

    with patch("rtdp_pubsub_publisher.pubsub_v1.PublisherClient", return_value=mock_publisher):
        from rtdp_pubsub_publisher import main
        main([
            "--project-id", "p",
            "--latency-artifact-path", str(artifact_path),
        ])

    lines = artifact_path.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["producer_created_at"] is None


def test_no_artifact_written_without_flag(tmp_path, capsys):
    artifact_path = tmp_path / "should_not_exist.jsonl"

    mock_publisher = MagicMock()
    mock_publisher.topic_path.return_value = "projects/p/topics/t"
    mock_future = MagicMock()
    mock_future.result.return_value = "msg-no-artifact"
    mock_publisher.publish.return_value = mock_future

    with patch("rtdp_pubsub_publisher.pubsub_v1.PublisherClient", return_value=mock_publisher):
        from rtdp_pubsub_publisher import main
        main(["--project-id", "p"])

    assert not artifact_path.exists()


# --- Config / CLI args ---


def test_parse_args_project_id_from_flag(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("PUBSUB_TOPIC", raising=False)
    args = _parse_args(["--project-id", "test-project"])
    assert args.project_id == "test-project"
    assert args.topic == "market-events-raw"


def test_parse_args_topic_override(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("PUBSUB_TOPIC", raising=False)
    args = _parse_args(["--project-id", "test-project", "--topic", "custom-topic"])
    assert args.project_id == "test-project"
    assert args.topic == "custom-topic"


def test_parse_args_reads_project_and_topic_from_env(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "env-project")
    monkeypatch.setenv("PUBSUB_TOPIC", "env-topic")
    args = _parse_args([])
    assert args.project_id == "env-project"
    assert args.topic == "env-topic"


def test_parse_args_latency_artifact_path(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    args = _parse_args(["--project-id", "p", "--latency-artifact-path", "/tmp/out.jsonl"])
    assert args.latency_artifact_path == "/tmp/out.jsonl"
    assert not args.include_latency_metadata


def test_parse_args_include_latency_metadata(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    args = _parse_args(["--project-id", "p", "--include-latency-metadata"])
    assert args.include_latency_metadata is True
    assert args.latency_artifact_path is None


def test_parse_args_latency_metadata_default_false(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    args = _parse_args(["--project-id", "p"])
    assert args.include_latency_metadata is False
    assert args.latency_artifact_path is None


def test_main_exits_with_error_when_no_project_id(monkeypatch, capsys):
    from rtdp_pubsub_publisher import main

    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 1
    assert "GCP_PROJECT_ID" in capsys.readouterr().err
