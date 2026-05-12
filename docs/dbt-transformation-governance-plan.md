# dbt Transformation Governance Plan

**Status:** PLAN ONLY — dbt is not implemented in this branch.
**Scope:** Documentation and governance design for the next implementation phase.

---

## 1. Purpose

This document defines how dbt should be introduced as the SQL transformation layer for
the Real-Time Data Platform. No dbt code, dependencies, or schema changes are introduced
here. Implementation belongs on a dedicated `feat/dbt-implementation` branch.

---

## 2. Current Transformation State

| Layer | Table | Population Mechanism | Trigger |
|---|---|---|---|
| bronze | `bronze.market_events` | Consumer: `ON CONFLICT(event_id) DO NOTHING` | Real-time, per message |
| silver | `silver.market_event_minute_aggregates` | `silver.refresh_market_event_minute_aggregates()` | Cloud Scheduler / manual |
| gold | `gold.market_event_daily_aggregates` | `gold.refresh_market_event_daily_aggregates()` | Manual / on-demand |

Both refresh functions are defined in `infra/postgres/init.sql`. The silver function is
executed by the Cloud Run Job `rtdp-silver-refresh-job`; the gold function has been
validated through controlled Cloud SQL execution evidence. There is no transformation
framework, no lineage tracking, and no automated data quality tests at the transformation
layer.

---

## 3. Why dbt Is Needed

- **No lineage**: bronze → silver → gold is implicit in stored functions, not a
  machine-readable DAG.
- **No transformation tests**: column nullability, uniqueness, and domain constraints are
  enforced only by the application layer (Pydantic), not at query time.
- **No documentation**: table descriptions exist only in evidence docs, not co-located
  with transformation logic.
- **No incremental strategy**: both functions re-aggregate the full bronze table on every
  run; incremental models reduce compute cost as event volume grows.
- **Difficult change management**: stored functions are applied as raw SQL; dbt provides
  version-controlled, testable, reviewable model files.

---

## 4. Proposed dbt Project Structure

```
dbt/
  dbt_project.yml
  profiles.yml.example            # Cloud SQL template; credentials via env/Secret Manager
  packages.yml                    # dbt-utils for composite-key unique tests
  models/
    sources.yml                   # bronze.market_events declared as source
    silver/
      silver_market_event_minute_aggregates.sql
      silver_market_event_minute_aggregates.yml
    gold/
      gold_market_event_daily_aggregates.sql
      gold_market_event_daily_aggregates.yml
  tests/
    assert_gold_price_range.sql   # business rule: min_price <= avg_price <= max_price
```

Target profile: `postgres` adapter, `realtime_platform` database. Cloud SQL connection
reuses the `DATABASE_URL` secret already managed in Secret Manager.

---

## 5. Model Mapping

### 5.1 Bronze Source

Declared in `models/sources.yml` as a source reference only — bronze is written by the
consumer, not managed by dbt. Columns exposed: `event_id`, `symbol`, `event_type`,
`price`, `quantity`, `event_timestamp`, `ingested_at`, `source_topic`.

### 5.2 Silver Minute Aggregate Model

`models/silver/silver_market_event_minute_aggregates.sql` replaces
`silver.refresh_market_event_minute_aggregates()`. Configured as an incremental model
materialised into `silver.market_event_minute_aggregates`, merging on
`(symbol, window_start)`.

### 5.3 Gold Daily Aggregate Model

`models/gold/gold_market_event_daily_aggregates.sql` replaces
`gold.refresh_market_event_daily_aggregates()`. Configured as an incremental model
materialised into `gold.market_event_daily_aggregates`, merging on
`(symbol, event_date)`.

---

## 6. Tests

### 6.1 Source Tests

| Column | Tests |
|---|---|
| `event_id` | `not_null`, `unique` |
| `symbol` | `not_null` |
| `event_type` | `not_null`, `accepted_values` based on the `MarketEvent` contract |
| `price` | `not_null` |
| `quantity` | `not_null` |
| `event_timestamp` | `not_null` |

### 6.2 Silver Model Tests

| Column | Tests |
|---|---|
| `symbol` | `not_null` |
| `window_start` | `not_null` |
| `(symbol, window_start)` | `unique` (composite via dbt-utils) |
| `event_count` | `not_null` |
| `avg_price` | `not_null` |

### 6.3 Gold Model Tests

| Column | Tests |
|---|---|
| `symbol` | `not_null` |
| `event_date` | `not_null` |
| `(symbol, event_date)` | `unique` (composite via dbt-utils) |
| `event_count` | `not_null` |
| `avg_price`, `min_price`, `max_price` | `not_null` |

### 6.4 Business Rule Test

`tests/assert_gold_price_range.sql` — singular test asserting that for every row in
`gold.market_event_daily_aggregates`, `min_price <= avg_price` and
`avg_price <= max_price`. Test passes when the query returns zero rows.

---

## 7. Documentation and Lineage Expectations

- Every model `.yml` file must include a `description` at model level and for each column.
- `dbt docs generate` must produce a catalog with node lineage:
  `bronze.market_events → silver_market_event_minute_aggregates → gold_market_event_daily_aggregates`.
- Generated `catalog.json` and `manifest.json` are archived as CI artifacts.

---

## 8. Local Execution Plan

```bash
cd dbt/
dbt deps                             # install dbt-utils
dbt debug --profiles-dir .           # confirm database connection
dbt run --profiles-dir .             # materialise silver and gold
dbt test --profiles-dir .            # run schema + business rule tests
dbt docs generate --profiles-dir .   # build catalog and manifest
```

Local development targets the Docker Compose PostgreSQL container at `localhost:15432`.

---

## 9. CI Integration Plan

Add a `dbt` job to `.github/workflows/ci.yml` after the existing `validate` job. The job
spins up a `postgres:16` service container (same credentials as the local stack), runs
`dbt deps → dbt compile → dbt test --target ci`, and uploads `dbt/target/` as an artifact.
dbt tests must pass before any PR can merge to main.

---

## 10. Migration Strategy

The stored functions remain authoritative until dbt models are validated in CI.

1. Implement dbt models on `feat/dbt-implementation`.
2. Run `dbt run` and `dbt test` against a local database seeded with the same data used
   to validate the stored functions.
3. Confirm dbt model output matches stored function output row-for-row.
4. On acceptance, replace the refresh function call in the Cloud Run Job with
   `dbt run --select silver,gold`.
5. Remove both stored functions from `init.sql` only after dbt CI passes on three
   consecutive main-branch builds; update the Cloud Scheduler job description.

The bronze table and consumer write path are not affected.

---

## 11. Out of Scope

- dbt installation or dependencies in this branch.
- BigQuery dbt adapter (`dbt-bigquery`), Dataflow, streaming dbt, and dbt Cloud hosting.
- SCD type 2 snapshot models.
- `ai.market_event_embeddings` — not managed by dbt.
- Automatic deploy-on-merge for dbt runs.

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| dbt model output diverges from stored function | Row-count and sample-row reconciliation before function removal |
| Cloud SQL credentials exposed in CI | Use GitHub Actions secrets; never hardcode in `profiles.yml` |
| Slow dbt install step in CI | Pin `dbt-postgres` version; cache pip dependencies |
| Stored function removed before dbt stabilises | Enforce two-phase rollout: coexist until three clean CI builds pass |
| dbt test failures block silver/gold refresh | Separate `dbt run` (refresh) from `dbt test` (validation) in Cloud Run Job |

---

## 13. Acceptance Criteria for the Implementation Branch

The `feat/dbt-implementation` branch is complete when:

- [ ] `dbt compile` exits 0 with no missing refs or undefined sources.
- [ ] `dbt run` materialises both silver and gold models with row count >= 1.
- [ ] `dbt test` passes all schema tests (not_null, unique, accepted_values) with zero failures.
- [ ] `assert_gold_price_range` singular test returns zero rows.
- [ ] `dbt docs generate` produces a catalog with all three nodes in the lineage DAG.
- [ ] Existing `uv run pytest -q` suite continues to pass without modification.
- [ ] `uv run ruff check .` returns clean.
- [ ] A CI `dbt` job runs on every PR and passes before merge.
- [ ] Migration runbook (section 10) is executed and evidenced in a dedicated evidence doc.
