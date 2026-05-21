# Steady-State 10 EPS 30 Minute Cloud Validation Evidence

## Status

| Field | State |
|---|---|
| Document type | CLOUD VALIDATION |
| New GCP workload execution | Yes |
| Target rate | 10 events/sec |
| Target duration | 30 minutes |
| Events attempted | 18000 |
| Events acknowledged | 18000 |
| Publish errors | 0 |
| Observed events/sec | 10.0 |
| Cloud SQL started | Yes, controlled window only |
| Cloud SQL restored | STOPPED / NEVER |
| Schedulers final state | PAUSED |
| Terraform apply executed | No |
| Sustained throughput validated | YES |
| p50/p95/p99 latency validated | YES, artifact/log join |

**Status:** VALIDATED -- sustained 10 events/sec for 30 minutes with 18,000 acknowledged publishes, 18,000 matched worker events, zero missing events, zero publish errors, and p50/p95/p99 end-to-end latency computed from producer artifacts and worker structured logs.

---

## Executive Summary

This branch validates the first steady-state throughput target defined in `docs/steady-state-throughput-test-plan.md`.

A controlled cloud run published 18,000 latency-instrumented events to `market-events-raw` at a target rate of 10 events/sec for 30 minutes.

The deployed Cloud Run worker image included latency artifact/log instrumentation from commit `16a18b1`.

Publisher JSONL artifacts and Cloud Run worker structured logs were joined by `event_id`.

The validation confirms:

- 18,000 attempted publishes.
- 18,000 acknowledged publishes.
- 0 publish errors.
- Observed publish rate: 10.0 events/sec.
- 18,000 unique publisher event_ids.
- 18,000 unique worker event_ids.
- 18,000 latency samples.
- 0 missing worker events.
- 0 extra worker events.
- p50/p95/p99 end-to-end latency computed.

Observed caveat: worker logs contained 18,001 raw success log rows for 18,000 unique worker event_ids. One event_id appeared twice in worker logs. This is documented as a duplicate worker log caveat. It did not create missing events, extra events, or duplicate publisher event_ids.

Cloud SQL was started only for the controlled validation window and restored to `STOPPED / NEVER`.
Schedulers remained `PAUSED`.
No Terraform apply was executed.
No schema migration was executed.
No secrets were printed.

---

## Run Parameters

| Parameter | Value |
|---|---|
| RUN_TS | `20260521095522` |
| Test prefix | `steady10eps-20260521095522` |
| Publisher artifact | `docs/evidence/steady-state-10eps-30min-cloud-validation/steady-state-publisher-20260521095522.jsonl` |
| Publisher summary | `docs/evidence/steady-state-10eps-30min-cloud-validation/steady-state-publisher-summary-20260521095522.json` |
| Worker logs artifact | `docs/evidence/steady-state-10eps-30min-cloud-validation/worker-logs-20260521095522.json` |
| Latency report | `docs/evidence/steady-state-10eps-30min-cloud-validation/steady-state-latency-report-20260521095522.json` |
| Target events/sec | 10 |
| Target duration seconds | 1800 |
| Expected events | 18000 |
| Attempted events | 18000 |
| Acknowledged events | 18000 |
| Publish error count | 0 |
| Observed events/sec | 10.0 |
| Elapsed seconds | 1799.969 |
| Average publish interval ms | 100.002 |
| Min publish interval ms | 36.405 |
| Max publish interval ms | 2253.804 |

---

## Match and Completeness Results

| Metric | Value |
|---|---:|
| Publisher rows | 18000 |
| Worker log rows raw | 18001 |
| Matched worker log rows | 18001 |
| Matched unique events | 18000 |
| Missing events | 0 |
| Latency sample count | 18000 |

---

## End-to-End Latency Results

| Metric | Value ms |
|---|---:|
| p50 | 154.385 |
| p95 | 227.59 |
| p99 | 693.995 |
| min | 101.877 |
| max | 960263.973 |
| avg | 276.863 |

### End-to-End Latency Outlier Caveat

The end-to-end latency distribution includes one high max value: `960263.973 ms`.
This does not affect the accepted p50/p95/p99 evidence, but it must be interpreted as an
artifact/log-join outlier or delayed worker completion observation, not as the normal
steady-state latency profile.

The accepted latency positioning is therefore:

- p50/p95/p99 latency is validated for the 18,000-event run.
- The max value is explicitly documented as an outlier.
- No strict latency SLO is claimed.
- No enterprise-grade latency SLO enforcement is claimed.
- Cloud SQL percentile queries are not claimed.

---

## Worker Processing Latency Results

| Metric | Value ms |
|---|---:|
| p50 | 28.037 |
| p95 | 35.948 |
| p99 | 45.357 |
| min | 23.659 |
| max | 500.969 |
| avg | 29.231 |

---

## Database Write Latency Results

| Metric | Value ms |
|---|---:|
| p50 | 27.911 |
| p95 | 35.807 |
| p99 | 45.208 |
| min | 23.575 |
| max | 500.308 |
| avg | 29.096 |

---

## Validation Latency Results

| Metric | Value ms |
|---|---:|
| p50 | 0.097 |
| p95 | 0.143 |
| p99 | 0.222 |
| min | 0.052 |
| max | 8.783 |
| avg | 0.105 |

---

## Duplicate Worker Log Caveat

The validation found:

| Check | Result |
|---|---:|
| Unique publisher event_ids | 18,000 |
| Duplicate publisher event_ids | 0 |
| Raw worker log rows | 18,001 |
| Unique worker event_ids | 18,000 |
| Duplicate worker event_ids | 1 |
| Missing worker event_ids | 0 |
| Extra worker event_ids | 0 |

The duplicate worker log caveat is documented explicitly. It does not invalidate the sustained throughput result because the accepted event-level join produced 18,000 unique matched events and 18,000 latency samples.

This result should be described as sustained throughput with at-least-once/log-duplication caveat, not exactly-once production semantics.

---

## Final Safe State

| Resource | State |
|---|---|
| Cloud SQL `rtdp-postgres` | STOPPED / NEVER |
| Cloud Scheduler jobs | PAUSED |
| Terraform apply | NOT run |
| Schema migration | NOT run |
| Secrets printed | NONE |

---

## Explicit Non-Claims

- Maximum throughput is not claimed.
- Saturation point is not claimed.
- Multi-hour or multi-day production stability is not claimed.
- Exactly-once production semantics are not claimed.
- Dataflow is not implemented.
- Enterprise-grade latency SLO enforcement is not claimed.
- Cloud SQL percentile queries are not claimed.
- This validation uses artifact/log join, not persisted Cloud SQL latency columns.

---

## Final Verdict

The sustained throughput gap is now materially closed for the first production-like target.

The platform has validated a controlled 10 events/sec for 30 minutes cloud run with 18,000 acknowledged events, zero publish errors, zero missing worker events, and p50/p95/p99 latency evidence.

Next production-like step: either increase rate to 25 events/sec for 30 minutes, or implement Cloud SQL persisted latency columns for stronger database-native latency analytics.
