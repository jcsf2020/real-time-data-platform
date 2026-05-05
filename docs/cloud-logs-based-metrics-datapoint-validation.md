# Cloud Logs-Based Metrics Datapoint Validation

## Status

Validated on: 2026-05-05

Actual Cloud Monitoring timeSeries datapoints are confirmed for both success counters:
`worker_message_processed_count` and `silver_refresh_success_count`. Each metric returned at
least one positive `int64Value: 1` datapoint within the query window, confirming that Cloud
Monitoring ingested real signal from the underlying log entries.

---

## Validation Objective

Prove that the Cloud Monitoring API exposes actual timeSeries records (not just metric
descriptor configuration) for the two success logs-based counters created in the prior branch.
A positive datapoint in a DELTA INT64 metric confirms that at least one matching log entry was
ingested and aggregated into a monitoring interval.

---

## Prior State

- [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md)
  created and confirmed the configuration of all four logs-based metrics
  (`worker_message_processed_count`, `worker_message_error_count`,
  `silver_refresh_success_count`, `silver_refresh_error_count`).
- This document validates actual Cloud Monitoring datapoints for the two **success** counters.
  The error counter datapoints are deferred to a subsequent branch once a safe synthetic error
  path is defined.

---

## Pre-Check State

| Check | Result |
|---|---|
| Tests | 75 passed |
| Ruff | All checks passed |
| Cloud SQL | NEVER STOPPED |

---

## gcloud CLI Limitation

The `gcloud monitoring` command group does not expose `metric-descriptors` or `time-series`
subcommands in the installed SDK version.

**Command run:**

```bash
gcloud monitoring --help | sed -n '1,120p'
```

**Available groups confirmed:**

- `dashboards`
- `policies`
- `snoozes`
- `uptime`

**Not available:**

- `metric-descriptors`
- `time-series`

Because no `gcloud` CLI path exists for reading timeSeries, the Cloud Monitoring REST API was
queried directly using a Bearer token obtained from `gcloud auth print-access-token`. This is a
read-only operation — no resources were created or modified.

---

## Metrics Queried

Confirmed present via `gcloud logging metrics list` before the datapoint query:

**Command:**

```bash
gcloud logging metrics list \
  --project=project-42987e01-2123-446b-ac7 \
  --filter='name:worker_message_processed_count OR name:silver_refresh_success_count' \
  --format="table(name,metricDescriptor.metricKind,metricDescriptor.valueType)"
```

**Output:**

```
NAME                            METRIC_KIND  VALUE_TYPE
silver_refresh_success_count    DELTA        INT64
worker_message_processed_count  DELTA        INT64
```

Both metrics are `DELTA` / `INT64` counters, consistent with the prior branch.

---

## API Query Method

TimeSeries were queried through the Cloud Monitoring REST API using an OAuth token from
`gcloud`. This is read-only — no dashboards, alert policies, or metric descriptors were
created.

**Command:**

```bash
START_TIME="$(date -u -v-6H +%Y-%m-%dT%H:%M:%SZ)" && \
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)" && \
TOKEN="$(gcloud auth print-access-token)" && \
echo "window=${START_TIME}..${END_TIME}" && \
curl -s \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/timeSeries?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fworker_message_processed_count%22&interval.startTime=${START_TIME}&interval.endTime=${END_TIME}" && \
echo && \
curl -s \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/timeSeries?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fsilver_refresh_success_count%22&interval.startTime=${START_TIME}&interval.endTime=${END_TIME}" && \
echo
```

**Query window:**

```
2026-05-05T10:42:23Z..2026-05-05T16:42:23Z
```

---

## worker_message_processed_count Datapoint Evidence

**Metric:**

| Field | Value |
|---|---|
| `metric.type` | `logging.googleapis.com/user/worker_message_processed_count` |
| `metricKind` | `DELTA` |
| `valueType` | `INT64` |
| `resource.type` | `cloud_run_revision` |

**Resource labels:**

| Label | Value |
|---|---|
| `location` | `europe-west1` |
| `project_id` | `project-42987e01-2123-446b-ac7` |
| `service_name` | `rtdp-pubsub-worker` |
| `revision_name` | `rtdp-pubsub-worker-00003-dh6` |
| `configuration_name` | `rtdp-pubsub-worker` |

**Positive datapoint:**

| Interval start | Interval end | int64Value |
|---|---|---|
| `2026-05-05T15:25:23Z` | `2026-05-05T15:26:23Z` | **1** |

**Surrounding zero points (context):**

| Interval start | Interval end | int64Value |
|---|---|---|
| `2026-05-05T15:23:23Z` | `2026-05-05T15:24:23Z` | 0 |
| `2026-05-05T15:24:23Z` | `2026-05-05T15:25:23Z` | 0 |
| `2026-05-05T15:26:23Z` | `2026-05-05T15:27:23Z` | 0 |

The positive datapoint is isolated — not a sustained stream — which is consistent with a
single Pub/Sub message being processed during that one-minute window.

---

## silver_refresh_success_count Datapoint Evidence

**Metric:**

| Field | Value |
|---|---|
| `metric.type` | `logging.googleapis.com/user/silver_refresh_success_count` |
| `metricKind` | `DELTA` |
| `valueType` | `INT64` |
| `resource.type` | `cloud_run_job` |

**Resource labels:**

| Label | Value |
|---|---|
| `location` | `europe-west1` |
| `project_id` | `project-42987e01-2123-446b-ac7` |
| `job_name` | `rtdp-silver-refresh-job` |

**Positive datapoint:**

| Interval start | Interval end | int64Value |
|---|---|---|
| `2026-05-05T15:27:23Z` | `2026-05-05T15:28:23Z` | **1** |

**Surrounding zero points (context):**

| Interval start | Interval end | int64Value |
|---|---|---|
| `2026-05-05T15:25:23Z` | `2026-05-05T15:26:23Z` | 0 |
| `2026-05-05T15:26:23Z` | `2026-05-05T15:27:23Z` | 0 |
| `2026-05-05T15:28:23Z` | `2026-05-05T15:29:23Z` | 0 |

The positive datapoint is isolated, consistent with one silver refresh job execution completing
successfully during that one-minute window.

---

## Cost-Control State

Cloud SQL (`rtdp-postgres`) was **NEVER STOPPED** during this validation. No Cloud SQL start
was required — the entire validation is read-only against Cloud Monitoring and Cloud Logging
APIs. No database connections were opened.

---

## What This Proves

- The Cloud Monitoring REST API exposes actual timeSeries records for both logs-based metrics,
  confirming that log-to-metric ingestion is active end-to-end.
- `worker_message_processed_count` has at least one positive datapoint (`int64Value: 1`) in
  the `cloud_run_revision` resource for `rtdp-pubsub-worker`.
- `silver_refresh_success_count` has at least one positive datapoint (`int64Value: 1`) in the
  `cloud_run_job` resource for `rtdp-silver-refresh-job`.
- Both metrics are `DELTA` / `INT64`, consistent with their configured metric descriptors.
- Positive datapoints align with the post-metric signal generation performed in the prior
  branch (`docs/cloud-logs-based-metrics-validation.md`).
- The entire validation was read-only and required no Cloud SQL start, no deployments, and no
  GCP write commands.

---

## What This Does Not Prove Yet

- Datapoints for `worker_message_error_count` or `silver_refresh_error_count` (error counters
  require a safe synthetic error path to be defined first).
- Alert policy configuration or alert firing.
- Cloud Monitoring dashboard existence or layout.
- Grafana integration.
- Latency distribution metrics.
- Scheduler / missing-execution detection metrics.

---

## Honest Architecture Claim

> Cloud Monitoring datapoints validated for worker and silver refresh success counters.

Alerting, dashboards, and error counter datapoints are not yet validated.

---

## Next Recommended Branch

**Branch:** `docs/cloud-error-counter-validation-plan`

**Objective:** Plan a safe synthetic error validation path for:

- `worker_message_error_count`
- `silver_refresh_error_count`

Do not generate error traffic until the safe path is defined. The plan should specify the
exact log entry that triggers each filter, the minimum blast radius (ideally a single
controlled Pub/Sub message or job execution), and the rollback / cleanup steps.
