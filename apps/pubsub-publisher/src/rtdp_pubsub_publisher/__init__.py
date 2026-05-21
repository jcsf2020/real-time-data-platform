"""GCP Pub/Sub publisher for MarketEvent payloads."""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from google.cloud import pubsub_v1

from rtdp_contracts import MarketEvent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_sample_event() -> MarketEvent:
    return MarketEvent(
        event_id=str(uuid.uuid4()),
        symbol="BTCUSDT",
        price=Decimal("67500.00"),
        quantity=Decimal("0.01"),
        event_timestamp=datetime.now(timezone.utc),
    )


def serialize_event(event: MarketEvent, extra_fields: dict | None = None) -> bytes:
    if extra_fields is None:
        return event.model_dump_json().encode("utf-8")
    payload = json.loads(event.model_dump_json())
    payload.update(extra_fields)
    return json.dumps(payload).encode("utf-8")


def publish_event(
    publisher: pubsub_v1.PublisherClient,
    project_id: str,
    topic_name: str,
    event: MarketEvent,
    extra_fields: dict | None = None,
) -> str:
    topic_path = publisher.topic_path(project_id, topic_name)
    data = serialize_event(event, extra_fields)
    future = publisher.publish(topic_path, data=data)
    return future.result()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish a MarketEvent to GCP Pub/Sub.")
    parser.add_argument(
        "--project-id",
        default=os.environ.get("GCP_PROJECT_ID", ""),
        help="GCP project ID (or set GCP_PROJECT_ID env var)",
    )
    parser.add_argument(
        "--topic",
        default=os.environ.get("PUBSUB_TOPIC", "market-events-raw"),
        help="Pub/Sub topic name (default: market-events-raw)",
    )
    parser.add_argument(
        "--latency-artifact-path",
        default=None,
        help="If set, append a JSONL row with publish timestamps to this file.",
    )
    parser.add_argument(
        "--include-latency-metadata",
        action="store_true",
        default=False,
        help="Include producer_created_at in the published payload.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if not args.project_id:
        print("ERROR: --project-id or GCP_PROJECT_ID is required", file=sys.stderr)
        sys.exit(1)

    event = build_sample_event()

    extra_fields: dict | None = None
    producer_created_at: str | None = None
    if args.include_latency_metadata:
        producer_created_at = utc_now_iso()
        extra_fields = {"producer_created_at": producer_created_at}

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(args.project_id, args.topic)
    data = serialize_event(event, extra_fields)
    future = publisher.publish(topic_path, data=data)
    message_id = future.result()
    pubsub_publish_ack_at = utc_now_iso()

    if args.latency_artifact_path:
        row = {
            "status": "published",
            "event_id": event.event_id,
            "message_id": message_id,
            "symbol": event.symbol,
            "topic": topic_path,
            "producer_created_at": producer_created_at,
            "pubsub_publish_ack_at": pubsub_publish_ack_at,
        }
        with open(args.latency_artifact_path, "a") as f:
            f.write(json.dumps(row) + "\n")

    print(
        json.dumps(
            {
                "status": "published",
                "message_id": message_id,
                "event_id": event.event_id,
                "symbol": event.symbol,
                "topic": topic_path,
            }
        )
    )
