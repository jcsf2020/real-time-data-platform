# Silver Refresh Error Metric Filter — Validation Evidence

**Status:** VALIDATED
**Date:** 2026-05-06
**Branch:** `exec/silver-refresh-error-metric-filter-validation`
**Runbook:** [docs/silver-refresh-error-metric-filter-runbook.md](silver-refresh-error-metric-filter-runbook.md)

---

## Executive Summary

- The `silver_refresh_error_count` logs-based metric filter was safely updated to remove the hardcoded `resource.labels.job_name="rtdp-silver-refresh-job"` condition.
- A temporary isolated Cloud Run Job (`rtdp-silver-refresh-job-error-test`) was created without `DATABASE_URL`, executed, confirmed to fail with exit code 1, and emitted the expected structured `EnvironmentError` log.
- Cloud Monitoring returned one timeSeries with `TOTAL=1` — `SILVER_ERROR_DATAPOINT_VALIDATED: True`.
- The temporary job was deleted. Cloud SQL remained `NEVER / STOPPED` throughout.
- All four logs-based metrics now have validated Cloud Monitoring timeSeries datapoints.

---

## Problem and Root Cause

The previous validation cycle ([docs/isolated-error-counter-validation-evidence.md](isolated-error-counter-validation-evidence.md)) established:

- The temporary isolated job emitted a correctly structured error log with `resource.labels.job_name="rtdp-silver-refresh-job-error-test"`.
- The metric filter hardcoded `resource.labels.job_name="rtdp-silver-refresh-job"` — an exact string match against the production job name.
- Cloud Run sets `resource.labels.job_name` from the job's own name at infrastructure level; the container cannot override it.
- Because the temporary job must use a different name to avoid mutating the production job, the log was excluded and no timeSeries datapoint was produced.

---

## Old Metric Filter (Before This Branch)

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"
```

---

## New Metric Filter (After This Branch)

```
resource.type="cloud_run_job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"
```

`resource.labels.job_name` is absent.

---

## Why Removing `resource.labels.job_name` Was Safe

`jsonPayload.service` is emitted by the application container itself, hardcoded to `"rtdp-silver-refresh-job"` in the source code. It does not change based on which Cloud Run job name executes the container. The four retained conditions are sufficient to uniquely identify silver refresh error events across all Cloud Run Jobs in the project:

| Condition | Set by | Role |
|---|---|---|
| `resource.type="cloud_run_job"` | Cloud Run infrastructure | Scopes to Cloud Run Jobs only |
| `jsonPayload.service="rtdp-silver-refresh-job"` | Application code | Identifies the silver refresh service |
| `jsonPayload.operation="refresh_market_event_minute_aggregates"` | Application code | Identifies the specific operation |
| `jsonPayload.status="error"` | Application code | Scopes to error-path logs only |

No other Cloud Run Job in the project emits `jsonPayload.service="rtdp-silver-refresh-job"` with `jsonPayload.operation="refresh_market_event_minute_aggregates"`.

---

## Pre-Execution Checks

All gates passed before any GCP write:

| Check | Result |
|---|---|
| Branch | `exec/silver-refresh-error-metric-filter-validation` |
| `uv sync --all-packages` | Succeeded |
| `uv run pytest -q` | 116 passed, 0 failed |
| `uv run ruff check .` | All checks passed |
| Cloud SQL state | `NEVER / STOPPED` |

---

## GCP Metric Update Evidence

### Update Command Executed

```bash
gcloud logging metrics update silver_refresh_error_count \
  --project=project-42987e01-2123-446b-ac7 \
  --log-filter='resource.type="cloud_run_job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"'
```

### Update Output

```
Updated [silver_refresh_error_count].
```

### Post-Update Filter Verification

| Assertion | Result |
|---|---|
| `resource.labels.job_name` absent from filter | **True** |
| `resource.type="cloud_run_job"` present | **True** |
| `jsonPayload.service="rtdp-silver-refresh-job"` present | **True** |
| `jsonPayload.operation="refresh_market_event_minute_aggregates"` present | **True** |
| `jsonPayload.status="error"` present | **True** |

---

## Temporary Job Validation Evidence

### Production Job Image Inspected

```
europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest
```

### Temporary Job Created

```bash
gcloud run jobs create rtdp-silver-refresh-job-error-test \
  --image=europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --max-retries=0 \
  --task-timeout=60s
```

Output:

```
Job [rtdp-silver-refresh-job-error-test] has successfully been created.
```

### Temporary Job Safety Verification

| Property | Value |
|---|---|
| JOB_NAME | `rtdp-silver-refresh-job-error-test` |
| IMAGE | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest` |
| ENV_VARS | `[]` |
| HAS_DATABASE_URL | `False` |
| SAFE | `DATABASE_URL absent` |

### Temporary Job Executed

```bash
gcloud run jobs execute rtdp-silver-refresh-job-error-test \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --wait
```

| Property | Value |
|---|---|
| Execution name | `rtdp-silver-refresh-job-error-test-k68kp` |
| Exit code | `1` |
| Reason | Container exited with an error |
| Task | `rtdp-silver-refresh-job-error-test-k68kp-task0` |

Failure was expected — `DATABASE_URL` was intentionally absent to trigger the error path.

---

## Structured Error Log Evidence

Cloud Logging entry matching the updated metric filter:

| Field | Value |
|---|---|
| `insertId` | `69fb17b000081acaa80baa3e` |
| `resource.type` | `cloud_run_job` |
| `resource.labels.job_name` | `rtdp-silver-refresh-job-error-test` |
| `resource.labels.location` | `europe-west1` |
| `resource.labels.project_id` | `project-42987e01-2123-446b-ac7` |
| `jsonPayload.component` | `silver-refresh` |
| `jsonPayload.service` | `rtdp-silver-refresh-job` |
| `jsonPayload.operation` | `refresh_market_event_minute_aggregates` |
| `jsonPayload.status` | `error` |
| `jsonPayload.error_type` | `EnvironmentError` |
| `jsonPayload.error_message` | `DATABASE_URL environment variable is not set` |
| `jsonPayload.processing_time_ms` | `0` |
| `jsonPayload.timestamp_utc` | `2026-05-06T10:28:00.528361+00:00` |
| `run.googleapis.com/execution_name` | `rtdp-silver-refresh-job-error-test-k68kp` |
| `run.googleapis.com/task_attempt` | `0` |
| `run.googleapis.com/task_index` | `0` |

---

## Cloud Monitoring timeSeries Evidence

Query: `logging.googleapis.com/user/silver_refresh_error_count`

```
TIME_SERIES_COUNT: 1
metric:   logging.googleapis.com/user/silver_refresh_error_count
resource: cloud_run_job {
  location:   europe-west1
  job_name:   rtdp-silver-refresh-job-error-test
  project_id: project-42987e01-2123-446b-ac7
}
```

Datapoints:

| Window start (UTC) | Window end (UTC) | Count |
|---|---|---|
| 2026-05-06T10:27:58Z | 2026-05-06T10:28:58Z | **1** |
| 2026-05-06T10:26:58Z | 2026-05-06T10:27:58Z | 0 |
| 2026-05-06T10:28:58Z | 2026-05-06T10:29:58Z | 0 |
| 2026-05-06T10:29:58Z | 2026-05-06T10:30:58Z | 0 |

| Summary field | Value |
|---|---|
| POINTS | 4 |
| TOTAL | 1 |
| SILVER_ERROR_DATAPOINT_VALIDATED | **True** |

---

## Cleanup Evidence

### Temporary Job Deleted

```bash
gcloud run jobs delete rtdp-silver-refresh-job-error-test \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --quiet
```

Output:

```
Deleted job [rtdp-silver-refresh-job-error-test].
```

### Final Cloud Run Job List

| JOB |
|---|
| `rtdp-silver-refresh-job` |

`rtdp-silver-refresh-job-error-test` is absent.

### Final Cloud SQL State

```
NEVER   STOPPED
```

---

## Acceptance Matrix

| Criterion | Status |
|---|---|
| Metric filter updated — `resource.labels.job_name` absent | **ACCEPTED** |
| All four retained conditions present in new filter | **ACCEPTED** |
| `HAS_DATABASE_URL: False` on temporary job | **ACCEPTED** |
| Temporary job failed with exit code 1 | **ACCEPTED** |
| Failure reason: `DATABASE_URL environment variable is not set` | **ACCEPTED** |
| Structured `EnvironmentError` log found in Cloud Logging | **ACCEPTED** |
| Cloud Monitoring timeSeries — at least one `int64Value > 0` | **ACCEPTED** (`TOTAL=1`) |
| Temporary job deleted — not in `gcloud run jobs list` | **ACCEPTED** |
| Cloud SQL `NEVER / STOPPED` throughout | **ACCEPTED** |
| 116 tests passed | **ACCEPTED** |
| Ruff clean | **ACCEPTED** |

All criteria met. Evidence status: **VALIDATED**.

---

## What This Evidence Proves

- The updated `silver_refresh_error_count` metric filter correctly matches error logs emitted by any Cloud Run Job running the silver refresh container — not only the production job named `rtdp-silver-refresh-job`.
- `silver_refresh_error_count` now has a confirmed Cloud Monitoring timeSeries datapoint (`int64Value=1` at `2026-05-06T10:27:58Z–10:28:58Z`).
- All four logs-based metrics now have validated Cloud Monitoring timeSeries datapoints:
  - `worker_message_processed_count` — validated (load test, TOTAL=1000)
  - `worker_message_error_count` — validated (isolated DLQ test, TOTAL=13)
  - `silver_refresh_success_count` — validated (single-event test, int64Value=1)
  - `silver_refresh_error_count` — **validated on this branch** (TOTAL=1)
- The production `rtdp-silver-refresh-job` definition was not mutated.
- Cloud SQL was not started.

---

## What This Evidence Does Not Claim

- Does not claim alert policies are configured (none exist).
- Does not claim the production push subscription has a dead-letter policy (it does not).
- Does not claim resources are managed by Terraform or IaC.
- Does not claim Cloud Scheduler triggers the silver refresh job automatically.
- Does not claim BigQuery or Dataflow integration is implemented.
- Does not claim 5,000-event scale throughput has been validated.
- Does not claim the production Cloud Run Job definition was changed in any way.

---

## Remaining Gaps After This Validation

| Gap | Priority | Notes |
|---|---|---|
| Production Pub/Sub DLQ | P0 | `market-events-raw-worker-push` has no `deadLetterPolicy`; malformed messages cause unbounded retries |
| Alert policies | P0 | No Cloud Monitoring alert on any metric; no notification for error spikes |
| Cloud Scheduler for silver refresh | P1 | Silver refresh is only triggered manually; no recurring execution |
| Terraform / IaC | P1 | All GCP resources were created imperatively; no Terraform state |
| BigQuery / Dataflow | P1 | Analytical tier not implemented; silver layer is operational only |
| 5,000-event load test | P1 | Load test plan exists; 100 and 1,000 tiers passed; 5,000 tier not executed |
