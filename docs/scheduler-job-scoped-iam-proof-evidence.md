# Scheduler Job-Scoped IAM Proof Evidence

**Status:** VALIDATED — LIVE IAM PROOF
**Date:** 2026-05-16
**Branch:** `exec/scheduler-job-scoped-iam-proof`

---

## Scope

This document proves that the IAM hardening introduced in PR #131
(`04ef3c7 Harden scheduler IAM with job-scoped invoker bindings`) is live in GCP.
It validates IAM scoping only. No schedulers were executed. No Cloud SQL was started.
No BigQuery data was mutated.

---

## What Was Hardened

PR #131 replaced a broad project-level `roles/run.invoker` binding on `rtdp-scheduler-sa`
with two resource-scoped `google_cloud_run_v2_job_iam_member` bindings:

| Terraform Resource | Job | Role |
| --- | --- | --- |
| `google_cloud_run_v2_job_iam_member.scheduler_bigquery_append_invoker` | `rtdp-bigquery-append-job` | `roles/run.invoker` |
| `google_cloud_run_v2_job_iam_member.scheduler_dbt_refresh_invoker` | `rtdp-dbt-refresh-job` | `roles/run.invoker` |

The old `google_project_iam_member.scheduler_run_invoker` was destroyed by the apply.

---

## Live IAM Proof

### Project-Level — roles/run.invoker for rtdp-scheduler-sa

```sh
gcloud projects get-iam-policy project-42987e01-2123-446b-ac7 \
  --flatten="bindings[].members" \
  --filter="bindings.role=roles/run.invoker AND bindings.members=serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com" \
  --format="table(bindings.role)"

(no rows returned)
```

The project-level invoker binding is gone.

### rtdp-bigquery-append-job

```sh
gcloud run jobs get-iam-policy rtdp-bigquery-append-job \
  --region=europe-west1 \
  --format="table(bindings.role,bindings.members)"

ROLE               MEMBERS
roles/run.invoker  serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

### rtdp-dbt-refresh-job

```sh
gcloud run jobs get-iam-policy rtdp-dbt-refresh-job \
  --region=europe-west1 \
  --format="table(bindings.role,bindings.members)"

ROLE               MEMBERS
roles/run.invoker  serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

### rtdp-silver-refresh-job

```sh
gcloud run jobs get-iam-policy rtdp-silver-refresh-job \
  --region=europe-west1 \
  --format="table(bindings.role,bindings.members)"

(no scheduler invoker binding — expected)
```

`rtdp-silver-refresh-job` is not targeted by any scheduler and has no invoker binding,
confirming the scoping is exact.

---

## Terraform Zero-Diff Proof

```sh
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode

No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

The applied state matches the configuration exactly. Nothing is pending.

---

## Safe State

| Component | State |
| --- | --- |
| Cloud SQL (`rtdp-postgres`) | `NEVER / STOPPED` |
| `rtdp-bigquery-append-scheduler` | `PAUSED` |
| `rtdp-silver-refresh-scheduler` | `PAUSED` |
| `dbt/profiles.yml` | Absent |
| Git | Clean on `exec/scheduler-job-scoped-iam-proof` |

### Scheduler Targets (unchanged)

```sh
gcloud scheduler jobs describe rtdp-bigquery-append-scheduler \
  --location=europe-west1 \
  --format="value(state,httpTarget.uri,schedule,timeZone)"

PAUSED
https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-bigquery-append-job:run
0 * * * *
Europe/Lisbon
```

```sh
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --format="value(state,httpTarget.uri,schedule,timeZone)"

PAUSED
https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-dbt-refresh-job:run
*/15 * * * *
UTC
```

---

## Validation Results

| Check | Required | Observed | Pass |
| --- | --- | --- | --- |
| Project-level `roles/run.invoker` for `rtdp-scheduler-sa` | removed | no rows returned | **Yes** |
| `rtdp-bigquery-append-job` IAM has scheduler invoker | Yes | confirmed | **Yes** |
| `rtdp-dbt-refresh-job` IAM has scheduler invoker | Yes | confirmed | **Yes** |
| `rtdp-silver-refresh-job` IAM has no scheduler invoker | Yes | no binding | **Yes** |
| `terraform plan` | `PLAN_EXIT=0` | `PLAN_EXIT=0` | **Yes** |
| pytest | 187 passed | 187 passed | **Yes** |
| ruff | clean | clean | **Yes** |
| `dbt/profiles.yml` absent | true | true | **Yes** |
| Cloud SQL | `NEVER / STOPPED` | `NEVER / STOPPED` | **Yes** |
| `rtdp-bigquery-append-scheduler` state | `PAUSED` | `PAUSED` | **Yes** |
| `rtdp-bigquery-append-scheduler` target | `rtdp-bigquery-append-job:run` | `rtdp-bigquery-append-job:run` | **Yes** |
| `rtdp-silver-refresh-scheduler` state | `PAUSED` | `PAUSED` | **Yes** |
| `rtdp-silver-refresh-scheduler` target | `rtdp-dbt-refresh-job:run` | `rtdp-dbt-refresh-job:run` | **Yes** |
| Scheduler executed | No | No | **Yes** |
| Cloud SQL started | No | No | **Yes** |
| BigQuery data mutated | No | No | **Yes** |
| Secrets printed | No | No | **Yes** |

---

## What This Proves

`rtdp-scheduler-sa` now holds `roles/run.invoker` only on the two Cloud Run Jobs it
must invoke — `rtdp-bigquery-append-job` and `rtdp-dbt-refresh-job`. The project-level
binding is absent from GCP. The Terraform state is a zero-diff match against live GCP.

The blast radius of a compromised `rtdp-scheduler-sa` credential is now bounded to
those two jobs rather than any Cloud Run resource in the project.

---

## What This Does Not Claim

- Does not prove scheduler-triggered execution succeeded — schedulers remain PAUSED.
- Does not start Cloud SQL.
- Does not execute any Cloud Run Job.
- Does not mutate BigQuery data.

---

## Acceptance Matrix

| Criterion | Status |
| --- | --- |
| Project-level `roles/run.invoker` removed from GCP | **ACCEPTED** |
| Job-scoped invoker live on `rtdp-bigquery-append-job` | **ACCEPTED** |
| Job-scoped invoker live on `rtdp-dbt-refresh-job` | **ACCEPTED** |
| No invoker binding on `rtdp-silver-refresh-job` | **ACCEPTED** |
| Terraform `PLAN_EXIT=0` | **ACCEPTED** |
| Both schedulers PAUSED and targets unchanged | **ACCEPTED** |
| Cloud SQL `NEVER / STOPPED` | **ACCEPTED** |
| 187 tests passed | **ACCEPTED** |
| Ruff clean | **ACCEPTED** |
| `dbt/profiles.yml` absent | **ACCEPTED** |
| No scheduler execution | **ACCEPTED** |
| No BigQuery mutation | **ACCEPTED** |
| No secrets printed | **ACCEPTED** |

All criteria met. Evidence status: **VALIDATED — LIVE IAM PROOF**.
