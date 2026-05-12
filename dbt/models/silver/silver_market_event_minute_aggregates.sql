{{
    config(
        materialized='table',
        schema='silver',
        alias='market_event_minute_aggregates'
    )
}}

-- Reproduces silver.refresh_market_event_minute_aggregates() from infra/postgres/init.sql.
-- Aggregates bronze.market_events by (symbol, minute window).
--
-- Next step: convert to incremental materialization merging on (symbol, window_start)
-- once the table baseline is validated in CI.

SELECT
    symbol,
    DATE_TRUNC('minute', event_timestamp) AS window_start,
    COUNT(*)                              AS event_count,
    AVG(price)::NUMERIC(18, 8)            AS avg_price,
    SUM(quantity)::NUMERIC(18, 8)         AS total_quantity,
    MIN(event_timestamp)                  AS first_event_timestamp,
    MAX(event_timestamp)                  AS last_event_timestamp,
    NOW()                                 AS updated_at
FROM {{ source('bronze', 'market_events') }}
GROUP BY
    symbol,
    DATE_TRUNC('minute', event_timestamp)
