# Load and Throughput Validation Plan

## Status

**PLAN ONLY — NOT EXECUTED**

This document defines the controlled load and throughput validation plan for the Real-Time Data
Platform GCP MVP. No events have been published, no Cloud SQL instance has been started, and no
validation runs have been executed. All statements are forward-looking and describe intended
future execution only.

---

## 1. Purpose

This plan addresses **Devil's Advocate gap #1**: the existing end-to-end validation evidence
([docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md)) covers only a single
published event per run. It does not demonstrate that the pipeline can ingest, process, and
serve a meaningful volume of events under observed conditions.

The purpose of this plan is to define a bounded, reproducible, evidence-generating protocol for
controlled throughput validation. Execution of this plan will produce:

- Pub/Sub publish counts at defined test sizes
- Cloud Run worker processing evidence via logs and metrics
- Cloud SQL bronze-layer insert and API readback evidence
- Silver refresh and gold aggregate readback evidence
- Cloud Logging filter evidence for the full test prefix
- Cloud Monitoring logs-based metric increment evidence
- Pub/Sub backlog drain evidence

This is a **plan only**. Throughput has not been validated. Do not claim any metric until
the corresponding evidence has been captured during a future execution run.

---

## 2. Scope

### In scope

- Controlled Pub/Sub throughput validation (100 / 1 000 / 5 000 events)
- Cloud Run worker processing validation (structured logs + metric increment)
- Cloud SQL bronze-layer insert and API `/events` readback
- Silver refresh after load via `rtdp-silver-refresh-job`
- Gold / API aggregate readback via `/aggregates/minute`
- Cloud Logging validation (structured `jsonPayload` log filter per prefix)
- Cloud Monitoring logs-based metric validation
  (`logging.googleapis.com/user/worker_message_processed_count`)
- Pub/Sub backlog observation before, during, and after processing window
- Cost-control protocol (Cloud SQL start/stop with final state confirmation)

### Out of scope

- Malformed or schema-invalid messages
- Retry / DLQ testing on the production push subscription
- Any event count beyond 5 000 per run
- Schema changes or migration testing
- IaC changes (Terraform or gcloud config mutations)
- Alert policy creation or dashboard creation
- Production benchmarking claims before execution evidence is captured
- Multi-region validation
- Autoscaling stress or concurrency limit testing

---

## 3. Test Sizes

| Size | Label | Purpose |
|---|---|---|
| **100 events** | Smoke-scale | Confirm end-to-end path works at minimal volume before increasing scale |
| **1 000 events** | Moderate throughput | Representative ingest batch; validates worker under sustained multi-second load |
| **5 000 events** | Bounded portfolio-scale | Maximum planned test size; demonstrates platform behaviour at the upper bound of this validation |

Test sizes are cumulative but independent. Each run must complete, be verified, and have Cloud
SQL stopped before the next size is attempted. Do not run multiple sizes concurrently.

---

## 4. Deterministic Event ID Prefixes

Each test run uses a unique deterministic prefix embedded in every `event_id`. The prefix
format is:

```
loadtest-<size>-<YYYYMMDDHHMMSS>-
```

| Test size | Example prefix |
|---|---|
| 100 events | `loadtest-100-20260601120000-` |
| 1 000 events | `loadtest-1000-20260601130000-` |
| 5 000 events | `loadtest-5000-20260601140000-` |

The timestamp component (`YYYYMMDDHHMMSS`) is the wall-clock time at which the producer run
begins and is recorded before the first message is published.

### Requirements for event IDs

- Every `event_id` in a run must be globally unique (e.g. `loadtest-100-20260601120000-00001`).
- The prefix must be recorded before execution begins.
- The prefix is the primary traceability key used for:
  - Cloud Logging filter (`jsonPayload.event_id` starts with prefix)
  - API readback filter (`/events` response inspection for prefix strings)
  - Cloud SQL query (`WHERE event_id LIKE 'loadtest-100-...'`)
  - Cloud Monitoring timeSeries context (log filter implicitly scoped by the structured log
    entries emitted during that prefix window)

Only one prefix may be active at a time. Do not publish a second size while a prior prefix is
still draining.

---

## 5. Producer Strategy

### Dry-run generator (local, no Pub/Sub)

`scripts/generate_load_test_events.py` generates deterministic `MarketEvent`-compatible JSON
Lines locally. It does not publish to Pub/Sub, access Cloud SQL, or mutate any GCP resource.
Use it to inspect event shape and verify event IDs before a live publishing run.

```bash
# Write 100 events to stdout
uv run python scripts/generate_load_test_events.py \
  --size 100 --prefix-timestamp 20260601120000

# Write 1 000 events to a file
uv run python scripts/generate_load_test_events.py \
  --size 1000 --prefix-timestamp 20260601130000 --output /tmp/events-1000.jsonl
```

No Pub/Sub publish count, worker processing log, or Cloud SQL insert is produced by this tool.
Evidence for those steps requires live publishing against the deployed pipeline (see below).

### Local JSONL validator (pre-publish evidence only)

`scripts/validate_load_test_events.py` validates a JSONL file produced by the dry-run generator
before any live publishing occurs. It is **local-only**: it does not publish to Pub/Sub, access
Cloud SQL, or mutate any GCP resource. Its output is a compact JSON report written to stdout (or
to a file via `--report-output`).

```bash
# Validate 100-event file and print report to stdout
uv run python scripts/validate_load_test_events.py \
  --input /tmp/events-100.jsonl \
  --size 100 \
  --prefix-timestamp 20260601120000

# Write report to a file
uv run python scripts/validate_load_test_events.py \
  --input /tmp/events-100.jsonl \
  --size 100 \
  --prefix-timestamp 20260601120000 \
  --report-output /tmp/report-100.json
```

The validator checks: event count, JSON validity, `event_id` sequence and prefix, `schema_version`,
`event_type`, allowed symbols, `event_timestamp` presence, duplicate `event_id` detection, and full
schema compliance via the worker's `validate_event` function. It exits non-zero on any failure.

This tool produces **pre-publish evidence only**. A passing report confirms that the generated
events are schema-valid and correctly sequenced; it does not validate throughput, worker
processing, or Cloud SQL ingestion. Those steps require live publishing (see below).

### Live publishing

The future live-publish producer script or command sequence must implement the following
approach.

### Event generation

- Generate deterministic JSON events conforming to the `MarketEvent` schema (`schema_version:
  "1.0"`, `event_id`, `symbol`, `event_type: "trade"`, `price`, `quantity`,
  `event_timestamp`).
- Use only symbols already accepted by the deployed worker (e.g. `BTCUSDT`, `ETHUSDT`). Do not
  introduce new symbol strings that may be rejected or that produce unexpected aggregate rows.
- Space `event_timestamp` values in stable 1-second increments across the test window to ensure
  that silver aggregates are distributed across meaningful minute buckets rather than collapsed
  into a single bucket.

### Publishing behaviour

- Publish only valid, schema-compliant messages. No malformed or partial-schema events in this
  plan.
- Throttle the publish rate to a controlled pace (e.g. no more than 50 messages per second)
  to avoid overwhelming the push subscription delivery pipeline and to produce interpretable
  metrics.
- Stop immediately on any Pub/Sub publish error. Do not continue publishing if the `messageId`
  is not returned for a message.
- Record the total published count and total elapsed publish time before any validation step
  begins.

### Pre-publish checklist

- Cloud SQL instance is in `RUNNABLE` state (confirmed via `gcloud sql instances describe`).
- Pub/Sub subscription `market-events-raw-worker-push` is in `ACTIVE` state.
- Cloud Run worker `rtdp-pubsub-worker` health check returns `{"status":"ok"}`.
- No prior load test prefix is still draining.

---

## 6. Expected Metrics and Evidence

For each completed run, the following evidence is expected:

| Evidence item | Expected value |
|---|---|
| Published event count | Equals intended test size (100 / 1 000 / 5 000) |
| `worker_message_processed_count` increment | Approximately equal to test size (within observed delivery window) |
| Worker structured logs (`status=ok`) | At least one log entry per published event containing the test prefix in `event_id` |
| API `/events` readback | Response contains records whose `event_id` starts with the run prefix |
| API `/aggregates/minute` readback | Response contains aggregate rows for the symbols and minute windows covered by the run |
| Silver refresh job status | Cloud Logging entry: `jsonPayload.status=ok`, `operation=refresh_market_event_minute_aggregates` |
| Pub/Sub backlog | Returns to zero or near-zero within the expected processing window after publish completes |

None of these values are pre-validated. They represent the intended evidence that a future
execution run must produce and document.

---

## 7. Safety Limits

The following hard limits apply to all execution runs under this plan:

- **Maximum test size:** 5 000 events. Do not exceed this bound.
- **No malformed messages.** Every published message must be schema-valid.
- **No retry / DLQ validation.** The production push subscription
  (`market-events-raw-worker-push`) has no DLQ configured (confirmed in
  [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md)). Malformed messages
  would retry indefinitely. This plan publishes only valid messages.
- **No parallel load runs.** Only one test size may be in-flight at any time.
- **One active prefix at a time.** Do not publish a second prefix before the first has drained
  and been verified.

### Abort conditions

Abort the run immediately (stop publishing, do not proceed to readback) if any of the following
are observed:

- `worker_message_error_count` Cloud Monitoring metric increases unexpectedly during the run.
- Pub/Sub backlog grows and does not begin draining within a reasonable observation window
  (e.g. 5 minutes after publish completes).
- Cloud Run errors appear in Cloud Logging for `rtdp-pubsub-worker` during the run.
- Cloud SQL cannot be confirmed as `RUNNABLE` before publish, or cannot be set to `NEVER` /
  confirmed as `STOPPED` after the run.
- Any individual publish call fails to return a `messageId`.

On abort, record the abort condition and the last known published count. Do not attempt the
same run again without first diagnosing and resolving the abort cause.

---

## 8. Cloud SQL Start / Stop Protocol

Cloud SQL (`rtdp-postgres`) must be in `NEVER / STOPPED` state at all times outside of an
active validation run. The following operational protocol describes the required sequence.
Exact start/stop commands belong in the future execution branch, not in this plan document.

### Before execution

1. **Verify initial Cloud SQL state.** Query the instance describe API (read-only) and confirm
   the activation policy is `NEVER` and the instance state is `STOPPED`. Do not proceed if the
   state is unexpected or if the instance is already running.

2. **Start Cloud SQL** by setting the activation policy to `ALWAYS` via the appropriate GCP
   management interface. This step must be performed immediately before publishing begins and
   must not be performed on an idle or standing basis.

3. **Confirm `RUNNABLE` state** by querying the instance describe API again (read-only) and
   waiting until the state is `RUNNABLE`. Do not publish any events while the instance is still
   starting.

### During execution

4. Execute the bounded load validation: publish the planned event count, observe worker
   structured logs and Pub/Sub backlog.

5. After publish completes, wait for the Pub/Sub backlog to drain before proceeding (see
   section 9).

6. **Trigger the silver refresh job** (`rtdp-silver-refresh-job`) only after all events have
   been ingested and the Pub/Sub backlog has drained. Use the Cloud Run Job execution interface
   and wait for the job to complete before proceeding to readback.

7. Perform API readback, Cloud Logging filter, and Cloud Monitoring metric validation (see
   sections 10–12).

### After execution

8. **Immediately set the Cloud SQL activation policy back to `NEVER`** via the appropriate GCP
   management interface. This must be the first action after readback completes, before closing
   the execution window.

9. **Confirm final state** by querying the instance describe API (read-only) and recording the
   output. Acceptance requires `activationPolicy: NEVER` and `state: STOPPED`.

Do not leave Cloud SQL running after the validation window closes. This is a hard cost-control
requirement. The final state confirmation must be captured in the execution evidence document.

---

## 9. Pub/Sub Backlog Observation

The push subscription `market-events-raw-worker-push` must be observed at the following points
during each run. Backlog is read from the Cloud Monitoring metric
`pubsub.googleapis.com/subscription/num_undelivered_messages` or from the subscription
describe output.

| Observation point | Expected value | Purpose |
|---|---|---|
| Before publish | 0 (or near-zero) | Confirm clean starting state |
| Immediately after publish completes | Approximately equal to test size | Confirm messages were accepted |
| During worker drain window | Decreasing | Confirm worker is processing |
| After expected processing window | Near-zero or zero | Confirm successful drain |
| Final backlog check | 0 | Acceptance criterion |

The observation window for drain depends on test size. For 5 000 events, allow at least 10
minutes after publish completes before asserting a final backlog value.

If the backlog does not begin draining within 5 minutes of publish completion, treat this as an
abort condition (see section 7).

---

## 10. Worker Processed Count Metric Validation

After each run, query the Cloud Monitoring REST API for the
`logging.googleapis.com/user/worker_message_processed_count` timeSeries.

The `gcloud monitoring` CLI does not expose `time-series` subcommands in the installed SDK
version (confirmed in [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md)).
Use the Cloud Monitoring REST API directly with a Bearer token:

```
https://monitoring.googleapis.com/v3/projects/<PROJECT_ID>/timeSeries
  ?filter=metric.type="logging.googleapis.com/user/worker_message_processed_count"
  &interval.startTime=<START>
  &interval.endTime=<END>
```

The query window should span from just before publish began to at least 15 minutes after the
backlog drain is confirmed, to capture all DELTA intervals.

Expected evidence: the sum of all `int64Value` datapoints in the response within the run
window is approximately equal to the test size. Due to DELTA aggregation windows, the total
may be distributed across multiple 1-minute intervals. Count the sum, not just the peak.

---

## 11. API Readback Validation

After the silver refresh job completes, validate the pipeline outputs via the Cloud Run API.

### Bronze layer — `/events`

Query the `/events` endpoint (refer to
[docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) for the validated API URL
and endpoint pattern). Filter the response for records whose `event_id` starts with the run
prefix. Confirm:

- At least one record is present.
- For a complete run, the count should approach the test size (subject to the endpoint's
  default page limit — use `limit` parameter or paginate as needed).
- Each record includes `source_topic: "market-events-raw"` and an `ingested_at` timestamp.

### Silver / aggregate layer — `/aggregates/minute`

Query the `/aggregates/minute` endpoint. Confirm:

- At least one aggregate row is present for each symbol used in the test run.
- Rows reflect the `event_timestamp` minute buckets generated by the producer.
- If the silver refresh job completed successfully, the most recent `event_timestamp` in the
  bronze layer should appear in at least one aggregate row.

Do not invent exact response structures here. Refer to the validated API evidence in
[docs/silver-refresh-job-validation.md](silver-refresh-job-validation.md) for the expected
response shape.

---

## 12. Cloud Logging Validation

After each run, validate Cloud Logging for the expected structured log entries. Use the
following conceptual filters.

### Worker message processing (success path)

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="ok"
```

Refine with the test prefix to scope results to the specific run:

```
jsonPayload.event_id =~ "^loadtest-<size>-<YYYYMMDDHHMMSS>-"
```

Expected: at least one log entry per published event. For a complete run, the count should
approach the test size.

### Worker message processing (error path — monitoring only)

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="error"
```

This filter should return **zero results** during a valid load test run. Any error entries
are an abort signal (see section 7).

### Silver refresh job (success path)

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="ok"
```

Expected: one log entry per silver refresh job execution triggered during the run.

---

## 13. Cost-Control Guardrails

The following cost-control requirements apply to all execution runs:

- **Cloud SQL must not remain running after validation.** Final state must be
  `activationPolicy: NEVER` / `state: STOPPED` before the execution branch is closed.
- **Final evidence must include the Cloud SQL state output.** Record the output of
  `gcloud sql instances describe rtdp-postgres --format="value(settings.activationPolicy,state)"`
  in the execution evidence document.
- **Bounded event counts only.** Do not exceed 5 000 events per run. Do not re-run a size
  without a documented reason.
- **Avoid repeated test execution.** Each test size (100 / 1 000 / 5 000) should be run once
  per evidence document. Do not run idle soak tests or sustained load loops.
- **No autoscaling stress.** Do not deliberately trigger Cloud Run autoscaling beyond normal
  push subscription delivery behaviour. This plan does not test autoscaling limits.
- **One active Cloud SQL window per run.** Do not start Cloud SQL for exploratory queries
  between test sizes. Batch all readback validation within the same Cloud SQL window as the
  corresponding load run.

---

## 14. Acceptance Criteria

### 100-event run

| Criterion | Required evidence |
|---|---|
| Publish count | 100 messages confirmed published (100 `messageId` values returned) |
| Worker metric evidence | `worker_message_processed_count` timeSeries sum ≈ 100 within run window |
| Log evidence | Cloud Logging returns ≥ 1 `status=ok` entry for the `loadtest-100-` prefix |
| API readback | `/events` returns ≥ 1 record with `event_id` matching prefix |
| Silver refresh evidence | Silver refresh job completes with `status=ok` log entry |
| Aggregate readback | `/aggregates/minute` returns ≥ 1 row for the test symbols |
| Cloud SQL final state | `NEVER   STOPPED` confirmed after run |

### 1 000-event run

| Criterion | Required evidence |
|---|---|
| Publish count | 1 000 messages confirmed published |
| Worker metric evidence | `worker_message_processed_count` timeSeries sum ≈ 1 000 within run window |
| Log evidence | Cloud Logging returns `status=ok` entries for the `loadtest-1000-` prefix; zero `status=error` entries for this prefix |
| API readback | `/events` returns records with prefix-matching `event_id` values across multiple pages if needed |
| Silver refresh evidence | Silver refresh job completes with `status=ok` log entry |
| Aggregate readback | `/aggregates/minute` returns aggregate rows spanning multiple minute buckets |
| Cloud SQL final state | `NEVER   STOPPED` confirmed after run |

### 5 000-event run

| Criterion | Required evidence |
|---|---|
| Publish count | 5 000 messages confirmed published |
| Worker metric evidence | `worker_message_processed_count` timeSeries sum ≈ 5 000 within run window |
| Log evidence | Cloud Logging returns `status=ok` entries for the `loadtest-5000-` prefix; zero `status=error` entries for this prefix |
| API readback | `/events` returns records with prefix-matching `event_id` values |
| Silver refresh evidence | Silver refresh job completes with `status=ok` log entry |
| Aggregate readback | `/aggregates/minute` reflects load across multiple symbol/minute combinations |
| Cloud SQL final state | `NEVER   STOPPED` confirmed after run |
| Pub/Sub backlog final | Subscription backlog returns to 0 within the observation window |

---

## 15. What Can Be Claimed After Execution

The following claims are appropriate after evidence has been captured for a given test size:

- Controlled bounded throughput validation completed up to N events (where N is the largest
  validated test size).
- The Cloud Run worker (`rtdp-pubsub-worker`) processed N valid Pub/Sub messages under
  observed GCP managed-service conditions.
- Cloud SQL `bronze.market_events` ingested N records and the API confirmed readback for the
  test prefix.
- Silver refresh job produced aggregate rows after load, confirmed via `/aggregates/minute`.
- Cloud Logging structured log evidence captured for all processed events with `status=ok`.
- Cloud Monitoring `worker_message_processed_count` metric reflected the load volume within the
  DELTA aggregation window.
- Cloud SQL was started only for the validation window and returned to `NEVER / STOPPED`.
- Pub/Sub backlog drained to zero within the expected window after publish completed.

---

## 16. What Cannot Be Claimed After Execution

Even after all three test sizes are validated, the following claims remain out of scope:

- Unlimited or unbounded scale — this plan tests only up to 5 000 events.
- Enterprise-grade stress testing or production-equivalent load simulation.
- Production SLO or SLA for latency, throughput, or error rate.
- DLQ or retry safety under failure conditions — this plan publishes only valid messages.
- Sustained high-throughput benchmark — each run is a bounded burst, not a continuous load.
- Multi-region resilience or failover behaviour.
- Autoscaling limit characterisation or cold-start latency under load.
- BigQuery or Dataflow throughput — neither is in scope for this plan.
- Worker concurrency ceiling — Cloud Run concurrency limits under load are not tested.

---

## 17. Recruiter and B2B Positioning

This validation plan matters beyond technical completeness.

**The gap it closes:** A single-event end-to-end test proves the plumbing works. It does not
demonstrate that the platform holds up when you send it a meaningful volume of events. Recruiters
and technical reviewers evaluating a real-time data platform expect to see evidence of
throughput, not just connectivity.

**What execution of this plan demonstrates:**
- The project is moving from a toy pipeline to a measured operational platform.
- The team understands that throughput, observability, and cost discipline are inseparable: load
  tests do not count unless they are bounded, traced, and cleaned up.
- Evidence is captured end-to-end: publish counts, worker metrics, structured logs, API
  readback, silver aggregates, and Cloud SQL cost-control state — all for the same traceable
  prefix.

**What it does not overclaim:**
- This plan is explicitly bounded (≤ 5 000 events) and scoped to the deployed GCP MVP.
- The plan does not assert production SLAs or enterprise scale.
- All statements are evidence-safe: nothing is claimed until the corresponding evidence document
  is written and merged.

The combination of end-to-end validation evidence, observability evidence (logs-based metrics,
structured logs), and this bounded throughput evidence creates a coherent picture of a platform
that has been built with operational discipline — not just connectivity.

---

## Related Documents

| Document | Relationship |
|---|---|
| [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) | Single-event end-to-end baseline this plan extends |
| [docs/silver-refresh-job-validation.md](silver-refresh-job-validation.md) | Silver refresh execution evidence used by post-load readback step |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Datapoint query method and Cloud Monitoring API usage reference |
| [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) | Confirms no DLQ on production subscription; informs valid-messages-only constraint |
| [docs/cloud-error-counter-validation-plan.md](cloud-error-counter-validation-plan.md) | Error counter plan; abort conditions in this plan reference that work |
| [docs/cloud-observability-metrics-plan.md](cloud-observability-metrics-plan.md) | Logs-based metrics context |
| [docs/load-test-local-sample-evidence.md](load-test-local-sample-evidence.md) | Local pre-publish sample evidence: dry-run generator and validator output for the 100-event smoke-scale size (no Pub/Sub, no Cloud SQL) |
| [docs/load-test-100-cloud-runbook.md](load-test-100-cloud-runbook.md) | Operational runbook for the first controlled live 100-event cloud load test |
| [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) | Accepted 100-event cloud evidence — all acceptance criteria met |
| [docs/load-test-1000-cloud-runbook.md](load-test-1000-cloud-runbook.md) | Operational runbook for the 1000-event cloud load test (not yet executed) |
