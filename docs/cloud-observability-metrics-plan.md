# Cloud Observability Metrics Plan

## Status

**PLAN ONLY — NOT EXECUTED**

No GCP resources are created, modified, or deployed by this document. All commands shown are
templates only and must be reviewed against current `gcloud` help before execution. Cloud SQL
was not started during this session.

---

## Objective

Turn validated Cloud Logging evidence into operational metrics, alerting policies, and
dashboard signals. The worker and silver refresh job both emit structured `jsonPayload` logs
to Cloud Logging — these are the raw signal. This plan defines how to extract counters,
distributions, and latency metrics from those log entries, wire them to alert policies, and
surface them in a Cloud Monitoring dashboard. Grafana is addressed as a future visualization
layer once the metrics foundation exists.

---

## Validated Log Sources

The following log sources are confirmed in evidence docs. All `jsonPayload` fields listed
below are individually queryable in Cloud Logging.

### 1. Worker structured logs (`jsonPayload`)

Validated in [docs/worker-structured-logs-validation.md](worker-structured-logs-validation.md).
Revision: `rtdp-pubsub-worker-00003-dh6`.

| Field | Validated value |
|---|---|
| `resource.type` | `cloud_run_revision` |
| `resource.labels.service_name` | `rtdp-pubsub-worker` |
| `jsonPayload.service` | `rtdp-pubsub-worker` |
| `jsonPayload.component` | `pubsub-worker` |
| `jsonPayload.operation` | `process_message` |
| `jsonPayload.status` | `ok` |
| `jsonPayload.event_id` | `worker-structured-log-test-20260505112347` |
| `jsonPayload.symbol` | `SOLUSDT` |
| `jsonPayload.source_topic` | `market-events-raw` |
| `jsonPayload.processing_time_ms` | `295.135` |
| `logName` | `run.googleapis.com/stdout` |

### 2. Silver refresh job structured logs (`jsonPayload`)

Validated in [docs/silver-refresh-job-validation.md](silver-refresh-job-validation.md) and
[docs/cloud-observability-evidence.md](cloud-observability-evidence.md).
Execution: `rtdp-silver-refresh-job-x54pc`.

| Field | Validated value |
|---|---|
| `resource.type` | `cloud_run_job` |
| `resource.labels.job_name` | `rtdp-silver-refresh-job` |
| `jsonPayload.service` | `rtdp-silver-refresh-job` |
| `jsonPayload.component` | `silver-refresh` |
| `jsonPayload.operation` | `refresh_market_event_minute_aggregates` |
| `jsonPayload.status` | `ok` |
| `jsonPayload.processing_time_ms` | `419.349` |
| `logName` | `run.googleapis.com/stdout` |

### 3. Cloud Run request logs (`httpRequest`)

Validated in [docs/cloud-observability-evidence.md](cloud-observability-evidence.md).

| Field | Validated value |
|---|---|
| `resource.type` | `cloud_run_revision` |
| `resource.labels.service_name` | `rtdp-pubsub-worker` |
| `httpRequest.requestMethod` | `POST` |
| `httpRequest.requestUrl` | `.../pubsub/push` |
| `httpRequest.status` | `200` |
| `httpRequest.latency` | `3.207767544s` |
| `httpRequest.userAgent` | `APIs-Google` |

### 4. Cloud Run audit / execution logs

Validated in [docs/cloud-observability-evidence.md](cloud-observability-evidence.md).

| Field | Validated value |
|---|---|
| `resource.type` | `cloud_run_job` |
| `resource.labels.job_name` | `rtdp-silver-refresh-job` |
| `protoPayload.methodName` | `/Jobs.RunJob` |
| Status message | `Execution rtdp-silver-refresh-job-x54pc has completed successfully.` |
| `succeededCount` | `1` |
| `startTime` | `2026-05-05T06:09:38.301457Z` |
| `completionTime` | `2026-05-05T06:10:05.258025Z` |

---

## Target Observability Model

```text
structured stdout JSON
  -> Cloud Logging jsonPayload
    -> logs-based metrics
      -> Cloud Monitoring alert policies
        -> Cloud Monitoring dashboard / future Grafana
```

Cloud Run writes container stdout to Cloud Logging automatically. JSON lines are parsed into
`jsonPayload` with no log agent or sidecar. Logs-based metrics extract counters and
distributions from specific log filter expressions, making them queryable in Cloud Monitoring
exactly like native GCP resource metrics.

---

## Logs-Based Metrics Plan

All metrics below are **NOT CREATED**. This table is a design target only.

| # | Metric name | Source | Log filter | Type | Labels |
|---|---|---|---|---|---|
| 1 | `worker_message_processed_count` | `jsonPayload` — worker | `resource.type="cloud_run_revision"`<br>`resource.labels.service_name="rtdp-pubsub-worker"`<br>`jsonPayload.service="rtdp-pubsub-worker"`<br>`jsonPayload.operation="process_message"`<br>`jsonPayload.status="ok"` | Counter | `symbol` = `jsonPayload.symbol`<br>`source_topic` = `jsonPayload.source_topic` |
| 2 | `worker_message_error_count` | `jsonPayload` — worker | Same as above but `jsonPayload.status="error"` | Counter | `error_type` = `jsonPayload.error_type` (if present)<br>`source_topic` = `jsonPayload.source_topic` |
| 3 | `worker_processing_latency_ms` | `jsonPayload` — worker | Same resource + service filter; value from `jsonPayload.processing_time_ms` | Distribution | `symbol` = `jsonPayload.symbol`<br>`source_topic` = `jsonPayload.source_topic` |
| 4 | `silver_refresh_success_count` | `jsonPayload` — silver refresh job | `resource.type="cloud_run_job"`<br>`resource.labels.job_name="rtdp-silver-refresh-job"`<br>`jsonPayload.service="rtdp-silver-refresh-job"`<br>`jsonPayload.operation="refresh_market_event_minute_aggregates"`<br>`jsonPayload.status="ok"` | Counter | _(none required initially)_ |
| 5 | `silver_refresh_error_count` | `jsonPayload` — silver refresh job | Same as above but `jsonPayload.status="error"` | Counter | `error_type` = `jsonPayload.error_type` (if present) |
| 6 | `silver_refresh_latency_ms` | `jsonPayload` — silver refresh job | Same resource + service filter; value from `jsonPayload.processing_time_ms` | Distribution | _(none required initially)_ |
| 7 | `cloud_run_job_completed_count` | Audit / execution logs | `resource.type="cloud_run_job"`<br>`resource.labels.job_name="rtdp-silver-refresh-job"`<br>`protoPayload.methodName="/Jobs.RunJob"`<br>`protoPayload.status.message:"completed successfully"` | Counter | _(none required initially)_ |
| 8 | `worker_pubsub_push_http_5xx_count` | Request logs — worker | `resource.type="cloud_run_revision"`<br>`resource.labels.service_name="rtdp-pubsub-worker"`<br>`httpRequest.requestUrl:"/pubsub/push"`<br>`httpRequest.status>=500` | Counter | _(none required initially)_ |
| 9 | `worker_pubsub_push_latency_ms` | Request logs — worker | Same resource + URL filter; value from `httpRequest.latency` | Distribution | **Note:** Cloud Monitoring may expose native Cloud Run request latency more cleanly than a logs-based metric. Evaluate both before creating this metric — if the native `run.googleapis.com/request_latencies` metric covers the use case, prefer it over a custom metric. |

### Notes on metric type choice

- **Counter** — for success/error event counts; use `DELTA` aggregation in dashboards.
- **Distribution** — for latency; enables percentile queries (p50, p95, p99) in Cloud Monitoring.
- Distribution metrics require a value extractor pointing at the numeric field (`jsonPayload.processing_time_ms` is a float).
- Label cardinality: `symbol` can grow as new trading pairs are added. Monitor label cardinality to avoid excessive metric series.

---

## Alerting Plan

All policies below are **NOT CREATED**. This table is a design target only.

| # | Policy name | Trigger condition | Severity | Rationale |
|---|---|---|---|---|
| 1 | Worker processing errors detected | `worker_message_error_count > 0` within a 5-minute rolling window | Warning / High depending on sustained volume | Any error during message processing risks data loss; early warning before errors accumulate. |
| 2 | Silver refresh failure detected | `silver_refresh_error_count > 0` within a 15-minute window | High | A single failure in the silver refresh job breaks the bronze → silver aggregation path; data consumers see stale aggregates. |
| 3 | Worker Pub/Sub push 5xx detected | `worker_pubsub_push_http_5xx_count > 0` within a 5-minute window | High | HTTP 5xx returned to Pub/Sub causes message retry storms; Pub/Sub will re-deliver indefinitely until the push endpoint succeeds or the message expires. |
| 4 | Worker processing latency high | p95 `worker_processing_latency_ms > 2000 ms` over a 10-minute evaluation window | Warning | Sustained p95 above 2 s indicates DB connection overhead, Cloud SQL cold start, or upstream latency. Alert before the Pub/Sub message ack deadline is approached. |
| 5 | Silver refresh latency high | p95 `silver_refresh_latency_ms > 5000 ms` over a 30-minute evaluation window | Warning | Validated baseline is 419 ms; a 5 s threshold gives headroom for growth before the aggregate query becomes a reliability concern. |
| 6 | Scheduled refresh missing | **FUTURE ONLY** — do not implement until Cloud Scheduler or equivalent recurring trigger exists. | High | Trigger: no `silver_refresh_success_count` event in the expected execution interval (e.g., 60 minutes). Absence-of-signal alert requires a known execution schedule; without Cloud Scheduler this alert cannot be grounded. |

### Alert tuning notes

- Start with `ANY TIME SERIES VIOLATES` conditions before tuning to aggregated thresholds — this surfaces real signals during low-volume early operation.
- Set notification channels (email, PagerDuty, Slack webhook) before policies go live. An alert policy with no channel is silent.
- Alert 6 (missing refresh) must not fire before Cloud Scheduler is deployed. It is listed here to document the intent; implement only after recurring execution is validated.

---

## Dashboard Plan

A single Cloud Monitoring dashboard named **RTDP Pipeline Overview**. All panels below are
**NOT CREATED**.

### Sections and panel candidates

**Pipeline overview**
- Service health summary (Cloud Run service/job status)
- Pub/Sub topic message throughput (from native Pub/Sub metrics if available)
- Most recent silver refresh timestamp (derived from `silver_refresh_success_count` or audit log)

**Worker message processing**
- `worker_message_processed_count` — rate over time (messages/minute)
- Breakdown by `symbol` label (stacked or multi-line)

**Worker error rate**
- `worker_message_error_count` — rate over time
- Ratio panel: `error_count / (processed_count + error_count)` — error fraction

**Worker latency**
- `worker_processing_latency_ms` — p50, p95, p99 over time
- Heatmap (if supported) or percentile line chart

**Pub/Sub push HTTP status**
- `worker_pubsub_push_http_5xx_count` — count over time
- HTTP 200 rate from native Cloud Run request metrics (as baseline signal)

**Silver refresh job success / failure**
- `silver_refresh_success_count` — count per interval
- `silver_refresh_error_count` — count per interval
- `cloud_run_job_completed_count` — from audit logs (corroborating signal)

**Silver refresh latency**
- `silver_refresh_latency_ms` — p50, p95 over time
- Baseline reference line at validated value (419 ms) as annotation

**Cloud SQL note (manual runbook item)**
- Cloud SQL compute cost accrues only when the instance is in `RUNNABLE` state.
- Cloud SQL does not have a native "stopped" metric in Cloud Monitoring; its state is
  controlled via `gcloud sql instances patch --activation-policy=NEVER`.
- Add a text panel or annotation noting the manual start/stop runbook URL.
- Do not create an alert based on Cloud SQL state until cost monitoring is wired separately.

---

## Grafana Integration Path

Grafana is a visualization layer. It should not be set up before the metrics foundation exists.

**Correct sequence:**
1. Create logs-based metrics in Cloud Monitoring.
2. Validate that metrics receive data from real log entries.
3. Create alert policies.
4. Create a Cloud Monitoring dashboard.
5. Add Grafana as an additional visualization layer if the team prefers it.

**Do not start with Grafana before completing steps 1–4.** Grafana connected to an empty
or unvalidated Cloud Monitoring workspace produces misleading "no data" panels.

**Possible future integration paths:**

| Path | Description | When to use |
|---|---|---|
| 1. Grafana Cloud + Google Cloud Monitoring datasource | Grafana Cloud connects directly to Cloud Monitoring using a service account or Workload Identity. Metrics appear as standard time-series in Grafana dashboards. | Simplest path once logs-based metrics exist. Suitable for a single-project setup. |
| 2. Managed Prometheus / Prometheus-compatible metrics | The FastAPI `/metrics-prometheus` endpoint already exposes Prometheus gauge text. Cloud Managed Prometheus can scrape this endpoint and make the metrics available to Grafana via the Prometheus datasource. | Useful if expanding beyond Cloud Monitoring or if running workloads on GKE. |
| 3. Cloud Monitoring metrics export to Grafana | Use the Google Cloud Monitoring Grafana plugin to query Cloud Monitoring metrics directly from a self-hosted or Grafana Cloud instance. | Covers all Cloud Monitoring metrics (logs-based, native, Managed Prometheus) in one place. |

Grafana is a visualization preference, not an observability foundation. Alerts, SLOs, and
metric definitions belong in Cloud Monitoring regardless of which dashboard layer is used.

---

## Execution Plan

**PLAN ONLY — NOT EXECUTED.** Phases must be completed in order.

| Phase | Action | Precondition |
|---|---|---|
| 1 | Create logs-based metrics via GCP Console or `gcloud` | Cloud Logging queries validated (done) |
| 2 | Validate that each metric receives data by running a test Pub/Sub message and a silver refresh job execution | Cloud SQL must be started temporarily; stop immediately after |
| 3 | Create alert policies for metrics from Phase 1 | Metrics from Phase 1 receive data |
| 4 | Create Cloud Monitoring dashboard with the panels defined above | Metrics and alerts from Phases 1–3 exist |
| 5 | Document validation evidence for each metric in a new `docs/` file | Dashboard and alerts confirmed working |
| 6 | _(Optional)_ Add Grafana Cloud datasource pointing at Cloud Monitoring | Phases 1–5 complete |

---

## Suggested gcloud Commands

**NOT EXECUTED. Templates only. Verify all flags and syntax against `gcloud help` before running.**

The exact JSON schema for `--config-from-file` varies between `gcloud` versions. Prefer the
GCP Console UI for first creation to avoid YAML/JSON schema drift, then export the resulting
config with `gcloud logging metrics describe` for version control.

### Create a logs-based counter metric (worker processed)

```bash
# NOT EXECUTED — template only
gcloud logging metrics create worker_message_processed_count \
  --description="Count of successfully processed Pub/Sub messages by the worker" \
  --log-filter='resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.service="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="ok"' \
  --project=project-42987e01-2123-446b-ac7
```

### Create a logs-based distribution metric (worker latency)

```bash
# NOT EXECUTED — template only
# Distribution metrics with value extractors require --config-from-file (JSON/YAML).
# Use GCP Console for first creation; export with:
#   gcloud logging metrics describe worker_processing_latency_ms --format=json
# to capture the exact schema before committing to source control.
gcloud logging metrics create worker_processing_latency_ms \
  --description="Distribution of worker message processing latency in ms" \
  --log-filter='resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.service="rtdp-pubsub-worker"
jsonPayload.operation="process_message"' \
  --value-extractor='EXTRACT(jsonPayload.processing_time_ms)' \
  --project=project-42987e01-2123-446b-ac7
# Note: --value-extractor flag availability and exact syntax must be verified
# against installed gcloud version before execution.
```

### Create a logs-based counter metric (silver refresh success)

```bash
# NOT EXECUTED — template only
gcloud logging metrics create silver_refresh_success_count \
  --description="Count of successful silver refresh job executions" \
  --log-filter='resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.service="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="ok"' \
  --project=project-42987e01-2123-446b-ac7
```

### Create an alert policy (worker error count)

```bash
# NOT EXECUTED — template only
# Alert policies require a JSON/YAML condition file.
# Use GCP Console to create and then export with:
#   gcloud monitoring policies list --format=json
# The exact JSON schema for alert conditions changes between gcloud versions.
# Do not hand-author alert condition JSON without validating against the schema first.
gcloud monitoring policies create \
  --policy-from-file=alerting/worker-error-alert-policy.json \
  --project=project-42987e01-2123-446b-ac7
```

### Describe Cloud SQL state (read-only, no side effects)

```bash
# Safe to run — read-only, no Cloud SQL start
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)" \
  --project=project-42987e01-2123-446b-ac7
```

---

## Acceptance Criteria

Before this plan can be marked executed and validated:

- [ ] All 9 logs-based metrics listed in this plan are created in Cloud Monitoring
- [ ] Each metric receives at least one data point from a real worker or job log entry
- [ ] At least one `status=error` log entry is safely induced (e.g., by publishing a malformed
      Pub/Sub message in a non-production context) and the corresponding error counter increments
- [ ] Alert policies 1–5 are created and tested without false-positive spam
- [ ] Alert 6 (missing refresh) is **not created** until Cloud Scheduler exists
- [ ] Cloud Monitoring dashboard shows worker processing rate, error rate, latency, silver
      refresh success/failure, and silver refresh latency
- [ ] Cloud SQL final state is `NEVER / STOPPED` after any validation session that requires it

---

## What This Improves for B2B / Recruiting

| Before | After |
|---|---|
| Platform works end-to-end once in a validated session | Platform is observable in production; failures surface without manual intervention |
| Logs exist but require manual `gcloud logging read` to inspect | Metrics, alerts, and dashboards surface signal automatically |
| Silver refresh job must be triggered manually | Missing executions will eventually be detectable via absence-of-signal alert |
| "Observability" claim is backed by log queries only | "Observability" claim is backed by metrics, alerts, and a live dashboard |

**Specific recruiting / B2B signals this adds:**

- **Reliability mindset** — defining alert policies before incidents happen demonstrates
  SRE/Platform Engineer thinking, not just "it works on my machine."
- **GCP observability skills** — logs-based metrics, Cloud Monitoring alert policies, and
  Cloud Monitoring dashboards are core GCP Platform Engineer competencies.
- **Data Engineer production-readiness** — a data pipeline without alerting on processing
  errors or missing refreshes is not production-ready. This closes that gap.
- **Honest gap tracking** — documenting what is NOT YET done (Cloud Scheduler, Grafana,
  distributed traces, SLOs) demonstrates professional maturity over overclaiming.
- **Platform Engineer expectations** — Platform Engineers are expected to own the full
  observability stack: metrics, alerts, dashboards, runbooks. This plan is that stack.

---

## Out of Scope

The following are explicitly not part of this plan or this branch:

- No actual logs-based metrics creation (this branch is docs-only)
- No alert policy deployment
- No Cloud Monitoring dashboard creation
- No Grafana dashboard deployment
- No Cloud Scheduler configuration
- No BigQuery export or Dataflow pipeline
- No Terraform or Infrastructure-as-Code for Cloud Monitoring resources
- No load testing or high-throughput benchmark
- No distributed tracing (Cloud Trace)
- No SLO definition

---

## Next Recommended Branch

**Branch name:** `feat/cloud-logs-based-metrics`

**Objective:** Create the first safe logs-based metrics in Cloud Monitoring using validated
log filter expressions from this plan. Start with the four highest-signal counters:

1. `worker_message_processed_count` — confirms messages are being processed
2. `worker_message_error_count` — critical early warning for data loss
3. `silver_refresh_success_count` — confirms the bronze → silver path is running
4. `silver_refresh_error_count` — critical alert trigger for pipeline breakage

**Prerequisites before executing that branch:**
- Cloud SQL start is required to generate log entries for metric validation.
- Cloud SQL must be stopped immediately after validation.
- No metric creation command should be run until the log filter is verified by
  `gcloud logging read` returning a non-empty result for that filter.

**Validation sequence for that branch:**
1. Create each metric (Console or `gcloud`).
2. Run a test Pub/Sub message → confirm `worker_message_processed_count` increments.
3. Run the silver refresh job → confirm `silver_refresh_success_count` increments.
4. Check Cloud Monitoring metric explorer for each metric.
5. Document evidence in `docs/cloud-logs-based-metrics-validation.md`.
6. Stop Cloud SQL.
