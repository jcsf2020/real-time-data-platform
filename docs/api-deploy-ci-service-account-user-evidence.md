

# API Deploy CI Service Account User Evidence

Branch: feat/api-deploy-ci-service-account-user
Status: APPLIED - ZERO-DIFF PLAN CONFIRMED

## Objective

Grant the dedicated Cloud Run deploy CI service account permission to deploy the API service while preserving the current API runtime service account.

This closes the IAM prerequisite identified in the API deploy CI runbook before creating the API deployment workflow.

## Scope

This branch adds only one Terraform-managed IAM binding:

```text
roles/iam.serviceAccountUser
```

on:

```text
892892382088-compute@developer.gserviceaccount.com
```

for:

```text
rtdp-cloud-run-deploy-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

## Terraform Resource Added

```hcl
resource "google_service_account_iam_member" "cloud_run_deploy_ci_api_service_account_user" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/892892382088-compute@developer.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = local.cloud_run_deploy_ci_member

  depends_on = [
    google_service_account.rtdp_cloud_run_deploy_ci,
  ]
}
```

## Initial Plan

The Terraform plan showed exactly:

```text
Plan: 1 to add, 0 to change, 0 to destroy.
```

Full plan evidence is stored at:

```text
docs/evidence/api-deploy-ci-service-account-user/terraform-plan.txt
```

## Apply Result

Terraform applied successfully:

```text
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

## Final IAM State

Default compute service account policy now includes:

```text
roles/iam.serviceAccountUser
member: serviceAccount:rtdp-cloud-run-deploy-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

## Final Validation

| Check | Result |
|---|---|
| terraform fmt -check -recursive infra/terraform/gcp | OK |
| terraform validate | OK |
| Initial terraform plan | 1 to add, 0 to change, 0 to destroy |
| terraform apply | 1 added, 0 changed, 0 destroyed |
| Final terraform plan | zero-diff |
| terraform_plan_exit_code | 0 |
| Cloud SQL final state | NEVER STOPPED |

## Safety Constraints

| Constraint | Status |
|---|---|
| Dedicated deploy identity used | OK |
| Terraform Plan CI service account not reused | OK |
| API runtime service account not reused as deployer | OK |
| No Cloud Run deployment executed | OK |
| No image pushed | OK |
| No Cloud SQL start or mutation | OK |
| No Pub/Sub mutation | OK |
| No Scheduler mutation | OK |

## Production Readiness Impact

This closes the API deployment IAM prerequisite.

The API deploy workflow can now be created in a separate branch using the dedicated deploy service account while preserving the current API runtime service account.
