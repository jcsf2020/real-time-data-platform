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
)

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
    t0 = time.monotonic()
    event_id = None
    symbol = None
    try:
        payload = decode_message(data)
        event = validate_event(payload)
        event_id = event.event_id
        symbol = event.symbol
        insert_bronze_event(event, payload, database_url)
    except Exception as exc:
        emit_log({
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
            "timestamp_utc": utc_now_iso(),
        })
        return {"status": "error", "error": str(exc)}
    emit_log({
        "component": "pubsub-worker",
        "event_id": event_id,
        "operation": "process_message",
        "processing_time_ms": round((time.monotonic() - t0) * 1000, 3),
        "service": "rtdp-pubsub-worker",
        "source_topic": SOURCE_TOPIC,
        "status": "ok",
        "symbol": symbol,
        "timestamp_utc": utc_now_iso(),
    })
    return {"status": "ok", "event_id": event_id}


def main(argv: list[str] | None = None) -> None:
    """Read a JSON MarketEvent from stdin and process it. For local validation only."""
    database_url = os.getenv("DATABASE_URL", DATABASE_URL)
    data = sys.stdin.buffer.read()
    result = process_message(data, database_url)
    print(json.dumps(result))
    if result["status"] != "ok":
        sys.exit(1)
