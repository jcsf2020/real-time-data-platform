# Platform Audit After Cost/Performance Summary

**Status:** EXECUTIVE AUDIT -- post-cost/performance platform assessment
**Date:** 2026-05-22
**Branch:** docs/platform-audit-after-cost-performance

---

## 1. Executive Summary

The Real-Time Data Platform is now a strong GCP Data Engineering portfolio asset.
Evidence spans ingestion (Pub/Sub + Cloud Run), persistence (Cloud SQL PostgreSQL),
analytics (BigQuery + dbt), observability (Cloud Monitoring, logs-based metrics,
structured logs), alerting (incident creation and email notification delivery proven),
infrastructure-as-code (Terraform, zero-diff discipline throughout), sustained throughput
(50,000-event bounded load test, 10 events/sec for 30 minutes), p50/p95/p99 latency
evidence (artifact/log join), and cost-control posture (Cloud SQL STOPPED/NEVER,
schedulers PAUSED, Cloud Run maxScale=1).

This audit synthesises what has been closed, what remains open, and how the evidence
positions the project for GCP-oriented Data Engineer and Data Platform Engineer roles.
It does not claim Dataflow, exactly-once production semantics, maximum throughput, or
enterprise-certified production readiness.

---

## 2. What Has Been Closed

| Capability | Evidence | Caveats |
|---|---|---|
| 50,000-event bounded cloud load test | load-test-50000-cloud-evidence.md | Bounded validation; not a claim of enterprise-scale throughput |
| Sustained 10 events/sec for 30 minutes | steady-state-10eps-30min-cloud-validation-evidence.md | 18,000 attempted and acknowledged publishes; 0 publish errors; 0 missing worker events |
| p50/p95/p99 latency | steady-state-10eps-30min-cloud-validation-evidence.md | Artifact/log join; p50=154.385 ms, p95=227.59 ms, p99=693.995 ms; max=960,263.973 ms documented as outlier/delayed-observation caveat; persisted DB latency NOT implemented |
| Cost-control posture | cost-performance-summary.md | Cloud SQL STOPPED/NEVER; schedulers PAUSED; Cloud Run maxScale=1, concurrency=1; no exact EUR/USD/GBP cost claimed; billing export not analyzed |
| BigQuery analytical tier | bigquery-terraform-apply-evidence.md, bigquery-bounded-backfill-evidence.md, bigquery-incremental-append-evidence.md | Dataset rtdp_analytics + 3 tables; 6,120 rows; cursor-based incremental MERGE; quality checks with Cloud Monitoring metrics and email alert delivery proven |
| dbt incremental execution | dbt-cloud-sql-incremental-execution-proof.md | Cloud SQL live incremental dbt execution proven; dbt run PASS=2; dbt test PASS=22; Cloud SQL live execution proven |
| Alerting and incident notification | bigquery-quality-incident-notification-delivery-proof.md | Alert policy OPEN incident proven by CLI; email delivery proven by Gmail inbox screenshot |
| Terraform zero-diff discipline | All *-import-plan-evidence.md files; bigquery-terraform-apply-evidence.md | PLAN_EXIT=0 across all evidence branches |
| DLQ malformed routing | dlq-malformed-message-validation-evidence.md | Malformed payload reached DLQ; exactly-once DLQ routing NOT claimed; multiple delivery counts observed |
| Evidence index / recruiter-facing documentation | EVIDENCE_INDEX.md, recruiter-facing-platform-summary.md, portfolio-b2b-narrative.md | Curated documentation map; safe interview positioning documented |

---

## 3. What Remains Open

| Gap | Impact | Notes |
|---|---|---|
| Dataflow / Apache Beam not implemented | High for streaming-first JDs | Cloud Run worker handles Pub/Sub push; Dataflow deferred pending higher-scale or replay requirements |
| Replay/backfill strategy partial | Medium | Bounded backfill proven; automated replay consumer not implemented |
| DLQ production consumer not implemented | Medium | DLQ routing proven; no automated consumer reads or reprocesses DLQ messages in production |
| dbt-specific observability metrics open | Low-medium | No custom Cloud Monitoring metrics emitted from dbt job execution itself |
| Cloud SQL persisted latency columns not implemented | Low-medium | p50/p95/p99 derived from artifact/log join; DB-persisted latency analytics would be more robust |
| Exact cost per event not calculated | Low | cost_per_event formula documented; billing export not analyzed; no EUR/USD/GBP figure proven |
| Staging/prod split missing | Medium | Single GCP project; no isolated staging environment |
| Deploy-on-merge not implemented | Low-medium | Both worker and API deploy workflows require manual workflow_dispatch |
| Product-facing dashboard missing | Low | Cloud Monitoring 4-panel internal dashboard exists; no end-user or stakeholder-facing product dashboard |
| Enterprise security certification not present | Out of scope | No SOC 2, ISO 27001, or equivalent audit performed |
| Maximum throughput / saturation point not claimed | Medium | 50,000-event bounded load tested; saturation point, queue depth limits, and back-pressure behavior not characterized |
| Multi-day production stability not proven | High for production credibility | Scheduler runs are bounded and paused; no continuous multi-day live data flow proven |

---

## 4. Recruitment Value Assessment

| Evidence | Recruitment Signal |
|---|---|
| Pub/Sub + Cloud Run + Cloud SQL | GCP event-processing pattern; demonstrates managed messaging, serverless compute, and relational persistence |
| BigQuery + dbt | Analytics engineering layer; demonstrates analytical tier design, incremental models, and data quality discipline |
| Terraform zero-diff | Infrastructure discipline; shows IaC ownership, state management, and change control |
| Cloud Monitoring + incident email | Operational maturity; alert policies, logs-based metrics, structured logs, and proven notification delivery |
| 50,000-event bounded load + 10 eps sustained | Scale and sustained throughput credibility; concrete numbers with acceptance criteria |
| p50/p95/p99 latency evidence | Observability and performance literacy; shows the candidate can instrument, measure, and reason about latency |
| Cost-control posture summary | Pragmatic cloud ownership; stopping Cloud SQL when idle, capping Cloud Run scale, and documenting cost drivers without inflating claims |

---

## 5. Devil's Advocate Review

The following criticisms are accurate and should be understood before interviews.

**Still not a full enterprise production system.**
The platform handles bounded, controlled validation runs in a single GCP project.
It has never processed continuous multi-day live production traffic.

**Dataflow not implemented.**
Cloud Run push-pull worker is not equivalent to Apache Beam / Dataflow.
Roles requiring Dataflow, windowing semantics, or exactly-once streaming pipelines
cannot be satisfied by this evidence.

**Exactly-once production semantics not claimed.**
Pub/Sub guarantees at-least-once delivery. The worker writes to Cloud SQL using
event_id deduplication, but exactly-once end-to-end semantics under concurrent
failure scenarios have not been formally proven.

**Cost per event not proven without billing export.**
The cost_per_event formula is documented. Actual GCP billing export has not been
analyzed. No EUR, USD, or GBP figure should be cited in interviews without the
caveat that it is a formula estimate, not a measured invoice value.

**Cloud SQL STOPPED/NEVER is good for cost, but not a production availability posture.**
Stopping the database between validation runs demonstrates cost discipline.
In a production system, this posture would require an activation strategy, warm-up
time, and connection pool management that have not been implemented.

**Single GCP project; no staging/prod split.**
All infrastructure lives in one project. There is no isolation between
experimentation and production-equivalent workloads.

**Manual deploy workflow remains.**
Both the worker and API Cloud Run deployments require explicit workflow_dispatch.
There is no automated deploy-on-merge pipeline.

**Artifact/log latency is useful, but persisted DB latency analytics would be stronger.**
p50/p95/p99 are computed from a producer artifact joined with worker Cloud Logging
structured logs. This approach depends on log retention and timestamp accuracy.
Persisted latency columns in Cloud SQL would enable richer, query-time analysis.

---

## 6. Safe Interview Positioning

The following statement is accurate and should be used verbatim or paraphrased
closely. Do not inflate it.

> "I validated a GCP event-processing platform with Pub/Sub, Cloud Run, Cloud SQL,
> BigQuery, dbt, Terraform, Cloud Monitoring, alerting, DLQ evidence, a 50,000-event
> bounded load test, and a sustained 10 events/sec for 30 minutes run with p50/p95/p99
> latency evidence. I do not claim Dataflow, exactly-once production semantics,
> maximum throughput, or enterprise-certified production readiness."

If pressed on cost:

> "I documented the cost drivers and a cost_per_event formula, but I have not
> analyzed a real billing export. I cannot cite an exact figure per event."

If pressed on production readiness:

> "The platform has been validated through bounded, controlled tests in a single
> GCP project. It is a portfolio demonstration, not a multi-team production system
> with SLA obligations."

---

## 7. Recommended Next Branches

Prioritised by recruitment ROI. All are documentation or low-risk planning branches
unless stated otherwise.

### P1 -- Closes the most visible remaining gaps

| Branch | Rationale |
|---|---|
| `docs/replay-backfill-strategy` | Documents the replay and backfill approach; directly answers a common data platform interview question |
| `feat/dbt-observability-metrics-plan` or `docs/dbt-observability-metrics-plan` | Closes the dbt observability gap; adds depth to the analytics engineering story |
| `docs/dataflow-decision-record` | Explains why Dataflow was deferred; shows architectural reasoning rather than ignorance |

### P2 -- Operational maturity improvements

| Branch | Rationale |
|---|---|
| `docs/staging-environment-plan` | Addresses the single-project gap; shows environment isolation awareness |
| `docs/cloud-sql-persisted-latency-plan` | Plans the stronger latency analytics approach; complements the artifact/log join evidence |
| `docs/deploy-on-merge-decision-record` | Explains the manual dispatch choice; documents trade-offs and a path to CI/CD automation |

### P3 -- Nice-to-have for completeness

| Branch | Rationale |
|---|---|
| `docs/dashboard-productization-plan` | Outlines a stakeholder-facing dashboard concept; differentiates from internal Cloud Monitoring panels |
| `docs/billing-export-cost-per-event-plan` | Plans a billing export analysis to convert the formula to a measured cost figure |

---

## 8. Final Verdict

The project is now strong for **Data Engineer** and **Data Platform Engineer** recruitment,
particularly for GCP-oriented roles. The evidence covers the full pipeline lifecycle:
ingestion, persistence, analytics, observability, alerting, IaC, throughput, latency,
and cost awareness.

The most significant remaining gaps -- Dataflow, staging/prod split, multi-day
production stability, and exact cost per event -- are either intentionally deferred
or out of scope for a portfolio project. They should be disclosed proactively in
interviews, not hidden.

Closing P1 branches (replay/backfill strategy, dbt observability metrics plan,
Dataflow decision record) will further strengthen the operational maturity narrative
without requiring any additional GCP spend or infrastructure changes.
