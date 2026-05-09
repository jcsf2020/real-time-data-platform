# Service Accounts Terraform Import Plan Evidence

## 1. Status

Service Accounts Terraform import completed and validated.

| Item | Result |
| --- | --- |
| Custom service accounts imported | Yes |
| Default compute service account imported | No |
| IAM bindings imported | No |
| Terraform plan | Zero diff |
| `terraform apply` executed | No |
| Service accounts replaced | No |
| Cloud SQL final state | `NEVER STOPPED` |

---

## 2. Branch

```text
exec/service-accounts-terraform-import-plan
```

---

## 3. Scope

This execution branch imported only the existing custom IAM service accounts into Terraform state and added matching HCL.

Imported resources:

```text
google_service_account.rtdp_scheduler_sa
google_service_account.rtdp_worker_sa
google_service_account.rtdp_pubsub_push_sa
google_service_account.rtdp_terraform_plan_ci
```

New Terraform file:

```text
infra/terraform/gcp/service_accounts.tf
```

The branch did not import the Google-managed default compute service account and did not import or modify IAM bindings.

---

## 4. Preflight

Before adding service account HCL or importing resources, the branch started from a clean Terraform baseline.

Preflight results:

```text
Git branch: exec/service-accounts-terraform-import-plan
Terraform plan before Service Account HCL: No changes
Cloud SQL final state: NEVER STOPPED
```

Existing pre-import Terraform state resources included Pub/Sub, Scheduler, Monitoring, Cloud Run, Cloud SQL, and Secret Manager metadata.

---

## 5. Service Accounts Inventory

Custom service accounts imported in this branch:

| Service account | Display name | Disabled |
| --- | --- | --- |
| `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | `RTDP Cloud Scheduler caller for silver refresh job` | `False` |
| `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | `RTDP PubSub Worker` | `False` |
| `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | `RTDP PubSub Push Invoker` | `False` |
| `rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | `RTDP Terraform Plan CI` | `False` |

Google-managed service account intentionally not imported:

```text
892892382088-compute@developer.gserviceaccount.com
```

The default compute service account is referenced by runtime resources but is not managed as a created custom `google_service_account` resource in this branch.

---

## 6. HCL Added

`infra/terraform/gcp/service_accounts.tf` defines:

```text
google_service_account.rtdp_scheduler_sa
google_service_account.rtdp_worker_sa
google_service_account.rtdp_pubsub_push_sa
google_service_account.rtdp_terraform_plan_ci
```

The HCL preserves:

- account IDs;
- project reference;
- display names;
- Terraform `prevent_destroy` lifecycle guards.

No IAM role bindings are defined in this file.

---

## 7. Import Commands Executed

### `rtdp-scheduler-sa`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_service_account.rtdp_scheduler_sa \
  projects/project-42987e01-2123-446b-ac7/serviceAccounts/rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

Result:

```text
Import successful.
```

### `rtdp-worker-sa`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_service_account.rtdp_worker_sa \
  projects/project-42987e01-2123-446b-ac7/serviceAccounts/rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

Result:

```text
Import successful.
```

### `rtdp-pubsub-push-sa`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_service_account.rtdp_pubsub_push_sa \
  projects/project-42987e01-2123-446b-ac7/serviceAccounts/rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

Result:

```text
Import successful.
```

### `rtdp-terraform-plan-ci`

```bash
terraform -chdir=infra/terraform/gcp import \
  google_service_account.rtdp_terraform_plan_ci \
  projects/project-42987e01-2123-446b-ac7/serviceAccounts/rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
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

Final service account resources in Terraform state:

```text
google_service_account.rtdp_pubsub_push_sa
google_service_account.rtdp_scheduler_sa
google_service_account.rtdp_terraform_plan_ci
google_service_account.rtdp_worker_sa
```

These resources now live in the GCS-backed Terraform state together with the previously imported Pub/Sub, Scheduler, Monitoring, Cloud Run, Cloud SQL, and Secret Manager metadata resources.

---

## 10. Final Validation

Final validation commands executed:

```bash
terraform -chdir=infra/terraform/gcp state list | grep "google_service_account"
terraform -chdir=infra/terraform/gcp plan
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Final validation results:

```text
google_service_account.rtdp_pubsub_push_sa
google_service_account.rtdp_scheduler_sa
google_service_account.rtdp_terraform_plan_ci
google_service_account.rtdp_worker_sa
terraform -chdir=infra/terraform/gcp plan: No changes
Cloud SQL final state: NEVER STOPPED
```

---

## 11. Explicit Non-Actions

The following actions were not performed:

- No `terraform apply`
- No default compute service account import
- No IAM binding import
- No IAM policy update
- No service account creation
- No service account deletion
- No service account replacement
- No service account key creation
- No Workload Identity Federation change
- No Terraform Plan CI permission expansion
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

The custom RTDP service accounts are now imported into Terraform state with final zero-diff plan.

Terraform now manages the following custom service accounts:

```text
google_service_account.rtdp_scheduler_sa
google_service_account.rtdp_worker_sa
google_service_account.rtdp_pubsub_push_sa
google_service_account.rtdp_terraform_plan_ci
```

No infrastructure mutation was applied. The migration was state-only plus matching HCL. IAM role bindings remain out of scope for this branch.
