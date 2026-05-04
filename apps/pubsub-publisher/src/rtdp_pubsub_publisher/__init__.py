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


def build_sample_event() -> MarketEvent:
    return MarketEvent(
        event_id=str(uuid.uuid4()),
        symbol="BTCUSDT",
        price=Decimal("67500.00"),
        quantity=Decimal("0.01"),
        event_timestamp=datetime.now(timezone.utc),
    )


def serialize_event(event: MarketEvent) -> bytes:
    return event.model_dump_json().encode("utf-8")


def publish_event(
    publisher: pubsub_v1.PublisherClient,
    project_id: str,
    topic_name: str,
    event: MarketEvent,
) -> str:
    topic_path = publisher.topic_path(project_id, topic_name)
    data = serialize_event(event)
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if not args.project_id:
        print("ERROR: --project-id or GCP_PROJECT_ID is required", file=sys.stderr)
        sys.exit(1)

    event = build_sample_event()
    publisher = pubsub_v1.PublisherClient()
    message_id = publish_event(publisher, args.project_id, args.topic, event)

    print(
        json.dumps(
            {
                "status": "published",
                "message_id": message_id,
                "event_id": event.event_id,
                "symbol": event.symbol,
                "topic": publisher.topic_path(args.project_id, args.topic),
            }
        )
    )
