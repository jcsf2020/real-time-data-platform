CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS observability;
CREATE SCHEMA IF NOT EXISTS ai;

CREATE TABLE IF NOT EXISTS bronze.market_events (
    event_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    price NUMERIC(18, 8) NOT NULL,
    quantity NUMERIC(18, 8) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_topic TEXT NOT NULL,
    raw_payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS observability.pipeline_metrics (
    metric_id BIGSERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai.market_event_embeddings (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES bronze.market_events(event_id),
    content TEXT NOT NULL,
    embedding VECTOR(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.market_event_minute_aggregates (
    symbol TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    event_count BIGINT NOT NULL,
    avg_price NUMERIC(18, 8) NOT NULL,
    total_quantity NUMERIC(18, 8) NOT NULL,
    first_event_timestamp TIMESTAMPTZ NOT NULL,
    last_event_timestamp TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, window_start)
);

CREATE OR REPLACE FUNCTION silver.refresh_market_event_minute_aggregates()
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    affected_rows BIGINT;
BEGIN
    INSERT INTO silver.market_event_minute_aggregates (
        symbol,
        window_start,
        event_count,
        avg_price,
        total_quantity,
        first_event_timestamp,
        last_event_timestamp,
        updated_at
    )
    SELECT
        symbol,
        DATE_TRUNC('minute', event_timestamp) AS window_start,
        COUNT(*) AS event_count,
        AVG(price)::NUMERIC(18, 8) AS avg_price,
        SUM(quantity)::NUMERIC(18, 8) AS total_quantity,
        MIN(event_timestamp) AS first_event_timestamp,
        MAX(event_timestamp) AS last_event_timestamp,
        NOW() AS updated_at
    FROM bronze.market_events
    GROUP BY
        symbol,
        DATE_TRUNC('minute', event_timestamp)
    ON CONFLICT (symbol, window_start)
    DO UPDATE SET
        event_count = EXCLUDED.event_count,
        avg_price = EXCLUDED.avg_price,
        total_quantity = EXCLUDED.total_quantity,
        first_event_timestamp = EXCLUDED.first_event_timestamp,
        last_event_timestamp = EXCLUDED.last_event_timestamp,
        updated_at = NOW();

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows;
END;
$$;

