# GCP Terraform Infrastructure — Real-Time Data Platform

## Current Status

This directory contains an implemented IaC baseline for the RTDP GCP infrastructure.
Resources were adopted from previously created cloud resources via `terraform import`,
validated with zero-diff `terraform plan` output, and backed by a GCS remote state bucket.

| Item | State |
|---|---|
| Terraform files created | Yes |
| GCS remote backend configured | Yes (`versions.tf` — `rtdp-terraform-state-*`) |
| `terraform import` executed | Yes — all resource areas below |
| Zero-diff `terraform plan` verified | Yes — documented in evidence files |
| `terraform apply` executed | Selective — BigQuery, IAM grants, Pub/Sub alert policies, Dataflow prerequisites only |
| Live GCP state verified in this branch | No — this branch is docs-only |
| Cloud SQL current state | `NEVER / STOPPED` |
| Scheduler jobs current state | `PAUSED` |

This README update does not execute Terraform, does not run any GCP commands, and does
not verify current live GCP state. It corrects stale skeleton-state language. Evidence
for all import and apply operations is in `docs/` (see Evidence References below).

---

## What Terraform Covers

| Area | File(s) | Purpose | Evidence / Notes |
|---|---|---|---|
| Provider / backend | `versions.tf`, `providers.tf` | GCS-backed remote state; google provider ~> 6.0 | Backend active; evidence in terraform-remote-backend-migration-evidence.md |
| Input variables | `variables.tf` | `project_id`, `region`, `environment`, OIDC SA email | Confirmed by Phase 0 inventory |
| Shared locals | `locals.tf` | Stable resource names and URLs across files | Used by multiple resource files |
| Pub/Sub | `pubsub.tf` | `market-events-raw` topic, DLQ topic, push subscription with OIDC and dead-letter policy | Imported; zero-diff plan; evidence in terraform-pubsub-scheduler-import-plan-evidence.md |
| Cloud Scheduler | `scheduler.tf` | `rtdp-silver-refresh-scheduler` (PAUSED) targeting `rtdp-dbt-refresh-job:run` | Imported; zero-diff plan; scheduler PAUSED by default |
| Cloud Run services | `cloud_run_services.tf` | `rtdp-api` and `rtdp-pubsub-worker` Cloud Run services | Imported; zero-diff plan; evidence in cloud-run-terraform-import-plan-evidence.md |
| Cloud Run jobs | `cloud_run_jobs.tf` | `rtdp-silver-refresh-job`, `rtdp-dbt-refresh-job`, `rtdp-bigquery-append-job` | Imported or applied; evidence in cloud-run-terraform-import-plan-evidence.md and dbt-refresh-cloud-run-deploy-evidence.md |
| Cloud SQL | `cloud_sql.tf` | `rtdp-postgres` Cloud SQL PostgreSQL instance | Imported; zero-diff plan; `NEVER / STOPPED`; evidence in cloud-sql-terraform-import-plan-evidence.md |
| BigQuery | `bigquery.tf` | Dataset `rtdp_analytics`, tables `market_events_raw` / `market_events_raw_staging` / `market_event_minute_aggregates` / `market_event_daily_aggregates`, IAM bindings | Applied via Terraform; evidence in bigquery-terraform-apply-evidence.md |
| Monitoring | `monitoring.tf` | Logs-based metrics (worker processed/error, silver success/error), dashboard, alert policies (worker error, silver error, BigQuery quality failure, Pub/Sub backlog, DLQ count) | Imported (metrics, dashboard, initial alert policies); additional alert policies applied; evidence in terraform-monitoring-import-plan-evidence.md and pubsub-backlog-dlq-alert-policies-evidence.md |
| IAM | `iam.tf` | Project and service-account IAM members; scoped Cloud Run job invoker bindings; `roles/monitoring.metricWriter` for worker SA | Imported and applied; evidence in iam-members-terraform-import-plan-evidence.md, scheduler-job-invoker-iam-hardening-evidence.md, dbt-metrics-runtime-monitoring-iam-evidence.md |
| Service accounts | `service_accounts.tf` | Custom RTDP service accounts | Imported; zero-diff plan; evidence in service-accounts-terraform-import-plan-evidence.md |
| Secrets | `secrets.tf` | Secret Manager `rtdp-database-url` metadata (not secret value) | Imported; zero-diff plan; evidence in secret-manager-terraform-import-plan-evidence.md |
| Artifact Registry | `artifact_registry.tf` | `rtdp` Docker repository | Imported; zero-diff plan; evidence in artifact-registry-terraform-import-plan-evidence.md |
| Workload Identity | `workload_identity.tf` | GitHub Actions OIDC Workload Identity Pool and Provider | Imported; zero-diff plan; evidence in workload-identity-terraform-import-plan-evidence.md |
| Dataflow prerequisites | `dataflow.tf` | Proof-only topic/subscription, GCS staging bucket, BigQuery proof table, `rtdp-dataflow-sa` service account, IAM bindings | Applied; evidence in dataflow-bounded-proof-prereqs-evidence.md |
| Schemas | `schemas/` | JSON table schemas for BigQuery resources | Used by `bigquery.tf` at plan time |

---

## Operational Safety Rules

These rules apply to all execution branches touching this Terraform layer:

- **No blind apply.** Always run `terraform plan` first. Any plan showing a destroy or
  replacement is a hard stop. Do not proceed without reviewing the diff.
- **Cloud SQL stays stopped.** `rtdp-postgres` must remain at activation policy
  `NEVER / STOPPED` except during a bounded, time-limited validation window. Return it
  to `NEVER / STOPPED` before closing the window.
- **Schedulers stay paused.** `rtdp-silver-refresh-scheduler` and `rtdp-bigquery-append-scheduler`
  must remain `PAUSED` by default. Resume only during an explicitly scoped proof run;
  re-pause on completion.
- **Secrets from Secret Manager or env vars only.** No credentials, connection strings,
  or API keys committed to the repository. `terraform.tfstate` and `.terraform/`
  local working directories are gitignored and must never be committed.
  Keep `.terraform.lock.hcl` versioned to pin Terraform provider versions.
- **Import before apply for existing resources.** Any new resource that already exists
  in GCP must be imported and validated with a zero-diff plan before applying.
- **Execution branches only.** Run `terraform init`, `terraform import`, and
  `terraform apply` on dedicated execution branches, never directly on `main`.
- **Plan CI is read-only.** The `terraform-plan.yml` workflow runs `terraform plan`
  only. It does not apply and does not modify live resources.

---

## Evidence References

All import, apply, and validation evidence is indexed in `docs/EVIDENCE_INDEX.md`.
Key documents for this Terraform layer:

| Document | What It Covers |
|---|---|
| [docs/EVIDENCE_INDEX.md](../../../docs/EVIDENCE_INDEX.md) | Full indexed map of all project evidence |
| [docs/terraform-iac-baseline-runbook.md](../../../docs/terraform-iac-baseline-runbook.md) | Phased IaC adoption strategy, safety constraints, and stop conditions |
| [docs/terraform-remote-backend-migration-evidence.md](../../../docs/terraform-remote-backend-migration-evidence.md) | GCS remote backend active; local state migrated |
| [docs/terraform-pubsub-scheduler-import-plan-evidence.md](../../../docs/terraform-pubsub-scheduler-import-plan-evidence.md) | Pub/Sub topics, push subscription, Cloud Scheduler imported; zero-diff plan |
| [docs/terraform-monitoring-import-plan-evidence.md](../../../docs/terraform-monitoring-import-plan-evidence.md) | Logs-based metrics, dashboard, alert policies imported; zero-diff plan |
| [docs/terraform-monitoring-import-runbook.md](../../../docs/terraform-monitoring-import-runbook.md) | Monitoring import runbook and step-by-step safety procedure |
| [docs/cloud-run-terraform-import-plan-evidence.md](../../../docs/cloud-run-terraform-import-plan-evidence.md) | Cloud Run services and jobs imported; zero-diff plan |
| [docs/cloud-sql-terraform-import-plan-evidence.md](../../../docs/cloud-sql-terraform-import-plan-evidence.md) | Cloud SQL imported; `NEVER / STOPPED` preserved |
| [docs/bigquery-terraform-apply-evidence.md](../../../docs/bigquery-terraform-apply-evidence.md) | BigQuery dataset, tables, IAM applied via Terraform; zero-diff post-apply |
| [docs/iam-members-terraform-import-plan-evidence.md](../../../docs/iam-members-terraform-import-plan-evidence.md) | IAM bindings imported; zero-diff plan |
| [docs/workload-identity-terraform-import-plan-evidence.md](../../../docs/workload-identity-terraform-import-plan-evidence.md) | GitHub Actions Workload Identity imported; zero-diff plan |
| [docs/artifact-registry-terraform-import-plan-evidence.md](../../../docs/artifact-registry-terraform-import-plan-evidence.md) | Artifact Registry imported; zero-diff plan |
| [docs/pubsub-backlog-dlq-alert-policies-evidence.md](../../../docs/pubsub-backlog-dlq-alert-policies-evidence.md) | Pub/Sub backlog and DLQ alert policies applied; post-apply zero-diff plan |
| [docs/scheduler-job-invoker-iam-hardening-evidence.md](../../../docs/scheduler-job-invoker-iam-hardening-evidence.md) | Scoped Cloud Run job invoker IAM bindings applied |
| [docs/dataflow-bounded-proof-prereqs-evidence.md](../../../docs/dataflow-bounded-proof-prereqs-evidence.md) | Dataflow proof prerequisites applied via Terraform |
| [docs/gcp-architecture.md](../../../docs/gcp-architecture.md) | GCP service mapping: local components to GCP targets |

---

## Not Claimed By This README

- This README update does not prove current live GCP state.
- This branch (`docs/rtdp-infra-readme-current-state`) does not run `terraform init`,
  `terraform plan`, `terraform apply`, or `terraform import`.
- This branch does not issue any `gcloud` commands.
- This branch does not deploy or mutate any GCP resources.
- Live GCP resource state (Cloud Run revision health, Cloud SQL row counts, Pub/Sub
  message counts, alert policy trigger state) is not verified here.
- The `monitoring.tf` file retains a stale `# SKELETON ONLY` comment in its header;
  that comment predates the completed import and applies are documented in the
  monitoring evidence files. The `.tf` file is not edited in this branch.
