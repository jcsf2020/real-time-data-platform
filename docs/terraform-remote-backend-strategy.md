# Terraform Remote Backend Strategy

## 1. Status

> **STRATEGY ONLY — NOT EXECUTED**

| Item | State |
|---|---|
| GCS bucket created | No |
| State migrated | No |
| GCP writes performed | No |
| `backend.tf` created | No |
| `versions.tf` modified | No |
| `terraform init -migrate-state` run | No |
| `terraform apply` run | No |

This document is a planning and safety strategy only. No backend has been created, no state has been moved, and no GCP resources have been written or modified.

---

## 2. Purpose

Define how to move from local Terraform state to a GCS remote backend safely, preserving all imported resources and keeping the zero-diff plan intact.

The current local state already represents:

- Pub/Sub raw topic and DLQ topic
- Pub/Sub push subscription
- Cloud Scheduler job
- Logs-based metrics (×4)
- Cloud Monitoring dashboard
- Alert policies (×2)

The email notification channel (`projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885`) is intentionally unmanaged — referenced by literal ID from the alert policies, not imported into Terraform state.

A remote backend is the prerequisite before importing higher-risk resources — Cloud Run, Cloud SQL, IAM bindings, Secret Manager — because those imports must never be done when state lives only on a single developer laptop with no versioning or locking.

---

## 3. Current State

| Item | State |
|---|---|
| Terraform state location | `infra/terraform/gcp/terraform.tfstate` (local only) |
| Terraform state backup | `infra/terraform/gcp/terraform.tfstate.backup` (local only) |
| State files committed | No — gitignored, must remain uncommitted |
| Backend block in `versions.tf` | Empty — intentionally local-only (see `versions.tf` comment and `docs/terraform-iac-baseline-runbook.md` §9) |
| GCS bucket | Does not exist |
| Resources in state | Pub/Sub, Scheduler, Monitoring metrics, dashboard, alert policies |

State files must remain uncommitted at all times. They may contain metadata that should not appear in git history.

---

## 4. Why Remote Backend Now

| Reason | Detail |
|---|---|
| Local state fragility | State lives on one machine; loss or corruption is unrecoverable |
| CI plan workflow | `terraform plan` in GitHub Actions requires state accessible to the runner |
| Reproducible management | Any operator with correct IAM can run plan without state hand-off |
| High-risk import gate | Cloud Run, Cloud SQL, IAM, and Secret Manager imports must not proceed against local-only state |
| Locking | The GCS backend uses state locking semantics supported by Terraform's backend behavior; the migration branch must validate locking behavior before enabling CI plan workflows |

The existing runbook (§9 of `docs/terraform-iac-baseline-runbook.md`) explicitly deferred remote backend until a strategy was approved. This document is that strategy.

---

## 5. Recommended Backend

**Type:** GCS (Google Cloud Storage)

| Parameter | Value |
|---|---|
| Bucket name | `rtdp-terraform-state-project-42987e01-2123-446b-ac7` |
| Prefix | `real-time-data-platform/gcp/prod` |
| Region / location | `europe-west1` (or `EU` multi-region) |
| Versioning | Enabled |
| Uniform bucket-level access | Enabled |
| Public access prevention | Enforced |
| Lifecycle policy (old versions) | Optional — deferred |
| Encryption | Google-managed default (acceptable for portfolio; CMEK optional/deferred) |

The bucket name includes the project ID to reduce ambiguity and avoid cross-project confusion. The final execution branch must still verify global bucket name availability before creation. The prefix isolates this workspace from any future workspaces sharing the bucket.

---

## 6. IAM Model

| Principal | Required Role / Permission | Scope | When |
|---|---|---|---|
| Local operator (migration) | `storage.objectAdmin` | State bucket / prefix | Migration only |
| GitHub Actions service account | Custom least-privilege role, or temporary bucket-scoped `storage.objectAdmin` until backend locking/write requirements are validated | State bucket / prefix | CI plan runs |
| No principal | `roles/owner` | Project-wide | Avoid — too broad |

Separate migration rights from CI plan rights where possible. The migration role can be granted temporarily and revoked after the state move is confirmed. The CI service account should receive only the minimum bucket permissions required for `terraform init` and `terraform plan` against the remote backend, including any backend state-lock/write behavior Terraform requires. It must never run `terraform apply`.

Workload Identity Federation is preferred over long-lived service account keys for the GitHub Actions principal.

---

## 7. State Migration Strategy

Perform the migration on a dedicated **execution branch** (`exec/terraform-remote-backend-migration` or similar), not on `main`. Never merge the backend block before the migration is confirmed clean.

### Preflight Checks

- [ ] Confirm `terraform state list` on local state matches expected resources (Pub/Sub, Scheduler, Monitoring)
- [ ] Confirm `terraform plan` shows **No changes** against local state
- [ ] Confirm Cloud SQL status is `NEVER / STOPPED`
- [ ] Confirm Scheduler status is `PAUSED`
- [ ] Confirm no uncommitted changes to `*.tf` files

### Migration Steps

1. **Backup local state**
   ```bash
   cp infra/terraform/gcp/terraform.tfstate \
      infra/terraform/gcp/terraform.tfstate.pre-migration.bak
   ```
   Keep the backup outside the repo or in a secure location. Do not commit it.

2. **Create the GCS bucket** (separate controlled step, outside this docs branch)
   ```bash
   gcloud storage buckets create gs://rtdp-terraform-state-project-42987e01-2123-446b-ac7 \
     --location=europe-west1 \
     --uniform-bucket-level-access \
     --public-access-prevention
   gcloud storage buckets update gs://rtdp-terraform-state-project-42987e01-2123-446b-ac7 \
     --versioning
   ```

3. **Add backend config** — only after bucket exists and IAM is confirmed (see §8 candidate block)

4. **Run `terraform init -migrate-state`** (execution branch only)
   ```bash
   cd infra/terraform/gcp
   terraform init -migrate-state
   ```
   Review the prompt carefully. Accept only if it proposes to copy state from local to GCS — never if it proposes to delete or recreate resources.

5. **Verify `terraform state list`** — output must match the pre-migration list exactly

6. **Verify `terraform plan`** — must show **No changes. Your infrastructure matches the configuration.**

7. **Do not run `terraform apply`** at any point during migration.

---

## 8. Backend HCL Candidate

The following block is a documentation candidate only. **Do not paste into `versions.tf` until the execution branch is approved and the GCS bucket exists.**

```hcl
terraform {
  backend "gcs" {
    bucket = "rtdp-terraform-state-project-42987e01-2123-446b-ac7"
    prefix = "real-time-data-platform/gcp/prod"
  }
}
```

This block replaces the empty backend (local default) currently in `versions.tf`. The `bucket` and `prefix` values must match the bucket created in §7 step 2.

---

## 9. CI Plan Workflow Implications

Once the remote backend is active, a GitHub Actions workflow can run `terraform plan` as a read-only gate:

- `terraform init` — downloads provider, connects to GCS state
- `terraform plan` — reads state, compares to configuration, outputs diff
- Plan output reviewed in PR — no auto-apply
- `terraform apply` — **never automated**; requires manual approval in a separate step

Authentication should use **Workload Identity Federation** linked to the GitHub Actions OIDC provider — no long-lived service account keys stored as secrets.

Secrets must not be exposed in workflow logs. Use `terraform plan -out=tfplan` and upload only non-sensitive summaries as PR artifacts. Never run `terraform state show` on sensitive resources in CI.

---

## 10. Security and Risk Controls

| Control | Detail |
|---|---|
| State contains sensitive metadata | Treat the state bucket as sensitive; restrict access |
| Secret Manager import deferred | State leakage risk not yet resolved; remains out of scope |
| Bucket versioning | Protects against accidental overwrite; enables rollback |
| Uniform bucket-level access | Prevents per-object ACL bypass |
| Public access prevention | Enforced at bucket level |
| State in PR artifacts | Never expose state file in PR artifacts or CI logs |
| `terraform state show` in CI | Never run against sensitive resources in public logs |
| Bucket IAM | Restrict to known principals; no `allUsers` or `allAuthenticatedUsers` |

---

## 11. Stop Conditions

Stop immediately and do not proceed if any of the following occur:

- GCS bucket creation fails or conflicts with an existing bucket
- `terraform init -migrate-state` proposes to delete or recreate any resource
- The migration prompt cannot be reviewed safely (non-interactive, piped, or scripted)
- `terraform state list` after migration does not match the pre-migration list
- `terraform plan` shows anything other than **No changes**
- Secrets or credential values appear in state, plan output, or CI logs
- Bucket IAM cannot be locked down before state is written

---

## 12. Acceptance Criteria

| Criterion | Check |
|---|---|
| GCS bucket exists with versioning and locked-down IAM | `gcloud storage buckets describe …` |
| Backend config added only in approved execution branch | PR review gate |
| `terraform init -migrate-state` succeeds without resource changes | Migration log reviewed |
| `terraform state list` matches pre-migration resources | Diff confirmed empty |
| `terraform plan` returns **No changes** | Plan output attached as evidence |
| No `terraform apply` run | Execution log reviewed |
| README and docs updated | This document and links in README |

---

## 13. Non-Goals

The following are explicitly out of scope for the remote backend migration:

- Cloud Run resource import
- Cloud SQL resource import
- IAM binding import
- Secret Manager import
- Automated `terraform apply` in CI
- GCS bucket creation in this documentation branch
- Any modification to application code or tests

---

## 14. Recommended Next Branches

| Branch | Purpose |
|---|---|
| `feat/terraform-remote-backend-skeleton` or `exec/terraform-remote-backend-migration` | Create the GCS bucket, add backend config, run `terraform init -migrate-state`, validate |
| `docs/terraform-cloud-run-import-runbook` | After remote backend is accepted: plan for Cloud Run import |

The remote backend migration must be fully accepted (zero-diff plan on GCS state, all acceptance criteria met) before any high-risk resource import proceeds.
