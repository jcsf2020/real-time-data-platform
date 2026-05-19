# dbt Incremental Gold Model -- Evidence

**Status:** IMPLEMENTED -- LOCAL DISPOSABLE POSTGRES VALIDATION PASSED; CLOUD SQL LIVE EXECUTION NOT YET PROVEN
**Branch:** `feat/dbt-incremental-gold`
**Date:** 2026-05-19

---

## What Changed

| File | Change |
|---|---|
| `dbt/models/gold/gold_market_event_daily_aggregates.sql` | `materialized='table'` -> `materialized='incremental'`; `incremental_strategy='delete+insert'`; `unique_key=['symbol', 'event_date']`; `is_incremental()` WHERE guard added; stale "Next step" comment removed |
| `dbt/models/gold/gold_market_event_daily_aggregates.yml` | Description updated to reflect incremental materialization; `materialized: table` -> `materialized: incremental` in config block |

No other files were modified. `dbt_project.yml` was not changed (the model-level `config()` block overrides the gold-layer project default).

---

## Incremental Strategy

| Property | Value |
|---|---|
| `materialized` | `incremental` |
| `incremental_strategy` | `delete+insert` |
| `unique_key` | `['symbol', 'event_date']` |
| Lookback window | 3 days behind `MAX(event_date)` in the target table; `COALESCE(..., DATE '1900-01-01')` fallback when target is empty |

### Why `delete+insert`

dbt-postgres supports three incremental strategies: `append`, `delete+insert`, and `merge`
(PostgreSQL 15+). `delete+insert` was chosen because:

- It works on all PostgreSQL versions supported by dbt-postgres (>= 9.4), including the
  Cloud SQL PostgreSQL instance used by this project.
- It is explicit and auditable: dbt deletes rows matching `(symbol, event_date)` from the
  target table, then inserts all rows produced by the query for that window.
- The existing dbt test `dbt_utils.unique_combination_of_columns` on `(symbol, event_date)`
  continues to enforce uniqueness after each incremental run.
- Mirrors the strategy already proven for the silver model.

### Why the 3-day lookback

The `is_incremental()` WHERE clause filters to:

```sql
WHERE event_timestamp::date >= COALESCE(
    (
        SELECT MAX(event_date) - 3
        FROM {{ this }}
    ),
    DATE '1900-01-01'
)
```

The gold grain is daily, not sub-minute. Three days was chosen as the lookback because:

- It is wider than the silver 10-minute lookback relative to the aggregation window size,
  providing a proportionally safe buffer for late-arriving daily events (end-of-day
  corrections, delayed event timestamps, or restatements).
- On the first run (or after `--full-refresh`), `is_incremental()` is false and the WHERE
  clause is omitted, so the full bronze table is aggregated to build the baseline.
- If the target table exists but is empty, `MAX(event_date)` returns NULL. Without a fallback,
  `>= NULL` filters to zero rows, silently producing an empty model instead of rebuilding.
  `COALESCE(..., DATE '1900-01-01')` replaces the NULL with an epoch floor, so the filter
  passes all bronze rows and the model rebuilds correctly.

### Note on type safety

`event_date` is of type `DATE` (cast from `event_timestamp::date`). Integer subtraction
(`MAX(event_date) - 3`) returns a `DATE` in PostgreSQL. The COALESCE fallback `DATE '1900-01-01'`
is also `DATE`. Both operands are the same type, and the comparison `event_timestamp::date >= DATE`
is clean. This avoids the `DATE - INTERVAL` -> TIMESTAMP coercion that would require an
explicit `::date` cast.

---

## Why Incremental Gold Matters

### Operational signal

A full-refresh table re-scans and rewrites the entire `bronze.market_events` table on every
dbt run. As the bronze table grows, so does run time and I/O cost, proportionally. An
incremental model decouples run cost from total history size: each run touches only recent
data.

This is the standard production dbt pattern for append-only source tables. The silver model
was already converted to incremental (PR #172). Closing the gold gap completes the incremental
materialization story for the dbt layer.

### B2B portfolio signal

- Demonstrates end-to-end incremental materialization across both silver and gold dbt layers.
- Shows the dbt layer is designed to be schedulable at frequency (daily or sub-daily) without
  increasing cost proportional to total event history.
- Closes the gold incremental gap listed in `docs/EVIDENCE_INDEX.md` (Known Remaining Gaps;
  "gold incremental model" listed as pending as of PR #172).

---

## Validation

Validation was performed against a disposable local `pgvector/pgvector:pg16` container
on host port 15433. The container mirrors the CI ephemeral container exactly: user `rtdp`,
db `realtime_platform`, trust auth, initialized with `infra/postgres/init.sql`. Cloud SQL
was not started. No GCP resources were mutated.

`profiles.yml.example` requires env vars with no defaults. A temporary profiles directory
with hardcoded values targeting the disposable container was used (no real credentials, no
Cloud SQL, no GCP mutation).

### dbt validation

- [x] `uv run dbt deps` -- `dbt_utils` installed; `DBT_DEPS_EXIT=0`
- [x] `uv run dbt parse` -- Jinja + schema valid; `DBT_PARSE_EXIT=0`
- [x] `uv run dbt compile --select gold_market_event_daily_aggregates` -- rendered SQL written to `dbt/target/compiled/`; incremental WHERE guard resolved correctly; `DBT_COMPILE_EXIT=0`
- [x] `uv run dbt run --select gold_market_event_daily_aggregates --full-refresh` -- model created from empty bronze (SELECT 0); `DBT_RUN_FULL_REFRESH_EXIT=0`
- [x] `uv run dbt run --select gold_market_event_daily_aggregates` -- incremental run; `COALESCE` fallback used (empty table -> epoch floor); INSERT 0 0 as expected; `DBT_RUN_INCREMENTAL_EXIT=0`
- [x] `uv run dbt test --select gold_market_event_daily_aggregates` -- all 8 tests pass (unique_combination_of_columns, not_null x5, assert_gold_price_range); `DBT_TEST_EXIT=0`

### Suite validation

- [x] `git diff --check` -- no whitespace errors; `GIT_DIFF_CHECK_EXIT=0`
- [x] `uv run pytest -q` -- 239 passed; `PYTEST_EXIT=0`
- [x] `uv run ruff check .` -- All checks passed; `RUFF_EXIT=0`
- [x] `terraform fmt -check -recursive infra/terraform/gcp` -- `TERRAFORM_FMT_EXIT=0`
- [x] `terraform -chdir=infra/terraform/gcp validate` -- configuration is valid; `TERRAFORM_VALIDATE_EXIT=0`
- [x] `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false` -- No changes; `PLAN_EXIT=0`
- [ ] CI passes on push (`uv run pytest -q` + ruff + dbt compile/run/test against CI ephemeral pgvector:pg16)

---

## What Is NOT Claimed

| Claim | Status |
|---|---|
| Cloud SQL live incremental execution proven | NOT PROVEN -- Cloud SQL is NEVER/STOPPED; no `dbt run` was executed against the live Cloud SQL instance on this branch |
| Production sustained workload validated | NOT CLAIMED -- this is a portfolio platform operating in bounded validation windows |
| 3-day lookback is production-calibrated | NOT PROVEN -- chosen as a pragmatic constant; real tuning requires observed P99 event latency data for daily grain |
| dbt-postgres `merge` strategy used | NOT USED -- `delete+insert` was chosen for cross-version PostgreSQL compatibility |
| Terraform apply executed | NOT EXECUTED -- no `terraform apply` was run; no infrastructure was mutated |
| Dataflow implemented | NOT IMPLEMENTED |
| dbt-specific observability metrics | NOT IMPLEMENTED -- remains a known remaining gap |

---

## Risk and Assumptions

| Risk | Mitigation |
|---|---|
| PostgreSQL version compatibility | `delete+insert` works on all PostgreSQL versions >= 9.4; no version constraint introduced |
| Composite `unique_key` with `delete+insert` | Supported by dbt-core >= 1.0 for `delete+insert` strategy; confirmed by dbt documentation; mirrors silver implementation |
| `updated_at = NOW()` differs across runs | Expected and documented; `updated_at` reflects the dbt run timestamp for rows in the reprocessed window |
| Target table exists but is empty | Without a fallback, `MAX(event_date)` returns NULL and `>= NULL` silently filters to zero rows, producing an empty model. `COALESCE(..., DATE '1900-01-01')` replaces NULL with an epoch floor so the full bronze table is scanned and the model rebuilds correctly. The canonical fix for a persistently empty incremental target is `--full-refresh`; the COALESCE guard prevents a silent zero-row materialisation in the interim. |
| Existing dbt tests remain compatible | The `unique_combination_of_columns` test on `(symbol, event_date)` is unchanged and continues to enforce the incremental key contract; all 8 tests pass |
| Integer date subtraction vs interval | `DATE - 3` returns `DATE` in PostgreSQL; `DATE - INTERVAL '3 days'` returns `TIMESTAMP`. Integer subtraction is used to keep the COALESCE operands both `DATE` and avoid implicit casts. |
