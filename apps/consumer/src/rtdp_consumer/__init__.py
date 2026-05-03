import json
import os
from datetime import UTC, datetime
import psycopg
from kafka import KafkaConsumer
from rtdp_contracts import MarketEvent


TOPIC = "market.events.raw"
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rtdp:rtdp@localhost:15432/realtime_platform",
)

_DEFAULT_SILVER_REFRESH_INTERVAL = 25


def parse_silver_refresh_interval() -> int:
    raw = os.getenv("SILVER_REFRESH_EVERY_N_EVENTS", "")
    try:
        value = int(raw)
        if value >= 1:
            return value
    except (ValueError, TypeError):
        pass
    return _DEFAULT_SILVER_REFRESH_INTERVAL


def log_event(event: dict) -> None:
    print(json.dumps(event, default=str, sort_keys=True))


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


def refresh_silver_minute_aggregates() -> int:
    query = "SELECT silver.refresh_market_event_minute_aggregates() AS affected_rows;"
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0


def main() -> None:
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )

    log_event({"status": "started"})

    processed = 0
    silver_refresh_interval = parse_silver_refresh_interval()

    try:
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

                log_event(
                    {
                        "status": "processed",
                        "event_id": event.event_id,
                        "offset": message.offset,
                        "processing_lag_seconds": round(processing_lag_seconds, 3),
                    }
                )

                if processed % silver_refresh_interval == 0:
                    affected_rows = refresh_silver_minute_aggregates()
                    log_event(
                        {
                            "status": "silver_refreshed",
                            "affected_rows": affected_rows,
                            "processed": processed,
                        }
                    )

            except Exception as exc:
                insert_metric("consumer_errors_total", 1.0)
                log_event({"status": "error", "error": str(exc)})
    except KeyboardInterrupt:
        log_event({"status": "shutting_down"})
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
