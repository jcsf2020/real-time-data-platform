# rtdp-silver-refresh-job

Refreshes the silver minute-aggregate table by invoking the existing PostgreSQL function.

## Why this job exists

The cloud ingestion path (Pub/Sub → Cloud Run worker → Cloud SQL) writes raw events to
`bronze.market_events` but does not automatically materialise the silver layer. This job
fills that gap: it connects to Cloud SQL and calls the aggregate refresh function so that
`silver.market_event_minute_aggregates` stays current.

Locally, the Kafka consumer triggers the same function every 25 events. This job provides
the equivalent trigger for the cloud path, intended to run as a Cloud Run Job (on demand
or via Cloud Scheduler).

## SQL function called

```sql
SELECT silver.refresh_market_event_minute_aggregates();
```

The function already exists in Cloud SQL and is not modified by this package.

## How it fits into the pipeline

```
Pub/Sub → Cloud Run worker → bronze.market_events
                                        ↓
                          rtdp-silver-refresh-job (this package)
                                        ↓
                    silver.market_event_minute_aggregates
```

Run the job after new bronze events land (manually, or later via Cloud Scheduler).

## Usage

```bash
DATABASE_URL="postgresql://user:pass@host/db" uv run rtdp-silver-refresh-job
```

The job emits one structured JSON log line and exits with code 0 on success, 1 on failure.

Example success log:

```json
{
  "component": "silver-refresh",
  "operation": "refresh_market_event_minute_aggregates",
  "processing_time_ms": 42.1,
  "service": "rtdp-silver-refresh-job",
  "status": "ok",
  "timestamp_utc": "2026-05-04T10:00:00.000000+00:00"
}
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | psycopg-compatible PostgreSQL connection string |

The job exits immediately with `status=error` if `DATABASE_URL` is not set. The URL is
never written to logs.

## Implementation status

| Feature | Status |
|---|---|
| Runner logic and structured logging | Implemented and tested |
| Cloud Run Job definition | **Not included in this branch** |
| Cloud Scheduler trigger | **Not included in this branch** |
| Cloud SQL | Stopped (cost control) — no GCP commands executed |

## Docker

This image is intended for a future Cloud Run Job deployment. No deployment is included in this branch.

Build the image from the repository root (the Docker context must be the root so `uv` workspace resolution can see all packages):

```bash
docker build -f apps/silver-refresh-job/Dockerfile -t rtdp-silver-refresh-job .
```

`DATABASE_URL` must be provided at runtime — it is not baked into the image:

```bash
docker run --rm \
  -e DATABASE_URL="postgresql://user:pass@host/db" \
  rtdp-silver-refresh-job
```

## Tests

```bash
uv run pytest tests/test_silver_refresh_job.py -v
```

All tests run without a real database connection.
