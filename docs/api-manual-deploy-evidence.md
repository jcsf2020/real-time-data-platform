# API Manual Deploy Evidence

Branch: evidence/api-manual-deploy
Status: MANUAL DEPLOY SUCCEEDED AFTER WORKFLOW FIX

## Objective

Execute the manual GitHub Actions Cloud Run deployment workflow for the API service and capture evidence.

This validates the deployment path:

```text
GitHub Actions -> Artifact Registry -> Cloud Run
```

for:

```text
rtdp-api
```

## Context

The first API manual deploy attempt failed because the workflow referenced the wrong runtime service account format.

The failed workflow attempted to use:

```text
892892382088-compute@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

The actual API runtime service account is:

```text
892892382088-compute@developer.gserviceaccount.com
```

The failure was captured and preserved as evidence before fixing the workflow.

The workflow was then fixed in PR #95 and re-executed successfully.

## Workflow Runs

| Run ID | Result | Purpose |
|---|---|---|
| 25637933908 | failure | Initial deploy attempt; failed due to wrong runtime service account |
| 25638169193 | success | Corrected deploy attempt after workflow fix |

## Failed Attempt Evidence

The first deploy attempt failed with:

```text
PERMISSION_DENIED: Permission 'iam.serviceaccounts.actAs' denied on service account 892892382088-compute@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

This confirmed the workflow bug was in the service account email used by the deploy command, not in the Terraform IAM binding.

Evidence files:

```text
docs/evidence/api-manual-deploy/workflow-run-25637933908-failed.txt
docs/evidence/api-manual-deploy/failed-deploy-validation.txt
```

## Successful Workflow Run

| Field | Value |
|---|---|
| Workflow | Deploy API to Cloud Run |
| Workflow file | .github/workflows/deploy-api-cloud-run.yml |
| Run ID | 25638169193 |
| Trigger | workflow_dispatch |
| Ref | main |
| Result | success |

Full successful workflow log evidence:

```text
docs/evidence/api-manual-deploy/workflow-run-25638169193.txt
```

## Image Built And Pushed

| Field | Value |
|---|---|
| Image | europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-api |
| Tag | 66ac7fef54496bc11635f946928d4a9afe8ecfcb |
| Digest | sha256:319510547f9003e70db8317ea4f82345c3ff665a6e4dc657d18b15ab495b53c5 |
| Registry | Artifact Registry rtdp |
| Region | europe-west1 |

## Cloud Run Deployment Result

| Field | Before | After |
|---|---|---|
| Service | rtdp-api | rtdp-api |
| Revision | rtdp-api-00006-gd8 | rtdp-api-00007-9gd |
| Image | cloud-run-source-deploy/rtdp-api@sha256:0b44c36a71b305653dfe85a74d98075ae238bf19458917412d95a3a29515af78 | rtdp/rtdp-api:66ac7fef54496bc11635f946928d4a9afe8ecfcb |
| Runtime service account | 892892382088-compute@developer.gserviceaccount.com | 892892382088-compute@developer.gserviceaccount.com |
| DATABASE_URL secret | rtdp-database-url:latest | rtdp-database-url:latest |
| SERVICE_NAME | rtdp-api | rtdp-api |
| SERVICE_VERSION | 0.1.0-pagination-fix | 0.1.0-pagination-fix |
| ENVIRONMENT | gcp-cloud-run | gcp-cloud-run |
| Cloud SQL instance | project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres | project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres |
| Container concurrency | 80 | 80 |
| Max scale annotation | 20 | 20 |

## Validation

| Check | Result |
|---|---|
| Workflow completed | success |
| API image built from Dockerfile | OK |
| Artifact Registry SHA tag exists | OK |
| Cloud Run new revision deployed | OK |
| Cloud Run serving traffic | 100 percent |
| Runtime service account preserved | OK |
| DATABASE_URL secret preserved | OK |
| SERVICE_NAME preserved | OK |
| SERVICE_VERSION preserved | OK |
| ENVIRONMENT preserved | OK |
| Cloud SQL mount preserved | OK |
| Container concurrency preserved | OK |
| Max scale preserved | OK |
| Terraform plan after deploy | zero-diff |
| terraform_plan_exit_code | 0 |
| Cloud SQL final state | NEVER STOPPED |

## Evidence Files

| File | Purpose |
|---|---|
| docs/evidence/api-manual-deploy/baseline-before-deploy.txt | API and workflow baseline before deploy |
| docs/evidence/api-manual-deploy/workflow-run-25637933908-failed.txt | Failed workflow run log |
| docs/evidence/api-manual-deploy/failed-deploy-validation.txt | Failed deploy validation and root cause |
| docs/evidence/api-manual-deploy/workflow-run-25638169193.txt | Successful workflow run log |
| docs/evidence/api-manual-deploy/post-deploy-validation.txt | Cloud Run, Artifact Registry, Terraform and Cloud SQL validation after deploy |

## Safety Notes

- Deployment was manually triggered.
- No automatic deployment on push was enabled.
- No Terraform apply was executed in this branch.
- No IAM mutation occurred in this branch.
- No Cloud SQL start or mutation occurred.
- No Pub/Sub or Scheduler mutation occurred.
- Runtime configuration was explicitly preserved by deploy flags.
- A failed deploy attempt was captured before correction.
- The failed attempt did not change the running Cloud Run revision.

## Production Readiness Impact

This closes the API deployment automation evidence gap identified in the critical technical audit.

The API now has a validated manual deployment path using immutable commit-SHA image tags instead of relying on the previous Cloud Run source deployment path.

Together with the Pub/Sub worker deploy evidence, the project now demonstrates controlled deployment automation for both runtime Cloud Run services:

```text
rtdp-pubsub-worker
rtdp-api
```
