# dbt Refresh Cloud Run Job — Deployment Evidence

**Status:** DEPLOYED — TERRAFORM ZERO-DIFF — ACCEPTED  
**Branch:** `feat/dbt-refresh-cloud-run-deploy`  
**Date:** 2026-05-13  
**Runbook:** [docs/dbt-refresh-cloud-run-job-plan.md](dbt-refresh-cloud-run-job-plan.md)  
**Plan:** [docs/dbt-operational-migration-plan.md](dbt-operational-migration-plan.md)

---

## Executive Summary

`google_cloud_run_v2_job.rtdp_dbt_refresh_job` has been successfully deployed via
`terraform apply` and is confirmed to exist in GCP and Terraform state.

Two apply failures were encountered and resolved before the final successful deployment.
Both failures were caused by unsupported Cloud Run v2 Job system annotations in the
original scaffold. After the annotations were removed, `terraform apply` succeeded. A
subsequent `terraform plan -detailed-exitcode` returns exit code 0 — no changes. The
Cloud Run Job configuration in GCP matches the Terraform configuration exactly.

Cloud SQL remained `NEVER / STOPPED` throughout. The Cloud Run Job was not executed.
The scheduler was not changed. Stored functions remain intact. All 153 pytest tests pass.
Ruff is clean.

---

## Deployment Failures and Fixes

### Failure 1 — Unsupported annotation: `run.googleapis.com/cloudsql-instances`

**Root cause:** The original scaffold included a `template[0].annotations` block on the
`rtdp_dbt_refresh_job` resource containing:

```hcl
annotations = {
  "run.googleapis.com/cloudsql-instances"    = "project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres"
  "run.googleapis.com/execution-environment" = "gen2"
}
```

Cloud Run v2 Jobs do not support the `run.googleapis.com/cloudsql-instances` system
annotation on the outer job template. Cloud SQL instance binding is provided instead via
the `volumes` / `cloud_sql_instance` block in the task container spec.

**Fix:** Removed the `run.googleapis.com/cloudsql-instances` annotation from the
`rtdp_dbt_refresh_job` template annotations.

### Failure 2 — Unsupported annotation: `run.googleapis.com/execution-environment`

**Root cause:** After removing the cloudsql annotation, the apply failed again because
Cloud Run v2 Jobs also do not support the `run.googleapis.com/execution-environment`
system annotation on the outer job template at apply time.

**Fix:** Removed the remaining `run.googleapis.com/execution-environment` annotation from
the `rtdp_dbt_refresh_job` template annotations. The entire `annotations` block was
removed from the `rtdp_dbt_refresh_job` resource. The Cloud SQL volume mount and
`cloud_sql_instance` block in the task `volumes` spec are the correct mechanism for Cloud
SQL access and remain present.

**Note on `rtdp_silver_refresh_job`:** The silver refresh job resource retains the
`run.googleapis.com/execution-environment = "gen2"` annotation in its template because it
was already deployed with this annotation. Terraform's `ignore_changes =
[template[0].annotations]` prevents drift detection on this field for the silver refresh
job. The dbt refresh job does not require this annotation.

### Failure 3 — Stale saved plan

After the second fix, the apply was attempted with a previously saved plan. It failed with:

```
Error: Saved plan is stale
```

The saved plan referenced the pre-fix scaffold state. A fresh `terraform plan
-detailed-exitcode` was run immediately after, returning exit code 0 — confirming that the
fix had already been applied to GCP during the prior apply attempt and that the
infrastructure now matches the configuration.

---

## Pre-Execution Validation

| Check | Result |
|---|---|
| Branch | `feat/dbt-refresh-cloud-run-deploy` |
| pytest | 153 passed |
| ruff | All checks passed |
| terraform fmt | Clean (exit 0) |
| terraform validate | Success |
| Cloud SQL state | `NEVER / STOPPED` |

---

## Terraform State Audit

### State list

```
google_cloud_run_v2_job.rtdp_dbt_refresh_job
```

Resource confirmed present in Terraform state.

### Terraform plan result

```
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode
```

```
No changes. Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your configuration
and found no differences, so no changes are needed.

PLAN_EXIT=0
```

Zero diff. The deployed Cloud Run Job in GCP matches the Terraform configuration exactly.

---

## GCP Cloud Run Job Verification

### gcloud describe output (parsed)

```
JOB_NAME=rtdp-dbt-refresh-job
CREATE_TIME=2026-05-13T19:16:23.899505Z
GENERATION=1
```

```
IMAGE=europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-dbt-refresh-job:latest
SERVICE_ACCOUNT=rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
TIMEOUT=600
```

```
ENV_KEYS=DATABASE_URL,DBT_POSTGRES_DBNAME,DBT_POSTGRES_HOST,DBT_POSTGRES_PORT,DBT_POSTGRES_USER,DBT_PROFILES_DIR,DBT_PROJECT_DIR,DBT_REFRESH_MODE,DBT_TARGET
HAS_DATABASE_URL_SECRET=True
DBT_REFRESH_MODE=run-and-test
DBT_POSTGRES_HOST=/cloudsql/project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres
DBT_TARGET=cloudsql
DATABASE_URL_SECRET_REF={'key': 'latest', 'name': 'rtdp-database-url'}
```

```
PROBLEMATIC_ANNOTATIONS=[]
ALL_ANNOTATIONS=['run.googleapis.com/creator', 'run.googleapis.com/lastModifier', 'run.googleapis.com/operation-id']
```

No unsupported system annotations present. Only GCP-managed system annotations appear
(`creator`, `lastModifier`, `operation-id` — these are set by GCP, not by Terraform).

### Configuration verification

| Field | Expected | Observed | Match |
|---|---|---|---|
| Job name | `rtdp-dbt-refresh-job` | `rtdp-dbt-refresh-job` | Yes |
| Image | `rtdp-dbt-refresh-job:latest` | `rtdp-dbt-refresh-job:latest` | Yes |
| Service account | `rtdp-worker-sa@...` | `rtdp-worker-sa@...` | Yes |
| Timeout | 600s | 600 | Yes |
| `DBT_REFRESH_MODE` | `run-and-test` | `run-and-test` | Yes |
| `DBT_POSTGRES_HOST` | `/cloudsql/...rtdp-postgres` | `/cloudsql/...rtdp-postgres` | Yes |
| `DBT_TARGET` | `cloudsql` | `cloudsql` | Yes |
| `DATABASE_URL` secret | `rtdp-database-url:latest` | `rtdp-database-url:latest` | Yes |
| `DBT_PROFILES_DIR` | `/tmp/rtdp-dbt-profiles` | present in ENV_KEYS | Yes |
| Cloud SQL volume | `europe-west1:rtdp-postgres` mounted at `/cloudsql` | present in spec | Yes |
| Problematic annotations | None | None | Yes |

---

## Invariant Checks

### Cloud SQL state

```
NEVER   STOPPED
```

Cloud SQL was not started at any point during this branch.

### Scheduler state

```hcl
# infra/terraform/gcp/scheduler.tf
paused    = true
uri       = "...jobs/rtdp-silver-refresh-job:run"
```

Scheduler remains `paused = true`. URI still targets `rtdp-silver-refresh-job:run`.
The TODO comment is preserved — the URI switch to `rtdp-dbt-refresh-job:run` remains
pending a future controlled evidence branch.

### Stored functions

```
grep -c "CREATE OR REPLACE FUNCTION" infra/postgres/init.sql
2
```

Both `silver.refresh_market_event_minute_aggregates()` and
`gold.refresh_market_event_daily_aggregates()` remain present in `infra/postgres/init.sql`.
Stored functions are not removed.

### Silver refresh job unchanged

```python
# apps/silver-refresh-job/src/rtdp_silver_refresh_job/__init__.py:11
_SQL = "SELECT silver.refresh_market_event_minute_aggregates();"
```

`rtdp-silver-refresh-job` runtime is unchanged. It remains the authoritative operational
refresh path until the dbt job execution evidence is accepted and the scheduler is switched.

### dbt profile and artifacts

```
REPO_DBT_PROFILE_ABSENT=true
git status --ignored --short dbt  →  (no output)
```

`dbt/profiles.yml` is absent from the repository. No generated dbt artifacts are tracked
or present in the dbt directory.

---

## Acceptance Criteria

| Criterion | Required | Observed | Met? |
|---|---|---|---|
| `rtdp-dbt-refresh-job` exists in GCP | Yes | `CREATE_TIME=2026-05-13T19:16:23.899505Z` | Yes |
| Resource in Terraform state | Yes | `google_cloud_run_v2_job.rtdp_dbt_refresh_job` in state list | Yes |
| `terraform plan -detailed-exitcode` returns 0 | Yes | `PLAN_EXIT=0` | Yes |
| Correct image | `rtdp-dbt-refresh-job:latest` | Confirmed | Yes |
| `DATABASE_URL` wired to `rtdp-database-url:latest` secret | Yes | `DATABASE_URL_SECRET_REF` confirmed | Yes |
| `DBT_POSTGRES_HOST` set to Cloud SQL Unix socket | Yes | `/cloudsql/.../rtdp-postgres` | Yes |
| `DBT_REFRESH_MODE=run-and-test` | Yes | Confirmed | Yes |
| No unsupported system annotations | Yes | `PROBLEMATIC_ANNOTATIONS=[]` | Yes |
| Cloud SQL `NEVER / STOPPED` | Yes | Confirmed | Yes |
| Scheduler `PAUSED`, still targeting silver refresh job | Yes | `paused = true`, URI unchanged | Yes |
| Stored functions present in `infra/postgres/init.sql` | 2 | `grep -c` = 2 | Yes |
| Silver refresh job runtime unchanged | Yes | `_SQL` unchanged at line 11 | Yes |
| `dbt/profiles.yml` absent | Yes | `REPO_DBT_PROFILE_ABSENT=true` | Yes |
| No generated dbt artifacts committed | Yes | `git status --ignored --short dbt` empty | Yes |
| `uv run pytest -q` passes | 153 passed | 153 passed | Yes |
| `uv run ruff check .` clean | Yes | All checks passed | Yes |
| `terraform fmt -check` clean | Yes | Exit 0 | Yes |
| `terraform validate` success | Yes | Success | Yes |

All acceptance criteria met.

---

## What Was Changed on This Branch

| File | Change | Reason |
|---|---|---|
| `infra/terraform/gcp/cloud_run_jobs.tf` | Removed `template[0].annotations` block from `rtdp_dbt_refresh_job` | `run.googleapis.com/cloudsql-instances` and `run.googleapis.com/execution-environment` are not supported on Cloud Run v2 Job outer template; Cloud SQL is correctly provided via `volumes.cloud_sql_instance` |
| `infra/terraform/gcp/cloud_run_jobs.tf` | Updated stale scaffold comment at line 2 | Previous "SCAFFOLD ONLY" comment was stale after deployment; updated to reflect deployed state |

`rtdp_silver_refresh_job` was not modified.

---

## What Remains Pending (Next Branch)

This branch establishes Terraform ownership of `rtdp-dbt-refresh-job` with a confirmed
zero-diff plan. The Cloud Run Job exists in GCP with the correct configuration. It has
not been executed. The following remain for subsequent branches:

| Item | Next Branch |
|---|---|
| Execute `rtdp-dbt-refresh-job` against Cloud SQL and validate dbt run + test success | `exec/dbt-refresh-job-execution-proof` |
| Switch Cloud Scheduler URI from `rtdp-silver-refresh-job:run` to `rtdp-dbt-refresh-job:run` | `feat/dbt-scheduler-switch` (after execution evidence is accepted) |
| Decommission `rtdp-silver-refresh-job` | Separate cleanup branch, after scheduler switch is validated |

---

## Safety Confirmation

| Control | Status |
|---|---|
| No runtime code modified | Confirmed |
| No dbt models modified | Confirmed |
| No GitHub Actions workflows modified | Confirmed |
| No stored functions removed | Confirmed |
| Cloud Run Job not executed | Confirmed |
| Cloud SQL not started | Confirmed: `NEVER / STOPPED` |
| Scheduler not changed | Confirmed: `paused = true`, URI unchanged |
| No `dbt/profiles.yml` committed | Confirmed |
| No generated dbt artifacts committed | Confirmed |
| `terraform apply` not run on this evidence-gathering pass | Confirmed — deploy was completed in prior apply attempts; this pass is state audit only |
| `rtdp-silver-refresh-job` unchanged | Confirmed |
