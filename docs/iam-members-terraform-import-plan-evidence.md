# IAM Members Terraform Import Plan Evidence

## 1. Status

IAM member-level Terraform import completed and validated.

| Item | Result |
| --- | --- |
| Project IAM members imported | Yes |
| Service account IAM member imported | Yes |
| Authoritative IAM policy used | No |
| Authoritative IAM binding used | No |
| Terraform plan | Zero diff |
| `terraform apply` executed | No |
| IAM permissions mutated | No |
| Cloud SQL final state | `NEVER STOPPED` |

---

## 2. Branch

```text
exec/iam-members-terraform-import-plan
```

---

## 3. Scope

This execution branch imported only existing IAM member-level bindings into Terraform state and added matching non-authoritative HCL.

Imported project-level IAM resources:

```text
google_project_iam_member.compute_artifactregistry_writer
google_project_iam_member.compute_cloudsql_client
google_project_iam_member.worker_cloudsql_client
google_project_iam_member.compute_logging_log_writer
google_project_iam_member.scheduler_run_invoker
google_project_iam_member.compute_storage_object_viewer
google_project_iam_member.terraform_plan_ci_viewer
```

Imported service-account-level IAM resource:

```text
google_service_account_iam_member.terraform_plan_ci_workload_identity_user
```

New Terraform file:

```text
infra/terraform/gcp/iam.tf
```

The branch did not use `google_project_iam_policy`, `google_project_iam_binding`, or any authoritative IAM resource that could replace unrelated members.

---

## 4. Preflight

Before adding IAM HCL or importing resources, the branch started from a clean Terraform baseline.

Preflight results:

```text
Git branch: exec/iam-members-terraform-import-plan
Terraform plan before IAM HCL: No changes
Cloud SQL final state: NEVER STOPPED
```

Existing pre-import Terraform state resources included Pub/Sub, Scheduler, Monitoring, Cloud Run, Cloud SQL, Secret Manager metadata, and custom service accounts.

---

## 5. IAM Inventory

Relevant project-level IAM bindings observed before import:

| Role | Member |
| --- | --- |
| `roles/artifactregistry.writer` | `serviceAccount:892892382088-compute@developer.gserviceaccount.com` |
| `roles/cloudsql.client` | `serviceAccount:892892382088-compute@developer.gserviceaccount.com` |
| `roles/cloudsql.client` | `serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| `roles/logging.logWriter` | `serviceAccount:892892382088-compute@developer.gserviceaccount.com` |
| `roles/run.invoker` | `serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| `roles/storage.objectViewer` | `serviceAccount:892892382088-compute@developer.gserviceaccount.com` |
| `roles/viewer` | `serviceAccount:rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |

Relevant service-account-level IAM binding observed before import:

| Service account | Role | Member |
| --- | --- | --- |
| `rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | `roles/iam.workloadIdentityUser` | `principalSet://iam.googleapis.com/projects/892892382088/locations/global/workloadIdentityPools/github-actions/attribute.repository/jcsf2020/real-time-data-platform` |

The service account IAM policies for `rtdp-scheduler-sa`, `rtdp-worker-sa`, and `rtdp-pubsub-push-sa` had no relevant bindings beyond empty policy metadata.

---

## 6. HCL Added

`infra/terraform/gcp/iam.tf` defines:

```text
google_project_iam_member.compute_artifactregistry_writer
google_project_iam_member.compute_cloudsql_client
google_project_iam_member.worker_cloudsql_client
google_project_iam_member.compute_logging_log_writer
google_project_iam_member.scheduler_run_invoker
google_project_iam_member.compute_storage_object_viewer
google_project_iam_member.terraform_plan_ci_viewer
google_service_account_iam_member.terraform_plan_ci_workload_identity_user
```

The HCL uses only member-level IAM resources.

The HCL preserves:

- existing roles;
- existing members;
- existing project ID references;
- existing Workload Identity principal for GitHub Actions Terraform Plan CI.

No authoritative IAM policy or IAM binding resource is defined.

---

## 7. Import Commands Executed

### `compute_artifactregistry_writer`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_project_iam_member.compute_artifactregistry_writer \
  "project-42987e01-2123-446b-ac7 roles/artifactregistry.writer serviceAccount:892892382088-compute@developer.gserviceaccount.com"
```

Result:

```text
Import successful.
```

### `compute_cloudsql_client`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_project_iam_member.compute_cloudsql_client \
  "project-42987e01-2123-446b-ac7 roles/cloudsql.client serviceAccount:892892382088-compute@developer.gserviceaccount.com"
```

Result:

```text
Import successful.
```

### `worker_cloudsql_client`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_project_iam_member.worker_cloudsql_client \
  "project-42987e01-2123-446b-ac7 roles/cloudsql.client serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
```

Result:

```text
Import successful.
```

### `compute_logging_log_writer`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_project_iam_member.compute_logging_log_writer \
  "project-42987e01-2123-446b-ac7 roles/logging.logWriter serviceAccount:892892382088-compute@developer.gserviceaccount.com"
```

Result:

```text
Import successful.
```

### `scheduler_run_invoker`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_project_iam_member.scheduler_run_invoker \
  "project-42987e01-2123-446b-ac7 roles/run.invoker serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
```

Result:

```text
Import successful.
```

### `compute_storage_object_viewer`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_project_iam_member.compute_storage_object_viewer \
  "project-42987e01-2123-446b-ac7 roles/storage.objectViewer serviceAccount:892892382088-compute@developer.gserviceaccount.com"
```

Result:

```text
Import successful.
```

### `terraform_plan_ci_viewer`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_project_iam_member.terraform_plan_ci_viewer \
  "project-42987e01-2123-446b-ac7 roles/viewer serviceAccount:rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
```

Result:

```text
Import successful.
```

### `terraform_plan_ci_workload_identity_user`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_service_account_iam_member.terraform_plan_ci_workload_identity_user \
  "projects/project-42987e01-2123-446b-ac7/serviceAccounts/rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com roles/iam.workloadIdentityUser principalSet://iam.googleapis.com/projects/892892382088/locations/global/workloadIdentityPools/github-actions/attribute.repository/jcsf2020/real-time-data-platform"
```

Result:

```text
Import successful.
```

---

## 8. Drift Found and Resolved

Post-import Terraform plan returned zero diff immediately.

```text
No changes. Your infrastructure matches the configuration.
```

No HCL drift correction was required after import.

---

## 9. Final Terraform State

Final IAM member resources in Terraform state:

```text
google_project_iam_member.compute_artifactregistry_writer
google_project_iam_member.compute_cloudsql_client
google_project_iam_member.compute_logging_log_writer
google_project_iam_member.compute_storage_object_viewer
google_project_iam_member.scheduler_run_invoker
google_project_iam_member.terraform_plan_ci_viewer
google_project_iam_member.worker_cloudsql_client
google_service_account_iam_member.terraform_plan_ci_workload_identity_user
```

These resources now live in the GCS-backed Terraform state together with the previously imported Pub/Sub, Scheduler, Monitoring, Cloud Run, Cloud SQL, Secret Manager metadata, and custom service account resources.

---

## 10. Final Validation

Final validation commands executed:

```bash
terraform -chdir=infra/terraform/gcp state list | grep "_iam_member"
terraform -chdir=infra/terraform/gcp plan
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Final validation results:

```text
google_project_iam_member.compute_artifactregistry_writer
google_project_iam_member.compute_cloudsql_client
google_project_iam_member.compute_logging_log_writer
google_project_iam_member.compute_storage_object_viewer
google_project_iam_member.scheduler_run_invoker
google_project_iam_member.terraform_plan_ci_viewer
google_project_iam_member.worker_cloudsql_client
google_service_account_iam_member.terraform_plan_ci_workload_identity_user
terraform -chdir=infra/terraform/gcp plan: No changes
Cloud SQL final state: NEVER STOPPED
```

---

## 11. Explicit Non-Actions

The following actions were not performed:

- No `terraform apply`
- No `google_project_iam_policy`
- No `google_project_iam_binding`
- No authoritative IAM policy replacement
- No authoritative IAM binding replacement
- No IAM permission mutation
- No IAM member deletion
- No broad role grant beyond existing observed bindings
- No Owner or Editor grant
- No service account key creation
- No service account creation
- No service account deletion
- No Workload Identity Federation pool or provider change
- No Terraform Plan CI permission expansion beyond existing observed bindings
- No Cloud SQL start
- No Cloud SQL mutation
- No Secret Manager mutation
- No Scheduler run
- No Cloud Run Job execution
- No Pub/Sub publishing
- No application code changes
- No test changes

---

## 12. Acceptance Result

Accepted.

Relevant RTDP IAM member-level bindings are now imported into Terraform state with final zero-diff plan.

Terraform now manages the following IAM member resources:

```text
google_project_iam_member.compute_artifactregistry_writer
google_project_iam_member.compute_cloudsql_client
google_project_iam_member.worker_cloudsql_client
google_project_iam_member.compute_logging_log_writer
google_project_iam_member.scheduler_run_invoker
google_project_iam_member.compute_storage_object_viewer
google_project_iam_member.terraform_plan_ci_viewer
google_service_account_iam_member.terraform_plan_ci_workload_identity_user
```

No infrastructure mutation was applied. The migration was state-only plus matching member-level HCL. IAM policy remains non-authoritative.
