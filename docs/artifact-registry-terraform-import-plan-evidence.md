# Artifact Registry - Terraform Import Plan Evidence

Branch: feat/terraform-artifact-registry-iac
Status: ZERO-DIFF PLAN CONFIRMED - NOT APPLIED

## Objective

Import the existing project-specific Artifact Registry repository rtdp into Terraform state.

This closes the Terraform coverage gap for the container image registry used by the Real-Time Data Platform Cloud Run workloads.

## Target Resource

| Field | Value |
|---|---|
| Repository ID | rtdp |
| Location | europe-west1 |
| Format | DOCKER |
| Mode | STANDARD_REPOSITORY |
| Description | Real-Time Data Platform container images |
| Registry URI | europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp |
| Encryption | Google-managed key |
| Vulnerability scanning | SCANNING_DISABLED |

cloud-run-source-deploy was intentionally not imported because it is not the project-specific RTDP image registry.

## Terraform HCL Added

File: infra/terraform/gcp/artifact_registry.tf

Resource: google_artifact_registry_repository.rtdp

Configured fields:

- project = var.project_id
- location = var.region
- repository_id = rtdp
- format = DOCKER
- description = Real-Time Data Platform container images
- lifecycle prevent_destroy = true

## Import Command Executed

terraform -chdir=infra/terraform/gcp import google_artifact_registry_repository.rtdp projects/project-42987e01-2123-446b-ac7/locations/europe-west1/repositories/rtdp

Result: Import successful.

## Terraform State Confirmation

Resource now present in Terraform state:

google_artifact_registry_repository.rtdp

Confirmed state values:

- format = DOCKER
- location = europe-west1
- mode = STANDARD_REPOSITORY
- project = project-42987e01-2123-446b-ac7
- repository_id = rtdp
- kms_key_name = null
- vulnerability scanning = SCANNING_DISABLED

## Terraform Plan Result

terraform -chdir=infra/terraform/gcp plan -detailed-exitcode

Result:

No changes. Your infrastructure matches the configuration.

terraform_plan_exit_code=0

## Safety Constraints Respected

| Constraint | Status |
|---|---|
| No terraform apply executed | OK |
| No IAM changes | OK |
| No Cloud Run deployment | OK |
| No Container Scanning API enablement | OK |
| No import of cloud-run-source-deploy | OK |
| No cleanup policy change | OK |
| No runtime mutation | OK |
| prevent_destroy added | OK |

## Explicit Non-Actions

- No terraform apply
- No IAM binding addition
- No IAM binding removal
- No Container Scanning enablement
- No image push
- No image deletion
- No cleanup policy configuration
- No Cloud Run service update
- No Cloud Run job update
- No Cloud SQL start
- No Cloud SQL mutation
- No Pub/Sub mutation
- No Scheduler mutation
- No application code change

## Production Readiness Impact

This closes the Artifact Registry Terraform coverage gap.

The project-specific Docker image repository is now represented in Terraform state with a zero-diff plan, without changing IAM, image lifecycle, scanning configuration, or runtime workloads.

This prepares the next production-readiness step: immutable image tagging and Cloud Run deployment automation.
