import json
import os
from datetime import UTC, datetime
import psycopg
from kafka import KafkaConsumer
from rtdp_contracts import MarketEvent


TOPIC = "market.events.raw"
BOOTSTRAP_SERVERS = "localhost:19092"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rtdp:rtdp@localhost:15432/realtime_platform",
)


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
                    "source_topic": TOPIC,
                    "raw_payload": json.dumps(raw_payload),
                },
            )


def insert_metric(metric_name: str, metric_value: float) -> None:
    query = """
        INSERT INTO observability.pipeline_metrics (
            metric_name,
            metric_value
        )
        VALUES (%s, %s);
    """

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (metric_name, metric_value))


def main() -> None:
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )

    print("consumer started...")

    processed = 0

    for message in consumer:
        raw_payload = message.value

        try:
            event = MarketEvent.model_validate(raw_payload)
            insert_bronze_event(event, raw_payload)

            processed += 1
            processing_lag_seconds = (
                datetime.now(UTC) - event.event_timestamp
            ).total_seconds()

            insert_metric("events_processed_total", float(processed))
            insert_metric("latest_processed_offset", float(message.offset))
            insert_metric("processing_lag_seconds", processing_lag_seconds)

            print(
                {
                    "status": "processed",
                    "event_id": event.event_id,
                    "offset": message.offset,
                    "processing_lag_seconds": round(processing_lag_seconds, 3),
                }
            )

        except Exception as exc:
            insert_metric("consumer_errors_total", 1.0)
            print({"status": "error", "error": str(exc)})


if __name__ == "__main__":
    main()
