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

## Credential contract

**Resolved.** The runtime accepts a full `DATABASE_URL` secret and derives dbt connection
fields from it. Explicit `DBT_POSTGRES_*` env vars override any field parsed from the URL.

On Cloud Run the scaffold keeps `DBT_POSTGRES_HOST=/cloudsql/...` as a plain env var so the
Unix socket mount is used instead of the TCP host embedded in the URL.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | — | Full PostgreSQL URL (`postgresql://user:pw@host:port/db`); fields used as defaults for `DBT_POSTGRES_*` when set |
| `DBT_POSTGRES_HOST` | Yes* | — | PostgreSQL host; overrides host parsed from `DATABASE_URL` |
| `DBT_POSTGRES_PORT` | No | `5432` | PostgreSQL port; overrides port parsed from `DATABASE_URL` |
| `DBT_POSTGRES_USER` | Yes* | — | PostgreSQL user; overrides user parsed from `DATABASE_URL` |
| `DBT_POSTGRES_PASSWORD` | No | `""` | PostgreSQL password (never logged); overrides password parsed from `DATABASE_URL` |
| `DBT_POSTGRES_DBNAME` | Yes* | — | PostgreSQL database name; overrides dbname parsed from `DATABASE_URL` |
| `DBT_TARGET` | No | `cloudsql` | dbt target name in profiles.yml |
| `DBT_PROJECT_DIR` | No | `/app/dbt` | Path to the dbt project directory |
| `DBT_PROFILES_DIR` | No | `/tmp/rtdp-dbt-profiles` | Directory for generated profiles.yml |
| `DBT_REFRESH_MODE` | No | `run-and-test` | One of: compile, run, test, run-and-test |

\* Required unless `DATABASE_URL` provides the value.

---

## Safety

- `dbt/profiles.yml` is never committed to the repository.
- Passwords (whether from `DBT_POSTGRES_PASSWORD` or parsed from `DATABASE_URL`) are never written to logs or stdout.
- The profiles.yml is generated at runtime into `/tmp/rtdp-dbt-profiles/` (outside the repo tree)
  and deleted after the job completes.
- The generated file is on the container filesystem and is not persisted after the container exits.
- `DBT_PROFILES_DIR` must not point inside the repository `dbt/` directory; `_resolve_config` raises `ValueError` if it does.

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

## Cloud Run Job deployment status

**Not yet deployed.** The Terraform scaffold (`infra/terraform/gcp/cloud_run_jobs.tf`) and
deploy workflow (`.github/workflows/deploy-dbt-refresh-cloud-run.yml`) exist but have not
been applied or dispatched.

Credential contract resolved (this branch):
- `DATABASE_URL` secret from `rtdp-database-url` is the credential source.
- Runtime parses `DATABASE_URL` to derive host, port, user, password, dbname.
- `DBT_POSTGRES_HOST=/cloudsql/...` overrides the URL host to use the Cloud SQL Unix socket mount.
- `DBT_POSTGRES_PASSWORD` secret is no longer wired to `rtdp-database-url`.

Still pending (controlled deployment branch):
1. Start Cloud SQL (`NEVER → RUNNABLE`).
2. Dispatch `deploy-dbt-refresh-cloud-run.yml`.
3. Execute the job manually and confirm dbt run + test success in Cloud Logging.
4. Return Cloud SQL to `NEVER / STOPPED`.
5. Document evidence.

Scheduler switch (`rtdp-silver-refresh-scheduler` → `rtdp-dbt-refresh-job`) is a separate
branch after deployment evidence is accepted.

**This branch does not deploy anything and does not mutate GCP.**
