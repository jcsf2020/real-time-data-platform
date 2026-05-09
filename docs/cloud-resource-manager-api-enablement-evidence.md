# Cloud Resource Manager API Enablement Evidence

## 1. Status

Cloud Resource Manager API enablement completed and validated.

| Item | Result |
| --- | --- |
| API enabled | Yes |
| API | `cloudresourcemanager.googleapis.com` |
| Project | `project-42987e01-2123-446b-ac7` |
| Trigger | Terraform Plan CI failure on IAM member refresh |
| Terraform HCL changed | No |
| Terraform import executed | No |
| `terraform apply` executed | No |
| IAM bindings changed | No |
| Cloud SQL final state | `NEVER STOPPED` |

---

## 2. Branch

```text
docs/cloud-resource-manager-api-enablement-evidence
```

---

## 3. Context

During PR `#83` for IAM member-level Terraform import, local validation passed, but the GitHub Actions Terraform Plan job failed while refreshing `google_project_iam_member` resources.

The failure happened in CI because the Terraform Plan workflow authenticates through Workload Identity Federation using:

```text
rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

Terraform needed to read the project IAM policy during `terraform plan` refresh. That requires the Cloud Resource Manager API.

---

## 4. CI Failure Observed

Failing check:

```text
Terraform Plan/Terraform plan (pull_request)
```

Relevant error:

```text
Error retrieving IAM policy for project "project-42987e01-2123-446b-ac7":
googleapi: Error 403: Cloud Resource Manager API has not been used in project 892892382088 before or it is disabled.
```

Service reported as disabled:

```text
cloudresourcemanager.googleapis.com
```

Reason:

```text
SERVICE_DISABLED
```

Affected Terraform resources included member-level IAM resources such as:

```text
google_project_iam_member.compute_artifactregistry_writer
google_project_iam_member.compute_cloudsql_client
google_project_iam_member.worker_cloudsql_client
google_project_iam_member.compute_logging_log_writer
google_project_iam_member.scheduler_run_invoker
google_project_iam_member.compute_storage_object_viewer
```

---

## 5. Pre-Enablement Check

Before enabling the API, the service list returned no enabled Cloud Resource Manager API entry:

```bash
gcloud services list \
  --project=project-42987e01-2123-446b-ac7 \
  --filter="config.name=cloudresourcemanager.googleapis.com" \
  --format="table(config.name,state)"
```

Observed result:

```text
<empty output>
```

---

## 6. Enablement Command Executed

```bash
gcloud services enable cloudresourcemanager.googleapis.com \
  --project=project-42987e01-2123-446b-ac7
```

Result:

```text
Operation "operations/acat.p2-892892382088-73e9fd00-a216-4438-a03b-41164137a9eb" finished successfully.
```

---

## 7. Post-Enablement Verification

Verification command:

```bash
gcloud services list \
  --project=project-42987e01-2123-446b-ac7 \
  --filter="config.name=cloudresourcemanager.googleapis.com" \
  --format="table(config.name,state)"
```

Result:

```text
NAME                                 STATE
cloudresourcemanager.googleapis.com  ENABLED
```

Cloud SQL safety check:

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Result:

```text
NEVER   STOPPED
```

---

## 8. CI Rerun Result

The failed Terraform Plan job was rerun:

```bash
gh run rerun 25598785273 --failed
```

PR checks after rerun:

```text
All checks were successful
0 cancelled, 0 failing, 3 successful, 0 skipped, and 0 pending checks
```

Successful checks:

```text
GitGuardian Security Checks
Terraform Plan/Terraform plan (pull_request)
CI/Validate workspace (pull_request)
```

---

## 9. Post-Merge Validation

After PR `#83` was merged into `main`, final validation confirmed:

```text
Terraform init: OK
Terraform validate: success
Terraform plan: No changes
pytest: 116 passed
ruff: clean
Cloud Resource Manager API: ENABLED
Cloud SQL final state: NEVER STOPPED
Git: ## main...origin/main
```

IAM member state confirmed:

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

---

## 10. Relation to Devil Advocate Audit

This evidence closes the immediate documentation gap identified after the IAM import phase.

The API enablement was not an IAM permission expansion. It was required so Terraform Plan CI could refresh member-level IAM resources through Cloud Resource Manager.

This improves the project in the following areas:

- CI reproducibility;
- IAM Terraform refresh reliability;
- auditability of real GCP API enablement changes;
- B2B evidence discipline;
- production-light operational transparency.

---

## 11. Explicit Non-Actions

The following actions were not performed in this API enablement step:

- No Terraform HCL change
- No `terraform import`
- No `terraform apply`
- No IAM binding addition
- No IAM binding removal
- No IAM authoritative policy use
- No IAM permission expansion
- No service account mutation
- No Workload Identity Federation pool or provider change
- No Secret Manager mutation
- No Cloud SQL start
- No Cloud SQL mutation
- No Cloud Run deployment
- No Cloud Run Job execution
- No Scheduler run
- No Pub/Sub publishing
- No application code changes
- No test changes

---

## 12. Acceptance Result

Accepted.

Cloud Resource Manager API is enabled because Terraform Plan CI requires it to refresh member-level project IAM resources.

The enablement fixed the CI Terraform Plan failure without changing IAM permissions or mutating runtime infrastructure.
