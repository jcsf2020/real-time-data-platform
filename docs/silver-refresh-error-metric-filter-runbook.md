# Silver Refresh Error Metric Filter — Fix Runbook

**Status:** PENDING EXECUTION
**Branch:** `fix/silver-refresh-error-metric-filter`
**Preceded by:** [docs/isolated-error-counter-validation-evidence.md](isolated-error-counter-validation-evidence.md)

---

## Purpose

Safely update the `silver_refresh_error_count` logs-based metric filter so that an isolated temporary Cloud Run Job — with a different `job_name` than the production job — can produce a matching Cloud Monitoring timeSeries datapoint.

This runbook does not touch application code, production Cloud Run Job definitions, Cloud SQL, Pub/Sub, or alert policies.

---

## Current Failure Mode

The `silver_refresh_error_count` logs-based metric filter currently hardcodes:

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"
```

When the isolated temporary job `rtdp-silver-refresh-job-error-test` was executed in the previous validation cycle, it emitted a correctly structured error log:

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job-error-test"   ← set by Cloud Run, not the app
jsonPayload.service="rtdp-silver-refresh-job"                   ← set by application code
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"
```

Because `resource.labels.job_name` is set by Cloud Run infrastructure from the job name at execution time, the temporary job — which must have a different name to avoid mutating the production job — cannot match an exact `job_name` filter that hardcodes `"rtdp-silver-refresh-job"`. Cloud Monitoring returned zero timeSeries datapoints despite a valid structured log.

---

## Why Removing `resource.labels.job_name` Is Safe

The remaining three conditions are sufficient to uniquely identify silver refresh error events:

| Condition | Set by | Meaning |
|---|---|---|
| `resource.type="cloud_run_job"` | Cloud Run infrastructure | Scopes to Cloud Run Jobs only (not Cloud Run Services) |
| `jsonPayload.service="rtdp-silver-refresh-job"` | Application code (hardcoded) | Identifies the silver refresh application regardless of job name |
| `jsonPayload.operation="refresh_market_event_minute_aggregates"` | Application code (hardcoded) | Identifies the specific operation within the service |
| `jsonPayload.status="error"` | Application code | Scopes to error-path logs only |

`jsonPayload.service` is emitted by the application container itself — it is set to the string literal `"rtdp-silver-refresh-job"` in the source code and does not change based on which Cloud Run job name is used to execute the container. This provides equivalent selectivity to `resource.labels.job_name` for the purpose of metric filtering, while allowing isolated temporary jobs to match.

No other Cloud Run Job in the project emits `jsonPayload.service="rtdp-silver-refresh-job"` with `jsonPayload.operation="refresh_market_event_minute_aggregates"`.

---

## Proposed New Filter

```
resource.type="cloud_run_job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"
```

The only change from the current filter is the removal of the `resource.labels.job_name="rtdp-silver-refresh-job"` line.

---

## Pre-Execution Checks

All of the following must pass before any GCP write is performed.

### 1. Branch and code quality

```bash
git status --short --branch
uv sync --all-packages
uv run pytest -q
uv run ruff check .
```

Expected:
- Branch: `fix/silver-refresh-error-metric-filter`
- 116 tests passed
- Ruff: all checks passed

### 2. Cloud SQL state

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER` and `STOPPED` (two values on separate lines, or `NEVER	STOPPED`).

**Stop if Cloud SQL is not `NEVER / STOPPED`.**

### 3. Current metric filter

```bash
gcloud logging metrics describe silver_refresh_error_count \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

Expected: the `filter` field contains `resource.labels.job_name="rtdp-silver-refresh-job"`. Record the full current filter as baseline evidence before any update.

---

## Step 1: Update the Metric Filter

### Command (FUTURE EXECUTION — do not run until all pre-execution checks pass)

```bash
gcloud logging metrics update silver_refresh_error_count \
  --project=project-42987e01-2123-446b-ac7 \
  --log-filter='resource.type="cloud_run_job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"'
```

### Post-update verification

```bash
gcloud logging metrics describe silver_refresh_error_count \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

Assert all of the following before continuing:

| Assertion | Expected |
|---|---|
| `resource.labels.job_name` absent from filter | True |
| `resource.type="cloud_run_job"` present | True |
| `jsonPayload.service="rtdp-silver-refresh-job"` present | True |
| `jsonPayload.operation="refresh_market_event_minute_aggregates"` present | True |
| `jsonPayload.status="error"` present | True |

**Stop if any assertion fails. Do not continue to the isolated job step.**

---

## Step 2: Isolated Temporary Job Validation

### 2.1 Inspect production job image

```bash
gcloud run jobs describe rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(spec.template.spec.template.spec.containers[0].image)"
```

Record the image URI. Use this same image for the temporary job.

### 2.2 Create temporary job without DATABASE_URL

```bash
gcloud run jobs create rtdp-silver-refresh-job-error-test \
  --image=<IMAGE_FROM_STEP_2_1> \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --max-retries=0 \
  --task-timeout=60s
```

**Do not add `DATABASE_URL` or any Secret Manager bindings. The absence of `DATABASE_URL` is the mechanism that triggers the error path.**

Verify the created job has no `DATABASE_URL` environment variable:

```bash
gcloud run jobs describe rtdp-silver-refresh-job-error-test \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json | python3 -c "
import json, sys
job = json.load(sys.stdin)
containers = job['spec']['template']['spec']['template']['spec']['containers']
env_vars = containers[0].get('env', [])
print('ENV VARS:', [e['name'] for e in env_vars])
has_db_url = any(e['name'] == 'DATABASE_URL' for e in env_vars)
print('HAS_DATABASE_URL:', has_db_url)
assert not has_db_url, 'STOP: DATABASE_URL must not be present'
print('SAFE: DATABASE_URL absent')
"
```

**Stop if `HAS_DATABASE_URL` is True.**

### 2.3 Execute temporary job

```bash
gcloud run jobs execute rtdp-silver-refresh-job-error-test \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --wait
```

Expected: execution fails with exit code 1. Record the execution name (e.g. `rtdp-silver-refresh-job-error-test-XXXXX`).

**If the job succeeds (exit code 0), stop immediately. This would indicate DATABASE_URL is present somehow, which must not be the case.**

### 2.4 Verify structured error log in Cloud Logging

```bash
gcloud logging read \
  'resource.type="cloud_run_job"
   resource.labels.job_name="rtdp-silver-refresh-job-error-test"
   jsonPayload.status="error"
   jsonPayload.operation="refresh_market_event_minute_aggregates"' \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=5 \
  --format=json
```

Expected log fields:

| Field | Expected value |
|---|---|
| `resource.type` | `cloud_run_job` |
| `resource.labels.job_name` | `rtdp-silver-refresh-job-error-test` |
| `jsonPayload.service` | `rtdp-silver-refresh-job` |
| `jsonPayload.operation` | `refresh_market_event_minute_aggregates` |
| `jsonPayload.status` | `error` |
| `jsonPayload.error_type` | `EnvironmentError` |
| `jsonPayload.error_message` | `DATABASE_URL environment variable is not set` |

**Stop if the log is not found or if any expected field is missing.**

### 2.5 Wait for Cloud Monitoring propagation

Cloud Monitoring logs-based metric propagation typically takes 60–120 seconds after the log entry is ingested.

```bash
sleep 90
```

### 2.6 Query Cloud Monitoring timeSeries

```bash
PROJECT_NUMBER=892892382088
ACCESS_TOKEN=$(gcloud auth print-access-token)

curl -s \
  "https://monitoring.googleapis.com/v3/projects/${PROJECT_NUMBER}/timeSeries?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fsilver_refresh_error_count%22&interval.startTime=$(date -u -v-10M +%Y-%m-%dT%H:%M:%SZ)&interval.endTime=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ts_list = data.get('timeSeries', [])
print('TIME_SERIES_COUNT:', len(ts_list))
total = 0
for ts in ts_list:
    for pt in ts.get('points', []):
        val = pt['value'].get('int64Value', 0)
        total += int(val)
        print('  interval:', pt['interval'], 'value:', val)
print('TOTAL:', total)
print('SILVER_ERROR_DATAPOINT_VALIDATED:', total > 0)
assert total > 0, 'STOP: no timeSeries datapoints found — validation failed'
"
```

Expected: at least one point with `int64Value > 0` and `SILVER_ERROR_DATAPOINT_VALIDATED: True`.

**Stop if `SILVER_ERROR_DATAPOINT_VALIDATED: False`. Do not mark the runbook as accepted.**

---

## Step 3: Cleanup

### 3.1 Delete temporary job

```bash
gcloud run jobs delete rtdp-silver-refresh-job-error-test \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --quiet
```

### 3.2 Verify only production job remains

```bash
gcloud run jobs list \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

Expected: only `rtdp-silver-refresh-job` listed. `rtdp-silver-refresh-job-error-test` must be absent.

### 3.3 Verify Cloud SQL state

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER` / `STOPPED`.

---

## Evidence to Capture

The evidence document must record:

1. **Old filter** — full `gcloud logging metrics describe` JSON output before update
2. **New filter** — full `gcloud logging metrics describe` JSON output after update, confirming `resource.labels.job_name` absent
3. **Metric update command output**
4. **Temporary job definition** — `gcloud run jobs describe rtdp-silver-refresh-job-error-test --format=json` confirming `HAS_DATABASE_URL: False`
5. **Failed execution output** — execution name, exit code 1, reason: `DATABASE_URL environment variable is not set`
6. **Structured error log** — full Cloud Logging JSON entry with all expected fields
7. **Cloud Monitoring timeSeries** — full API response with at least one `int64Value > 0`
8. **Cleanup output** — job deletion confirmation, `gcloud run jobs list` showing only production job
9. **Final Cloud SQL state** — `NEVER / STOPPED`
10. **Final test run** — `uv run pytest -q` 116 passed
11. **Final Ruff** — `uv run ruff check .` all checks passed

---

## Acceptance Criteria

| Criterion | Required |
|---|---|
| Metric filter updated — `resource.labels.job_name` absent | Yes |
| All four retained conditions present in new filter | Yes |
| `HAS_DATABASE_URL: False` on temporary job | Yes |
| Temporary job failed with exit code 1 | Yes |
| Structured `EnvironmentError` log found in Cloud Logging | Yes |
| Cloud Monitoring timeSeries has at least one `int64Value > 0` | Yes |
| Temporary job deleted — not in `gcloud run jobs list` | Yes |
| Cloud SQL `NEVER / STOPPED` throughout | Yes |
| 116 tests passed | Yes |
| Ruff clean | Yes |

All criteria must be met for the evidence document to be marked `VALIDATED`.

---

## Stop Conditions

Stop and do not proceed to the next step if any of the following occur:

- Cloud SQL is not `NEVER / STOPPED` at any pre-execution check
- `gcloud logging metrics update` returns an error
- Post-update verification shows `resource.labels.job_name` is still present
- Any retained filter condition is absent after update
- Temporary job is created with `DATABASE_URL` present
- Temporary job execution succeeds (exit code 0) — indicates DATABASE_URL may be present
- Temporary job fails for any reason other than missing `DATABASE_URL`
- Cloud Logging query returns no matching log entry
- Cloud Monitoring timeSeries query returns zero datapoints after a 90-second wait
- Cleanup command fails — investigate before retrying

---

## What This Runbook Does Not Do

- Does not modify application code in any package
- Does not mutate the production `rtdp-silver-refresh-job` definition or secrets
- Does not start Cloud SQL
- Does not publish Pub/Sub messages
- Does not create or modify alert policies
- Does not add a dead-letter policy to the production push subscription
- Does not add Terraform or IaC for any resource
- Does not validate 5,000-event scale throughput
- Does not create or validate `worker_message_error_count` (already accepted)

---

## Related Documents

| Document | Role |
|---|---|
| [isolated-error-counter-validation-runbook.md](isolated-error-counter-validation-runbook.md) | Predecessor runbook — isolated Pub/Sub DLQ + temporary job approach |
| [isolated-error-counter-validation-evidence.md](isolated-error-counter-validation-evidence.md) | Partial evidence — worker counter accepted, silver counter blocked |
| [cloud-error-counter-validation-plan.md](cloud-error-counter-validation-plan.md) | Original plan document for error counter validation |
| [cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md) | Metric creation and configuration evidence |
| [cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Success counter timeSeries evidence |
