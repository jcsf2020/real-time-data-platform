# Architecture Decision Record: Apache Beam / Google Cloud Dataflow

**Status:** DECISION RECORD -- Dataflow / Apache Beam not implemented; next proof branch defined
**Date:** 2026-05-23
**Branch:** `docs/dataflow-apache-beam-architecture-decision`
**Author intent:** Portfolio-grade GCP Data Engineering architecture decision. No implementation in this branch. No GCP resources mutated. Evidence-first, honest scoping throughout.

---

## 1. Executive Summary

The Real-Time Data Platform currently operates on a validated Pub/Sub → Cloud Run worker → Cloud SQL → BigQuery → dbt → Cloud Monitoring path. This path has been proven at 50,000 bounded events, at 10 events/sec sustained for 30 minutes, and with a complete observability and alerting loop through Cloud Monitoring and email delivery. All infrastructure is Terraform-managed with GCS remote state.

**The Cloud Run worker remains the correct choice for the current MVP ingestion path.** It is cost-controlled, operationally simple, and has produced credible evidence at the current validated scale. There is no measured evidence that it is approaching its throughput ceiling.

**Apache Beam / Google Cloud Dataflow becomes the high-value next extension** when one or more of the following conditions are met by measured evidence: replay semantics requiring message-level rewind, event-time windowed aggregations, stateful transforms, late or out-of-order event handling, autoscaling beyond a single Cloud Run instance, or a sustained throughput requirement that exceeds the Cloud Run path's demonstrated envelope.

**This branch is a decision record only.** No Beam pipeline code is written. No Dataflow job is launched. No GCP resource is created or modified. The purpose of this document is to define, in portfolio-grade detail, when Dataflow is justified, how it fits the existing architecture, what a safe first proof looks like, what risks must be managed, and what the recommended implementation sequence is.

---

## 2. Current Architecture

### 2.1 Validated GCP Flow

```text
Event source (bounded or sustained)
  → Pub/Sub topic: market-events-raw
      → Cloud Run worker (push subscription; maxScale=1; concurrency=1)
          → Cloud SQL PostgreSQL: bronze.market_events (ON CONFLICT DO NOTHING; idempotent)

Cloud SQL PostgreSQL
  → Cloud Run Job: rtdp-dbt-refresh-job
      → dbt silver: silver_market_event_minute_aggregates (incremental, delete+insert)
      → dbt gold:   gold_market_event_daily_aggregates   (incremental, delete+insert)

Cloud SQL PostgreSQL
  → Cloud Run Job: rtdp-bigquery-append-job
      → BigQuery: rtdp_analytics.market_events_raw_staging (cursor-based MERGE; idempotent)
      → BigQuery: rtdp_analytics.market_events_raw         (incremental append)

BigQuery quality checks (GitHub Actions; scheduled + workflow_dispatch)
  → scripts/push_bigquery_quality_metrics.py
      → Cloud Monitoring: custom.googleapis.com/rtdp/bigquery_quality/* (12 time series)
          → Alert policy: RTDP BigQuery Quality Failure
              → Email notification channel: RTDP Operator Email Alerts

Cloud Run API: rtdp-api
  → /events, /aggregates/daily, /health, /readiness, /version, /metrics-prometheus
```

All components are Terraform-managed under `infra/terraform/gcp/` with GCS remote backend.
Cloud Scheduler jobs target `rtdp-dbt-refresh-job:run` and `rtdp-bigquery-append-job:run` and are kept **PAUSED** by default.
Cloud SQL `rtdp-postgres` is kept at activation policy **NEVER / STOPPED** outside bounded validation windows.

### 2.2 What Is Currently Proven

| Capability | Evidence | Value |
|---|---|---|
| 50,000-event bounded cloud load test | load-test-50000-cloud-evidence.md | published_total=50000; 0 errors; 0 duplicates |
| Sustained 10 events/sec for 30 minutes | steady-state-10eps-30min-cloud-validation-evidence.md | 18,000 events; p50=154 ms; p95=227 ms; p99=694 ms |
| Cloud Run worker idempotent writes | gcp-worker-cloud-validation.md | ON CONFLICT DO NOTHING; 0 duplicates across 50k + 18k events |
| Pub/Sub DLQ routing | production-pubsub-dlq-evidence.md | maxDeliveryAttempts=5; 10s/60s backoff; malformed messages routed to DLQ |
| dbt incremental silver model | dbt-cloud-sql-incremental-execution-proof.md | silver INSERT 0 13; dbt run PASS=2; dbt test PASS=22 |
| dbt incremental gold model | dbt-cloud-sql-incremental-execution-proof.md | gold INSERT 0 7; dbt run PASS=2; dbt test PASS=22 |
| BigQuery analytical tier | bigquery-incremental-append-evidence.md | 6,120 rows; cursor-based MERGE; idempotent second run |
| BigQuery quality checks (scheduled) | bigquery-quality-scheduled-event-execution-evidence.md | cron 15 6 * * *; status ok; row_count=6120 |
| Cloud Monitoring quality metrics | bigquery-quality-cloud-monitoring-metrics-evidence.md | 12 time series pushed; metricWriter IAM applied |
| Alert policy → email delivery | bigquery-quality-incident-notification-delivery-proof.md | OPEN incident; Gmail inbox screenshot |
| Terraform zero-diff discipline | All *-import-plan-evidence.md files; all apply evidence | PLAN_EXIT=0 across all evidence branches |
| 348 pytest passing | dbt-metrics-runtime-monitoring-iam-evidence.md | ruff clean; all tests passing |

### 2.3 What Is Not Yet Proven

| Gap | Status | Relevant Document |
|---|---|---|
| Apache Beam pipeline (any form) | Not implemented | This ADR defines the proof design |
| Dataflow job execution | Not executed | This ADR defines acceptance criteria |
| Event-time windowed aggregations | Not implemented | dbt aggregations are processing-time batch |
| Late-event / out-of-order event handling | Not implemented | No AllowedLateness policy exists |
| Stateful stream processing | Not implemented | No per-key state in current path |
| Pub/Sub message-level replay | Not documented at operational depth | replay-backfill-strategy.md covers cursor-based BigQuery path |
| Dataflow autoscaling | Not implemented | Cloud Run maxScale=1 is the current ceiling |
| BigQuery Storage Write API (COMMITTED mode) | Not implemented | Current path uses cursor-based batch MERGE |
| Exactly-once transport-layer semantics | Not claimed | ON CONFLICT deduplication is application-layer only |
| Sustained throughput saturation point | Not characterized | 10 eps is the maximum sustained rate proven |
| Live dbt metric writes to Cloud Monitoring | Not yet proven | DBT_METRICS_DRY_RUN=true; IAM now applied |
| GitHub notification bell delivery | Not yet proven | Email delivery proven; bell not yet tested |
| Staging / production environment separation | Not implemented | Single GCP project throughout |

---

## 3. Decision

**Keep the Cloud Run worker as the validated primary ingestion and processing path.**

The Pub/Sub → Cloud Run worker → Cloud SQL path has been validated at 50,000 bounded events and at 10 events/sec sustained for 30 minutes. It is operationally simple, cost-controlled, Terraform-managed, and observable. No measured evidence shows it approaching a throughput or capability ceiling.

**Introduce Apache Beam / Google Cloud Dataflow as the next high-value streaming architecture extension.**

Dataflow is the highest-priority remaining capability gap for international GCP Data Engineering positioning. A decision record that defines when Dataflow is justified, how it fits the existing architecture, and what a minimal proof requires is sufficient to close the gap without premature implementation risk or cloud cost exposure.

**The first Beam implementation must be bounded and controlled.**

The first Dataflow proof will use DirectRunner locally (no GCP execution, no cost), followed by a bounded DataflowRunner execution using a small controlled input. Always-on streaming Dataflow is deferred until sustained throughput requirements, event-time windowing, or stateful processing needs are demonstrated by measured evidence.

---

## 4. Cloud Run Worker vs Dataflow: Comparison

| Dimension | Cloud Run Worker (Current) | Apache Beam / Dataflow |
|---|---|---|
| **Operational complexity** | Low: standard Python container; Terraform-managed; no runner config | High: Beam SDK; pipeline options; runner config; staging bucket; Dataflow-specific IAM |
| **Cost control** | Very low: scales to zero; Cloud SQL STOPPED/NEVER when idle | Medium to high: billing starts on job launch regardless of event volume; always-on streaming is costly |
| **Replay handling** | Cursor-based BigQuery incremental append proven; message-level Pub/Sub replay not documented at operational depth | Native: Pub/Sub subscription seek to timestamp; pipeline rerun; idempotent if designed correctly |
| **Event-time windows** | Not implemented: dbt aggregations are processing-time batch (processing timestamp, not event timestamp) | Native: FixedWindows, SlidingWindows, SessionWindows over event-time streams |
| **Late / out-of-order events** | Not handled: no AllowedLateness policy; no side output for late events | Native: AllowedLateness policy; side output (TaggedOutput) for discarded late events |
| **Autoscaling** | maxScale=1 (intentional cost + ordering control): single instance ceiling | Native: THROUGHPUT_BASED autoscaling; min/max worker count configurable |
| **Backpressure** | Implicit: Pub/Sub buffering upstream of single Cloud Run instance; no pipeline-level backpressure signal | Native: Dataflow system lag metric; pubsub_undelivered_bytes; pipeline staleness alerting |
| **Stateful transforms** | Not supported: each event processed independently; no per-key state | Native: Beam stateful DoFn; per-key state and timers |
| **Exactly-once / at-least-once semantics** | At-least-once delivery; application-layer deduplication via ON CONFLICT(event_id) DO NOTHING; 0 duplicates proven at 50k events | At-least-once by default; exactly-once possible via Beam BigQuery Storage Write API COMMITTED mode; must be implemented and validated before claim |
| **Recruiter / market value** | Strong for GCP platform and Data Engineer roles; insufficient for Dataflow-specific streaming roles | High for streaming-specific roles; demonstrates GCP-native streaming depth; addresses binary gap for senior reviewers |
| **Portfolio value** | Validated: 50k bounded + 10 eps sustained + full observability loop | Planned: decision record closes architectural gap; proof branch will produce credible Beam evidence |

---

## 5. Dataflow Target Architecture

The proposed future flow when Dataflow is introduced:

```text
Pub/Sub topic: market-events-raw
  → Apache Beam / Google Cloud Dataflow pipeline
      ├── ReadFromPubSub (with timestamp_attribute for event-time semantics)
      ├── Parse MarketEvent (validated against shared contract)
      ├── FixedWindows (configurable duration; event-time)
      ├── AllowedLateness (configurable tolerance; e.g., 60 seconds)
      ├── Dead-letter side output (TaggedOutput for parse failures and late events)
      │   → BigQuery: rtdp_analytics.market_events_beam_dlq (or Pub/Sub DLQ topic)
      └── WriteToBigQuery (BigQuery Storage Write API; target: COMMITTED mode)
          → BigQuery: rtdp_analytics.market_events_raw (or dedicated staging table)

BigQuery: rtdp_analytics.market_events_raw
  → dbt silver: silver_market_event_minute_aggregates (incremental, delete+insert)
  → dbt gold:   gold_market_event_daily_aggregates   (incremental, delete+insert)
  → Cloud Monitoring: custom.googleapis.com/rtdp/bigquery_quality/* (quality checks)
      → Alert policy: RTDP BigQuery Quality Failure
          → Email notification channel: RTDP Operator Email Alerts

Cloud Monitoring: dataflow.googleapis.com/job/*
  → system_lag, pubsub_undelivered_bytes, elements_produced_count
  → Alert policy: Dataflow pipeline staleness / lag threshold

Cloud Run API: rtdp-api
  → /events, /aggregates/daily, /health, /readiness, /version, /metrics-prometheus
```

**Key design constraints for this target architecture:**

- The Dataflow pipeline uses a **separate Pub/Sub subscription** from the Cloud Run worker push subscription. Both paths can coexist without message loss.
- The BigQuery sink for the Dataflow proof is a **dedicated staging or proof table** (`market_events_beam_proof` or `market_events_raw_staging`). The production `market_events_raw` table is not written to during the first proof.
- All infrastructure (Dataflow IAM, GCS staging bucket, BigQuery proof table) is **Terraform-managed** before any Dataflow job is launched.
- The Cloud Run worker path remains active as the validated baseline. Promotion of the Dataflow path to primary is a post-proof decision.

---

## 6. Minimal Future Proof Design

A safe first Dataflow proof must follow this design. No implementation is done in this branch.

### 6.1 Phase 1: DirectRunner Local Validation

**Branch:** `feat/beam-directrunner-market-events-pipeline`

| Requirement | Detail |
|---|---|
| SDK | Apache Beam Python SDK (added to `uv` dependency group, not production worker image) |
| Runner | DirectRunner only (local; no GCP execution; no cloud cost) |
| Input | Small static JSONL file of MarketEvent records (not live Pub/Sub) |
| Transform | Parse MarketEvent; validate schema; emit to in-memory or file sink |
| Output | Local file or in-memory assertion; no BigQuery write in this phase |
| Tests | pytest unit tests for each DoFn; at least one DirectRunner integration test with N synthetic events |
| Cost | Zero: no GCP resource created or used |
| Evidence | Pipeline runs locally; test output count matches input count; no GCP mutations |

### 6.2 Phase 2: Terraform and IAM Prerequisites

**Branch:** `infra/dataflow-bounded-proof-prereqs`

| Requirement | Detail |
|---|---|
| Dataflow service account | `rtdp-dataflow-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` (new; Terraform-managed) |
| Required roles | `roles/dataflow.worker`, `roles/bigquery.dataEditor` (scoped to proof dataset), `roles/pubsub.subscriber` (scoped to proof subscription), `roles/storage.objectAdmin` (scoped to staging bucket) |
| GCS staging bucket | `rtdp-dataflow-staging` (Terraform-managed; lifecycle rule: delete after 7 days) |
| BigQuery proof table | `rtdp_analytics.market_events_beam_proof` (Terraform-managed; schema matches `market_events_raw`) |
| Pub/Sub proof subscription | `market-events-raw-beam-proof-sub` (pull; separate from worker push subscription) |
| Validation | `terraform plan` must show only adds for new resources; PLAN_EXIT=2 pre-apply; PLAN_EXIT=0 post-apply |
| Safety | Cloud SQL STOPPED/NEVER; schedulers PAUSED; production subscriptions untouched |

### 6.3 Phase 3: Bounded DataflowRunner Proof

**Branch:** `feat/dataflow-bounded-market-events-proof`

| Requirement | Detail |
|---|---|
| Runner | DataflowRunner (GCP-managed; bounded job; not always-on streaming) |
| Input | Bounded: N pre-published test events on the proof Pub/Sub subscription, OR a GCS file source |
| Transform | ReadFromPubSub (or ReadFromText) → parse MarketEvent → WriteToBigQuery |
| Output | BigQuery: `rtdp_analytics.market_events_beam_proof` |
| Job type | Batch or bounded streaming with explicit drain/cancel after N events consumed |
| Cost controls | Explicit start timestamp; 10-minute job ceiling; drain/cancel command in runbook before session end; cost estimate recorded |
| Evidence | Dataflow job ID captured; job state DONE or DRAINED; BigQuery row count matches input; Cloud Logging shows no pipeline errors; cost estimate recorded |
| Safety | Cloud SQL STOPPED/NEVER; schedulers PAUSED; no production table written; no production subscription consumed |

### 6.4 Required Runbook Components

Every Dataflow execution branch must include:

```bash
# Start: record job launch timestamp
LAUNCH_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Launch job (example):
python pipelines/beam_market_events.py \
  --runner=DataflowRunner \
  --project=project-42987e01-2123-446b-ac7 \
  --region=europe-west1 \
  --temp_location=gs://rtdp-dataflow-staging/temp \
  --staging_location=gs://rtdp-dataflow-staging/staging \
  --job_name=rtdp-beam-proof-$(date +%s) \
  --service_account_email=rtdp-dataflow-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com

# Monitor: capture job ID
JOB_ID=<captured from launch output>

# Cancel within time ceiling (mandatory):
gcloud dataflow jobs cancel $JOB_ID \
  --project=project-42987e01-2123-446b-ac7 \
  --region=europe-west1

# Verify final state:
gcloud dataflow jobs describe $JOB_ID \
  --project=project-42987e01-2123-446b-ac7 \
  --region=europe-west1 \
  --format="table(id,name,currentState)"
```

---

## 7. Acceptance Criteria for Future Dataflow MVP

The following criteria must all be satisfied before any branch can be merged as a Dataflow MVP.

| Criterion | Required Evidence |
|---|---|
| Beam pipeline unit tests | pytest passing for each DoFn; DirectRunner integration test |
| DirectRunner proof | Local pipeline run; input count = output count; no errors |
| Terraform plan for Dataflow prerequisites | `PLAN_EXIT=2` pre-apply (new resources planned); `PLAN_EXIT=0` post-apply; no unintended changes |
| GCS staging bucket exists | `gs://rtdp-dataflow-staging` visible in `gsutil ls`; lifecycle rule applied |
| Dataflow service account exists | `rtdp-dataflow-sa` visible in `gcloud iam service-accounts list` |
| Bounded DataflowRunner proof | Dataflow job ID captured; final state DONE or DRAINED; no pipeline errors in Cloud Logging |
| BigQuery row count / readback | `SELECT COUNT(*) FROM rtdp_analytics.market_events_beam_proof` = N input events; no duplicates |
| BigQuery schema validation | Proof table schema matches `market_events_raw`; symbol / event_type / price / quantity / event_id visible |
| Cloud Monitoring / logs evidence | Cloud Logging job run logs captured; no ERROR entries; Dataflow system metrics visible |
| Cost guard | Job cancelled or drained within 10-minute ceiling; estimated vCPU-hours recorded in evidence |
| Teardown / idle-state check | Cloud SQL STOPPED/NEVER confirmed post-run; both schedulers PAUSED confirmed post-run |
| PLAN_EXIT=0 after cleanup | Terraform plan shows no drift after proof run |
| Safety state confirmed | No production table written; no production subscription consumed; no always-on streaming job left running |
| Explicit non-claims documented | Evidence explicitly states: bounded proof only; not production Dataflow; exactly-once semantics not claimed |

---

## 8. Market Alignment

This decision record materially improves the portfolio's international GCP Data Engineer and Data Platform Engineer positioning across the following dimensions.

### 8.1 GCP-Native Streaming Depth

The platform already demonstrates GCP-native ingestion (Pub/Sub), processing (Cloud Run), storage (Cloud SQL, BigQuery), transformation (dbt), and observability (Cloud Monitoring, alerting). Adding a Dataflow decision record that defines the streaming evolution path signals end-to-end GCP streaming platform thinking, not just component assembly.

Senior technical reviewers for GCP Data Engineering roles evaluate whether a candidate understands *when* to use which tool, not just *whether* they can use it. A documented decision record with explicit trigger conditions, a cost-controlled proof design, and honest non-claims demonstrates that judgment.

### 8.2 Apache Beam Architectural Awareness

Apache Beam is the dominant open-source portable stream processing SDK for GCP. It is a hard requirement in a significant fraction of senior Data Engineering job descriptions targeting GCP or multi-cloud environments. This document demonstrates:

- Understanding of Beam's execution model (DirectRunner vs DataflowRunner)
- Windowing semantics (FixedWindows, SlidingWindows, SessionWindows)
- Watermarking and late-event handling (AllowedLateness, TaggedOutput side output)
- Stateful processing (DoFn state and timers)
- BigQuery write path options (batch MERGE vs Storage Write API COMMITTED mode)

None of these are claimed as implemented experience. They are documented as architectural knowledge, which is honest and verifiable.

### 8.3 Dataflow as a GCP Differentiator

Dataflow is a GCP-specific managed Beam runner. Demonstrating the ability to design, cost-control, and safely execute a bounded Dataflow job in a portfolio project is a meaningful differentiator for:

- **International GCP-specialist Data Engineering roles**: Dataflow is often listed alongside BigQuery and Pub/Sub as a core GCP Data Engineering skill. The absence of any Dataflow evidence is a visible gap for experienced reviewers.
- **B2B consulting engagement positioning**: clients running GCP-native streaming architectures expect consultants to evaluate Dataflow vs Cloud Run vs Spark vs Flink with measured reasoning. This decision record is exactly that reasoning documented.
- **Senior platform engineering roles**: architectural decision records with explicit trigger conditions, cost controls, and evidence criteria signal senior-level judgment, which separates candidates at the pipeline engineer / data platform engineer / staff engineer level.

### 8.4 Full Stack GCP Data Platform Evidence

When combined with existing evidence, this ADR completes a portfolio that demonstrates the full GCP data platform lifecycle:

| Capability | Status |
|---|---|
| GCP-native streaming ingestion | Pub/Sub; proven at 50k events and 10 eps sustained |
| Cloud Run managed processing | Worker + API + Cloud Run Jobs; Terraform-managed |
| BigQuery analytical tier | 6,120 rows; incremental MERGE; quality checks; scheduled execution |
| Terraform IaC discipline | Zero-diff plans across 60+ evidence branches; GCS remote state |
| dbt analytics engineering | Incremental silver and gold models; Cloud SQL live execution proven |
| Observability and alerting | Cloud Monitoring; 12 time series; alert policies; email delivery proven |
| Production runbooks | DLQ routing; scheduler controls; cost controls; safety state discipline |
| Cost / risk controls | Cloud SQL NEVER/STOPPED; schedulers PAUSED; bounded validation only |
| Apache Beam / Dataflow | Decision record: architectural reasoning; proof design; trigger conditions |

---

## 9. Non-Goals for This Branch

The following are explicitly out of scope for `docs/dataflow-apache-beam-architecture-decision`.

- No Apache Beam pipeline code is written.
- No Dataflow job is launched or executed.
- No Terraform resources are added, changed, or destroyed.
- No Cloud Scheduler jobs are activated or modified.
- No Cloud SQL instance is started.
- No live traffic is migrated from Cloud Run to Dataflow.
- No claim of exactly-once semantics is made (not proven until Beam BigQuery Storage Write API COMMITTED mode is implemented and validated).
- No claim of production Dataflow readiness is made.
- No claim that this decision record constitutes Apache Beam or Dataflow implementation experience.

---

## 10. Risks

### 10.1 Cost Risk from Always-On Streaming Dataflow

A Dataflow streaming job bills from the moment it is launched. At `n1-standard-2` worker pricing in `europe-west1`, a streaming job running for 1 hour costs approximately $0.10–$0.15 in worker compute alone. A job left running overnight incurs significant cost. The mandatory 10-minute ceiling and explicit drain/cancel instructions in the proof runbook (Section 6.4) are the primary mitigations. Always-on streaming Dataflow is not in scope for the first proof and is not claimed as the target architecture until throughput requirements justify it.

### 10.2 IAM Complexity

Dataflow requires a Dataflow worker service account with a specific set of roles. Overly broad IAM grants (e.g., project-level BigQuery Admin) violate least-privilege discipline. The proposed IAM design in Section 6.2 scopes all Dataflow permissions to the proof resources. A Terraform `plan` must be reviewed before any `apply` to confirm no unintended IAM grants.

### 10.3 BigQuery Duplicate Handling

The current BigQuery write path uses a cursor-based MERGE for idempotent appends. A Dataflow pipeline writing to BigQuery using the legacy Streaming Insert API (not Storage Write API COMMITTED mode) provides at-least-once delivery, which can produce duplicate rows on retry. The proof design targets the Storage Write API, but exactly-once semantics must be validated in the actual implementation. Duplicates in the proof table do not affect the production `market_events_raw` table, since the proof uses a dedicated staging/proof table.

### 10.4 Pub/Sub Ack / Retry Semantics

Pub/Sub guarantees at-least-once delivery. A Dataflow pipeline that consumes from a Pub/Sub subscription must handle duplicate message delivery. If the Dataflow pipeline and the Cloud Run worker share a subscription, messages consumed by Dataflow will not be processed by the worker (and vice versa). The proof design uses a **separate Pub/Sub subscription** for Dataflow to avoid interference with the validated Cloud Run worker path.

### 10.5 Late / Out-of-Order Event Handling

The current Cloud Run path has no event-time awareness. A Dataflow pipeline using `ReadFromPubSub` with `timestamp_attribute` and `FixedWindows` must handle late events explicitly via `AllowedLateness`. Events that arrive after the window watermark without `AllowedLateness` are silently dropped. The proof design documents `AllowedLateness` as a required pipeline component, but late-event handling is not claimed as implemented until the pipeline code is written and tested.

### 10.6 Operational Complexity vs Cloud Run Worker

The Cloud Run worker is a standard Python container with a straightforward Terraform resource definition. A Dataflow pipeline adds: Beam SDK dependency management, pipeline options configuration, Dataflow-specific IAM, GCS staging bucket lifecycle management, Dataflow job state monitoring, drain/cancel runbook, and pipeline upgrade strategy. This complexity is justified only when the capabilities Dataflow provides (windowing, state, late-event handling, autoscaling) are required by measured evidence or by a specific client/role requirement.

---

## 11. Recommended Next Branches

The following branches are recommended in order. Each builds on the previous without overlap.

### Branch a: `feat/beam-directrunner-market-events-pipeline`

**Scope:** Local Beam pipeline with DirectRunner only. No GCP execution. No cloud cost.

**Deliverables:**
- `pipelines/beam_market_events.py`: ReadFromText (or static input) → parse MarketEvent → WriteToBigQuery (mocked or file sink)
- `tests/test_beam_pipeline.py`: pytest unit tests for each DoFn; DirectRunner integration test with N synthetic events
- `docs/beam-directrunner-pipeline-evidence.md`: local run output; test results; input count = output count

**Acceptance criteria:**
- All DoFn unit tests pass
- DirectRunner integration test: N input events → N output events; 0 errors
- `uv run pytest -q` passes (all existing tests + new Beam tests)
- `uv run ruff check .` clean
- No GCP resources created or modified
- Cloud SQL STOPPED/NEVER; schedulers PAUSED; PLAN_EXIT=0

---

### Branch b: `infra/dataflow-bounded-proof-prereqs`

**Scope:** Minimal Terraform for Dataflow proof infrastructure. PLAN_EXIT=2 pre-apply; PLAN_EXIT=0 post-apply.

**Deliverables:**
- `infra/terraform/gcp/dataflow.tf`: service account, GCS staging bucket, BigQuery proof table, Pub/Sub pull subscription
- `docs/dataflow-proof-prereqs-evidence.md`: terraform plan output; apply output; resource confirmation

**Acceptance criteria:**
- `terraform plan` shows only new resource adds (no changes to existing resources)
- `terraform apply` succeeds; PLAN_EXIT=0 post-apply
- `rtdp-dataflow-sa` service account confirmed
- `gs://rtdp-dataflow-staging` bucket confirmed with lifecycle rule
- `rtdp_analytics.market_events_beam_proof` table confirmed
- `market-events-raw-beam-proof-sub` pull subscription confirmed
- Cloud SQL STOPPED/NEVER; schedulers PAUSED

---

### Branch c: `feat/dataflow-bounded-market-events-proof`

**Scope:** Bounded DataflowRunner execution. N test events. Proof table only. No always-on streaming.

**Deliverables:**
- Updated `pipelines/beam_market_events.py`: DataflowRunner support; pipeline options for project/region/staging/service-account
- `docs/dataflow-bounded-proof-runbook.md`: launch command; monitoring commands; drain/cancel command; cost ceiling
- `docs/dataflow-bounded-market-events-proof-evidence.md`: job ID; final state; BigQuery row count; Cloud Logging excerpt; cost estimate; Cloud SQL / scheduler safety state

**Acceptance criteria:** All criteria in Section 7 of this document.

---

### Branch d: `docs/dataflow-vs-cloud-run-worker-operational-review`

**Scope:** Post-proof decision document. Docs-only. Determines whether to keep both paths, promote Dataflow, or retire it.

**Deliverables:**
- `docs/dataflow-vs-cloud-run-operational-review.md`: comparison of actual proof results vs this ADR's predictions; recommendation on path forward; updated trigger conditions if any have changed

**Acceptance criteria:**
- Document is honest about proof results
- Recommendation is grounded in measured evidence, not assumption
- No new GCP resources created
- Cloud SQL STOPPED/NEVER; schedulers PAUSED; PLAN_EXIT=0

---

## 12. Validation Commands

These commands confirm that the current branch introduces only documentation changes, with no impact on tests, Terraform, or GCP resources.

```bash
uv run pytest -q
uv run ruff check .
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo PLAN_EXIT=$?
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state,settings.activationPolicy)"
gcloud scheduler jobs list \
  --project=project-42987e01-2123-446b-ac7 \
  --location=europe-west1 \
  --format="table(id,state,schedule)"
```

**Expected results:**

| Check | Expected |
|---|---|
| pytest | All passing (348 or more) |
| ruff | Clean |
| terraform fmt | No formatting changes |
| terraform validate | Success |
| PLAN_EXIT | 0 |
| Cloud SQL state | STOPPED / NEVER |
| Schedulers | Both PAUSED |

---

## 13. Explicit Non-Claims

As of 2026-05-23:

- **Apache Beam is not implemented.** No `pipelines/beam_market_events.py` or equivalent file exists.
- **Dataflow is not implemented.** No Dataflow job has been launched against any GCP project.
- **No GCP resources were created or modified in this branch.** This is a docs-only branch.
- **Exactly-once semantics are not claimed.** Pub/Sub guarantees at-least-once delivery. ON CONFLICT deduplication is application-layer, not transport-layer exactly-once.
- **Windowed event-time streaming is not implemented.** dbt aggregations are processing-time batch, not Beam event-time windows.
- **Late-event handling is not implemented.** No AllowedLateness policy, watermark, or side output exists.
- **Dataflow autoscaling is not proven.** maxScale=1 on Cloud Run is the current concurrency ceiling.
- **BigQuery Storage Write API exactly-once path is not proven.** The current path uses cursor-based batch MERGE.
- **Production Dataflow readiness is not claimed.** No production streaming Dataflow job has been launched.
- **The architectural awareness documented here is not equivalent to Beam implementation experience.** The DirectRunner and DataflowRunner proof branches listed in Section 11 must be executed before any Beam experience claim can be made.

---

## 14. Evidence Links

| Document | Relevance |
|---|---|
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog |
| [docs/gcp-architecture.md](gcp-architecture.md) | GCP service mapping and target flow |
| [docs/dataflow-decision-record.md](dataflow-decision-record.md) | Prior decision record: Dataflow deferred pending measured justification |
| [docs/market-value-gap-audit-2026-2027.md](market-value-gap-audit-2026-2027.md) | Gap audit that identified Dataflow/Beam as Priority 5 gap |
| [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md) | 50,000-event bounded cloud load test |
| [docs/steady-state-10eps-30min-cloud-validation-evidence.md](steady-state-10eps-30min-cloud-validation-evidence.md) | 10 eps for 30 min; p50/p95/p99 latency evidence |
| [docs/bigquery-incremental-append-evidence.md](bigquery-incremental-append-evidence.md) | BigQuery cursor-based MERGE; 6,120 rows; idempotent append |
| [docs/dbt-cloud-sql-incremental-execution-proof.md](dbt-cloud-sql-incremental-execution-proof.md) | dbt run PASS=2; dbt test PASS=22; Cloud SQL live incremental execution |
| [docs/bigquery-quality-incident-notification-delivery-proof.md](bigquery-quality-incident-notification-delivery-proof.md) | Alert policy → Cloud Monitoring incident → email delivery proven |
| [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) | Pub/Sub DLQ: maxDeliveryAttempts=5; 10s/60s backoff |
| [docs/cost-performance-summary.md](cost-performance-summary.md) | Cost drivers; Cloud Run maxScale=1; resource sizing |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | Production-light SLO targets; incident runbooks |
| [docs/gap-closure-snapshot-after-steady-state.md](gap-closure-snapshot-after-steady-state.md) | Post-steady-state gap closure assessment |
| [docs/platform-audit-after-cost-performance.md](platform-audit-after-cost-performance.md) | Post-cost/performance platform assessment; Dataflow deferred |
| [docs/replay-backfill-strategy.md](replay-backfill-strategy.md) | Replay and backfill semantics; cursor-based BigQuery path |
