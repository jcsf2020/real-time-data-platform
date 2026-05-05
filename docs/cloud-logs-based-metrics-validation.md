# Cloud Logs-Based Metrics Validation

## Status

Validated on: 2026-05-05

The first four Cloud Logging logs-based metrics for the Real-Time Data Platform were created
and confirmed at configuration level. Metric resources exist in Cloud Monitoring. Log filter
expressions are grounded in validated `jsonPayload` entries. New log entries were generated
after metric creation to provide forward signal.

---

## Validation Objective

Prove that logs-based metric resources can be created in Cloud Monitoring using filters
grounded in the validated `jsonPayload` log entries from both the `rtdp-pubsub-worker` Cloud
Run service and the `rtdp-silver-refresh-job` Cloud Run Job. Prove the filters match real log
entries by generating new log entries after metric creation.

This validation does **not** claim that Cloud Monitoring datapoints are visible in the UI —
that is the objective of the next branch. This validation proves the metric resources exist
with correct configuration and that the underlying log signals are active.

---

## Metrics Created

All four metrics are `DELTA` / `INT64` counters. No distribution or latency metrics are
created in this branch.

| Metric name | Type | Description | Log source |
|---|---|---|---|
| `worker_message_processed_count` | DELTA / INT64 | Count of successfully processed Pub/Sub messages by the RTDP worker | `cloud_run_revision` — `rtdp-pubsub-worker` — `jsonPayload.status="ok"` |
| `worker_message_error_count` | DELTA / INT64 | Count of failed Pub/Sub message processing attempts by the RTDP worker | `cloud_run_revision` — `rtdp-pubsub-worker` — `jsonPayload.status="error"` |
| `silver_refresh_success_count` | DELTA / INT64 | Count of successful silver refresh Cloud Run Job executions | `cloud_run_job` — `rtdp-silver-refresh-job` — `jsonPayload.status="ok"` |
| `silver_refresh_error_count` | DELTA / INT64 | Count of failed silver refresh Cloud Run Job executions | `cloud_run_job` — `rtdp-silver-refresh-job` — `jsonPayload.status="error"` |

---

## Pre-Checks Before Metric Creation

| Check | Result |
|---|---|
| Branch | `feat/cloud-logs-based-metrics` |
| Test suite | 75 passed |
| Ruff | All checks passed |
| Cloud SQL | `NEVER / STOPPED` — not started before this session |

---

## Pre-Creation Log Filter Evidence

Before creating any metric, the log filter expressions were verified against existing Cloud
Logging entries to confirm they return non-empty results.

### Worker success filter — pre-existing evidence

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.service="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="ok"
```

Confirmed return (from [docs/worker-structured-logs-validation.md](worker-structured-logs-validation.md)):

| Field | Value |
|---|---|
| `jsonPayload.event_id` | `worker-structured-log-test-20260505112347` |
| `jsonPayload.symbol` | `SOLUSDT` |
| `jsonPayload.status` | `ok` |
| `jsonPayload.processing_time_ms` | `295.135` |

### Silver refresh success filter — pre-existing evidence

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="ok"
```

Confirmed return (from [docs/cloud-observability-evidence.md](cloud-observability-evidence.md)):

| Field | Value |
|---|---|
| `jsonPayload.service` | `rtdp-silver-refresh-job` |
| `jsonPayload.status` | `ok` |
| `jsonPayload.processing_time_ms` | `419.349` |

---

## Metric Creation Evidence

### Success counters (worker + silver refresh)

```bash
gcloud logging metrics create worker_message_processed_count \
  --project=project-42987e01-2123-446b-ac7 \
  --description="Count of successfully processed Pub/Sub messages by the RTDP worker" \
  --log-filter='resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.service="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="ok"' && \
gcloud logging metrics create silver_refresh_success_count \
  --project=project-42987e01-2123-446b-ac7 \
  --description="Count of successful silver refresh Cloud Run Job executions" \
  --log-filter='resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="ok"'
```

**Terminal behaviour:** The terminal exit indicator showed failure, but subsequent inspection
via `gcloud logging metrics describe` and `gcloud logging metrics list` confirmed both metrics
were created successfully. The failure indicator was not accompanied by an error message and
is interpreted as a transient CLI/shell exit-code artefact, not a creation failure.

### Error counters (worker + silver refresh)

```bash
gcloud logging metrics create worker_message_error_count \
  --project=project-42987e01-2123-446b-ac7 \
  --description="Count of failed Pub/Sub message processing attempts by the RTDP worker" \
  --log-filter='resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.service="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="error"' && \
gcloud logging metrics create silver_refresh_error_count \
  --project=project-42987e01-2123-446b-ac7 \
  --description="Count of failed silver refresh Cloud Run Job executions" \
  --log-filter='resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="error"'
```

**Output:**

```
Created [worker_message_error_count].
Created [silver_refresh_error_count].
```

---

## Metric Descriptor Evidence

`gcloud logging metrics describe` and `gcloud logging metrics list` confirmed all four
metrics were created with the correct configuration.

### worker_message_processed_count

| Field | Value |
|---|---|
| `metricKind` | `DELTA` |
| `valueType` | `INT64` |
| Filter | See success filter above |

### silver_refresh_success_count

| Field | Value |
|---|---|
| `metricKind` | `DELTA` |
| `valueType` | `INT64` |
| Filter | See success filter above |

### Full metric list confirmed by gcloud

```
NAME                            METRIC_KIND  VALUE_TYPE  DESCRIPTION
silver_refresh_error_count      DELTA        INT64       Count of failed silver refresh Cloud Run Job executions
silver_refresh_success_count    DELTA        INT64       Count of successful silver refresh Cloud Run Job executions
worker_message_error_count      DELTA        INT64       Count of failed Pub/Sub message processing attempts by the RTDP worker
worker_message_processed_count  DELTA        INT64       Count of successfully processed Pub/Sub messages by the RTDP worker
```

---

## Cloud Monitoring CLI Limitation

A follow-up command was attempted to confirm Cloud Monitoring metric descriptors directly:

```bash
gcloud monitoring metric-descriptors list \
  --project=project-42987e01-2123-446b-ac7 \
  --filter='metric.type = starts_with("logging.googleapis.com/user/")' \
  --format="table(type,metricKind,valueType,displayName)" | grep -E "worker_message|silver_refresh"
```

**Error:**

```
ERROR: (gcloud.monitoring) Invalid choice: 'metric-descriptors'.
```

**Interpretation:** The installed `gcloud` CLI version does not include the
`gcloud monitoring metric-descriptors` command group. This is a local CLI version limitation,
not a metric creation failure. The `gcloud logging metrics list` and
`gcloud logging metrics describe` commands confirmed metric existence and configuration
independently. The Cloud Monitoring Metrics Explorer in the GCP Console, or the Cloud
Monitoring API, can be used to verify the descriptors directly without the CLI limitation.

---

## Post-Creation Signal Generation

Logs-based metrics do not backfill. Entries logged before metric creation are not counted.
To provide forward signal, new log entries were generated after metric creation.

### Cloud SQL temporary start

Cloud SQL was started only for the duration of this validation step.

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS && \
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"
```

Output:

```
ALWAYS  RUNNABLE
```

### New worker success log — Pub/Sub event

```bash
EVENT_ID="metrics-worker-test-$(date +%Y%m%d%H%M%S)" && \
EVENT_JSON="{\"schema_version\":\"1.0\",\"event_id\":\"${EVENT_ID}\",\"symbol\":\"ADAUSDT\",\"event_type\":\"trade\",\"price\":\"0.45\",\"quantity\":\"100.00\",\"event_timestamp\":\"2026-05-05T14:00:00+00:00\"}" && \
echo "Publishing event_id=${EVENT_ID}" && \
gcloud pubsub topics publish market-events-raw \
  --message="${EVENT_JSON}" && \
sleep 10 && \
curl -s "https://rtdp-api-892892382088.europe-west1.run.app/events?limit=5" && \
echo
```

**Output:**

```
Publishing event_id=metrics-worker-test-20260505162547
messageIds:
- '18808022922713751'
```

**API `/events` confirmation:**

| Field | Value |
|---|---|
| `event_id` | `metrics-worker-test-20260505162547` |
| `symbol` | `ADAUSDT` |
| `event_type` | `trade` |
| `price` | `0.45` |
| `quantity` | `100.0` |
| `event_timestamp` | `2026-05-05T14:00:00Z` |
| `ingested_at` | `2026-05-05T15:25:51.592477Z` |
| `source_topic` | `market-events-raw` |

**Cloud Logging `jsonPayload` confirmation (follow-up query):**

| Field | Value |
|---|---|
| `jsonPayload.event_id` | `metrics-worker-test-20260505162547` |
| `jsonPayload.symbol` | `ADAUSDT` |
| `jsonPayload.status` | `ok` |
| `jsonPayload.processing_time_ms` | `337.257` |

This log entry was emitted after `worker_message_processed_count` was created. The filter
expression matches this entry; the metric counter should have incremented for this execution.

### New silver refresh success log — job execution

```bash
gcloud run jobs execute rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --wait
```

**Output:**

```
Execution [rtdp-silver-refresh-job-v5qfc] has successfully completed.
1 / 1 complete
```

**Cloud Logging `jsonPayload` confirmation (follow-up query):**

| Field | Value |
|---|---|
| `jsonPayload.service` | `rtdp-silver-refresh-job` |
| `jsonPayload.status` | `ok` |
| `jsonPayload.processing_time_ms` | `506.525` |

This log entry was emitted after `silver_refresh_success_count` was created. The filter
expression matches this entry; the metric counter should have incremented for this execution.

---

## Cost-Control Final State

Cloud SQL was stopped immediately after the post-creation signal generation step.

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER && \
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"
```

**First patch attempt returned:**

```
ERROR: (gcloud.sql.instances.patch) HTTPError 400: Invalid request: Instance properties other
than activation policy are not allowed to be updated when the instance is stopped and not
started in the same operation..
```

**Interpretation:** The stop had already been reached or was in transition before the patch
command completed. This error message is known to appear when Cloud SQL reaches the stopped
state faster than expected. The follow-up `describe` command confirmed the final state:

```
NEVER   STOPPED
```

Cloud SQL is confirmed stopped and will not incur compute charges.

---

## Local Validation (Final)

```
uv sync --all-packages   →  resolved, no errors
uv run pytest -q         →  75 passed
uv run ruff check .      →  All checks passed!
Cloud SQL final state    →  NEVER   STOPPED
Metrics confirmed        →  4 metrics, DELTA INT64
```

---

## What This Proves

- All four logs-based metric resources exist in Cloud Monitoring:
  `worker_message_processed_count`, `worker_message_error_count`,
  `silver_refresh_success_count`, `silver_refresh_error_count`.
- Each metric's log filter expression is grounded in validated `jsonPayload` log entries that
  were confirmed before metric creation (not invented).
- New log entries matching the `status="ok"` filters for both worker and silver refresh were
  generated after metric creation, providing forward signal for the counters to increment.
- All four metrics are correctly typed `DELTA / INT64`.
- Cloud SQL was started only for the duration of the post-creation signal generation and was
  stopped immediately after; final state is `NEVER / STOPPED`.
- The Pub/Sub → worker → Cloud SQL → API end-to-end path continues to work correctly
  (symbol `ADAUSDT` event confirmed via the API).
- Test suite (75 passed) and linter (ruff clean) are unaffected.

---

## What This Does Not Prove Yet

- **Cloud Monitoring datapoints visible** — metric counter values in the Cloud Monitoring
  Metrics Explorer or API have not been queried. This is the gap addressed by the next branch.
- **Error counters incrementing** — `worker_message_error_count` and
  `silver_refresh_error_count` exist but no error log entries have been generated to exercise
  them. A safe synthetic error path is required before claiming these counters work.
- **Alert policies** — no alerting policies have been created or wired to these metrics.
- **Cloud Monitoring dashboard** — no dashboard has been created.
- **Grafana** — no Grafana integration configured.
- **Latency distribution metrics** — `worker_processing_latency_ms` and
  `silver_refresh_latency_ms` are not created in this branch.
- **Automated / scheduled refresh** — no Cloud Scheduler or recurring trigger exists.
  The silver refresh job was executed manually.

---

## Honest Architecture Claim

> **First Cloud Logging logs-based metrics created for worker and silver refresh success/error
> counters.**

Do not claim Cloud Monitoring dashboards, alert policies, or visible datapoints until those
are explicitly configured and validated in a subsequent session.

---

## Next Recommended Branch

**Branch name:** `docs/cloud-logs-based-metrics-datapoint-validation`

**Objective:** Confirm that actual Cloud Monitoring datapoints are visible for:

- `worker_message_processed_count`
- `silver_refresh_success_count`

These are the two success counters for which log entries were generated after metric creation.
The correct query path is via the Cloud Monitoring Metrics Explorer in the GCP Console or the
Cloud Monitoring API (`timeSeries.list`), since the local `gcloud monitoring metric-descriptors`
command group is not available in the installed CLI version.

**Also note:** `worker_message_error_count` and `silver_refresh_error_count` exist but should
be validated separately with a deliberately safe synthetic error path — for example, a
malformed Pub/Sub message payload that fails `MarketEvent` schema validation. Do not claim
error counter functionality until at least one error log entry is confirmed to have incremented
the counter.
