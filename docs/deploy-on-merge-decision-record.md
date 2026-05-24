# Deploy-on-Merge Decision Record

**Status:** DECISION RECORD -- deploy-on-merge and promotion-gate strategy for the validated GCP data platform
**Date:** 2026-05-22
**Branch:** `docs/deploy-on-merge-decision-record`
**Author intent:** Rigorous CI/CD production-readiness assessment. No unsupported claims.
This branch does NOT implement any workflow changes, does NOT apply Terraform, does NOT
start Cloud SQL, and does NOT resume Cloud Scheduler jobs.

---

## 1. Context

### Current CI/CD State

The Real-Time Data Platform has a mature continuous integration (CI) pipeline and a
deliberately manual continuous delivery (CD) pipeline.

**CI is fully automated.** The `ci.yml` workflow triggers on every push to `main`,
`feat/**`, `docs/**`, and `chore/**` branches, and on every pull request targeting
`main`. Each CI run executes:

- `uv run ruff check .` (lint)
- `uv run pytest -q` (257 tests as of 2026-05-22)
- Import smoke test for all workspace packages
- `dbt compile`, `dbt run`, `dbt test` against an ephemeral PostgreSQL service container

The `terraform-plan.yml` workflow triggers on PR and push to `main` (for infra-path
changes) and on `workflow_dispatch`. It runs `terraform fmt -check`, `terraform validate`,
and `terraform plan -detailed-exitcode`. The current baseline is `PLAN_EXIT=0` (zero diff
against live GCP state).

**CD is intentionally manual.** All three deploy workflows require explicit
`workflow_dispatch` invocation:

- `deploy-api-cloud-run.yml` -- builds and deploys the FastAPI image to Cloud Run
- `deploy-worker-cloud-run.yml` -- builds and deploys the Pub/Sub worker image to Cloud Run
- `deploy-dbt-refresh-cloud-run.yml` -- builds and pushes the dbt refresh job image to
  Artifact Registry only (Terraform owns the Cloud Run Job resource)

The `bigquery-quality-checks.yml` workflow runs on `workflow_dispatch` and a scheduled
cron (`15 6 * * *`). It is a read-only quality check, not a deployment.

**No deploy-on-merge is currently implemented.** A merge to `main` triggers CI but never
automatically deploys any service to production. Both manual deploy workflows have been
validated with explicit `workflow_dispatch` runs:

- API deploy: evidence in `docs/api-manual-deploy-evidence.md`
- Worker deploy: evidence in `docs/cloud-run-worker-manual-deploy-evidence.md`

### Production Resource State

All GCP resources are Terraform-managed with a GCS-backed remote state
(`rtdp-terraform-state-project-42987e01-2123-446b-ac7`, prefix
`real-time-data-platform/gcp/prod`). Workload Identity Federation (OIDC) is in place
for CI authentication; no stored service account keys exist in any workflow.

**Cloud SQL (`rtdp-postgres`) final safe state: STOPPED / NEVER.** This discipline is
verified in 60+ evidence documents. Cloud SQL is started only during bounded, controlled
validation windows and returned to `NEVER/STOPPED` immediately after.

**Cloud Scheduler jobs (`rtdp-silver-refresh-scheduler`, `rtdp-bigquery-append-scheduler`)
final safe state: PAUSED.** Both schedulers are explicitly paused in Terraform and in
every evidence document. No scheduler runs automatically or continuously.

**No staging environment is currently implemented.** The platform operates in a single
GCP project (`project-42987e01-2123-446b-ac7`, region `europe-west1`). There is no
staging Cloud SQL, no staging Pub/Sub, no staging Cloud Run services, and no staging
Terraform state prefix. A staging plan is documented in `docs/staging-environment-plan.md`
but not yet implemented.

### What This Document Is

This is an architecture decision record (ADR) and CI/CD production-readiness strategy
document. It evaluates the case for deploy-on-merge, explains why direct production
deploy-on-merge is not safe yet, defines the target promotion model, and provides an
explicit roadmap for implementing it safely. It does not create any GCP resources, modify
any GitHub Actions workflows, execute any `terraform apply`, start Cloud SQL, or resume
any Cloud Scheduler jobs.

---

## 2. Decision

**Decision: Do NOT enable direct production deploy-on-merge at this time.**

Direct deploy-on-merge to production is explicitly deferred. The reasons are documented
in Section 4.

**Recommended future state:** staging deploy-on-merge (automatic deployment to a staging
environment on merge to `main`), followed by manual approval before any production deploy.

**Until staging exists:** keep all production deploys manual via `workflow_dispatch`. The
existing deploy workflows are sufficient for the current portfolio validation cadence.
Manual deploy is a deliberate, defensible choice given the absence of a staging
environment, not an oversight.

**This decision does not mean CI/CD is weak.** CI is fully automated, proven, and
trustworthy. The current manual CD reflects a sound risk posture: deploying automatically
to the only production environment, without a staging gate, without smoke tests, and
without a rollback workflow, would introduce more risk than it eliminates. Documenting
that reasoning is itself a production-readiness signal.

**Superseding condition:** Once `feat/staging-environment-phase-1` is implemented and
validated, the decision can be revisited for staging deploy-on-merge. Production deploy
must remain gated behind manual approval even after staging exists.

---

## 3. Current Workflow Inventory

The following table describes every GitHub Actions workflow in the current platform,
its trigger, purpose, production risk, and the recommended change when staging is available.

| Workflow | Trigger | Current Purpose | Production Risk | Recommended Future Change |
|---|---|---|---|---|
| `ci.yml` | Push to main / `feat/**` / `docs/**` / `chore/**`; PR to main | Lint (ruff), pytest (257 tests), import smoke test, dbt compile/run/test against ephemeral Postgres | No GCP writes; no deployment; read-only CI | Add optional staging Terraform plan step; otherwise unchanged |
| `terraform-plan.yml` | PR to main (infra path); push to main (infra path); `workflow_dispatch` | Terraform fmt, validate, plan (prod state, `-detailed-exitcode`); PLAN_EXIT=0 required | Read-only plan; no apply; no GCP mutation | Add staging plan step (`-var-file=staging.tfvars`) before prod plan step; prod plan remains required gate |
| `deploy-api-cloud-run.yml` | `workflow_dispatch` (manual) | Build Docker image from `Dockerfile`; push to Artifact Registry with commit-SHA tag; `gcloud run deploy rtdp-api`; post-deploy config verification | Direct production deploy; image tags a live revision; Cloud SQL is configured on the service | Phase 1: staging first (automatic); Phase 2: add manual approval gate before prod deploy |
| `deploy-worker-cloud-run.yml` | `workflow_dispatch` (manual) | Build Docker image from `apps/pubsub-worker/Dockerfile`; push to Artifact Registry; `gcloud run deploy rtdp-pubsub-worker`; post-deploy config verification | Direct production deploy; replaces the live Pub/Sub worker revision | Phase 1: staging first; add worker smoke test (10 synthetic events) before prod deploy |
| `deploy-dbt-refresh-cloud-run.yml` | `workflow_dispatch` (manual) | Build dbt refresh job image; push to Artifact Registry with commit-SHA tag and `:latest` tag; **no Cloud Run mutation** -- Terraform owns `google_cloud_run_v2_job.rtdp_dbt_refresh_job` | Image push only; Terraform apply required separately for Cloud Run Job to pick up new image | Unchanged for now; when staging exists, add a staging Cloud Run Job image build step |
| `bigquery-quality-checks.yml` | `workflow_dispatch`; cron `15 6 * * *` | Read-only BigQuery quality checks against `rtdp_analytics.market_events_raw`; push metrics to Cloud Monitoring; upload `ci-report.json` artifact | No BigQuery mutation; no Cloud SQL start; no scheduler execution; OIDC authentication to Terraform plan service account | Extend with `--dataset staging` flag when staging BigQuery dataset exists |

**Key observation:** Neither deploy workflow (`deploy-api-cloud-run.yml`,
`deploy-worker-cloud-run.yml`) contains any safety gate, smoke test, approval step,
or rollback mechanism. They execute a direct production deploy unconditionally when
invoked. This is acceptable for manual dispatch (the operator invoking the workflow is
the approval step) but is not acceptable for automatic trigger on merge.

---

## 4. Why Direct Production Deploy-on-Merge Is Not Safe Yet

This section is direct. These are accurate technical risks, not softened concerns.

### No Staging Environment

There is no staging environment. A merge to `main` that triggers an automatic production
deploy has no pre-production rehearsal boundary. Every deployed revision is a live
production change with full blast radius. Schema-incompatible dbt models, misconfigured
Cloud Run secrets, or broken health check paths would go directly to the production Cloud
Run service with no opportunity to detect the failure in isolation.

### No Smoke Test Gate

The existing deploy workflows do not contain any post-deploy smoke tests that would halt
promotion on failure. `deploy-api-cloud-run.yml` performs a post-deploy configuration
verification (checks image URI, service account, secret reference, Cloud SQL annotation,
concurrency, and max scale), but it does not verify that the deployed service is actually
serving traffic correctly. A broken API that passes configuration checks would be silently
promoted by an automatic deploy-on-merge workflow.

There is no automated smoke test for the Pub/Sub worker. The worker receives messages via
push subscription; no workflow currently publishes synthetic messages to verify end-to-end
processing after a deploy.

### No Production Approval Gate

Direct production deploy-on-merge removes the human review step that `workflow_dispatch`
currently provides. The operator who triggers the workflow manually is, in effect, the
deployment approval. Removing that friction before a formal approval gate (GitHub
Environment protection rule with required reviewers) is in place would eliminate the only
non-automated safety check in the current CD path.

### No Rollback Automation

No rollback workflow exists. If a production deploy-on-merge results in a broken revision,
the recovery path is: identify the previous known-good image SHA in Artifact Registry,
re-invoke the deploy workflow manually with the correct SHA, and verify the Cloud Run
service returns to healthy state. This is a manual multi-step process under incident
conditions. Before automatic deploys are enabled, an explicit rollback workflow must exist.

### Cloud SQL STOPPED/NEVER Discipline

The deploy workflows for the API and worker both configure
`--add-cloudsql-instances=${PROJECT_ID}:${REGION}:rtdp-postgres`. This annotation must
be kept. However, it is critical to confirm that no deploy workflow starts Cloud SQL
automatically. The current deploy workflows do not issue any `gcloud sql instances patch`
command. This discipline must be preserved: the Cloud SQL instance is configured as the
connection target, but the deploy workflow must never start it. An automatic deploy-on-merge
workflow that accidentally starts Cloud SQL would violate the established STOPPED/NEVER
discipline and incur unexpected cost.

### Schedulers PAUSED Discipline

Both Cloud Scheduler jobs (`rtdp-silver-refresh-scheduler`, `rtdp-bigquery-append-scheduler`)
are kept `PAUSED` in Terraform. A deploy-on-merge workflow must never include a step that
resumes any Cloud Scheduler job. Resuming a scheduler automatically on deploy would trigger
Cloud Run job executions, which in turn would start Cloud SQL (the jobs connect to the
database). The scheduler state must remain under explicit human control.

### Evidence Base Must Not Be Contaminated

The production evidence base (50,000 Cloud SQL rows, 6,120 BigQuery rows, 257 passing
tests, `PLAN_EXIT=0`) represents validated, intentional states. An automatic deploy that
modifies Cloud Run service configuration, triggers unexpected Cloud SQL activity, or
mutates BigQuery tables would contaminate the evidence base without a corresponding
evidence document. The evidence-first discipline established throughout this platform
requires that every production change be deliberate and documented.

---

## 5. Target Promotion Model

The following model describes the target CI/CD promotion flow once a staging environment
exists. This is a design, not an implementation. None of these workflows exist today.

### Step-by-Step Flow

1. **PR validation** -- Developer opens a PR to `main`. `ci.yml` runs automatically:
   pytest, ruff, dbt compile/run/test, import smoke test. `terraform-plan.yml` runs for
   infra-path changes. All gates must pass. PR cannot merge while CI fails.

2. **Merge to main** -- PR is merged to `main` after code review and passing CI.

3. **Staging deploy (automatic)** -- A new `staging-deploy.yml` workflow triggers on
   merge to `main`. It deploys to the staging Cloud Run services and jobs only:
   - `terraform plan -var-file=staging.tfvars` must return PLAN_EXIT=0 or PLAN_EXIT=2
     (pending changes with explicit review).
   - Build Docker image; push to Artifact Registry with `staging-<GITHUB_SHA>` tag.
   - `gcloud run deploy rtdp-staging-api` and `gcloud run deploy rtdp-staging-pubsub-worker`.

4. **Staging smoke tests (automatic)** -- Executed within `staging-deploy.yml` after
   staging deploy completes:
   - `curl https://rtdp-staging-api-<hash>.run.app/health` must return HTTP 200.
   - Publish 10 synthetic events to `staging-market-events-raw`; verify 10 worker OK logs.
   - Cloud SQL staging state check: `STOPPED/NEVER` (unless started for the smoke test
     window, in which case it must be stopped after).
   - Upload staging evidence artifact (run ID, smoke test result, PLAN_EXIT, Cloud SQL state).

5. **Manual approval gate** -- A GitHub Environment protection rule on the `production`
   environment requires at least one designated reviewer to approve before production
   deploy proceeds. The staging evidence artifact is visible to the approver.

6. **Production deploy (gated)** -- A new `prod-deploy.yml` workflow or a production
   job within `staging-deploy.yml` executes after approval:
   - `terraform plan -detailed-exitcode` for prod must return PLAN_EXIT=0.
   - Build or promote the staging image (retag from `staging-<SHA>` to `prod-<SHA>`).
   - `gcloud run deploy rtdp-api` and `gcloud run deploy rtdp-pubsub-worker`.

7. **Post-production validation (automatic)** -- Executed within the production deploy
   job:
   - `curl https://rtdp-api-fpy4of3i5a-ew.a.run.app/health` must return HTTP 200.
   - Verify Cloud SQL state: `STOPPED/NEVER`.
   - Verify scheduler state: `PAUSED`.
   - Capture PLAN_EXIT=0 after deploy.

8. **Evidence artifact upload** -- The production deploy job uploads a CI artifact
   containing: run ID, deployed image SHA, PLAN_EXIT, Cloud SQL state, scheduler state,
   health check result, and timestamp. This becomes the production deploy evidence document.

### ASCII Promotion Flow Diagram

```
Developer
  │
  ├── git push origin feat/my-feature
  │
  ▼
PR opened → ci.yml (automatic)
  ├── ruff check                   ──► PASS required
  ├── pytest -q (257 tests)        ──► PASS required
  ├── dbt compile/run/test         ──► PASS required
  └── terraform-plan.yml           ──► PLAN_EXIT=0 required (infra path)
  │
  ▼ (all CI gates green)
  │
PR reviewed + approved by team
  │
  ▼
Merge to main
  │
  ▼
staging-deploy.yml (AUTOMATIC on merge)
  ├── terraform plan (staging)     ──► PLAN_EXIT=0 required
  ├── docker build + push          ──► staging-<SHA> tag
  ├── gcloud run deploy (staging)  ──► staging services only
  ├── staging smoke tests:
  │     ├── API /health → HTTP 200  ──► PASS required
  │     ├── 10 events round-trip   ──► 10/10 required
  │     └── Cloud SQL STOPPED      ──► STOPPED/NEVER required
  └── upload staging evidence artifact
  │
  ▼ (staging gates green)
  │
MANUAL APPROVAL GATE
  (GitHub Environment: production)
  (Required reviewers: designated approver)
  (Staging artifact visible in UI)
  │
  ▼ (approved)
prod-deploy.yml (GATED, post-approval)
  ├── terraform plan (prod)        ──► PLAN_EXIT=0 required
  ├── docker retag or rebuild      ──► prod-<SHA> tag
  ├── gcloud run deploy (prod)     ──► production services
  ├── post-prod validation:
  │     ├── API /health → HTTP 200  ──► PASS required
  │     ├── Cloud SQL STOPPED      ──► STOPPED/NEVER required
  │     └── Schedulers PAUSED      ──► PAUSED required
  └── upload prod evidence artifact
  │
  ▼
Production deploy complete
Evidence artifact persisted (run ID, SHA, PLAN_EXIT, Cloud SQL state)
```

---

## 6. Recommended GitHub Environments

GitHub Environments provide deployment protection rules including required reviewers,
wait timers, and environment-specific secrets. They are a prerequisite for the target
promotion model.

### staging GitHub Environment

**Name:** `staging`
**Protection rules:** None required initially. Optionally add a wait timer (e.g. 2
minutes) to allow the deploy to settle before smoke tests run.
**Secrets:**
- `GCP_WORKLOAD_IDENTITY_PROVIDER` -- same Workload Identity pool as production
  (staging-specific CI service account with staging-only permissions)
- `GCP_STAGING_CLOUD_RUN_DEPLOY_SERVICE_ACCOUNT` -- a new staging deploy service account
  with `roles/run.developer` scoped to staging Cloud Run resources only; must not have
  any production resource permissions.

**Purpose:** Staging is the first automatic gate after merge. It must be fast (target:
under 5 minutes for build + deploy + smoke test) to preserve merge-to-feedback velocity.

### production GitHub Environment

**Name:** `production`
**Protection rules:**
- **Required reviewers:** At least one designated reviewer must approve before the
  production deploy job executes. For a solo project, this can be the repository owner
  themselves (self-approval is a valid but weaker gate).
- **Wait timer:** Optional 5-minute wait after approval to allow for second thoughts.
  Useful if the approver cannot immediately monitor the deploy.
- **Deployment branch policy:** Only allow deploys from the `main` branch. No feature
  branch can trigger a production deploy.

**Secrets:**
- `GCP_WORKLOAD_IDENTITY_PROVIDER` -- same Workload Identity pool (production CI service
  account with production deploy permissions)
- `GCP_CLOUD_RUN_DEPLOY_SERVICE_ACCOUNT` -- existing `rtdp-cloud-run-deploy-ci` service
  account; already validated for production deploys

### OIDC / Workload Identity Implications

The existing Workload Identity pool (`github-actions`, provider `github`) is configured
with an `attribute_condition` scoped to `assertion.repository == 'jcsf2020/real-time-data-platform'`.
This means any workflow in the repository can request tokens for any service account that
has an `iam.workload_identity_pool_users` binding.

When staging is introduced:
- A new `rtdp-staging-cloud-run-deploy-ci` service account must be created with
  permissions scoped to staging resources only.
- The existing `rtdp-cloud-run-deploy-ci` service account retains its production
  permissions; it must not be granted staging resource permissions.
- The GitHub Environment `staging` uses `vars.GCP_STAGING_CLOUD_RUN_DEPLOY_SERVICE_ACCOUNT`
  while the `production` environment uses `vars.GCP_CLOUD_RUN_DEPLOY_SERVICE_ACCOUNT`.
  These must be separate variables pointing to separate service accounts.
- For Phase 2 (separate GCP projects), a separate Workload Identity pool in the staging
  project eliminates cross-project token sharing.

### Why Production Deploy Requires Approval

Automatic production deploy without human review is incompatible with the current
platform state for the following reasons:

1. **No staging gate exists yet.** Until staging is validated, there is no technical
   mechanism to confirm that the deployed artifact behaves correctly in a pre-production
   environment.
2. **Cloud SQL and scheduler discipline.** A human reviewer confirms that no deploy
   step accidentally starts Cloud SQL or resumes a scheduler.
3. **Evidence base integrity.** Each production deploy should correspond to an explicit
   decision and a documented evidence artifact. Automatic deploys without a review step
   produce undocumented changes to the production state.
4. **Rollback readiness.** The reviewer confirms that the previous known-good image SHA
   is identified before approving, so rollback is immediately actionable if needed.

---

## 7. Required Validation Gates

The following table defines the full set of validation gates required to support the
target promotion model. Gates marked "Blocks promotion?" YES must pass before the
corresponding deployment step proceeds.

| Gate | Environment | Command / Check | Required Result | Blocks Promotion? |
|---|---|---|---|---|
| pytest | CI (every push/PR) | `uv run pytest -q` | All 257 tests pass; exit code 0 | YES -- PR cannot merge if failing |
| ruff | CI (every push/PR) | `uv run ruff check .` | No lint issues; exit code 0 | YES -- PR cannot merge if failing |
| terraform fmt | CI (every push/PR, infra path) | `terraform fmt -check -recursive infra/terraform/gcp` | No formatting differences; exit code 0 | YES -- PR cannot merge if failing |
| terraform validate | CI (every push/PR, infra path) | `terraform -chdir=infra/terraform/gcp validate` | `Success!` output; exit code 0 | YES -- PR cannot merge if failing |
| terraform plan (prod) | CI (every push/PR, infra path) | `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"` | `PLAN_EXIT=0` (zero diff against live GCP state) | YES -- any non-zero drift blocks promotion |
| dbt compile/run/test | CI (every push/PR) | `dbt compile`, `dbt run`, `dbt test` via `ci.yml` dbt job against ephemeral Postgres | All compile/run/test steps pass; no ERROR or FAIL | YES -- PR cannot merge if dbt tests fail |
| terraform plan (staging) | Staging deploy | `terraform plan -var-file=staging.tfvars -detailed-exitcode` | `PLAN_EXIT=0` or `PLAN_EXIT=2` with explicit review | YES -- staging deploy blocked if PLAN_EXIT=1 |
| API health check (staging) | Staging smoke test | `curl https://rtdp-staging-api-<hash>.run.app/health` | HTTP 200 | YES -- blocks manual approval request |
| worker smoke test (staging) | Staging smoke test | Publish 10 synthetic events to `staging-market-events-raw`; verify 10 worker OK logs in Cloud Logging | 10/10 events matched; 0 worker errors | YES -- blocks manual approval request |
| Cloud SQL state check (staging) | Staging post-deploy | `gcloud sql instances describe rtdp-staging-postgres ... --format="table(name,state,settings.activationPolicy)"` | `STOPPED / NEVER` | YES -- staging does not pass if Cloud SQL running |
| Scheduler state check (staging) | Staging post-deploy | `gcloud scheduler jobs list ... --format="table(id,state)"` | All staging schedulers `PAUSED` | YES -- staging does not pass if any scheduler enabled |
| Manual approval | Production gate | GitHub Environment protection rule; required reviewer approves | Approval granted by designated reviewer | YES -- production deploy cannot start without approval |
| terraform plan (prod) | Production deploy | `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"` | `PLAN_EXIT=0` | YES -- production deploy blocked if any Terraform drift |
| API health check (production) | Post-prod validation | `curl https://rtdp-api-fpy4of3i5a-ew.a.run.app/health` | HTTP 200 | YES -- deploy is not accepted if health check fails |
| Cloud SQL state check (production) | Post-prod validation | `gcloud sql instances describe rtdp-postgres --project=project-42987e01-2123-446b-ac7 --format="table(name,state,settings.activationPolicy)"` | `STOPPED / NEVER` | YES -- deploy evidence is not complete if Cloud SQL running |
| Scheduler state check (production) | Post-prod validation | `gcloud scheduler jobs list --project=project-42987e01-2123-446b-ac7 --location=europe-west1 --format="table(id,state,schedule)"` | Both schedulers `PAUSED` | YES -- deploy evidence is not complete if any scheduler enabled |
| PLAN_EXIT=0 after deploy | Post-prod validation | Re-run terraform plan after production deploy completes | `PLAN_EXIT=0` | YES -- any Terraform drift after deploy must be investigated |

---

## 8. Production Deployment Safety Rules

The following rules are absolute constraints for any production deployment workflow,
whether manual or automatic. Violating any of these rules is a deployment safety failure.

**Rule 1: Never start Cloud SQL automatically in a deploy workflow.**
No deploy workflow (`deploy-api-cloud-run.yml`, `deploy-worker-cloud-run.yml`,
`deploy-dbt-refresh-cloud-run.yml`, or any future `prod-deploy.yml`) may issue
`gcloud sql instances patch rtdp-postgres --activation-policy=ALWAYS` or any equivalent
command. The Cloud SQL annotation in `gcloud run deploy` (`--add-cloudsql-instances`)
configures the Cloud SQL connection proxy but does not start the instance. This must
remain true. Cloud SQL is started only during explicitly bounded, human-initiated
validation windows.

**Rule 2: Never resume schedulers automatically in a deploy workflow.**
No deploy workflow may issue `gcloud scheduler jobs resume` for any scheduler job.
Resuming a scheduler triggers Cloud Run job executions that connect to Cloud SQL. This
would violate the STOPPED/NEVER discipline and incur unexpected costs. Schedulers are
controlled exclusively by deliberate, time-bounded manual operations.

**Rule 3: No `terraform apply` to production without explicit human approval.**
Terraform apply against the production state (`real-time-data-platform/gcp/prod`) must
never be triggered automatically on merge. `terraform plan` is automated; `terraform apply`
is gated. Any production Terraform change requires: a zero-diff pre-apply plan, a dedicated
evidence branch, and explicit human invocation. A `prod-deploy.yml` workflow that includes
a `terraform apply` step must require a GitHub Environment `production` approval gate.

**Rule 4: No production deploy without staging evidence once staging exists.**
Once `feat/staging-environment-phase-1` is validated, every production deploy must be
preceded by a successful staging deploy with captured smoke test evidence. The production
approval step should require the staging evidence artifact to be present in the same CI run.
Bypassing staging evidence to accelerate a production deploy is not permitted.

**Rule 5: Production deploy must capture evidence.**
Every production deploy (whether manual or gated automatic) must produce a CI artifact
containing: run ID, commit SHA, deployed image URI, PLAN_EXIT value, Cloud SQL state,
scheduler states, API health check result, and deploy timestamp. This artifact constitutes
the production deploy evidence document and is indexed in `docs/EVIDENCE_INDEX.md`.

**Rule 6: Production rollback must use a previous known-good image tag.**
If a production deploy results in a broken revision, rollback must use the previous
commit-SHA image tag already present in Artifact Registry. Rollback must not rebuild
from source; it must redeploy the previously validated image. The rollback procedure
is defined in Section 9.

---

## 9. Rollback Strategy

No automated rollback workflow currently exists. The following describes the rollback
procedure for each service and the expected evidence to capture after rollback.

### Cloud Run Revision Rollback

Cloud Run maintains all previously deployed revisions. If a new revision is unhealthy,
Cloud Run can serve 100% of traffic from a previous revision without rebuilding.

**Immediate action:** Verify which revision is currently serving:

```bash
gcloud run services describe rtdp-api \
  --project=project-42987e01-2123-446b-ac7 \
  --region=europe-west1 \
  --format="table(status.traffic)"
```

If the new revision is receiving traffic and is unhealthy, migrate traffic to the
previous revision by redeploying the previous known-good image:

```bash
gcloud run deploy rtdp-api \
  --project=project-42987e01-2123-446b-ac7 \
  --region=europe-west1 \
  --image=europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-api:<PREVIOUS_SHA> \
  --quiet
```

### Previous Known-Good Image Tag

Before any production deploy, the current serving image SHA must be recorded. This is
available from `gcloud run services describe` (`status.latestReadyRevisionName` → revision
→ image annotation). The Artifact Registry image history provides the full list of pushed
images for `rtdp-api` and `rtdp-pubsub-worker`.

In the target promotion model, the staging evidence artifact records the staging image
SHA before promotion. The production evidence artifact records the pre-rollback image SHA.
This creates a durable, indexed rollback target for every production deploy.

### Terraform Rollback

If a `terraform apply` introduced a configuration regression:

1. Identify the prior state using `git log -- infra/terraform/gcp/` to find the commit
   before the change.
2. Revert the Terraform configuration file(s) to the prior commit.
3. Run `terraform plan -detailed-exitcode` to confirm the revert produces PLAN_EXIT=2
   (pending changes that will restore the prior state).
4. Apply in a dedicated rollback evidence branch with explicit human invocation.
5. Confirm `PLAN_EXIT=0` after the rollback apply.

### dbt Job Rollback

If a `dbt run` regression affects the silver or gold models:

1. The previous dbt refresh job image tag (from Artifact Registry) is the rollback target.
2. Redeploy the Cloud Run Job resource with the previous image tag via Terraform
   (update `image` in the `google_cloud_run_v2_job` resource; plan; apply in a dedicated
   rollback branch).
3. Trigger a manual Cloud Run Job execution to re-run the prior dbt model version.
4. Verify `dbt run PASS=2` and `dbt test PASS=22` in the execution logs.
5. Cloud SQL must be started only for the bounded rollback window and returned to
   STOPPED/NEVER immediately after.

### API Rollback

1. Record the pre-rollback image URI from `gcloud run services describe rtdp-api`.
2. Invoke `deploy-api-cloud-run.yml` via `workflow_dispatch` with the previous known-good
   SHA (requires modifying the `IMAGE_URI` in the workflow or a separate rollback workflow
   that accepts an image URI input).
3. Verify post-deploy API configuration check passes.
4. Verify `curl https://rtdp-api-fpy4of3i5a-ew.a.run.app/health` returns HTTP 200.

### Worker Rollback

1. Record the pre-rollback image URI from `gcloud run services describe rtdp-pubsub-worker`.
2. Invoke `deploy-worker-cloud-run.yml` via `workflow_dispatch` with the previous known-good
   SHA.
3. Verify post-deploy worker configuration check passes.
4. Verify Pub/Sub message delivery to the worker resumes (check Cloud Logging for worker
   `status=ok` entries).

### Evidence to Capture After Rollback

Every rollback is a production incident. The following evidence must be captured and
indexed in a dedicated `docs/<service>-rollback-evidence.md` document:

- Run ID of the failing deploy that triggered rollback
- Root cause of the failure (log excerpt or Terraform plan diff)
- Rollback decision timestamp
- Previous known-good image SHA used for rollback
- Post-rollback health check result
- Post-rollback PLAN_EXIT value
- Post-rollback Cloud SQL state (STOPPED/NEVER)
- Post-rollback scheduler state (PAUSED)
- Duration of production impact

---

## 10. Terraform Apply Decision

**Current default: terraform apply is manual.** The `terraform-plan.yml` workflow runs
`terraform plan` only. No apply step exists in any CI workflow. This is the correct
default for the current single-environment platform.

**Why terraform apply remains manual:**
- There is no staging environment to rehearse the apply before production.
- Every `terraform apply` against the production state has full blast radius.
- The zero-diff (`PLAN_EXIT=0`) discipline is the safety baseline. Introducing an
  auto-apply step eliminates the manual review window between plan and apply.
- Prior `terraform apply` operations (BigQuery dataset, Cloud Run Jobs, IAM hardening)
  were each executed on dedicated evidence branches with explicit human invocation.
  This evidence-first pattern must be preserved.

**Staging terraform apply can be automated later.**
Once `feat/staging-environment-phase-1` is implemented, the `staging-deploy.yml` workflow
may include a `terraform apply -var-file=staging.tfvars` step for staging resources only.
Staging apply automation is acceptable because:
- Staging state is separate from production state.
- Staging resources are disposable (staging data is synthetic, staging Cloud SQL is
  STOPPED/NEVER by default).
- A failed staging apply does not affect production.
- Staging apply is gated by the same pre-apply PLAN_EXIT=0 check.

**Production terraform apply requires manual approval in all cases.**
Even in the target promotion model, `terraform apply` against the production state requires
a separate approval step beyond the standard deployment approval. A production deploy
that also modifies Terraform-managed infrastructure (e.g. adding a new Cloud Run service
revision timeout, changing Pub/Sub ack deadline) must produce a reviewed plan, receive
explicit operator approval, and generate a dedicated evidence artifact.

**PLAN_EXIT=0 remains the safety baseline.**
The zero-diff Terraform plan baseline (`PLAN_EXIT=0`) is the most important safety signal
in the current IaC posture. It confirms that live GCP state matches Terraform-declared
state. This baseline must be maintained throughout all future branches:

- Every PR to `main` must pass `terraform-plan.yml` with `PLAN_EXIT=0`.
- Every production deploy must re-run `terraform plan` before the deploy step and after.
- Any `PLAN_EXIT=2` (pending changes) observed outside a declared Terraform apply branch
  must be investigated before any other work proceeds.

---

## 11. Relationship to Staging Plan

**The staging environment plan is the prerequisite for deploy-on-merge.**

`docs/staging-environment-plan.md` defines the two-phase staging strategy:
- Phase 1: same-project prefixed resources with separate Terraform state prefix
- Phase 2: separate GCP projects with full IAM isolation

Deploy-on-merge becomes valuable -- and safe -- only after Phase 1 is implemented and
validated. Without a staging environment, deploy-on-merge would mean automatic production
deployment on every merge to `main`. This is not acceptable given the current platform state.

**The staging plan defines the promotion model foundation.** Section 9 of
`docs/staging-environment-plan.md` describes the future CI/CD promotion flow in detail.
This decision record adopts and extends that flow, adding specifics about GitHub Environments,
validation gates, safety rules, Terraform apply policy, and rollback strategy.

**Same-project staging is an acceptable interim.** For a solo portfolio project, same-project
prefixed staging (Option B from the staging plan) provides sufficient environment separation
to enable a meaningful staging deploy gate. It is acknowledged as a weaker isolation boundary
than separate GCP projects, but it closes the most critical gap: the absence of any
pre-production rehearsal boundary.

**Separate GCP projects are the production-grade target.** Phase 2 of the staging plan
(separate GCP projects, separate Workload Identity, separate secrets) is the correct
architecture for a team-operated platform. It should be implemented when budget and
operational need justify the overhead. The deploy-on-merge model described in this document
is designed to work with either the same-project or separate-project staging topology.

**Until staging exists, keep production deploys manual.** The absence of staging is
the single most important reason direct production deploy-on-merge is not safe today.
When a developer asks "can we enable deploy-on-merge?", the answer is: implement staging
first, validate it, then revisit this decision record.

---

## 12. Relationship to Recruitment Value

### Why CI/CD Maturity Matters for GCP Data Engineer / Data Platform Roles

CI/CD ownership is consistently listed as a requirement in 2026-2027 GCP Data Platform and
Data Engineer job descriptions. The specific signals technical interviewers look for are:

- **Automated CI** with lint, unit tests, integration tests, and IaC plan checks. This
  platform has this fully implemented and evidenced.
- **Automated CD with promotion gates.** This is the gap this decision record addresses.
  Many platforms implement deploy-on-merge; the better ones implement it with staging gates.
- **Rollback capability.** The ability to revert a bad deploy quickly is a production-grade
  signal. Currently manual; rollback strategy is documented.
- **Environment separation.** The absence of staging is the most predictable senior
  reviewer challenge. The staging plan addresses this architecturally; this decision record
  connects it to the CI/CD story.

### How Manual CD Is Acceptable If Documented

Manual CD (`workflow_dispatch`) is not an inherent weakness. It is a weakness only if it
is unintentional, undocumented, or cannot be explained. The correct framing is:

> "CD is currently manual. This is a deliberate decision, not an omission. The production
> environment has no staging gate, no smoke test, and no automated rollback. Enabling
> deploy-on-merge in this state would remove the human review step that is currently the
> only non-automated safety check in the CD path. The staging plan is the prerequisite.
> Once staging is validated, deploy-on-merge to staging becomes safe and automatic;
> production deploy remains gated behind manual approval."

This framing demonstrates architectural maturity: the candidate understands the risks
of automatic production deployment and has made a deliberate choice to defer it.

### Why Reckless Deploy-on-Merge Would Be Worse Than Manual Deploys

A candidate who enables direct production deploy-on-merge without staging, without a
smoke test gate, and without a rollback workflow is demonstrating that they prioritise
convenience over safety. For a senior technical reviewer or hiring manager, this is a
negative signal: it suggests the candidate does not understand why environment separation
exists, or does not care about the blast radius of an automatic production deploy.

The documented reasoning in this decision record -- "we have CI, we have manual CD, we
have a staging plan, and we will implement deploy-on-merge in the right order" -- is
a stronger production-readiness signal than a three-line `on: push: branches: [main]`
trigger in a deploy workflow.

### How This Decision Improves Production-Readiness Story

This decision record closes the deploy-on-merge documentation gap identified in
`docs/market-value-gap-audit-2026-2027.md` (Priority 5: `docs/deploy-on-merge-decision-record`).
By documenting:

- the current manual CD posture and why it is appropriate today,
- the promotion model target (staging-first, gated production),
- the safety rules that must never be violated in deploy workflows,
- the validation gate table that defines promotion criteria,
- the rollback strategy that makes production deploys reversible, and
- the Terraform apply policy that preserves the zero-diff safety baseline,

this document converts the CI/CD gap from a visible weakness into a documented,
reasoned decision. A senior reviewer who finds this document will see not an omission
but a mature engineering judgment about when and how to automate production deployment.

---

## 13. Implementation Roadmap

The following phases describe the incremental implementation path from the current
manual CD state to a fully gated, staged, evidence-backed promotion model.

### P0 -- Docs-Only Decision Record (This Branch)

**Branch:** `docs/deploy-on-merge-decision-record`
**Expected files:** `docs/deploy-on-merge-decision-record.md`, updated `docs/EVIDENCE_INDEX.md`
**Cloud SQL required:** No
**Terraform apply required:** No
**GCP cost risk:** None
**Validation evidence:** All CI gates pass; PLAN_EXIT=0; Cloud SQL STOPPED/NEVER;
schedulers PAUSED; this document indexed in EVIDENCE_INDEX.md; grep section headers present

### P1 -- Staging Deploy Workflow Design

**Branch:** `docs/staging-deploy-workflow-design`
**Expected files:** `docs/staging-deploy-workflow-design.md` -- detailed workflow YAML
designs for `staging-deploy.yml` and `prod-deploy.yml` with all safety guards annotated;
GitHub Environment configuration instructions; OIDC / Workload Identity staging extensions
**Cloud SQL required:** No
**Terraform apply required:** No
**GCP cost risk:** None
**Validation evidence:** Docs-only; grep section headers; CI gates pass

### P2 -- Staging Deploy Implementation

**Branch:** `feat/staging-deploy-workflow`
**Expected files:** `.github/workflows/staging-deploy.yml`, `.github/workflows/prod-deploy.yml`,
updated GitHub Actions variables for staging service account, staging environment
configuration in repository settings
**Prerequisite:** `feat/staging-environment-phase-1` must be merged and validated first
(staging Cloud Run services and staging Terraform state must exist)
**Cloud SQL required:** Staging Cloud SQL only (staging window, `rtdp-staging-postgres`,
STOPPED/NEVER by default; started only for smoke test if needed)
**Terraform apply required:** Staging Terraform apply only (`-var-file=staging.tfvars`)
**GCP cost risk:** Low (staging Cloud Run + ephemeral Cloud SQL start if smoke test requires it)
**Validation evidence:** `staging-deploy-workflow-evidence.md` -- first successful staging
deploy run; smoke test pass; PLAN_EXIT=0; staging Cloud SQL STOPPED/NEVER; production
state unchanged; schedulers PAUSED

### P3 -- Production Promotion Gate

**Branch:** `feat/prod-promotion-gate`
**Expected files:** GitHub Environment `production` configured with required reviewers;
`prod-deploy.yml` extended with approval gate; Workload Identity staging service account
created and scoped; `docs/prod-promotion-gate-evidence.md`
**Prerequisite:** P2 validated; at least one successful staging deploy cycle
**Cloud SQL required:** Staging only (for end-to-end promotion test)
**Terraform apply required:** Staging only (for promotion rehearsal)
**GCP cost risk:** Low
**Validation evidence:** First successful staged promotion: staging deploy → smoke test
pass → manual approval → production deploy → post-prod validation; PLAN_EXIT=0 throughout;
evidence artifact uploaded

### P4 -- Rollback Automation and Evidence Artifacts

**Branch:** `feat/rollback-automation`
**Expected files:** `.github/workflows/rollback-api.yml`, `.github/workflows/rollback-worker.yml`
(accept image URI input via `workflow_dispatch`; deploy to prod with specified SHA; run
post-rollback validation); `docs/rollback-workflow-evidence.md`
**Cloud SQL required:** No (rollback workflows are Cloud Run only)
**Terraform apply required:** No
**GCP cost risk:** None (Cloud Run redeploys to previous revision; no new resources)
**Validation evidence:** Successful rollback drill: deploy a known-bad image to production;
invoke rollback workflow with the previous SHA; confirm health check passes; PLAN_EXIT=0;
evidence artifact uploaded

---

## 14. Critical Technical Review

The following challenges are stated as they would actually be raised by a senior technical
interviewer or hiring manager. Each answer is evidence-based, not apologetic.

---

**"You do not have real CD."**

Correct. CD is manual. Three deploy workflows require explicit `workflow_dispatch`
invocation. No deploy triggers automatically on merge. This is a real gap, not a
claimed capability.

The defensive answer: Real CD in a production platform requires a staging environment,
smoke test gates, an approval workflow, and a rollback mechanism. None of these exist
yet. Enabling CD without them would be reckless. The staging plan and this decision
record are the architectural foundation. The CI half of CI/CD is fully automated and
evidenced. The CD half is in a documented, reasoned "deliberately manual" state pending
the staging environment.

---

**"Manual deploys are not production-grade."**

This statement is oversimplified. Many production platforms use manual approval gates
for production deploys, including large enterprise platforms. The distinction that matters
is whether manual deploys are intentional, repeatable, and documented.

The defensive answer: The manual deploy workflows are validated, evidenced, and version-
controlled. Each `workflow_dispatch` run produces a verified post-deploy configuration
check. The current posture is: automated CI (every push), manual CD (every production
deploy requires explicit operator action). This is the correct posture when there is no
staging environment. Once staging exists, staging deploys will be automatic; production
deploys will be gated (not fully automatic). "Production-grade CD" is not synonymous with
"fully automatic CD." It means repeatable, tested, and monitored deployment with rollback
capability.

---

**"Deploy-on-merge is table stakes."**

It is table stakes for a CI-only view of CD. It is not table stakes for a staging-aware
production platform.

The defensive answer: Deploy-on-merge to what? If the answer is "to the only production
environment, without a smoke test, without a staging gate, without a rollback workflow,"
then yes, many platforms do this, and many platforms have production incidents because of
it. Implementing deploy-on-merge correctly -- staging-first, gated production, with a
rollback drill -- is table stakes for a production-grade platform. Implementing it
naively -- direct production on every merge -- is a common mistake, not a best practice.
This decision record documents why the naive version is deferred and what the correct
implementation path looks like.

---

**"Without staging, this is not safe."**

Correct. Without staging, any deploy workflow change, Cloud Run configuration change, or
dbt model change goes directly to the only production environment.

The defensive answer: The absence of staging is documented as the primary blocker for
deploy-on-merge and as a known production-readiness gap. The staging plan defines the
implementation path. The decision to keep production deploys manual until staging exists
is the correct response to this gap, not a workaround or an apology. The gap is known,
documented, and queued.

---

**"You cannot claim production-ready CI/CD."**

Correct. The platform cannot claim production-ready CI/CD in the sense of "fully automated
from commit to production with staging gates, smoke tests, and rollback." That is explicitly
a non-claim in Section 15.

The defensive answer: The CI half is production-grade: 257 tests, ruff, dbt compile/run/test,
Terraform plan, all on every push, all gated on PR merge. The CD half is in a documented
"deliberately manual with a defined automation path" state. "Production-ready CI/CD" at most
companies means CI-automated and CD-gated (human approval for production). That is exactly
what this platform will have once the staging and promotion gate branches are implemented.

---

**"Where is rollback?"**

There is no automated rollback workflow. The rollback procedure is manual and documented
in Section 9 of this document.

The defensive answer: Cloud Run maintains all previous revisions. A manual rollback
using the previous known-good SHA from Artifact Registry takes approximately 2 minutes
via `workflow_dispatch`. The rollback procedure is documented. The automation of rollback
is deferred to Phase 4 of the roadmap. The absence of an automated rollback workflow is
a real gap; it is acknowledged and queued, not dismissed.

---

## 15. Explicit Non-Claims

The following is a precise list of what is NOT true about the current platform CI/CD
state. These are not weaknesses to apologise for; they are accurate technical facts
that must be stated explicitly to maintain evidence integrity.

- **No deploy-on-merge is implemented.** Merging a PR to `main` does not trigger any
  deployment to any GCP service. The CI pipeline runs; no CD pipeline runs automatically.
- **No staging deploy workflow is implemented.** There is no `staging-deploy.yml`
  workflow. No staging Cloud Run service exists. No staging deploy has been executed.
- **No production approval gate is implemented.** There is no GitHub Environment
  `production` protection rule. No required reviewer configuration exists.
- **No rollback automation is implemented.** There is no `rollback-api.yml` or
  `rollback-worker.yml` workflow. Rollback is a manual procedure documented in Section 9.
- **No automated Terraform apply to production.** The `terraform-plan.yml` workflow
  runs plan only. No CI workflow executes `terraform apply` against the production state.
  All prior `terraform apply` operations were manual, documented, and executed on
  dedicated evidence branches.
- **No automated production smoke test workflow.** After a production deploy (manual or
  future gated), there is no automated smoke test workflow that verifies the deployed
  service is serving traffic correctly end-to-end.
- **No production SLA.** The platform has been validated through bounded, controlled
  tests only. No service level agreement with measurable availability or latency targets
  applies to the current deployment. `docs/SLO_AND_INCIDENT_RESPONSE.md` defines
  production-light SLO targets; these are aspirational, not contractual.
- **No staging environment is implemented yet.** `docs/staging-environment-plan.md`
  defines the staging strategy. No staging GCP resources, no staging Terraform state,
  no staging secrets, and no staging CI jobs exist.

---

## 16. Safe Recruitment Positioning

### Recruiter-Facing Paragraph

> The Real-Time Data Platform has fully automated CI (257 tests, ruff, dbt
> compile/run/test, Terraform plan) on every push via GitHub Actions with Workload
> Identity Federation. Deployment is currently manual via workflow_dispatch -- a deliberate
> architectural decision documented in the deploy-on-merge decision record. The platform
> is positioned for a phased CI/CD evolution: staging deploy-on-merge (automatic) once
> a staging environment is validated, followed by a gated manual approval for production.
> Validation gates, safety rules, a rollback strategy, and a Terraform apply policy are
> all documented. No deploy-on-merge is currently implemented; the documentation shows
> why, and the roadmap shows how.

### Technical Interview Paragraph

> CI is fully automated with 257 tests, ruff, dbt, and Terraform plan on every push.
> CD is manual: all three deploy workflows require explicit workflow_dispatch. I have not
> implemented deploy-on-merge because there is no staging environment yet, no automated
> smoke test gate, and no rollback workflow. Enabling direct production deploy-on-merge
> in this state would remove the only non-automated safety check in the CD path. The
> architecture decision record for deploy-on-merge documents the target promotion model:
> staging deploy-on-merge on every merge to main, staging smoke tests gate the approval
> request, a GitHub Environment protection rule requires manual approval for production,
> and a post-deploy PLAN_EXIT=0 check confirms no Terraform drift. The next implementation
> branch after staging exists is feat/staging-deploy-workflow.

### Senior Reviewer Caveat Paragraph

> For senior technical reviewers: I am aware that manual CD is not equivalent to
> production-grade automated deployment with staging gates. I have not claimed otherwise.
> The deploy-on-merge decision record documents the precise reasons why automatic
> production deployment is deferred, what the correct implementation path is, and what
> safety rules must never be violated in any deploy workflow. The current manual posture
> is the correct posture for a single-environment platform with no staging gate and no
> rollback automation. The CI/CD gap is documented, reasoned, and queued. The next steps
> are staging environment implementation followed by a staged promotion workflow. No claims
> of production-ready CI/CD are made.

---

## 17. Final Recommendation

**Keep production deploys manual for now.**
The current `workflow_dispatch` deploy pattern is correct. It provides human review,
version-controlled deploy procedure, and a post-deploy configuration verification step.
It is not a gap to hide; it is a documented, defensible posture.

**Do not implement direct production deploy-on-merge.**
Adding `on: push: branches: [main]` to the existing deploy workflows is explicitly not
recommended. The resulting deploy-on-merge would be: automatic, ungated, without smoke
tests, without a staging boundary, without a rollback workflow, and without a production
approval step. That combination is not production-grade; it is fast-and-loose deployment
that would undermine the evidence discipline the platform has maintained throughout.

**Implement staging first.**
The `feat/staging-environment-phase-1` branch is the prerequisite for deploy-on-merge.
Staging Cloud Run services, a separate Terraform state prefix, staging secrets, and
staging smoke tests must exist and be validated before any form of automated deployment
is enabled.

**Then implement staging deploy-on-merge.**
Once staging exists, `feat/staging-deploy-workflow` can introduce automatic deployment
to staging on merge to `main`. This is safe because staging is isolated, staging data is
synthetic, and a failed staging deploy has no production impact.

**Then implement the manual production approval gate.**
`feat/prod-promotion-gate` introduces the GitHub Environment `production` protection rule.
Production remains manually approved even after staging deploy is automatic. The
combination -- automatic staging, gated production -- is the target production-grade
CI/CD posture for this platform.

**Next branch decision:**
The recommended next branch depends on whether the priority is documentation depth or
implementation progress:

- **If continuing docs-hardening:** `docs/slo-burn-rate-monitoring-plan` -- converts the
  documented production-light SLOs into a detailed burn-rate alerting design, completing
  the observability story. Closes the final major documentation gap identified in
  `docs/market-value-gap-audit-2026-2027.md`.
- **If moving to implementation:** `feat/staging-environment-phase-1` -- implements
  the staging resources (Terraform state prefix, Pub/Sub topics, Cloud Run services,
  Cloud SQL, secrets, service accounts) that are the direct prerequisite for
  deploy-on-merge. This is the higher-leverage choice for production-readiness.

The decision between these branches depends on the current portfolio priority: if a
technical interview or senior review is imminent, `docs/slo-burn-rate-monitoring-plan`
adds depth to the existing evidence base without GCP cost risk. If the goal is to
demonstrate working CI/CD automation, `feat/staging-environment-phase-1` is the
prerequisite that unlocks everything else in the deploy-on-merge roadmap.

---

## Validation Commands

```bash
git diff --check
uv run pytest -q
uv run ruff check .
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"
grep -En "deploy-on-merge-decision-record|DECISION RECORD -- deploy-on-merge" docs/EVIDENCE_INDEX.md
grep -En "Deploy|Promotion|GitHub Environments|Validation Gates|Rollback|Terraform Apply|Staging|Recruitment|Critical|Explicit Non-Claims|Final Recommendation" docs/deploy-on-merge-decision-record.md
gcloud sql instances describe rtdp-postgres --project=project-42987e01-2123-446b-ac7 --format="table(name,state,settings.activationPolicy)"
gcloud scheduler jobs list --project=project-42987e01-2123-446b-ac7 --location=europe-west1 --format="table(id,state,schedule)"
git status --short --branch
```

---

## Evidence Links

| Document | Purpose |
|---|---|
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog -- 60+ documents indexed by category |
| [docs/staging-environment-plan.md](staging-environment-plan.md) | Staging/prod separation strategy -- direct prerequisite for deploy-on-merge |
| [docs/market-value-gap-audit-2026-2027.md](market-value-gap-audit-2026-2027.md) | Gap audit identifying deploy-on-merge as Priority 5 gap |
| [docs/dataflow-decision-record.md](dataflow-decision-record.md) | Dataflow deferred; Cloud Run is current architecture; consistent with this deploy decision |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | Production-light SLO targets; incident runbooks; staging incidents separate from production |
| [docs/replay-backfill-strategy.md](replay-backfill-strategy.md) | Replay semantics; staging environment is appropriate rehearsal target for replay operations |
| [docs/dbt-observability-metrics-plan.md](dbt-observability-metrics-plan.md) | dbt metrics plan; environment label strategy defined; consistent with staging separation |
| [docs/platform-audit-after-cost-performance.md](platform-audit-after-cost-performance.md) | Platform audit; deploy-on-merge gap acknowledged |
| [docs/gap-closure-snapshot-after-steady-state.md](gap-closure-snapshot-after-steady-state.md) | Gap snapshot; automatic deploy-on-merge listed as remaining open |
| [docs/cost-performance-summary.md](cost-performance-summary.md) | Cost discipline; Cloud SQL STOPPED/NEVER, schedulers PAUSED; must be preserved by deploy workflows |
