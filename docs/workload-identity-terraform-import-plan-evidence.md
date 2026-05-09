# Workload Identity Federation - Terraform Import Plan Evidence

**Branch:** `feat/terraform-workload-identity-iac`
**Date:** 2026-05-09
**Status:** ZERO-DIFF PLAN CONFIRMED - NOT APPLIED

---

## Objective

Add `google_iam_workload_identity_pool` and `google_iam_workload_identity_pool_provider` to
Terraform state so GCP Workload Identity Federation is fully managed under IaC.

These resources back the GitHub Actions OIDC authentication used by the Terraform Plan CI
workflow. Importing them closes the last security-critical gap in Terraform coverage.

---

## Pre-import Live Resource Discovery

```
$ gcloud iam workload-identity-pools describe github-actions \
    --location=global \
    --project=project-42987e01-2123-446b-ac7 \
    --format=yaml

displayName: GitHub Actions
name: projects/892892382088/locations/global/workloadIdentityPools/github-actions
state: ACTIVE
```

```
$ gcloud iam workload-identity-pools providers list \
    --workload-identity-pool=github-actions \
    --location=global \
    --project=project-42987e01-2123-446b-ac7 \
    --format=yaml

attributeCondition: assertion.repository=='jcsf2020/real-time-data-platform'
attributeMapping:
  attribute.actor: assertion.actor
  attribute.ref: assertion.ref
  attribute.repository: assertion.repository
  google.subject: assertion.sub
displayName: GitHub OIDC Provider
name: projects/892892382088/locations/global/workloadIdentityPools/github-actions/providers/github
oidc:
  issuerUri: https://token.actions.githubusercontent.com
state: ACTIVE
```

---

## HCL Added

**File:** `infra/terraform/gcp/workload_identity.tf`

```hcl
resource "google_iam_workload_identity_pool" "github_actions" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC Provider"
  attribute_condition                = "assertion.repository=='jcsf2020/real-time-data-platform'"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.ref"        = "assertion.ref"
    "attribute.repository" = "assertion.repository"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  lifecycle {
    prevent_destroy = true
  }
}
```

---

## Terraform Validate

```
$ terraform -chdir=infra/terraform/gcp validate
Success! The configuration is valid.
```

---

## Import Commands Executed

```
$ terraform -chdir=infra/terraform/gcp import \
    google_iam_workload_identity_pool.github_actions \
    "projects/project-42987e01-2123-446b-ac7/locations/global/workloadIdentityPools/github-actions"

google_iam_workload_identity_pool.github_actions: Importing from ID "..."
google_iam_workload_identity_pool.github_actions: Import prepared!
  Prepared google_iam_workload_identity_pool for import
google_iam_workload_identity_pool.github_actions: Refreshing state...

Import successful!
```

```
$ terraform -chdir=infra/terraform/gcp import \
    google_iam_workload_identity_pool_provider.github \
    "projects/project-42987e01-2123-446b-ac7/locations/global/workloadIdentityPools/github-actions/providers/github"

google_iam_workload_identity_pool_provider.github: Importing from ID "..."
google_iam_workload_identity_pool_provider.github: Import prepared!
  Prepared google_iam_workload_identity_pool_provider for import
google_iam_workload_identity_pool_provider.github: Refreshing state...

Import successful!
```

---

## Terraform Plan - Zero Diff Confirmed

```
$ terraform -chdir=infra/terraform/gcp plan -detailed-exitcode

No changes. Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your configuration
and found no differences, so no changes are needed.

exit_code=0
```

All 28 resources refreshed with no pending changes.

---

## Safety Constraints Respected

| Constraint | Status |
|---|---|
| No `terraform apply` executed | OK |
| No IAM permissions changed | OK |
| No GitHub Actions workflow modified | OK |
| No runtime resources touched | OK |
| `prevent_destroy = true` on both resources | OK |
| `authoritative` IAM policy/binding resources not used | OK |
| Unrelated Terraform files not modified | OK |

---

## IaC Coverage After This Import

| Resource type | Managed in Terraform |
|---|---|
| `google_iam_workload_identity_pool` | OK This branch |
| `google_iam_workload_identity_pool_provider` | OK This branch |
| `google_service_account` (x4) | OK PR #82 |
| `google_project_iam_member` (x7) | OK PR #83 |
| `google_service_account_iam_member` | OK PR #83 |
| `google_pubsub_topic` (x2) | OK PR #68 |
| `google_pubsub_subscription` | OK PR #68 |
| `google_cloud_scheduler_job` | OK PR #68 |
| `google_cloud_run_v2_service` (x2) | OK PR #78 |
| `google_cloud_run_v2_job` | OK PR #78 |
| `google_sql_database_instance` | OK PR #80 |
| `google_secret_manager_secret` | OK PR #81 |
| `google_logging_metric` (x4) | OK PR #72 |
| `google_monitoring_dashboard` | OK PR #72 |
| `google_monitoring_alert_policy` (x2) | OK PR #72 |
