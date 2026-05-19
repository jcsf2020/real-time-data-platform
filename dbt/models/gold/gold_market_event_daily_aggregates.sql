{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key=['symbol', 'event_date'],
        schema='gold',
        alias='market_event_daily_aggregates'
    )
}}

-- Reproduces gold.refresh_market_event_daily_aggregates() from infra/postgres/init.sql.
-- Aggregates bronze.market_events by (symbol, calendar date).
-- Reads directly from bronze (same as the stored function); the silver minute aggregates
-- are not used here because daily rollups require distinct price extremes from raw events.

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
{% if is_incremental() %}
-- Reprocess the trailing 3-day window from the current high-water mark to
-- pick up late-arriving events without scanning the full bronze table.
-- COALESCE ensures an existing-but-empty target table rebuilds from epoch rather
-- than filtering to zero rows when MAX(event_date) returns NULL.
WHERE event_timestamp::date >= COALESCE(
    (
        SELECT MAX(event_date) - 3
        FROM {{ this }}
    ),
    DATE '1900-01-01'
)
{% endif %}
GROUP BY
    symbol,
    event_timestamp::date
