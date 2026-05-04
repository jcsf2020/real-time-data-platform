"""Tests for the Pub/Sub worker HTTP runtime."""

import base64
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from rtdp_pubsub_worker.http_app import create_app, extract_pubsub_data


@pytest.fixture()
def client():
    return TestClient(create_app())


def _make_envelope(data_b64: str, *, message_id: str = "msg-001") -> dict:
    return {
        "message": {
            "data": data_b64,
            "messageId": message_id,
            "publishTime": "2024-01-01T00:00:00Z",
        },
        "subscription": "projects/test-project/subscriptions/test-sub",
    }


def _encode_payload(**overrides) -> str:
    defaults = {
        "schema_version": "1.0",
        "event_id": "test-evt-001",
        "symbol": "BTCUSDT",
        "event_type": "trade",
        "price": "67500.00",
        "quantity": "0.01",
        "event_timestamp": "2024-01-01T00:00:00+00:00",
    }
    return base64.b64encode(json.dumps({**defaults, **overrides}).encode()).decode()


# --- /health ---


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --- extract_pubsub_data unit tests ---


def test_extract_pubsub_data_decodes_valid_envelope():
    raw = b'{"hello": "world"}'
    envelope = _make_envelope(base64.b64encode(raw).decode())
    assert extract_pubsub_data(envelope) == raw


def test_extract_pubsub_data_raises_on_missing_message():
    with pytest.raises(ValueError, match="missing 'message'"):
        extract_pubsub_data({"subscription": "test"})


def test_extract_pubsub_data_raises_on_missing_data():
    with pytest.raises(ValueError, match="missing 'data'"):
        extract_pubsub_data({"message": {"messageId": "x"}})


def test_extract_pubsub_data_raises_on_invalid_base64():
    with pytest.raises(ValueError, match="invalid base64"):
        extract_pubsub_data({"message": {"data": "!!!invalid!!!", "messageId": "x"}})


# --- POST /pubsub/push ---


def test_push_valid_envelope_calls_process_message_and_returns_200(client):
    envelope = _make_envelope(_encode_payload())
    with patch(
        "rtdp_pubsub_worker.http_app.process_message",
        return_value={"status": "ok", "event_id": "test-evt-001"},
    ):
        response = client.post("/pubsub/push", json=envelope)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["event_id"] == "test-evt-001"


def test_push_missing_message_returns_400(client):
    response = client.post("/pubsub/push", json={"subscription": "test"})
    assert response.status_code == 400


def test_push_missing_data_returns_400(client):
    response = client.post(
        "/pubsub/push",
        json={"message": {"messageId": "x"}, "subscription": "test"},
    )
    assert response.status_code == 400


def test_push_invalid_base64_returns_400(client):
    envelope = {"message": {"data": "!!!invalid!!!", "messageId": "x"}, "subscription": "test"}
    response = client.post("/pubsub/push", json=envelope)
    assert response.status_code == 400


def test_push_process_message_error_returns_500(client):
    envelope = _make_envelope(_encode_payload())
    with patch(
        "rtdp_pubsub_worker.http_app.process_message",
        return_value={"status": "error", "error": "db connection refused"},
    ):
        response = client.post("/pubsub/push", json=envelope)
    assert response.status_code == 500
    assert response.json()["status"] == "error"
