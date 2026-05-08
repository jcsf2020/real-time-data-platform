# Terraform GCP Skeleton — Real-Time Data Platform

## Status

> **SKELETON ONLY — NOT EXECUTED**

| Item | State |
|---|---|
| `terraform init` executed | No |
| `terraform plan` executed | No |
| `terraform apply` executed | No |
| `terraform import` executed | No |
| Terraform state committed | No |
| GCP writes performed | No |

---

## Purpose

This directory contains the initial Terraform skeleton for the Real-Time Data Platform GCP infrastructure. It covers the low-risk Pub/Sub topics, push subscription, and Cloud Scheduler job identified in the phased IaC baseline strategy.

The skeleton is structured to match existing live GCP resources so they can be imported safely — via `terraform import` followed by `terraform plan` — without destroying or drifting any validated infrastructure.

See [docs/terraform-iac-baseline-runbook.md](../../../docs/terraform-iac-baseline-runbook.md) for the full phased strategy, safety constraints, and stop conditions.

---

## File Layout

```
infra/terraform/gcp/
├── versions.tf     # Terraform version constraint and required providers
├── providers.tf    # google provider: project and region from variables
├── variables.tf    # Input variables: project_id, region, environment
├── locals.tf       # Stable resource names and URLs used across modules
├── pubsub.tf       # google_pubsub_topic (×2) and google_pubsub_subscription
├── scheduler.tf    # google_cloud_scheduler_job (PAUSED)
├── monitoring.tf   # logs-based metrics, dashboard, alert policies — SKELETON ONLY
└── README.md       # This file
```

> **`monitoring.tf` is a skeleton aligned to Phase 0 inventory.** It must not be applied before each resource is individually imported (`terraform import`) and validated with a zero-diff `terraform plan`. See [docs/terraform-monitoring-import-runbook.md](../../../docs/terraform-monitoring-import-runbook.md) for the step-by-step import procedure and stop conditions.

**Not included in this skeleton** (deferred — see runbook §7):

- `cloud_run.tf` — Cloud Run services and jobs (image drift strategy required)
- `sql.tf` — Cloud SQL instance (deletion protection guardrails required)
- `iam.tf` — IAM bindings (full audit required)
- `secrets.tf` — Secret Manager (state leakage risk must be resolved)

---

## Safe Next Steps

Execute these steps **on a dedicated execution branch**, not on `main`:

1. **Phase 0 — Read-only inventory**
   Run `gcloud describe` commands from the runbook §6 to confirm all field values match the skeleton before any import. Confirm Cloud SQL `NEVER / STOPPED`, Scheduler `PAUSED`.

2. **`terraform fmt`**
   ```bash
   terraform fmt infra/terraform/gcp/
   ```
   Format-only, no state changes.

3. **`terraform init`** (execution branch only, never on `main`)
   ```bash
   cd infra/terraform/gcp
   terraform init
   ```
   Downloads the provider. Creates `.terraform/` and `.terraform.lock.hcl` — both are gitignored.

4. **`terraform import` — low-risk resources**
   Import in the order documented in the runbook §8:
   1. `google_pubsub_topic.market_events_raw`
   2. `google_pubsub_topic.market_events_raw_dlq`
   3. `google_pubsub_subscription.market_events_raw_worker_push`
   4. `google_cloud_scheduler_job.silver_refresh_scheduler`

   Run `terraform plan` after **each** import and verify zero changes before proceeding.

5. **`terraform plan` — acceptance gate**
   The plan must show **zero changes, zero destroys, zero replacements**. Any destroy or replacement is an immediate stop condition.

---

## Forbidden Actions

The following must **never** occur on this skeleton branch:

| Action | Reason |
|---|---|
| `terraform apply` | Would mutate live GCP resources |
| Import Cloud SQL first | Highest destruction risk; activation policy must be verified clean |
| Import IAM first | Removing a binding could break live service connectivity |
| Commit `terraform.tfstate` or `.terraform.lock.hcl` | State may contain sensitive values |
| Commit secrets or credential files | Standard security hygiene |
| Resume or trigger Cloud Scheduler | Must remain `PAUSED` at all times except bounded windows |
| Start Cloud SQL | Must remain `NEVER / STOPPED` for cost control |

---

## Links

- [docs/terraform-iac-baseline-runbook.md](../../../docs/terraform-iac-baseline-runbook.md) — Full phased IaC strategy, safety constraints, import commands, stop conditions, and acceptance criteria.
- [docs/terraform-remote-backend-strategy.md](../../../docs/terraform-remote-backend-strategy.md) — GCS remote backend strategy: how to migrate local state to GCS safely before high-risk imports. Strategy only — no backend created, no GCP writes.
