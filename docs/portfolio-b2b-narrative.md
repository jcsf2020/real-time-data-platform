# Real-Time Data Platform -- Portfolio and B2B Narrative

**Purpose:** Recruiter and B2B technical front-door summary.

**For deep technical review:** see [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) and
[docs/ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md).

**Date:** 2026-05-19

---

## Executive Positioning

A GCP-native, evidence-backed data engineering platform demonstrating production-light
operation: real-time event ingestion via Pub/Sub, governed dbt transformations on Cloud Run,
a BigQuery analytical tier with cursor-based incremental append, full Terraform IaC coverage
across all deployed GCP resources, data quality monitoring with live incident creation and
email notification delivery proven end-to-end, and principled cost control.

This is a portfolio-grade platform, not a continuously running production service. Every
capability is backed by a scoped runbook and an accepted evidence document with verifiable
run IDs. Claims that cannot be evidenced are not made.

---

## What Is Validated

### Ingestion and Serving

- Pub/Sub topic and push subscription to Cloud Run worker (`rtdp-pubsub-worker`): validated end-to-end
- Idempotent bronze writes: `ON CONFLICT(event_id) DO NOTHING` confirmed at persistence layer
- FastAPI serving layer (`rtdp-api`) on Cloud Run: health, readiness, events, aggregates endpoints
- Bounded load tests: 100, 1,000, and 5,000 events -- all acceptance criteria met; metric sums confirmed
- Configured dead-letter policy: `deadLetterPolicy`, `maxDeliveryAttempts=5`, 10s/60s backoff, DLQ topic

### Transformation and Analytics

- dbt silver and gold models on Cloud Run Job (`rtdp-dbt-refresh-job`): 22 dbt tests, Cloud SQL parity confirmed
- Scheduler-triggered dbt execution: `rtdp-dbt-refresh-job` dispatched by Cloud Scheduler (`PAUSED` by default)
- BigQuery analytical tier: dataset `rtdp_analytics` (europe-west1); three Terraform-managed, DAY-partitioned tables
- BigQuery bounded backfill: 6,120 rows from `bronze.market_events`; source/target count match accepted
- BigQuery incremental append: cursor-based MERGE; idempotent; second run confirms zero net inserts
- BigQuery append scheduler: `rtdp-bigquery-append-scheduler`; proof executions accepted (`PAUSED` by default)

### Data Quality and Alerting

- Read-only BigQuery quality workflow: 6 base checks + `row_count_minimum` threshold + `freshness_age_hours` threshold
- Scheduled quality execution: real `event: schedule` run proven (PR #167; Run ID 26028523804; cron `15 6 * * *`)
- Cloud Monitoring quality metrics: 12 custom time series pushed per run under `custom.googleapis.com/rtdp/bigquery_quality/`
- Alert policy (`RTDP BigQuery Quality Failure`): Terraform-managed; enabled; `failed_checks_count` trigger
- Incident creation: Cloud Monitoring OPEN incident proven via CLI (PR #169; Run ID 26089332693)
- Email notification delivery: Gmail inbox delivery proven by screenshot evidence (PR #169)

### Infrastructure, Security, and Cost Control

- Terraform: 100% GCP resource coverage; GCS-backed remote state; zero-diff plans on all resource batches
- Workload Identity Federation: GitHub Actions OIDC -- no stored service account keys in CI
- Scheduler IAM hardening: project-level `roles/run.invoker` replaced with two job-scoped bindings
- Artifact Registry: Docker repository; commit-SHA image tags on all deployed images
- Cloud SQL cost control: `rtdp-postgres` kept `NEVER / STOPPED` outside bounded validation windows
- Scheduler cost control: both schedulers `PAUSED` by default; resumed only for controlled execution proofs

### Observability

- Four logs-based Cloud Monitoring metrics with confirmed timeSeries datapoints
- 4-panel RTDP Pipeline Overview dashboard (version-controlled at `infra/monitoring/dashboards/`)
- Two infrastructure alert policies (worker error, silver refresh error) with email notification channel
- BigQuery quality custom metrics: status, failed_checks_count, check_pass, row_count, freshness_age_hours

---

## What Is Intentionally Not Claimed

| Item | Correct Statement |
|---|---|
| Dataflow / stateful windowed streaming | Not implemented. Cloud Run is the worker. No Dataflow pipeline exists in this repository. |
| Continuous production traffic | Not a continuously running production service. Compute is inactive outside bounded validation windows. |
| Sustained throughput above 5,000 events | Bounded burst tests only. Steady-state streaming throughput is not validated. |
| Automatic deploy-on-merge (CD) | Both deploy workflows require explicit manual `workflow_dispatch`. No deploy happens automatically on merge. |
| Incremental dbt models | Silver and gold models use full-refresh table materialization. Incremental merge is not yet implemented. |
| GitHub notification bell delivery | Email delivery is proven (PR #169). GitHub notification bell delivery is not yet proven. |
| Multi-environment deployment | Single GCP project. No staging environment, no canary deployment, no multi-region. |
| Real-world data variability | All events are synthetic deterministic records with predictable event-ID prefixes. |

---

## Evidence Entry Points

Recommended reading path for a technical reviewer:

1. [docs/ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) -- architecture overview, validated capabilities, key trade-offs, and known gaps
2. [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) -- complete catalog of 60+ evidence documents by category
3. [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) -- Pub/Sub to Cloud Run to Cloud SQL to API path
4. [docs/bigquery-quality-incident-notification-delivery-proof.md](bigquery-quality-incident-notification-delivery-proof.md) -- most recent end-to-end proof: incident creation and email delivery (PR #169)
5. [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) -- bounded throughput evidence (5,000 events)
6. [infra/terraform/gcp/](../infra/terraform/gcp/) -- Terraform resource definitions for all deployed GCP services

For a time-bounded review, steps 1 through 3 cover the full capability scope and take
approximately 20 minutes.

---

## Recruiter and B2B Talking Points

**Cloud-native GCP data platform.** Every deployed platform component runs on GCP managed services:
Pub/Sub for ingestion, Cloud Run for processing and transformation, Cloud SQL for operational
serving, BigQuery for analytics, Cloud Scheduler for orchestration, Cloud Monitoring for
alerting, and Artifact Registry for image management. No self-managed brokers, no
containerised databases in production.

**Terraform at 100% resource coverage.** Every deployed GCP resource is Terraform-managed
with a GCS-backed remote state and validated zero-diff plans. Resources were imported in
phased batches without destroy-and-recreate operations on live infrastructure. This is the
IaC maturity a senior platform engineer is expected to bring rather than learn on the job.

**Evidence discipline.** Every execution is documented in a scoped evidence file with run
IDs, CLI output, and explicit NOT YET PROVEN markers for anything not yet demonstrated. A
reviewer can verify every claimed capability directly from the repository without trusting
prose summaries.

**Governed dbt transformations.** Silver and gold models run on Cloud Run, dispatched by
Cloud Scheduler, with 22 dbt tests passing on every CI push against an ephemeral pgvector
container. Credentials are managed through Secret Manager and a runtime-only `profiles.yml`
that is deleted after each execution -- no credentials are ever committed.

**End-to-end incident response.** A BigQuery quality check failure triggers a Cloud
Monitoring alert, creates an OPEN incident, and delivers an email notification. This chain
-- from data check failure to delivered alert -- is proven end-to-end with CLI evidence and
Gmail inbox screenshot evidence (PR #169, Run ID 26089332693).

**Cost-controlled portfolio discipline.** Cloud SQL is `NEVER / STOPPED` outside bounded
windows. Schedulers are `PAUSED` by default. No idle compute runs between validation
exercises. This is verifiable from the evidence trail and signals the cost awareness
expected in a senior data or platform engineering role.

---

## 2026--2027 Relevance

| Hiring Signal | Platform Evidence |
|---|---|
| GCP expertise | Pub/Sub, Cloud Run (services + jobs), Cloud SQL, BigQuery, Secret Manager, Artifact Registry, Workload Identity, Cloud Monitoring, Cloud Scheduler -- all Terraform-managed and evidence-backed |
| BigQuery proficiency | Terraform-managed dataset; bounded backfill and cursor-based incremental append proven; quality checks with Cloud Monitoring custom metrics and incident delivery |
| dbt operational maturity | 22 dbt tests; CI on every push against an ephemeral container; scheduler-triggered Cloud Run execution accepted; Cloud SQL parity evidence |
| Data quality engineering | 8-check read-only quality workflow; threshold checks; controlled failure proof; scheduled execution proven; custom Cloud Monitoring metrics; incident creation; email notification delivery |
| Keyless CI security | Workload Identity Federation for GitHub Actions; no stored service account keys |
| IaC-first engineering | 100% Terraform; GCS remote state; zero-diff plans; phased import documentation |
| Evidence-based delivery | 60+ evidence documents; EVIDENCE_INDEX; ARCHITECTURE_REVIEW; explicit gap tracking with NOT YET PROVEN markers |

**Biggest positioning gap for real-time roles:** Dataflow is not implemented. Cloud Run is
the current worker; no stateful windowed aggregations exist. This is the most visible gap
against a job description requiring Dataflow or Apache Beam experience.

**Biggest dbt gap for senior roles:** Incremental materialization is not yet implemented.
Models use full-refresh table materialization. Converting to incremental merge is the
highest-value next dbt step.

---

## Current Gaps and Next Technical Moves

Confirmed as of 2026-05-19, ranked by B2B / recruiter value:

| Gap | Status | Next Step |
|---|---|---|
| GitHub notification bell delivery | Not yet proven | Prove bell delivery on a quality failure -- no code change required |
| Incremental dbt models | Not yet implemented | Convert silver and gold to incremental merge materialization |
| Automatic deploy-on-merge | Manual `workflow_dispatch` only | Add push trigger on `main` scoped to the worker service |
| Dataflow streaming enrichment | Not implemented | Implement Pub/Sub to Dataflow to BigQuery for windowed aggregations; largest step-change in real-time credibility; highest implementation cost |
| Sustained throughput above 5,000 events | Not validated | Validate steady-state streaming at 50 msg/s sustained over a timed window |

The platform is at a stage where the evidence base supports a senior Data Engineer or Data
Platform Engineer portfolio review. The controlled failure proof, threshold quality checks,
Cloud Monitoring custom metrics integration, incident creation, and email notification
delivery add operational maturity signal that distinguishes this platform from a one-pass
demo project.

See [docs/gaps-resolved-vs-remaining-report.md](gaps-resolved-vs-remaining-report.md) for a
detailed gap-by-gap analysis with B2B value rankings and recommended execution order.
