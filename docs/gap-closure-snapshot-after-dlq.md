# Gap Closure Snapshot After DLQ Validation

**Date:** 2026-05-20
**Branch:** `docs/gap-closure-snapshot-after-dlq`
**Status:** SNAPSHOT -- post-50k and post-DLQ gap closure assessment
**Audience:** Recruiters, hiring managers, technical reviewers, B2B reviewers

---

## Executive Summary

The Real-Time Data Platform now has evidence for the main GCP data platform path:

Pub/Sub -> Cloud Run worker -> Cloud SQL -> BigQuery -> dbt -> Cloud Monitoring

The project is no longer a simple demo. It has bounded cloud execution evidence,
Terraform-managed infrastructure, CI validation, observability, alerting, data quality,
and DLQ malformed-message validation.

The strongest validated milestone remains the 50,000-event bounded cloud load test.
The newest reliability milestone is the malformed-message DLQ validation. That validation
proved that a malformed payload reached the DLQ, but it also exposed an important caveat:
multiple DLQ entries were observed for the same original test marker. Therefore, exactly-once
DLQ semantics are not claimed.

Best current positioning:

> I validated a GCP event-processing path at 50,000 events with Pub/Sub, Cloud Run,
> Cloud SQL, structured logs, Cloud Monitoring metrics, Terraform zero-diff checks, and
> indexed evidence. I also validated malformed-message DLQ routing, with an observed
> caveat: multiple DLQ entries appeared for the same test marker, so I do not claim
> exactly-once DLQ semantics.

---

## What Is Now Closed

| Gap | Status | Evidence |
|---|---|---|
| GCP event ingestion | Closed | Pub/Sub topic, push subscription, Cloud Run worker |
| Bounded cloud load above toy scale | Closed | 50,000-event cloud load test |
| Idempotent write path | Closed | 50,000 Cloud SQL rows, duplicate_event_id_count=0 |
| Worker structured logs | Closed | Worker status=ok and status=error logs |
| Cloud Monitoring metrics | Closed | logs-based metrics and datapoints |
| Terraform IaC coverage | Closed | imported resources, remote state, PLAN_EXIT=0 |
| BigQuery analytical tier | Closed | dataset, partitioned tables, incremental append |
| dbt transformation layer | Closed | silver/gold incremental models, 22 dbt tests |
| Data quality workflow | Closed | 8-check BigQuery quality workflow |
| Alerting loop | Closed | Cloud Monitoring incident and email delivery |
| DLQ configuration | Closed | deadLetterPolicy, retryPolicy, maxDeliveryAttempts=5 |
| DLQ malformed-message routing | Closed with caveat | malformed payload reached DLQ; multiple entries observed |
| README front-door positioning | Closed | 50k milestone and non-claims added |
| Recruiter-facing summary | Closed | one-page platform summary added |
| Executive audit | Closed | post-50k executive platform audit added |
| Latency/throughput interpretation | Closed as analysis | conservative rate analysis; no p95/p99 claim |

---

## What Remains Open

| Gap | Current State | Why It Matters |
|---|---|---|
| Sustained throughput | Not proven | Current tests are bounded, not steady-state production workloads |
| p50/p95/p99 latency | Not measured | No per-event publish-to-worker-to-db timing yet |
| Dataflow / Apache Beam | Not implemented | No windowed streaming, late-event handling, or stateful pipeline proof |
| DLQ deduplication strategy | Missing | Multiple DLQ entries for one malformed test marker require dedup-aware handling |
| Replay / backfill strategy | Partial | BigQuery incremental append exists, but message-level replay strategy is not complete |
| Cost per event | Not calculated | Useful for B2B and production-style evaluation |
| Staging environment | Missing | Single GCP project; no staging/prod split |
| Automatic deploy-on-merge | Not implemented | CI exists; CD remains manual/workflow_dispatch |
| End-user dashboard | Missing | Engineering evidence exists; product-facing dashboard does not |
| Production SLO enforcement | Partial | SLO docs exist; burn-rate monitoring is not implemented |
| Enterprise security certification | Not present | No SOC2, pen test, DPA, or external audit |

---

## Production-Likeness Assessment

| Dimension | Assessment | Reason |
|---|---|---|
| Event ingestion | Strong | Pub/Sub and Cloud Run worker validated at 50k bounded scale |
| Persistence | Strong | Cloud SQL write path validated with idempotency and zero duplicates |
| Analytics | Good | BigQuery and dbt are implemented and evidenced |
| Observability | Strong | logs, metrics, dashboard, alerting and email notification proven |
| Reliability | Good | DLQ routing validated, but duplicate DLQ entries require dedup strategy |
| IaC | Strong | Terraform remote state and zero-diff plans validated |
| CI | Strong | pytest, ruff, dbt and Terraform validation run consistently |
| Cost control | Strong | Cloud SQL STOPPED/NEVER and schedulers PAUSED by default |
| Latency measurement | Missing | no p50/p95/p99 |
| Sustained throughput | Missing | no steady-state run |
| Streaming architecture maturity | Partial | Cloud Run worker exists; Dataflow not implemented |
| Security posture | Partial | Secret Manager and Workload Identity exist; no external certification |

---

## Value Assessment

| Area | Value |
|---|---|
| Recruitment value | High |
| B2B credibility | Strong and improving |
| Production maturity | Partial but credible |
| Evidence quality | Strong |
| Main remaining technical gap | sustained streaming architecture / Dataflow or equivalent |
| Main operational caveat | DLQ requires deduplication-aware handling |
| Best next move | document DLQ deduplication strategy, then plan sustained steady-state throughput and latency instrumentation |

The project now demonstrates real delivery ability across GCP data platform components.
The strongest market value is not that it is a production SaaS. The strongest value is
that it proves disciplined data engineering execution: event contracts, idempotency,
cloud deployment, observability, IaC, data quality, alerting, failure-path validation,
and honest non-claims.

---

## Safe Interview Positioning

Use this wording:

> I validated a GCP event-processing path at 50,000 events with Pub/Sub, Cloud Run,
> Cloud SQL, structured logs, Cloud Monitoring metrics, Terraform zero-diff checks, and
> indexed evidence. I also validated malformed-message DLQ routing, with an observed
> caveat: multiple DLQ entries appeared for the same test marker, so I do not claim
> exactly-once DLQ semantics.

Follow-up if challenged:

> The project is intentionally evidence-first. I do not claim Dataflow, sustained
> production throughput, exactly-once delivery, or enterprise-certified security. I show
> what was validated, what failed, what was corrected, and what remains open.

---

## Priority Next Branches

### P1 -- Immediate

| Branch / Doc | Purpose |
|---|---|
| `docs/dlq-deduplication-strategy` | Explain how DLQ consumers should deduplicate by payload hash, test_marker, or original event_id |
| `docs/steady-state-throughput-test-plan` | Define a safe 10 msg/s or similar steady-state benchmark |
| `docs/latency-instrumentation-plan` | Define publish, worker receive, and DB write timestamps for p50/p95/p99 |

### P2 -- Medium Value

| Branch / Doc | Purpose |
|---|---|
| `docs/cost-performance-summary` | Estimate cost per 1,000 events and cost per validation window |
| `docs/dataflow-decision-record` | Explain when Dataflow becomes justified and what it would add |
| `docs/replay-backfill-strategy` | Define operational replay and backfill semantics |

### P3 -- Longer Term

| Branch / Doc | Purpose |
|---|---|
| `docs/dashboard-productization-plan` | Convert engineering evidence into a visible demo layer |
| `infra/staging-environment-plan` | Define staging/prod separation and safer release flow |

---

## Explicit Non-Claims

- Dataflow is not implemented.
- Sustained production throughput is not claimed.
- p50/p95/p99 latency is not claimed.
- Exactly-once DLQ routing is not claimed.
- Clean single-message DLQ semantics are not claimed.
- Production-grade poison-message handling is not claimed.
- Enterprise-certified security is not claimed.
- Multi-region production architecture is not claimed.

---

## Final Verdict

This project is now strong as a GCP Data Engineering portfolio asset.

It is credible because it does not overclaim. It has real GCP infrastructure, real
bounded workload evidence, real failure-path evidence, real CI, real Terraform state,
real alerting evidence, and documented caveats.

The next improvement should not be another large feature. The next improvement should
be precision: DLQ deduplication strategy, steady-state throughput plan, and latency
instrumentation plan.
