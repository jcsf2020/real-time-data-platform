import json
import os
import random
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from kafka import KafkaProducer
from rtdp_contracts import MarketEvent


TOPIC = "market.events.raw"
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")


def build_market_event() -> dict:
    symbols = {
        "BTCUSDT": (62000, 72000),
        "ETHUSDT": (2800, 4200),
        "SOLUSDT": (120, 220),
    }

    symbol = random.choice(list(symbols.keys()))
    low, high = symbols[symbol]

    event = MarketEvent(
        event_id=str(uuid.uuid4()),
        symbol=symbol,
        price=Decimal(str(round(random.uniform(low, high), 2))),
        quantity=Decimal(str(round(random.uniform(0.001, 2.5), 6))),
        event_timestamp=datetime.now(UTC),
    )

    return json.loads(event.model_dump_json())


def main() -> None:
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        compression_type="snappy",
    )

    print("producer started...")

    while True:
        event = build_market_event()
        metadata = producer.send(TOPIC, value=event).get(timeout=10)

        print(
            {
                "status": "produced",
                "topic": metadata.topic,
                "partition": metadata.partition,
                "offset": metadata.offset,
                "event_id": event["event_id"],
                "symbol": event["symbol"],
            }
        )

        time.sleep(1)


if __name__ == "__main__":
    main()
