"""Pub/Sub worker: decode, validate, and persist MarketEvent messages."""

import json
import os
import sys
import time
from datetime import datetime, timezone

import psycopg

from rtdp_contracts import MarketEvent

SOURCE_TOPIC = "market-events-raw"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rtdp:rtdp@localhost:15432/realtime_platform",
).strip()

_INSERT_SQL = """
    INSERT INTO bronze.market_events (
        event_id,
        symbol,
        event_type,
        price,
        quantity,
        event_timestamp,
        source_topic,
        raw_payload
    )
    VALUES (
        %(event_id)s,
        %(symbol)s,
        %(event_type)s,
        %(price)s,
        %(quantity)s,
        %(event_timestamp)s,
        %(source_topic)s,
        %(raw_payload)s
    )
    ON CONFLICT (event_id) DO NOTHING;
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _diff_ms(start_iso: str | None, end_iso: str | None) -> float | None:
    if start_iso is None or end_iso is None:
        return None
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        return round((end - start).total_seconds() * 1000, 3)
    except Exception:
        return None


def emit_log(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


def decode_message(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))


def validate_event(payload: dict) -> MarketEvent:
    return MarketEvent.model_validate(payload)


def insert_bronze_event(event: MarketEvent, raw_payload: dict, database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                _INSERT_SQL,
                {
                    "event_id": event.event_id,
                    "symbol": event.symbol,
                    "event_type": event.event_type,
                    "price": event.price,
                    "quantity": event.quantity,
                    "event_timestamp": event.event_timestamp,
                    "source_topic": SOURCE_TOPIC,
                    "raw_payload": json.dumps(raw_payload),
                },
            )


def process_message(data: bytes, database_url: str = DATABASE_URL) -> dict:
    """Process one Pub/Sub message. Returns status dict; never raises."""
    worker_received_at = utc_now_iso()
    t0 = time.monotonic()
    event_id = None
    symbol = None
    producer_created_at: str | None = None
    worker_decoded_at: str | None = None
    worker_validated_at: str | None = None
    db_insert_started_at: str | None = None
    db_insert_completed_at: str | None = None

    try:
        payload = decode_message(data)
        worker_decoded_at = utc_now_iso()
        producer_created_at = payload.get("producer_created_at")
        event = validate_event(payload)
        worker_validated_at = utc_now_iso()
        event_id = event.event_id
        symbol = event.symbol
        db_insert_started_at = utc_now_iso()
        insert_bronze_event(event, payload, database_url)
        db_insert_completed_at = utc_now_iso()
    except Exception as exc:
        worker_completed_at = utc_now_iso()
        log_entry: dict = {
            "component": "pubsub-worker",
            "error_message": str(exc),
            "error_type": type(exc).__name__,
            "event_id": event_id,
            "operation": "process_message",
            "processing_time_ms": round((time.monotonic() - t0) * 1000, 3),
            "service": "rtdp-pubsub-worker",
            "source_topic": SOURCE_TOPIC,
            "status": "error",
            "symbol": symbol,
            "timestamp_utc": worker_completed_at,
            "worker_completed_at": worker_completed_at,
            "worker_received_at": worker_received_at,
        }
        if worker_decoded_at is not None:
            log_entry["worker_decoded_at"] = worker_decoded_at
        if worker_validated_at is not None:
            log_entry["worker_validated_at"] = worker_validated_at
        if db_insert_started_at is not None:
            log_entry["db_insert_started_at"] = db_insert_started_at
        emit_log(log_entry)
        return {"status": "error", "error": str(exc)}

    worker_completed_at = utc_now_iso()

    validation_latency_ms = _diff_ms(worker_received_at, worker_validated_at)
    db_write_latency_ms = _diff_ms(db_insert_started_at, db_insert_completed_at)
    worker_processing_latency_ms = _diff_ms(worker_received_at, worker_completed_at)

    log_entry = {
        "component": "pubsub-worker",
        "db_insert_completed_at": db_insert_completed_at,
        "db_insert_started_at": db_insert_started_at,
        "db_write_latency_ms": db_write_latency_ms,
        "event_id": event_id,
        "operation": "process_message",
        "processing_time_ms": round((time.monotonic() - t0) * 1000, 3),
        "service": "rtdp-pubsub-worker",
        "source_topic": SOURCE_TOPIC,
        "status": "ok",
        "symbol": symbol,
        "timestamp_utc": worker_completed_at,
        "validation_latency_ms": validation_latency_ms,
        "worker_completed_at": worker_completed_at,
        "worker_decoded_at": worker_decoded_at,
        "worker_processing_latency_ms": worker_processing_latency_ms,
        "worker_received_at": worker_received_at,
        "worker_validated_at": worker_validated_at,
    }
    if producer_created_at is not None:
        log_entry["producer_created_at"] = producer_created_at
        end_to_end_latency_ms = _diff_ms(producer_created_at, worker_completed_at)
        if end_to_end_latency_ms is not None:
            log_entry["end_to_end_latency_ms"] = end_to_end_latency_ms

    emit_log(log_entry)
    return {"status": "ok", "event_id": event_id}


def main(argv: list[str] | None = None) -> None:
    """Read a JSON MarketEvent from stdin and process it. For local validation only."""
    database_url = os.getenv("DATABASE_URL", DATABASE_URL).strip()
    data = sys.stdin.buffer.read()
    result = process_message(data, database_url)
    print(json.dumps(result))
    if result["status"] != "ok":
        sys.exit(1)
