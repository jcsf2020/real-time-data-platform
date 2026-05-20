# Steady-State Throughput Test Plan

## Status

| Field | State |
|---|---|
| Document type | PLAN ONLY |
| New GCP workload execution | No |
| New events published | No |
| Cloud SQL started | No |
| Terraform apply executed | No |
| Sustained throughput validated | NOT YET PROVEN |

This document defines the next controlled validation step after the 50,000-event bounded
cloud load test and DLQ malformed-message validation. It does not execute any workload.

---

## Purpose

The current project has strong bounded load evidence: 50,000 events were published,
processed, persisted, observed, and validated with zero duplicates and zero worker errors.

However, the 50k test was a bounded sequential publish-and-ack workload. It proves
correctness, idempotency, observability, and operational discipline at meaningful scale.
It does not prove sustained steady-state throughput.

This plan defines a safe future test to validate whether the platform can sustain a
controlled fixed publish rate for a defined time window.

---

## Current Evidence Baseline

| Area | Current state |
|---|---|
| 50k bounded cloud load test | VALIDATED |
| Average 50k publish rate | 14.62 events/sec, client-side conservative |
| Pub/Sub -> Cloud Run -> Cloud SQL path | VALIDATED |
| Worker errors during 50k | 0 |
| Duplicate event_ids during 50k | 0 |
| Cloud Monitoring metrics | VALIDATED |
| Terraform drift | PLAN_EXIT=0 |
| DLQ malformed-message routing | VALIDATED WITH OBSERVED CAVEAT |
| DLQ deduplication strategy | DOCUMENTED |
| Sustained throughput | NOT YET PROVEN |
| p50/p95/p99 latency | NOT YET MEASURED |
| Dataflow | NOT IMPLEMENTED |

---

## Target Test Shape

Recommended initial steady-state validation:

| Parameter | Value |
|---|---|
| Target rate | 10 events/sec |
| Duration | 30 minutes |
| Expected events | 18,000 |
| Publish pattern | fixed-rate paced publishing |
| Topic | market-events-raw |
| Worker | rtdp-pubsub-worker |
| Persistence target | Cloud SQL bronze.market_events |
| Validation target | Cloud SQL prefix row count + worker logs + Cloud Monitoring |
| Cloud SQL lifecycle | start before test, restore to NEVER/STOPPED after test |
| Scheduler lifecycle | remain PAUSED throughout |
| Terraform apply | forbidden |
| Dataflow | not used |

This target is intentionally conservative. It is not designed to find maximum throughput.
It is designed to prove that the platform can maintain a stable ingestion rate over time
without relying on a burst/bounded publish pattern.

---

## Why 10 Events/Sec First

10 events/sec for 30 minutes gives a clean first sustained proof:

- Large enough to exceed toy-demo scale.
- Small enough to control cost and operational risk.
- Easy to reason about: 600 events/minute, 18,000 events total.
- Below the already observed bounded publish rate from the 50k test.
- Suitable for validating stability before increasing volume.
- Safer than jumping directly to saturation testing.

This is a production-like stability test, not a benchmark ceiling test.

---

## Acceptance Criteria

The future execution is accepted only if all criteria pass:

| Criterion | Required result |
|---|---|
| Publish count | 18,000 attempted and 18,000 acknowledged |
| Publish pacing | average close to 10 events/sec over 30 minutes |
| Worker OK logs | 18,000 status=ok entries for the test prefix |
| Worker errors | 0 for the test prefix |
| Cloud SQL rows | 18,000 rows for the test prefix |
| Duplicate event_ids | 0 |
| DLQ messages | 0 for the test prefix |
| Cloud Monitoring processed metric | confirms expected scale, with window caveat documented |
| Cloud Monitoring error metric | 0 |
| Cloud SQL final state | STOPPED / NEVER |
| Schedulers final state | PAUSED |
| Terraform plan | PLAN_EXIT=0 after execution |
| Evidence document | created separately after execution |

---

## Required Instrumentation

The future execution should generate a machine-readable report with at least:

| Field | Purpose |
|---|---|
| run_id | unique steady-state run identifier |
| test_prefix | unique event_id prefix |
| target_events_per_second | configured target rate |
| target_duration_seconds | configured duration |
| expected_total_events | expected event count |
| publish_start_time_utc | start window |
| publish_end_time_utc | end window |
| attempted_count | attempted events |
| acknowledged_count | successful Pub/Sub acks |
| publish_error_count | failed publishes |
| elapsed_seconds | actual elapsed time |
| observed_events_per_second | actual average publish rate |
| min_publish_interval_ms | pacing guard |
| max_publish_interval_ms | pacing guard |
| payload_sha256_sample | evidence reproducibility |
| script_version | reproducibility |

---

## Preflight Checks

Before execution:

| Check | Required result |
|---|---|
| Branch | execution branch, not this plan branch |
| git status | clean or docs-only expected changes |
| Cloud SQL | STOPPED / NEVER before controlled start |
| Schedulers | PAUSED |
| Pub/Sub topic | market-events-raw exists |
| Worker | rtdp-pubsub-worker Ready |
| DLQ topic | market-events-raw-dlq exists |
| DLQ baseline | no messages for new test prefix |
| pytest | pass |
| ruff | pass |
| terraform fmt | pass |
| terraform validate | pass |
| terraform plan | PLAN_EXIT=0 |

Abort if any preflight check fails.

---

## Future Execution Outline

Do not run these steps in this plan branch.

1. Create an execution branch.
2. Generate a unique run_id and test_prefix.
3. Confirm Cloud SQL is STOPPED / NEVER.
4. Start Cloud SQL only for the controlled test window.
5. Confirm worker readiness.
6. Run the paced publisher at 10 events/sec for 30 minutes.
7. Capture publish report.
8. Query worker logs for status=ok and status=error counts.
9. Query Cloud SQL row count and duplicate event_id count for the prefix.
10. Query DLQ for the prefix.
11. Query Cloud Monitoring processed/error metrics.
12. Restore Cloud SQL to NEVER / STOPPED.
13. Confirm schedulers remained PAUSED.
14. Run Terraform plan and confirm PLAN_EXIT=0.
15. Create an execution evidence document.

---

## What This Will Prove

If accepted, the future execution will prove:

- The platform can sustain a fixed, controlled event rate for a defined time window.
- Pub/Sub, Cloud Run worker, and Cloud SQL remain stable under paced sustained load.
- The worker does not accumulate visible errors during the test window.
- The persistence layer remains idempotent under a sustained input stream.
- Operational controls remain intact after execution.

---

## What This Will Not Prove

- Maximum throughput.
- Multi-hour or multi-day production stability.
- Saturation point of Cloud Run or Cloud SQL.
- p50/p95/p99 latency.
- Exactly-once production semantics.
- Dataflow streaming capability.
- Enterprise-grade multi-region resilience.
- Production-grade SLO enforcement.

---

## Scale-Up Path

Only after 10 events/sec for 30 minutes passes:

| Phase | Target | Purpose |
|---|---|---|
| Phase 1 | 10 events/sec for 30 min | first sustained proof |
| Phase 2 | 25 events/sec for 30 min | moderate sustained proof |
| Phase 3 | 50 events/sec for 30 min | higher sustained proof |
| Phase 4 | 10 events/sec for 2 hours | duration proof |
| Phase 5 | saturation test | only if justified; not immediate |

Do not skip phases. Each phase requires its own evidence.

---

## Safe Interview Wording

Use this only after the future execution passes:

> I validated not only bounded 50,000-event processing, but also a controlled
> steady-state workload at a fixed publish rate. I treat this as stability evidence,
> not a maximum throughput claim.

Until execution is performed, use:

> I have bounded 50,000-event evidence and a documented steady-state test plan. Sustained
> throughput remains planned, not yet proven.

---

## Explicit Non-Claims

- Sustained throughput is not yet proven by this plan.
- Maximum throughput is not claimed.
- p50/p95/p99 latency is not claimed.
- Dataflow is not implemented.
- Exactly-once production semantics are not claimed.
- Enterprise-grade production scale is not claimed.
- Terraform apply is not executed by this plan.
- No new events are published by this plan.

---

## Final Verdict

This is the correct next gap after the 50k and DLQ work. The project already proves
bounded correctness and reliability behaviour. The next production-like step is sustained,
paced throughput evidence with conservative scope, strict cost controls, and no
overclaiming.
