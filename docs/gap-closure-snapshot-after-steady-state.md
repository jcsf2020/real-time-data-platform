# Gap Closure Snapshot After Steady-State Validation

**Date:** 2026-05-21
**Branch:** `docs/gap-closure-snapshot-after-steady-state`
**Status:** SNAPSHOT -- post-50k, post-DLQ, post-latency, and post-steady-state gap closure assessment
**Audience:** Recruiters, hiring managers, technical reviewers, B2B reviewers

---

## Executive Summary

The project is now beyond bounded-only validation.

It has validated:

- 50,000-event bounded cloud load test.
- Malformed-message DLQ routing with caveat.
- DLQ deduplication strategy documented.
- Artifact/log latency instrumentation.
- 100-event latency cloud validation.
- Sustained 10 events/sec for 30 minutes with 18,000 acknowledged events.
- p50/p95/p99 latency evidence from producer artifacts and worker structured logs.

Strongest current positioning:

> I validated a GCP event-processing path with both bounded 50,000-event evidence and
> sustained 10 events/sec for 30 minutes evidence, including Pub/Sub, Cloud Run, Cloud SQL,
> BigQuery, dbt, Cloud Monitoring, alerting, DLQ validation, latency instrumentation,
> Terraform zero-diff checks, and indexed evidence. I explicitly do not claim exactly-once
> production semantics, Dataflow, maximum throughput, or enterprise-grade SLO enforcement.

---

## What Is Now Closed

| Gap | Status | Evidence |
|---|---|---|
| Bounded cloud load above toy scale | Closed | 50,000-event validation. |
| Sustained throughput first target | Closed | 10 eps for 30 min; 18,000 attempted/acknowledged; 0 publish errors; observed 10.0 eps. |
| p50/p95/p99 latency first target | Closed | artifact/log join; p50 154.385 ms; p95 227.59 ms; p99 693.995 ms. |
| Latency instrumentation Option B | Closed | producer JSONL artifact + worker structured logs. |
| DLQ malformed routing | Closed with caveat | malformed payload reached DLQ; duplicate DLQ entries observed. |
| DLQ deduplication strategy | Closed as design | event_id / payload_sha256 strategy documented. |
| Alerting loop | Closed | Cloud Monitoring incident and email notification proven. |
| BigQuery analytical tier | Closed | dataset, tables, incremental append, quality checks. |
| dbt transformation layer | Closed | silver/gold incremental models and Cloud SQL live execution proven. |
| Terraform/IaC coverage | Closed | zero-diff plans preserved. |
| Cost-control operations | Closed | Cloud SQL STOPPED/NEVER and schedulers PAUSED after validations. |

---

## What Remains Open

| Gap | Current State |
|---|---|
| Dataflow / Apache Beam | Not implemented. |
| Maximum throughput / saturation point | Not claimed. |
| Multi-hour or multi-day sustained stability | Not proven. |
| Exactly-once production semantics | Not claimed. |
| DLQ production consumer implementation | Strategy documented, not implemented. |
| Replay/backfill operational strategy | Partial. |
| Cloud SQL persisted latency columns | Not implemented; current latency evidence is artifact/log join. |
| dbt-specific observability metrics | Still open. |
| Automatic deploy-on-merge | Not implemented; deploy remains workflow_dispatch. |
| Staging/prod split | Missing. |
| Cost per event | Not calculated. |
| Product-facing dashboard | Missing. |
| Enterprise security certification | Not present. |

---

## Production-Likeness Assessment

| Dimension | Assessment | Reason |
|---|---|---|
| Event ingestion | Strong | Pub/Sub and Cloud Run worker validated at bounded and sustained scale. |
| Persistence | Strong | Cloud SQL write path validated with idempotency and zero duplicates. |
| Analytics | Good | BigQuery and dbt implemented and evidenced. |
| Observability | Strong | Logs, metrics, dashboard, alerting, and email notification proven. |
| Reliability | Good with caveats | DLQ routing validated; duplicate DLQ entries and one duplicate worker log event observed. |
| IaC | Strong | Terraform remote state and zero-diff plans validated. |
| CI | Strong | pytest, ruff, dbt, and Terraform validation run consistently. |
| Cost control | Strong | Cloud SQL STOPPED/NEVER and schedulers PAUSED by default. |
| Latency measurement | Improved / first cloud evidence validated | p50/p95/p99 computed from artifact/log join at 18,000-event scale. |
| Sustained throughput | Improved / first steady-state target validated | 10 eps for 30 min with 18,000 acknowledged events. |
| Streaming architecture maturity | Partial | Cloud Run worker exists; Dataflow not implemented. |
| Security posture | Partial | Secret Manager and Workload Identity exist; no external certification. |

---

## Critical Caveats

- One duplicate worker log event_id was observed in the 18,000-event steady-state run.
- No missing worker events.
- No duplicate publisher event_ids.
- One high end-to-end latency max value was observed: 960263.973 ms.
- p50/p95/p99 remain accepted, but max should be treated as an outlier/log-join/delayed-observation caveat, not as normal steady-state latency.
- This result should be described as sustained throughput with at-least-once/log-duplication caveat, not exactly-once production semantics.

---

## Safe Interview Positioning

Main positioning:

> I validated a GCP event-processing platform with Pub/Sub, Cloud Run, Cloud SQL, BigQuery,
> dbt, Terraform, Cloud Monitoring, alerting, and DLQ evidence. The project includes a
> 50,000-event bounded cloud load test and a sustained 10 events/sec for 30 minutes
> validation with 18,000 acknowledged events and p50/p95/p99 latency evidence.

Caveat positioning:

> I do not claim Dataflow, exactly-once production semantics, maximum throughput, multi-day
> production stability, or enterprise-grade SLO enforcement. The evidence is intentionally
> precise: it shows what was validated, what caveats were observed, and what remains open.

---

## Priority Next Branches

### P1 -- Immediate

| Branch / Doc | Purpose |
|---|---|
| `docs/cost-performance-summary` | Estimate cost per 1,000 events and cost per validation window. |
| `docs/dataflow-decision-record` | Explain when Dataflow becomes justified and what it would add. |
| `docs/replay-backfill-strategy` | Define operational replay and backfill semantics. |

### P2 -- Medium Value

| Branch / Doc | Purpose |
|---|---|
| `feat/dbt-observability-metrics-plan` | Define dbt-specific Cloud Monitoring metrics. |
| `docs/staging-environment-plan` | Define staging/prod separation and safer release flow. |
| `docs/cloud-sql-persisted-latency-plan` | Plan Cloud SQL timestamp columns for database-native latency analytics. |

### P3 -- Longer Term

| Branch / Doc | Purpose |
|---|---|
| `docs/dashboard-productization-plan` | Convert engineering evidence into a visible demo layer. |
| `ci/deploy-on-merge-decision-record` | Document the decision and path for automatic deploy-on-merge. |

---

## Explicit Non-Claims

- Maximum throughput is not claimed.
- Saturation point is not claimed.
- Multi-hour or multi-day production stability is not claimed.
- Exactly-once production semantics are not claimed.
- Dataflow is not implemented.
- Enterprise-grade latency SLO enforcement is not claimed.
- Cloud SQL persisted latency columns are not implemented.
- Enterprise-certified security is not claimed.
- Production DLQ consumer is not implemented.

---

## Final Verdict

The project is now materially stronger than after the DLQ snapshot because the two main
previous gaps -- sustained throughput and latency percentiles -- now have first cloud
validation evidence.

The 50,000-event bounded load test proved scale above toy level. The 10 events/sec for
30 minutes steady-state run proved sustained throughput with 18,000 acknowledged events
and zero publish errors. The p50/p95/p99 latency evidence from artifact/log join provides
credible, documented percentile claims at production-like event counts.

It is still not an enterprise production platform. Dataflow is not implemented. Exactly-once
semantics are not claimed. Multi-day stability is not proven. But the project is now a
strong GCP Data Engineering portfolio asset with unusually rigorous evidence, honest
caveats, and a clear map of what remains open.
