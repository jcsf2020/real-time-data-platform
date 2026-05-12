# dbt — Real-Time Data Platform Transformation Layer

This directory contains the dbt project for the Real-Time Data Platform.
It implements the silver and gold transformation models as version-controlled,
testable SQL, replacing the stored functions as the primary transformation
mechanism once CI validation is complete.

---

## Project Structure

```
dbt/
  dbt_project.yml                              # Project config, schema bindings
  packages.yml                                 # dbt-utils for composite-key tests
  profiles.yml                                 # Local Docker Postgres (safe to commit)
  profiles.yml.example                         # Cloud SQL template
  macros/
    generate_schema_name.sql                   # Preserves silver/gold schema names exactly
  models/
    sources.yml                                # bronze.market_events declared as source
    silver/
      silver_market_event_minute_aggregates.sql
      silver_market_event_minute_aggregates.yml
    gold/
      gold_market_event_daily_aggregates.sql
      gold_market_event_daily_aggregates.yml
  tests/
    assert_gold_price_range.sql                # min_price <= avg_price <= max_price
```

---

## Prerequisites

1. Docker Compose stack running: `docker compose up --build -d`
   - PostgreSQL will be available at `localhost:15432`
2. Python environment with dbt installed: `uv sync --all-packages`
3. Local dbt profile created from the example:

```bash
cp dbt/profiles.yml.example dbt/profiles.yml
export DBT_POSTGRES_HOST=localhost
export DBT_POSTGRES_PORT=15432
export DBT_POSTGRES_USER=<local_user>
export DBT_POSTGRES_PASSWORD=<local_password>
export DBT_POSTGRES_DBNAME=<local_database>
```

---

## Running dbt Locally (Docker Postgres)

All commands use `--profiles-dir dbt` to read `dbt/profiles.yml`.
Run from the repository root:

```bash
# 1. Install dbt packages (dbt-utils)
uv run dbt deps --project-dir dbt --profiles-dir dbt

# 2. Verify database connection
uv run dbt debug --project-dir dbt --profiles-dir dbt

# 3. Materialise silver and gold tables
uv run dbt run --project-dir dbt --profiles-dir dbt

# 4. Run schema and business rule tests
uv run dbt test --project-dir dbt --profiles-dir dbt

# 5. Generate documentation catalog
uv run dbt docs generate --project-dir dbt --profiles-dir dbt
uv run dbt docs serve --project-dir dbt --profiles-dir dbt
```

Alternatively, set `DBT_PROFILES_DIR`:

```bash
export DBT_PROFILES_DIR=dbt
uv run dbt run --project-dir dbt
```

### Profile environment variables (optional overrides)

The default `profiles.yml` points to the Docker Compose Postgres. To override:

| Variable              | Default          | Description           |
|-----------------------|------------------|-----------------------|
| `DBT_POSTGRES_HOST`   | `localhost`      | PostgreSQL host       |
| `DBT_POSTGRES_PORT`   | `15432`          | PostgreSQL port       |
| `DBT_POSTGRES_USER`   | required         | Database user         |
| `DBT_POSTGRES_PASSWORD` | required       | Database password     |
| `DBT_POSTGRES_DBNAME` | required         | Database name         |

### Connecting to Cloud SQL

Use the Cloud SQL Auth Proxy and the `cloudsql` target in `profiles.yml.example`.
Copy `profiles.yml.example` to `profiles.yml`, configure the `cloudsql` output,
and run:

```bash
uv run dbt run --target cloudsql --project-dir dbt --profiles-dir dbt
```

Never commit Cloud SQL credentials. Use environment variables or Secret Manager.

---

## Model Descriptions

### `silver_market_event_minute_aggregates`

Reproduces `silver.refresh_market_event_minute_aggregates()`.  
Reads `bronze.market_events`, groups by `(symbol, DATE_TRUNC('minute', event_timestamp))`,
and materializes as `silver.market_event_minute_aggregates`.

Schema tests: `not_null` on `symbol`, `window_start`, `event_count`, `avg_price`,
`total_quantity`; composite unique on `(symbol, window_start)`.

### `gold_market_event_daily_aggregates`

Reproduces `gold.refresh_market_event_daily_aggregates()`.  
Reads `bronze.market_events` directly (not via silver — daily min/max require raw
event granularity), groups by `(symbol, event_timestamp::date)`, and materializes
as `gold.market_event_daily_aggregates`.

Schema tests: `not_null` on key columns; composite unique on `(symbol, event_date)`;
singular business rule test (`assert_gold_price_range`) verifying
`min_price <= avg_price <= max_price`.

---

## What Is Intentionally Not Yet Implemented

| Item | Reason / Next Step |
|---|---|
| Incremental models | Table materialization is used for the first implementation. Convert to incremental with `unique_key: [symbol, window_start]` / `[symbol, event_date]` once the table baseline is validated in CI. |
| CI dbt job | Not added in this PR. Add a `dbt` job to `.github/workflows/ci.yml` after the existing `validate` job: spin up `postgres:16` service, run `dbt deps → dbt compile → dbt test --target ci`. |
| Cloud SQL automated run | Replace the Cloud Run Job's stored-function call with `dbt run --select silver,gold` after dbt CI passes on three consecutive main-branch builds (see governance plan section 10). |
| BigQuery adapter | Out of scope. Use `dbt-bigquery` if the analytical layer migrates to BigQuery. |
| SCD type 2 snapshots | Out of scope for this phase. |
| `ai.market_event_embeddings` | Not managed by dbt; populated by a separate embedding pipeline. |

---

## Coexistence with Stored Functions

The stored functions `silver.refresh_market_event_minute_aggregates()` and
`gold.refresh_market_event_daily_aggregates()` in `infra/postgres/init.sql` remain
**authoritative** until dbt models are validated in CI. Both mechanisms write to the
same physical tables but via different code paths:

- **Stored functions** — the silver function is called by the Cloud Run Job
  (`rtdp-silver-refresh-job`); the gold function is executed on demand via `psql`.
  They use `INSERT … ON CONFLICT … DO UPDATE` (upsert semantics).
- **dbt table models** — recreate the full table on each run (`DROP → CREATE TABLE AS SELECT`).
  Running `dbt run` against a live database **will overwrite** the silver/gold tables.

Do not run `dbt run` against Cloud SQL during the coexistence period unless you are
explicitly executing a controlled migration step per the governance plan
(docs/dbt-transformation-governance-plan.md section 10).

The `assert_gold_price_range` singular test and all schema tests can be run at any time
(`dbt test`) — they are read-only and safe against live data.

---

## Future CI Integration

When ready, add a `dbt` job to `.github/workflows/ci.yml`:

```yaml
dbt:
  name: dbt compile and test
  runs-on: ubuntu-latest
  needs: validate
  services:
    postgres:
      image: postgres:16
      env:
        POSTGRES_USER: rtdp
        POSTGRES_PASSWORD: rtdp
        POSTGRES_DB: realtime_platform
      options: >-
        --health-cmd pg_isready
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
      ports:
        - 5432:5432
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v5
    - run: uv sync --all-packages
    - run: psql "$DATABASE_URL" -f infra/postgres/init.sql
    - run: uv run dbt deps --project-dir dbt --profiles-dir dbt
    - run: uv run dbt compile --project-dir dbt --profiles-dir dbt
    - run: uv run dbt run --project-dir dbt --profiles-dir dbt
    - run: uv run dbt test --project-dir dbt --profiles-dir dbt
```

This is **not yet added** — CI changes are out of scope for this branch per the
implementation constraints.
