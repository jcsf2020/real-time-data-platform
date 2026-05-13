# Evidence Index

This document is a curated map of project evidence for the Real-Time Data Platform.
It is intended for fast review of architecture, infrastructure-as-code, CI/CD, observability,
load testing, and production-readiness evidence. It indexes existing documentation; it does
not summarize or vouch for the project beyond what the linked documents contain.

---

## Review Path

Recommended 3-minute entry path for reviewers:

1. [README.md](../README.md) -- project overview, local quickstart, GCP status summary
2. [docs/gcp-architecture.md](gcp-architecture.md) -- GCP service mapping and target flow
3. [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) -- this document (evidence categories and links)
4. [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) -- end-to-end cloud validation
5. [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) -- bounded throughput evidence

---

## Current Validated Capabilities

| Area | Evidence | Status |
|---|---|---|
| Local Kafka-compatible pipeline | README.md, Docker Compose stack | Implemented |
| GCP Pub/Sub ingestion | gcp-end-to-end-validation.md | Validated |
| Cloud Run worker | gcp-worker-cloud-validation.md | Validated |
| Cloud Run API | gcp-end-to-end-validation.md | Validated |
| Cloud SQL PostgreSQL | cloud-sql-terraform-import-plan-evidence.md | Implemented, NEVER/STOPPED |
| Terraform-managed infrastructure | All *-import-plan-evidence.md files | Zero-diff plan verified |
| Terraform remote backend | terraform-remote-backend-migration-evidence.md | GCS backend active |
| Workload Identity Federation | workload-identity-terraform-import-plan-evidence.md | Imported, zero-diff |
| Artifact Registry | artifact-registry-terraform-import-plan-evidence.md | Imported, zero-diff |
| Manual deploy workflow -- worker | cloud-run-worker-manual-deploy-evidence.md | workflow_dispatch validated |
| Manual deploy workflow -- API | api-manual-deploy-evidence.md | workflow_dispatch validated |
| Cloud Monitoring metrics | cloud-logs-based-metrics-datapoint-validation.md | 4 metrics, datapoints confirmed |
| Alert policies | cloud-alert-policies-evidence.md | 2 policies, email channel attached |
| Monitoring dashboard | cloud-monitoring-dashboard-evidence.md | 4-panel dashboard, GCP-created |
| Load test evidence | load-test-100/1000/5000-cloud-evidence.md | 100 / 1,000 / 5,000 events accepted |
| DLQ and retry configuration | production-pubsub-dlq-evidence.md | deadLetterPolicy, maxDeliveryAttempts=5 |
| Scheduler and silver refresh | silver-refresh-scheduler-execution-proof-evidence.md | Scheduled execution validated |
| Cost-control state | Cloud SQL NEVER/STOPPED, Scheduler PAUSED (multiple docs) | Verified throughout |

---

## Architecture Evidence

| Document | Purpose | What It Proves |
|---|---|---|
| [docs/gcp-architecture.md](gcp-architecture.md) | GCP service mapping | Maps local components to Cloud Run, Pub/Sub, Cloud SQL, BigQuery, Dataflow |
| [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) | End-to-end cloud validation | Full Pub/Sub -> Cloud Run worker -> Cloud SQL -> API readback path confirmed |
| [docs/gcp-worker-cloud-validation.md](gcp-worker-cloud-validation.md) | Cloud Run worker validation | Worker deployment, Pub/Sub push subscription, idempotent bronze writes |
| [docs/worker-structured-logs-validation.md](worker-structured-logs-validation.md) | Structured log validation | Cloud Logging jsonPayload structure confirmed for the deployed worker |

---

## Infrastructure as Code Evidence

Terraform import operations were performed against a GCS-backed remote state.
Import batches were validated with zero-diff plans. Apply operations, where present in
separate evidence branches, are documented in their specific evidence files.

| Document | Scope |
|---|---|
| [docs/terraform-iac-baseline-runbook.md](terraform-iac-baseline-runbook.md) | Strategy document: phased import approach |
| [docs/terraform-remote-backend-migration-evidence.md](terraform-remote-backend-migration-evidence.md) | GCS remote backend active, local state migrated |
| [docs/terraform-pubsub-scheduler-import-plan-evidence.md](terraform-pubsub-scheduler-import-plan-evidence.md) | Pub/Sub topics, push subscription, Cloud Scheduler imported |
| [docs/terraform-monitoring-import-plan-evidence.md](terraform-monitoring-import-plan-evidence.md) | Logs-based metrics, dashboard, alert policies imported |
| [docs/cloud-run-terraform-import-plan-evidence.md](cloud-run-terraform-import-plan-evidence.md) | rtdp-api, rtdp-pubsub-worker, rtdp-silver-refresh-job imported |
| [docs/cloud-sql-terraform-import-plan-evidence.md](cloud-sql-terraform-import-plan-evidence.md) | Cloud SQL rtdp-postgres imported, NEVER/STOPPED preserved |
| [docs/secret-manager-terraform-import-plan-evidence.md](secret-manager-terraform-import-plan-evidence.md) | Secret Manager rtdp-database-url metadata imported |
| [docs/service-accounts-terraform-import-plan-evidence.md](service-accounts-terraform-import-plan-evidence.md) | Custom RTDP service accounts imported |
| [docs/iam-members-terraform-import-plan-evidence.md](iam-members-terraform-import-plan-evidence.md) | Project and service-account IAM members imported |
| [docs/workload-identity-terraform-import-plan-evidence.md](workload-identity-terraform-import-plan-evidence.md) | GitHub Actions Workload Identity Pool and OIDC Provider imported |
| [docs/artifact-registry-terraform-import-plan-evidence.md](artifact-registry-terraform-import-plan-evidence.md) | Artifact Registry rtdp Docker repository imported |
| [docs/cloud-resource-manager-api-enablement-evidence.md](cloud-resource-manager-api-enablement-evidence.md) | cloudresourcemanager API enabled; Terraform Plan CI rerun green |
| [docs/api-deploy-ci-service-account-user-evidence.md](api-deploy-ci-service-account-user-evidence.md) | CI service account user binding for API deploy validated |

---

## CI/CD and Deployment Evidence

| Workflow | Trigger | Scope |
|---|---|---|
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | Push to main / PR | Lint (ruff), tests (pytest), import smoke test; dbt compile/run/test against ephemeral Postgres service container |
| [.github/workflows/terraform-plan.yml](../.github/workflows/terraform-plan.yml) | PR / push to main (infra path) | Terraform plan via Workload Identity; no apply |
| [.github/workflows/deploy-worker-cloud-run.yml](../.github/workflows/deploy-worker-cloud-run.yml) | workflow_dispatch (manual) | Builds and deploys worker image to Cloud Run |
| [.github/workflows/deploy-api-cloud-run.yml](../.github/workflows/deploy-api-cloud-run.yml) | workflow_dispatch (manual) | Builds and deploys API image to Cloud Run |
| [.github/workflows/deploy-dbt-refresh-cloud-run.yml](../.github/workflows/deploy-dbt-refresh-cloud-run.yml) | workflow_dispatch (manual) | Builds and pushes dbt refresh job image to Artifact Registry only — no Cloud Run mutation; Terraform owns `google_cloud_run_v2_job.rtdp_dbt_refresh_job`; deployment evidence pending |

Supporting evidence:

- [docs/cloud-run-worker-manual-deploy-evidence.md](cloud-run-worker-manual-deploy-evidence.md) -- validated worker manual deploy run
- [docs/api-deploy-ci-runbook.md](api-deploy-ci-runbook.md) -- API deploy CI runbook
- [docs/api-manual-deploy-evidence.md](api-manual-deploy-evidence.md) -- validated API manual deploy run

Neither deploy workflow triggers automatically on merge to main; both require explicit manual dispatch.

---

## Observability Evidence

| Document | What It Proves |
|---|---|
| [docs/cloud-observability-evidence.md](cloud-observability-evidence.md) | Cloud Logging structured logs across services and jobs |
| [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md) | Four logs-based metrics created and configured in Cloud Monitoring |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | timeSeries datapoints confirmed for worker and silver refresh success counters |
| [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) | Two alert policies enabled; email notification channel attached |
| [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md) | 4-panel RTDP Pipeline Overview dashboard created in GCP and exported to JSON |
| [docs/notification-channels-evidence.md](notification-channels-evidence.md) | Email notification channel created and attached to both alert policies |

---

## Load and Throughput Evidence

All load tests were bounded and deterministic. Cloud SQL was started only during each test
window and returned to `NEVER / STOPPED` on completion. This is bounded validation evidence,
not a claim of enterprise-scale throughput.

| Document | Scope |
|---|---|
| [docs/load-test-plan.md](load-test-plan.md) | Test plan: event sizes, acceptance criteria, safety protocol |
| [docs/load-test-local-sample-evidence.md](load-test-local-sample-evidence.md) | 100-event JSONL generated and validated locally before cloud publish |
| [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) | 100 events: 100 acks, 100 worker ok logs, metric sum=100, API readback confirmed |
| [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) | 1,000 events: all acceptance criteria met |
| [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) | 5,000 events: 5,000 acks, metric sum=4,963, DLQ empty, silver refresh succeeded |

---

## Reliability and Safety Evidence

| Document | What It Proves |
|---|---|
| [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) | Read-only inspection of production Pub/Sub retry and DLQ configuration before mutation |
| [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) | Production DLQ topic and deadLetterPolicy configured (maxDeliveryAttempts=5, 10s/60s backoff) |
| [docs/silver-refresh-scheduler-evidence.md](silver-refresh-scheduler-evidence.md) | Cloud Scheduler job configured and paused; service account and invoker role validated |
| [docs/silver-refresh-scheduler-execution-proof-evidence.md](silver-refresh-scheduler-execution-proof-evidence.md) | Scheduler dispatched silver refresh job; execution succeeded; success metric confirmed |
| [docs/silver-refresh-job-validation.md](silver-refresh-job-validation.md) | Cloud Run Job silver refresh execution validated |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | Production-light SLO targets, error budget definition, incident severity levels, and incident response runbooks for all RTDP components |
| [docs/gold-cloud-sql-deployment-evidence.md](gold-cloud-sql-deployment-evidence.md) | Cloud SQL deployment evidence for gold daily aggregates: SQL applied, refresh returned 7 rows, API /aggregates/daily returned HTTP 200, Cloud SQL returned to NEVER / STOPPED |
| [docs/gold-cloud-sql-deployment-runbook.md](gold-cloud-sql-deployment-runbook.md) | Controlled runbook used to deploy the gold daily aggregates layer to Cloud SQL |
| [docs/dbt-ci-validation-evidence.md](dbt-ci-validation-evidence.md) | dbt transformation layer (PR #104) and CI validation (PR #105): 22 dbt tests, 117 pytest, ruff clean; ephemeral pgvector container; no Cloud SQL mutation |
| [docs/dbt-cloud-sql-migration-runbook.md](dbt-cloud-sql-migration-runbook.md) | Controlled runbook used to validate dbt silver and gold models against Cloud SQL and reconcile output with the stored-function baseline. |

---

## Cost Control Evidence

Cost-control state is recorded throughout the evidence documents. The following practices
are verified across the evidence base:

- Cloud SQL (`rtdp-postgres`) is kept at activation policy `NEVER / STOPPED` and started only
  during bounded validation windows. This state is confirmed in every load test and Terraform
  import evidence document.
- Cloud Scheduler (`rtdp-silver-refresh-scheduler`) is kept `PAUSED` by default and resumed
  only during controlled execution proofs. Final state is confirmed as `PAUSED` in
  [docs/silver-refresh-scheduler-execution-proof-evidence.md](silver-refresh-scheduler-execution-proof-evidence.md).
- Terraform state uses a GCS-backed remote backend. No `terraform apply` was executed during
  import operations; all changes were import-only with verified zero-diff plans.

---

## Known Remaining Gaps

- Gold analytics layer: `gold.market_event_daily_aggregates` table and refresh function are implemented and cloud-validated. See [docs/gold-cloud-sql-deployment-evidence.md](gold-cloud-sql-deployment-evidence.md).
- dbt CI validation is implemented (`feat/dbt-ci-validation`). Cloud SQL automated run remains pending (governance plan section 10).
- Sustained throughput validation above 5,000 events is pending.
- BigQuery and Dataflow remain target architecture items; neither is implemented.
- A consolidated architecture review document beyond gcp-architecture.md has not been written.

| [docs/dbt-cloud-sql-validation-evidence.md](dbt-cloud-sql-validation-evidence.md) | Evidence that dbt compile/run/test succeeded against Cloud SQL, matched stored-function outputs, and API readback returned HTTP 200. |
| [docs/dbt-operational-migration-plan.md](dbt-operational-migration-plan.md) | Plan only — not executed. Phases, decision matrix (Option A/B/C), credential strategy, rollback paths, and acceptance criteria for migrating the Cloud Run Job from stored functions to dbt. |
| [apps/dbt-refresh-job/](../apps/dbt-refresh-job/) | Local dbt refresh runtime package (`rtdp-dbt-refresh-job` CLI): parses `DATABASE_URL` secret to derive dbt connection fields; explicit `DBT_POSTGRES_*` vars override; `DBT_POSTGRES_HOST` override used for Cloud SQL Unix socket; structured JSON logs; profiles.yml deleted after each run. Not deployed — Cloud Run Job credential contract resolved; controlled deployment validation pending. |
| [docs/dbt-refresh-cloud-run-job-plan.md](dbt-refresh-cloud-run-job-plan.md) | Terraform resource definition (`google_cloud_run_v2_job.rtdp_dbt_refresh_job`) as source of truth; image build/push workflow only — no Cloud Run mutation. Credential contract resolved: `DATABASE_URL` secret from `rtdp-database-url`; `DBT_POSTGRES_PASSWORD` secret removed. Scheduler still targets `rtdp-silver-refresh-job`. Cloud SQL still NEVER / STOPPED. Terraform apply/deployment evidence pending a future controlled branch. |
