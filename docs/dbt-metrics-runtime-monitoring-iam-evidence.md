# dbt Metrics Runtime Monitoring IAM Evidence

**Branch:** `infra/dbt-metrics-runtime-monitoring-iam`
**Date:** 2026-05-23
**Change type:** Terraform IAM grant — 1 resource add

---

## Purpose

Add `roles/monitoring.metricWriter` to the `rtdp-worker-sa` service account so that the
`rtdp-dbt-refresh-job` Cloud Run Job can write custom metrics to Cloud Monitoring once
`DBT_METRICS_DRY_RUN=false` is enabled in a future branch.

This is the implementation of the recommendation from the read-only audit in
`docs/dbt-metrics-runtime-monitoring-iam-audit.md` (PR #207).

No Cloud Run jobs were executed. No scheduler was activated. `DBT_METRICS_DRY_RUN=false`
was not enabled. Live dbt metric writes are still not proven in this branch.

---

## Terraform Resource Added

**File:** `infra/terraform/gcp/iam.tf`

```hcl
resource "google_project_iam_member" "worker_monitoring_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = local.rtdp_worker_service_account
}
```

`local.rtdp_worker_service_account` resolves to:

```text
serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

This local was already defined in `iam.tf:3` and used by `worker_cloudsql_client`. No new
locals, variables, modules, Python code, Dockerfiles, workflows, or Cloud Run env vars were
introduced.

---

## Pre-Apply Validation

### terraform fmt -check

```shell
terraform fmt -check -recursive infra/terraform/gcp
FMT_EXIT=0
```

### terraform validate

```shell
terraform -chdir=infra/terraform/gcp validate
Success! The configuration is valid.
VALIDATE_EXIT=0
```

### terraform plan (pre-apply)

```shell
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false

Terraform will perform the following actions:

  # google_project_iam_member.worker_monitoring_metric_writer will be created
  + resource "google_project_iam_member" "worker_monitoring_metric_writer" {
      + etag    = (known after apply)
      + id      = (known after apply)
      + member  = "serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
      + project = "project-42987e01-2123-446b-ac7"
      + role    = "roles/monitoring.metricWriter"
    }

Plan: 1 to add, 0 to change, 0 to destroy.
PLAN_EXIT=2
```

Exactly 1 add. No changes, replacements, or destroys. Gate passed.

---

## Apply

```shell
terraform -chdir=infra/terraform/gcp apply -auto-approve

  # google_project_iam_member.worker_monitoring_metric_writer will be created
  + resource "google_project_iam_member" "worker_monitoring_metric_writer" {
      + etag    = (known after apply)
      + id      = (known after apply)
      + member  = "serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
      + project = "project-42987e01-2123-446b-ac7"
      + role    = "roles/monitoring.metricWriter"
    }

Plan: 1 to add, 0 to change, 0 to destroy.
google_project_iam_member.worker_monitoring_metric_writer: Creating...
google_project_iam_member.worker_monitoring_metric_writer: Creation complete after 9s
  [id=project-42987e01-2123-446b-ac7/roles/monitoring.metricWriter/serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com]

Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
APPLY_EXIT=0
```

---

## Post-Apply Plan

```shell
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false

No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

Zero drift confirmed.

---

## Read-Only IAM Confirmation

```shell
gcloud projects get-iam-policy project-42987e01-2123-446b-ac7 \
  --flatten="bindings[].members" \
  --filter="bindings.role=roles/monitoring.metricWriter AND bindings.members:rtdp-worker-sa" \
  --format="table(bindings.role,bindings.members)"

ROLE                           MEMBERS
roles/monitoring.metricWriter  serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

`roles/monitoring.metricWriter` is now present for the Cloud Run Job runtime service account.

---

## Safety State

### Cloud SQL

```shell
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state,settings.activationPolicy)"

NAME           STATE    ACTIVATION_POLICY
rtdp-postgres  STOPPED  NEVER
```

### Cloud Scheduler

```shell
gcloud scheduler jobs list \
  --project=project-42987e01-2123-446b-ac7 \
  --location=europe-west1 \
  --format="table(id,state,schedule)"

ID  STATE   SCHEDULE
    PAUSED  */15 * * * *
    PAUSED  0 * * * *
```

---

## Final Validation

### pytest

```shell
uv run pytest -q
348 passed in 5.04s
```

### ruff

```shell
uv run ruff check .
All checks passed!
RUFF_EXIT=0
```

### terraform fmt (final)

```shell
terraform fmt -check -recursive infra/terraform/gcp
FMT_EXIT=0
```

### terraform validate (final)

```shell
terraform -chdir=infra/terraform/gcp validate
Success! The configuration is valid.
VALIDATE_EXIT=0
```

### terraform plan (post-apply)

```shell
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

---

## Explicit Non-Claims

| Claim | Status |
| --- | --- |
| `DBT_METRICS_DRY_RUN=false` enabled | **NO — still `true` by default** |
| `DBT_METRICS_ENABLED=true` set | **NO — still `false` by default** |
| Cloud Run Job executed | **NO** |
| Scheduler activated | **NO** |
| Live dbt metric writes proven | **NO** |
| Cloud SQL started | **NO** |
| IAM mutated via gcloud manually | **NO — Terraform only** |
| Python code modified | **NO** |
| Dockerfiles modified | **NO** |
| Workflows modified | **NO** |
| Cloud Run env vars modified | **NO** |

---

## What This Unblocks

`rtdp-worker-sa` now holds `roles/monitoring.metricWriter` at project scope. A separate
execution branch may enable `DBT_METRICS_ENABLED=true` and `DBT_METRICS_DRY_RUN=false` on
the Cloud Run Job and execute a live metric write proof to confirm that
`custom.googleapis.com/rtdp/dbt_metrics/*` time series appear in Cloud Monitoring from an
actual `rtdp-dbt-refresh-job` execution.

---

## Recruiter / Portfolio Value

This branch demonstrates minimal-footprint IAM hygiene: the exact missing binding identified
by the audit (PR #207) is added via Terraform as a single `google_project_iam_member`
resource, touching no application code, no env vars, and no CI configuration. The dry-run
guard from PR #204 (`DBT_METRICS_DRY_RUN=true`) continues to protect the live write path
until the next intentional proof branch. The pattern — audit branch, Terraform-only grant
branch, proof branch — reflects how IAM changes are handled responsibly in production GCP
environments where misconfigured permissions cause silent runtime failures.
