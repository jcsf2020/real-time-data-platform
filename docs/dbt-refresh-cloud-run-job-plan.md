# dbt Refresh Cloud Run Job — Scaffold Plan

**Status: SCAFFOLD ONLY — NOT DEPLOYED**

This document records the Terraform and deployment scaffolding added for `rtdp-dbt-refresh-job`
in branch `feat/dbt-refresh-cloud-run-job`. No `terraform apply` has been run, no Cloud Run Job
has been deployed, and no GCP state has been mutated.

---

## What Was Added

| Artifact | Path | Description |
|---|---|---|
| Terraform Cloud Run Job resource | `infra/terraform/gcp/cloud_run_jobs.tf` | `google_cloud_run_v2_job.rtdp_dbt_refresh_job` — scaffold definition |
| Scheduler TODO comment | `infra/terraform/gcp/scheduler.tf` | Reminder to switch URI after deployment evidence is accepted |
| Deploy workflow | `.github/workflows/deploy-dbt-refresh-cloud-run.yml` | `workflow_dispatch`-only build/push/deploy pipeline |
| This document | `docs/dbt-refresh-cloud-run-job-plan.md` | Scaffold plan and credential contract warning |

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

| Name | Secret | Version |
|---|---|---|
| `DBT_POSTGRES_PASSWORD` | `rtdp-database-url` | `latest` |

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
- Runs a post-deploy verification step that reads `gcloud run jobs describe` JSON and
  asserts image, service account, timeout, max_retries, env vars, and secret ref.
- Does NOT execute the job after deploy — execution requires a separate
  `gcloud run jobs execute rtdp-dbt-refresh-job` command or scheduler trigger.

---

## Credential Contract Warning

**This is the primary blocker before deployment.**

The existing `rtdp-database-url` Secret Manager secret almost certainly stores a full
`postgresql://user:password@host/dbname` connection URL — not a raw password string.

The Terraform resource and the deploy workflow wire `DBT_POSTGRES_PASSWORD` directly from
`rtdp-database-url:latest`. If the secret value is a full URL, the runtime will receive the
entire URL as the password value and the dbt connection will fail.

Before running `terraform apply` or dispatching the deploy workflow:

1. Confirm the format of the `rtdp-database-url` secret value (full URL vs raw password).
2. Choose a resolution:
   - **Option A (preferred):** Create a new `rtdp-dbt-postgres-password` secret containing
     only the raw password, then update the Terraform resource and workflow to reference it.
   - **Option B:** Update the `apps/dbt-refresh-job` runtime to accept `DATABASE_URL` and
     parse the password from it, then adjust the env var mapping.
3. Update this document and the Terraform resource once the credential contract is resolved.

The TODO comment in `cloud_run_jobs.tf` and in the deploy workflow records this blocker inline.

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

1. **Resolve credential contract** — confirm `rtdp-database-url` format; create a dedicated
   raw-password secret or update the runtime to parse `DATABASE_URL`.
2. **Execute controlled deployment validation** — once the credential is resolved:
   a. Start Cloud SQL (`NEVER → RUNNABLE`).
   b. Dispatch the `deploy-dbt-refresh-cloud-run.yml` workflow.
   c. Manually execute the job: `gcloud run jobs execute rtdp-dbt-refresh-job --region=europe-west1`.
   d. Confirm dbt run + test success in Cloud Logging.
   e. Stop Cloud SQL (`RUNNABLE → NEVER`).
   f. Document evidence in a new branch.
3. **Switch scheduler** — in a separate branch after deployment evidence is accepted, update
   the scheduler URI from `rtdp-silver-refresh-job:run` to `rtdp-dbt-refresh-job:run`.
4. **Decommission silver refresh job** — only after the dbt path is fully validated and
   the scheduler switch is confirmed in production.
