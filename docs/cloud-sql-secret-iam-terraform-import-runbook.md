# Cloud SQL, Secret Manager, and IAM Terraform Import Runbook

## 1. Status

> **RUNBOOK ONLY — NOT EXECUTED**

| Item | State |
| --- | --- |
| Cloud SQL imported | No |
| Secret Manager imported | No |
| IAM bindings imported | No |
| Terraform HCL created | No |
| `terraform import` executed | No |
| `terraform apply` executed | No |
| Cloud SQL started | No |
| Scheduler run | No |
| Secret values exposed | No |

This document defines the safety-first plan for importing the remaining high-risk GCP resources into Terraform after Pub/Sub, Scheduler, Monitoring, Cloud Run, GCS remote backend, and Terraform Plan CI have been validated.

---

## 2. Purpose

Bring the remaining infrastructure dependencies under Terraform state management without changing runtime behavior, exposing secret values, starting Cloud SQL, weakening IAM, or mutating live services.

This phase is higher-risk than Pub/Sub, Scheduler, Monitoring, and Cloud Run imports because it includes:

- Cloud SQL instance configuration;
- Secret Manager metadata and secret version handling;
- service account IAM bindings;
- project-level IAM bindings;
- runtime permissions used by Cloud Run, Cloud Scheduler, Pub/Sub push, and Terraform Plan CI.

No execution should occur until this runbook is reviewed and accepted.

---

## 3. Current Terraform State Baseline

The current Terraform state already includes:

```text
google_cloud_run_v2_job.rtdp_silver_refresh_job
google_cloud_run_v2_service.rtdp_api
google_cloud_run_v2_service.rtdp_pubsub_worker
google_cloud_scheduler_job.silver_refresh_scheduler
google_logging_metric.silver_refresh_error_count
google_logging_metric.silver_refresh_success_count
google_logging_metric.worker_message_error_count
google_logging_metric.worker_message_processed_count
google_monitoring_alert_policy.silver_refresh_error
google_monitoring_alert_policy.worker_error
google_monitoring_dashboard.rtdp_pipeline_overview
google_pubsub_subscription.market_events_raw_worker_push
google_pubsub_topic.market_events_raw
google_pubsub_topic.market_events_raw_dlq
```

The state is GCS-backed and Terraform Plan CI is already active.

---

## 4. Current Cloud SQL Inventory

Project:

```text
project-42987e01-2123-446b-ac7
```

Cloud SQL instance:

| Field | Value |
| --- | --- |
| Name | `rtdp-postgres` |
| Region | `europe-west1` |
| Database version | `POSTGRES_16` |
| Tier | `db-custom-1-3840` |
| Availability type | `ZONAL` |
| Backup enabled | `false` |
| Activation policy | `NEVER` |
| State | `STOPPED` |
| Public IPv4 | `true` |
| Authorized network | `37.189.31.189/32` |
| SSL mode | `ALLOW_UNENCRYPTED_AND_ENCRYPTED` |
| Server CA mode | `GOOGLE_MANAGED_INTERNAL_CA` |

Cloud SQL is intentionally stopped for cost control. Import work must preserve `activationPolicy = NEVER` and must not start the instance.

---

## 5. Current Secret Manager Inventory

| Secret | Created | Replication |
| --- | --- | --- |
| `rtdp-database-url` | `2026-05-03T21:23:45` | automatic |

The secret value must never be read into documentation, Terraform files, plan artifacts, CI logs, or PR output.

Only secret metadata should be considered for Terraform import. Secret versions are high-risk because they may expose or manage sensitive values and should remain out of scope unless a separate secret rotation strategy is approved.

---

## 6. Current Service Accounts Inventory

| Service account | Display name | Purpose |
| --- | --- | --- |
| `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | RTDP Cloud Scheduler caller for silver refresh job | Invokes Cloud Run job through Scheduler |
| `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | RTDP PubSub Worker | Runtime identity for worker and silver refresh job |
| `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | RTDP PubSub Push Invoker | Pub/Sub push invocation identity |
| `rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | RTDP Terraform Plan CI | GitHub Actions Terraform plan identity |
| `892892382088-compute@developer.gserviceaccount.com` | Default compute service account | Current runtime identity for `rtdp-api` |

---

## 7. Current Relevant IAM Bindings

Observed project-level IAM bindings relevant to the platform:

| Role | Member |
| --- | --- |
| `roles/artifactregistry.writer` | `serviceAccount:892892382088-compute@developer.gserviceaccount.com` |
| `roles/cloudsql.client` | `serviceAccount:892892382088-compute@developer.gserviceaccount.com` |
| `roles/cloudsql.client` | `serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| `roles/logging.logWriter` | `serviceAccount:892892382088-compute@developer.gserviceaccount.com` |
| `roles/run.invoker` | `serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| `roles/storage.objectViewer` | `serviceAccount:892892382088-compute@developer.gserviceaccount.com` |
| `roles/viewer` | `serviceAccount:rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |

Terraform Plan CI also uses Workload Identity Federation and bucket-level state permissions. Those were configured earlier and should not be modified in this branch unless a dedicated IAM evidence branch is created.

---

## 8. Risk Classification

| Risk | Why it matters | Control |
| --- | --- | --- |
| Cloud SQL starts unexpectedly | Cost and runtime mutation risk | Preserve `activationPolicy = NEVER`; stop if any plan changes activation policy |
| Cloud SQL replacement | Data loss or outage risk | Stop if plan proposes replacement or recreation |
| Public IP / authorized network drift | Network access can break or become too permissive | Preserve current IP configuration exactly during import |
| Secret value exposure | `DATABASE_URL` is sensitive | Do not read secret payload; do not manage secret versions in this phase |
| IAM authoritative overwrite | Project IAM can remove unrelated bindings if wrong resource type is used | Prefer member-level resources, not authoritative policy resources |
| Runtime permission loss | Cloud Run, Scheduler, Pub/Sub, and SQL access can break | Import one IAM binding at a time and run plan after each |
| CI permission expansion | Plan CI should not become apply-capable | Do not grant Owner/Editor; keep plan-only posture |
| Terraform apply risk | Could mutate live GCP resources | No `terraform apply` in import branch |

---

## 9. Recommended Terraform File Layout

Candidate files for a future execution branch:

```text
infra/terraform/gcp/cloud_sql.tf
infra/terraform/gcp/secrets.tf
infra/terraform/gcp/iam.tf
```

Do not mix Cloud SQL, Secret Manager, and IAM into existing Pub/Sub, Scheduler, Monitoring, or Cloud Run files.

---

## 10. Candidate Terraform Resources

Candidate Cloud SQL resource:

```text
google_sql_database_instance.rtdp_postgres
```

Candidate Secret Manager metadata resource:

```text
google_secret_manager_secret.rtdp_database_url
```

Candidate service account resources:

```text
google_service_account.rtdp_scheduler_sa
google_service_account.rtdp_worker_sa
google_service_account.rtdp_pubsub_push_sa
google_service_account.rtdp_terraform_plan_ci
```

The default compute service account should not be created as a normal `google_service_account` resource. It is Google-managed and should be referenced, not recreated.

Candidate IAM member resources:

```text
google_project_iam_member.compute_artifactregistry_writer
google_project_iam_member.compute_cloudsql_client
google_project_iam_member.worker_cloudsql_client
google_project_iam_member.compute_logging_log_writer
google_project_iam_member.scheduler_run_invoker
google_project_iam_member.compute_storage_object_viewer
google_project_iam_member.terraform_plan_ci_viewer
```

Use member-level IAM resources to avoid replacing the full project IAM policy.

---

## 11. Candidate Import IDs

### Cloud SQL

```bash
terraform -chdir=infra/terraform/gcp import \
  google_sql_database_instance.rtdp_postgres \
  project-42987e01-2123-446b-ac7/rtdp-postgres
```

### Secret Manager metadata

```bash
terraform -chdir=infra/terraform/gcp import \
  google_secret_manager_secret.rtdp_database_url \
  projects/project-42987e01-2123-446b-ac7/secrets/rtdp-database-url
```

### Service accounts

```bash
terraform -chdir=infra/terraform/gcp import \
  google_service_account.rtdp_scheduler_sa \
  projects/project-42987e01-2123-446b-ac7/serviceAccounts/rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

```bash
terraform -chdir=infra/terraform/gcp import \
  google_service_account.rtdp_worker_sa \
  projects/project-42987e01-2123-446b-ac7/serviceAccounts/rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

```bash
terraform -chdir=infra/terraform/gcp import \
  google_service_account.rtdp_pubsub_push_sa \
  projects/project-42987e01-2123-446b-ac7/serviceAccounts/rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

```bash
terraform -chdir=infra/terraform/gcp import \
  google_service_account.rtdp_terraform_plan_ci \
  projects/project-42987e01-2123-446b-ac7/serviceAccounts/rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

### Project IAM members

Use the import format:

```text
PROJECT_ID roles/ROLE MEMBER
```

Example:

```bash
terraform -chdir=infra/terraform/gcp import \
  google_project_iam_member.worker_cloudsql_client \
  "project-42987e01-2123-446b-ac7 roles/cloudsql.client serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
```

Do not run any of these imports in this documentation branch.

---

## 12. Required Preflight Before Future Import

Before any execution branch:

```bash
git status --short --branch
terraform -chdir=infra/terraform/gcp state list
terraform -chdir=infra/terraform/gcp plan
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="yaml(name,region,databaseVersion,state,settings.activationPolicy,settings.tier,settings.availabilityType,settings.backupConfiguration.enabled,settings.ipConfiguration)"
gcloud secrets list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,createTime,replication.automatic)"
gcloud iam service-accounts list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(email,displayName)"
gcloud projects get-iam-policy project-42987e01-2123-446b-ac7 --format=json
```

Required preflight result:

```text
Terraform plan: No changes
Cloud SQL: NEVER STOPPED
Git: clean except expected docs/HCL changes
No secret payload values printed
```

---

## 13. HCL Authoring Rules

Future HCL must follow these rules:

1. Preserve Cloud SQL name `rtdp-postgres`.
2. Preserve Cloud SQL `POSTGRES_16`.
3. Preserve Cloud SQL region `europe-west1`.
4. Preserve Cloud SQL tier `db-custom-1-3840` unless a separate resizing branch is approved.
5. Preserve `activationPolicy = NEVER`.
6. Preserve Cloud SQL `ZONAL` availability.
7. Preserve backups disabled unless a separate backup policy branch is approved.
8. Preserve current IP configuration during first import.
9. Do not read, export, print, or commit secret values.
10. Import Secret Manager metadata only; do not manage secret versions in this phase.
11. Use IAM member resources, not authoritative project IAM policy resources.
12. Do not create, delete, or replace service accounts.
13. Do not import default compute service account as a created resource.
14. Do not run `terraform apply`.

---

## 14. Recommended Execution Order

Future execution should be split into smaller branches, not one large import.

Recommended order:

1. `docs/cloud-sql-secret-iam-terraform-import-runbook` — this runbook only.
2. `exec/cloud-sql-terraform-import-plan` — Cloud SQL HCL + import + zero-diff evidence.
3. `exec/secret-manager-terraform-import-plan` — Secret Manager metadata HCL + import + zero-diff evidence.
4. `exec/service-accounts-terraform-import-plan` — custom service account HCL + import + zero-diff evidence.
5. `exec/iam-members-terraform-import-plan` — member-level IAM imports one binding at a time.

Cloud SQL should be imported before Secret Manager and IAM because Cloud Run connectivity already depends on the Cloud SQL instance reference.

---

## 15. Stop Conditions

Stop immediately if any plan proposes:

- starting Cloud SQL;
- changing `activationPolicy` away from `NEVER`;
- replacing or deleting the Cloud SQL instance;
- changing database version;
- changing tier;
- changing IP access unexpectedly;
- enabling or disabling backups unexpectedly;
- exposing a secret value;
- creating a new secret version;
- deleting or replacing a service account;
- removing an IAM binding;
- replacing the full project IAM policy;
- granting broad roles such as Owner or Editor;
- changing Terraform Plan CI into an apply-capable identity;
- running Scheduler;
- executing Cloud Run jobs;
- running `terraform apply`.

---

## 16. Explicit Non-Actions

This branch does not perform:

- No `terraform import`
- No `terraform apply`
- No Cloud SQL import
- No Cloud SQL start
- No Secret Manager import
- No secret value read
- No secret version management
- No service account import
- No IAM import
- No IAM policy update
- No Scheduler run
- No Cloud Run Job execution
- No Pub/Sub publishing
- No application code changes
- No test changes

---

## 17. Acceptance Criteria for This Runbook

This documentation branch is accepted if:

- the runbook records current Cloud SQL inventory;
- the runbook records current Secret Manager metadata inventory;
- the runbook records relevant service accounts;
- the runbook records relevant IAM bindings;
- the runbook defines candidate Terraform resources;
- the runbook defines candidate import IDs;
- the runbook defines stop conditions;
- README links to this runbook;
- local validation remains green;
- no live GCP resources are modified.

---

## 18. Recommended Next Branch

After this runbook is merged, the next branch should be:

```text
exec/cloud-sql-terraform-import-plan
```

That future branch may add Cloud SQL HCL and import `google_sql_database_instance.rtdp_postgres`, stopping unless the final plan is zero-diff and Cloud SQL remains `NEVER STOPPED`.
