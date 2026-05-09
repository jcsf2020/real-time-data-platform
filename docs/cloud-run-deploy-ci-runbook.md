# Cloud Run Deploy CI Runbook

Branch: docs/cloud-run-deploy-ci-runbook
Status: PLAN ONLY - NOT EXECUTED

## Objective

Define the controlled plan for adding Cloud Run deployment automation to the Real-Time Data Platform.

The first deployment automation target is the Pub/Sub worker service:

- Cloud Run service: rtdp-pubsub-worker
- Dockerfile: apps/pubsub-worker/Dockerfile
- Artifact Registry repository: europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp
- Target image name: rtdp-pubsub-worker
- Target image tag strategy: Git commit SHA

## Current State

The project already has:

- GitHub Actions CI for Python validation
- GitHub Actions Terraform Plan workflow
- Workload Identity Federation for GitHub Actions to GCP authentication
- Terraform-managed Artifact Registry repository rtdp
- Terraform-managed Cloud Run service rtdp-pubsub-worker
- Terraform-managed service account rtdp-worker-sa
- Existing worker image currently referenced as latest
- Cloud SQL kept in safe resting state: activationPolicy NEVER and state STOPPED unless explicitly testing

## Problem Being Solved

The current worker Cloud Run service uses a mutable image tag:

europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest

Mutable latest tags weaken production traceability because a Cloud Run revision cannot be linked cleanly to a source commit.

The target production-readiness improvement is to deploy immutable commit-SHA image tags.

## Scope

In scope for the future execution branch:

- Add a dedicated GitHub Actions workflow for worker deployment
- Authenticate to GCP using Workload Identity Federation
- Configure Docker authentication for Artifact Registry
- Build the worker image from apps/pubsub-worker/Dockerfile
- Tag image with the Git commit SHA
- Push image to Artifact Registry rtdp
- Deploy rtdp-pubsub-worker to Cloud Run using the SHA-tagged image
- Preserve existing Cloud Run environment variables, service account, Cloud SQL mount, scaling, timeout, and concurrency

Out of scope for the first execution branch:

- API deployment automation
- silver refresh job deployment automation
- Terraform apply
- Cloud SQL mutation
- Pub/Sub mutation
- Scheduler mutation
- IAM mutation unless a missing permission is discovered and explicitly scoped
- Container Scanning enablement
- traffic splitting
- multi-environment deployment
- rollback automation beyond Cloud Run revision history

## Proposed Workflow Name

.github/workflows/deploy-worker-cloud-run.yml

## Proposed Triggers

Initial safe version:

- workflow_dispatch only

Reason:

Manual trigger allows validation without deploying on every merge to main. After the first successful evidence-backed deployment, the workflow can be extended to deploy on push to main.

Future version:

- push to main
- paths limited to:
  - apps/pubsub-worker/**
  - packages/**
  - pyproject.toml
  - uv.lock
  - apps/pubsub-worker/Dockerfile
  - .github/workflows/deploy-worker-cloud-run.yml

## Proposed Image

europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:${{ github.sha }}

## Proposed Deployment Command

gcloud run deploy rtdp-pubsub-worker \
  --project=project-42987e01-2123-446b-ac7 \
  --region=europe-west1 \
  --image=europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:${GITHUB_SHA}

The execution branch must preserve the already configured service settings and avoid passing unrelated flags that could reset runtime configuration.

## Safety Gates Before Execution

Before creating the deployment workflow, confirm:

1. Current branch starts from clean main.
2. Terraform plan is zero-diff.
3. Current worker Cloud Run configuration is captured.
4. Artifact Registry rtdp exists and is Terraform-managed.
5. Workload Identity Federation works through existing CI.
6. Required Artifact Registry push permission exists.
7. Required Cloud Run deploy permission is verified or scoped explicitly.
8. Cloud SQL remains NEVER STOPPED.

## Expected Validation After First Deployment

After the first manual deployment run:

- GitHub Actions workflow succeeds
- Artifact Registry contains image tagged with the commit SHA
- Cloud Run rtdp-pubsub-worker has a new revision
- New revision image references the SHA tag
- Worker service account remains rtdp-worker-sa
- DATABASE_URL secret reference remains unchanged
- Cloud SQL mount remains unchanged
- scaling remains min 0 and max 1
- concurrency remains 1
- Cloud SQL final state remains NEVER STOPPED
- Terraform plan remains zero-diff because image changes are currently ignored by lifecycle ignore_changes

## Evidence To Capture

The execution branch should create:

docs/cloud-run-worker-deploy-ci-evidence.md

Evidence should include:

- workflow run URL or ID
- image URI pushed
- Cloud Run revision name
- deployed image confirmation
- service account confirmation
- env/secret confirmation
- scaling/concurrency confirmation
- Terraform plan zero-diff after deployment
- Cloud SQL NEVER STOPPED
- CI checks green

## Production Readiness Impact

This plan prepares the project to close the deployment automation gap.

It also prepares the removal of mutable latest-tag deployment from the worker path by introducing commit-SHA image tags and an auditable GitHub Actions to Artifact Registry to Cloud Run deployment path.
