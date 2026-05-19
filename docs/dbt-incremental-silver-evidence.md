# dbt Incremental Silver Model — Evidence

**Status:** IMPLEMENTED — LOCAL CODE CHANGE ONLY; LIVE CLOUD SQL EXECUTION NOT YET PROVEN
**Branch:** `feat/dbt-incremental-silver`
**Date:** 2026-05-19

---

## What Changed

| File | Change |
|---|---|
| `dbt/models/silver/silver_market_event_minute_aggregates.sql` | `materialized='table'` → `materialized='incremental'`; `incremental_strategy='delete+insert'`; `unique_key=['symbol', 'window_start']`; `is_incremental()` WHERE guard added |
| `dbt/models/silver/silver_market_event_minute_aggregates.yml` | Description updated to reflect incremental materialization; `materialized: table` → `materialized: incremental` in config block |

No other files were modified. `dbt_project.yml` was not changed (the model-level `config()` block overrides the silver-layer project default).

---

## Incremental Strategy

| Property | Value |
|---|---|
| `materialized` | `incremental` |
| `incremental_strategy` | `delete+insert` |
| `unique_key` | `['symbol', 'window_start']` |
| Lookback window | 10 minutes behind `MAX(window_start)` in the target table; `COALESCE(..., TIMESTAMP '1900-01-01')` fallback when target is empty |

### Why `delete+insert`

dbt-postgres supports three incremental strategies: `append`, `delete+insert`, and `merge`
(PostgreSQL 15+). `delete+insert` was chosen because:

- It works on all PostgreSQL versions supported by dbt-postgres (≥ 9.4), including the
  Cloud SQL PostgreSQL instance used by this project.
- It is explicit and auditable: dbt deletes rows matching `(symbol, window_start)` from the
  target table, then inserts all rows produced by the query for that window. No hidden MERGE
  semantics.
- The existing dbt test `dbt_utils.unique_combination_of_columns` on `(symbol, window_start)`
  continues to enforce uniqueness after each incremental run.

### Why the 10-minute lookback

The `is_incremental()` WHERE clause filters to:

```sql
WHERE DATE_TRUNC('minute', event_timestamp) >= COALESCE(
    (
        SELECT MAX(window_start) - INTERVAL '10 minutes'
        FROM {{ this }}
    ),
    TIMESTAMP '1900-01-01'
)
```

This reprocesses the trailing 10 windows from the current high-water mark on every
incremental run. The rationale:

- Late-arriving events (clock skew, consumer retries) that fall within the last few minutes
  of the current high-water mark are picked up without a full-refresh.
- 10 minutes is a pragmatic, production-like constant. A real platform with measurable event
  latency distribution would tune this based on observed P99 latency.
- On the first run (or after `--full-refresh`), `is_incremental()` is false and the WHERE
  clause is omitted, so the full bronze table is aggregated to build the baseline.
- If the target table exists but is empty (e.g. a fresh incremental target with no prior
  rows), `MAX(window_start)` returns NULL. Without a fallback, `>= NULL` filters to zero
  rows, silently producing an empty model instead of rebuilding. `COALESCE(...,
  TIMESTAMP '1900-01-01')` replaces the NULL with an epoch floor, so the filter passes all
  bronze rows and the model rebuilds correctly. The correct fix for a persistently empty
  target is `--full-refresh`, but the COALESCE guard prevents a silent zero-row materialisation
  in the meantime.

---

## Why Incremental Materialization Matters

### Operational signal

A full-refresh table re-scans and rewrites the entire `bronze.market_events` table on every
dbt run. As the bronze table grows, so does run time and I/O cost, proportionally. An
incremental model decouples run cost from total history size: each run touches only recent
data.

This is the standard production dbt pattern for append-only source tables. A senior data
engineer hiring manager expects to see incremental models in a portfolio platform, not
permanent full-refresh.

### B2B portfolio signal

- Demonstrates awareness of operational efficiency at scale, not just functional correctness.
- Shows that the dbt layer is designed to be schedulable at frequency (hourly or sub-hourly)
  without increasing cost proportional to total event history.
- Closes the incremental materialization gap listed in `docs/gaps-resolved-vs-remaining-report.md`
  (Gap #7, B2B Value: Medium, Risk: Low).

---

## Validation Checklist

All dbt commands (deps, parse, compile, run, test) require a live PostgreSQL instance.
A disposable local `pgvector/pgvector:pg16` container is sufficient; Cloud SQL is not
required and was not started. The container mirrors the CI ephemeral container exactly:
user `rtdp`, db `realtime_platform`, trust auth, initialized with `infra/postgres/init.sql`.

`profiles.yml.example` requires env vars with no defaults. The validation uses a temporary
profiles.yml with hardcoded values targeting the disposable container (no real credentials,
no Cloud SQL, no GCP mutation).

- [x] `uv run dbt deps` — `dbt_utils` installed; `DBT_DEPS_EXIT=0`
- [x] `uv run dbt parse` — Jinja + schema valid; `DBT_PARSE_EXIT=0`
- [x] `uv run dbt compile --select silver_market_event_minute_aggregates` — rendered SQL written to `dbt/target/compiled/`; `DBT_COMPILE_EXIT=0`
- [x] `uv run dbt run --select silver_market_event_minute_aggregates --full-refresh` — model created from empty bronze; `DBT_RUN_FULL_REFRESH_EXIT=0`
- [x] `uv run dbt run --select silver_market_event_minute_aggregates` — incremental run; `COALESCE` fallback used (empty table → epoch floor); `DBT_RUN_INCREMENTAL_EXIT=0`
- [x] `uv run dbt test --select silver_market_event_minute_aggregates` — all `unique_combination_of_columns` and `not_null` tests pass; `DBT_TEST_EXIT=0`
- [ ] CI passes on push (`uv run pytest -q` + ruff + dbt compile/run/test against CI ephemeral pgvector:pg16)

---

## What Is NOT Claimed

| Claim | Status |
|---|---|
| Gold model converted to incremental | NOT DONE — `gold_market_event_daily_aggregates` remains `materialized='table'`; gold incremental is a separate future branch |
| Cloud SQL live incremental execution proven | NOT PROVEN — Cloud SQL is NEVER/STOPPED; no `dbt run` was executed against the live Cloud SQL instance on this branch |
| Production sustained workload validated | NOT CLAIMED — this is a portfolio platform operating in bounded validation windows |
| 10-minute lookback is production-calibrated | NOT PROVEN — chosen as a pragmatic constant; real tuning requires observed P99 event latency data |
| dbt-postgres `merge` strategy used | NOT USED — `delete+insert` was chosen for cross-version PostgreSQL compatibility |

---

## Risk and Assumptions

| Risk | Mitigation |
|---|---|
| PostgreSQL version compatibility | `delete+insert` works on all PostgreSQL versions ≥ 9.4; no version constraint introduced |
| Composite `unique_key` with `delete+insert` | Supported by dbt-core ≥ 1.0 for `delete+insert` strategy; confirmed by dbt documentation |
| `updated_at = NOW()` differs across runs | Expected and documented; `updated_at` reflects the dbt run timestamp for rows in the reprocessed window, not the event timestamp |
| Target table exists but is empty | Without a fallback, `MAX(window_start)` returns NULL and `>= NULL` silently filters to zero rows, producing an empty model. `COALESCE(..., TIMESTAMP '1900-01-01')` replaces NULL with an epoch floor so the full bronze table is scanned and the model rebuilds correctly. The canonical fix for a persistently empty incremental target is `--full-refresh`; the COALESCE guard prevents a silent zero-row materialisation in the interim. |
| Existing dbt tests remain compatible | The `unique_combination_of_columns` test on `(symbol, window_start)` is unchanged and continues to enforce the incremental key contract |
