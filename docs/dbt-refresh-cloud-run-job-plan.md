# dbt Refresh Cloud Run Job — Scaffold Plan

**Status: SCAFFOLD ONLY — NOT DEPLOYED**

This document records the Terraform and deployment scaffolding added for `rtdp-dbt-refresh-job`.
No `terraform apply` has been run, no Cloud Run Job has been deployed, and no GCP state has
been mutated.

---

## What Was Added

| Artifact | Path | Description |
|---|---|---|
| Terraform Cloud Run Job resource | `infra/terraform/gcp/cloud_run_jobs.tf` | `google_cloud_run_v2_job.rtdp_dbt_refresh_job` — scaffold definition |
| Scheduler TODO comment | `infra/terraform/gcp/scheduler.tf` | Reminder to switch URI after deployment evidence is accepted |
| Deploy workflow | `.github/workflows/deploy-dbt-refresh-cloud-run.yml` | `workflow_dispatch`-only build/push/deploy pipeline |
| This document | `docs/dbt-refresh-cloud-run-job-plan.md` | Scaffold plan |

---

## Credential Contract

**Resolved** (branch `feat/dbt-refresh-database-url-runtime`).

The `rtdp-database-url` Secret Manager secret stores a full PostgreSQL connection URL
(`postgresql://user:password@host/dbname`), not a raw password string.

Resolution: the runtime now accepts `DATABASE_URL` and parses it to derive connection
fields. Explicit `DBT_POSTGRES_*` env vars override any field parsed from the URL.

On Cloud Run, `DBT_POSTGRES_HOST=/cloudsql/...` is kept as a plain env var so the Unix
socket mount is used instead of the TCP host in the URL.

Before this fix, `DBT_POSTGRES_PASSWORD` was wired to `rtdp-database-url:latest`, which
would have caused the dbt connection to receive a full URL as the password value and fail.
That wiring has been removed from both the Terraform scaffold and the deploy workflow.

---

## Terraform Resource Summary

Resource: `google_cloud_run_v2_job.rtdp_dbt_refresh_job`

| Field | Value |
|---|---|
| name | `rtdp-dbt-refresh-job` |
| location | `var.region` (europe-west1) |
| project | `var.project_id` |
| task_count | 1 |
| service_account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| timeout | `600s` (dbt run + test may exceed the 300s silver refresh window) |
| max_retries | 0 |
| image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-dbt-refresh-job:latest` |

Plain environment variables:

| Name | Value |
|---|---|
| `DBT_REFRESH_MODE` | `run-and-test` |
| `DBT_POSTGRES_HOST` | `/cloudsql/project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres` |
| `DBT_POSTGRES_PORT` | `5432` |
| `DBT_POSTGRES_USER` | `rtdp` |
| `DBT_POSTGRES_DBNAME` | `realtime_platform` |
| `DBT_TARGET` | `cloudsql` |
| `DBT_PROJECT_DIR` | `/app/dbt` |
| `DBT_PROFILES_DIR` | `/tmp/rtdp-dbt-profiles` |

Secret environment variable:

| Name | Secret | Version | Notes |
|---|---|---|---|
| `DATABASE_URL` | `rtdp-database-url` | `latest` | Full connection URL; runtime parses it |

`DBT_POSTGRES_PASSWORD` is no longer wired to a secret — password is derived from `DATABASE_URL`.
`DBT_POSTGRES_HOST` overrides the URL host to use the Cloud SQL Unix socket mount.

Cloud SQL volume: `project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres` mounted at `/cloudsql`.

Lifecycle: image, annotations, labels, client, client_version changes ignored (matches silver refresh job pattern).

---

## Deploy Workflow Summary

File: `.github/workflows/deploy-dbt-refresh-cloud-run.yml`

- Trigger: `workflow_dispatch` only — does NOT auto-run on push or merge.
- Builds `apps/dbt-refresh-job/Dockerfile` with the repo root as build context.
- Tags image with `GITHUB_SHA` and also pushes `:latest` to Artifact Registry.
- Uses the same Workload Identity Federation / `GCP_WORKLOAD_IDENTITY_PROVIDER` /
  `GCP_CLOUD_RUN_DEPLOY_SERVICE_ACCOUNT` vars as existing deploy workflows.
- Deploys via `gcloud run jobs deploy` (Cloud Run Jobs syntax, not `gcloud run deploy`).
- Sets `--set-secrets="DATABASE_URL=rtdp-database-url:latest"`.
- Keeps `DBT_POSTGRES_HOST=/cloudsql/...` in `--set-env-vars`.
- Runs a post-deploy verification step that reads `gcloud run jobs describe` JSON and
  asserts image, service account, timeout, max_retries, env vars, `DATABASE_URL` secret ref,
  and `DBT_POSTGRES_HOST` value.
- Does NOT execute the job after deploy — execution requires a separate
  `gcloud run jobs execute rtdp-dbt-refresh-job` command or scheduler trigger.

---

## Scheduler

The Cloud Scheduler (`rtdp-silver-refresh-scheduler`) still targets `rtdp-silver-refresh-job:run`.
The URI has not been changed in this branch. A TODO comment in `scheduler.tf` marks the
pending switch. The scheduler remains `paused = true`.

Scheduler switch steps (separate branch, after deployment evidence is accepted):

1. Update the scheduler URI to point to `rtdp-dbt-refresh-job:run`.
2. Validate one controlled scheduled execution.
3. Confirm `silver_refresh_success_count` metric increments (or add a dbt-specific metric).
4. Retain `rtdp-silver-refresh-job` as a fallback until dbt path is fully accepted.

---

## Non-Goals For This Branch

- No `terraform apply`.
- No Cloud Run Job deployment.
- No Cloud SQL start.
- No scheduler URI switch.
- No scheduler resume.
- No stored function removal.
- No changes to `apps/silver-refresh-job`.
- No changes to dbt models.
- No generated dbt artifacts committed.
- No `dbt/profiles.yml` committed.

---

## Next Steps

1. **Execute controlled deployment validation** — credential contract resolved; proceed when ready:
   a. Start Cloud SQL (`NEVER → RUNNABLE`).
   b. Dispatch the `deploy-dbt-refresh-cloud-run.yml` workflow.
   c. Manually execute the job: `gcloud run jobs execute rtdp-dbt-refresh-job --region=europe-west1`.
   d. Confirm dbt run + test success in Cloud Logging.
   e. Stop Cloud SQL (`RUNNABLE → NEVER`).
   f. Document evidence in a new branch.
2. **Switch scheduler** — in a separate branch after deployment evidence is accepted, update
   the scheduler URI from `rtdp-silver-refresh-job:run` to `rtdp-dbt-refresh-job:run`.
3. **Decommission silver refresh job** — only after the dbt path is fully validated and
   the scheduler switch is confirmed in production.
