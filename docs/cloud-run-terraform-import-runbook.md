# Cloud Run Terraform Import Runbook

## 1. Status

> **RUNBOOK ONLY — NOT EXECUTED**

| Item | State |
| --- | --- |
| Cloud Run services imported | No |
| Cloud Run jobs imported | No |
| `cloud_run_services.tf` created | No |
| `cloud_run_jobs.tf` created | No |
| `terraform import` executed | No |
| `terraform apply` executed | No |
| Live Cloud Run resources modified | No |

This document defines the safety-first plan for importing existing Cloud Run services and jobs into Terraform after the Pub/Sub, Scheduler, Monitoring, GCS backend, and Terraform Plan CI layers have been validated.

---

## 2. Purpose

Bring existing Cloud Run runtime resources under Terraform state management without replacing revisions, changing traffic, restarting services, leaking secrets, or mutating production behavior.

Cloud Run is treated as high-risk for Terraform import because the live resources include:

- container image references;
- revision templates;
- service accounts;
- environment variables;
- Cloud SQL annotations;
- autoscaling annotations;
- traffic routing;
- job retry and timeout settings.

Any mismatch between live configuration and HCL can produce a Terraform plan that attempts to update the running service or job.

---

## 3. Current Cloud Run Inventory

Project:

```text
project-42987e01-2123-446b-ac7
```

Region:

```text
europe-west1
```

### Cloud Run services

| Service | URL | Service account |
| --- | --- | --- |
| `rtdp-api` | `https://rtdp-api-fpy4of3i5a-ew.a.run.app` | `892892382088-compute@developer.gserviceaccount.com` |
| `rtdp-pubsub-worker` | `https://rtdp-pubsub-worker-fpy4of3i5a-ew.a.run.app` | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |

### Cloud Run jobs

| Job | Created |
| --- | --- |
| `rtdp-silver-refresh-job` | `2026-05-05T05:59:18.234811Z` |

---

## 4. Runtime Configuration Snapshot

### `rtdp-api`

| Field | Value |
| --- | --- |
| Image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/cloud-run-source-deploy/rtdp-api@sha256:0b44c36a71b305653dfe85a74d98075ae238bf19458917412d95a3a29515af78` |
| Port | `8080` / `http1` |
| Service account | `892892382088-compute@developer.gserviceaccount.com` |
| Env names | `DATABASE_URL`, `ENVIRONMENT`, `SERVICE_NAME`, `SERVICE_VERSION` |
| Secret reference | `DATABASE_URL` from `rtdp-database-url`, key `latest` |
| `SERVICE_NAME` | `rtdp-api` |
| `SERVICE_VERSION` | `0.1.0-pagination-fix` |
| `ENVIRONMENT` | `gcp-cloud-run` |
| CPU | `1` |
| Memory | `512Mi` |
| Container concurrency | `80` |
| Timeout | `300` seconds |
| Max scale | `20` |
| Cloud SQL instance | `project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres` |
| Startup CPU boost | `true` |
| Ingress | `all` |
| Traffic | `100%` to latest revision |
| Latest ready revision | `rtdp-api-00006-gd8` |

### `rtdp-pubsub-worker`

| Field | Value |
| --- | --- |
| Image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest` |
| Port | `8080` / `http1` |
| Service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Env names | `DATABASE_URL` |
| Secret reference | `DATABASE_URL` from `rtdp-database-url`, key `latest` |
| CPU | `1000m` |
| Memory | `512Mi` |
| Container concurrency | `1` |
| Timeout | `60` seconds |
| Max scale | `1` |
| Cloud SQL instance | `project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres` |
| Startup CPU boost | `true` |
| Ingress | `all` |
| Traffic | `100%` to latest revision |
| Latest ready revision | `rtdp-pubsub-worker-00003-dh6` |

### `rtdp-silver-refresh-job`

| Field | Value |
| --- | --- |
| Image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest` |
| Service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Env names | `DATABASE_URL` |
| Secret reference | `DATABASE_URL` from `rtdp-database-url`, key `latest` |
| CPU | `1000m` |
| Memory | `512Mi` |
| Task count | `1` |
| Max retries | `0` |
| Timeout | `300` seconds |
| Cloud SQL instance | `project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres` |
| Execution environment | `gen2` |
| Latest execution status | `EXECUTION_SUCCEEDED` |
| Latest execution | `rtdp-silver-refresh-job-z676s` |

---

## 5. Risk Classification

| Risk | Why it matters | Control |
| --- | --- | --- |
| Image drift | Service images may use digest or `:latest`; Terraform can force revision updates if HCL differs | Capture live image exactly; use `ignore_changes` if the deployment pipeline owns images |
| Secret/env drift | `DATABASE_URL` must not leak into HCL, plan logs, or state | Use Secret Manager references only; never hardcode secret values |
| Revision template drift | Cloud Run creates new revisions when template fields change | Import first, plan second, apply never until zero-diff |
| Traffic drift | Wrong traffic block can shift traffic | Preserve `100%` latest revision behavior or ignore traffic if managed externally |
| Cloud SQL annotation drift | Missing annotation can break database connectivity | Preserve `run.googleapis.com/cloudsql-instances` exactly |
| Service account drift | Incorrect service account can break Cloud SQL, Pub/Sub, or invocation | Preserve current service accounts |
| Autoscaling drift | `maxScale` controls cost and worker concurrency | Preserve `maxScale=20` for API and `maxScale=1` for worker |
| Job execution drift | Job retry/timeout changes affect scheduled refresh behavior | Preserve `maxRetries=0` and `timeout=300` |
| Apply risk | Terraform can mutate live runtime resources | This phase is runbook-only; import branch must stop unless plan is zero-diff |

---

## 6. Recommended Terraform File Layout

Candidate files for a future execution branch:

```text
infra/terraform/gcp/cloud_run_services.tf
infra/terraform/gcp/cloud_run_jobs.tf
```

Do not combine Cloud Run service/job resources into existing Pub/Sub, Scheduler, or Monitoring files.

---

## 7. Candidate Terraform Resources

Use Cloud Run v2 resources:

```text
google_cloud_run_v2_service.rtdp_api
google_cloud_run_v2_service.rtdp_pubsub_worker
google_cloud_run_v2_job.rtdp_silver_refresh_job
```

Cloud Run v2 is preferred because it maps more directly to current Cloud Run service/job APIs.

---

## 8. Import IDs

Candidate import commands for a future execution branch:

```bash
terraform -chdir=infra/terraform/gcp import \
  google_cloud_run_v2_service.rtdp_api \
  projects/project-42987e01-2123-446b-ac7/locations/europe-west1/services/rtdp-api
```

```bash
terraform -chdir=infra/terraform/gcp import \
  google_cloud_run_v2_service.rtdp_pubsub_worker \
  projects/project-42987e01-2123-446b-ac7/locations/europe-west1/services/rtdp-pubsub-worker
```

```bash
terraform -chdir=infra/terraform/gcp import \
  google_cloud_run_v2_job.rtdp_silver_refresh_job \
  projects/project-42987e01-2123-446b-ac7/locations/europe-west1/jobs/rtdp-silver-refresh-job
```

Do not run these commands in this documentation branch.

---

## 9. Required Preflight Before Future Import

Before any Cloud Run import execution branch:

```bash
git status --short --branch
terraform -chdir=infra/terraform/gcp state list
terraform -chdir=infra/terraform/gcp plan
gcloud run services describe rtdp-api --project=project-42987e01-2123-446b-ac7 --region=europe-west1 --format=json
gcloud run services describe rtdp-pubsub-worker --project=project-42987e01-2123-446b-ac7 --region=europe-west1 --format=json
gcloud run jobs describe rtdp-silver-refresh-job --project=project-42987e01-2123-446b-ac7 --region=europe-west1 --format=json
gcloud sql instances describe rtdp-postgres --project=project-42987e01-2123-446b-ac7 --format="value(settings.activationPolicy,state)"
```

Required preflight result:

```text
Terraform plan: No changes
Cloud SQL: NEVER STOPPED
Git: clean except expected HCL/doc changes
```

---

## 10. HCL Authoring Rules

Future HCL must follow these rules:

1. Preserve exact resource names.
2. Preserve current region `europe-west1`.
3. Preserve current service accounts.
4. Preserve Cloud SQL annotation exactly.
5. Preserve memory and CPU limits.
6. Preserve API max scale `20`.
7. Preserve worker max scale `1`.
8. Preserve job `maxRetries=0`.
9. Preserve job timeout `300`.
10. Do not hardcode secret values.
11. Do not introduce new traffic behavior.
12. Do not execute `terraform apply`.

---

## 11. Recommended Lifecycle Ignore Strategy

Future HCL should explicitly decide which fields Terraform owns and which fields remain deployment-pipeline owned.

Recommended default for first import attempt:

- Terraform owns resource identity, region, service account, Cloud SQL connectivity, scaling limits, resource limits, timeout, secret reference shape, and job retry policy.
- Deployment pipeline may continue to own image rollouts.
- Consider `lifecycle.ignore_changes` for image fields if `:latest` or source deploy workflows are expected to change outside Terraform.
- Do not use broad `ignore_changes = all`; it defeats the purpose of IaC drift detection.

Any ignored field must be documented in the future import evidence file.

---

## 12. Expected Future Execution Flow

1. Create a new execution branch.
2. Add Cloud Run HCL skeleton matching live resources.
3. Run `terraform fmt` and `terraform validate`.
4. Import one resource at a time.
5. Run `terraform plan` after each import.
6. Resolve any drift only in HCL.
7. Stop immediately if Terraform proposes replacement, deletion, traffic change, revision template mutation, or secret exposure.
8. Accept only when final plan returns zero diff.
9. Create evidence document.
10. Open PR and require Terraform Plan CI to pass.

---

## 13. Stop Conditions

Stop immediately if any plan proposes:

- deleting or replacing a Cloud Run service;
- deleting or replacing a Cloud Run job;
- creating a new Cloud Run revision unexpectedly;
- changing traffic split;
- removing Cloud SQL connectivity;
- changing service account;
- exposing `DATABASE_URL` or secret values;
- increasing worker max scale above `1`;
- changing job retry or timeout behavior;
- starting Cloud SQL;
- running the Scheduler;
- executing the silver refresh job;
- running `terraform apply`.

---

## 14. Explicit Non-Actions

This branch does not perform:

- No `terraform import`
- No `terraform apply`
- No Cloud Run service import
- No Cloud Run job import
- No Cloud Run deployment
- No Cloud SQL import
- No IAM import
- No Secret Manager import
- No Scheduler run
- No Cloud Run Job execution
- No Pub/Sub publishing
- No application code changes
- No test changes

---

## 15. Acceptance Criteria for This Runbook

This documentation branch is accepted if:

- the runbook records the current Cloud Run services and job inventory;
- the runbook defines import IDs;
- the runbook identifies high-risk drift areas;
- the runbook defines stop conditions;
- README links to this runbook;
- local validation remains green;
- no live Cloud Run resources are modified.

---

## 16. Recommended Next Branch

After this runbook is merged, the next branch should be:

```text
exec/cloud-run-terraform-import-plan
```

That future branch may create Cloud Run HCL and execute imports one resource at a time, with plan checks after each import.
