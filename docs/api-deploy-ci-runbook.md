

# API Deploy CI Runbook

Branch: docs/api-deploy-ci-runbook
Status: PLAN ONLY - NOT EXECUTED

## Objective

Define the controlled plan for adding Cloud Run deployment automation to the Real-Time Data Platform API service.

The deployment automation target is:

- Cloud Run service: rtdp-api
- Dockerfile: Dockerfile
- Entrypoint: rtdp-api
- Artifact Registry repository: europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp
- Target image name: rtdp-api
- Target image tag strategy: Git commit SHA

## Current API State

| Field | Value |
|---|---|
| Cloud Run service | rtdp-api |
| Current revision | rtdp-api-00006-gd8 |
| Current image source | cloud-run-source-deploy |
| Current image | europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/cloud-run-source-deploy/rtdp-api@sha256:0b44c36a71b305653dfe85a74d98075ae238bf19458917412d95a3a29515af78 |
| Runtime service account | 892892382088-compute@developer.gserviceaccount.com |
| DATABASE_URL secret | rtdp-database-url:latest |
| SERVICE_NAME | rtdp-api |
| SERVICE_VERSION | 0.1.0-pagination-fix |
| ENVIRONMENT | gcp-cloud-run |
| Cloud SQL instance | project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres |
| Container concurrency | 80 |
| Max scale annotation | 20 |
| Min scale | 0 |

## Problem Being Solved

The API is still deployed from the Cloud Run source deployment path.

That weakens deployment traceability because the API runtime image is not managed through the same auditable GitHub Actions to Artifact Registry to Cloud Run path now validated for the Pub/Sub worker.

The target production-readiness improvement is to deploy the API using immutable commit-SHA image tags from the project-specific Artifact Registry repository.

## Key Difference From Worker

The Pub/Sub worker uses a dedicated runtime service account:

```text
rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

The API currently uses the default compute service account:

```text
892892382088-compute@developer.gserviceaccount.com
```

Current IAM inspection shows:

- rtdp-cloud-run-deploy-ci has project-level roles:
  - roles/artifactregistry.writer
  - roles/run.developer
- rtdp-cloud-run-deploy-ci has serviceAccountUser on:
  - rtdp-worker-sa
- rtdp-cloud-run-deploy-ci does not currently have serviceAccountUser on:
  - 892892382088-compute@developer.gserviceaccount.com

Therefore, API deployment automation must not be created until the missing runtime service account impersonation permission is added or the API runtime service account is intentionally changed in a separate scoped branch.

## Required Prerequisite Branch

Before creating the API deploy workflow, create a Terraform branch to add:

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

Expected Terraform resource:

```hcl
resource "google_service_account_iam_member" "cloud_run_deploy_ci_api_service_account_user" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/892892382088-compute@developer.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = local.cloud_run_deploy_ci_member
}
```

This branch must include:

- Terraform fmt
- Terraform validate
- Terraform plan showing only the new service account IAM binding
- Terraform apply
- Final zero-diff Terraform plan
- Cloud SQL final state: NEVER STOPPED
- Evidence document

## Future API Deploy Workflow

Future workflow file:

```text
.github/workflows/deploy-api-cloud-run.yml
```

Initial trigger:

```text
workflow_dispatch
```

Future optional trigger after successful manual validation:

```text
push to main
```

with paths limited to:

- Dockerfile
- apps/api/**
- packages/**
- pyproject.toml
- uv.lock
- .github/workflows/deploy-api-cloud-run.yml

## Proposed Image

```text
europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-api:${GITHUB_SHA}
```

## Runtime Configuration To Preserve

The future deploy command must explicitly preserve:

```text
--service-account=892892382088-compute@developer.gserviceaccount.com
--set-secrets=DATABASE_URL=rtdp-database-url:latest
--set-env-vars=SERVICE_NAME=rtdp-api,SERVICE_VERSION=0.1.0-pagination-fix,ENVIRONMENT=gcp-cloud-run
--add-cloudsql-instances=project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres
--concurrency=80
--max-instances=20
```

## Required Post-Deploy Checks

The future workflow must fail automatically unless all checks pass:

| Check | Expected |
|---|---|
| deployed image | IMAGE_URI |
| runtime service account | 892892382088-compute@developer.gserviceaccount.com |
| DATABASE_URL secret | rtdp-database-url:latest |
| SERVICE_NAME | rtdp-api |
| SERVICE_VERSION | 0.1.0-pagination-fix |
| ENVIRONMENT | gcp-cloud-run |
| Cloud SQL annotation | project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres |
| container concurrency | 80 |
| max scale annotation | 20 |

## Out Of Scope For This Runbook Branch

- No workflow creation
- No Terraform change
- No terraform apply
- No IAM mutation
- No Cloud Run deployment
- No image push
- No Cloud SQL start or mutation
- No Pub/Sub mutation
- No Scheduler mutation
- No API runtime service account migration

## Production Readiness Impact

This runbook defines the safe API deploy CI path without skipping the required IAM prerequisite.

The next branch should close the API runtime service account impersonation prerequisite through Terraform before creating the API deployment workflow.
