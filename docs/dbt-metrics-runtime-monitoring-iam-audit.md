# dbt Metrics Runtime Monitoring IAM Audit

**Branch:** `infra/dbt-metrics-runtime-monitoring-iam-audit`
**Date:** 2026-05-23
**Audit type:** Read-only IAM and runtime configuration audit

---

## Purpose

Before `DBT_METRICS_DRY_RUN=false` can be enabled on the `rtdp-dbt-refresh-job` Cloud Run Job,
the runtime service account must hold `roles/monitoring.metricWriter`. This audit identifies the
exact runtime service account, determines whether that binding already exists in the live GCP
project, and produces a Terraform recommendation if the binding is missing.

No GCP resources were mutated. No secrets or tokens appear in this document.

---

## Current Runtime Service Account

**Service account:** `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com`

### Evidence sources

| Source | Path | Value |
|---|---|---|
| Terraform `cloud_run_jobs.tf:12` | `google_cloud_run_v2_job.rtdp_dbt_refresh_job.template[0].template[0].service_account` | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Live GCP JSON (`/tmp/rtdp-dbt-job.json`) | `spec.template.spec.template.spec.serviceAccountName` | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |

Both sources agree. No drift between Terraform and live configuration.

### Commands used (read-only)

```bash
gcloud run jobs describe rtdp-dbt-refresh-job \
  --project=project-42987e01-2123-446b-ac7 \
  --region=europe-west1 \
  --format=json > /tmp/rtdp-dbt-job.json

python3 -c "
import json
with open('/tmp/rtdp-dbt-job.json') as f:
    data = json.load(f)
sa = data['spec']['template']['spec']['template']['spec']['serviceAccountName']
print('serviceAccountName:', sa)
"
```

Output:
```
serviceAccountName: rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

---

## Current monitoring.metricWriter Bindings

**Command used (read-only):**

```bash
gcloud projects get-iam-policy project-42987e01-2123-446b-ac7 \
  --format=json > /tmp/rtdp-iam-policy.json
```

Filtered for `roles/monitoring.metricWriter`:

```
Role: roles/monitoring.metricWriter
  Member: serviceAccount:rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

### Summary

| Member | Has roles/monitoring.metricWriter |
|---|---|
| `rtdp-terraform-plan-ci@...` (GitHub Actions CI) | YES |
| `rtdp-worker-sa@...` (Cloud Run Job runtime) | **NO** |

The `rtdp-terraform-plan-ci` service account holds the binding because it was granted
`roles/monitoring.metricWriter` in PR #157 to support the BigQuery quality metrics workflow.
That grant is scoped to the CI service account; it does not extend to the Cloud Run Job runtime.

### Current Terraform IAM for rtdp-worker-sa

From `infra/terraform/gcp/iam.tf`, the `rtdp-worker-sa` currently holds:

| Resource | Role |
|---|---|
| `worker_cloudsql_client` | `roles/cloudsql.client` |
| `scheduler_bigquery_append_invoker` (job-scoped) | `roles/run.invoker` on `rtdp-bigquery-append-job` |
| `scheduler_dbt_refresh_invoker` (job-scoped) | `roles/run.invoker` on `rtdp-dbt-refresh-job` |
| BigQuery IAM (from BigQuery tier) | `roles/bigquery.jobUser` |

`roles/monitoring.metricWriter` is absent.

---

## Finding: NOT Ready for Live Metric Writes

**Status: IAM MISSING**

`rtdp-worker-sa` does not have `roles/monitoring.metricWriter`. Enabling
`DBT_METRICS_DRY_RUN=false` on the Cloud Run Job today would cause every metric write attempt to
fail with a 403 PERMISSION_DENIED from the Cloud Monitoring API. The dry-run guard in PR #204
(`DBT_METRICS_DRY_RUN=true` default) is correctly protecting against this failure.

---

## Safety State

| Check | Result |
|---|---|
| Cloud SQL `rtdp-postgres` state | STOPPED / NEVER |
| `rtdp-silver-refresh-scheduler` | PAUSED |
| `rtdp-bigquery-append-scheduler` | PAUSED |
| Terraform plan exit code | PLAN_EXIT=0 |
| GCP resources mutated | None |
| Secrets or tokens in logs | None |

---

## Terraform Recommendation

Add the following resource to `infra/terraform/gcp/iam.tf`:

```hcl
resource "google_project_iam_member" "worker_monitoring_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = local.rtdp_worker_service_account
}
```

`local.rtdp_worker_service_account` is already defined in `iam.tf:3`:

```hcl
rtdp_worker_service_account = "serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
```

This is the minimal change required. No other resources, env vars, or application code need to
change as a prerequisite. After this IAM grant is applied, `DBT_METRICS_DRY_RUN=false` can be
enabled and a live metric write proof can be executed.

**Do not implement this grant in this audit branch.** This branch is docs-only.

---

## Exact Next Branch Recommendation

**Branch:** `infra/dbt-metrics-runtime-monitoring-iam`

Scope of that branch (minimal, IAM-only):

1. Add `google_project_iam_member.worker_monitoring_metric_writer` to `iam.tf`.
2. Run `terraform plan -detailed-exitcode` — expect PLAN_EXIT=2 (1 add).
3. Apply and confirm PLAN_EXIT=0 post-apply.
4. Create `docs/dbt-metrics-runtime-monitoring-iam-evidence.md`.

After that branch merges, a separate execution branch can enable `DBT_METRICS_DRY_RUN=false`
and prove a live metric write from the Cloud Run Job.

---

## Validation Commands and Outputs

All commands were run on branch `infra/dbt-metrics-runtime-monitoring-iam-audit`.

### pytest

```
uv run pytest -q
348 passed in 5.04s
```

### ruff

```
uv run ruff check .
All checks passed!
```

### terraform fmt

```
terraform -chdir=infra/terraform/gcp fmt -check -recursive
FMT_EXIT=0
```

### terraform validate

```
terraform -chdir=infra/terraform/gcp validate
Success! The configuration is valid.
VALIDATE_EXIT=0
```

### terraform plan

```
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

### Cloud SQL

```
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state,settings.activationPolicy)"

NAME           STATE    ACTIVATION_POLICY
rtdp-postgres  STOPPED  NEVER
```

### Cloud Scheduler

```
gcloud scheduler jobs list \
  --project=project-42987e01-2123-446b-ac7 \
  --location=europe-west1 \
  --format="table(id,state,schedule)"

ID  STATE   SCHEDULE
    PAUSED  */15 * * * *
    PAUSED  0 * * * *
```

---

## Recruiter / Portfolio Value

This audit demonstrates production-readiness discipline: before enabling a live Cloud Monitoring
write path, the IAM surface was audited first, using only read-only GCP commands. The finding
is accurate and actionable — a single `google_project_iam_member` resource is the exact delta
required. The dry-run guard introduced in PR #204 is validated as a correct safety mechanism.

This pattern — audit before mutation, evidence-first branch discipline — reflects how IAM
changes are handled responsibly in production GCP environments where misconfigured permissions
cause silent failures at runtime.
