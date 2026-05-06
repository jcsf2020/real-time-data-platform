# Isolated Error Counter Validation Evidence

**Status:** PARTIAL VALIDATION — WORKER ERROR COUNTER VALIDATED, SILVER ERROR COUNTER BLOCKED BY METRIC FILTER

**Date:** 2026-05-06

**Branch:** docs/isolated-error-counter-validation-evidence

---

## 1. Executive Summary

- `worker_message_error_count` was validated end-to-end with real Cloud Monitoring timeSeries datapoints (TOTAL=13 across 10 one-minute windows).
- `silver_refresh_error_count` is **not validated**. The silver refresh error path emitted the correct structured error log, but the official logs-based metric filter hardcodes `resource.labels.job_name="rtdp-silver-refresh-job"`, which excluded the log emitted by the temporary isolated job (`rtdp-silver-refresh-job-error-test`). No timeSeries datapoint was produced.
- All isolated resources (Pub/Sub topic, DLQ topic, subscription, temporary Cloud Run Job) were created, used, and fully cleaned up.
- Cloud SQL (`rtdp-postgres`) remained in `NEVER STOPPED` state throughout. It was not started.
- The production Pub/Sub topic (`market-events-raw`) and production push subscription (`market-events-raw-worker-push`) were not used for malformed message publishing.
- A failed attempt to override `DATABASE_URL` on the production Cloud Run Job via `--update-env-vars` at execution time is documented below. It did not succeed and did not mutate the production job definition.

---

## 2. Pre-Execution Validation

All gates passed before any GCP interaction:

| Check | Result |
|---|---|
| `uv sync --all-packages` | Succeeded |
| `uv run pytest -q` | 116 passed, 0 failed |
| `uv run ruff check .` | All checks passed |
| Cloud SQL state | NEVER STOPPED (not started) |
| logs-based metrics existence | All four confirmed |

### Confirmed logs-based metrics

| Metric name | Kind | Type |
|---|---|---|
| `worker_message_processed_count` | DELTA | INT64 |
| `worker_message_error_count` | DELTA | INT64 |
| `silver_refresh_success_count` | DELTA | INT64 |
| `silver_refresh_error_count` | DELTA | INT64 |

---

## 3. Production Pub/Sub Baseline

The production Pub/Sub push subscription was inspected read-only before any malformed-message publishing:

| Property | Value |
|---|---|
| subscription | `market-events-raw-worker-push` |
| topic | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw` |
| state | ACTIVE |
| pushEndpoint | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` |
| hasDeadLetterPolicy | False |
| hasRetryPolicy | False |
| ackDeadlineSeconds | 30 |
| messageRetentionDuration | 600s |

The production subscription had no dead-letter policy and no bounded retry. Publishing a malformed message to the production topic would have caused unbounded redelivery to the live push endpoint. Therefore, production topic `market-events-raw` was **not used** for malformed message publishing. All error-path testing was performed through an isolated topic and subscription.

---

## 4. Worker Error Counter Validation Evidence

### 4.1 Isolated Resources Created

| Resource | Name |
|---|---|
| Isolated topic | `market-events-raw-error-test` |
| DLQ topic | `market-events-raw-error-test-dlq` |
| Isolated subscription | `market-events-raw-error-test-worker-push` |

Pub/Sub service agent used for DLQ IAM binding:

| Property | Value |
|---|---|
| PROJECT_NUMBER | 892892382088 |
| PUBSUB_SA | `service-892892382088@gcp-sa-pubsub.iam.gserviceaccount.com` |
| IAM binding granted | `roles/pubsub.publisher` on DLQ topic |

### 4.2 Isolated Subscription Configuration

| Property | Value |
|---|---|
| name | `projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-error-test-worker-push` |
| topic | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-error-test` |
| state | ACTIVE |
| pushEndpoint | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` |
| pushServiceAccount | `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| deadLetterTopic | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-error-test-dlq` |
| maxDeliveryAttempts | 5 |
| minimumBackoff | 10s |
| maximumBackoff | 60s |
| messageRetentionDuration | 600s |

`maxDeliveryAttempts=5` ensured the malformed message would be redelivered a bounded number of times before being forwarded to the DLQ. This allowed observation of multiple error log entries and metric datapoints without unbounded retry.

### 4.3 Malformed Message Published

A single message with payload `not-valid-json` (base64-encoded) was published to the isolated topic only:

| Property | Value |
|---|---|
| topic | `market-events-raw-error-test` |
| payload | base64 of `not-valid-json` |
| messageId | `18853301548034471` |

### 4.4 Worker Error Logs Observed

Log entries matching the error path were observed in Cloud Logging:

| Field | Value |
|---|---|
| `resource.type` | `cloud_run_revision` |
| `resource.labels.service_name` | `rtdp-pubsub-worker` |
| `jsonPayload.operation` | `process_message` |
| `jsonPayload.status` | `error` |
| `jsonPayload.error_type` | `JSONDecodeError` |
| `jsonPayload.error_message` | `Expecting value: line 1 column 1 (char 0)` |

Multiple retries were observed (up to `maxDeliveryAttempts=5`). Example insertIds:

- `69faffb5000b1241f52a6e14`
- `69faff910009d4e49475e8dc`
- `69faff7900058ec1a7b6c5f5`
- `69faff63000570d2e6336759`
- `69faff52000481b8c731093c`

### 4.5 Cloud Monitoring Datapoint Validation

Cloud Monitoring timeSeries query for `logging.googleapis.com/user/worker_message_error_count` returned the following datapoints:

| Window start (UTC) | Window end (UTC) | Count |
|---|---|---|
| 2026-05-06T08:43:09Z | 2026-05-06T08:44:09Z | 2 |
| 2026-05-06T08:44:09Z | 2026-05-06T08:45:09Z | 3 |
| 2026-05-06T08:45:09Z | 2026-05-06T08:46:09Z | 2 |
| 2026-05-06T08:46:09Z | 2026-05-06T08:47:09Z | 1 |
| 2026-05-06T08:47:09Z | 2026-05-06T08:48:09Z | 1 |
| 2026-05-06T08:48:09Z | 2026-05-06T08:49:09Z | 2 |
| 2026-05-06T08:49:09Z | 2026-05-06T08:50:09Z | 1 |
| 2026-05-06T08:50:09Z | 2026-05-06T08:51:09Z | 1 |
| 2026-05-06T08:41:09Z | 2026-05-06T08:42:09Z | 0 |
| 2026-05-06T08:42:09Z | 2026-05-06T08:43:09Z | 0 |

| Summary field | Value |
|---|---|
| POINTS | 10 |
| TOTAL | 13 |
| WORKER_ERROR_DATAPOINT_VALIDATED | True |

### 4.6 Isolated Pub/Sub Cleanup Verification

After validation, all isolated Pub/Sub resources were deleted:

| Action | Resource |
|---|---|
| Deleted subscription | `market-events-raw-error-test-worker-push` |
| Deleted topic | `market-events-raw-error-test` |
| Deleted topic | `market-events-raw-error-test-dlq` |

Post-cleanup Pub/Sub resource list showed only production resources:

- subscription: `market-events-raw-worker-push`
- subscription: `market-events-raw-verify`
- topic: `market-events-raw`

No isolated error-test topic or subscription remained.

---

## 5. Silver Refresh Error Counter Attempt

### 5.1 Production Job Inspection

| Property | Value |
|---|---|
| JOB_NAME | `rtdp-silver-refresh-job` |
| REGION | `europe-west1` |
| IMAGE | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest` |
| DATABASE_URL | PRESENT — bound via Secret Manager |

### 5.2 Temporary Job Creation

A temporary Cloud Run Job was created without `DATABASE_URL` to trigger the error path:

| Property | Value |
|---|---|
| JOB_NAME | `rtdp-silver-refresh-job-error-test` |
| IMAGE | same as production job |
| HAS_DATABASE_URL | False |
| MAX_RETRIES | 0 |
| TASK_TIMEOUT | 60s |

### 5.3 Temporary Job Execution

The job was executed and failed with exit code 1 as expected, because `DATABASE_URL` was absent.

| Property | Value |
|---|---|
| execution | `rtdp-silver-refresh-job-error-test-99vvz` |
| outcome | failed (exit code 1) |
| reason | DATABASE_URL environment variable is not set |

### 5.4 Structured Error Log Emitted

The temporary job emitted a correctly structured error log:

| Field | Value |
|---|---|
| `resource.type` | `cloud_run_job` |
| `resource.labels.job_name` | `rtdp-silver-refresh-job-error-test` |
| `jsonPayload.service` | `rtdp-silver-refresh-job` |
| `jsonPayload.operation` | `refresh_market_event_minute_aggregates` |
| `jsonPayload.status` | `error` |
| `jsonPayload.error_type` | `EnvironmentError` |
| `jsonPayload.error_message` | `DATABASE_URL environment variable is not set` |
| `insertId` | `69fb04580007d6c1afbc9182` |
| `execution_name` | `rtdp-silver-refresh-job-error-test-99vvz` |
| `timestamp` | `2026-05-06T09:05:28.513729Z` |

### 5.5 Cloud Monitoring timeSeries Query Result

Cloud Monitoring timeSeries query for `logging.googleapis.com/user/silver_refresh_error_count` returned:

```json
{
  "unit": "1"
}
```

No `timeSeries` field was present. Zero datapoints were produced.

### 5.6 Metric Filter Diagnosis

The official `silver_refresh_error_count` metric filter is:

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"
```

The temporary job used `resource.labels.job_name="rtdp-silver-refresh-job-error-test"`.

The condition `resource.labels.job_name="rtdp-silver-refresh-job"` is hardcoded to the production job name. The log emitted by the temporary job had `job_name="rtdp-silver-refresh-job-error-test"` and therefore did **not** match the metric filter. The structured log was correct; the metric filter excluded it.

### 5.7 Conclusion

`silver_refresh_error_count` is **NOT validated**. The metric filter must be relaxed before an isolated temporary job can produce a datapoint. See Section 9 for the recommended next branch.

---

## 6. Failed Production Job Override Attempt

An attempt was made to execute the production job with a string-literal `DATABASE_URL` override to trigger the error path without touching Cloud SQL:

```bash
gcloud run jobs execute rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --update-env-vars=DATABASE_URL=not-a-valid-postgres-url \
  --wait
```

The command failed before any execution with:

```
Cannot update environment variable [DATABASE_URL] to string literal because it has already been set with a different type.
```

**Explanation:** `DATABASE_URL` on the production job is a Secret Manager binding (not a plain string). Cloud Run does not allow changing an environment variable from a secret reference to a string literal at execution time via `--update-env-vars`. The production job definition was not mutated. No execution was started.

**This must not be considered validation.** No metric datapoint was produced by this attempt.

---

## 7. Cleanup and Final State

| Resource | Action | Post-cleanup state |
|---|---|---|
| Pub/Sub subscription `market-events-raw-error-test-worker-push` | Deleted | Not present |
| Pub/Sub topic `market-events-raw-error-test` | Deleted | Not present |
| Pub/Sub topic `market-events-raw-error-test-dlq` | Deleted | Not present |
| Cloud Run Job `rtdp-silver-refresh-job-error-test` | Deleted | Not present |
| Cloud Run Job `rtdp-silver-refresh-job` | Not touched | Still present, unchanged |
| Cloud SQL `rtdp-postgres` | Not started | NEVER STOPPED |

Final `gcloud run jobs list` showed only:

- `rtdp-silver-refresh-job`

Final Pub/Sub `gcloud pubsub subscriptions list` and `topics list` showed only production resources.

---

## 8. Acceptance Matrix

| Item | Status |
|---|---|
| `worker_message_error_count` timeSeries validated | **ACCEPTED** |
| `silver_refresh_error_count` timeSeries validated | **BLOCKED / NOT ACCEPTED** |
| Pub/Sub isolated resource cleanup | **ACCEPTED** |
| Temporary Cloud Run Job cleanup | **ACCEPTED** |
| Cloud SQL state (NEVER STOPPED) | **ACCEPTED** |
| Full error-counter validation (both metrics) | **NOT ACCEPTED** |

---

## 9. Next Required Branch

**Recommended branch:** `fix/silver-refresh-error-metric-filter`

**Objective:** Safely update the `silver_refresh_error_count` logs-based metric filter so that an isolated temporary Cloud Run Job (with a different `job_name`) can produce a matching datapoint — without mutating production job secrets or starting Cloud SQL.

**Proposed safe direction:** Remove or relax the hardcoded `resource.labels.job_name="rtdp-silver-refresh-job"` condition from the metric filter while retaining all other conditions:

```
resource.type="cloud_run_job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"
```

The `jsonPayload.service` field is set by the application code itself (not by the Cloud Run job name), so it still uniquely identifies the silver refresh service regardless of which job name triggered the execution. This change allows isolated temporary jobs to be validated safely.

This filter change, its runbook, and its acceptance evidence must be done in a separate branch/runbook/evidence cycle.

---

## 10. What This Evidence Does Not Claim

- Does **not** claim `silver_refresh_error_count` is validated.
- Does **not** claim all four logs-based metrics are fully validated with error-counter datapoints.
- Does **not** create or validate alert policies.
- Does **not** close the IaC/Terraform gap (metrics and dashboards are not managed as code).
- Does **not** close the production DLQ safety gap (the production push subscription still has no dead-letter policy).
- Does **not** validate 5,000-event scale throughput.
- Does **not** claim the production job definition was mutated in any way.
