# dbt Refresh Cloud Run Job — Scaffold Plan

**Status: SCAFFOLD ONLY — NOT DEPLOYED**

This document records the Terraform and image-build scaffolding added for `rtdp-dbt-refresh-job`.
No `terraform apply` has been run, no Cloud Run Job has been deployed, and no GCP state has
been mutated.

---

## IaC / Deploy Boundary

**Terraform is the source of truth for the Cloud Run Job definition.**

- `google_cloud_run_v2_job.rtdp_dbt_refresh_job` is declared in
  `infra/terraform/gcp/cloud_run_jobs.tf` and managed exclusively by Terraform.
- The GitHub Actions workflow (`deploy-dbt-refresh-cloud-run.yml`) builds and pushes the
  container image only. It does not create, update, or execute the Cloud Run Job.
- No Cloud Run mutation occurs in the workflow.
- Cloud Run Job deployment and execution must be handled in a dedicated controlled Terraform
  apply and evidence branch, only after Terraform resource ownership is accepted.

---

## What Was Added

| Artifact | Path | Description |
|---|---|---|
| Terraform Cloud Run Job resource | `infra/terraform/gcp/cloud_run_jobs.tf` | `google_cloud_run_v2_job.rtdp_dbt_refresh_job` — Terraform-owned scaffold definition |
| Scheduler TODO comment | `infra/terraform/gcp/scheduler.tf` | Reminder to switch URI after deployment evidence is accepted |
| Image build/push workflow | `.github/workflows/deploy-dbt-refresh-cloud-run.yml` | `workflow_dispatch`-only build/push pipeline — no Cloud Run deployment |
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

**Terraform is the authoritative owner of this resource. No workflow or manual gcloud command
creates or updates it.**

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

## Image Build/Push Workflow Summary

File: `.github/workflows/deploy-dbt-refresh-cloud-run.yml`
Workflow name: `Build dbt Refresh Job Image`

- Trigger: `workflow_dispatch` only — does NOT auto-run on push or merge.
- Builds `apps/dbt-refresh-job/Dockerfile` with the repo root as build context.
- Tags image with `GITHUB_SHA` and also pushes `:latest` to Artifact Registry.
- Uses the same Workload Identity Federation / `GCP_WORKLOAD_IDENTITY_PROVIDER` /
  `GCP_CLOUD_RUN_DEPLOY_SERVICE_ACCOUNT` vars as existing deploy workflows.
- **Does NOT run `gcloud run jobs deploy`.**
- **Does NOT run `gcloud run jobs describe`.**
- **Does NOT run `gcloud run jobs execute`.**
- **No Cloud Run Job is created, updated, or executed by this workflow.**
- Outputs: `IMAGE_URI`, `LATEST_URI`, `IMAGE_PUSHED=true`,
  `CLOUD_RUN_JOB_NOT_DEPLOYED_BY_THIS_WORKFLOW=true`.

---

## Scheduler

The Cloud Scheduler (`rtdp-silver-refresh-scheduler`) still targets `rtdp-silver-refresh-job:run`.
The URI has not been changed in this branch. A TODO comment in `scheduler.tf` marks the
pending switch. The scheduler remains `paused = true`.

The scheduler URI will not be switched until the dbt refresh path is fully deployed,
validated, and the switch is executed in a dedicated controlled evidence branch.

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

## Controlled Deployment Path (Future Branch)

The following steps must be executed in a dedicated controlled evidence branch, only after
Terraform resource ownership is confirmed:

1. **Build/push image** — dispatch `Build dbt Refresh Job Image` workflow to push the image
   to Artifact Registry.
2. **Terraform plan** — run `terraform plan` against `infra/terraform/gcp/` and confirm
   the Cloud Run Job resource is in the expected state.
3. **Terraform apply** — apply only in a dedicated controlled evidence branch/window, after
   plan review and explicit approval.
4. **Execute job manually** — only after Terraform ownership is accepted:
   `gcloud run jobs execute rtdp-dbt-refresh-job --region=europe-west1`.
5. **Validate dbt logs and API readback** — confirm dbt run + test success in Cloud Logging;
   confirm silver and gold aggregates are populated.
6. **Stop Cloud SQL** — return Cloud SQL to `NEVER / STOPPED`.
7. **Document evidence** — record all outputs, log excerpts, and API responses in an
   evidence document.

---

## Next Steps

1. **Execute controlled deployment validation** — credential contract resolved; proceed when ready
   using the controlled deployment path above.
2. **Switch scheduler** — in a separate branch after deployment evidence is accepted, update
   the scheduler URI from `rtdp-silver-refresh-job:run` to `rtdp-dbt-refresh-job:run`.
3. **Decommission silver refresh job** — only after the dbt path is fully validated and
   the scheduler switch is confirmed in production.
