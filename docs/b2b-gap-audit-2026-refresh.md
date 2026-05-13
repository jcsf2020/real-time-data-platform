# B2B Gap Audit — 2026 Refresh

**Date:** 2026-05-13  
**Scope:** Post dbt / Cloud Run Job / Terraform scaffold work  
**Branch:** `main` (clean, zero diff)  
**Validation state:** 153 pytest passed · ruff clean · terraform fmt/validate clean · dbt/profiles.yml absent

---

## 1. Executive Status

### What the platform currently proves

This is a production-light, evidence-driven GCP data platform. It demonstrates:

- A complete real-time ingestion path: Pub/Sub → Cloud Run worker → Cloud SQL → FastAPI API, validated end-to-end with 100 / 1,000 / 5,000-event bounded load tests.
- A medallion data architecture (bronze / silver / gold / observability / ai schemas) in PostgreSQL, with a governed dbt transformation layer covering silver and gold models.
- Full Terraform IaC coverage across every deployed GCP resource, backed by a GCS remote state, validated with zero-diff plans. A new Cloud Run Job scaffold for the dbt refresh path is committed but not yet applied.
- Operational observability: 4 logs-based Cloud Monitoring metrics with confirmed timeSeries datapoints, a 4-panel dashboard, 2 enabled alert policies with email notification, and a production DLQ with `deadLetterPolicy`.
- A two-job CI pipeline: pytest (153 tests), ruff lint, import smoke test, and a full dbt compile/run/test run on every push — including an ephemeral pgvector container.
- Principled cost control: Cloud SQL is `NEVER / STOPPED` outside bounded validation windows. No resource has been mutated without a scoped, runbook-backed evidence branch.
- dbt models validated against real Cloud SQL data with parity vs. stored functions confirmed (silver 256/256, gold 7/7). API readback verified. Operational execution pending Terraform apply of the new Cloud Run Job.

### What is production-light versus not production-grade

| Category | Production-light (claimed) | Not production-grade (honest) |
|---|---|---|
| Availability | Validated during bounded windows only | Not continuously running; Cloud SQL stopped by default |
| Scale | 5,000-event bounded bursts validated | Sustained streaming throughput not validated above 5,000 |
| Data | Synthetic deterministic events | No real-world data variability exercised |
| dbt | CI-validated, Cloud SQL parity confirmed | Not the operational refresh path yet; stored functions are authoritative |
| CI/CD | CI green on every push; manual deploys tested | No automatic deploy-on-merge |
| Multi-environment | Single GCP project / environment | No staging, no canary, no multi-region |
| SLO | Defined and documented | Aspirational targets; no continuous measurement |

### Current B2B / recruiter value

**Strong:** Full GCP data engineering stack evidenced end-to-end. Terraform discipline and evidence-first documentation are distinguishing signals. dbt with CI validation and Cloud SQL parity demonstrates governed transformation practice. The Pub/Sub DLQ, alert policies, and email notification channel demonstrate production-aware reliability thinking.

**Honest ceiling:** This is a portfolio-grade platform operated in controlled windows, not a service taking live traffic 24/7. The dbt operational migration, BigQuery analytical tier, and automatic CD are the three gaps most visible to a technical interviewer.

---

## 2. Resolved Gaps Since the Previous Audit

### dbt transformation layer

**Resolved.** Silver and gold dbt models implemented (`dbt/models/silver/`, `dbt/models/gold/`), with 22 schema and business-rule tests covering source quality, model integrity, and price-range constraints. Models reproduce the existing stored-function logic with confirmed parity. Stored functions are preserved as a rollback path. Evidence: `docs/dbt-ci-validation-evidence.md`.

### dbt CI

**Resolved.** A `dbt` CI job was added to `.github/workflows/ci.yml` (PR #105). It runs after the `validate` job and executes `dbt deps → dbt compile → dbt run → dbt test` against an ephemeral `pgvector/pgvector:pg16` service container on every push to `main` and on PRs. No GCP resources are touched. Evidence: `docs/dbt-ci-validation-evidence.md`.

### dbt Cloud SQL validation

**Resolved.** A controlled validation window was executed against the real Cloud SQL instance with Cloud SQL Auth Proxy. dbt compiled, ran, and tested successfully. Silver output: 256 rows (matches stored-function baseline). Gold output: 7 rows (matches baseline). All 22 dbt tests passed. API `/aggregates/minute` and `/aggregates/daily` both returned HTTP 200 with rows. Cloud SQL was returned to `NEVER / STOPPED`. Evidence: `docs/dbt-cloud-sql-validation-evidence.md`.

### dbt refresh runtime

**Resolved.** `apps/dbt-refresh-job/src/rtdp_dbt_refresh_job/__init__.py` implements the `rtdp-dbt-refresh-job` CLI. It orchestrates `dbt deps → dbt compile → dbt run --select silver,gold → dbt test`, writes a temporary `profiles.yml` at runtime and deletes it after each run, emits structured JSON logs, and supports four `DBT_REFRESH_MODE` values (`compile`, `run`, `test`, `run-and-test`). 36 dedicated pytest tests cover config validation, profiles generation, subprocess orchestration, and cleanup. Evidence: `tests/test_dbt_refresh_job.py`.

### DATABASE_URL runtime handling

**Resolved** (branch `feat/dbt-refresh-database-url-runtime`). The runtime now parses the full `postgresql://user:password@host/dbname` URL stored in the `rtdp-database-url` Secret Manager secret and derives connection fields. Explicit `DBT_POSTGRES_*` env vars override any field from the URL. `DBT_POSTGRES_HOST` is set to the Cloud SQL Unix socket path on Cloud Run, overriding the TCP host from the URL. `DBT_POSTGRES_PASSWORD` is no longer wired directly to the secret (which would have passed the full URL string as the password). The Terraform scaffold and deploy workflow were corrected to reflect this contract. Evidence: `docs/dbt-refresh-cloud-run-job-plan.md`.

### Terraform Cloud Run Job scaffold

**Resolved.** `google_cloud_run_v2_job.rtdp_dbt_refresh_job` is declared in `infra/terraform/gcp/cloud_run_jobs.tf`. It is Terraform-owned — no workflow creates or updates the Cloud Run Job. The resource specifies the Cloud SQL volume mount, the `DATABASE_URL` secret reference, explicit `DBT_POSTGRES_*` env vars, a 600s timeout, and lifecycle ignore rules for image and annotation drift. Terraform fmt and validate are clean. `terraform apply` and deployment evidence remain pending a future controlled branch. Evidence: `docs/dbt-refresh-cloud-run-job-plan.md`.

### IaC / deploy boundary correction

**Resolved.** The previous state had `deploy-dbt-refresh-cloud-run.yml` attempting Cloud Run Job deployment. The boundary has been corrected: the workflow builds and pushes the container image only (`IMAGE_PUSHED=true`, `CLOUD_RUN_JOB_NOT_DEPLOYED_BY_THIS_WORKFLOW=true`). Terraform is the sole source of truth for the Cloud Run Job definition. The scheduler TODO comment in `scheduler.tf` marks the pending URI switch. Evidence: `docs/dbt-refresh-cloud-run-job-plan.md`, `ARCHITECTURE_REVIEW.md`.

### Observability

**Resolved.** Four logs-based Cloud Monitoring metrics with confirmed timeSeries datapoints (`worker_message_processed_count`, `worker_message_error_count`, `silver_refresh_success_count`, `silver_refresh_error_count`). A 4-panel RTDP Pipeline Overview dashboard created in GCP and exported to `infra/monitoring/dashboards/rtdp-pipeline-overview.json`. Two enabled alert policies with an email notification channel (`RTDP Operator Email Alerts`, channel ID `1439157631105258885`). All monitoring resources are under Terraform state with zero-diff plan. Evidence: `docs/cloud-monitoring-dashboard-evidence.md`, `docs/cloud-alert-policies-evidence.md`.

### Load testing

**Resolved.** Three tiers of bounded cloud load tests accepted: 100 events (all criteria met), 1,000 events (all criteria met, metric sum = 1,000), 5,000 events (all criteria met, metric sum = 4,963, DLQ empty, silver refresh succeeded). Each test used deterministic event-ID prefixes, bounded publish rates (≤50 msg/s), Cloud SQL started only for the test window, and confirmed `NEVER / STOPPED` on completion. Evidence: `docs/load-test-1000-cloud-evidence.md`, `docs/load-test-5000-cloud-evidence.md`.

### Pub/Sub / DLQ

**Resolved.** Production push subscription `market-events-raw-worker-push` updated in-place with `deadLetterPolicy`: `maxDeliveryAttempts=5`, 10s/60s backoff, routing to `market-events-raw-dlq`. DLQ topic created, Pub/Sub service agent IAM granted. DLQ confirmed empty during 5,000-event load test. Evidence: `docs/production-pubsub-dlq-evidence.md`.

### Cost control

**Verified throughout.** Cloud SQL (`rtdp-postgres`) is kept `NEVER / STOPPED` by default; confirmed in every evidence document. Cloud Scheduler (`rtdp-silver-refresh-scheduler`) is kept `PAUSED` by default. All deployments are manual `workflow_dispatch`; no continuous pipeline incurs unexpected costs. No `terraform apply` was run during import operations.

---

## 3. Remaining Gaps

Ranked by B2B value impact, technical risk, and recommended priority.

| # | Gap | Description | B2B Value Impact | Technical Risk | Priority |
|---|---|---|---|---|---|
| 1 | dbt operational deployment | `terraform apply` for `rtdp-dbt-refresh-job`, execute the job against Cloud SQL, validate dbt run + test success, confirm API readback | High | Medium | P0 |
| 2 | Scheduler switch to dbt job | Update scheduler URI from `rtdp-silver-refresh-job:run` to `rtdp-dbt-refresh-job:run`; validate one scheduled execution | High | Low | P1 |
| 3 | BigQuery analytical tier | Stream or batch-export bronze events to BigQuery; demonstrate long-horizon analytical queries separate from the operational store | High | Medium | P1 |
| 4 | Automatic deploy-on-merge | Convert at least one deploy workflow from `workflow_dispatch` to `push` trigger on `main`, with a meaningful rollback path | Medium | Low | P1 |
| 5 | Incremental dbt models | Convert silver and gold from full-refresh table materialization to incremental merge on `(symbol, window_start)` / `(symbol, event_date)` | Medium | Low | P2 |
| 6 | Dataflow / streaming enrichment | Replace or augment the Cloud Run worker with a Dataflow pipeline for windowed aggregations | Medium | High | P2 |
| 7 | Sustained throughput validation | Validate steady-state streaming above 5,000 events (e.g. a 10-minute continuous publish at 50 msg/s ≈ 30,000 events) | Medium | Low | P2 |
| 8 | dbt observability metrics | Add Cloud Monitoring metrics specific to the dbt refresh job (run duration, test pass/fail count) | Low | Low | P3 |
| 9 | Stored-function retirement | Remove `silver.refresh_market_event_minute_aggregates()` and `gold.refresh_market_event_daily_aggregates()` from `infra/postgres/init.sql` after dbt is the validated operational path | Low | Low | P3 |
| 10 | Multi-environment (staging) | Add a staging GCP environment or a separate Terraform workspace | Low | High | P3 |

---

## 4. Critical Next Steps

### Branch 1: `feat/dbt-refresh-cloud-run-deploy`

**Objective:** Deploy `rtdp-dbt-refresh-job` via `terraform apply`, execute it once manually against Cloud SQL, and produce accepted evidence of dbt run + test success.

**Files likely touched:**
- `docs/dbt-refresh-deploy-evidence.md` (new)
- `docs/evidence/dbt-refresh-deploy/` (new evidence artifacts)
- `docs/ARCHITECTURE_REVIEW.md` (update Known Remaining Gaps)
- `docs/EVIDENCE_INDEX.md` (add row)

**Must not touch:** `infra/terraform/gcp/cloud_run_jobs.tf`, `infra/terraform/gcp/scheduler.tf`, dbt models, `apps/silver-refresh-job/`, `apps/dbt-refresh-job/__init__.py`, any test files, GitHub Actions workflows.

**Validation commands:**
```bash
uv run pytest -q
uv run ruff check .
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
test ! -f dbt/profiles.yml && echo "REPO_DBT_PROFILE_ABSENT=true"
git status --ignored --short dbt
git diff --stat
```

**Acceptance criteria:**
- `terraform apply` exits 0; `google_cloud_run_v2_job.rtdp_dbt_refresh_job` created in GCP.
- `gcloud run jobs execute rtdp-dbt-refresh-job --region=europe-west1 --wait` exits 0.
- Cloud Logging confirms `dbt_run_and_test` with `status: success`.
- API `/aggregates/minute` and `/aggregates/daily` return HTTP 200 with rows.
- Cloud SQL returned to `NEVER / STOPPED`.
- No `dbt/profiles.yml` committed.
- 153 pytest pass; ruff clean.

**B2B value gained:** Closes the most visible remaining gap: dbt is not only CI-validated and Cloud SQL-parity confirmed — it runs operationally on GCP. Demonstrates end-to-end governed transformation in production cloud infrastructure.

---

### Branch 2: `feat/dbt-scheduler-switch`

**Objective:** Update the Cloud Scheduler URI to target `rtdp-dbt-refresh-job:run`, validate one controlled scheduled execution, and confirm the success log and metric.

**Files likely touched:**
- `infra/terraform/gcp/scheduler.tf` (update URI, keep `paused = true` until validation window)
- `docs/dbt-scheduler-switch-evidence.md` (new)
- `docs/ARCHITECTURE_REVIEW.md` (update)
- `docs/EVIDENCE_INDEX.md` (add row)

**Must not touch:** `cloud_run_jobs.tf`, dbt models, app code, test files.

**Validation commands:**
```bash
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
uv run pytest -q
```

**Acceptance criteria:**
- `terraform apply` on `scheduler.tf` updates the scheduler URI; zero drift on subsequent plan.
- One controlled `gcloud scheduler jobs run` execution triggers `rtdp-dbt-refresh-job`.
- Cloud Logging confirms `status: success` for the dbt refresh.
- Scheduler returned to `paused = true`.
- Cloud SQL returned to `NEVER / STOPPED`.

**B2B value gained:** Closes the operational migration loop. The platform now demonstrates a fully automated, scheduled dbt transformation path on GCP — not just a manual execution proof.

---

### Branch 3: `feat/bigquery-streaming-sink`

**Objective:** Introduce BigQuery as an analytical tier. Write a Cloud Run worker or Cloud Function that streams or batch-exports events from `bronze.market_events` (or directly from Pub/Sub) into a BigQuery dataset. Demonstrate a SQL query over long-horizon event history.

**Files likely touched:**
- `infra/terraform/gcp/bigquery.tf` (new resource: dataset, table)
- `apps/bq-sink/` or extended worker (new or updated)
- `docs/bigquery-sink-plan.md`, `docs/bigquery-sink-evidence.md` (new)
- `docs/ARCHITECTURE_REVIEW.md`, `docs/EVIDENCE_INDEX.md`

**Must not touch:** existing Cloud Run services, `infra/postgres/`, dbt models.

**Validation commands:**
```bash
uv run pytest -q
uv run ruff check .
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
```

**Acceptance criteria:**
- BigQuery dataset and table created via Terraform.
- At least 1,000 events queryable in BigQuery via `bq query`.
- A sample analytical query (e.g. daily average price per symbol) returns correct results.
- Terraform plan zero-diff after apply.
- Cloud SQL `NEVER / STOPPED` throughout.

**B2B value gained:** Adds the most-requested missing layer for data engineering roles. BigQuery + streaming Pub/Sub → BigQuery is a canonical GCP pattern. Bridges the platform from an operational store to a dual-store architecture (Cloud SQL for serving, BigQuery for analytics).

---

### Branch 4: `feat/cd-on-merge`

**Objective:** Add auto-deploy on push to `main` for the Pub/Sub worker (lowest blast-radius service). Document the rollback path (revision rollback in Cloud Run).

**Files likely touched:**
- `.github/workflows/deploy-worker-cloud-run.yml` (add `push: branches: [main]` trigger, scoped to `apps/pubsub-worker/**`)
- `docs/cd-on-merge-plan.md`, `docs/cd-on-merge-evidence.md` (new)
- `docs/ARCHITECTURE_REVIEW.md`

**Must not touch:** API deploy workflow, Terraform, dbt models, test files.

**Validation commands:**
```bash
uv run pytest -q
uv run ruff check .
```

**Acceptance criteria:**
- A commit to `apps/pubsub-worker/` on `main` triggers a deploy automatically.
- Deployed revision is tagged with `GITHUB_SHA`.
- A rollback command (`gcloud run services update-traffic`) is documented and tested.
- CI and deploy both green.
- Cloud SQL `NEVER / STOPPED` throughout.

**B2B value gained:** Demonstrates modern CD discipline. Moves from "manual deploy tested" to "deploy on merge, rollback documented" — the difference a hiring manager cares about for a senior data engineering role.

---

### Branch 5: `feat/incremental-dbt-models`

**Objective:** Convert silver and gold models from `materialized='table'` (full refresh) to `materialized='incremental'` merging on `(symbol, window_start)` and `(symbol, event_date)` respectively.

**Files likely touched:**
- `dbt/models/silver/silver_market_event_minute_aggregates.sql` (add `is_incremental()` block)
- `dbt/models/gold/gold_market_event_daily_aggregates.sql` (add `is_incremental()` block)
- `dbt/models/silver/silver_market_event_minute_aggregates.yml` (update description)
- `dbt/models/gold/gold_market_event_daily_aggregates.yml` (update description)
- `docs/dbt-incremental-models-evidence.md` (new)

**Must not touch:** app runtime code, Terraform, stored functions.

**Validation commands:**
```bash
uv run dbt compile --project-dir dbt --profiles-dir dbt
uv run dbt run --project-dir dbt --profiles-dir dbt
uv run dbt test --project-dir dbt --profiles-dir dbt
uv run pytest -q
uv run ruff check .
```

**Acceptance criteria:**
- All 22 dbt tests pass after conversion.
- `dbt run` completes in CI against the ephemeral container.
- Full-refresh (`--full-refresh`) flag also passes.
- Cloud SQL validation (controlled window): incremental run adds only new rows; row counts increase correctly; API readback HTTP 200.
- Cloud SQL `NEVER / STOPPED`.

**B2B value gained:** Demonstrates awareness of dbt production performance patterns. Incremental materialization is the expected default for any dbt model at scale; showing the transition from table to incremental signals production dbt maturity, not just proof-of-concept knowledge.

---

## 5. Clear Stop Conditions

The following should **not** be built next because they would be overengineering, low portfolio signal, or disproportionate cost for this project's purpose.

| Item | Reason to stop |
|---|---|
| Multi-region GCP deployment | Adds infrastructure cost and operational complexity with zero differentiation for a portfolio project at this stage |
| Apache Flink / Dataflow windowed streaming | High implementation cost; Pub/Sub + Cloud Run is already validated and sufficient for demonstrating the streaming pattern |
| Apache Airflow / Cloud Composer orchestration | Overengineering for a two-model dbt project; Cloud Scheduler is the right tool for this scale |
| pgvector embedding population | The `ai.market_event_embeddings` schema exists; populating it is a separate product concern, not a data engineering signal |
| Auth / multi-tenant API layer | Not a data engineering concern for this project |
| Real-time UI dashboard | Frontend work adds no data engineering signal |
| Kafka Streams / KSQL | Redpanda/Kafka is used locally only; adding streaming SQL on top does not add GCP portfolio value |
| Test coverage tooling (coverage.xml, codecov) | 153 tests with CI is already strong; coverage percentage adds no recruiter signal |
| Separate staging GCP project | Doubles cloud cost; not appropriate until the platform has production traffic |
| Automatic rollback triggers | Undifferentiated for a cost-controlled portfolio platform; document the rollback command, do not automate it |

---

## 6. Recommended Final Positioning

### For recruiters

> A production-light GCP data platform demonstrating the full spectrum of modern data engineering: real-time event ingestion (Pub/Sub → Cloud Run → Cloud SQL), governed transformation (dbt with 22 tests, CI validation, and Cloud SQL parity evidence), IaC (100% of GCP resources in Terraform with zero-diff plans and GCS remote state), operational observability (logs-based metrics, dashboard, alert policies, email notification), and bounded load-test evidence at 5,000 events. Principled cost control is maintained throughout. The platform is evidence-driven: every capability is backed by a scoped runbook and an accepted evidence document.

### For technical interviewers

> The platform implements a dual-path architecture: a stored-function refresh path that has been operationally validated with scheduled execution proof, and a dbt transformation layer that has been CI-validated on every push and confirmed at output parity against Cloud SQL. The dbt operational deployment is the current frontier: the Terraform resource is scaffolded, the runtime parses `DATABASE_URL` to derive connection fields and writes a temporary `profiles.yml` that is deleted after each run, and the credential contract has been resolved. The next step is `terraform apply` followed by a controlled execution evidence branch. IaC covers every GCP resource via phased import with zero-diff plans; no resource was created without an explicit evidence trail. The CI pipeline runs ruff, 153 pytest tests, an import smoke test, and a full dbt compile/run/test on ephemeral containers on every push.

### For B2B clients

> This platform demonstrates a vendor-appropriate pattern for a real-time event processing system on GCP: event ingestion from Pub/Sub with a dead-letter policy, idempotent persistence to Cloud SQL, governed dbt transformations with automated quality tests, Cloud Monitoring alert policies with email notification, and a FastAPI serving layer. The operational model is cost-controlled and evidence-backed: every GCP resource is managed by Terraform, every validation step is documented in a scoped evidence file. The platform is not a continuously running production service, but it demonstrates the practices — IaC discipline, transformation governance, observability, and load-tested reliability — that a production deployment would require.

---

## 7. Updated Scorecard

| Dimension | Score (0–10) | Basis |
|---|---|---|
| GCP alignment | 8 | Pub/Sub, Cloud Run (services + jobs), Cloud SQL, Secret Manager, Artifact Registry, Workload Identity, Cloud Monitoring, Cloud Scheduler all deployed and IaC-managed. BigQuery and Dataflow absent. |
| Real-time / event-driven architecture | 7 | Full Pub/Sub → Cloud Run → PostgreSQL path validated at 5,000 events. DLQ configured. No Dataflow / windowed streaming. Bounded bursts only. |
| IaC maturity | 8 | 100% of GCP resources in Terraform with zero-diff plans and GCS remote state. Workload Identity for CI auth. One scaffold resource (`rtdp-dbt-refresh-job`) not yet applied. No `terraform apply` executed without a scoped evidence branch. |
| dbt / transformation maturity | 7 | Silver and gold models with 22 tests. CI validates on every push. Cloud SQL parity confirmed. `DATABASE_URL` runtime handling resolved. Not yet the operational refresh path; stored functions remain authoritative. |
| Observability | 7 | 4 logs-based metrics with datapoints, 4-panel dashboard, 2 alert policies, email notification channel, DLQ. No distributed tracing, no Prometheus scrape endpoint wired to Cloud Monitoring. |
| CI/CD | 7 | CI: ruff + pytest + smoke test + dbt on every push. Terraform Plan CI on infra path changes. Manual deploy workflows validated for API and worker. No auto-deploy-on-merge. |
| Reliability / rollback | 7 | DLQ with maxDeliveryAttempts=5. Alert policies enabled. Stored functions as dbt rollback. SLO and incident response documented. Cloud SQL NEVER/STOPPED discipline. Not continuously running. |
| Cost control | 9 | Rigorous Cloud SQL NEVER/STOPPED discipline confirmed in every evidence document. Scheduler PAUSED by default. Manual-only deploys. No unexpected idle compute. |
| Documentation / evidence | 9 | Exceptional: every capability is backed by a scoped runbook and a separate accepted evidence document. EVIDENCE_INDEX, ARCHITECTURE_REVIEW, and SLO document up to date. Phased import evidence. Zero overclaiming. |
| B2B market value | 7 | Strong GCP + dbt + IaC + observability signal. Missing: BigQuery, Dataflow, auto-CD. Honest positioning as production-light reduces risk of credibility gap in interviews. |
| Enterprise production readiness | 5 | Cost-controlled single-environment platform validated in bounded windows. Not continuously running. No multi-region. No staging environment. No real traffic. No auto-scaling evidence. Appropriate ceiling for a portfolio project. |

**Overall signal:** A well-evidenced, disciplined GCP data engineering portfolio project. Strongest signals are IaC maturity, documentation quality, cost discipline, and dbt governance approach. The gap between current state and enterprise-grade production is clearly understood and honestly communicated.

---

## 8. Final Recommendation

**Execute `feat/dbt-refresh-cloud-run-deploy` next.**

This is the highest-priority remaining branch because it closes the most visible gap: dbt is CI-validated, Cloud SQL-parity confirmed, runtime package tested (36 tests), Terraform resource scaffolded, and credential contract resolved. The only missing piece is `terraform apply` followed by a controlled execution evidence branch. When this branch is merged, the platform will demonstrate that dbt runs operationally on GCP infrastructure — not just in CI. That is the difference between "I know dbt" and "I deployed dbt as an operational transformation job on GCP."

After that, `feat/dbt-scheduler-switch` closes the automation loop (scheduled dbt execution, not just manual). Then `feat/bigquery-streaming-sink` adds the analytical tier that is currently the largest structural gap in the architecture. BigQuery is the most-asked-about missing component in any GCP data engineering review.

Do not start BigQuery before the dbt operational deployment is accepted. Do not start CD-on-merge before the BigQuery tier is planned. The logical sequence is: dbt operational → scheduler switch → BigQuery → CD-on-merge → incremental models.

The platform is already at a strong B2B signal level. The next three branches will take it from "strong portfolio" to "credible production-pattern demonstration."

---

## Validation Results

| Check | Result |
|---|---|
| `uv run pytest -q` | 153 passed |
| `uv run ruff check .` | All checks passed |
| `terraform fmt -check -recursive infra/terraform/gcp` | Clean (exit 0) |
| `terraform -chdir=infra/terraform/gcp validate` | Success — configuration is valid |
| `test ! -f dbt/profiles.yml` | `REPO_DBT_PROFILE_ABSENT=true` |
| `git status --ignored --short dbt` | No output — no tracked or ignored artifacts in dbt/ |
| `git diff --stat` | No diff |
| `git status --short --branch` | `## main...origin/main` (clean) |

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
| No scheduler state changed | Confirmed — `paused = true` in `scheduler.tf` |
| No Cloud SQL started | Confirmed — Cloud SQL not touched |
| No `terraform apply` run | Confirmed |
| No GCP state mutated | Confirmed |
| No `dbt/profiles.yml` committed | Confirmed |
| No generated dbt artifacts committed | Confirmed |
