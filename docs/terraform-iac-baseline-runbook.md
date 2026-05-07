# Terraform / IaC Baseline Runbook

## 1. Status

> **RUNBOOK ONLY — NOT EXECUTED**

| Item | State |
|---|---|
| Terraform files created | No |
| `terraform init` executed | No |
| `terraform plan` executed | No |
| `terraform apply` executed | No |
| `terraform import` executed | No |
| GCP writes performed | No |
| Cloud SQL started | No |
| Scheduler run | No |
| Cloud Run Job executed | No |
| Pub/Sub messages published | No |
| Deployment performed | No |

This document is a planning and safety runbook only. No infrastructure state has been created or modified.

---

## 2. Purpose

The goal of this runbook is to introduce Terraform / Infrastructure-as-Code safely into the Real-Time Data Platform project **without destroying or drifting existing validated GCP resources**.

Key context:

- All current GCP resources were created imperatively via `gcloud` CLI and the Cloud Console — there is no Terraform history.
- The platform is already operationally validated: accepted 100 / 1,000 / 5,000-event cloud load tests, end-to-end ingestion, silver refresh, Cloud Monitoring, and alerting with email notification are all confirmed working.
- Terraform must be introduced via **inventory → import → plan**, not rebuild. The expected path is:
  1. Read-only inventory of current resource state.
  2. Write a Terraform skeleton that describes existing resources.
  3. Import resources into local state **without applying**.
  4. Run `terraform plan` and verify it shows **zero changes, zero destroys, zero replacements**.
  5. Only after clean plan output: consider merging the skeleton into the main branch.
- **`terraform apply` must not occur until imported state and plan are fully clean.**

Any plan that proposes a destroy or replacement is a hard stop.

---

## 3. Current State

| Item | State |
|---|---|
| Terraform files (`*.tf`) | Absent — no Terraform in repository |
| Terraform state (`terraform.tfstate`) | Absent |
| `.terraform.lock.hcl` | Absent |
| `infra/monitoring/dashboards/rtdp-pipeline-overview.json` | Present — exported from GCP |
| `infra/postgres/init.sql` | Present — database schema initialisation |
| GCP resources | **Already live and validated** (see §4 for inventory) |
| Cloud SQL (`rtdp-postgres`) | Expected: activation policy `NEVER`, instance state `STOPPED` |
| Cloud Scheduler (`rtdp-silver-refresh-scheduler`) | Expected: `PAUSED` |

The platform has no IaC representation of the live GCP resources. All resource definitions exist only in GCP.

---

## 4. Candidate Resource Inventory

### A. Low-risk first import candidates

| Resource | GCP Name | Notes |
|---|---|---|
| Pub/Sub topic | `market-events-raw` | Producer target; stateless; no destruction risk |
| Pub/Sub topic | `market-events-raw-dlq` | DLQ target; stateless; no destruction risk |
| Pub/Sub subscription | `market-events-raw-worker-push` | Push endpoint, DLQ policy (`maxDeliveryAttempts=5`, 10s/60s backoff), and retry policy must all be preserved exactly |
| Cloud Scheduler job | `rtdp-silver-refresh-scheduler` | Must preserve `PAUSED` state; no scheduled execution risk |

**Why low-risk:** These resources have no active state (no data in flight, no running processes) and their configuration is fully describable via `gcloud`. Importing them does not risk activating any compute or mutating live data.

### B. Medium-risk candidates

| Resource | GCP Name | Notes |
|---|---|---|
| Logs-based metric | `worker_message_processed_count` | Monitoring resource; read-only operational impact |
| Logs-based metric | `worker_message_error_count` | Monitoring resource; read-only operational impact |
| Logs-based metric | `silver_refresh_success_count` | Monitoring resource; read-only operational impact |
| Logs-based metric | `silver_refresh_error_count` | Monitoring resource; read-only operational impact |
| Cloud Monitoring dashboard | `RTDP Pipeline Overview` | Exported to `infra/monitoring/dashboards/rtdp-pipeline-overview.json` |
| Alert policy | `RTDP Worker Message Error Alert` | Attached to notification channel |
| Alert policy | `RTDP Silver Refresh Error Alert` | Attached to notification channel |

**Why medium-risk:** Terraform provider support for monitoring resources can be incomplete or use non-obvious resource IDs. A mismatch could destroy and recreate an alert policy, briefly disabling alerting. Careful plan review is required.

### C. High-risk / delayed candidates

| Resource | Notes |
|---|---|
| Cloud Run service `rtdp-api` | Image digest drift between Terraform state and live container is a known problem. Requires `ignore_changes = [template[0].spec[0].containers[0].image]` or equivalent strategy before import. |
| Cloud Run service `rtdp-pubsub-worker` | Same image drift concern. |
| Cloud Run Job `rtdp-silver-refresh-job` | Same image drift concern; also risk of inadvertently executing on `terraform apply`. |
| Cloud SQL instance `rtdp-postgres` | Highest destruction risk: wrong `activation_policy` or `deletion_protection` setting in a plan could trigger an instance restart, deletion, or data loss. Must not be imported first. |
| Secret Manager secret `rtdp-database-url` | Secret values must never appear in plan or state output. Provider may expose them in state. |
| IAM bindings | Over-broad removal of an IAM binding during plan could break live service connectivity. Import last after all other resources are stable. |
| Notification channel `RTDP Operator Email Alerts` (ID: `1439157631105258885`) | Provider may not support in-place import of all channel types safely; replacement risk. |

**Why high-risk:** These resources have either live operational impact (Cloud Run services serving traffic, Cloud SQL with validated event data), significant destruction risk (Cloud SQL deletion protection, IAM), or secret leakage risk (Secret Manager). They require explicit guardrails before import.

---

## 5. Proposed Phased Strategy

### Phase 0 — Read-only inventory (no writes)

**Goal:** Capture current resource configuration before writing any Terraform.

- Run `gcloud describe`/`list` commands from §6 against the live project.
- Confirm Cloud SQL activation policy: `NEVER`, state: `STOPPED`.
- Confirm Scheduler state: `PAUSED`.
- Record all field values that will need to match Terraform resource blocks.
- No GCP writes. No Terraform files created.

### Phase 1 — Create Terraform skeleton (no apply)

**Goal:** Write HCL resource definitions that match the live resource inventory.

- Create files in `infra/terraform/gcp/` (see §7 for proposed file list).
- Populate resource blocks using output from Phase 0 inventory.
- Configure provider with project ID and region variables.
- Backend strategy: **local state only** initially for the exploratory import branch. Remote backend must be explicitly decided before production use.
- **Do not run `terraform apply`.** Do not run `terraform init` on the main branch.

### Phase 2 — Import low-risk resources (Pub/Sub + Scheduler)

**Goal:** Bring low-risk resources under Terraform state management and verify clean plan.

- Run `terraform import` for each Pub/Sub topic, the push subscription, and the Scheduler job (see §8 for commands).
- Run `terraform plan` after each import.
- **Acceptance gate:** plan shows zero changes, zero destroys, zero replacements.
- Any destroy or replacement is an immediate stop condition (see §11).

### Phase 3 — Import monitoring resources

**Goal:** Bring logs-based metrics, dashboard, and alert policies under Terraform state.

- Import monitoring resources one at a time.
- Run `terraform plan` after each import.
- Import notification channel **only if** provider can represent it safely without replacement.
- Same acceptance gate: plan clean after each import.

### Phase 4 — Evaluate Cloud Run / Cloud SQL / IAM

**Goal:** Define import strategy for high-risk resources.

- Only proceed after Phase 2 and Phase 3 state is stable and clean.
- Cloud Run services: define `ignore_changes` strategy for image digest before import.
- Cloud SQL: define explicit `deletion_protection = true` and activation policy guardrails before import. Verify no destructive settings are generated by plan.
- IAM: audit all bindings before import; import only what is fully understood.
- Secret Manager: ensure provider version does not write secret values to state before import.

---

## 6. Exact Future Inventory Commands

The following commands are **read-only**. They may be run during Phase 0. No writes are performed.

```bash
# Repository state
git status

# Terraform availability
terraform version   # if installed; not required for Phase 0

# Active GCP project
gcloud config get-value project

# Pub/Sub topics
gcloud pubsub topics describe market-events-raw \
  --project=project-42987e01-2123-446b-ac7

gcloud pubsub topics describe market-events-raw-dlq \
  --project=project-42987e01-2123-446b-ac7

# Pub/Sub subscription (push endpoint, DLQ policy, retry policy)
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7

# Cloud Run services
gcloud run services describe rtdp-api \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

gcloud run services describe rtdp-pubsub-worker \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# Cloud Run Job
gcloud run jobs describe rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# Cloud Scheduler job — confirm PAUSED
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)"
# Expected: PAUSED

# Cloud SQL — confirm NEVER / STOPPED
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Expected: NEVER  STOPPED

# Cloud Monitoring logs-based metrics (REST API — read-only)
# List all custom metrics in the project:
gcloud logging metrics list \
  --project=project-42987e01-2123-446b-ac7

# Describe each metric individually:
gcloud logging metrics describe worker_message_processed_count \
  --project=project-42987e01-2123-446b-ac7

gcloud logging metrics describe worker_message_error_count \
  --project=project-42987e01-2123-446b-ac7

gcloud logging metrics describe silver_refresh_success_count \
  --project=project-42987e01-2123-446b-ac7

gcloud logging metrics describe silver_refresh_error_count \
  --project=project-42987e01-2123-446b-ac7

# Cloud Monitoring alert policies (REST API — read-only)
gcloud alpha monitoring policies list \
  --project=project-42987e01-2123-446b-ac7

# Notification channels (REST API — read-only)
gcloud alpha monitoring channels describe 1439157631105258885 \
  --project=project-42987e01-2123-446b-ac7
```

All commands above are read-only. None start Cloud SQL, resume the Scheduler, execute a Cloud Run Job, or publish any Pub/Sub message.

---

## 7. Proposed Terraform Skeleton File Plan

The following file structure is **proposed only**. No files are created in this runbook. Actual creation belongs to a separate skeleton branch (e.g. `feat/terraform-skeleton`).

```
infra/terraform/gcp/
├── versions.tf       # Required provider versions and Terraform version constraint
├── providers.tf      # google provider configuration: project, region, credentials
├── variables.tf      # Input variables: project_id, region, environment
├── locals.tf         # Computed locals derived from variables (e.g. resource name prefix)
├── pubsub.tf         # google_pubsub_topic (market-events-raw, market-events-raw-dlq)
│                     # google_pubsub_subscription (market-events-raw-worker-push)
├── scheduler.tf      # google_cloud_scheduler_job (rtdp-silver-refresh-scheduler, PAUSED)
├── monitoring.tf     # google_logging_metric (×4)
│                     # google_monitoring_dashboard (RTDP Pipeline Overview)
│                     # google_monitoring_alert_policy (×2)
│                     # google_monitoring_notification_channel (if safe)
└── README.md         # IaC-specific README: backend config instructions, import notes
```

**Not included in initial skeleton** (deferred to Phase 4 or later):

- `cloud_run.tf` — Cloud Run services and jobs (image drift policy required first)
- `sql.tf` — Cloud SQL instance (explicit destruction guardrails required first)
- `iam.tf` — IAM bindings (full audit required first)
- `secrets.tf` — Secret Manager (state leakage risk must be resolved first)

---

## 8. Import Strategy

### Safe import order

Import resources in this sequence to minimise risk at each step:

1. **Pub/Sub topic** `market-events-raw`
2. **Pub/Sub topic** `market-events-raw-dlq`
3. **Pub/Sub subscription** `market-events-raw-worker-push`
4. **Cloud Scheduler job** `rtdp-silver-refresh-scheduler`
5. **Cloud Monitoring dashboard** `RTDP Pipeline Overview`
6. **Logs-based metric** `worker_message_processed_count`
7. **Logs-based metric** `worker_message_error_count`
8. **Logs-based metric** `silver_refresh_success_count`
9. **Logs-based metric** `silver_refresh_error_count`
10. **Alert policy** `RTDP Worker Message Error Alert`
11. **Alert policy** `RTDP Silver Refresh Error Alert`
12. **Notification channel** `RTDP Operator Email Alerts` — only if provider supports safely without replacement
13. **Cloud Run services/jobs** — only after image drift `ignore_changes` policy is defined
14. **Cloud SQL** — only after explicit `deletion_protection = true` and activation policy guardrails are verified in plan
15. **IAM bindings** — last; import only fully understood bindings

### Template import commands (for future execution branch)

These are **templates only** — do not execute from this branch.

```bash
# Pub/Sub topics
terraform import google_pubsub_topic.market_events_raw \
  projects/project-42987e01-2123-446b-ac7/topics/market-events-raw

terraform import google_pubsub_topic.market_events_raw_dlq \
  projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq

# Pub/Sub subscription
terraform import google_pubsub_subscription.market_events_raw_worker_push \
  projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push

# Cloud Scheduler job
terraform import google_cloud_scheduler_job.silver_refresh_scheduler \
  projects/project-42987e01-2123-446b-ac7/locations/europe-west1/jobs/rtdp-silver-refresh-scheduler

# Cloud Monitoring dashboard (ID from describe output)
terraform import google_monitoring_dashboard.rtdp_pipeline_overview \
  projects/project-42987e01-2123-446b-ac7/dashboards/<DASHBOARD_ID>

# Logs-based metrics
terraform import google_logging_metric.worker_message_processed_count \
  worker_message_processed_count

terraform import google_logging_metric.worker_message_error_count \
  worker_message_error_count

terraform import google_logging_metric.silver_refresh_success_count \
  silver_refresh_success_count

terraform import google_logging_metric.silver_refresh_error_count \
  silver_refresh_error_count
```

After **each** import, run `terraform plan` and verify zero changes before proceeding to the next import.

---

## 9. State Strategy

### Local state for exploratory import branch

For the initial skeleton and import work, use **local state only** (`terraform.tfstate` in `infra/terraform/gcp/`). This is intentional: a local-state exploratory branch has no external side-effects and can be discarded if import fails.

### What must not happen with state

- **Do not commit `terraform.tfstate` or `terraform.tfstate.backup`** to any branch. Add both to `.gitignore` in the Terraform directory before running `terraform init`.
- **Secrets must not appear in state.** Do not import Secret Manager secrets until the provider's state handling is verified to not expose secret values.
- **Do not push state to a shared location** until the backend strategy is explicitly decided.

### Remote backend decision (deferred)

A GCS remote backend is the natural choice for GCP-hosted state, but requires:

- A GCS bucket created and configured for state storage.
- Appropriate IAM permissions for the CI/CD identity.
- Explicit team agreement on bucket naming, locking strategy, and access.

This decision belongs to a separate infrastructure decision, not this runbook. The initial skeleton branch should use local state and include a comment in `versions.tf` indicating where the backend block will go.

### Proposed `.gitignore` entries for the Terraform directory

```
infra/terraform/gcp/.terraform/
infra/terraform/gcp/.terraform.lock.hcl
infra/terraform/gcp/terraform.tfstate
infra/terraform/gcp/terraform.tfstate.backup
infra/terraform/gcp/*.tfvars
infra/terraform/gcp/override.tf
infra/terraform/gcp/override.tf.json
```

---

## 10. Safety Constraints

The following constraints are **absolute** and apply to all Terraform work on this platform:

| Constraint | Reason |
|---|---|
| No `terraform apply` in the first skeleton branch | Importing into state is safe; applying risks unintended resource mutation |
| No GCP writes from the docs branch | This branch is documentation-only |
| Do not import Cloud SQL first | Highest destruction risk; activation policy must be verified clean |
| Do not import IAM first | Removing a binding in plan could break live service connectivity |
| Do not manage Cloud Run image without `ignore_changes` strategy | Image digest drifts with every deploy; Terraform would try to revert it |
| Do not commit state files | State may contain sensitive values from resource imports |
| Do not commit secrets or credential files | Standard security hygiene; never in repository |
| Do not leave Scheduler enabled | `rtdp-silver-refresh-scheduler` must remain `PAUSED` at all times except during bounded execution windows |
| Do not start Cloud SQL | `rtdp-postgres` must remain `NEVER / STOPPED` for cost control |
| No destroy/recreate allowed | Any plan showing a destroy or replacement is a hard stop |
| Any plan showing destroy or replacement is a stop condition | See §11 |

---

## 11. Stop Conditions

Stop all Terraform work immediately if any of the following occur:

1. `terraform plan` proposes **destroy** of any resource.
2. `terraform plan` proposes **replacement** (`-/+`) of any resource.
3. Plan would change Cloud SQL `activation_policy` from `NEVER` to any other value.
4. Plan would change Scheduler state from `PAUSED` to `ENABLED`.
5. Plan would change the Pub/Sub push endpoint URL on `market-events-raw-worker-push`.
6. Plan would remove or modify the `deadLetterPolicy` on `market-events-raw-worker-push` unexpectedly.
7. Plan would remove any IAM binding currently granting live service connectivity.
8. Plan would replace the notification channel `RTDP Operator Email Alerts` (channel ID `1439157631105258885`).
9. Secrets or credential values appear in `terraform plan` or `terraform state show` output.
10. Terraform provider cannot represent an existing resource accurately (e.g. import succeeds but plan immediately shows changes that cannot be suppressed without `ignore_changes`).

When a stop condition is hit: do not apply, do not push state, investigate root cause, and update the resource block or `ignore_changes` configuration before retrying.

---

## 12. Evidence to Capture in Future Execution Branch

The execution branch (e.g. `feat/terraform-iac-baseline`) must produce an evidence document recording:

| Item | Required value |
|---|---|
| Branch name | e.g. `feat/terraform-iac-baseline` |
| Terraform version | output of `terraform version` |
| Google provider version | from `.terraform.lock.hcl` |
| Inventory outputs | `gcloud describe` output for each resource (Phase 0) |
| Skeleton file list | `ls -la infra/terraform/gcp/` |
| Import commands used | Exact commands run, in order |
| `terraform plan` output | Full plan output after all imports |
| No destroy/recreate confirmation | Explicit statement from plan output |
| Cloud SQL final state | `NEVER STOPPED` |
| Scheduler final state | `PAUSED` |
| Test results | `uv run pytest -q` output (116 tests, all passed) |
| Ruff result | `uv run ruff check .` — no issues |
| No Pub/Sub publishing | Explicit confirmation |
| No deployment | Explicit confirmation |
| No Cloud Run Job execution | Explicit confirmation |

---

## 13. Acceptance Criteria

The IaC baseline is accepted when a future execution branch delivers all of the following:

- [ ] Terraform skeleton committed to `infra/terraform/gcp/`
- [ ] Low-risk resources imported into local state **or** intentionally deferred with documented reason
- [ ] `terraform plan` exits with status 0
- [ ] Plan output shows **no destroy, no replacement**
- [ ] Critical live values preserved:
  - Pub/Sub topic names `market-events-raw` and `market-events-raw-dlq` unchanged
  - Push endpoint URL on `market-events-raw-worker-push` unchanged
  - `deadLetterPolicy` on `market-events-raw-worker-push` unchanged (`maxDeliveryAttempts=5`, 10s/60s backoff)
  - Scheduler `rtdp-silver-refresh-scheduler` state remains `PAUSED`
  - Cloud SQL `rtdp-postgres` activation policy `NEVER`, state `STOPPED`
- [ ] 116 tests pass (`uv run pytest -q`)
- [ ] Ruff clean (`uv run ruff check .`)
- [ ] Evidence document created in `docs/`

---

## 14. What This Runbook Does Not Do

This runbook explicitly does **not**:

- Create any Terraform files.
- Import any resource into Terraform state.
- Run `terraform plan` or `terraform apply`.
- Mutate any GCP resource.
- Start Cloud SQL.
- Resume or trigger the Cloud Scheduler job.
- Execute any Cloud Run Job.
- Publish any Pub/Sub messages.
- Deploy any service.

It is a planning and safety document only.

---

## 15. Roadmap Position

### What this runbook delivers

After this runbook is merged:

- The Terraform/IaC gap has a documented, safe migration strategy.
- The next branch (`feat/terraform-skeleton`) can create the skeleton files and run Phase 0 inventory without executing any plan.
- The next execution branch (`feat/terraform-iac-baseline`) can import low-risk resources and produce a clean plan.
- BigQuery / Dataflow analytical tier work can proceed in parallel or after the IaC baseline, scoped independently.

### Remaining gaps after this runbook

| Gap | Description |
|---|---|
| Terraform skeleton | `infra/terraform/gcp/` files do not exist yet |
| Terraform import baseline | No resources are under state management yet |
| BigQuery / Dataflow analytical tier | Silver layer data is not yet flowing to BigQuery |
| CI/CD deployment automation | Deployments are currently manual via `gcloud` |

These gaps are tracked in the project roadmap and are the next planned phases after this documentation baseline.
