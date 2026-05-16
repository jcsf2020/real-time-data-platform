# BigQuery Append Scheduler — Evidence

**Status:** VALIDATED — CONFIGURATION ONLY / PAUSED
**Date:** 2026-05-16
**Branch:** `feat/bigquery-append-scheduler`

---

## Executive Summary

The Cloud Scheduler job for the BigQuery incremental append path was created in this branch via Terraform.

- Scheduler name: `rtdp-bigquery-append-scheduler`
- Scheduler created via Terraform apply on `feat/bigquery-append-scheduler`.
- Scheduler is **PAUSED by default** — it was not triggered or executed.
- Scheduler targets `rtdp-bigquery-append-job:run` via authenticated HTTP POST.
- No new service account or IAM resources were required. `rtdp-scheduler-sa` already has project-level `roles/run.invoker`, so no new IAM resources were required in this branch. This keeps the change minimal and avoids unrelated IAM churn. It is operationally valid for this single-project portfolio environment, but a future hardening branch may scope invocation to specific Cloud Run Jobs if stricter least privilege is required.
- Existing `rtdp-silver-refresh-scheduler` remains unchanged and PAUSED, still targeting `rtdp-dbt-refresh-job:run`.
- Cloud SQL remained **NEVER / STOPPED** throughout — was not started at any point.
- The BigQuery append job was not executed.
- No BigQuery data was mutated.
- No scheduler was triggered.
- `dbt/profiles.yml` is absent from the repository.

---

## Terraform Changes

Two files modified:

| File | Change |
|---|---|
| `infra/terraform/gcp/locals.tf` | Added `scheduler_bigquery_append = "rtdp-bigquery-append-scheduler"` local |
| `infra/terraform/gcp/scheduler.tf` | Added `google_cloud_scheduler_job.bigquery_append_scheduler` resource |

### Scheduler Resource Definition

```hcl
resource "google_cloud_scheduler_job" "bigquery_append_scheduler" {
  name      = local.scheduler_bigquery_append
  region    = var.region
  schedule  = "0 * * * *"
  time_zone = "Europe/Lisbon"
  paused    = true

  http_target {
    uri         = "https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-bigquery-append-job:run"
    http_method = "POST"

    oauth_token {
      service_account_email = "rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
    }
  }

  retry_config {
    retry_count          = 0
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }
}
```

### IAM Analysis

No new service account or IAM binding was created. `rtdp-scheduler-sa` already has project-level `roles/run.invoker` (managed by `google_project_iam_member.scheduler_run_invoker` in `iam.tf`), so no new IAM resources were required in this branch. This keeps the change minimal and avoids unrelated IAM churn. It is operationally valid for this single-project portfolio environment, but a future hardening branch may scope invocation to specific Cloud Run Jobs if stricter least privilege is required.

---

## Terraform Plan Summary

Plan executed before apply:

```
Plan: 1 to add, 0 to change, 0 to destroy.
```

Resources planned:

| Action | Resource |
|---|---|
| create | `google_cloud_scheduler_job.bigquery_append_scheduler` |

No destroys. No replacements. No changes to `rtdp-silver-refresh-scheduler`.

---

## Terraform Apply Output

```
google_cloud_scheduler_job.bigquery_append_scheduler: Creating...
google_cloud_scheduler_job.bigquery_append_scheduler: Creation complete after 5s
  [id=projects/project-42987e01-2123-446b-ac7/locations/europe-west1/jobs/rtdp-bigquery-append-scheduler]

Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

---

## Post-Apply Validation

### Final Terraform Plan (zero-diff)

```
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

### Scheduler State — New Job

```
gcloud scheduler jobs describe rtdp-bigquery-append-scheduler \
  --location=europe-west1 \
  --format="value(state,httpTarget.uri,schedule,timeZone)"

PAUSED
https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-bigquery-append-job:run
0 * * * *
Europe/Lisbon
```

### Scheduler State — Existing Silver Refresh (unchanged)

```
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --format="value(state,httpTarget.uri,schedule,timeZone)"

PAUSED
https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-dbt-refresh-job:run
*/15 * * * *
UTC
```

### Cloud SQL State

```
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"

NEVER
STOPPED
```

### Test Suite

```
187 passed in 4.65s
```

### Linter

```
All checks passed!
```

### dbt/profiles.yml

```
REPO_DBT_PROFILE_ABSENT=true
```

---

## Verification Table

| Check | Required | Observed | Pass |
|---|---|---|---|
| `rtdp-bigquery-append-scheduler` exists | Yes | Yes | **Yes** |
| Scheduler state | `PAUSED` | `PAUSED` | **Yes** |
| Scheduler target | `rtdp-bigquery-append-job:run` | `rtdp-bigquery-append-job:run` endpoint | **Yes** |
| Schedule | `0 * * * *` | `0 * * * *` | **Yes** |
| Timezone | `Europe/Lisbon` | `Europe/Lisbon` | **Yes** |
| `rtdp-silver-refresh-scheduler` state | `PAUSED` | `PAUSED` | **Yes** |
| `rtdp-silver-refresh-scheduler` target | `rtdp-dbt-refresh-job:run` | `rtdp-dbt-refresh-job:run` endpoint | **Yes** |
| Terraform final plan | `PLAN_EXIT=0` | `PLAN_EXIT=0` | **Yes** |
| Cloud SQL | `NEVER / STOPPED` | `NEVER / STOPPED` | **Yes** |
| pytest | 187 passed | 187 passed | **Yes** |
| ruff | All checks passed | All checks passed | **Yes** |
| `dbt/profiles.yml` absent | `true` | `REPO_DBT_PROFILE_ABSENT=true` | **Yes** |
| Scheduler executed | No | No | **Yes** |
| BigQuery append job executed | No | No | **Yes** |
| BigQuery data mutated | No | No | **Yes** |
| Secrets printed | No | No | **Yes** |

---

## Final Safety State

| Component | State |
|---|---|
| Terraform | `PLAN_EXIT=0` |
| Cloud SQL (`rtdp-postgres`) | `NEVER / STOPPED` |
| BigQuery append scheduler (`rtdp-bigquery-append-scheduler`) | `PAUSED` |
| Silver refresh scheduler (`rtdp-silver-refresh-scheduler`) | `PAUSED` |
| `dbt/profiles.yml` | Absent |

---

## What This Proves

The operational orchestration gap for BigQuery incremental append is closed at configuration level.

There is now a Terraform-managed Scheduler job (`rtdp-bigquery-append-scheduler`) capable of dispatching `rtdp-bigquery-append-job` on a `0 * * * *` Europe/Lisbon cadence via authenticated HTTP POST using `rtdp-scheduler-sa`. The job is paused intentionally to preserve the cost-control invariant until a controlled execution validation branch is run.

---

## What This Does Not Claim

- Does not prove scheduled execution succeeded — the scheduler was not triggered.
- Does not start Cloud SQL.
- Does not execute the `rtdp-bigquery-append-job` Cloud Run Job.
- Does not mutate BigQuery data.

---

## Acceptance Matrix

| Criterion | Status |
|---|---|
| Scheduler created via Terraform | **ACCEPTED** |
| Scheduler name `rtdp-bigquery-append-scheduler` | **ACCEPTED** |
| Scheduler PAUSED by default | **ACCEPTED** |
| Scheduler targets `rtdp-bigquery-append-job:run` | **ACCEPTED** |
| Schedule `0 * * * *`, timezone `Europe/Lisbon` | **ACCEPTED** |
| No new IAM or service account resources needed | **ACCEPTED** |
| Existing silver/dbt scheduler unchanged and PAUSED | **ACCEPTED** |
| Terraform `PLAN_EXIT=0` | **ACCEPTED** |
| Cloud SQL `NEVER / STOPPED` throughout | **ACCEPTED** |
| 187 tests passed | **ACCEPTED** |
| Ruff clean | **ACCEPTED** |
| `dbt/profiles.yml` absent | **ACCEPTED** |
| No scheduler execution | **ACCEPTED** |
| No BigQuery append job execution | **ACCEPTED** |
| No BigQuery data mutation | **ACCEPTED** |
| No secrets printed | **ACCEPTED** |

All criteria met. Evidence status: **VALIDATED — CONFIGURATION ONLY / PAUSED**.
