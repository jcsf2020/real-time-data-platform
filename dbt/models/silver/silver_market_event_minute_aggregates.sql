{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key=['symbol', 'window_start'],
        schema='silver',
        alias='market_event_minute_aggregates'
    )
}}

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
{% if is_incremental() %}
-- Reprocess the trailing 10-minute window from the current high-water mark to
-- pick up late-arriving events without scanning the full bronze table.
-- COALESCE ensures an existing-but-empty target table rebuilds from epoch rather
-- than filtering to zero rows when MAX(window_start) returns NULL.
WHERE DATE_TRUNC('minute', event_timestamp) >= COALESCE(
    (
        SELECT MAX(window_start) - INTERVAL '10 minutes'
        FROM {{ this }}
    ),
    TIMESTAMP '1900-01-01'
)
{% endif %}
GROUP BY
    symbol,
    DATE_TRUNC('minute', event_timestamp)
