# Back-Pressure and Queue-Depth Analysis

**Status:** ANALYSIS — docs-only; no GCP resources created; no Terraform apply; no messages published  
**Branch:** `docs/back-pressure-queue-depth-analysis`  
**Date:** 2026-05-24

---

## 1. Current Ingestion Architecture and Back-Pressure Points

### Data flow

```text
Event source
  -> Pub/Sub topic: market-events-raw
      -> Push subscription: market-events-raw-worker-push
          -> Cloud Run worker: rtdp-pubsub-worker
              -> Cloud SQL PostgreSQL: rtdp-postgres (bronze.market_events)
                  -> BigQuery analytical tier (incremental append via separate scheduler)
```

The validated path is Pub/Sub push → Cloud Run → Cloud SQL. BigQuery ingestion is a separate
batch path (Cloud Scheduler → Cloud Run Job → BigQuery MERGE) and is not part of the
real-time pressure chain.

### Back-pressure points

| Point | Mechanism | Risk at saturation |
|---|---|---|
| Pub/Sub subscription queue | Message retention window (600s); unacked message backlog | Messages expire unredelivered if backlog age exceeds retention; producer has no synchronous feedback |
| Cloud Run worker concurrency | `containerConcurrency: 1`; at most one message processed per instance revision | Worker queues requests; excess messages remain in Pub/Sub or are timed-out by ack deadline |
| Cloud Run worker max instances | Template annotation `autoscaling.knative.dev/maxScale: 1` | Only one worker instance ever runs; no horizontal scale-out under sustained load |
| Cloud SQL write latency | Synchronous INSERT to `bronze.market_events`; worker holds the message until the write completes or fails | Slow writes extend per-message latency; if write exceeds ack deadline (30s), Pub/Sub redelivers the message |
| Cloud SQL connectivity | Worker uses Cloud SQL connector attachment; Cloud SQL must be RUNNING | If Cloud SQL is STOPPED (the default operational state), all writes fail immediately; messages are retried and eventually routed to DLQ |

The most constrained point in normal operation is **Cloud Run worker concurrency combined with
max instances = 1**. This configuration processes one message at a time in a single instance.
Under a burst of messages the subscription backlog grows until the single worker processes
through it. The system has been validated at 50,000 events (bounded burst) and at a steady
rate of 10 events per second for 30 minutes under these constraints.

---

## 2. Pub/Sub Delivery Semantics

### Confirmed configuration

From `docs/production-pubsub-dlq-evidence.md` (validated 2026-05-06):

| Parameter | Value |
|---|---|
| Subscription | `market-events-raw-worker-push` |
| Type | Push (HTTPS to Cloud Run worker endpoint) |
| `ackDeadlineSeconds` | 30 |
| `messageRetentionDuration` | 600s (10 minutes) |
| `deadLetterTopic` | `projects/.../topics/market-events-raw-dlq` |
| `maxDeliveryAttempts` | 5 |
| `retryPolicy.minimumBackoff` | 10s |
| `retryPolicy.maximumBackoff` | 60s |

### Ack deadline behaviour

The ack deadline is **30 seconds**. If the Cloud Run worker does not return HTTP 200 within
30 seconds of receiving a push delivery, Pub/Sub treats the message as unacknowledged and
schedules a redeliver.

The worker's startup probe has a `periodSeconds: 240` and `timeoutSeconds: 240` configuration.
Cold-start latency on a scaled-to-zero instance can exceed the 30-second ack deadline before the
instance is ready to serve the first message. Under repeated cold starts the same message may be
delivered, timed out, and redelivered multiple times before the worker is consistently warm.

### Retry and redelivery

Each delivery attempt that does not receive an ack increments the delivery counter. The retry
backoff starts at 10s and caps at 60s. After 5 delivery attempts the message is forwarded to
the `market-events-raw-dlq` topic.

The retry sequence for a failing message is approximately:

```
Attempt 1: deliver → ack deadline expires (30s) → wait ≥10s
Attempt 2: deliver → ack deadline expires (30s) → wait ≤60s
Attempt 3: deliver → ack deadline expires (30s) → wait ≤60s
Attempt 4: deliver → ack deadline expires (30s) → wait ≤60s
Attempt 5: deliver → ack deadline expires (30s) → route to DLQ
```

Total elapsed time from first delivery to DLQ routing: approximately 3–5 minutes depending on
backoff jitter.

### Backlog behaviour

Pub/Sub maintains an internal delivery backlog for the push subscription. Under normal operation
the backlog is bounded by the rate at which the Cloud Run worker processes and acks messages.

The `messageRetentionDuration` of 600s (10 minutes) is the maximum age of any unacked or
undelivered message on the subscription. A message that sits undelivered in the backlog longer
than this duration is **expired** without delivery. Because the subscription is push-type,
Pub/Sub controls delivery pacing; the worker cannot pull messages at its own rate — it receives
them as HTTPS POST requests at whatever rate Pub/Sub chooses to send.

**Important:** the `messageRetentionDuration` of 600s is short. Under a sustained ingestion
pause (e.g. worker unavailable for 10 minutes), the backlog can age out entirely, producing
permanent message loss for any message that was never delivered before the window closed.
The topic itself may retain messages longer if `topic.messageRetentionDuration` is configured
separately; this has not been confirmed in the current evidence base.

### At-least-once delivery

Pub/Sub push delivery is **at-least-once**. The worker may receive the same message more than
once in normal operation, particularly near the ack deadline boundary or after a worker restart.
The current worker implements idempotent writes using `event_id` as a uniqueness key in
`bronze.market_events`. Duplicate delivery does not produce duplicate rows if the worker
processes the second delivery after the first has been committed.

Exactly-once semantics are **not claimed** for the current architecture.

---

## 3. Cloud Run Worker Scaling Limits, Concurrency, and Saturation

### Observed configuration

From `docs/evidence/terraform-phase-0-inventory/cloudrun-service-rtdp-pubsub-worker.json`
(inventory captured from production service):

| Parameter | Value |
|---|---|
| Service `run.googleapis.com/maxScale` | 20 (service-level annotation) |
| Template `autoscaling.knative.dev/maxScale` | **1** |
| `spec.template.spec.containerConcurrency` | **1** |
| CPU limit | 1000m (1 vCPU) |
| Memory limit | 512Mi |
| Startup probe | `tcpSocket: 8080`, `periodSeconds: 240`, `failureThreshold: 1` |

The template-level `autoscaling.knative.dev/maxScale: 1` annotation is the effective scaling
ceiling. Only **one worker instance** can run at any time. The service-level annotation of 20
is a historical or UI artefact; the active revision cap is 1.

With `containerConcurrency: 1` and `maxScale: 1`, the worker processes **one message at a time
in a single instance**. This is a sequential single-channel ingestion path.

### Implication for throughput

Processing throughput is bounded by:

```
max_throughput ≈ 1 / (per_message_processing_latency_seconds)
```

The steady-state validation evidence (10 events/sec for 30 minutes, 18,000 events; see
`docs/steady-state-10eps-30min-cloud-validation-evidence.md`) indicates the worker can sustain
approximately 10 messages per second at this configuration. Burst tests at 50,000 events
(see `docs/load-test-50000-cloud-evidence.md`) were published rapidly and processed by the
single worker over time; the Pub/Sub backlog absorbed the burst within the 10-minute
`messageRetentionDuration` window.

### Saturation behaviour

If inbound message rate exceeds the single worker's processing rate, the following sequence
occurs:

1. Pub/Sub push backlog grows; `subscription/num_undelivered_messages` increases.
2. Pub/Sub may throttle push delivery to the worker endpoint if the worker is slow to respond
   (observing HTTP 429 or delivery backpressure internally).
3. If messages remain unacked beyond 30s, Pub/Sub redelivers; the worker receives duplicate
   deliveries while still processing earlier messages.
4. If the backlog age approaches the 600s `messageRetentionDuration`, messages begin to expire.
5. Messages that fail five delivery attempts are routed to the DLQ.

Under sustained overload the worker **does not crash gracefully on its own** — messages simply
accumulate in the Pub/Sub backlog until they expire or are routed to the DLQ. The single
instance constraint means there is no automatic horizontal relief.

**No sustained overload test has been executed.** The 50,000-event bounded test and the
10 eps/30-minute steady-state test represent the upper bound of validated throughput for the
current configuration.

---

## 4. Detecting Backlog Growth with Cloud Monitoring

### Key Pub/Sub metrics

| Metric | Description | Alarm threshold guidance |
|---|---|---|
| `pubsub.googleapis.com/subscription/num_undelivered_messages` | Messages in the subscription backlog not yet delivered or acked | Alert if > O(1000) for more than 2–3 minutes |
| `pubsub.googleapis.com/subscription/oldest_unacked_message_age` | Age in seconds of the oldest unacked message | Alert if > 120s (approaching ack deadline + one retry cycle) |
| `pubsub.googleapis.com/subscription/num_outstanding_messages` | Messages delivered but not yet acked | Alert if growing and not draining |
| `pubsub.googleapis.com/topic/send_message_operation_count` | Inbound publish rate on the topic | Baseline for rate comparison |

### Key Cloud Run worker metrics

| Metric | Description | Alarm threshold guidance |
|---|---|---|
| `logging.googleapis.com/user/worker_message_error_count` | Custom logs-based metric for worker processing errors | Alert on any non-zero rate |
| `logging.googleapis.com/user/worker_message_processed_count` | Custom logs-based metric for successfully processed messages | Use as throughput baseline |
| `run.googleapis.com/request_latencies` | Cloud Run request latency distribution | Alert if p95 > 20s (approaching ack deadline) |
| `run.googleapis.com/request_count` (5xx) | HTTP error responses from the worker | Alert on elevated 5xx rate |

### DLQ metrics

| Metric | Description | Alarm threshold guidance |
|---|---|---|
| `pubsub.googleapis.com/topic/send_message_operation_count` (DLQ topic) | Messages arriving on `market-events-raw-dlq` | Alert on any sustained non-zero rate |
| `pubsub.googleapis.com/subscription/num_undelivered_messages` (DLQ subscription) | If a DLQ subscription exists for inspection | Alert on growth |

### Current observability state

Four logs-based metrics are currently configured and have confirmed datapoints:
`worker_message_processed_count`, `worker_message_error_count`,
`silver_refresh_success_count`, `silver_refresh_error_count`.

Alert policies for `worker_message_error_count` and `silver_refresh_error_count` exist in
Cloud Monitoring (see `docs/cloud-alert-policies-evidence.md`). The existing alert policies
do not include Pub/Sub backlog metrics; see Section 8 for proposed additions.

---

## 5. Failure Modes

### 5.1 Slow Cloud SQL writes

**Trigger:** Cloud SQL is running but experiencing elevated write latency (connection pool
exhaustion, CPU throttle, disk I/O stall).

**Behaviour:** The worker holds the Pub/Sub push connection open until the INSERT commits.
If the write takes > 30s the ack deadline expires; Pub/Sub treats the message as undelivered
and schedules a retry. The worker may complete the first write and then receive the same
message again — the idempotent `event_id` key prevents a duplicate row but the worker
executes a redundant INSERT that returns 0 rows affected.

**Detection:** Elevated `run.googleapis.com/request_latencies`, 5xx responses if the worker
returns an error rather than hanging, growing `oldest_unacked_message_age`.

### 5.2 Worker crash or container restart

**Trigger:** Worker exits (OOM, uncaught exception, runtime error, startup probe failure).

**Behaviour:** Cloud Run terminates the container. Any messages currently being processed are
not acked. Pub/Sub redelivers after the ack deadline. Cold-start time for the new instance
is bounded by the startup probe timeout (240s). During cold start, Pub/Sub may deliver
messages before the instance is ready, resulting in HTTP 503 responses that are treated as
failed deliveries and counted toward the `maxDeliveryAttempts` counter.

**Detection:** `run.googleapis.com/request_count` (5xx), `worker_message_error_count` metric,
Cloud Logging `severity=ERROR` entries from the worker.

### 5.3 Malformed messages

**Trigger:** A publisher sends a payload that fails schema validation in the worker (invalid
JSON, missing required fields, type mismatch against `MarketEvent` contract).

**Behaviour:** The worker parses the payload, detects schema violation, logs an error, and
returns HTTP 200 (explicit ack without writing to Cloud SQL). This is the current validated
behaviour from `docs/dlq-malformed-message-validation-evidence.md`. The message is consumed
and not redelivered. Alternatively, if the worker returns non-200 for a malformed message,
Pub/Sub retries up to `maxDeliveryAttempts=5`, then routes to DLQ.

**Note:** The malformed-message validation evidence observed multiple DLQ entries for the
same test marker (delivery counts 5–16), indicating that DLQ routing is not exactly-once.
The DLQ may receive the same original message more than once.

### 5.4 DLQ routing

**Trigger:** A message fails delivery 5 times.

**Behaviour:** Pub/Sub writes the message to `market-events-raw-dlq`. The message is
available for inspection via any subscription attached to the DLQ topic. No automatic
remediation is configured. The DLQ topic currently has no monitoring alert attached.

**Operational requirement:** DLQ growth must be detected by monitoring (see Section 8).
A manual DLQ inspection and drain runbook exists; see `docs/production-pubsub-dlq-runbook.md`.

### 5.5 Duplicate delivery

**Trigger:** Ack deadline expires before the worker commits the write; Pub/Sub redelivers.

**Behaviour:** The worker receives the same message payload again. If the `event_id` is
already present in `bronze.market_events`, the INSERT returns 0 rows affected (idempotent).
The worker returns HTTP 200 and the duplicate delivery is acked. No data anomaly results
in Cloud SQL.

For BigQuery, the incremental append job uses a MERGE with `event_id` as the unique key
(see `docs/bigquery-incremental-append-evidence.md`). Duplicate rows in `market_events_raw`
are not introduced if the append job runs after deduplication in Cloud SQL. If Cloud SQL is
not involved (e.g. in a future direct Dataflow-to-BigQuery path), separate deduplication
logic is required.

---

## 6. Safe Operational Response

The following response steps are ordered by escalation level. **Do not start Cloud SQL or
activate schedulers outside a bounded validation window.**

### 6.1 Detecting an incident

1. Check `subscription/oldest_unacked_message_age` in Cloud Monitoring. Values > 120s indicate
   delivery stall.
2. Check `subscription/num_undelivered_messages`. Values growing over time indicate the worker
   is not consuming at inbound rate.
3. Check Cloud Run worker logs in Cloud Logging for `severity=ERROR` entries.
4. Check `worker_message_error_count` metric for sustained non-zero rate.

### 6.2 Scheduler and Cloud SQL state

- **Do not activate Cloud Scheduler** (`rtdp-silver-refresh-scheduler` or
  `rtdp-bigquery-append-scheduler`) outside a bounded validation window. Both schedulers
  are kept PAUSED by default.
- **Do not start Cloud SQL** (`rtdp-postgres`) outside a bounded validation window. The
  activation policy is NEVER/STOPPED. Starting Cloud SQL for an unplanned operational
  response should be treated as a deliberate bounded window with an explicit stop plan.
- If Cloud SQL is not running and messages are failing delivery, they will be retried and
  eventually routed to DLQ. This is expected and does not represent data loss beyond the
  DLQ accumulation (see Section 6.3).

### 6.3 Inspecting the DLQ

If messages are accumulating in `market-events-raw-dlq`:

```bash
# Check DLQ topic message count via a subscription
gcloud pubsub subscriptions describe <dlq-subscription-name> \
  --project=project-42987e01-2123-446b-ac7

# Pull a sample without acknowledging (for inspection)
gcloud pubsub subscriptions pull <dlq-subscription-name> \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=5 \
  --auto-ack=false
```

Do not bulk-acknowledge DLQ messages without understanding their content. DLQ messages may
represent replayable events (infrastructure failure) or permanently unprocessable payloads
(schema violations). These require different remediation paths.

### 6.4 Scaling the worker

The current `maxScale: 1` constraint means **no horizontal scaling is possible without a
deliberate configuration change**. Increasing `maxScale` requires a Cloud Run service update
(either via Terraform apply or `gcloud run services update --max-instances`).

**Do not change `maxScale` without explicit approval.** Increasing max instances increases
Cloud SQL connection concurrency. The current database URL is a single Cloud SQL connection
string accessed by multiple instances simultaneously; a pool exhaustion or connection limit
error would cause all instances to fail writes simultaneously.

Any scale-out change must be accompanied by a review of Cloud SQL connection pool capacity
and the idempotency behaviour under concurrent writes.

### 6.5 Pausing inbound traffic

There is no ingress pause mechanism in the current architecture (no ingress firewall, no
Pub/Sub subscription suspend API). To stop the worker from receiving messages:

- Detach the push subscription endpoint (not recommended without a runbook; messages continue
  accumulating in the backlog during detachment and are redelivered on reattachment).
- Allow the subscription to exhaust its `messageRetentionDuration` (messages expire after 600s;
  results in message loss).

Neither option is safe without a planned runbook. The preferred operational response for
a capacity event is to monitor the backlog, confirm DLQ routing is working, and investigate
the root cause before making configuration changes.

---

## 7. Relationship to Dataflow

### Current state

The validated pipeline architecture is:

```
Pub/Sub → Cloud Run worker (push subscription) → Cloud SQL
```

A bounded Apache Beam DirectRunner proof (`pipelines/beam_market_events.py`) and a bounded
DataflowRunner proof (job `2026-05-24_03_59_31-13978483355822818690`, 10 rows to proof-only
table `market_events_beam_proof`) have been executed and validated. See
`docs/dataflow-bounded-runner-proof-evidence.md`.

**Production-like always-on Dataflow streaming is not implemented and not claimed.**
The DataflowRunner proof used a proof-only topic, a proof-only subscription, and a proof-only
BigQuery table. It was operator-drained after processing 10 messages. It does not represent
a sustained streaming pipeline.

### When Dataflow becomes appropriate

The current Cloud Run worker architecture is adequate for the validated throughput range
(up to 50,000-event bounded bursts; 10 eps steady-state) and for stateless per-message
processing. Dataflow becomes appropriate when:

| Condition | Cloud Run limit | Dataflow capability |
|---|---|---|
| Sustained backlog exceeding worker processing rate | `maxScale: 1` hard limit; no horizontal relief without manual intervention | Managed horizontal scaling; adjustable worker parallelism |
| Windowed aggregations (e.g. per-symbol 1-minute VWAP) | Not supported in a stateless per-message worker | `FixedWindows`, `SlidingWindows`, `Sessions` with Apache Beam |
| Stateful processing (e.g. sequence deduplication, late-event correction) | Stateless worker; no persistent per-key state | Stateful DoFns, state API, timers |
| Event-time vs. processing-time alignment | No event-time semantics; messages processed in delivery order | `EventTimeTrigger`, `AllowedLateness`, watermarks |
| Fan-out to multiple sinks in one pipeline | Requires separate jobs or side effects in the worker | Beam branching (`ParDo` fan-out, side outputs) |

The bounded DataflowRunner proof demonstrates that the infrastructure prerequisites
(Dataflow API, service account, GCS staging bucket, proof-only Pub/Sub resources, BigQuery
proof table, IAM) are in place. A production streaming Dataflow pipeline would require:

1. A production-safe Pub/Sub pull subscription (not the existing push subscription).
2. A windowing and watermark strategy.
3. Exactly-once or at-least-once sink semantics explicitly chosen for the output layer.
4. Cost controls (worker type, region, autoscaling policy, drain runbook).
5. Monitoring specific to Dataflow (system lag, data freshness, worker count, error rate).

---

## 8. Proposed Future Metrics and Alerts

These metrics and alert policies are **not currently implemented**. They are recommendations
for the next observability iteration.

### 8.1 Pub/Sub oldest unacked message age

```
Metric:  pubsub.googleapis.com/subscription/oldest_unacked_message_age
Filter:  subscription_id = "market-events-raw-worker-push"
Alert:   threshold > 120s, duration 2 minutes
Policy:  page if > 300s (half of messageRetentionDuration); ticket if 120–300s
```

This is the earliest signal of delivery stall. It becomes non-zero the moment a message fails
to ack within the deadline and grows until the worker drains the backlog or the message is
routed to DLQ.

### 8.2 Num undelivered messages

```
Metric:  pubsub.googleapis.com/subscription/num_undelivered_messages
Filter:  subscription_id = "market-events-raw-worker-push"
Alert:   threshold > 500, duration 5 minutes
Policy:  page if monotonically increasing for 10 minutes; ticket if stable high
```

Distinguishes between a burst (backlog is growing then draining) and a stall
(backlog only grows). Should be observed together with `oldest_unacked_message_age`.

### 8.3 Worker error count

```
Metric:  logging.googleapis.com/user/worker_message_error_count
Alert:   threshold > 0, duration 1 minute (already exists; confirm notification channel)
```

The existing alert policy covers this metric. Confirm the email notification channel is
attached and that the alert fires as expected (verified for the incident path in
`docs/bigquery-quality-incident-notification-delivery-proof.md` for BigQuery; analogous
proof for the worker error alert is pending).

### 8.4 DLQ message count

```
Metric:  pubsub.googleapis.com/topic/send_message_operation_count
Filter:  topic_id = "market-events-raw-dlq"
Alert:   threshold > 0 messages in a 5-minute window
Policy:  ticket on first occurrence; page if rate > 10/minute
```

Any non-zero DLQ inflow requires operator investigation. The current architecture has no
DLQ consumer; accumulation is permanent until manually drained.

### 8.5 Processing latency (end-to-end)

```
Source:  worker structured logs; timestamp fields (ingest_timestamp, producer publish_timestamp)
Metric:  custom.googleapis.com/rtdp/worker/e2e_latency_seconds (proposed)
Alert:   p95 > 10s; page if p95 > 25s (approaching ack deadline)
```

End-to-end latency from producer publish to successful Cloud SQL write is the primary SLO
metric for the ingestion path. The current evidence base includes p50/p95/p99 from a
100-event instrumented run (see `docs/latency-artifact-100-cloud-validation-evidence.md`).
A Cloud Monitoring custom metric emitted from the worker on each successful write would
enable continuous latency monitoring without a separate test run.

---

## 9. Explicit Non-Claims

This document is an analytical assessment of the current architecture. The following have
**not** been performed on this branch or in any prior branch unless individually noted in
existing evidence documents:

| Claim | Status |
|---|---|
| Sustained overload test executed | **NOT EXECUTED** — no test has pushed the system into sustained backlog exhaustion |
| New GCP resources created | **NOT CREATED** — this branch is docs-only; no `terraform apply`; no `gcloud` mutations |
| Terraform apply executed | **NOT EXECUTED** — `PLAN_EXIT=0`; infrastructure matches configuration |
| Pub/Sub messages published | **NOT PUBLISHED** — no messages published on this branch |
| Cloud SQL started | **NOT STARTED** — `rtdp-postgres` remains STOPPED / NEVER |
| Production scaling change | **NOT CHANGED** — `maxScale` and `containerConcurrency` are unchanged |
| DLQ consumer implemented | **NOT IMPLEMENTED** — DLQ routing is configured; no automated consumer exists |
| Exactly-once delivery proven | **NOT CLAIMED** — at-least-once semantics are the basis; idempotent writes mitigate duplicates |
| Maximum throughput characterised | **NOT CHARACTERISED** — 50,000-event bounded burst and 10 eps/30 min steady-state are the observed upper bounds; saturation point unknown |
| Dataflow production streaming | **NOT CLAIMED** — bounded DataflowRunner proof validated; always-on production streaming is not implemented |

---

## 10. Recommended Next Implementation Options (Ranked by ROI)

The following options address the gaps identified in this analysis. They are ranked by the
ratio of observability or reliability improvement to implementation effort, given the current
validated baseline.

### Option 1 — Add Pub/Sub backlog alert policies (highest ROI)

**What:** Create two Cloud Monitoring alert policies for
`subscription/oldest_unacked_message_age` and `subscription/num_undelivered_messages` on
`market-events-raw-worker-push`.

**Why:** These metrics provide the earliest signals of delivery stall or saturation.
They are native Pub/Sub metrics; no code changes or custom metric emission required.
Implementation is a Terraform resource addition (`google_monitoring_alert_policy`).

**Effort:** Low — one Terraform resource block per metric; no application code change.

**Evidence path:** Add to `infra/terraform/gcp/monitoring.tf`; validate with `PLAN_EXIT=2`
pre-apply, `APPLY_EXIT=0`, `PLAN_EXIT=0` post-apply; confirm alert policy exists via CLI.

---

### Option 2 — Add DLQ monitoring alert (high ROI)

**What:** Create an alert policy that fires when any message lands in `market-events-raw-dlq`.

**Why:** The DLQ is currently silent — messages route there but no operator is notified.
A single DLQ message is diagnostic evidence of either a permanent message defect or a
delivery infrastructure failure. Both require investigation.

**Effort:** Low — same Terraform pattern as Option 1; use `topic/send_message_operation_count`
filtered on `market-events-raw-dlq`.

**Evidence path:** Same Terraform apply + alert existence verification pattern.

---

### Option 3 — Instrument per-message latency in the worker (medium ROI)

**What:** Emit a custom Cloud Monitoring time series (`custom.googleapis.com/rtdp/worker/e2e_latency_seconds`)
from the worker on each successful write, using the difference between the producer-embedded
`event_timestamp` and the Cloud SQL commit timestamp.

**Why:** The current observability base has a point-in-time latency sample from a 100-event
instrumented test but no continuous latency signal. A continuously emitted metric enables
SLO tracking, regression detection, and saturation-approach alerting.

**Effort:** Medium — requires a worker code change to extract and emit the latency metric;
`roles/monitoring.metricWriter` is already granted for `rtdp-worker-sa` (see
`docs/dbt-metrics-runtime-monitoring-iam-evidence.md`); no IAM change needed.

**Evidence path:** Worker code change, new pytest tests, Cloud Run redeploy, Cloud Monitoring
series confirmation.

---

### Option 4 — Implement a minimal DLQ consumer (medium ROI)

**What:** A Cloud Run Job (manually triggered) that pulls messages from a DLQ subscription,
logs them with full metadata, and provides an operator decision point (replay or discard).

**Why:** The current DLQ is a dead end — messages accumulate with no automated path to
inspection, replay, or discard. A simple consumer that emits structured logs per DLQ message
closes the observability gap without requiring a full replay pipeline.

**Effort:** Medium — new Cloud Run Job; new Pub/Sub subscription on the DLQ topic; controlled
execution runbook; no schema changes.

**Evidence path:** Manual execution with a known DLQ message; verify log output; verify
message is acked; verify DLQ subscription drain.

---

### Option 5 — Increase maxScale and validate concurrent writes (lower ROI, higher risk)

**What:** Increase `autoscaling.knative.dev/maxScale` from 1 to 3–5; validate concurrent
worker instances write to Cloud SQL without deadlock or duplicate row anomaly.

**Why:** The current single-instance constraint is the binding throughput limit. Horizontal
scaling would increase sustained throughput capacity and reduce backlog accumulation under
burst traffic.

**Risk:** Cloud SQL connection concurrency, idempotency behaviour under concurrent inserts
for the same `event_id`, and the cost of keeping Cloud SQL running during a scale-out test
are all non-trivial. A bounded validation window with controlled concurrent load would be
required.

**Effort:** High — requires Cloud Run configuration change, Cloud SQL start, concurrent load
test, validation of duplicate-free results.

---

### Option 6 — Introduce production Dataflow streaming (longest horizon, highest capability)

**What:** Implement an always-on Dataflow streaming pipeline from
`market-events-raw-worker-push` pull subscription to BigQuery with windowed aggregations.

**Why:** For sustained throughput above what a single Cloud Run instance can handle, or for
windowed/stateful processing requirements, Dataflow is the appropriate managed streaming layer.
The bounded DataflowRunner proof validates the infrastructure path; the gap is the sustained
streaming design, cost controls, and production runbook.

**Risk:** Ongoing Dataflow streaming worker cost; requires a production-safe pull subscription
separate from the push subscription; windowing and watermark design; exactly-once vs.
at-least-once sink decision.

**Effort:** High — new Beam pipeline with windowing; new pull subscription; BigQuery sink
with streaming inserts; cost controls; monitoring.

---

## Evidence Links

| Document | Relevance |
|---|---|
| [docs/gcp-architecture.md](gcp-architecture.md) | GCP service mapping and validated flow |
| [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) | Pub/Sub DLQ configuration: subscription parameters, retry policy, DLQ topic |
| [docs/dlq-malformed-message-validation-evidence.md](dlq-malformed-message-validation-evidence.md) | DLQ routing behaviour observed with synthetic malformed payload |
| [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md) | 50,000-event bounded burst: throughput evidence |
| [docs/steady-state-10eps-30min-cloud-validation-evidence.md](steady-state-10eps-30min-cloud-validation-evidence.md) | 10 eps / 30 min sustained: throughput evidence |
| [docs/latency-artifact-100-cloud-validation-evidence.md](latency-artifact-100-cloud-validation-evidence.md) | p50/p95/p99 end-to-end latency from 100-event instrumented run |
| [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) | Existing alert policies (worker error, silver refresh error) |
| [docs/dataflow-bounded-runner-proof-evidence.md](dataflow-bounded-runner-proof-evidence.md) | DataflowRunner bounded proof: validated execution, isolation, non-claims |
| [docs/dataflow-apache-beam-architecture-decision.md](dataflow-apache-beam-architecture-decision.md) | Architecture decision record for Cloud Run vs Dataflow |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | SLO targets, error budget, and incident response runbooks |
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Full evidence index |
