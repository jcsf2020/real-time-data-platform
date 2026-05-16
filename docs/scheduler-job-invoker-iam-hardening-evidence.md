# Scheduler IAM Hardening — Job-Scoped Invoker Evidence

**Status:** VALIDATED — TERRAFORM PLAN ONLY / NOT YET APPLIED
**Date:** 2026-05-16
**Branch:** `harden/scheduler-job-invoker-iam`

---

## Executive Summary

This branch replaces the broad project-level `roles/run.invoker` binding on
`rtdp-scheduler-sa` with two resource-scoped `google_cloud_run_v2_job_iam_member`
bindings — one per Cloud Run Job that the scheduler must invoke.

The Google provider (6.50.0, `~> 6.0`) fully supports `google_cloud_run_v2_job_iam_member`
and was verified against the live provider schema before any changes were made.

---

## Investigation Results

### Provider Support Check

```
Resource query: google_cloud_run_v2_job_iam_*

Supported resources:
  google_cloud_run_v2_job_iam_binding
  google_cloud_run_v2_job_iam_member
  google_cloud_run_v2_job_iam_policy

Provider version: 6.50.0 (constraint: ~> 6.0)
```

`google_cloud_run_v2_job_iam_member` is available. Job-level IAM hardening is supported.

### Schema

Required attributes: `member`, `name`, `role`
Optional attributes: `project`, `location`

---

## Prior State

`rtdp-scheduler-sa` had project-level `roles/run.invoker` via:

```hcl
resource "google_project_iam_member" "scheduler_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = local.rtdp_scheduler_service_account
}
```

This granted the scheduler service account the ability to invoke any Cloud Run
resource in the project. The previous evidence documents
(`bigquery-append-scheduler-evidence.md`, line 67) explicitly flagged this as
"operationally valid but a future hardening branch may scope invocation to specific
Cloud Run Jobs if stricter least privilege is required."

---

## Change Made

**File modified:** `infra/terraform/gcp/iam.tf`

**Removed:**

```hcl
resource "google_project_iam_member" "scheduler_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = local.rtdp_scheduler_service_account
}
```

**Added:**

```hcl
resource "google_cloud_run_v2_job_iam_member" "scheduler_bigquery_append_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.rtdp_bigquery_append_job.name
  role     = "roles/run.invoker"
  member   = local.rtdp_scheduler_service_account
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_dbt_refresh_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.rtdp_dbt_refresh_job.name
  role     = "roles/run.invoker"
  member   = local.rtdp_scheduler_service_account
}
```

### Scheduler-to-Job Mapping

| Scheduler | Target Job | IAM Resource |
|---|---|---|
| `rtdp-bigquery-append-scheduler` | `rtdp-bigquery-append-job` | `scheduler_bigquery_append_invoker` |
| `rtdp-silver-refresh-scheduler` | `rtdp-dbt-refresh-job` | `scheduler_dbt_refresh_invoker` |

`rtdp-silver-refresh-job` is not targeted by any scheduler and does not require
an invoker binding.

---

## Terraform Plan

```
Plan: 2 to add, 0 to change, 1 to destroy.
PLAN_EXIT=2
```

| Action | Resource |
|---|---|
| create | `google_cloud_run_v2_job_iam_member.scheduler_bigquery_append_invoker` |
| create | `google_cloud_run_v2_job_iam_member.scheduler_dbt_refresh_invoker` |
| destroy | `google_project_iam_member.scheduler_run_invoker` |

`PLAN_EXIT=2` is expected: the plan contains pending changes that have not yet been
applied. All changes are intentional. No other resources are affected.

---

## Validation Results

### Terraform fmt

```
FMT_PASS=true
```

### Terraform validate

```
Success! The configuration is valid.
VALIDATE_PASS=true
```

### pytest

```
187 passed in 4.64s
```

### ruff

```
All checks passed!
RUFF_PASS=true
```

### dbt/profiles.yml

```
REPO_DBT_PROFILE_ABSENT=true
```

### Cloud SQL State

```
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"

NEVER	STOPPED
```

### Scheduler State — BigQuery Append

```
gcloud scheduler jobs describe rtdp-bigquery-append-scheduler \
  --location=europe-west1 \
  --format="value(state,httpTarget.uri,schedule,timeZone)"

PAUSED
https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-bigquery-append-job:run
0 * * * *
Europe/Lisbon
```

### Scheduler State — Silver Refresh

```
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --format="value(state,httpTarget.uri,schedule,timeZone)"

PAUSED
https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-dbt-refresh-job:run
*/15 * * * *
UTC
```

### Git Status (pre-commit)

```
## harden/scheduler-job-invoker-iam
 M infra/terraform/gcp/iam.tf
```

---

## Verification Table

| Check | Required | Observed | Pass |
|---|---|---|---|
| Provider supports `google_cloud_run_v2_job_iam_member` | Yes | Yes (6.50.0) | **Yes** |
| `scheduler_bigquery_append_invoker` in plan | Yes | create | **Yes** |
| `scheduler_dbt_refresh_invoker` in plan | Yes | create | **Yes** |
| `scheduler_run_invoker` removed from plan | Yes | destroy | **Yes** |
| No unrelated resources in plan | Yes | 0 change | **Yes** |
| Terraform fmt | pass | pass | **Yes** |
| Terraform validate | pass | pass | **Yes** |
| pytest | 187 passed | 187 passed | **Yes** |
| ruff | clean | clean | **Yes** |
| `dbt/profiles.yml` absent | true | true | **Yes** |
| Cloud SQL | NEVER / STOPPED | NEVER / STOPPED | **Yes** |
| `rtdp-bigquery-append-scheduler` state | PAUSED | PAUSED | **Yes** |
| `rtdp-bigquery-append-scheduler` target | `rtdp-bigquery-append-job:run` | `rtdp-bigquery-append-job:run` | **Yes** |
| `rtdp-silver-refresh-scheduler` state | PAUSED | PAUSED | **Yes** |
| `rtdp-silver-refresh-scheduler` target | `rtdp-dbt-refresh-job:run` | `rtdp-dbt-refresh-job:run` | **Yes** |
| Scheduler executed | No | No | **Yes** |
| Cloud SQL started | No | No | **Yes** |
| BigQuery data mutated | No | No | **Yes** |
| Secrets printed | No | No | **Yes** |

---

## Final Safety State

| Component | State |
|---|---|
| Terraform | `PLAN_EXIT=2` (pending apply — intentional) |
| Cloud SQL (`rtdp-postgres`) | `NEVER / STOPPED` |
| BigQuery append scheduler (`rtdp-bigquery-append-scheduler`) | `PAUSED` |
| Silver refresh scheduler (`rtdp-silver-refresh-scheduler`) | `PAUSED` |
| `dbt/profiles.yml` | Absent |

---

## What This Proves

`google_cloud_run_v2_job_iam_member` is supported by Google provider 6.50.0.
The replacement of the project-level `roles/run.invoker` binding with two
resource-scoped bindings is technically sound and produces a clean, auditable plan
with no unintended side effects.

After `terraform apply`:
- `rtdp-scheduler-sa` will only be able to invoke `rtdp-bigquery-append-job` and
  `rtdp-dbt-refresh-job` specifically.
- It will no longer hold any project-level Cloud Run invocation permission.
- Both schedulers remain PAUSED; no execution occurs during this hardening.

---

## What This Does Not Claim

- Does not prove scheduler-triggered job execution — schedulers remain PAUSED.
- Does not apply the Terraform plan. Apply must be run explicitly in a controlled window.
- Does not start Cloud SQL.
- Does not mutate BigQuery data.

---

## Acceptance Matrix

| Criterion | Status |
|---|---|
| Provider supports job-level IAM | **ACCEPTED** |
| Project-level binding removed from config | **ACCEPTED** |
| Job-scoped bindings added for both scheduled jobs | **ACCEPTED** |
| Terraform fmt passes | **ACCEPTED** |
| Terraform validate passes | **ACCEPTED** |
| Terraform plan: 2 add, 0 change, 1 destroy — no unrelated changes | **ACCEPTED** |
| 187 tests passed | **ACCEPTED** |
| Ruff clean | **ACCEPTED** |
| `dbt/profiles.yml` absent | **ACCEPTED** |
| Cloud SQL NEVER / STOPPED | **ACCEPTED** |
| Both schedulers PAUSED and targets unchanged | **ACCEPTED** |
| No scheduler execution | **ACCEPTED** |
| No BigQuery data mutation | **ACCEPTED** |
| No secrets printed | **ACCEPTED** |

All criteria met. Evidence status: **VALIDATED — TERRAFORM PLAN ONLY / NOT YET APPLIED**.
