# Latency and Throughput Analysis After 50k Load Test

## Status

- ANALYSIS ONLY
- Based on existing evidence from the 50,000-event bounded cloud load test
- No new events published
- No Cloud SQL start
- No new GCP workload execution
- No p50/p95/p99 latency claim

---

## Executive Summary

The 50,000-event bounded cloud load test validates a clean processing path through
Pub/Sub -> Cloud Run worker -> Cloud SQL. All 50,000 events were published without
error, processed by the worker without error, and persisted to Cloud SQL with zero
duplicate event_ids.

The publish script was intentionally conservative: it waited for each Pub/Sub publish
future to resolve before sending the next event. The observed elapsed time of 3420.294
seconds is therefore a conservative end-to-end publish-and-acknowledge window, not a
benchmark of maximum system throughput. The effective publish rate derived below
reflects the test harness design, not the ceiling of Pub/Sub, Cloud Run, or Cloud SQL.

Structured worker logs and Cloud SQL prefix row counts are the authoritative sources
for exact event completion counts. The Cloud Monitoring processed metric shows 50,002
due to DELTA window alignment: the metric query window boundary does not align exactly
with the publish start/end timestamps, so an extra 2 points from adjacent windows were
captured. This does not indicate duplicate processing; Cloud SQL duplicate_event_id_count
= 0 is definitive.

---

## Evidence Inputs

| Input | Value | Source |
|---|---|---|
| Event count | 50,000 | publish-report-50000.json |
| Publish start | 2026-05-20T07:28:08Z | publish-report-50000.json |
| Publish end | 2026-05-20T09:14:40Z | publish-report-50000.json |
| Publish elapsed seconds | 3420.294 | publish-report-50000.json |
| Published total | 50,000 | publish-report-50000.json |
| Unique message IDs | 50,000 | publish-report-50000.json |
| Publish errors | 0 | publish-report-50000.json |
| Worker OK logs | 50,000 | load-test-50000-cloud-evidence.md |
| Worker error count | 0 | monitoring-metrics-report-50000.json |
| Cloud SQL prefix rows | 50,000 | cloudsql-validation-report-50000.json |
| Duplicate event_id count | 0 | cloudsql-validation-report-50000.json |
| Monitoring processed total | 50,002 | monitoring-metrics-report-50000.json |
| Monitoring error total | 0 | monitoring-metrics-report-50000.json |
| Cloud SQL final state | STOPPED / NEVER | load-test-50000-cloud-evidence.md |
| Schedulers final state | PAUSED | load-test-50000-cloud-evidence.md |

---

## Derived Metrics

All calculations are performed directly from the evidence inputs above.
No per-event latency is inferred. No p50/p95/p99 is claimed.

### 50,000-Event Run

```
Publish elapsed seconds : 3420.294
Publish elapsed minutes : 3420.294 / 60           = 57.00 min
Avg publish rate        : 50000 / 3420.294         = 14.62 events/second
Avg publish rate        : 50000 / (3420.294 / 60) = 877.11 events/minute
```

### 10,000-Event Run (comparison baseline)

```
Publish elapsed seconds : 493.981
Publish elapsed minutes : 493.981 / 60            =  8.23 min
Avg publish rate        : 10000 / 493.981          = 20.24 events/second
Avg publish rate        : 10000 / (493.981 / 60)  = 1214.32 events/minute
```

### Cross-Run Comparison

| Metric | 10k Run | 50k Run |
|---|---|---|
| Event count | 10,000 | 50,000 |
| Elapsed seconds | 493.981 | 3420.294 |
| Elapsed minutes | 8.23 | 57.00 |
| Avg events/second | 20.24 | 14.62 |
| Avg events/minute | 1214.32 | 877.11 |
| Publish errors | 0 | 0 |
| Worker errors | 0 | 0 |
| Duplicate event_ids | 0 | 0 |

The 50k run shows a lower effective publish rate than the 10k run. This is consistent
with a single-threaded sequential publish pattern: at larger volumes, cumulative Pub/Sub
round-trip latency accumulates, slightly reducing the observable average rate. Both
figures are client-side conservative publish rates. They do not represent the maximum
throughput of the worker, Pub/Sub, or Cloud SQL.

---

## Interpretation

The 50,000-event run completes cleanly with zero errors and zero duplicates, proving
correctness and idempotency at a scale that exercises the full Pub/Sub -> Cloud Run
worker -> Cloud SQL path meaningfully.

The publish mechanism was intentionally sequential. The script issued one publish call
per event, waited for the Pub/Sub acknowledgement future to resolve, then proceeded to
the next event. This design ensures reliable evidence of per-message delivery but
constrains the observable rate to the client-side publish-and-ack cycle time, not the
system's maximum ingestion or processing throughput.

Worker processing kept up with the bounded publish stream because worker OK log counts
reached 50,000 and Cloud SQL prefix_row_count reached 50,000 with duplicate_event_id_count
= 0. No message backlog and no DLQ failures were evidenced in this bounded run.

The Cloud Monitoring processed metric of 50,002 must not be used as the authoritative
event count. The DELTA window alignment in the metric query captures points at window
boundaries that can span outside the exact publish interval. Worker structured logs and
Cloud SQL row counts are the definitive proof of exactly 50,000 events processed and
persisted.

---

## Production-Like Value

| Production Concern | What This Evidence Shows | What It Does Not Yet Prove |
|---|---|---|
| Bounded throughput | 50,000 events processed cleanly end-to-end via Pub/Sub -> Cloud Run -> Cloud SQL | Maximum throughput under concurrent or sustained load |
| Idempotent persistence | Zero duplicate event_ids across 50,000 events in Cloud SQL | Duplicate handling under retry or replay scenarios at scale |
| Error-free worker path | 0 worker errors, 0 publish errors, 0 DLQ messages | Behaviour under partial failures, retries, or poison messages |
| Observability | Cloud Monitoring processed metric confirms scale; worker logs authoritative | Per-event latency percentiles; end-to-end trace correlation |
| Cost-safe restoration | Cloud SQL returned to STOPPED/NEVER; schedulers PAUSED after test window | Long-running cost behaviour under production-like steady state |
| Terraform drift control | PLAN_EXIT=0 confirmed after test; no infrastructure drift | Drift detection under concurrent team changes |
| Data quality / alerting context | BigQuery quality checks pass; Cloud Monitoring alert policy proven for quality failures | Automated quality alerting triggered by 50k data in BigQuery tier |
| Latency | Not measured; no per-event timestamp from publish to DB write available | p50/p95/p99 latency; publish-to-worker latency; worker-to-DB write latency |
| Sustained throughput | Not tested; 57-minute bounded window only | Steady-state throughput at consistent msg/s for hours |
| Replay / backfill | Not tested in this run | Replay correctness at scale; backfill throughput |
| Dataflow / windowed streaming | Not implemented | Any Dataflow-based windowed aggregation capability |

---

## Safe Interview Wording

"The 50,000-event run proves a clean bounded processing path, not maximum throughput.
The client published sequentially and waited for Pub/Sub acknowledgements, so the
observed rate is conservative. I use the result to prove end-to-end correctness,
idempotency, observability, and operational discipline, not to claim sustained
production throughput."

---

## Remaining Measurement Gaps

- No p50/p95/p99 latency: no per-event publish timestamp to DB-write timestamp
  measurement exists in the current evidence set.
- No per-event timing: the publish report records start/end timestamps and total
  elapsed time only; individual message round-trip times are not captured.
- No sustained steady-state test: all load tests are bounded; no constant-rate
  multi-hour run has been executed.
- No cost-per-event estimate: Cloud SQL active window cost for the 50k test window
  has not been calculated.
- No Cloud Run concurrency tuning benchmark: the worker ran at default concurrency;
  no min/max instance tuning has been validated under load.
- No Cloud SQL write saturation analysis: no test has approached Cloud SQL write
  limits; no saturation point is known.
- No DLQ malformed-message validation: the DLQ is configured (maxDeliveryAttempts=5)
  but no controlled malformed-message routing test has been executed.
- No Dataflow comparison baseline: Dataflow is deferred; no latency or throughput
  comparison between Cloud Run and Dataflow is available.

---

## Recommended Next Steps

### P1

- Add lightweight log-derived timing report if existing Cloud Logging timestamps can
  be queried read-only without starting Cloud SQL. Structured worker logs contain
  event receipt and processing timestamps that could yield publish-to-process latency
  estimates without any live GCP cost.
- Add a controlled DLQ malformed-message validation plan: publish one malformed event,
  confirm it routes to the DLQ topic after maxDeliveryAttempts=5, confirm the worker
  does not crash or drop healthy messages.
- Add cost/performance summary from known Cloud SQL active windows: the test window
  timestamps are available; a Cloud Billing export or Console estimate would yield a
  credible cost-per-1000-events figure.

### P2

- Add instrumentation for publish timestamp, worker receive timestamp, and DB write
  timestamp in a future load test to enable p50/p95/p99 latency calculation.
- Add a steady-state benchmark at a fixed rate, such as 10 msg/s for 30 minutes, to
  validate consistent throughput without the sequential publish constraint.
- Add a Dataflow decision record: document the criteria (latency SLO, replay
  requirement, windowed aggregation need, cost threshold) that would trigger a Dataflow
  migration, even if not implemented yet.

### P3

- Implement Dataflow only if justified by measured bottlenecks or required by target
  role responsibilities, sustained throughput SLOs, or windowed aggregation at scale.
  Do not implement speculatively.

---

## Final Verdict

| Dimension | Assessment |
|---|---|
| Throughput evidence | Useful but conservative; reflects sequential client publish pattern |
| Correctness evidence | Strong; 50,000 events, 0 errors, 0 duplicates, end-to-end confirmed |
| Observability evidence | Strong; Cloud Monitoring metrics, structured logs, alert policy proven |
| Production maturity | Improving; bounded validation only, not sustained production load |
| Recruitment value | High; demonstrates disciplined end-to-end engineering at meaningful scale |
| Main next gap | Latency percentiles and sustained steady-state throughput measurement |
