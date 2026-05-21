# Latency Artifact 100 Cloud Validation Evidence

## Status

| Field | State |
|---|---|
| Document type | CLOUD VALIDATION |
| New GCP workload execution | Yes |
| Events published | 100 |
| Cloud SQL started | Yes, controlled window only |
| Cloud SQL restored | STOPPED / NEVER |
| Schedulers final state | PAUSED |
| Schema migration executed | No |
| Terraform apply executed | No |
| p50/p95/p99 latency validated | YES, artifact/log join |

**Status:** VALIDATED -- 100 latency-instrumented cloud events published and matched with worker structured logs; p50/p95/p99 end-to-end latency computed from producer artifact and worker logs.

---

## Executive Summary

This branch validates Option B from `docs/latency-instrumentation-plan.md`: artifact/log-based latency evidence.

A controlled cloud run published 100 latency-instrumented events to `market-events-raw`.
The deployed worker image was updated to commit `16a18b1`, which includes latency stage timestamp logging.
Publisher JSONL artifacts and Cloud Run worker structured logs were joined by `event_id`.

All 100 publisher events matched worker success logs.

Cloud SQL was started only for the controlled validation window and restored to `STOPPED / NEVER`.
Schedulers remained `PAUSED`.
No schema migration was executed.
No Terraform apply was executed.
No secrets were printed.

---

## Run Parameters

| Parameter | Value |
|---|---|
| RUN_TS | `20260521083127` |
| Publisher artifact | `docs/evidence/latency-artifact-100-cloud-validation/latency-publisher-20260521083127.jsonl` |
| Worker logs artifact | `docs/evidence/latency-artifact-100-cloud-validation/worker-logs-20260521083127.json` |
| Latency report | `docs/evidence/latency-artifact-100-cloud-validation/latency-report-20260521083127.json` |
| Published events | 100 |
| Raw worker logs | 100 |
| Matched worker logs | 100 |
| Matched events | 100 |
| Missing events | 0 |
| Latency samples | 100 |

---

## Latency Results

| Metric | Value ms |
|---|---:|
| p50 | 846.353 |
| p95 | 1333.54 |
| p99 | 3660.572 |
| min | 764.414 |
| max | 4924.04 |
| avg | 949.554 |

---

## Validation Summary

| Check | Result |
|---|---|
| Publisher rows | 100 |
| Worker logs matched | 100 |
| Missing event count | 0 |
| Latency sample count | 100 |
| Report status | ok |
| p50 present | Yes |
| p95 present | Yes |
| p99 present | Yes |

The worker emits success logs only after the database insert path returns successfully.
This gives cloud-path evidence for producer -> Pub/Sub -> Cloud Run worker -> Cloud SQL insert return -> worker completion.
This branch does not add Cloud SQL timestamp columns and does not compute percentiles inside Cloud SQL.

---

## Explicit Non-Claims

- This is not a sustained throughput test.
- Maximum throughput is not claimed.
- Cloud SQL percentile queries are not claimed.
- Cloud SQL schema migration was not executed.
- Dataflow is not implemented.
- Exactly-once production semantics are not claimed.
- Enterprise-grade latency SLO enforcement is not claimed.
- Multi-hour or multi-day latency stability is not claimed.

---

## Final Safe State

| Resource | State |
|---|---|
| Cloud SQL `rtdp-postgres` | STOPPED / NEVER |
| Cloud Scheduler jobs | PAUSED |
| Terraform apply | NOT run |
| Secrets printed | NONE |

---

## Final Verdict

The latency instrumentation gap is partially closed with cloud evidence.

The project now has real p50/p95/p99 latency evidence for a controlled 100-event cloud validation using producer artifacts and worker structured logs.

Next production-like step: run the steady-state throughput test with this latency instrumentation enabled.
