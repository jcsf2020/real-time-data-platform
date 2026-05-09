# Cloud Run Terraform Import Plan Evidence

## 1. Status

Cloud Run Terraform import completed and validated.

| Item | Result |
| --- | --- |
| Cloud Run services imported | Yes |
| Cloud Run job imported | Yes |
| Terraform plan | Zero diff |
| `terraform apply` executed | No |
| Cloud Run service deployment executed | No |
| Cloud Run job execution triggered | No |
| Cloud SQL final state | `NEVER STOPPED` |
| Scheduler final state | `PAUSED` |

---

## 2. Branch

```text
exec/cloud-run-terraform-import-plan
```

---

## 3. Scope

This execution branch imported the existing Cloud Run runtime resources into Terraform state and added matching HCL definitions.

Imported resources:

```text
google_cloud_run_v2_service.rtdp_api
google_cloud_run_v2_service.rtdp_pubsub_worker
google_cloud_run_v2_job.rtdp_silver_refresh_job
```

New Terraform files:

```text
infra/terraform/gcp/cloud_run_services.tf
infra/terraform/gcp/cloud_run_jobs.tf
```

The branch did not execute `terraform apply`. All live Cloud Run resources were imported into state only.

---

## 4. Preflight

Before adding Cloud Run HCL or importing resources, the branch started from a clean Terraform baseline.

Preflight results:

```text
Git branch: exec/cloud-run-terraform-import-plan
Terraform state before Cloud Run import: 11 existing resources
Terraform plan before Cloud Run HCL: No changes
Cloud Run services present: rtdp-api, rtdp-pubsub-worker
Cloud Run job present: rtdp-silver-refresh-job
Cloud SQL: NEVER STOPPED
```

Existing pre-import Terraform state resources were limited to Pub/Sub, Scheduler, Monitoring metrics, Monitoring dashboard, and alert policies.

---

## 5. HCL Added

### `cloud_run_services.tf`

Defines:

```text
google_cloud_run_v2_service.rtdp_api
google_cloud_run_v2_service.rtdp_pubsub_worker
```

The HCL preserves:

- service names;
- project and region;
- service accounts;
- container images;
- secret reference to `rtdp-database-url`;
- Cloud SQL connectivity via Cloud SQL volume and mount;
- container ports;
- CPU and memory limits;
- startup CPU boost;
- startup probes;
- scaling limits;
- traffic allocation to latest revision.

### `cloud_run_jobs.tf`

Defines:

```text
google_cloud_run_v2_job.rtdp_silver_refresh_job
```

The HCL preserves:

- job name;
- project and region;
- service account;
- container image;
- secret reference to `rtdp-database-url`;
- Cloud SQL connectivity via Cloud SQL volume and mount;
- CPU and memory limits;
- `task_count = 1`;
- `max_retries = 0`;
- `timeout = 300s`;
- Cloud Run gen2 execution annotation.

---

## 6. Import Commands Executed

### `rtdp-api`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_cloud_run_v2_service.rtdp_api \
  projects/project-42987e01-2123-446b-ac7/locations/europe-west1/services/rtdp-api
```

Result:

```text
Import successful.
```

### `rtdp-pubsub-worker`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_cloud_run_v2_service.rtdp_pubsub_worker \
  projects/project-42987e01-2123-446b-ac7/locations/europe-west1/services/rtdp-pubsub-worker
```

Result:

```text
Import successful.
```

### `rtdp-silver-refresh-job`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_cloud_run_v2_job.rtdp_silver_refresh_job \
  projects/project-42987e01-2123-446b-ac7/locations/europe-west1/jobs/rtdp-silver-refresh-job
```

Result:

```text
Import successful.
```

---

## 7. Drift Found and Resolved

### `rtdp-api`

Initial post-import plan showed an in-place update risk.

Drift areas:

```text
build_config
scaling
cpu_idle
startup_probe
Cloud SQL volume_mounts
Cloud SQL volumes
```

Resolution:

- HCL was aligned to imported Terraform state.
- `build_config.name` was not configured because it is a computed-only provider attribute.
- `build_config` is ignored in lifecycle because it is owned by the source deploy / gcloud build path.
- Cloud SQL connectivity was represented through volume and volume mount.
- Final plan for `rtdp-api` reached zero change.

### `rtdp-pubsub-worker`

Initial post-import plan showed an in-place update risk.

Drift areas:

```text
scaling
cpu_idle
startup_probe
Cloud SQL volume_mounts
Cloud SQL volumes
```

Resolution:

- HCL was aligned to imported Terraform state.
- Cloud SQL connectivity was represented through volume and volume mount.
- Final plan for `rtdp-pubsub-worker` reached zero change.

### `rtdp-silver-refresh-job`

Initial post-import plan showed an in-place update risk.

Drift areas:

```text
Cloud SQL volume_mounts
Cloud SQL volumes
```

Resolution:

- HCL was aligned to imported Terraform state.
- Cloud SQL connectivity was represented through volume and volume mount.
- Final plan for `rtdp-silver-refresh-job` reached zero change.

---

## 8. Final Terraform State

Final Cloud Run resources in Terraform state:

```text
google_cloud_run_v2_job.rtdp_silver_refresh_job
google_cloud_run_v2_service.rtdp_api
google_cloud_run_v2_service.rtdp_pubsub_worker
```

These resources now live in the GCS-backed Terraform state together with the previously imported Pub/Sub, Scheduler, and Monitoring resources.

---

## 9. Final Validation

Final validation commands executed:

```bash
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan
uv run pytest -q
uv run ruff check .
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)"
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Final validation results:

```text
terraform fmt -check -recursive infra/terraform/gcp: passed
terraform -chdir=infra/terraform/gcp validate: success
terraform -chdir=infra/terraform/gcp plan: No changes
uv run pytest -q: 116 passed
uv run ruff check .: clean
Scheduler final state: PAUSED
Cloud SQL final state: NEVER STOPPED
```

---

## 10. Explicit Non-Actions

The following actions were not performed:

- No `terraform apply`
- No Cloud Run deployment
- No Cloud Run service replacement
- No Cloud Run job replacement
- No Cloud Run job execution
- No Scheduler run
- No Cloud SQL start
- No Cloud SQL import
- No IAM import
- No Secret Manager import
- No Pub/Sub publishing
- No application code changes
- No test changes

---

## 11. Acceptance Result

Accepted.

Cloud Run services and the silver refresh Cloud Run job are now imported into Terraform state with final zero-diff plan.

Terraform now manages the following Cloud Run resources:

```text
google_cloud_run_v2_service.rtdp_api
google_cloud_run_v2_service.rtdp_pubsub_worker
google_cloud_run_v2_job.rtdp_silver_refresh_job
```

No infrastructure mutation was applied. The migration was state-only plus matching HCL.
