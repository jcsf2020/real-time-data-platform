# Recruiter-Facing Platform Summary

**Date:** 2026-05-20
**Audience:** Recruiters, hiring managers, non-deep-technical stakeholders
**Purpose:** One-page hiring and B2B translation of the Real-Time Data Platform evidence

---

## Short Pitch

This is a GCP real-time data platform project built as evidence-first portfolio work.
It validates a Pub/Sub -> Cloud Run -> Cloud SQL event-processing path with BigQuery,
dbt, Terraform, CI, structured logs, Cloud Monitoring metrics, and alerting.
The platform was validated at 50,000 events in a controlled cloud run with zero errors
and zero duplicate rows.
This is bounded evidence, not a sustained production benchmark.
Dataflow is not implemented.

---

## What This Project Demonstrates

| Capability | Evidence | Hiring Signal |
|---|---|---|
| GCP event processing | 50,000-event end-to-end cloud run; 0 errors; 0 duplicates | Operates real cloud infrastructure at non-trivial scale |
| Python worker processing | Cloud Run worker handled 50,000 events; structured JSON logs per event | Production-style service development in Python |
| Pub/Sub | 50,000 unique message IDs published; DLQ policy configured (maxDeliveryAttempts=5) | Understands managed messaging, idempotency, and failure policy |
| Cloud Run | Worker, API, dbt job, and BigQuery append job all on Cloud Run | Serverless GCP deployment across multiple service types |
| Cloud SQL / Postgres | 50,000 rows written; 0 duplicate event_id; ON CONFLICT idempotency | SQL-based write-path integrity at bounded scale |
| BigQuery analytical layer | rtdp_analytics dataset; 3 DAY-partitioned tables; cursor-based incremental append; 6,120 rows; 0 duplicates | End-to-end analytical tier deployed and validated |
| dbt incremental models | Silver and gold models; delete+insert strategy; 22 dbt tests; Cloud SQL live execution proven | Governed transformation layer, not just local testing |
| Terraform IaC | 100% GCP resource coverage; GCS remote state; PLAN_EXIT=0 throughout; Workload Identity for CI | Infrastructure-as-code discipline across the full stack |
| Cloud Monitoring / logs | 4 logs-based metrics with datapoints; 12 BigQuery quality time series per run; 4-panel dashboard | Observability wired and data-backed, not aspirational |
| CI validation | pytest (241 tests), ruff, Terraform plan CI on every push; dbt compile/run/test in CI | Automated quality gate at every merge |
| Data quality checks | 8-check BigQuery quality workflow; scheduled execution proven; controlled failure and pass runs both evidenced | Quality-first engineering with verifiable pass/fail signal |
| Incident / email notification | Cloud Monitoring alert -> OPEN incident -> email delivery; proven by CLI output and Gmail inbox screenshot | Full alerting loop closed end-to-end |
| Cost control | Cloud SQL NEVER/STOPPED verified in 60+ evidence docs; schedulers PAUSED by default; no idle compute | Demonstrates operational discipline and cloud cost awareness |

---

## Latest Validated Milestone

**50,000-event bounded GCP cloud load test -- 2026-05-20**

| Metric | Value |
|---|---|
| Events published | 50,000 |
| Unique Pub/Sub message IDs | 50,000 |
| Publish errors | 0 |
| Worker OK logs | 50,000 |
| Worker errors | 0 |
| Cloud SQL rows (prefix match) | 50,000 |
| Duplicate event_id count | 0 |
| Cloud Monitoring processed metric | 50,002 |
| Cloud Monitoring error metric | 0 |
| Terraform plan exit code | PLAN_EXIT=0 |
| Cloud SQL final state | STOPPED / NEVER |
| Schedulers final state | PAUSED |

**Why Cloud Monitoring shows 50,002 instead of 50,000:**
Cloud Monitoring DELTA window alignment can cause slight overcounting at window edges.
The structured worker logs and Cloud SQL row count (both exactly 50,000) are the
authoritative proof. The 50,002 metric value is expected, explained, and consistent
with zero error signal.

Evidence document: [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md)

---

## Why It Matters for Hiring

- **Proves practical GCP exposure.** Every GCP service (Pub/Sub, Cloud Run, Cloud SQL,
  BigQuery, Secret Manager, Artifact Registry, Cloud Monitoring, Cloud Scheduler) is
  deployed, Terraform-managed, and evidenced with verifiable run IDs -- not listed on
  a CV without proof.

- **Proves cloud debugging ability.** A DATABASE_URL secret newline issue was diagnosed,
  fixed (PR #176), and documented before the 50k run. API readiness was gated before
  any events were published. Problems were caught, traced, and resolved with evidence.

- **Proves evidence-backed engineering.** 60+ scoped evidence documents with specific
  run IDs, commit SHAs, and GCP resource names. Every claim is verifiable by an
  independent technical reviewer.

- **Proves IaC discipline.** Terraform zero-diff (PLAN_EXIT=0) maintained after every
  live execution. No infrastructure was mutated outside of planned apply operations.
  Workload Identity Federation eliminates stored service account keys in CI.

- **Proves observability and incident awareness.** A full alerting loop is closed:
  BigQuery quality failure -> Cloud Monitoring metric push -> OPEN incident -> email
  delivery. Proven by CLI output and Gmail inbox screenshot evidence.

- **Proves ability to communicate limitations honestly.** NOT YET PROVEN and Dataflow
  not implemented markers appear consistently throughout the evidence base. Honest
  limitation statements are included in every evidence document. This is an asset,
  not a weakness, for a reviewer who values engineering integrity.

---

## Safe Interview Positioning

> "I validated a GCP event-processing path at 50,000 events with Pub/Sub, Cloud Run,
> Cloud SQL, structured logs, Cloud Monitoring metrics, Terraform zero-diff checks, and
> indexed evidence. I do not claim sustained production throughput or Dataflow
> implementation; I present it as bounded, evidence-backed platform work."

---

## What I Would Not Claim

The following items are explicitly not part of this project's evidence base:

- **Dataflow implemented.** Cloud Run is the worker. No Apache Beam or Dataflow pipeline
  exists. Windowed aggregations, stateful streaming, and late-event handling are not proven.

- **Sustained production throughput.** All load tests are bounded, deterministic bursts.
  No steady-state streaming at constant throughput over an extended window is validated.

- **Exactly-once production semantics.** ON CONFLICT idempotency is proven at bounded
  scale. End-to-end exactly-once delivery semantics in a high-throughput production
  scenario are not claimed.

- **Enterprise-certified security.** Workload Identity Federation, Secret Manager, and
  job-scoped IAM are implemented. No SOC 2, GDPR DPA, penetration test, or enterprise
  security audit exists.

- **Multi-region production architecture.** Single GCP project, single region
  (europe-west1). No staging environment, canary deploys, or multi-region failover.

- **Mature replay / backfill semantics.** The BigQuery incremental append job provides
  cursor-based reprocessing from Cloud SQL. A full streaming replay or message-level
  rewind mechanism is not documented or proven.

---

## Best-Fit Roles

| Role Type | Fit |
|---|---|
| Data Engineer | Strong -- Pub/Sub, Cloud Run, Cloud SQL, BigQuery, dbt, Terraform, CI, observability all evidenced |
| Data Platform Engineer | Strong -- full IaC coverage, Workload Identity, cost-control discipline, alerting loop proven |
| Analytics Engineer with cloud / platform exposure | Good -- dbt incremental models, BigQuery quality workflow, scheduled execution, Cloud Monitoring custom metrics |
| GCP-focused Data Engineer | Strong -- every major GCP data service deployed, Terraform-managed, and evidenced |
| Junior / Mid Data Engineer with strong portfolio evidence | Strong -- 60+ indexed evidence docs, 241 tests, clean CI, honest limitation statements |
| B2B / freelance data platform delivery | Good -- bounded milestone delivery model; runbook-driven execution; cost-safe state maintained throughout |

---

## Evidence Links

| Document | What It Contains |
|---|---|
| [docs/executive-platform-audit-after-50k.md](executive-platform-audit-after-50k.md) | Full post-50k platform audit with devil-advocate review, gap tracking, and recruiter translation |
| [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md) | Primary 50,000-event cloud load test evidence with all acceptance criteria |
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog -- 60+ documents by category |
| [docs/gcp-architecture.md](gcp-architecture.md) | GCP service mapping and validated event-processing path |
| [docs/dbt-cloud-sql-incremental-execution-proof.md](dbt-cloud-sql-incremental-execution-proof.md) | dbt incremental execution against live Cloud SQL; dbt run PASS=2; dbt test PASS=22 |
| [docs/bigquery-quality-incident-notification-delivery-proof.md](bigquery-quality-incident-notification-delivery-proof.md) | End-to-end alerting loop: quality failure -> Cloud Monitoring incident -> email delivery |
