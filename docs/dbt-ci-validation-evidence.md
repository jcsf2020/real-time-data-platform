# dbt CI Validation Evidence

**Status:** DBT CI VALIDATION IMPLEMENTED

---

## Scope

This document records the evidence for the dbt transformation layer implementation and its
CI validation. It covers what was added in PR #104 (local dbt layer) and PR #105 (dbt CI
integration), the model and test coverage, the CI execution path, and the safety controls
maintained throughout.

---

## What PR #104 Added

PR #104 (`feat/dbt-implementation`) introduced the full local dbt transformation layer:

- `dbt/dbt_project.yml` — project config binding silver and gold schema targets
- `dbt/packages.yml` — dbt-utils dependency for composite-key unique tests
- `dbt/profiles.yml.example` — profile template for local/CI configuration
- `dbt/profiles.yml` — intentionally not committed; generated locally or inside CI only
- `dbt/macros/generate_schema_name.sql` — macro preserving `silver`/`gold` schema names
- `dbt/models/sources.yml` — `bronze.market_events` declared as a read-only source
- `dbt/models/silver/silver_market_event_minute_aggregates.sql` — silver table model
- `dbt/models/silver/silver_market_event_minute_aggregates.yml` — schema tests
- `dbt/models/gold/gold_market_event_daily_aggregates.sql` — gold table model
- `dbt/models/gold/gold_market_event_daily_aggregates.yml` — schema tests
- `dbt/tests/assert_gold_price_range.sql` — singular business rule test
- `dbt/README.md` — local execution instructions and coexistence notes

---

## What PR #105 Added

PR #105 (`feat/dbt-ci-validation`) added the `dbt` job to `.github/workflows/ci.yml`:

- A `pgvector/pgvector:pg16` service container (health-checked on `pg_isready`)
- Database initialization from `infra/postgres/init.sql`
- Inline `dbt/profiles.yml` generation in the runner (not committed)
- Sequential execution: `dbt deps → dbt compile → dbt run → dbt test`
- The `dbt` job runs after the existing `validate` job (`needs: validate`)

---

## dbt Model Coverage

### Bronze Source

`dbt/models/sources.yml` declares `bronze.market_events` as a read-only source.
dbt reads from this table but does not write to it — it is populated by the Python
consumer (`ON CONFLICT(event_id) DO NOTHING`).

Source tests defined: `not_null` and `unique` on `event_id`; `not_null` on `symbol`,
`event_type`, `price`, `quantity`, `event_timestamp`; `accepted_values` on `event_type`
(constrained to `['trade']` per the `MarketEvent` contract).

### Silver Minute Aggregate Model

`dbt/models/silver/silver_market_event_minute_aggregates.sql`

Reproduces `silver.refresh_market_event_minute_aggregates()`. Reads `bronze.market_events`,
groups by `(symbol, DATE_TRUNC('minute', event_timestamp))`, materializes as
`silver.market_event_minute_aggregates` (table materialization, `silver` schema).

Schema tests: `not_null` on `symbol`, `window_start`, `event_count`, `avg_price`,
`total_quantity`; composite unique on `(symbol, window_start)` via dbt-utils.

### Gold Daily Aggregate Model

`dbt/models/gold/gold_market_event_daily_aggregates.sql`

Reproduces `gold.refresh_market_event_daily_aggregates()`. Reads `bronze.market_events`
directly (not via silver — daily price extremes require raw event granularity), groups
by `(symbol, event_timestamp::date)`, materializes as `gold.market_event_daily_aggregates`
(table materialization, `gold` schema).

Schema tests: `not_null` on `symbol`, `event_date`, `event_count`, `avg_price`,
`min_price`, `max_price`, `total_quantity`; composite unique on `(symbol, event_date)`.

### Business Rule Test

`dbt/tests/assert_gold_price_range.sql`

Singular test asserting that for every row in `gold.market_event_daily_aggregates`,
`min_price <= avg_price` and `avg_price <= max_price`. Test passes when the query
returns zero rows (no violations).

---

## CI Validation Path

### GitHub Actions CI

The `dbt` job in `.github/workflows/ci.yml` runs on every push to `main` and on pull
requests. It depends on the `validate` job (ruff lint, pytest, import smoke test) and
will not execute if `validate` fails.

### pgvector PostgreSQL Service Container

The `dbt` job spins up an ephemeral `pgvector/pgvector:pg16` service container per run:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    env:
      POSTGRES_USER: rtdp
      POSTGRES_DB: realtime_platform
      POSTGRES_HOST_AUTH_METHOD: trust
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
    ports:
      - 5432:5432
```

The container is isolated to the CI runner — it is not Cloud SQL and does not touch any
GCP resources.

### Temporary profiles.yml Generated in Runner

`dbt/profiles.yml` is generated inline during CI using a heredoc step:

```yaml
rtdp:
  target: ci
  outputs:
    ci:
      type: postgres
      host: "{{ env_var('DBT_POSTGRES_HOST') }}"
      port: "{{ env_var('DBT_POSTGRES_PORT') | int }}"
      user: "{{ env_var('DBT_POSTGRES_USER') }}"
      password: ""
      dbname: "{{ env_var('DBT_POSTGRES_DBNAME') }}"
      schema: public
      threads: 1
```

This file is generated only inside the CI runner and is not committed to the repository.
It is listed in `.gitignore`. No committed `dbt/profiles.yml` exists; the profile is generated locally or inside CI only.

### dbt Execution Steps

The `dbt` CI job runs the following steps in order:

1. Database initialization: `psql -f infra/postgres/init.sql` — creates all medallion
   schemas and stored functions against the ephemeral container.
2. `uv run dbt deps --project-dir dbt --profiles-dir dbt` — installs dbt-utils.
3. `uv run dbt compile --project-dir dbt --profiles-dir dbt` — validates SQL and ref
   resolution with no database writes.
4. `uv run dbt run --project-dir dbt --profiles-dir dbt` — materializes silver and gold
   tables.
5. `uv run dbt test --project-dir dbt --profiles-dir dbt` — runs all schema tests and
   the singular business rule test.

---

## Validation Summary

| Check | Result |
|---|---|
| dbt tests (schema + singular) | 22 passed |
| pytest | 117 passed |
| ruff check | clean |

The 22 dbt tests break down as:
- 9 source tests on `bronze.market_events`
- 6 silver model tests (`not_null` ×5, composite unique ×1)
- 7 gold model tests (`not_null` ×6, composite unique ×1) plus the singular `assert_gold_price_range` test

---

## Safety Notes

| Control | Status |
|---|---|
| No Terraform change | Confirmed — no `.tf` files modified |
| No GCP mutation | Confirmed — dbt CI runs against an ephemeral local container only |
| No Cloud SQL mutation | Confirmed — this branch does not start or modify Cloud SQL |
| No runtime API change | Confirmed — no Python application code modified |
| No `dbt/profiles.yml` committed (CI version) | Confirmed — generated inline in runner only |
| No dbt artifacts committed | Confirmed — `dbt/target/` and `dbt/dbt_packages/` are gitignored |
| Stored functions preserved | Confirmed — `silver.refresh_market_event_minute_aggregates()` and `gold.refresh_market_event_daily_aggregates()` remain in `infra/postgres/init.sql` |

---

## Remaining Gaps

- **Cloud SQL automated dbt execution**: replacing the Cloud Run Job's stored-function
  call with `dbt run --select silver,gold` remains pending. This follows the two-phase
  migration in governance plan section 10: dbt must pass on three consecutive main-branch
  CI builds before the stored functions are removed.
- **Stored functions remain authoritative**: until Cloud SQL automated dbt execution is
  validated, `silver.refresh_market_event_minute_aggregates()` and
  `gold.refresh_market_event_daily_aggregates()` in `infra/postgres/init.sql` are the
  authoritative population mechanism for the silver and gold tables on Cloud SQL.
- **Incremental materialization**: both models use table materialization (full refresh on
  each run). Converting to incremental models merging on `(symbol, window_start)` and
  `(symbol, event_date)` respectively is a planned next step once the table baseline is
  validated through multiple CI runs.
