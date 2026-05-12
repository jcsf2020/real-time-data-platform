-- Business rule: for every row in gold.market_event_daily_aggregates,
-- min_price <= avg_price <= max_price must hold.
-- This singular test passes when the query returns zero rows (no violations).

SELECT *
FROM {{ ref('gold_market_event_daily_aggregates') }}
WHERE min_price > avg_price
   OR avg_price > max_price
