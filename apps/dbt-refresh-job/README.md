# rtdp-dbt-refresh-job

Runs dbt against Cloud SQL to materialise the silver and gold layers via dbt models.

**Status: NOT DEPLOYED** — This package defines the local runtime and tests for the dbt
refresh path. The Cloud Run Job Terraform resource and deployment workflow are planned for
a separate branch after this local runtime package is accepted.

---

## Why this job exists

The `rtdp-silver-refresh-job` currently calls `silver.refresh_market_event_minute_aggregates()`
directly via psycopg. This package implements the dbt-based alternative: running
`dbt run --select silver,gold` and `dbt test` as the operational refresh path.

dbt output parity with stored functions has been validated (silver 256/256, gold 7/7,
22 dbt tests passed). See `docs/dbt-cloud-sql-validation-evidence.md`.

Stored functions remain the authoritative path until this job is deployed and accepted.

---

## Modes

Controlled via `DBT_REFRESH_MODE`:

| Mode | Steps | Use case |
|---|---|---|
| `run-and-test` | deps → compile → run → test | Default; full operational refresh with compile pre-flight |
| `compile` | deps → compile | Pre-flight SQL resolution check |
| `run` | deps → run | Materialise models only |
| `test` | deps → test | Run data quality tests only |

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DBT_POSTGRES_HOST` | Yes | — | PostgreSQL host |
| `DBT_POSTGRES_PORT` | No | `5432` | PostgreSQL port |
| `DBT_POSTGRES_USER` | Yes | — | PostgreSQL user |
| `DBT_POSTGRES_PASSWORD` | No | `""` | PostgreSQL password (never logged) |
| `DBT_POSTGRES_DBNAME` | Yes | — | PostgreSQL database name |
| `DBT_TARGET` | No | `cloudsql` | dbt target name in profiles.yml |
| `DBT_PROJECT_DIR` | No | `/app/dbt` | Path to the dbt project directory |
| `DBT_PROFILES_DIR` | No | `/tmp/rtdp-dbt-profiles` | Directory for generated profiles.yml |
| `DBT_REFRESH_MODE` | No | `run-and-test` | One of: compile, run, test, run-and-test |

---

## Safety

- `dbt/profiles.yml` is never committed to the repository.
- `DBT_POSTGRES_PASSWORD` is never written to logs or stdout.
- The profiles.yml is generated at runtime into `/tmp/rtdp-dbt-profiles/` (outside the repo tree)
  and deleted after the job completes.
- The generated file is on the container filesystem and is not persisted after the container exits.

---

## Local usage

Requires a running PostgreSQL instance. Uses the Docker Compose Postgres by default.

```bash
# Install workspace
uv sync --all-packages

# Run against local Docker Postgres (must be running)
DBT_POSTGRES_HOST=localhost \
DBT_POSTGRES_PORT=15432 \
DBT_POSTGRES_USER=rtdp \
DBT_POSTGRES_DBNAME=realtime_platform \
DBT_TARGET=local \
DBT_PROJECT_DIR=dbt \
DBT_REFRESH_MODE=run-and-test \
uv run rtdp-dbt-refresh-job
```

Compile-only (no database writes):

```bash
DBT_POSTGRES_HOST=localhost \
DBT_POSTGRES_PORT=15432 \
DBT_POSTGRES_USER=rtdp \
DBT_POSTGRES_DBNAME=realtime_platform \
DBT_TARGET=local \
DBT_PROJECT_DIR=dbt \
DBT_REFRESH_MODE=compile \
uv run rtdp-dbt-refresh-job
```

---

## Structured logs

All log lines are JSON on stdout.

Started:

```json
{
  "component": "dbt-refresh",
  "mode": "run-and-test",
  "operation": "dbt_run_and_test",
  "service": "rtdp-dbt-refresh-job",
  "status": "started",
  "target": "cloudsql",
  "timestamp_utc": "2026-05-13T10:00:00+00:00"
}
```

Step success:

```json
{
  "command": "dbt run",
  "component": "dbt-refresh",
  "duration_ms": 2314.5,
  "mode": "run-and-test",
  "operation": "dbt_run",
  "service": "rtdp-dbt-refresh-job",
  "status": "success",
  "target": "cloudsql",
  "timestamp_utc": "2026-05-13T10:00:02+00:00"
}
```

Completion:

```json
{
  "component": "dbt-refresh",
  "duration_ms": 5100.2,
  "mode": "run-and-test",
  "operation": "dbt_run_and_test",
  "service": "rtdp-dbt-refresh-job",
  "status": "success",
  "target": "cloudsql",
  "timestamp_utc": "2026-05-13T10:00:05+00:00"
}
```

The `command` field logs only the command name (`dbt deps`, `dbt run`, etc.), never a full
command string that could expose path or credential information.

---

## Docker

Build from the repository root (context must be root for uv workspace resolution):

```bash
docker build -f apps/dbt-refresh-job/Dockerfile -t rtdp-dbt-refresh-job .
```

Run against a local Postgres:

```bash
docker run --rm \
  -e DBT_POSTGRES_HOST=host.docker.internal \
  -e DBT_POSTGRES_PORT=15432 \
  -e DBT_POSTGRES_USER=rtdp \
  -e DBT_POSTGRES_DBNAME=realtime_platform \
  -e DBT_TARGET=local \
  rtdp-dbt-refresh-job
```

`DBT_POSTGRES_PASSWORD` is provided at runtime when required by the target database; it is never baked into the image.

---

## Tests

```bash
uv run pytest tests/test_dbt_refresh_job.py -v
```

All tests run without a real database connection (subprocess is mocked).

---

## Future Cloud Run Job deployment

This package will be used in a future branch to create a new Cloud Run Job
(`rtdp-dbt-refresh-job`) with a dedicated Terraform resource and deployment workflow.

That branch will:

1. Add `google_cloud_run_v2_job.rtdp_dbt_refresh_job` to `infra/terraform/gcp/cloud_run_jobs.tf`
2. Update `rtdp-silver-refresh-scheduler` to point to the new job
3. Deploy and run `dbt compile`, `dbt run --select silver,gold`, and `dbt test` against Cloud SQL
4. Confirm API readback and return Cloud SQL to `NEVER / STOPPED`

**This branch does not deploy anything and does not mutate GCP.**
