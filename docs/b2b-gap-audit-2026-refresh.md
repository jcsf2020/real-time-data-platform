# Data Platform Gap Audit — 2026 Refresh

**Date:** 2026-05-15
**Scope:** Post BigQuery analytical tier scaffold + bounded backfill accepted
**Branch:** `docs/post-bigquery-evidence-refresh`
**Validation state:** 156 pytest passed · ruff clean · terraform fmt/validate clean · terraform plan zero-diff · dbt/profiles.yml absent · BigQuery PLAN_EXIT=0 · Cloud SQL NEVER/STOPPED

---

## 1. Platform Status

### Implemented Capabilities

This is a production-light, evidence-backed GCP data platform. The following capabilities
are implemented and evidenced:

- A complete real-time ingestion path: Pub/Sub → Cloud Run worker → Cloud SQL → FastAPI
  API, validated end-to-end with 100 / 1,000 / 5,000-event bounded load tests.
- A medallion data architecture (bronze / silver / gold / observability / ai schemas) in
  PostgreSQL, with a governed dbt transformation layer covering silver and gold models.
- Full Terraform IaC coverage across every deployed GCP resource, backed by a GCS remote
  state, validated with zero-diff plans. `rtdp-dbt-refresh-job` (Cloud Run Job for the dbt
  refresh path) exists in GCP under Terraform management with a confirmed zero-diff plan;
  execution evidence and scheduler switch are accepted.
- Operational observability: 4 logs-based Cloud Monitoring metrics with confirmed timeSeries
  datapoints, a 4-panel dashboard, 2 enabled alert policies with email notification, and a
  production DLQ with `deadLetterPolicy`.
- A two-job CI pipeline: pytest (156 tests), ruff lint, import smoke test, and a full dbt
  compile/run/test run on every push — including an ephemeral pgvector container.
- Principled cost control: Cloud SQL is `NEVER / STOPPED` outside bounded validation
  windows. No resource has been mutated without a scoped, runbook-backed evidence branch.
- dbt is the accepted operational scheduled transformation path: `rtdp-dbt-refresh-job` runs
  silver and gold models against Cloud SQL (silver 256 rows, gold 7 rows; 22 dbt tests
  passed; API readback HTTP 200). Cloud Scheduler targets `rtdp-dbt-refresh-job:run` (PAUSED
  by default). Scheduler-triggered execution accepted (`rtdp-dbt-refresh-job-6zb52`, dbt run
  PASS=2, dbt test PASS=22).
- A BigQuery analytical tier scaffold: dataset `rtdp_analytics` (europe-west1) and three
  Terraform-managed tables (`market_events_raw`, `market_event_minute_aggregates`,
  `market_event_daily_aggregates`), all DAY-partitioned and clustered. A bounded backfill of
  6,104 rows from Cloud SQL `bronze.market_events` to BigQuery `market_events_raw` was
  executed and validated: source/target count match confirmed, analytical query by
  symbol/event_type returned correct results (BTCUSDT 2,036 events, ETHUSDT 2,034, SOLUSDT
  2,033), Terraform PLAN_EXIT=0, Cloud SQL returned to NEVER / STOPPED. No continuous
  streaming to BigQuery exists.

### Current Operational Limitations

| Category | Implemented (production-light) | Not implemented / operational limitation |
|---|---|---|
| Availability | Validated during bounded windows only | Not continuously running; Cloud SQL stopped by default |
| Scale | 5,000-event bounded bursts validated | Sustained streaming throughput not validated above 5,000 |
| Data | Synthetic deterministic events | No real-world data variability exercised |
| dbt | Operationally scheduled via Cloud Scheduler (PAUSED by default); dbt run and test accepted; stored functions preserved as rollback | Scheduler paused by default; not continuously running; incremental models not yet implemented |
| BigQuery | Analytical tier scaffold implemented (Terraform-managed dataset + 3 tables); bounded backfill of 6,104 rows accepted; analytical query confirmed | No continuous streaming to BigQuery; incremental append path not yet implemented; no production streaming Dataflow; bounded DataflowRunner proof validated (see dataflow-bounded-runner-proof-evidence.md) |
| CI/CD | CI green on every push; manual deploys tested | No automatic deploy-on-merge |
| Multi-environment | Single GCP project / environment | No staging, no canary, no multi-region |
| SLO | Defined and documented | Aspirational targets; no continuous measurement |

### Current Professional Positioning

The platform demonstrates a complete GCP data engineering stack with full end-to-end
evidence. Terraform discipline and evidence-first documentation distinguish it from
undocumented implementations. dbt with CI validation and Cloud SQL parity demonstrates
governed transformation practice. The Pub/Sub DLQ, alert policies, and email notification
channel demonstrate production-aware reliability thinking. BigQuery analytical tier scaffold
and bounded backfill evidence close the dual-store architecture gap at the infrastructure
and data movement levels.

**Technical hiring relevance:** This is a production-light platform operated in controlled
windows, not a service under continuous load. The dbt operational migration, scheduler
switch, BigQuery analytical tier scaffold, and bounded backfill are accepted. The remaining
gaps visible in a senior technical review are: the incremental BigQuery append/streaming
path (no continuous data movement to BigQuery exists) and automatic CD.

---

## 2. Resolved Gaps Since the Previous Audit

### dbt transformation layer

**Resolved.** Silver and gold dbt models implemented (`dbt/models/silver/`,
`dbt/models/gold/`), with 22 schema and business-rule tests covering source quality, model
integrity, and price-range constraints. Models reproduce the existing stored-function logic
with confirmed parity. Stored functions are preserved as a rollback path. Evidence:
`docs/dbt-ci-validation-evidence.md`.

### dbt CI

**Resolved.** A `dbt` CI job was added to `.github/workflows/ci.yml` (PR #105). It runs
after the `validate` job and executes `dbt deps → dbt compile → dbt run → dbt test` against
an ephemeral `pgvector/pgvector:pg16` service container on every push to `main` and on PRs.
No GCP resources are touched. Evidence: `docs/dbt-ci-validation-evidence.md`.

### dbt Cloud SQL validation

**Resolved.** A controlled validation window was executed against the real Cloud SQL
instance with Cloud SQL Auth Proxy. dbt compiled, ran, and tested successfully. Silver
output: 256 rows (matches stored-function baseline). Gold output: 7 rows (matches
baseline). All 22 dbt tests passed. API `/aggregates/minute` and `/aggregates/daily` both
returned HTTP 200 with rows. Cloud SQL was returned to `NEVER / STOPPED`. Evidence:
`docs/dbt-cloud-sql-validation-evidence.md`.

### dbt refresh runtime

**Resolved.** `apps/dbt-refresh-job/src/rtdp_dbt_refresh_job/__init__.py` implements the
`rtdp-dbt-refresh-job` CLI. It orchestrates `dbt deps → dbt compile → dbt run --select
silver,gold → dbt test`, writes a temporary `profiles.yml` at runtime and deletes it after
each run, emits structured JSON logs, and supports four `DBT_REFRESH_MODE` values
(`compile`, `run`, `test`, `run-and-test`). 36 dedicated pytest tests cover config
validation, profiles generation, subprocess orchestration, and cleanup. Evidence:
`tests/test_dbt_refresh_job.py`.

### DATABASE_URL runtime handling

**Resolved** (branch `feat/dbt-refresh-database-url-runtime`). The runtime parses the full
`postgresql://user:password@host/dbname` URL stored in the `rtdp-database-url` Secret
Manager secret and derives connection fields. Explicit `DBT_POSTGRES_*` env vars override
any field from the URL. `DBT_POSTGRES_HOST` is set to the Cloud SQL Unix socket path on
Cloud Run, overriding the TCP host from the URL. `DBT_POSTGRES_PASSWORD` is no longer wired
directly to the secret. The Terraform scaffold and deploy workflow were corrected to reflect
this contract. Evidence: `docs/dbt-refresh-cloud-run-job-plan.md`.

### Terraform Cloud Run Job scaffold

**Resolved.** `google_cloud_run_v2_job.rtdp_dbt_refresh_job` is declared in
`infra/terraform/gcp/cloud_run_jobs.tf`. It is Terraform-owned — no workflow creates or
updates the Cloud Run Job. The resource specifies the Cloud SQL volume mount, the
`DATABASE_URL` secret reference, explicit `DBT_POSTGRES_*` env vars, a 600s timeout, and
lifecycle ignore rules for image and annotation drift. Evidence:
`docs/dbt-refresh-cloud-run-job-plan.md`.

### IaC / deploy boundary correction

**Resolved.** The deploy workflow boundary was corrected: `deploy-dbt-refresh-cloud-run.yml`
builds and pushes the container image only (`IMAGE_PUSHED=true`,
`CLOUD_RUN_JOB_NOT_DEPLOYED_BY_THIS_WORKFLOW=true`). Terraform is the sole source of truth
for the Cloud Run Job definition. Evidence: `docs/dbt-refresh-cloud-run-job-plan.md`.

### Observability

**Resolved.** Four logs-based Cloud Monitoring metrics with confirmed timeSeries datapoints
(`worker_message_processed_count`, `worker_message_error_count`,
`silver_refresh_success_count`, `silver_refresh_error_count`). A 4-panel RTDP Pipeline
Overview dashboard created in GCP and exported to
`infra/monitoring/dashboards/rtdp-pipeline-overview.json`. Two enabled alert policies with
an email notification channel. All monitoring resources are under Terraform state with
zero-diff plan. Evidence: `docs/cloud-monitoring-dashboard-evidence.md`,
`docs/cloud-alert-policies-evidence.md`.

### Load testing

**Resolved.** Three tiers of bounded cloud load tests accepted: 100 events (all criteria
met), 1,000 events (all criteria met, metric sum = 1,000), 5,000 events (all criteria met,
metric sum = 4,963, DLQ empty, silver refresh succeeded). Each test used deterministic
event-ID prefixes, bounded publish rates (≤50 msg/s), Cloud SQL started only for the test
window, and confirmed `NEVER / STOPPED` on completion. Evidence:
`docs/load-test-1000-cloud-evidence.md`, `docs/load-test-5000-cloud-evidence.md`.

### Pub/Sub / DLQ

**Resolved.** Production push subscription `market-events-raw-worker-push` updated
in-place with `deadLetterPolicy`: `maxDeliveryAttempts=5`, 10s/60s backoff, routing to
`market-events-raw-dlq`. DLQ topic created, Pub/Sub service agent IAM granted. DLQ
confirmed empty during 5,000-event load test. Evidence:
`docs/production-pubsub-dlq-evidence.md`.

### Cost control

**Verified throughout.** Cloud SQL (`rtdp-postgres`) is kept `NEVER / STOPPED` by default;
confirmed in every evidence document. Cloud Scheduler (`rtdp-silver-refresh-scheduler`) is
kept `PAUSED` by default. All deployments are manual `workflow_dispatch`; no continuous
pipeline incurs unexpected costs. No `terraform apply` was run during import operations.

### dbt operational deployment

**Resolved** (branch `feat/dbt-refresh-cloud-run-deploy`).
`google_cloud_run_v2_job.rtdp_dbt_refresh_job` was deployed to GCP via `terraform apply`.
Final `terraform apply` succeeded; subsequent `terraform plan -detailed-exitcode` returns
exit code 0. DATABASE_URL socket parsing was fixed to correctly derive the Cloud SQL Unix
socket from the URL stored in Secret Manager. The job was then executed in a controlled
validation window: `dbt run` passed (silver 256 rows, gold 7 rows) and `dbt test` passed
all 22 tests. API readback for minute and daily aggregates returned HTTP 200. Cloud SQL was
returned to `NEVER / STOPPED`. Evidence: `docs/dbt-refresh-cloud-run-deploy-evidence.md`,
`docs/dbt-refresh-job-execution-proof-evidence.md`.

### Scheduler switch to dbt job

**Resolved** (branch `feat/dbt-scheduler-switch`). `infra/terraform/gcp/scheduler.tf` was
updated to target `rtdp-dbt-refresh-job:run` instead of `rtdp-silver-refresh-job:run`.
Terraform apply updated one resource; subsequent plan is zero-diff. A controlled manual
scheduler trigger confirmed execution `rtdp-dbt-refresh-job-6zb52` completed with `dbt run`
PASS=2 and `dbt test` PASS=22. Scheduler returned to `paused = true`. Cloud SQL returned to
`NEVER / STOPPED`. `rtdp-silver-refresh-job` remains deployed as a rollback path but is not
the active scheduler target. Evidence: `docs/dbt-scheduler-switch-evidence.md`.

### BigQuery analytical tier scaffold

**Resolved** (branch `exec/bigquery-terraform-apply-evidence`).
`google_bigquery_dataset.rtdp_analytics` and three BigQuery tables (`market_events_raw`,
`market_event_minute_aggregates`, `market_event_daily_aggregates`) were created via
`terraform apply` (6 resources: dataset, 3 tables, 2 IAM bindings). Tables are
DAY-partitioned and clustered. Worker service account received `roles/bigquery.dataEditor`
on the dataset and `roles/bigquery.jobUser` at project level. Subsequent
`terraform plan -detailed-exitcode` returns PLAN_EXIT=0. Cloud SQL was not started.
Evidence: `docs/bigquery-terraform-apply-evidence.md`.

### BigQuery bounded backfill

**Resolved** (branch `exec/bigquery-bounded-backfill-evidence`). A bounded validation
window was executed: Cloud SQL `rtdp-postgres` was started; 6,104 rows were exported from
`bronze.market_events` via `COPY` to a local CSV; the CSV was loaded into BigQuery
`rtdp_analytics.market_events_raw` via `bq load`. Post-load count: 6,104 — source/target
match confirmed. An analytical query by symbol/event_type returned 4 symbol rows with
correct aggregates (BTCUSDT 2,036 events, ETHUSDT 2,034, SOLUSDT 2,033, ADAUSDT 1). Cloud
SQL was returned to `NEVER / STOPPED`. No Cloud Run Job was executed; no Scheduler was
resumed; no Dataflow is involved. Terraform final plan PLAN_EXIT=0. Evidence:
`docs/bigquery-bounded-backfill-evidence.md`.

---

## 3. Remaining Gaps

Ranked by technical relevance, implementation risk, and recommended priority.

| # | Gap | Description | Technical Relevance | Implementation Risk | Priority |
|---|---|---|---|---|---|
| 1 | BigQuery incremental append / recurring data movement | BigQuery scaffold and bounded backfill are accepted (6,104 rows; PLAN_EXIT=0). Remaining gap: continuous or scheduled incremental data movement from Pub/Sub or Cloud SQL to BigQuery; new events must appear in BigQuery without a full reload | High | Medium | P0 |
| 2 | Automatic deploy-on-merge | Convert at least one deploy workflow from `workflow_dispatch` to `push` trigger on `main`, with a documented rollback path | Medium | Low | P1 |
| 3 | Incremental dbt models | Convert silver and gold from full-refresh table materialization to incremental merge on `(symbol, window_start)` / `(symbol, event_date)` | Medium | Low | P2 |
| 4 | Dataflow / streaming enrichment | Bounded Apache Beam / DataflowRunner proof validated (JOB_STATE_DRAINED; 10 proof rows to rtdp_analytics.market_events_beam_proof; see dataflow-bounded-runner-proof-evidence.md). Remaining gap: production windowed/stateful Dataflow streaming. No sustained always-on Dataflow pipeline exists. | Medium | High | P2 |
| 5 | Sustained throughput validation | Validate steady-state streaming above 5,000 events (e.g. a 10-minute continuous publish at 50 msg/s ≈ 30,000 events) | Medium | Low | P2 |
| 6 | dbt observability metrics | Add Cloud Monitoring metrics specific to the dbt refresh job (run duration, test pass/fail count) | Low | Low | P3 |
| 7 | Stored-function retirement | Remove `silver.refresh_market_event_minute_aggregates()` and `gold.refresh_market_event_daily_aggregates()` from `infra/postgres/init.sql` once operational confidence in the dbt path is established | Low | Low | P3 |
| 8 | Multi-environment (staging) | Add a staging GCP environment or a separate Terraform workspace | Low | High | P3 |

---

## 4. Critical Next Steps

> **Completed:** `feat/dbt-refresh-cloud-run-deploy` (dbt Cloud Run Job deployed and
> executed), `feat/dbt-scheduler-switch` (scheduler switched; scheduler-triggered execution
> accepted), `exec/bigquery-terraform-apply-evidence` (BigQuery analytical tier scaffold:
> dataset + 3 tables + IAM applied via Terraform; PLAN_EXIT=0), and
> `exec/bigquery-bounded-backfill-evidence` (6,104 rows from Cloud SQL
> `bronze.market_events` → BigQuery `market_events_raw`; analytical query confirmed;
> Cloud SQL NEVER / STOPPED). All branches accepted and documented.

### Branch 1: `feat/bigquery-incremental-append`

**Objective:** Implement continuous or scheduled incremental data movement into BigQuery
`market_events_raw`. The BigQuery scaffold and bounded backfill (6,104 rows) are accepted.
This branch must demonstrate that new events published after the initial backfill appear in
BigQuery without a full reload. Options: scheduled batch export (Cloud Scheduler → Cloud Run
Job → `bq load` with deduplication) or Pub/Sub fan-out (native BigQuery subscription or
streaming insert from the existing worker).

**Files likely touched:**

- `apps/bq-sink/` or extended `rtdp-pubsub-worker` (new or updated)
- `infra/terraform/gcp/bigquery.tf` (if new scheduled job or subscription added)
- `docs/bigquery-incremental-append-plan.md`, `docs/bigquery-incremental-append-evidence.md` (new)
- `docs/ARCHITECTURE_REVIEW.md`, `docs/EVIDENCE_INDEX.md`

**Must not touch:** existing Cloud Run services (unless adding a BigQuery write path),
`infra/postgres/`, dbt models, Terraform resources not related to the append path.

**Acceptance criteria:**

- New events published after the bounded backfill appear in BigQuery.
- Incremental load adds only new rows (idempotent append; no duplication of existing
  6,104-row baseline).
- A BigQuery analytical query over the combined dataset returns correct results.
- Terraform plan zero-diff after any new Terraform resources.
- Cloud SQL `NEVER / STOPPED` if Cloud SQL is involved in the export path.

**Technical relevance:** Closes the continuous or recurring data movement gap. Demonstrates
the operational BigQuery pattern expected in a senior data engineering review: not a one-time
load, but a recurring, idempotent append path. Completes the dual-store architecture
(Cloud SQL for serving, BigQuery for analytics with live data).

---

### Branch 2: `feat/cd-on-merge`

**Objective:** Add automatic deploy on push to `main` for the Pub/Sub worker (lowest
blast-radius service). Document the rollback path (revision rollback in Cloud Run).

**Files likely touched:**

- `.github/workflows/deploy-worker-cloud-run.yml` (add `push: branches: [main]` trigger,
  scoped to `apps/pubsub-worker/**`)
- `docs/cd-on-merge-plan.md`, `docs/cd-on-merge-evidence.md` (new)
- `docs/ARCHITECTURE_REVIEW.md`

**Must not touch:** API deploy workflow, Terraform, dbt models, test files.

**Acceptance criteria:**

- A commit to `apps/pubsub-worker/` on `main` triggers a deploy automatically.
- Deployed revision is tagged with `GITHUB_SHA`.
- A rollback command (`gcloud run services update-traffic`) is documented and tested.
- CI and deploy both green.
- Cloud SQL `NEVER / STOPPED` throughout.

**Technical relevance:** Advances from "manual deploy tested" to "deploy on merge, rollback
documented" — a distinction relevant for senior data engineering and platform engineering
roles.

---

### Branch 3: `feat/incremental-dbt-models`

**Objective:** Convert silver and gold models from `materialized='table'` (full refresh) to
`materialized='incremental'` merging on `(symbol, window_start)` and `(symbol, event_date)`
respectively.

**Files likely touched:**

- `dbt/models/silver/silver_market_event_minute_aggregates.sql` (add `is_incremental()` block)
- `dbt/models/gold/gold_market_event_daily_aggregates.sql` (add `is_incremental()` block)
- `dbt/models/silver/silver_market_event_minute_aggregates.yml` (update description)
- `dbt/models/gold/gold_market_event_daily_aggregates.yml` (update description)
- `docs/dbt-incremental-models-evidence.md` (new)

**Must not touch:** app runtime code, Terraform, stored functions.

**Acceptance criteria:**

- All 22 dbt tests pass after conversion.
- `dbt run` completes in CI against the ephemeral container.
- Full-refresh (`--full-refresh`) flag also passes.
- Cloud SQL validation (controlled window): incremental run adds only new rows; row counts
  increase correctly; API readback HTTP 200.
- Cloud SQL `NEVER / STOPPED`.

**Technical relevance:** Demonstrates production dbt materialization patterns. Incremental
materialization is the expected default for any dbt model at scale; the transition from
table to incremental demonstrates operational dbt maturity.

---

## 5. Out-of-Scope Items

The following are out of scope for this phase because they would be overengineering,
disproportionate in cost relative to the platform's production-light constraint model,
or add low technical differentiation at this scale.

| Item | Reason |
|---|---|
| Multi-region GCP deployment | Adds infrastructure cost and operational complexity with negligible differentiation for a single-environment production-light platform |
| Apache Flink / Dataflow windowed streaming | High implementation cost; Pub/Sub + Cloud Run is validated and sufficient for demonstrating the streaming ingestion pattern at this scale |
| Apache Airflow / Cloud Composer orchestration | Overengineering for a two-model dbt project; Cloud Scheduler is the appropriate tool for this scale |
| pgvector embedding population | The `ai.market_event_embeddings` schema exists; populating it is a separate product concern outside the data engineering scope |
| Auth / multi-tenant API layer | Outside the data engineering scope of this platform |
| Real-time UI dashboard | Frontend work adds no data engineering differentiation |
| Kafka Streams / KSQL | Redpanda/Kafka is used locally only; streaming SQL on top does not add GCP implementation evidence |
| Test coverage tooling (coverage.xml, codecov) | 156 tests with CI green on every push is sufficient; coverage percentage is not a meaningful signal at this scale |
| Separate staging GCP project | Doubles cloud cost; not appropriate until the platform has production traffic |
| Automatic rollback triggers | Disproportionate for a cost-controlled production-light platform; document the rollback command, do not automate it |

---

## 6. Platform Positioning

### Technical Hiring Context

This platform demonstrates a complete, evidence-backed GCP data engineering implementation:
real-time event ingestion (Pub/Sub → Cloud Run → Cloud SQL), governed dbt transformation
(22 tests, CI validation on every push, Cloud SQL parity evidence), full Terraform IaC
coverage (zero-diff plans, GCS remote state, Workload Identity), operational observability
(logs-based metrics, dashboard, alert policies, email notification), bounded load-test
evidence at 5,000 events, and a BigQuery analytical tier (Terraform-managed dataset and
tables, bounded backfill of 6,104 rows, analytical query confirmed). Cost control and
evidence discipline are verified throughout. It is not a continuously running production
service; every capability is backed by a scoped runbook and an accepted evidence document.

### Senior Technical Review

The platform implements a dual-path transformation architecture: dbt is the accepted
operational scheduled path, executed by Cloud Scheduler targeting the Terraform-owned
`rtdp-dbt-refresh-job` Cloud Run Job, while stored functions remain available as a legacy
rollback path. A BigQuery analytical tier (`rtdp_analytics` dataset, three Terraform-managed
tables) is live; a bounded backfill of 6,104 rows from `bronze.market_events` was validated
with source/target count match and an analytical query by symbol/event_type. The dbt job
runs silver and gold models against Cloud SQL through Secret Manager and Cloud SQL Unix
socket connectivity, writes a temporary `profiles.yml` at runtime, deletes it after
execution, and emits structured logs. Controlled evidence confirms `dbt run` PASS=2, silver
SELECT 256, gold SELECT 7, `dbt test` PASS=22, API readback HTTP 200, scheduler-triggered
execution success, BigQuery PLAN_EXIT=0, and final Cloud SQL state `NEVER / STOPPED`
throughout. IaC covers every GCP resource via phased import with zero-diff plans. The CI
pipeline runs ruff, 156 pytest tests, an import smoke test, and a full dbt compile/run/test
on ephemeral containers on every push.

### Technical Scope for Production Deployment Discussion

This platform demonstrates the practices required for a production GCP event processing
system: event ingestion from Pub/Sub with a dead-letter policy, idempotent persistence to
Cloud SQL, governed dbt transformations with automated quality tests, a BigQuery analytical
warehouse (Terraform-managed, bounded batch backfill validated), Cloud Monitoring alert
policies with email notification, and a FastAPI serving layer. The operational model is
cost-controlled and evidence-backed: every GCP resource is managed by Terraform, every
validation step is documented in a scoped evidence file. The platform is not a continuously
running production service, but it demonstrates the IaC discipline, transformation
governance, analytical tier architecture, observability, and load-tested reliability that a
production deployment would require.

---

## 7. Capability Scorecard

| Dimension | Score (0–10) | Basis |
|---|---|---|
| GCP alignment | 9 | Pub/Sub, Cloud Run (services + jobs), Cloud SQL, Secret Manager, Artifact Registry, Workload Identity, Cloud Monitoring, Cloud Scheduler all deployed and IaC-managed. BigQuery analytical tier scaffold implemented (rtdp_analytics dataset, 3 Terraform-managed tables; bounded backfill of 6,104 rows accepted; analytical query confirmed). Bounded DataflowRunner proof validated; no production windowed Dataflow streaming. |
| Real-time / event-driven architecture | 7 | Full Pub/Sub → Cloud Run → PostgreSQL path validated at 5,000 events. DLQ configured. Bounded DataflowRunner proof validated (10 proof rows, JOB_STATE_DRAINED); no production windowed Dataflow streaming. Bounded bursts only. No continuous streaming to BigQuery. |
| IaC maturity | 8 | 100% of GCP resources in Terraform with zero-diff plans and GCS remote state. Workload Identity for CI auth. All resources applied; no `terraform apply` executed without a scoped evidence branch. |
| dbt / transformation maturity | 8 | Silver and gold models with 22 tests. CI validates on every push. Cloud SQL parity confirmed. `rtdp-dbt-refresh-job` deployed, executed, and scheduler-triggered execution accepted. dbt is the operational scheduled transformation path; stored functions preserved as rollback. Incremental models not yet implemented. |
| Observability | 7 | 4 logs-based metrics with datapoints, 4-panel dashboard, 2 alert policies, email notification channel, DLQ. No distributed tracing. No BigQuery-specific metrics. |
| CI/CD | 7 | CI: ruff + pytest + smoke test + dbt on every push. Terraform Plan CI on infra path changes. Manual deploy workflows validated for API and worker. No auto-deploy-on-merge. |
| Reliability / rollback | 7 | DLQ with maxDeliveryAttempts=5. Alert policies enabled. Stored functions as dbt rollback. SLO and incident response documented. Cloud SQL NEVER/STOPPED discipline. Not continuously running. |
| Cost control | 9 | Rigorous Cloud SQL NEVER/STOPPED discipline confirmed in every evidence document. Scheduler PAUSED by default. Manual-only deploys. No unexpected idle compute. |
| Documentation / evidence | 9 | Every capability is backed by a scoped runbook and a separate accepted evidence document. EVIDENCE_INDEX, ARCHITECTURE_REVIEW, and SLO document up to date. Phased import evidence. Zero overclaiming. |
| Technical hiring relevance | 9 | Complete GCP + dbt + IaC + observability + BigQuery evidence. BigQuery scaffold and bounded batch backfill close the dual-store architecture gap. Remaining gaps are incremental append path and auto-CD. Conservative production-light framing keeps the evidence aligned with senior technical review expectations. |
| Enterprise production readiness | 6 | Cost-controlled single-environment platform validated in bounded windows. dbt operationally scheduled (paused by default). Not continuously running. No multi-region. No staging environment. No real traffic. Appropriate for a production-light evidence platform at this stage. |

**Summary:** A well-evidenced, disciplined GCP data engineering platform. Strongest signals
are IaC maturity, documentation quality, cost discipline, dbt governance, and BigQuery
analytical tier implementation. The gap between current state and enterprise production is
clearly understood and explicitly documented.

---

## 8. Recommended Next Branch

**Execute `feat/bigquery-incremental-append` next.**

The dbt operational deployment, scheduler switch, BigQuery analytical tier scaffold, and
BigQuery bounded backfill are all accepted. The platform now demonstrates a dual-store
architecture (Cloud SQL for serving, BigQuery for analytics) with bounded batch data
movement evidence (6,104 rows, analytical query confirmed). The remaining BigQuery gap is
continuous or incremental data movement: new events appearing in Cloud SQL or directly from
Pub/Sub must flow into BigQuery without a full reload.

After the incremental append path, `feat/cd-on-merge` advances the CI/CD posture from
"manual deploy tested" to "deploy on merge, rollback documented." Then
`feat/incremental-dbt-models` demonstrates production dbt materialization patterns.

Recommended sequence: BigQuery incremental append → automatic CD → incremental dbt models.

---

## Validation Results

| Check | Result |
|---|---|
| `uv run pytest -q` | 156 passed |
| `uv run ruff check .` | All checks passed |
| `terraform fmt -check -recursive infra/terraform/gcp` | Clean (exit 0) |
| `terraform -chdir=infra/terraform/gcp validate` | Success — configuration is valid |
| `terraform plan -detailed-exitcode` | PLAN_EXIT=0 |
| `test ! -f dbt/profiles.yml` | `REPO_DBT_PROFILE_ABSENT=true` |
| `git status --ignored --short dbt` | No output — no tracked or ignored artifacts in dbt/ |
| BigQuery Terraform apply (`exec/bigquery-terraform-apply-evidence`) | Apply complete — 6 added, 0 changed, 0 destroyed; PLAN_EXIT=0 |
| BigQuery bounded backfill (`exec/bigquery-bounded-backfill-evidence`) | 6,104 rows Cloud SQL → BigQuery; source/target count match OK; analytical query returned 4 symbol rows |
| `git diff --stat` | No diff |
| `git status --short --branch` | `## docs/post-bigquery-evidence-refresh` (clean) |

---

## Safety Confirmation

| Control | Status |
|---|---|
| No runtime code modified | Confirmed |
| No Terraform files modified | Confirmed |
| No GitHub Actions workflows modified | Confirmed |
| No dbt models modified | Confirmed |
| No tests modified | Confirmed |
| No stored functions removed | Confirmed |
| Scheduler URI | Accepted — scheduler targets `rtdp-dbt-refresh-job:run`; `paused = true` preserved |
| Cloud SQL bounded start | Confirmed — started only for BigQuery bounded backfill validation window; returned to `NEVER / STOPPED` after backfill (docs/bigquery-bounded-backfill-evidence.md) |
| Terraform apply | Executed for dbt job deployment, scheduler URI switch, and BigQuery analytical tier scaffold; all documented in scoped evidence branches |
| GCP state mutation | `rtdp-dbt-refresh-job` Cloud Run Job created; scheduler URI updated; BigQuery dataset `rtdp_analytics` + 3 tables + 2 IAM bindings created — all accepted intentional changes |
| No `dbt/profiles.yml` committed | Confirmed |
| No generated dbt artifacts committed | Confirmed |
| No BigQuery data artifacts committed | Confirmed — backfill CSV written to /tmp only; no generated data files in repository |
