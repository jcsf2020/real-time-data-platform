{{
    config(
        materialized='table',
        schema='gold',
        alias='market_event_daily_aggregates'
    )
}}

-- Reproduces gold.refresh_market_event_daily_aggregates() from infra/postgres/init.sql.
-- Aggregates bronze.market_events by (symbol, calendar date).
-- Reads directly from bronze (same as the stored function); the silver minute aggregates
-- are not used here because daily rollups require distinct price extremes from raw events.
--
-- Next step: convert to incremental materialization merging on (symbol, event_date)
-- once the table baseline is validated in CI.

SELECT
    symbol,
    event_timestamp::date            AS event_date,
    COUNT(*)                         AS event_count,
    AVG(price)::NUMERIC(18, 8)       AS avg_price,
    MIN(price)::NUMERIC(18, 8)       AS min_price,
    MAX(price)::NUMERIC(18, 8)       AS max_price,
    SUM(quantity)::NUMERIC(18, 8)    AS total_quantity,
    MIN(event_timestamp)             AS first_event_timestamp,
    MAX(event_timestamp)             AS last_event_timestamp,
    NOW()                            AS updated_at
FROM {{ source('bronze', 'market_events') }}
GROUP BY
    symbol,
    event_timestamp::date
