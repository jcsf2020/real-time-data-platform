

# Cloud Run Deploy CI Service Account Evidence

Branch: feat/cloud-run-deploy-ci-service-account
Status: APPLIED - ZERO-DIFF PLAN CONFIRMED

## Objective

Create a dedicated GitHub Actions service account for future Cloud Run worker deployment automation.

This prepares the next deployment automation phase without reusing the Terraform Plan CI service account or the Cloud Run runtime service account.

## Resources Created

| Resource | Purpose |
|---|---|
| google_service_account.rtdp_cloud_run_deploy_ci | Dedicated deploy identity for GitHub Actions |
| google_project_iam_member.cloud_run_deploy_ci_artifactregistry_writer | Allows image push to Artifact Registry |
| google_project_iam_member.cloud_run_deploy_ci_run_developer | Allows Cloud Run service deployment/update |
| google_service_account_iam_member.cloud_run_deploy_ci_workload_identity_user | Allows GitHub Actions OIDC to impersonate the deploy service account |
| google_service_account_iam_member.cloud_run_deploy_ci_worker_service_account_user | Allows deploy service account to deploy revisions using rtdp-worker-sa as runtime identity |

## Initial Plan

The initial Terraform plan showed:

```text
Plan: 5 to add, 0 to change, 0 to destroy.
```

Full plan evidence is stored at:

```text
docs/evidence/cloud-run-deploy-ci-service-account/terraform-plan.txt
```

## Apply Notes

The first apply partially succeeded and failed on the worker serviceAccountUser binding because the deploy service account had just been created and was not yet visible for that IAM operation.

The Terraform graph was corrected with explicit depends_on relationships for IAM resources that reference the new service account through a local string.

The second apply created the remaining IAM binding successfully.

## Final State

Service account:

```text
rtdp-cloud-run-deploy-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com RTDP Cloud Run Deploy CI
```

Project IAM grants:

```text
roles/artifactregistry.writer
roles/run.developer
```

Worker service account IAM grant:

```text
roles/iam.serviceAccountUser on rtdp-worker-sa
member: serviceAccount:rtdp-cloud-run-deploy-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

Deploy service account Workload Identity grant:

```text
roles/iam.workloadIdentityUser
member: principalSet://iam.googleapis.com/projects/892892382088/locations/global/workloadIdentityPools/github-actions/attribute.repository/jcsf2020/real-time-data-platform
```

## Final Validation

| Check | Result |
|---|---|
| terraform fmt -check -recursive infra/terraform/gcp | OK |
| terraform validate | OK |
| terraform plan -detailed-exitcode | exit_code=0 |
| uv run pytest -q | 116 passed |
| uv run ruff check . | OK |
| Cloud SQL final state | NEVER STOPPED |

## Safety Constraints

| Constraint | Status |
|---|---|
| Dedicated deploy identity used | OK |
| Terraform Plan CI service account not reused | OK |
| Runtime worker service account not reused as deployer | OK |
| No Cloud Run deployment executed | OK |
| No image pushed | OK |
| No Container Scanning change | OK |
| No Cloud SQL start or mutation | OK |
| No Pub/Sub mutation | OK |
| No Scheduler mutation | OK |

## Production Readiness Impact

This closes the identity and permission prerequisite for a future manual GitHub Actions Cloud Run worker deployment workflow.

The next branch can now create the deployment workflow using this service account:

```text
rtdp-cloud-run-deploy-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```
