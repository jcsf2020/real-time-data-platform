

# Cloud Run Worker Manual Deploy Evidence

Branch: evidence/cloud-run-worker-manual-deploy
Status: MANUAL DEPLOY SUCCEEDED

## Objective

Execute the manual GitHub Actions Cloud Run deployment workflow for the Pub/Sub worker and capture evidence.

This validates the deployment path:

```text
GitHub Actions -> Artifact Registry -> Cloud Run
```

## Workflow Run

| Field | Value |
|---|---|
| Workflow | Deploy Worker to Cloud Run |
| Workflow file | .github/workflows/deploy-worker-cloud-run.yml |
| Run ID | 25622748867 |
| Trigger | workflow_dispatch |
| Ref | main |
| Result | success |

Full workflow log evidence:

```text
docs/evidence/cloud-run-worker-manual-deploy/workflow-run-25622748867.txt
```

## Image Built And Pushed

| Field | Value |
|---|---|
| Image | europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker |
| Tag | b9752c02b4ba0eec827aebe2420c2fdb92b5640b |
| Digest | sha256:739a225723d0f6c9576dc0a00dff681ca34dcba4f99c9a2fc4236029b304fb1c |
| Registry | Artifact Registry rtdp |
| Region | europe-west1 |

## Cloud Run Deployment Result

| Field | Before | After |
|---|---|---|
| Service | rtdp-pubsub-worker | rtdp-pubsub-worker |
| Revision | rtdp-pubsub-worker-00003-dh6 | rtdp-pubsub-worker-00004-cld |
| Image | rtdp-pubsub-worker:latest | rtdp-pubsub-worker:b9752c02b4ba0eec827aebe2420c2fdb92b5640b |
| Runtime service account | rtdp-worker-sa | rtdp-worker-sa |
| DATABASE_URL secret | rtdp-database-url:latest | rtdp-database-url:latest |
| Cloud SQL instance | project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres | project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres |
| Container concurrency | 1 | 1 |
| Max scale annotation | 1 | 1 |

## Validation

| Check | Result |
|---|---|
| Workflow completed | success |
| Artifact Registry SHA tag exists | OK |
| Cloud Run new revision deployed | OK |
| Cloud Run serving traffic | 100 percent |
| Runtime service account preserved | OK |
| DATABASE_URL secret preserved | OK |
| Cloud SQL mount preserved | OK |
| Container concurrency preserved | OK |
| Terraform plan after deploy | zero-diff |
| terraform_plan_exit_code | 0 |
| Cloud SQL final state | NEVER STOPPED |

## Evidence Files

| File | Purpose |
|---|---|
| docs/evidence/cloud-run-worker-manual-deploy/baseline-before-deploy.txt | Worker and workflow baseline before deploy |
| docs/evidence/cloud-run-worker-manual-deploy/workflow-run-25622748867.txt | GitHub Actions run summary and logs |
| docs/evidence/cloud-run-worker-manual-deploy/post-deploy-validation.txt | Cloud Run, Artifact Registry, Terraform and Cloud SQL validation after deploy |

## Safety Notes

- Deployment was manually triggered.
- No automatic deployment on push was enabled.
- No Terraform apply was executed in this branch.
- No Cloud SQL start or mutation occurred.
- No Pub/Sub or Scheduler mutation occurred.
- Runtime configuration was explicitly preserved by deploy flags.

## Production Readiness Impact

This closes the first deployment automation gap for the Pub/Sub worker.

The project now has a validated manual deployment path using immutable commit-SHA image tags instead of relying operationally on mutable latest tags.
