# Cloud Error Counter Validation Plan

## Status

**PLAN ONLY — NOT EXECUTED**

---

## Objective

Plan a safe path to produce and confirm Cloud Monitoring timeSeries datapoints for the two
error-counter logs-based metrics:

- `worker_message_error_count`
- `silver_refresh_error_count`

Both metrics are DELTA INT64 counters that increment when a matching structured log entry
reaches Cloud Logging. The challenge is generating exactly one controlled error log entry
per counter without triggering unbounded Pub/Sub retries, mutating production job configuration,
or incurring unnecessary Cloud SQL cost.

---

## Existing Error Metrics

| Metric | Kind | Type | Resource type | Filter key fields |
|---|---|---|---|---|
| `worker_message_error_count` | DELTA | INT64 | `cloud_run_revision` | `service=rtdp-pubsub-worker`, `operation=process_message`, `status=error` |
| `silver_refresh_error_count` | DELTA | INT64 | `cloud_run_job` | `service=rtdp-silver-refresh-job`, `operation=refresh_market_event_minute_aggregates`, `status=error` |

Full metric filters:

**worker_message_error_count**

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.service="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="error"
```

**silver_refresh_error_count**

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"
```

---

## Known Local Error Paths

### 1. Worker — `process_message` error paths

Source: [apps/pubsub-worker/src/rtdp_pubsub_worker/__init__.py](../apps/pubsub-worker/src/rtdp_pubsub_worker/__init__.py)

The `process_message` function (line 80) wraps all exceptions in a single `except Exception`
block and emits a structured JSON log with:

```python
{
    "component": "pubsub-worker",
    "error_message": str(exc),
    "error_type": type(exc).__name__,
    "event_id": event_id,        # None if decode failed
    "operation": "process_message",
    "processing_time_ms": ...,
    "service": "rtdp-pubsub-worker",
    "source_topic": SOURCE_TOPIC,
    "status": "error",
    "symbol": symbol,            # None if decode failed
    "timestamp_utc": ...,
}
```

This covers three triggerable error paths:

| Path | Trigger | `error_type` |
|---|---|---|
| Decode failure | Non-JSON bytes payload | `JSONDecodeError` |
| Validation failure | Valid JSON but missing/invalid `MarketEvent` fields | `ValidationError` |
| DB failure | Invalid `DATABASE_URL` or unreachable DB | `OperationalError` (or similar) |

Tests confirming these paths:

- `tests/test_pubsub_worker.py` — `test_process_message_bad_json_returns_error`,
  `test_process_message_validation_error`, `test_process_message_db_failure`

The HTTP endpoint in
[apps/pubsub-worker/src/rtdp_pubsub_worker/http_app.py](../apps/pubsub-worker/src/rtdp_pubsub_worker/http_app.py)
calls `process_message` and returns HTTP 200 regardless of the processing status (it returns 500
only on decode-level failures at the HTTP layer — see risk analysis below).

Test confirming HTTP error behaviour:

- `tests/test_pubsub_worker_http.py` — `test_push_process_message_error_returns_500`

### 2. Silver refresh job — error paths

Source: [apps/silver-refresh-job/src/rtdp_silver_refresh_job/__init__.py](../apps/silver-refresh-job/src/rtdp_silver_refresh_job/__init__.py)

The job has two error emission points:

**a. Missing `DATABASE_URL`** (line 54–65, `main` function):

```python
{
    "component": "silver-refresh",
    "error_message": "DATABASE_URL environment variable is not set",
    "error_type": "EnvironmentError",
    "operation": "refresh_market_event_minute_aggregates",
    "processing_time_ms": 0.0,
    "service": "rtdp-silver-refresh-job",
    "status": "error",
    "timestamp_utc": ...,
}
```

**b. DB failure** (line 38–49, `run_refresh` exception handler):

```python
{
    "component": "silver-refresh",
    "error_message": str(exc),
    "error_type": type(exc).__name__,
    "operation": "refresh_market_event_minute_aggregates",
    "processing_time_ms": ...,
    "service": "rtdp-silver-refresh-job",
    "status": "error",
    "timestamp_utc": ...,
}
```

Tests confirming these paths:

- `tests/test_silver_refresh_job.py` — `test_main_missing_database_url`,
  `test_run_refresh_db_failure`

---

## Risk Analysis

### Pub/Sub retry risk (worker)

- The deployed `rtdp-pubsub-worker` Cloud Run service is the push endpoint for a Pub/Sub
  subscription.
- `test_push_process_message_error_returns_500` confirms that a message causing a processing
  error at the HTTP layer returns HTTP 500.
- Pub/Sub interprets any non-2xx response as a delivery failure and will retry the message
  according to the subscription's retry policy.
- The retry policy configuration (minimum/maximum backoff, maximum delivery attempts, dead
  letter topic) has **not yet been inspected**. An unbounded retry policy could cause the same
  malformed message to trigger thousands of error log entries, inflating the error counter and
  potentially incurring cost.
- **Do not send malformed messages to the production Pub/Sub topic until the retry/DLQ
  configuration is read and bounded.**

### Production job mutation risk (silver refresh)

- The deployed `rtdp-silver-refresh-job` Cloud Run Job reads `DATABASE_URL` from Secret Manager.
- Forcing an error by unsetting or overwriting `DATABASE_URL` in the production job config would
  mutate a production resource and risk breaking future legitimate job executions.
- **Do not modify the `rtdp-silver-refresh-job` configuration.**

### Cloud SQL cost risk

- `rtdp-postgres` is currently in state `NEVER STOPPED`.
- Any validation step that starts Cloud SQL when it is stopped adds cost.
- Steps that do not require a database connection (e.g. missing `DATABASE_URL` path for the
  silver refresh job) are preferred because they carry no Cloud SQL cost risk.
- Verify Cloud SQL state before and after any execution step.

### No DLQ/retry bound validated yet

- No dead letter queue (DLQ) configuration has been confirmed on the production subscription.
- Until that is read and confirmed, the safe assumption is that retries are unbounded.

---

## Recommended Validation Strategy

### Phase A — Read-only design (next branch)

Before any traffic is generated, perform read-only inspection:

1. **Inspect Pub/Sub subscription retry and dead-letter policy** — run
   `gcloud pubsub subscriptions describe <subscription-name> --format=json` to confirm
   `retryPolicy.minimumBackoff`, `retryPolicy.maximumBackoff`, `maxDeliveryAttempts`, and
   whether a dead letter topic is configured.
2. **Inspect Cloud Run worker push configuration** — confirm the push endpoint URL, auth type
   (OIDC token), and audience so the subscription target is fully understood before any message
   is sent.
3. **Confirm whether a test-only topic/subscription exists** — check
   `gcloud pubsub topics list` and `gcloud pubsub subscriptions list` for any non-production
   topic (e.g. `market-events-test`, `market-events-raw-test`) that could be used for isolated
   error injection without affecting the production consumer.
4. **Do not send any message (malformed or otherwise) to the production topic in this phase.**

This read-only work belongs in branch `docs/pubsub-retry-dlq-inspection` (see below).

---

### Phase B — Controlled execution (after Phase A)

Execute only after the retry policy is confirmed to be bounded or a fully isolated path is
available.

#### Worker — `worker_message_error_count`

**Preferred path: isolated test topic/subscription**

1. If a test topic/subscription exists (confirmed in Phase A), configure a temporary Cloud Run
   worker revision or local HTTP target as the push endpoint.
2. Publish exactly **one** malformed Pub/Sub message (e.g. raw bytes `b"not-json"` or a JSON
   payload missing required `MarketEvent` fields) to the test topic only.
3. Allow the worker to process the message and confirm the Cloud Logging entry:
   - `jsonPayload.service = "rtdp-pubsub-worker"`
   - `jsonPayload.operation = "process_message"`
   - `jsonPayload.status = "error"`
   - `jsonPayload.error_type` present
4. Wait one full minute-boundary for the DELTA window to close.
5. Query the Cloud Monitoring REST API for `worker_message_error_count` timeSeries:

   ```bash
   START_TIME="$(date -u -v-6H +%Y-%m-%dT%H:%M:%SZ)"
   END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
   TOKEN="$(gcloud auth print-access-token)"
   curl -s \
     -H "Authorization: Bearer ${TOKEN}" \
     "https://monitoring.googleapis.com/v3/projects/<PROJECT_ID>/timeSeries?\
   filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fworker_message_error_count%22\
   &interval.startTime=${START_TIME}&interval.endTime=${END_TIME}"
   ```

6. Confirm at least one `int64Value > 0` datapoint in the response.
7. Clean up any temporary topics, subscriptions, or worker revisions.

**Fallback path: bounded production retry**

If no test topic exists and the production retry policy is confirmed as bounded (e.g. max 5
attempts with dead-letter topic), a single malformed message may be sent to the production
topic. This path requires:

- Dead-letter topic confirmed and monitored.
- Maximum delivery attempts confirmed (≤ 5).
- Immediate log inspection to confirm the error entry appeared.
- Acknowledge the dead-lettered message immediately after confirmation to prevent re-delivery.

**Do not use the fallback path if retries are unbounded.**

---

#### Silver refresh — `silver_refresh_error_count`

**Preferred path: temporary isolated Cloud Run Job**

1. Create a temporary Cloud Run Job with a distinct name (e.g. `rtdp-silver-refresh-job-test`)
   using the same container image as `rtdp-silver-refresh-job`.
2. Set the job's environment to **omit** `DATABASE_URL` (do not set the Secret Manager binding).
3. Execute the job once:

   ```bash
   gcloud run jobs execute rtdp-silver-refresh-job-test --wait --region=europe-west1
   ```

4. The `main()` function will detect the missing `DATABASE_URL` and emit:
   - `jsonPayload.service = "rtdp-silver-refresh-job"`
   - `jsonPayload.operation = "refresh_market_event_minute_aggregates"`
   - `jsonPayload.status = "error"`
   - `jsonPayload.error_type = "EnvironmentError"`
   without ever touching Cloud SQL.
5. Wait one full minute-boundary for the DELTA window to close.
6. Query the Cloud Monitoring REST API for `silver_refresh_error_count` timeSeries:

   ```bash
   START_TIME="$(date -u -v-6H +%Y-%m-%dT%H:%M:%SZ)"
   END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
   TOKEN="$(gcloud auth print-access-token)"
   curl -s \
     -H "Authorization: Bearer ${TOKEN}" \
     "https://monitoring.googleapis.com/v3/projects/<PROJECT_ID>/timeSeries?\
   filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fsilver_refresh_error_count%22\
   &interval.startTime=${START_TIME}&interval.endTime=${END_TIME}"
   ```

7. Confirm at least one `int64Value > 0` datapoint in the response.
8. **Delete the temporary job immediately after confirmation:**

   ```bash
   gcloud run jobs delete rtdp-silver-refresh-job-test --region=europe-west1 --quiet
   ```

**Why the `DATABASE_URL` missing path is preferred:**

- No Cloud SQL connection is attempted — no Cloud SQL start is required.
- The error is deterministic and emits exactly the fields matched by the metric filter.
- The production `rtdp-silver-refresh-job` is never touched.
- The temporary job is ephemeral and deleted immediately after.

---

## Alternative Safe Local-Only Validation

Local `pytest` already validates the error logging paths:

- `test_process_message_bad_json_returns_error` confirms the worker emits `status=error` for
  non-JSON input.
- `test_main_missing_database_url` confirms the silver refresh job emits `status=error` when
  `DATABASE_URL` is unset.

**Limitation:** Local test execution writes to local stdout and does not feed Cloud Logging.
Cloud Monitoring logs-based metrics are driven by log entries ingested into Cloud Logging from
deployed Cloud Run resources. Local tests therefore do not produce timeSeries datapoints in
Cloud Monitoring.

Local test results are useful as **confidence** that the code paths emit the correct structured
log fields, but they are not sufficient as proof that the Cloud Monitoring metric counter
increments.

---

## Execution Guardrails

The following constraints apply to any Phase B execution:

- **No production job mutation.** Do not update, override, or delete environment variables,
  secrets, or configuration of `rtdp-silver-refresh-job`.
- **No unbounded Pub/Sub retry.** Do not send malformed messages to the production topic unless
  the retry policy is confirmed bounded and a dead-letter topic is present.
- **Maximum one malformed event per validation run.** Send exactly one message; do not loop.
- **Verify Cloud SQL state before and after.** Run
  `gcloud sql instances describe rtdp-postgres --format="value(settings.activationPolicy,state)"`
  before starting and after completing each execution step.
- **Capture Cloud Logging evidence immediately.** Run the log query within 5 minutes of
  triggering the error to avoid any log expiry uncertainty.
- **Clean up temporary resources.** Delete any temporary Cloud Run Job, topic, or subscription
  created for validation before the branch is merged.
- **Document exact evidence.** Record the full API response (or the relevant timeSeries excerpt)
  in a companion validation document on the execution branch.

---

## Acceptance Criteria

- [ ] Worker error log entry visible in Cloud Logging with:
  - `jsonPayload.service = "rtdp-pubsub-worker"`
  - `jsonPayload.operation = "process_message"`
  - `jsonPayload.status = "error"`
- [ ] `worker_message_error_count` timeSeries returns at least one `int64Value > 0` datapoint
  via the Cloud Monitoring REST API.
- [ ] Silver refresh error log entry visible in Cloud Logging with:
  - `jsonPayload.service = "rtdp-silver-refresh-job"`
  - `jsonPayload.operation = "refresh_market_event_minute_aggregates"`
  - `jsonPayload.status = "error"`
- [ ] `silver_refresh_error_count` timeSeries returns at least one `int64Value > 0` datapoint
  via the Cloud Monitoring REST API.
- [ ] Cloud SQL final state: `NEVER STOPPED` (no Cloud SQL was started).
- [ ] No retry storm observed (Pub/Sub subscription delivery attempt count remains ≤ expected
  maximum).
- [ ] All temporary resources deleted (temporary Cloud Run Job, test topic/subscription if
  created).

---

## What This Will Prove After Execution

- All four logs-based metrics (`worker_message_processed_count`, `worker_message_error_count`,
  `silver_refresh_success_count`, `silver_refresh_error_count`) have been exercised with real
  Cloud Monitoring datapoints.
- The log filter for each error counter correctly matches the structured log entries emitted by
  the deployed services.
- The Cloud Run revision for `rtdp-pubsub-worker` and the Cloud Run Job for
  `rtdp-silver-refresh-job` emit error-path structured logs that are ingested and aggregated by
  Cloud Monitoring within a one-minute DELTA window.
- End-to-end observability coverage: success and error counters for both the streaming worker
  and the batch silver refresh job are confirmed as operational.

---

## What Remains Out of Scope

The following items are not addressed by this validation plan:

- Alert policy configuration or alert firing behaviour.
- Cloud Monitoring dashboards or Grafana integration.
- Latency distribution metrics.
- Scheduler / missing-execution detection metrics.
- Broad load testing or sustained failure injection.
- BigQuery metrics or Dataflow pipeline observability.

---

## Next Recommended Branch

**Branch:** `docs/pubsub-retry-dlq-inspection`

**Objective:** Read-only inspection of the Pub/Sub subscription retry policy, dead-letter
configuration, and Cloud Run worker push subscription setup before any malformed message is
sent.

**Specific read-only commands to run:**

```bash
# List all Pub/Sub subscriptions
gcloud pubsub subscriptions list --project=<PROJECT_ID> --format=json

# Describe the worker push subscription (name TBD from list output)
gcloud pubsub subscriptions describe <worker-subscription-name> \
  --project=<PROJECT_ID> --format=json

# List Cloud Run service push configuration
gcloud run services describe rtdp-pubsub-worker \
  --region=europe-west1 --format=json
```

**Gate:** Phase B worker validation may not proceed until the above commands are run and the
results confirm that either (a) a bounded retry policy with DLQ is in place, or (b) an isolated
test topic is available.
