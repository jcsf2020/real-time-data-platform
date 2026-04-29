import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Literal

import psycopg
from kafka import KafkaConsumer
from pydantic import BaseModel, Field


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rtdp:rtdp@localhost:15432/realtime_platform",
)


class MarketEvent(BaseModel):
    event_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    event_type: Literal["trade"]
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    event_timestamp: datetime


def insert_bronze_event(event: MarketEvent, raw_payload: dict) -> None:
    query = """
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

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                {
                    "event_id": event.event_id,
                    "symbol": event.symbol,
                    "event_type": event.event_type,
                    "price": event.price,
                    "quantity": event.quantity,
                    "event_timestamp": event.event_timestamp,
                    "source_topic": "market.events.raw",
                    "raw_payload": json.dumps(raw_payload),
                },
            )


def main() -> None:
    consumer = KafkaConsumer(
        "market.events.raw",
        bootstrap_servers="localhost:19092",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=5000,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )

    inserted = 0

    for message in consumer:
        raw_payload = message.value
        event = MarketEvent.model_validate(raw_payload)
        insert_bronze_event(event, raw_payload)
        inserted += 1

        print(
            {
                "status": "processed",
                "topic": message.topic,
                "partition": message.partition,
                "offset": message.offset,
                "event_id": event.event_id,
            }
        )




if __name__ == "__main__":
    main()
