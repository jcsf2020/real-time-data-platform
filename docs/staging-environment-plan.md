# Staging Environment Plan

**Status:** PLAN -- staging/prod separation strategy for the validated GCP data platform
**Date:** 2026-05-22
**Branch:** `docs/staging-environment-plan`
**Author intent:** Rigorous production-readiness architecture strategy. No unsupported claims.
No staging resources are created on this branch. No Terraform is applied. No GCP resources
are mutated. No Cloud SQL is started. No schedulers are resumed.

---

## 1. Context

### Current Architecture

The Real-Time Data Platform operates as a single-environment GCP deployment in project
`project-42987e01-2123-446b-ac7` (region: `europe-west1`). The validated event-processing
path is:

```
Pub/Sub (market-events-raw)
  → Cloud Run worker (rtdp-pubsub-worker, maxScale=1)
    → Cloud SQL PostgreSQL (rtdp-postgres, STOPPED/NEVER by default)
      → Cloud Run jobs (rtdp-dbt-refresh-job, rtdp-bigquery-append-job)
        → BigQuery (rtdp_analytics dataset, 3 DAY-partitioned tables)
          → Cloud Monitoring (4 logs-based metrics, 2 alert policies, email notification)
```

All GCP resources are Terraform-managed with a GCS-backed remote state
(`rtdp-terraform-state-project-42987e01-2123-446b-ac7`, prefix
`real-time-data-platform/gcp/prod`). CI runs on every push to main and every PR via
GitHub Actions with Workload Identity Federation. Deploy workflows are manual
(`workflow_dispatch` only).

### Why Staging/Prod Separation Matters

**For production-likeness:** A single-environment platform cannot safely validate infrastructure
changes before applying them to the only live environment. Every Terraform change, Cloud Run
deployment, or schema migration is a direct production risk with no rehearsal boundary.

**For recruitment value:** Senior technical reviewers and GCP platform interviewers treat
single-environment deployments as a production-readiness gap. The absence of a staging
boundary is a predictable interview challenge — acknowledged in the market-value gap audit
(`docs/market-value-gap-audit-2026-2027.md`) as a priority-4 gap with medium severity.

**For safe iteration:** Without staging isolation, controlled experiments (DLQ testing,
load testing, dbt schema changes) require careful one-shot procedures that contaminate
the production evidence base. A staging environment allows disposable data, disposable
resource state, and repeatable failure simulation.

### What This Document Is

This is a docs-only planning branch. It documents the target architecture, trade-off
analysis, recommended phased strategy, and explicit non-claims. It does not create
any GCP resources, modify any Terraform files, execute any `terraform apply`, start
Cloud SQL, or resume any Cloud Scheduler jobs.

---

## 2. Definitions

| Term | Definition |
|---|---|
| **environment** | A named, isolated deployment context with its own GCP resources, configuration, secrets, and operational state. Each environment is independently deployable and independently observable. |
| **dev** | A local developer workstation environment. Uses Docker Compose (Redpanda, PostgreSQL, FastAPI containers). No GCP resources. Not shared. |
| **staging** | A GCP environment that mirrors the production topology at reduced scale and cost. Used for pre-production validation, Terraform plan rehearsal, and safe failure simulation. Contains only synthetic data. |
| **production** | The live GCP environment. Currently the only GCP environment. Contains the authoritative event store (`bronze.market_events`), the BigQuery analytical tier (`rtdp_analytics`), and all validated Cloud Run services and jobs. |
| **promotion** | The controlled process of advancing a validated artifact (container image, Terraform plan, dbt model) from staging to production after passing defined validation gates. |
| **isolation boundary** | The technical or organisational mechanism that prevents staging activity from affecting production state. In GCP, this is achieved via separate projects (strongest) or namespace/prefix isolation within the same project (weaker). |
| **Terraform workspace** | A named Terraform state partition within a single backend and root module. Workspaces allow the same Terraform code to manage multiple environments with independent state files, but they share the same GCP credentials and project unless the provider configuration is parameterised. |
| **GCP project boundary** | A hard GCP isolation mechanism. Resources in separate GCP projects cannot directly access each other's networking, IAM, or APIs without explicit cross-project permissions. Separate projects provide the strongest isolation boundary available in GCP. |
| **environment parity** | The degree to which the staging environment mirrors the production environment in topology, configuration, and resource types. High parity means staging failures predict production failures accurately. |
| **blast radius** | The scope of impact of a failure, misconfiguration, or accidental mutation. In a single-environment platform, every incident has a blast radius covering 100% of the production evidence base. In a staged architecture, a staging incident is contained to the staging boundary. |
| **validation gate** | A defined, automatable check that must pass before a deployment is promoted. Examples: `terraform plan` producing PLAN_EXIT=0 in staging before a prod apply; smoke tests passing before traffic is shifted. |

---

## 3. Current Environment Baseline

### Resource Inventory

| Component | Current State | Evidence | Limitation |
|---|---|---|---|
| GCP project | Single project: `project-42987e01-2123-446b-ac7` | All evidence documents | No isolation boundary; all changes have production blast radius |
| Pub/Sub topic `market-events-raw` | Live; `prevent_destroy = true` | production-pubsub-dlq-evidence.md | No staging topic; any test events enter production ingestion path |
| Pub/Sub topic `market-events-raw-dlq` | Live; DLQ policy configured | production-pubsub-dlq-evidence.md | No staging DLQ; isolated DLQ testing requires ad-hoc ephemeral topics |
| Pub/Sub subscription `market-events-raw-worker-push` | Push subscription to Cloud Run worker; `maxDeliveryAttempts=5` | production-pubsub-dlq-evidence.md | No staging subscription; cannot test subscription config changes safely |
| Cloud Run service `rtdp-api` | Deployed; min_instances=0; max_instances=20 | cloud-run-terraform-import-plan-evidence.md | Single environment; any config change is a production risk |
| Cloud Run service `rtdp-pubsub-worker` | Deployed; maxScale=1; concurrency=1 | load-test-50000-cloud-evidence.md | Single environment; scaling changes affect the only worker |
| Cloud Run job `rtdp-dbt-refresh-job` | Deployed via Terraform; `dbt run PASS=2`, `dbt test PASS=22` proven | dbt-cloud-sql-incremental-execution-proof.md | No staging job; dbt schema changes go directly to production schemas |
| Cloud Run job `rtdp-bigquery-append-job` | Deployed via Terraform; cursor-based MERGE proven | bigquery-append-scheduler-proof-evidence.md | No staging job; BigQuery schema changes affect production tables |
| Cloud Run job `rtdp-silver-refresh-job` | Deployed; superseded by dbt path; PAUSED by default | silver-refresh-scheduler-execution-proof-evidence.md | Single environment; retained for evidence continuity |
| Cloud SQL `rtdp-postgres` | `NEVER / STOPPED`; PostgreSQL 16; region `europe-west1` | cloud-sql-terraform-import-plan-evidence.md | No staging Cloud SQL; any schema change affects the sole operational store |
| BigQuery dataset `rtdp_analytics` | 3 DAY-partitioned tables; 6,120 rows; `PLAN_EXIT=0` | bigquery-terraform-apply-evidence.md | No staging dataset; quality check thresholds and schema changes are untested before production |
| Cloud Scheduler `rtdp-silver-refresh-scheduler` | `PAUSED`; targets `rtdp-dbt-refresh-job:run` | dbt-scheduler-switch-evidence.md | No staging scheduler; cannot rehearse scheduler enable/disable sequences safely |
| Cloud Scheduler `rtdp-bigquery-append-scheduler` | `PAUSED`; `0 * * * *` Europe/Lisbon | bigquery-append-scheduler-proof-evidence.md | No staging scheduler; cannot rehearse append cadence changes safely |
| Cloud Monitoring metrics (×4 logs-based) | Active; datapoints confirmed | cloud-logs-based-metrics-datapoint-validation.md | No staging metrics namespace; staging events contaminate production dashboards |
| Cloud Monitoring alert policies (×2) | Enabled; email channel attached | cloud-alert-policies-evidence.md | Single alert channel; staging failures would page production operator email |
| BigQuery quality alert policy | Enabled; RTDP BigQuery Quality Failure | bigquery-quality-cloud-monitoring-alert-policy-evidence.md | No staging equivalent; cannot simulate alert policies without affecting production channel |
| Secret Manager `rtdp-database-url` | Metadata imported; no payload managed by Terraform | secret-manager-terraform-import-plan-evidence.md | Single production secret; staging Cloud SQL would need a separate connection string |
| IAM service accounts (×5) | `rtdp-scheduler-sa`, `rtdp-worker-sa`, `rtdp-pubsub-push-sa`, `rtdp-terraform-plan-ci`, `rtdp-cloud-run-deploy-ci` | service-accounts-terraform-import-plan-evidence.md | No staging service accounts; all CI/CD operations share production-level identities |
| Workload Identity Federation | Pool `github-actions`, provider `github`; OIDC; no stored keys | workload-identity-terraform-import-plan-evidence.md | Single pool/provider; staging CI would use same production OIDC provider |
| Terraform state (GCS backend) | Bucket `rtdp-terraform-state-project-42987e01-2123-446b-ac7`; prefix `real-time-data-platform/gcp/prod` | terraform-remote-backend-migration-evidence.md | State prefix already namespaced as `prod`; staging state does not exist |
| GitHub Actions CI | `ci.yml`, `terraform-plan.yml`, `bigquery-quality-checks.yml` | docs/EVIDENCE_INDEX.md CI/CD section | No environment-aware CI matrix; all CI runs target production project |
| GitHub Actions deploy workflows (×3) | `workflow_dispatch` only; no auto-deploy on merge | cloud-run-worker-manual-deploy-evidence.md, api-manual-deploy-evidence.md | No promotion workflow; no staging deploy gate before production deploy |
| Artifact Registry `rtdp` | Docker repository; images tagged with commit SHA | artifact-registry-terraform-import-plan-evidence.md | Single registry; no staging image prefix or tag strategy |

---

## 4. Why Single Environment Is a Gap

This section is direct and critical. These are accurate limitations, not softened concerns.

**No safe pre-production validation boundary.** Every Terraform change, Cloud Run deployment,
dbt model change, or BigQuery schema migration is applied directly to the production-equivalent
environment. There is no opportunity to rehearse changes in an isolated context before they
affect the authoritative evidence base.

**No isolated failure simulation.** Tests that require deliberate failure (malformed Pub/Sub
messages, controlled Cloud SQL schema errors, DLQ overflow simulation, alert policy threshold
testing) must be conducted against production resources using ad-hoc ephemeral resource patterns.
This introduces operational complexity and contamination risk on every test run.

**No promotion path.** There is no formalized process for moving a validated artifact from a
pre-production environment to production. Every deployment is a direct production deploy with
full blast radius. The absence of a promotion gate means there is no technical mechanism to
enforce a "staging-validated before production-applied" discipline.

**No safe Terraform apply rehearsal.** When Terraform changes involve resource additions,
modifications, or IAM changes, the only `terraform plan` run is against the production state.
A plan that looks clean locally may fail in apply with unexpected state drift. Staging would
allow a full apply rehearsal (using staging resources) before the production apply.

**No staging data set.** BigQuery quality checks, dbt incremental model changes, and append job
cursor logic are tested against the live production analytical dataset (`rtdp_analytics`).
A staging BigQuery dataset would allow destructive quality threshold tests, schema evolution
experiments, and append idempotency proofs without touching production row counts.

**No staging secrets.** There is one `rtdp-database-url` secret in Secret Manager. A staging
Cloud SQL instance would require a separate staging secret. Using the production secret in a
staging worker is a credential leakage risk. Using no secret means the staging worker cannot
connect to Cloud SQL and the staging environment is not end-to-end functional.

**Higher blast radius.** Any accidental misconfiguration (wrong scheduler enabled, Cloud SQL
left running, alert policy misconfigured, BigQuery table dropped) affects the production
environment directly. In a staged architecture, the worst-case blast radius is bounded to the
staging environment.

**Weaker production-readiness story.** For senior technical interviewers, a single-environment
GCP portfolio signals that the author has not operated production workloads at a team scale.
Production platforms universally require environment separation. Acknowledging this gap and
documenting a credible plan is more defensible than ignoring it.

---

## 5. Target Environment Topology

### Three-Tier Environment Model

```
┌─────────────────────────────────────────────────────────────────┐
│  dev / local                                                    │
│  Docker Compose: Redpanda, PostgreSQL 16, FastAPI, consumer     │
│  No GCP resources. Isolated per developer workstation.          │
│  Teardown: docker compose down -v                               │
└────────────────────────────┬────────────────────────────────────┘
                             │ PR + CI validation
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  staging (GCP)                                                  │
│  Reduced-scale mirror of production topology.                   │
│  Synthetic data only. Disposable. STOPPED/NEVER by default.     │
│  Cloud SQL: smallest viable tier (db-f1-micro or db-g1-small).  │
│  Cloud Run: min_instances=0, max_instances=1.                   │
│  BigQuery: separate dataset (rtdp_analytics_staging).           │
│  Terraform state: separate prefix or separate project.          │
└────────────────────────────┬────────────────────────────────────┘
                             │ Manual approval + promotion gate
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  production (GCP)                                               │
│  Current single environment: project-42987e01-2123-446b-ac7.    │
│  Authoritative evidence base. STOPPED/NEVER discipline.         │
│  Terraform state: real-time-data-platform/gcp/prod.             │
│  All current validated evidence remains in this environment.     │
└─────────────────────────────────────────────────────────────────┘
```

### Option A: Separate GCP Projects

Each environment lives in a distinct GCP project:

| Attribute | Staging | Production |
|---|---|---|
| GCP project ID | `rtdp-staging-<suffix>` (new) | `project-42987e01-2123-446b-ac7` (existing) |
| IAM boundary | Completely separate; no shared service accounts | Unchanged |
| Terraform state prefix | `real-time-data-platform/gcp/staging` | `real-time-data-platform/gcp/prod` (existing) |
| Pub/Sub topics | Identical names in staging project | Unchanged |
| Cloud SQL | Separate instance; smallest tier | `rtdp-postgres` (existing, STOPPED/NEVER) |
| BigQuery dataset | `rtdp_analytics` in staging project | `rtdp_analytics` in prod project |
| Secret Manager | Separate `rtdp-database-url` secret | Existing `rtdp-database-url` |
| Workload Identity | New pool in staging project OR same pool with repo-scoped provider | Existing pool/provider in prod |
| Cost | Additional project; Cloud SQL and Cloud Run charges when active | Unchanged |
| Isolation strength | **Maximum** -- hard GCP project boundary | N/A |
| Operational complexity | High -- two sets of everything to maintain | N/A |

**Pros:** Strongest possible isolation. IAM cannot leak between environments. A staging
failure cannot affect production API or production data. Mirrors enterprise production topology
credibly. Terraform apply in staging is genuinely rehearsed before prod.

**Cons:** Doubles operational overhead. Requires a second GCP billing account or careful project
cost controls. Requires cross-project Artifact Registry access or a staging registry. Requires
new Workload Identity setup in the staging project. Significantly more Terraform to maintain.

### Option B: Same GCP Project, Prefixed Resources and Terraform Workspaces

All environments live in the same GCP project with resource name prefixes:

| Attribute | Staging | Production |
|---|---|---|
| GCP project ID | `project-42987e01-2123-446b-ac7` (same) | `project-42987e01-2123-446b-ac7` (same) |
| IAM boundary | None (same project IAM) | N/A |
| Terraform state prefix | `real-time-data-platform/gcp/staging` | `real-time-data-platform/gcp/prod` (existing) |
| Pub/Sub topics | `staging-market-events-raw`, `staging-market-events-raw-dlq` | `market-events-raw`, `market-events-raw-dlq` |
| Cloud Run services | `rtdp-staging-api`, `rtdp-staging-pubsub-worker` | `rtdp-api`, `rtdp-pubsub-worker` |
| Cloud SQL | `rtdp-staging-postgres` (separate instance, smallest tier, STOPPED/NEVER) | `rtdp-postgres` (STOPPED/NEVER) |
| BigQuery dataset | `rtdp_analytics_staging` | `rtdp_analytics` |
| Secret Manager | `rtdp-staging-database-url` | `rtdp-database-url` |
| Service accounts | `rtdp-staging-worker-sa@...`, etc. | `rtdp-worker-sa@...`, etc. |
| Cost | Additional Cloud SQL instance + Cloud Run when active; cheaper than separate project | Unchanged |
| Isolation strength | **Weak** -- same project; staging service accounts can access production secrets if IAM is misconfigured | N/A |
| Operational complexity | Medium -- one project; prefix discipline required | N/A |

**Pros:** No new GCP project or billing setup. Uses existing Workload Identity pool. Lower
operational overhead. Terraform code is simpler (same provider block; only variable differences).
Staging state prefix mirrors prod prefix pattern already established. Good enough for portfolio
demonstration of environment separation awareness.

**Cons:** Not true isolation. An IAM misconfiguration or a Terraform mistake that targets the
wrong resource could affect production. A staging Cloud Run worker with access to the production
database secret is not genuinely isolated. Senior reviewers will note that same-project staging
is not equivalent to production staging. Blast radius is still GCP-project-wide for IAM,
billing, and quota exhaustion.

### Recommendation

**For this portfolio project:** Option B (same-project prefixed staging) is the recommended
interim step.

**Rationale:** Option A (separate GCP projects) is the correct production-like architecture.
For a solo portfolio project with bounded GCP budget and no requirement for concurrent
multi-engineer operation, the cost and operational overhead of two full GCP projects is not
justified before the staging plan is validated as a working concept.

**Honest caveat for senior reviewers:** Same-project prefixed staging is explicitly acknowledged
as a weaker isolation boundary than separate GCP projects. It is documented here as an interim
step, not as a claim of enterprise-grade environment isolation. The plan explicitly defines
Option A as the target when budget and operational need justify it.

**The recommendation is conservative and phased:** start with same-project prefixed staging,
evaluate whether the isolation is sufficient for the evidence goals, then escalate to Option A
if continued portfolio development or actual production use demands it.

---

## 6. Recommended Environment Strategy

### Phase 0: Documentation Only (This Branch)

**Scope:** Document the staging/prod separation plan. No GCP resources created. No Terraform
changed. No staging environment implemented.

**Output:** This document (`docs/staging-environment-plan.md`). Evidence index row updated.

**Value:** Closes the documentation gap. Provides a credible, auditable staging strategy for
technical interviews and senior reviewer scrutiny.

### Phase 1: Same-Project Prefixed Staging (Low-Cost Rehearsal)

**Scope:** Create a `staging` Terraform state prefix with prefixed resources in the same GCP
project (`project-42987e01-2123-446b-ac7`). No production resources modified.

**Resources to create:**

- Terraform workspace or state prefix: `real-time-data-platform/gcp/staging`
- Pub/Sub: `staging-market-events-raw`, `staging-market-events-raw-dlq`
- Pub/Sub subscription: `staging-market-events-raw-worker-push` (push to staging worker)
- Cloud Run worker: `rtdp-staging-pubsub-worker` (min_instances=0, max_instances=1)
- Cloud SQL: `rtdp-staging-postgres` (db-f1-micro or db-g1-small; `NEVER / STOPPED` by default)
- BigQuery dataset: `rtdp_analytics_staging`
- Secret Manager: `rtdp-staging-database-url`
- Cloud Scheduler jobs: `PAUSED` by default
- Service accounts: `rtdp-staging-worker-sa`, `rtdp-staging-scheduler-sa`

**Branch:** `feat/staging-environment-phase-1`

**Acceptance criteria:** PLAN_EXIT=0 for prod after staging apply; staging resources prefixed
and isolated at the resource name level; Cloud SQL STOPPED/NEVER; schedulers PAUSED.

### Phase 2: Separate Staging GCP Project

**Scope:** Create a new GCP project (`rtdp-staging-<suffix>`) with full environment parity
at reduced scale. Separate billing account or budget alert. Separate Workload Identity setup.

**Prerequisites:** Phase 1 validated as working concept; budget approved for second project;
operational demand (team growth or sustained iteration) justifies the overhead.

**Branch:** `feat/staging-project-isolation`

**Acceptance criteria:** Complete Terraform apply in staging project; zero-diff prod Terraform
plan; separate IAM; separate secrets; separate OIDC provider.

### Phase 3: Promotion Workflow and Deploy Gates

**Scope:** Automated or semi-automated promotion from staging to production with defined
validation gates. CI deploys to staging on PR merge; manual approval required for prod
promotion; PLAN_EXIT=0 for prod is a mandatory gate.

**Branch:** `feat/promotion-workflow-deploy-gates`

**Acceptance criteria:** Staging deploy is gated on smoke tests; prod deploy requires manual
approval after staging validation; no prod deploy without staging evidence.

---

## 7. Resource Separation Plan

| Resource Type | Current Prod Resource | Proposed Staging Equivalent | Isolation Requirement | Terraform Implication | Cost Implication |
|---|---|---|---|---|---|
| Pub/Sub topic (main) | `market-events-raw` | `staging-market-events-raw` | Resource name prefix | New `google_pubsub_topic` in staging module | Negligible (Pub/Sub topics are free; delivery costs scale with messages) |
| Pub/Sub topic (DLQ) | `market-events-raw-dlq` | `staging-market-events-raw-dlq` | Resource name prefix | New `google_pubsub_topic` in staging module | Negligible |
| Pub/Sub subscription | `market-events-raw-worker-push` | `staging-market-events-raw-worker-push` | Separate subscription targeting staging worker URL | New `google_pubsub_subscription` pointing to staging Cloud Run | Low (message delivery costs only during test runs) |
| Cloud Run worker | `rtdp-pubsub-worker` | `rtdp-staging-pubsub-worker` | Separate service; staging subscription only | New `google_cloud_run_v2_service` with staging name and staging secret ref | Very low (min_instances=0; billed only on request) |
| Cloud Run API | `rtdp-api` | `rtdp-staging-api` | Separate service; staging database secret only | New `google_cloud_run_v2_service` with staging name | Very low (min_instances=0) |
| Cloud Run job (dbt) | `rtdp-dbt-refresh-job` | `rtdp-staging-dbt-refresh-job` | Separate job; staging database secret | New `google_cloud_run_v2_job` | Low (billed only on execution) |
| Cloud Run job (BigQuery append) | `rtdp-bigquery-append-job` | `rtdp-staging-bigquery-append-job` | Separate job; staging BigQuery dataset | New `google_cloud_run_v2_job` with staging env vars | Low |
| Cloud SQL instance | `rtdp-postgres` (STOPPED/NEVER) | `rtdp-staging-postgres` (STOPPED/NEVER) | Separate instance; separate connection string | New `google_sql_database_instance`; activation_policy=NEVER | Medium: db-f1-micro ~$7-9/month if running; STOPPED/NEVER = $0 storage only |
| BigQuery dataset | `rtdp_analytics` | `rtdp_analytics_staging` | Separate dataset; staging tables | New `google_bigquery_dataset` and table resources | Low (storage costs for small dataset; query costs on test runs) |
| Cloud Scheduler (dbt) | `rtdp-silver-refresh-scheduler` (PAUSED) | `rtdp-staging-silver-refresh-scheduler` (PAUSED) | Separate job; PAUSED by default | New `google_cloud_scheduler_job` with paused=true | Negligible |
| Cloud Scheduler (BigQuery append) | `rtdp-bigquery-append-scheduler` (PAUSED) | `rtdp-staging-bigquery-append-scheduler` (PAUSED) | Separate job; PAUSED by default | New `google_cloud_scheduler_job` with paused=true | Negligible |
| Secret Manager secret | `rtdp-database-url` | `rtdp-staging-database-url` | Separate secret; staging Cloud SQL connection string | New `google_secret_manager_secret`; version managed manually or via CI | Negligible (Secret Manager charges per access and per version) |
| Artifact Registry | `rtdp` repository | Same repository with staging image tags (e.g. `staging-<SHA>`) OR separate `rtdp-staging` repository | Tag or repository prefix; staging images must not be deployed to prod | Tag strategy preferred (lower cost); separate repo if IAM isolation required | Negligible for same repo; low for new repo |
| Cloud Monitoring metrics | `custom.googleapis.com/rtdp/...` | `custom.googleapis.com/rtdp/staging/...` OR same metric with `environment=staging` label | Metric namespace or label isolation | New `google_logging_metric` with staging filter; or label-based filter on existing metrics | Negligible |
| Alert policies | `RTDP Worker Message Error Alert`, `RTDP Silver Refresh Error Alert` | Separate staging alert policies (disabled notification channel OR silent by default) | Staging alerts must not page production operator | New `google_monitoring_alert_policy` with staging filter; staging notification channel disabled | Negligible |
| Notification channels | `RTDP Operator Email Alerts` | Separate staging notification channel (disabled or separate email address) | Staging alerts must not deliver to production email | New `google_monitoring_notification_channel` | Negligible |
| IAM service accounts | `rtdp-worker-sa`, `rtdp-scheduler-sa`, `rtdp-pubsub-push-sa` | `rtdp-staging-worker-sa`, `rtdp-staging-scheduler-sa`, `rtdp-staging-pubsub-push-sa` | Least-privilege, scoped to staging resources only | New `google_service_account` resources per role per environment | Negligible |
| Workload Identity | Pool `github-actions`, provider `github` | Same pool; separate service account binding for staging CI | Staging CI must not have permissions to mutate prod resources | New `google_service_account_iam_member` for staging-specific CI service account | None |

---

## 8. Terraform Design Options

### Option 1: Terraform Workspaces

Use `terraform workspace select staging` and `terraform workspace select prod`. Workspace name
is surfaced via `terraform.workspace` and used in resource names and labels.

| Attribute | Value |
|---|---|
| Pros | Single root module; workspace switch is simple; state is backend-partitioned |
| Cons | Same provider block (same GCP project by default); workspace isolation does not enforce project separation; easy to apply to the wrong workspace; not composable with separate GCP projects without additional provider configuration |
| Cost | None additional |
| Operational complexity | Low initially; increases when environments diverge in configuration |
| Recommendation | **Acceptable for same-project prefixed staging (Phase 1).** Not recommended for separate GCP project isolation. |

### Option 2: Separate `tfvars` Files

Maintain `infra/terraform/gcp/staging.tfvars` and `infra/terraform/gcp/prod.tfvars`.
Each file overrides `project_id`, `environment`, and resource-specific variables.

| Attribute | Value |
|---|---|
| Pros | No Terraform workspace complexity; explicit per-environment variable overrides; easy to review and audit; compatible with existing `variables.tf` which already defines `variable "environment"` with default `"prod"` |
| Cons | Single state file unless backend is also parameterised; running `terraform plan -var-file=staging.tfvars` against the prod state bucket is a misconfiguration risk; requires backend partial configuration or wrapper scripts |
| Cost | None additional |
| Operational complexity | Medium; backend parameterisation is required to prevent state collisions |
| Recommendation | **Preferred for same-project staging (Phase 1)** when combined with a separate state prefix per environment. The existing `variable "environment"` in `variables.tf` is already a foundation for this approach. |

### Option 3: Separate Root Modules

Maintain `infra/terraform/gcp/staging/` and `infra/terraform/gcp/prod/` as independent root
modules, each with their own `main.tf`, `variables.tf`, and `backend.tf`.

| Attribute | Value |
|---|---|
| Pros | Maximum code clarity; no shared state risk; each environment is independently reviewable; easy to apply only to one environment |
| Cons | Code duplication; shared modules require a `modules/` directory to avoid drift between staging and prod; more files to maintain |
| Cost | None additional |
| Operational complexity | Medium-high for initial setup; lower once the module structure is established |
| Recommendation | **Preferred for separate GCP project isolation (Phase 2).** Use a shared `modules/rtdp-platform/` module called by both root modules. |

### Option 4: Separate State Buckets

Each environment uses a separate GCS bucket for Terraform state.

| Attribute | Value |
|---|---|
| Pros | Strongest state isolation; reduces the risk of a single corrupted state file affecting both environments; mirrors enterprise practice |
| Cons | Requires a new GCS bucket; bucket IAM must be separately managed; more backend configuration |
| Cost | Negligible (GCS storage is cheap; state files are small) |
| Operational complexity | Low incremental cost over separate prefixes in the same bucket |
| Recommendation | **Preferred for Phase 2 (separate GCP projects).** Each project has its own state bucket. For Phase 1 (same project), separate prefixes in the existing bucket are sufficient. |

### Option 5: Separate GCP Projects

Each environment is a full GCP project with its own provider configuration.

| Attribute | Value |
|---|---|
| Pros | Strongest isolation; mirrors enterprise multi-project architecture; IAM cannot leak between environments; billing is separately tracked; quota exhaustion in staging cannot affect prod |
| Cons | Highest operational overhead; requires new project creation, billing setup, API enablement, Workload Identity setup, and cross-project Artifact Registry permissions; doubles Terraform management surface |
| Cost | Additional GCP project overhead; Cloud SQL and Cloud Run charges if staging resources are active |
| Operational complexity | High; appropriate for multi-engineer teams or genuine production workloads |
| Recommendation | **Target architecture for Phase 2.** Not the immediate next step for this solo portfolio project. |

### Recommendation for This Project

**Phase 1:** Separate `tfvars` files (`staging.tfvars`, `prod.tfvars`) with separate state
prefixes in the existing GCS bucket (`real-time-data-platform/gcp/staging` and
`real-time-data-platform/gcp/prod`). The existing `variable "environment"` in `variables.tf`
is already a foundation — its default is `"prod"`, which is correctly aligned. Staging would
pass `environment = "staging"` to parameterise resource names and labels. This approach
requires minimal structural change to the existing Terraform configuration.

**Phase 2:** Separate root modules calling a shared `modules/rtdp-platform/` module; separate
GCP projects; separate state buckets; separate Workload Identity pools.

---

## 9. CI/CD and Promotion Model

### Current State

CI is automated: `ci.yml` runs `pytest`, `ruff`, and `terraform plan` on every push to `main`
and every PR. Deployment is manual: `deploy-worker-cloud-run.yml` and `deploy-api-cloud-run.yml`
require explicit `workflow_dispatch`. There is no auto-deploy on merge. There is no staging
deploy. There is no promotion gate. This is acknowledged as a known gap; it is documented in
the evidence index and in `docs/market-value-gap-audit-2026-2027.md`.

**This branch does not change any CI/CD workflow.** The following is a design for the future
promotion model.

### Future Promotion Flow (Design Only)

```
Developer pushes PR branch
  │
  ▼
ci.yml (automatic, on every PR)
  ├── pytest (241+ tests)
  ├── ruff check
  ├── terraform fmt -check
  ├── terraform validate
  └── terraform plan (prod state, -detailed-exitcode; must be PLAN_EXIT=0)
  │
  ▼  PR merged to main
  │
  ▼
staging-deploy.yml (triggered on merge to main OR workflow_dispatch)
  ├── terraform plan for staging (PLAN_EXIT must be 0 or 2 with review)
  ├── terraform apply for staging (staging state only)
  ├── docker build + push with staging image tag
  ├── gcloud run deploy to staging Cloud Run services/jobs
  ├── staging smoke tests:
  │     ├── health check: curl staging API /health
  │     ├── Pub/Sub publish 10 synthetic events to staging topic
  │     ├── verify 10 worker OK logs in staging Cloud Logging
  │     └── verify Cloud SQL staging row count (if Cloud SQL active window)
  └── upload staging evidence artifact (run ID, Cloud SQL state, scheduler state)
  │
  ▼  Manual approval gate (GitHub Environment protection rule)
  │
  ▼
prod-deploy.yml (requires manual approval after staging validation)
  ├── terraform plan for prod (PLAN_EXIT must be 0 before any apply)
  ├── terraform apply for prod (if Terraform changes are in scope)
  ├── docker build + push with prod image tag (or promote staging image)
  ├── gcloud run deploy to prod Cloud Run services/jobs
  ├── post-prod validation:
  │     ├── health check: curl prod API /health
  │     └── verify Cloud SQL state: STOPPED / NEVER
  └── upload prod evidence artifact (run ID, PLAN_EXIT, Cloud SQL state)
```

### CI Workflow Inventory (Current vs Future)

| Workflow | Current Trigger | Current Scope | Future Trigger | Future Scope |
|---|---|---|---|---|
| `ci.yml` | Push to main / PR | pytest, ruff, Terraform plan (prod) | Push to main / PR | Same + optional staging Terraform plan |
| `terraform-plan.yml` | Push to main / PR (infra path) | Terraform plan (prod only) | Push to main / PR | Staging plan on feature branches; prod plan on main |
| `deploy-worker-cloud-run.yml` | `workflow_dispatch` | Build + deploy to prod worker | `workflow_dispatch` (staging); manual approval (prod) | Staging deploy automatic; prod gated |
| `deploy-api-cloud-run.yml` | `workflow_dispatch` | Build + deploy to prod API | Same phased approach | Staging first; prod gated |
| `bigquery-quality-checks.yml` | `workflow_dispatch` + cron `15 6 * * *` | Read-only quality checks against prod BigQuery | Extend with staging dataset | Staging quality checks (synthetic data) before prod |
| `staging-deploy.yml` | Does not exist | N/A | Merge to main OR `workflow_dispatch` | Build + deploy + smoke test staging environment |
| `prod-deploy.yml` | Does not exist | N/A | Manual approval after staging validation | Build + deploy + validate production environment |

**Important:** This branch does not implement any of the future workflows. The `staging-deploy.yml`
and `prod-deploy.yml` files do not exist and are not created on this branch. The design above
is the documented target for a future `feat/promotion-workflow-deploy-gates` branch.

---

## 10. Data Strategy for Staging

**Synthetic data only.** The staging environment must never contain production event data.
All staging load tests use synthetic `MarketEvent` records with deterministic `event_id`
prefixes (e.g. `staging-lt-<run-id>-<seq>`) that identify the data as staging-origin.

**No production PII.** `MarketEvent` records contain trade symbols, prices, and quantities
but no personal data. The synthetic staging events use fabricated symbols and quantities.
No real market data should flow through a staging pipeline even if the data is not
considered sensitive.

**Bounded staging load tests.** Staging load tests should be bounded and smaller than
production-equivalent tests: the staging Cloud Run worker is maxScale=1 and the staging
Cloud SQL instance is the smallest viable tier. A staging load test of 1,000 to 5,000 events
is appropriate as a smoke test. The 50,000-event production evidence does not need to be
replicated in staging.

**Smaller Cloud SQL / BigQuery footprint.** The staging Cloud SQL instance uses the smallest
tier that is sufficient for functional validation. The staging BigQuery dataset contains only
staging test rows. Row counts in staging are not an evidence claim.

**Scheduler disabled by default.** All staging Cloud Scheduler jobs are `paused = true` in
Terraform. No staging scheduler should run continuously or automatically. Scheduler execution
in staging is a deliberate, time-bounded manual operation.

**Cloud SQL STOPPED / NEVER by default.** The staging Cloud SQL instance follows the same
`activation_policy = "NEVER"` discipline as production. It is started only during bounded
staging validation windows and returned to STOPPED/NEVER immediately after. This applies
regardless of Phase 1 or Phase 2 topology.

**Staging data is disposable.** The staging Cloud SQL database and staging BigQuery dataset
may be wiped and recreated for each staging test cycle. There is no staging data retention
requirement. A `terraform destroy` of staging resources followed by `terraform apply` should
be a safe, repeatable operation with no production impact.

**BigQuery staging dataset is separate from production.** The `rtdp_analytics_staging`
dataset must never be used as a source for production quality checks, dashboards, or alerts.
Quality check workflows must explicitly target either the staging or production dataset,
never both, and the target must be parameterised, not hardcoded.

---

## 11. Secrets and IAM Strategy

**Separate staging secrets.** The staging Cloud SQL connection string must be stored as a
separate Secret Manager secret (`rtdp-staging-database-url`). No staging Cloud Run service
or job should reference `rtdp-database-url` (the production secret). This prevents a staging
worker misconfiguration from connecting to the production database.

**Least-privilege staging service accounts.** Each staging Cloud Run service and job has its
own staging service account (`rtdp-staging-worker-sa`, `rtdp-staging-scheduler-sa`,
`rtdp-staging-pubsub-push-sa`). These accounts have `roles/run.invoker` scoped to staging
Cloud Run resources only and `roles/cloudsql.client` on the staging Cloud SQL instance only.
They must not have any permissions on production resources.

**Workload Identity separation.** For Phase 1 (same-project), the existing Workload Identity
pool (`github-actions`) can be reused with a separate staging-specific CI service account
(`rtdp-staging-terraform-apply-ci`) that has permissions to create and modify staging resources
only. For Phase 2 (separate project), a new Workload Identity pool and OIDC provider are
created in the staging project.

**No shared prod/staging credentials.** Production and staging service accounts must not share
keys, federated credentials, or IAM roles. The `rtdp-worker-sa` account (production) must
not be granted any permissions in the staging resource namespace. Conversely, staging service
accounts must not have any production resource permissions.

**Secret Manager naming convention.** All staging secrets follow the prefix convention
`rtdp-staging-<secret-name>`. All production secrets follow `rtdp-<secret-name>` without
the staging prefix. This naming convention is enforced at Terraform resource level
(`name = "rtdp-staging-${var.secret_name}"` in the staging module).

**CI permissions by environment.** The CI service account for staging deploys
(`rtdp-staging-terraform-apply-ci`) has `roles/run.developer` and
`roles/cloudsql.admin` on staging resources only. The CI service account for production
deploys (`rtdp-cloud-run-deploy-ci`) retains its existing scoped production permissions.
These accounts must not be interchangeable.

**Avoid service account keys.** No staging or production service account keys are generated
or stored. All CI authentication uses Workload Identity Federation (OIDC). This mirrors the
existing production pattern and eliminates key rotation risk.

---

## 12. Observability and Alerting Strategy

**Staging alerts must not page the production channel.** The production notification channel
(`RTDP Operator Email Alerts`, channel ID `1439157631105258885`) must not be attached to
any staging alert policy. Staging alert policies use a separate disabled notification channel
(`rtdp-staging-email-alerts`) or have no notification channels attached. This ensures that
a staging load test or staging quality failure does not deliver email to the production
operator address.

**Separate staging alert policies.** Staging Cloud Monitoring alert policies (if created)
use metric filters scoped to the staging environment label or staging Cloud Run service name.
A staging alert policy with `resource.labels.service_name = "rtdp-staging-pubsub-worker"`
cannot match production worker metrics.

**Staging metrics labelled by environment.** Custom Cloud Monitoring metrics emitted from
staging Cloud Run jobs and scripts include an `environment = "staging"` label in the metric
point. Production metrics use `environment = "prod"`. This label enables metric filter
separation in alert policies and dashboards.

**Production dashboards must not mix staging data.** The RTDP Pipeline Overview Cloud
Monitoring dashboard (4-panel, created in production) must not display staging metrics.
If a staging dashboard is created, it is a separate dashboard resource. Any shared metric
namespace (`custom.googleapis.com/rtdp/...`) must be filtered by environment label
before display.

**dbt observability metrics must include environment labels.** The future dbt-specific
Cloud Monitoring metrics defined in `docs/dbt-observability-metrics-plan.md` must be
designed from the start to include an `environment` label. This enables filtering dbt
run metrics by environment in staging and production without schema evolution.

---

## 13. Cost Control Strategy

**Cloud SQL stopped by default in both environments.** Both `rtdp-postgres` (production)
and `rtdp-staging-postgres` (proposed staging) use `activation_policy = "NEVER"`.
Neither instance runs continuously. Cloud SQL costs are incurred only during bounded,
time-limited validation windows. This is the established discipline proven in 60+ evidence
documents and must be preserved in the staging configuration.

**Schedulers paused by default.** All Cloud Scheduler jobs in both environments use
`paused = true` in Terraform. No scheduler should be enabled persistently in staging.
Scheduler execution is a deliberate, time-bounded manual operation in both environments.

**min_instances = 0 where possible.** All Cloud Run services in staging use
`min_instance_count = 0`. Staging Cloud Run instances scale to zero when idle. There is no
reason for a staging Cloud Run service to maintain a warm instance between test runs.

**Staging uses smallest viable resources.** The staging Cloud SQL instance targets the
smallest tier that supports functional validation: `db-f1-micro` or `db-g1-small`.
The staging Cloud Run worker uses `max_instance_count = 1` (same as production but already
the minimum viable). Staging BigQuery usage is bounded to small synthetic datasets.

**Dataflow remains deferred.** The Dataflow decision record (`docs/dataflow-decision-record.md`)
established that Dataflow is not justified at the current validated scale. This applies equally
to staging. No Dataflow staging path is planned or implemented. Staging data processing uses
Cloud Run jobs, consistent with the production architecture.

**Cost-per-event remains not claimed.** The cost-per-event formula is defined in
`docs/cost-performance-summary.md` but no billing export analysis has been performed.
Staging adds marginal Cloud SQL storage costs and occasional Cloud Run execution costs.
These costs are not claimed or quantified in this plan. The formula can be extended to
cover staging resource costs once a billing export analysis is performed.

**Staging must not run continuous jobs without explicit approval.** No staging Cloud Run
job, Cloud Scheduler job, or BigQuery append job should run on a continuous schedule
without a deliberate, time-bounded activation. Continuous staging execution risks uncontrolled
cloud spend and unintended database growth. All staging executions must have an explicit
start and stop boundary.

---

## 14. Validation Gates

The following gates must pass before any staging environment is considered validated and
before any promotion to production is considered.

### Per-PR / Per-Commit Gates (Already Implemented)

| Gate | Command | Expected Result |
|---|---|---|
| Code style | `uv run ruff check .` | No issues |
| Test suite | `uv run pytest -q` | All tests pass (241+ tests) |
| Terraform format | `terraform fmt -check -recursive infra/terraform/gcp` | No formatting differences |
| Terraform validate | `terraform -chdir=infra/terraform/gcp validate` | Success |
| Terraform plan (prod) | `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false` | `PLAN_EXIT=0` |
| Whitespace check | `git diff --check` | No trailing whitespace |

### Staging Deployment Gates (Future, Phase 1+)

| Gate | Command / Check | Expected Result |
|---|---|---|
| Staging Terraform plan | `terraform plan -var-file=staging.tfvars -detailed-exitcode` | `PLAN_EXIT=0` or `PLAN_EXIT=2` with review |
| Staging smoke test: API health | `curl https://rtdp-staging-api-<hash>.run.app/health` | HTTP 200 |
| Staging smoke test: Pub/Sub round-trip | Publish 10 synthetic events; verify 10 worker OK logs | 10/10 matched |
| Row-count check (staging) | BigQuery: `SELECT COUNT(*) FROM rtdp_analytics_staging.market_events_raw` | Expected staging row count |
| Cloud SQL staging state check | `gcloud sql instances describe rtdp-staging-postgres --format="table(name,state,settings.activationPolicy)"` | `STOPPED / NEVER` |
| Scheduler staging state check | `gcloud scheduler jobs list ... --format="table(id,state)"` | All staging schedulers `PAUSED` |
| dbt staging test | `dbt test --target staging` (inside staging Cloud Run job) | `PASS=22` |

### Production Promotion Gates (Future, Phase 3)

| Gate | Check | Condition |
|---|---|---|
| Staging validation complete | All staging gates above passed | Hard requirement; no promotion without staging evidence |
| Prod Terraform plan is no-op | `PLAN_EXIT=0` for prod plan | Hard requirement; any drift blocks promotion |
| Manual approval | GitHub Environment protection rule | At least one designated reviewer approves |
| Post-prod health check | `curl prod-api/health` | HTTP 200 |
| Cloud SQL prod state | `STOPPED / NEVER` after any validation window | Hard requirement |
| Scheduler prod state | All schedulers `PAUSED` | Hard requirement unless scheduler enable is in scope |
| PLAN_EXIT captured | `echo "PLAN_EXIT=$?"` in CI artifact | Must be `0` post-promotion |

---

## 15. Failure and Rollback Model

### Failed Staging Deploy

**Symptom:** Staging Terraform apply fails; staging Cloud Run deploy returns non-zero exit code;
staging smoke tests fail.

**Response:** Do not promote to production. Investigate the staging failure in isolation.
The production environment is unaffected. Fix the issue in the staging branch, re-run the
staging deploy, and repeat validation gates. Document the failure and fix as a staging evidence
artifact.

**Rollback:** If staging Terraform apply partially completes, run `terraform plan` to identify
drift, then `terraform apply` again to converge. Staging resource partial state does not affect
production.

### Failed Production Deploy

**Symptom:** Production Cloud Run deploy returns non-zero exit code; post-prod health check fails.

**Response:** Immediately run `gcloud run services describe` to determine the current serving
revision. If the new revision is not serving traffic, the previous revision remains active.
If the new revision is serving and unhealthy, revert by deploying the previous known-good
image tag. Document the failure as a production incident in `docs/SLO_AND_INCIDENT_RESPONSE.md`.

**Rollback:** Deploy the previous known-good container image using the existing
`workflow_dispatch` deploy workflow. The previous commit SHA is available in the Artifact
Registry image history.

### Failed Terraform Plan

**Symptom:** `terraform plan` returns `PLAN_EXIT=1` (error) or `PLAN_EXIT=2` (pending changes
when zero-diff is expected).

**Response:** `PLAN_EXIT=1` is a hard error; do not apply. `PLAN_EXIT=2` for prod when
zero-diff is expected indicates unexpected drift. Inspect the plan output to identify
the drifted resource. Investigate whether live GCP state was mutated outside Terraform.
Do not run `terraform apply` until the source of drift is understood.

**Rollback:** Revert the Terraform change that introduced the drift. Import the drifted
resource back into state if necessary. Restore the zero-diff baseline before the next PR.

### Unexpected Terraform Drift

**Symptom:** A resource in GCP has been mutated outside of Terraform (e.g. Cloud Run revision
updated via console, IAM binding changed manually).

**Response:** Do not run `terraform apply` blindly. Inspect the drift using
`terraform plan -refresh-only`. If the drift is intentional, import the new state. If the
drift is unintentional, document the incident and restore the intended state using Terraform.

### Bad BigQuery Append

**Symptom:** BigQuery append job completes but row count is incorrect; duplicate rows observed;
`staging_table_empty` check fails.

**Response:** In staging: wipe the staging dataset and re-run. Staging data is disposable.
In production: the BigQuery append job uses a cursor-based MERGE with idempotency. A repeated
append run should produce the same row count. If duplicates are observed, investigate the
cursor logic in the job. The cursor is stored in the staging table; verify it was not reset.

### Bad dbt Refresh

**Symptom:** `dbt run` exits with `ERROR=N`; `dbt test` exits with `FAIL=N`.

**Response:** In staging: investigate the dbt model error in isolation. The staging Cloud SQL
schema is disposable. Re-run after fixing.
In production: a `dbt run ERROR` does not modify the target tables if the error occurs before
the write. A `dbt test FAIL` indicates data quality regression. Trigger the incident response
procedure from `docs/SLO_AND_INCIDENT_RESPONSE.md` for data quality failures.

### Scheduler Accidentally Enabled

**Symptom:** A Cloud Scheduler job transitions from `PAUSED` to `ENABLED` (e.g. via console,
Terraform misconfiguration, or manual `gcloud` command).

**Response:** Immediately pause the scheduler: `gcloud scheduler jobs pause <job-name>`.
Verify Cloud SQL state (if the job targets a Cloud SQL-dependent Cloud Run job, Cloud SQL
may have been started by the job execution). Return Cloud SQL to `STOPPED/NEVER`. Document
the incident. Investigate the source of the accidental enable. Update Terraform to explicitly
enforce `paused = true` if the configuration was ambiguous.

### Cloud SQL Accidentally Left Running

**Symptom:** `gcloud sql instances describe rtdp-postgres` returns `state: RUNNABLE` outside
a declared validation window.

**Response:** Immediately stop the instance: `gcloud sql instances patch rtdp-postgres --activation-policy=NEVER`.
Verify no active connections remain. Document the incident with the duration Cloud SQL was
running and the estimated cost impact. Investigate whether a Cloud Run job or scheduler
triggered the start. Add a guard to the Terraform configuration to prevent future accidental starts.

### Alert Noise from Staging

**Symptom:** Staging Cloud Monitoring alert policy triggers and delivers to the production
notification channel.

**Response:** This should not happen if the staging alert policies are correctly configured
with separate or disabled notification channels. If it does happen, immediately detach the
production notification channel from all staging alert policies. Review the staging alert
policy `notification_channels` configuration in Terraform. Update to use a staging-only
channel or remove notification channels from staging alert policies entirely.

---

## 16. Production-Likeness Assessment

### What Is Already Production-Like

| Capability | Assessment |
|---|---|
| Terraform IaC | Strong -- 100% GCP resource coverage; GCS-backed remote state; zero-diff discipline; `prevent_destroy` guards on critical resources |
| Workload Identity Federation | Strong -- OIDC for CI; no stored service account keys; repository-scoped attribute condition |
| Least-privilege IAM | Good -- job-scoped `roles/run.invoker` for scheduler; no project-wide editor binding; service accounts per role |
| Secret Manager | Good -- secrets are not in code or CI environment variables; runtime injection only |
| Idempotent event processing | Strong -- `ON CONFLICT(event_id) DO NOTHING`; proven at 50,000 events and 0 duplicates |
| Observability | Good -- structured JSON logs; 4 logs-based Cloud Monitoring metrics; 4-panel dashboard; 2 alert policies; email delivery proven |
| Alerting loop | Good -- quality failure → Cloud Monitoring incident → email proven end-to-end |
| DLQ policy | Good -- `deadLetterPolicy`; `maxDeliveryAttempts=5`; backoff configured; malformed routing validated |
| CI discipline | Strong -- pytest (241+ tests); ruff; Terraform plan; dbt compile/run/test on every push |
| SLO documentation | Adequate -- production-light SLO targets; error budget; severity levels; incident runbooks documented |

### What Remains Portfolio-Grade

| Gap | Assessment |
|---|---|
| Single GCP environment | No staging isolation; full blast radius for every change; not equivalent to enterprise production |
| Manual deploy on merge | CD is manual workflow_dispatch; deploy-on-merge is not implemented; no automated promotion gate |
| Cloud SQL STOPPED/NEVER posture | Correct for cost control; not a production availability posture; a real production Cloud SQL instance runs continuously |
| No multi-day stability proof | All validation runs are bounded 30-60 minute windows; no continuous traffic proven |
| No promotion workflow | Changes go directly to the only production environment after CI; no staging gate |
| No staging data | All evidence data (6,120 BigQuery rows, 50,000 Cloud SQL events) is the production evidence base |
| Exact cost per event not claimed | Formula defined; billing export not analyzed; no EUR/USD/GBP figure cited |
| Dataflow not implemented | Cloud Run push-subscription worker does not perform windowed aggregations or exactly-once streaming |

### What Staging/Prod Separation Would Improve

A implemented staging environment (Phase 1 or Phase 2) would close the following gaps:

1. Safe pre-production Terraform apply rehearsal.
2. Isolated load test and DLQ test without contaminating the production evidence base.
3. dbt schema migration staging before production apply.
4. BigQuery quality threshold testing with disposable staging data.
5. Documented and tested promotion path (staging evidence → manual approval → prod).
6. Staging Cloud SQL for schema exploration without affecting `rtdp-postgres`.
7. A credible response to "how do you validate changes before they go to production?"

### What Enterprise Production Would Still Require

Even with a fully implemented staging environment, the following gaps would remain relative
to enterprise production:

- Multi-day continuous production traffic with proven stability (connection leaks, memory drift,
  log retention compliance).
- Exactly-once end-to-end semantics (requires Dataflow with BigQuery storage write API).
- SLO burn-rate alerting (documented as planned in the market-value gap audit).
- Data governance artifacts (lineage, catalog, masking policies, access review).
- Security certification (SOC 2, ISO 27001, penetration test).
- Disaster recovery validation (restore test; RTO/RPO proven).
- Multi-region failover or high-availability Cloud SQL.
- On-call rotation and incident handover documentation.

---

## 17. Relationship to Existing Plans

### Market-Value Gap Audit (`docs/market-value-gap-audit-2026-2027.md`)

The gap audit ranked staging/prod separation as priority 4 with medium severity, explicitly
listing `docs/staging-environment-plan` as the recommended branch. This document directly
closes that gap as a docs-only plan. The audit's recommendation -- "write the plan before
implementing" -- is followed exactly.

### Dataflow Decision Record (`docs/dataflow-decision-record.md`)

The Dataflow decision record established that Cloud Run is the appropriate architecture at
the current validated scale and that Dataflow is deferred. The staging plan is consistent
with this decision: the proposed staging architecture uses Cloud Run workers and jobs,
not Dataflow. No Dataflow staging path is designed or implied. If Dataflow is implemented
in a future branch, a staging Dataflow job resource should be added to the Phase 1 resource
separation table.

### Replay/Backfill Strategy (`docs/replay-backfill-strategy.md`)

The replay strategy documents the BigQuery cursor-based reprocessing path and Pub/Sub message
retention replay semantics. In a staging environment, replay operations should be rehearsed
against staging BigQuery and staging Pub/Sub before any production replay is attempted. The
staging BigQuery dataset (`rtdp_analytics_staging`) is an appropriate target for replay
simulation without risking the production analytical dataset.

### dbt Observability Metrics Plan (`docs/dbt-observability-metrics-plan.md`)

The dbt metrics plan proposes Cloud Monitoring metrics for dbt run duration, model row counts,
and test pass rates. All proposed metrics must include an `environment` label from the start,
as established in Section 12 of this document. Staging dbt executions emit
`environment = "staging"` metrics; production dbt executions emit `environment = "prod"`.
This label separation is a prerequisite for the dbt observability plan to work correctly
across environments.

### Deploy-on-Merge Future Decision Record

A future `docs/deploy-on-merge-decision-record` branch will evaluate whether automated
deploy-on-merge is justified and safe. The staging promotion model in Section 9 of this
document (staging deploy on merge to main; prod deploy after manual approval) is the natural
precursor to a deploy-on-merge decision. The deploy-on-merge decision record should reference
this staging plan and adopt or extend the promotion workflow design documented here.

### SLO and Incident Response (`docs/SLO_AND_INCIDENT_RESPONSE.md`)

The SLO document defines production-light SLO targets, error budget, and incident runbooks.
In a staged architecture, staging incidents must be classified separately from production
incidents. Staging SLO targets (if defined) should be lower than production targets and
should not contribute to the production error budget. The failure and rollback model in
Section 15 of this document is consistent with the incident severity classification in
`docs/SLO_AND_INCIDENT_RESPONSE.md`.

---

## 18. Explicit Non-Claims

The following is a precise list of what is NOT true about the current platform state or this
branch. These are not weaknesses to apologise for; they are accurate technical facts that
must be stated explicitly to maintain evidence integrity.

- **No staging environment is implemented.** The Real-Time Data Platform operates in a single
  GCP environment (`project-42987e01-2123-446b-ac7`). No second GCP project, no staging
  resource prefix, and no staging Terraform state exist.
- **No separate GCP project is created.** This branch does not create a new GCP project.
  No `gcloud projects create` command is run. No billing account is associated with a staging
  project.
- **No Terraform workspace split is implemented.** No `terraform workspace new staging` command
  is run. No staging `.tfvars` file is created. The Terraform state prefix remains
  `real-time-data-platform/gcp/prod` as the only active state.
- **No staging Cloud SQL instance exists.** There is one Cloud SQL instance: `rtdp-postgres`
  in `project-42987e01-2123-446b-ac7`, region `europe-west1`. Its state is `STOPPED / NEVER`.
  No staging Cloud SQL instance named `rtdp-staging-postgres` or any equivalent exists.
- **No staging Pub/Sub topic exists.** The Pub/Sub topics `market-events-raw` and
  `market-events-raw-dlq` are the only RTDP Pub/Sub topics. No `staging-market-events-raw`
  topic exists.
- **No staging BigQuery dataset exists.** The only RTDP BigQuery dataset is `rtdp_analytics`
  in `project-42987e01-2123-446b-ac7`. No `rtdp_analytics_staging` dataset exists.
- **No staging secrets exist.** The only RTDP database URL secret is `rtdp-database-url`.
  No `rtdp-staging-database-url` secret exists in Secret Manager.
- **No staging Cloud Run services or jobs exist.** There is no `rtdp-staging-api`,
  `rtdp-staging-pubsub-worker`, `rtdp-staging-dbt-refresh-job`, or
  `rtdp-staging-bigquery-append-job`.
- **No staging service accounts exist.** There is no `rtdp-staging-worker-sa`,
  `rtdp-staging-scheduler-sa`, or `rtdp-staging-pubsub-push-sa`.
- **No promotion workflow is implemented.** There is no `staging-deploy.yml` or
  `prod-deploy.yml` GitHub Actions workflow. Both worker and API deploy workflows remain
  `workflow_dispatch` only.
- **No deploy-on-merge is implemented.** This branch does not implement or enable automatic
  deployment on merge to main. The existing `workflow_dispatch`-only deploy pattern is unchanged.
- **No production SLA is claimed.** The platform has been validated through bounded,
  controlled tests only. No service level agreement with measurable availability targets
  applies to the current deployment.
- **No enterprise security certification is claimed.** No SOC 2, ISO 27001, GDPR DPA, or
  penetration test has been conducted or is implied by this plan.
- **No Dataflow staging path is implemented or planned for immediate implementation.**
  Dataflow remains deferred per `docs/dataflow-decision-record.md`. The staging plan is
  designed for a Cloud Run-based architecture. If Dataflow is implemented in a future branch,
  this document should be updated to include Dataflow staging considerations.

---

## 19. Safe Recruitment Positioning

### Recruiter-Facing Paragraph

> The Real-Time Data Platform currently operates in a single GCP environment with full
> Terraform management, Workload Identity Federation, and an evidence-first validation
> discipline. A comprehensive staging/production separation strategy has been designed and
> documented, covering GCP project topology options, resource isolation, Terraform design
> patterns, a promotion workflow model, staging data and secrets strategy, observability
> separation, and cost controls. The plan recommends same-project prefixed staging as an
> interim step and separate GCP projects as the production-grade target. No staging resources
> have been implemented yet; the plan documents the strategy and defines the implementation
> path.

### Technical Interview Paragraph

> The platform currently operates in a single GCP project, which is a known gap I have
> acknowledged and designed around. I have documented a staged migration plan: Phase 0 is
> this planning document; Phase 1 is same-project prefixed staging resources (separate
> Terraform state prefix, separate Pub/Sub topics, separate Cloud SQL instance, separate
> secrets) as a low-cost first step; Phase 2 is separate GCP projects with true IAM isolation
> as the production-equivalent target. I chose the same-project option first because it is
> lower cost and lower operational overhead for a solo project, while still providing the
> resource name isolation needed to rehearse Terraform changes and staging load tests. For a
> real production system, I would prioritise Phase 2 immediately.

### Senior Reviewer Caveat Paragraph

> For senior technical reviewers: I am aware that same-project prefixed staging does not
> provide true IAM isolation. A misconfigured service account in the same GCP project can
> access production resources. The plan explicitly acknowledges this and defines separate
> GCP projects as the Phase 2 target. The current single-environment platform is a portfolio
> project, not a production system with SLA obligations. All limitations are documented
> explicitly. No staging environment exists on this branch; this is a design document only.
> The next implementation branch would be `feat/staging-environment-phase-1` and would
> require a dedicated Terraform apply branch with evidence documentation following the same
> discipline as all prior platform branches.

---

## 20. Final Recommendation

**This branch closes the staging/prod separation gap as documentation only.**

The staging/prod separation plan is now documented with sufficient technical depth to answer
senior reviewer challenges, articulate a phased implementation path, and provide an honest
account of current limitations. The gap is closed at the documentation level. No GCP resources
have been created. No Terraform has been applied. No Cloud SQL has been started. No schedulers
have been resumed.

**The recommended implementation path is same-project prefixed staging first.**

Phase 1 (same-project prefixed staging) is the recommended next implementation step. It
provides meaningful environment isolation at the resource name level, allows Terraform plan
rehearsal in a staging state, and enables disposable staging data without the operational
overhead of a second GCP project. This is the honest, cost-appropriate choice for a solo
portfolio project.

**Separate GCP projects (Phase 2) are the production-grade target.**

Phase 2 (separate GCP projects) is the correct architecture for a platform used by a team
or serving genuine production traffic. It should be implemented when budget and operational
need justify it, not prematurely.

**The next documentation branch after this should be `docs/deploy-on-merge-decision-record`.**

The staging plan defines the promotion workflow design in Section 9. The deploy-on-merge
decision record is the logical next step: it evaluates whether the staging-to-prod gate
should be automated (deploy on merge to main with manual approval for prod) or kept manual
(workflow_dispatch for both). The decision record will reference this staging plan as the
promotion model foundation.

**Do not implement Dataflow as part of staging.** The Dataflow decision record establishes
that Dataflow is deferred. The staging plan is designed for the current Cloud Run architecture.
Dataflow staging resources are not in scope for Phase 1 or Phase 2.

**Do not create staging resources until Phase 1 is scoped as a dedicated implementation branch.**

The `feat/staging-environment-phase-1` branch should include its own Terraform apply plan,
scoped runbook, safety controls (STOPPED/NEVER for staging Cloud SQL, PAUSED for staging
schedulers), and evidence documentation following the same evidence-first discipline as all
prior platform branches. Staging resource creation on the same branch as this planning
document would violate the evidence discipline.

---

## Validation Commands

```bash
git diff --check
uv run pytest -q
uv run ruff check .
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"
grep -En "staging-environment-plan|PLAN -- staging/prod separation" docs/EVIDENCE_INDEX.md
grep -En "Staging|Production|Terraform|CI/CD|Promotion|Secrets|IAM|Observability|Cost Control|Validation Gates|Failure|Rollback|Explicit Non-Claims|Final Recommendation" docs/staging-environment-plan.md
gcloud sql instances describe rtdp-postgres --project=project-42987e01-2123-446b-ac7 --format="table(name,state,settings.activationPolicy)"
gcloud scheduler jobs list --project=project-42987e01-2123-446b-ac7 --location=europe-west1 --format="table(id,state,schedule)"
git status --short --branch
```

---

## Evidence Links

| Document | Purpose |
|---|---|
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog -- 60+ documents by category |
| [docs/market-value-gap-audit-2026-2027.md](market-value-gap-audit-2026-2027.md) | Gap audit that identified staging/prod separation as priority-4 gap |
| [docs/platform-audit-after-cost-performance.md](platform-audit-after-cost-performance.md) | Platform audit confirming staging gap remains open |
| [docs/dataflow-decision-record.md](dataflow-decision-record.md) | Dataflow deferred; Cloud Run is current architecture; staging plan is consistent |
| [docs/replay-backfill-strategy.md](replay-backfill-strategy.md) | Replay strategy; staging environment is the appropriate rehearsal target for replay operations |
| [docs/dbt-observability-metrics-plan.md](dbt-observability-metrics-plan.md) | dbt metrics plan; environment label requirement established in this staging plan |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | SLO targets; incident runbooks; staging incidents are separate from production incidents |
| [docs/recruiter-facing-platform-summary.md](recruiter-facing-platform-summary.md) | Recruiter-facing summary; staging gap acknowledged in the explicit non-claims section |
| [docs/gap-closure-snapshot-after-steady-state.md](gap-closure-snapshot-after-steady-state.md) | Gap closure snapshot; staging gap listed as remaining open |
| [docs/cost-performance-summary.md](cost-performance-summary.md) | Cost drivers and resource sizing; staging cost model follows same STOPPED/NEVER discipline |
