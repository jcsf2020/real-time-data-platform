# Gold Daily Aggregates -- Local Implementation Evidence

**Branch:** feat/gold-daily-aggregates
**Status:** LOCAL IMPLEMENTATION VALIDATED

---

## Objective

Close the known gap: "Gold analytics layer exists only as an empty schema; no
business-level aggregates are populated."

Implement a minimal gold daily aggregate layer: a table, a refresh function, and a
read API endpoint, validated locally by the full pytest suite.

---

## What Changed

- Added `gold.market_event_daily_aggregates` table to `infra/postgres/init.sql`.
- Added `gold.refresh_market_event_daily_aggregates()` function that aggregates from
  `bronze.market_events` by symbol and calendar date, and upserts results using
  `ON CONFLICT (symbol, event_date)`.
- Added `GET /aggregates/daily` endpoint to the FastAPI serving layer.
- Added `tests/test_api_daily_aggregates.py` to validate the new endpoint.

---

## Files Changed

| File | Change |
|---|---|
| `infra/postgres/init.sql` | Added gold table and gold refresh function |
| `apps/api/src/rtdp_api/__init__.py` | Added `/aggregates/daily` endpoint |
| `tests/test_api_daily_aggregates.py` | New test file mirroring minute aggregate test style |
| `docs/gold-daily-aggregates-evidence.md` | This document |
| `docs/EVIDENCE_INDEX.md` | Minimal reference added |
| `docs/ARCHITECTURE_REVIEW.md` | Data model and known gaps sections updated |
| `README.md` | Minimal pointer added to new endpoint and gold layer status |

---

## Validation

All validation was performed locally. No GCP resources were accessed or modified.

```
uv run pytest -q
```

Expected: full test suite passes including `test_api_daily_aggregates.py`.

```
uv run ruff check .
```

Expected: no lint errors.

Internal language check was performed against the files changed by this branch.

---

## New Table

`gold.market_event_daily_aggregates`

| Column | Type | Notes |
|---|---|---|
| symbol | TEXT NOT NULL | |
| event_date | DATE NOT NULL | |
| event_count | BIGINT NOT NULL | |
| avg_price | NUMERIC(18, 8) NOT NULL | |
| min_price | NUMERIC(18, 8) NOT NULL | |
| max_price | NUMERIC(18, 8) NOT NULL | |
| total_quantity | NUMERIC(18, 8) NOT NULL | |
| first_event_timestamp | TIMESTAMPTZ NOT NULL | |
| last_event_timestamp | TIMESTAMPTZ NOT NULL | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |

Primary key: `(symbol, event_date)`

---

## New Function

`gold.refresh_market_event_daily_aggregates() RETURNS BIGINT`

- Aggregates from `bronze.market_events` grouped by `symbol` and `event_timestamp::date`.
- Upserts using `ON CONFLICT (symbol, event_date) DO UPDATE`.
- Returns the number of affected rows via `GET DIAGNOSTICS`.
- Does not alter the silver table or silver function.

---

## New Endpoint

`GET /aggregates/daily`

- Default limit: 20. Range: 1--200.
- Queries `gold.market_event_daily_aggregates`.
- Orders by `event_date DESC, symbol`.
- Returns: symbol, event_date, event_count, avg_price, min_price, max_price,
  total_quantity, first_event_timestamp, last_event_timestamp, updated_at.

---

## Safety Constraints

- Terraform not modified.
- GitHub Actions workflows not modified.
- Dockerfiles not modified.
- No GCP resources accessed or mutated.
- `terraform apply` not run.
- Existing endpoints unchanged; `/aggregates/minute` behavior is unaffected.
- Existing silver table and function unmodified.

---

## Gap Closed

The gold schema now contains a populated table definition and a callable refresh
function. The API exposes the data through `/aggregates/daily`. The test suite
validates the endpoint against the gold schema without a live database.

---

## Known Limitation

This implementation is validated locally only. The `gold.market_event_daily_aggregates`
table and `gold.refresh_market_event_daily_aggregates()` function will take effect on
the local PostgreSQL container when `infra/postgres/init.sql` is applied (e.g., on
`docker compose up --build`). Cloud SQL deployment evidence is not yet captured; the
production Cloud SQL instance remains `NEVER / STOPPED`.
