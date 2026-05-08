# Terraform Monitoring Import Runbook

## 1. Status

> **RUNBOOK ONLY — NOT EXECUTED**

| Item | State |
|---|---|
| `monitoring.tf` created | No |
| `terraform init` executed | No |
| `terraform plan` executed | No |
| `terraform apply` executed | No |
| `terraform import` executed | No |
| Terraform state modified | No |
| GCP writes performed | No |
| Cloud SQL started | No |
| Scheduler run | No |
| Cloud Run Job executed | No |
| Pub/Sub messages published | No |

This document is a planning and safety runbook only. No infrastructure state has been created or modified.

---

## 2. Purpose

Bring the four existing Cloud Monitoring logs-based metrics, the RTDP Pipeline Overview dashboard, the two Cloud Monitoring alert policies, and the email notification channel under Terraform state management — safely, after the low-risk Pub/Sub and Scheduler import was validated with a zero-diff plan in PR #68.

The expected path follows the same discipline as the Phase 2 import:

1. Read-only inventory of current monitoring resource state (commands in §5).
2. Create `infra/terraform/gcp/monitoring.tf` with resource blocks that match the live inventory.
3. Import resources one at a time, in the order defined in §8.
4. Run `terraform plan` after each import.
5. Verify plan shows **zero changes, zero destroys, zero replacements** before proceeding.
6. Never run `terraform apply` during import validation.

Any plan that proposes a destroy or replacement is a hard stop (see §10).

---

## 3. Preconditions

All of the following must be true before branching for execution:

| Precondition | Required state |
|---|---|
| `main` branch clean | No uncommitted changes |
| PR #68 merged | Terraform Pub/Sub + Scheduler import/plan evidence |
| PR #69 merged | Link to import plan evidence in README |
| Cloud SQL (`rtdp-postgres`) | Activation policy `NEVER`, instance state `STOPPED` |
| Scheduler (`rtdp-silver-refresh-scheduler`) | State `PAUSED` |
| Terraform skeleton exists | `infra/terraform/gcp/` directory with `versions.tf`, `providers.tf`, `variables.tf`, `locals.tf`, `pubsub.tf`, `scheduler.tf` |
| Phase 0 inventory exists | `docs/evidence/terraform-phase-0-inventory/` contains monitoring JSON snapshots |
| Low-risk import evidence exists | `docs/terraform-pubsub-scheduler-import-plan-evidence.md` |

Verify preconditions with:

```bash
git status
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)"
# Expected: PAUSED

gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Expected: NEVER  STOPPED
```

---

## 4. Resource Risk Classification

### 4.1 Logs-based metrics — Lower risk

| Resource | GCP name | Risk driver |
|---|---|---|
| `google_logging_metric.worker_message_processed_count` | `worker_message_processed_count` | Filter expression must not change |
| `google_logging_metric.worker_message_error_count` | `worker_message_error_count` | Filter expression must not change |
| `google_logging_metric.silver_refresh_success_count` | `silver_refresh_success_count` | Filter expression must not change |
| `google_logging_metric.silver_refresh_error_count` | `silver_refresh_error_count` | Filter expression must not change |

**Why lower risk:** Metrics are read-only observability resources. Importing one into state and then destroying it would disable a metric counter, but would not affect live ingestion, Cloud SQL, or the Scheduler. However, a drift in the `filter` field would silently break the counter — the plan must show the filter unchanged.

**Known risk: filter normalisation.** The live filter expressions are multi-line strings (newline-separated conditions). The Terraform provider may normalise them to a single-line string with space separators, or may preserve newlines. If the plan shows a filter change, stop immediately and align the HCL to match the provider's canonical representation exactly.

**Phase 0 inventory files available:**

- `docs/evidence/terraform-phase-0-inventory/logging-metric-worker_message_processed_count.json`
- `docs/evidence/terraform-phase-0-inventory/logging-metric-worker_message_error_count.json`
- `docs/evidence/terraform-phase-0-inventory/logging-metric-silver_refresh_success_count.json`
- `docs/evidence/terraform-phase-0-inventory/logging-metric-silver_refresh_error_count.json`

### 4.2 Cloud Monitoring dashboard — Medium risk

| Resource | GCP name | Risk driver |
|---|---|---|
| `google_monitoring_dashboard.rtdp_pipeline_overview` | `RTDP Pipeline Overview` | Dashboard JSON drift causes large plan diff |

**Why medium risk:** The `google_monitoring_dashboard` resource uses a raw JSON blob (`dashboard_json`) that embeds the full dashboard configuration. Small differences between the exported JSON and the provider's canonical representation — field ordering, whitespace, default values inserted by the API — can produce a large plan diff even when the dashboard content is functionally identical. If the plan shows any change to `dashboard_json`, stop and investigate before applying.

**Dashboard ID confirmed from exported JSON:**

```text
projects/892892382088/dashboards/1277f289-1f9a-4983-944f-913ce0f92622
```

The exported dashboard JSON uses the numeric GCP project number (`892892382088`). Future Terraform import commands must verify whether the provider expects the numeric project number or the textual project ID (`project-42987e01-2123-446b-ac7`) before use.

**Dashboard JSON exported at:** `infra/monitoring/dashboards/rtdp-pipeline-overview.json`

The exported JSON is the source of truth for the `dashboard_json` argument. It must be re-fetched from GCP at the time of HCL authoring to ensure it reflects any provider-side mutations since the original export.

### 4.3 Alert policies — Medium risk

| Resource | GCP name | Alert policy ID | Risk driver |
|---|---|---|---|
| `google_monitoring_alert_policy.worker_error` | `RTDP Worker Message Error Alert` | `5769368960767699129` | Replacement briefly disables alerting |
| `google_monitoring_alert_policy.silver_refresh_error` | `RTDP Silver Refresh Error Alert` | `10553646324755759042` | Replacement briefly disables alerting |

**Why medium risk:** If Terraform proposes to destroy and recreate an alert policy instead of importing in-place, the policy will be briefly absent. During that window, no email notification would fire for a worker or silver refresh error. A replacement (`-/+`) is an immediate stop condition.

**Additional risks for alert policies:**

- The `notification_channels` field must reference the correct notification channel resource name. Drift here removes the email delivery attachment.
- The `enabled` field must be `true`. A plan that sets `enabled = false` is a stop condition.
- The metric filter strings within `condition_threshold.filter` must match exactly. Any change to the filter disables the policy's ability to fire correctly.
- The `combiner` field is `OR` on both policies.

**Phase 0 inventory file available:**

- `docs/evidence/terraform-phase-0-inventory/monitoring-alert-policies.json`

### 4.4 Notification channel — High caution (evaluate, do not blindly import)

| Resource | GCP name | Channel ID | Risk driver |
|---|---|---|---|
| `google_monitoring_notification_channel` | `RTDP Operator Email Alerts` | `1439157631105258885` | Provider may propose replacement; sensitive field handling; alert policy detachment if deleted |

**Why high caution:** The Terraform `google_monitoring_notification_channel` resource has known provider-side complexity:

1. **`sensitive_labels` vs `labels`:** Email notification channels store the email address in `labels.email_address`. The provider may represent this under `sensitive_labels` in some versions, causing a plan to show a diff even when the underlying value is unchanged.
2. **`verification_status`:** The API returns a `verification_status` field for email channels. If the provider exposes this as a computed field and the live channel has `UNVERIFIED` status, the plan may show a spurious change.
3. **Replacement risk:** If the import does not map cleanly to the provider schema, the provider may propose destroying and recreating the channel. If the channel is destroyed, both alert policies lose their notification attachment until the new channel is re-attached — creating a gap in alerting.
4. **Alert policy coupling:** Both alert policies reference this channel ID. A channel replacement generates a new ID, requiring a subsequent alert policy update to restore the attachment.

**Decision: defer notification channel import unless the following conditions are met:**

- `terraform import` of the channel succeeds without error.
- Immediate `terraform plan` after import shows **zero changes** — specifically no diff on `labels`, `sensitive_labels`, `verification_status`, or `type`.
- No `-/+` replacement in the plan output.

If any of these conditions are not met, do not proceed with notification channel import in this phase. Leave it unmanaged by Terraform and document the reason. Alert policy import can proceed independently by referencing the notification channel by its literal resource name string rather than a Terraform resource reference.

**Phase 0 inventory file available:**

- `docs/evidence/terraform-phase-0-inventory/monitoring-notification-channel-1439157631105258885.json`

---

## 5. Read-Only Inventory Commands

The following commands are **read-only**. They do not start Cloud SQL, resume the Scheduler, execute a Cloud Run Job, or publish any Pub/Sub message. Run these on the execution branch before authoring any HCL.

### 5.1 Logs-based metrics

```bash
# List all custom metrics
gcloud logging metrics list \
  --project=project-42987e01-2123-446b-ac7

# Describe each metric (captures exact filter expression)
gcloud logging metrics describe worker_message_processed_count \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json

gcloud logging metrics describe worker_message_error_count \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json

gcloud logging metrics describe silver_refresh_success_count \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json

gcloud logging metrics describe silver_refresh_error_count \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

Compare the `filter` field from each command against the Phase 0 inventory JSON files. Any change since Phase 0 must be incorporated into the HCL.

### 5.2 Alert policies

`gcloud alpha monitoring policies list` requires the alpha component. If the alpha component is not installed, use the Cloud Monitoring REST API directly:

```bash
# Via gcloud alpha (if available)
gcloud alpha monitoring policies list \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json

# Describe individual policy by ID (if gcloud alpha is available)
gcloud alpha monitoring policies describe \
  projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129 \
  --format=json

gcloud alpha monitoring policies describe \
  projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042 \
  --format=json
```

**REST API fallback (no alpha required):**

```bash
ACCESS_TOKEN=$(gcloud auth print-access-token)

# List all alert policies
curl -s -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/alertPolicies" \
  | python3 -m json.tool

# Describe worker policy
curl -s -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129" \
  | python3 -m json.tool

# Describe silver policy
curl -s -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042" \
  | python3 -m json.tool
```

Confirm for each policy: `enabled: true`, `notificationChannels` contains `1439157631105258885`, and the `filter` string in `conditionThreshold` is unchanged.

### 5.3 Notification channel

```bash
ACCESS_TOKEN=$(gcloud auth print-access-token)

curl -s -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885" \
  | python3 -m json.tool
```

Confirm: `enabled: true`, `type: email`, `labels.email_address` present.

### 5.4 Dashboard export check

```bash
# Confirm the exported JSON is still valid and matches the live resource
python3 -m json.tool infra/monitoring/dashboards/rtdp-pipeline-overview.json > /dev/null && \
  echo "JSON valid"

# Extract name and displayName from the exported JSON
python3 -c "
import json
d = json.load(open('infra/monitoring/dashboards/rtdp-pipeline-overview.json'))
print('name:', d.get('name'))
print('displayName:', d.get('displayName'))
"

# Re-fetch from GCP to compare (read-only)
ACCESS_TOKEN=$(gcloud auth print-access-token)
curl -s -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "https://monitoring.googleapis.com/v1/projects/project-42987e01-2123-446b-ac7/dashboards/1277f289-1f9a-4983-944f-913ce0f92622" \
  | python3 -m json.tool > /tmp/dashboard-live.json

diff infra/monitoring/dashboards/rtdp-pipeline-overview.json /tmp/dashboard-live.json
```

If the diff shows changes, update `infra/monitoring/dashboards/rtdp-pipeline-overview.json` with the live version before authoring the `google_monitoring_dashboard` HCL.

### 5.5 Final Cloud SQL and Scheduler state checks

Run these before and after all import work to confirm safe state is preserved throughout.

```bash
# Scheduler — must remain PAUSED
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)"
# Expected: PAUSED

# Cloud SQL — must remain NEVER / STOPPED
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Expected: NEVER  STOPPED
```

---

## 6. Proposed Terraform Mapping

The following resource blocks belong in a new file `infra/terraform/gcp/monitoring.tf`. This section describes the proposed mapping only. Do not create the file on the docs branch.

### 6.1 Logs-based metrics

```hcl
resource "google_logging_metric" "worker_message_processed_count" {
  name        = "worker_message_processed_count"
  description = "Count of successfully processed Pub/Sub messages by the RTDP worker"
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="rtdp-pubsub-worker"
    jsonPayload.service="rtdp-pubsub-worker"
    jsonPayload.operation="process_message"
    jsonPayload.status="ok"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "worker_message_error_count" {
  name        = "worker_message_error_count"
  description = "Count of failed Pub/Sub message processing attempts by the RTDP worker"
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="rtdp-pubsub-worker"
    jsonPayload.service="rtdp-pubsub-worker"
    jsonPayload.operation="process_message"
    jsonPayload.status="error"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "silver_refresh_success_count" {
  name        = "silver_refresh_success_count"
  description = "Count of successful silver refresh Cloud Run Job executions"
  filter      = <<-EOT
    resource.type="cloud_run_job"
    resource.labels.job_name="rtdp-silver-refresh-job"
    jsonPayload.service="rtdp-silver-refresh-job"
    jsonPayload.operation="refresh_market_event_minute_aggregates"
    jsonPayload.status="ok"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "silver_refresh_error_count" {
  name        = "silver_refresh_error_count"
  description = "Count of failed silver refresh Cloud Run Job executions"
  filter      = <<-EOT
    resource.type="cloud_run_job"
    resource.labels.job_name="rtdp-silver-refresh-job"
    jsonPayload.service="rtdp-silver-refresh-job"
    jsonPayload.operation="refresh_market_event_minute_aggregates"
    jsonPayload.status="error"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}
```

**Filter representation caveat:** The HCL above uses a heredoc. If `terraform plan` after import shows the filter as changed (e.g. provider canonicalises to a single-line space-separated string), adjust to match the provider's canonical form exactly before retrying. Do not `terraform apply` to reconcile the filter.

### 6.2 Cloud Monitoring dashboard

```hcl
resource "google_monitoring_dashboard" "rtdp_pipeline_overview" {
  dashboard_json = file("${path.root}/../../../infra/monitoring/dashboards/rtdp-pipeline-overview.json")
}
```

**Dashboard JSON path:** The `path.root` refers to the Terraform working directory (`infra/terraform/gcp/`). The relative path `../../../infra/monitoring/dashboards/rtdp-pipeline-overview.json` resolves to the exported dashboard JSON from the repository root. Confirm this path resolves correctly with `terraform validate` before running `terraform plan`.

**Dashboard JSON drift:** If the live dashboard JSON differs from the exported file (confirmed in §5.4 diff), update the exported file first. The Terraform plan must show zero diff on `dashboard_json` after import.

### 6.3 Alert policies

```hcl
resource "google_monitoring_alert_policy" "worker_error" {
  display_name = "RTDP Worker Message Error Alert"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "worker_message_error_count > 0"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/worker_message_error_count\" resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [
    "projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885"
  ]

  alert_strategy {
    auto_close = "604800s"
  }
}

resource "google_monitoring_alert_policy" "silver_refresh_error" {
  display_name = "RTDP Silver Refresh Error Alert"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "silver_refresh_error_count > 0"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/silver_refresh_error_count\" resource.type=\"cloud_run_job\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [
    "projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885"
  ]

  alert_strategy {
    auto_close = "604800s"
  }
}
```

**Note:** The `notification_channels` field uses a literal resource name string rather than a Terraform resource reference. This avoids a circular dependency if the notification channel is not imported in the same phase. If the notification channel is successfully imported and a `google_monitoring_notification_channel` resource is added to state, this can later be updated to reference `google_monitoring_notification_channel.operator_email.name`.

### 6.4 Notification channel — conditional only

Import and manage the notification channel under Terraform only if the caution criteria in §4.4 are fully satisfied. If proceeding, the proposed HCL is:

```hcl
resource "google_monitoring_notification_channel" "operator_email" {
  display_name = "RTDP Operator Email Alerts"
  type         = "email"
  enabled      = true

  labels = {
    email_address = "crsetsolutions@gmail.com"
  }
}
```

**Caution:** Some provider versions place the email address under `sensitive_labels` rather than `labels`. If `terraform plan` after import shows a diff on the email field, check the provider version's schema documentation for the correct field. Do not apply a plan that shows the email field changing.

---

## 7. Import ID Candidates

The following import IDs are derived from Phase 0 inventory and the Terraform provider documentation. They are marked **verify before use** — confirm each ID against the live resource state at execution time.

| Terraform resource | Import ID | Source | Notes |
|---|---|---|---|
| `google_logging_metric.worker_message_processed_count` | `worker_message_processed_count` | Provider docs | Metric name only — no project prefix |
| `google_logging_metric.worker_message_error_count` | `worker_message_error_count` | Provider docs | Metric name only |
| `google_logging_metric.silver_refresh_success_count` | `silver_refresh_success_count` | Provider docs | Metric name only |
| `google_logging_metric.silver_refresh_error_count` | `silver_refresh_error_count` | Provider docs | Metric name only |
| `google_monitoring_dashboard.rtdp_pipeline_overview` | `projects/project-42987e01-2123-446b-ac7/dashboards/1277f289-1f9a-4983-944f-913ce0f92622` | Phase 0 inventory | Dashboard ID confirmed from exported JSON |
| `google_monitoring_alert_policy.worker_error` | `projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129` | Phase 0 inventory | Full policy resource name |
| `google_monitoring_alert_policy.silver_refresh_error` | `projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042` | Phase 0 inventory | Full policy resource name |
| `google_monitoring_notification_channel.operator_email` | `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885` | Phase 0 inventory | **High caution — see §4.4** |

**Template import commands (for future execution branch only — do not run from docs branch):**

```bash
# Logs-based metrics
terraform import google_logging_metric.worker_message_processed_count \
  worker_message_processed_count

terraform import google_logging_metric.worker_message_error_count \
  worker_message_error_count

terraform import google_logging_metric.silver_refresh_success_count \
  silver_refresh_success_count

terraform import google_logging_metric.silver_refresh_error_count \
  silver_refresh_error_count

# Dashboard
terraform import google_monitoring_dashboard.rtdp_pipeline_overview \
  projects/project-42987e01-2123-446b-ac7/dashboards/1277f289-1f9a-4983-944f-913ce0f92622

# Alert policies
terraform import google_monitoring_alert_policy.worker_error \
  projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129

terraform import google_monitoring_alert_policy.silver_refresh_error \
  projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042

# Notification channel — only if §4.4 caution criteria are met
terraform import google_monitoring_notification_channel.operator_email \
  projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885
```

---

## 8. Plan Strategy

### 8.1 Branch structure

| Branch | Purpose |
|---|---|
| `feat/terraform-monitoring-skeleton` | Create `monitoring.tf`, review HCL against inventory, no import |
| `exec/terraform-monitoring-import-plan` | Import one resource at a time, run `terraform plan` after each import |

Do not merge the skeleton branch until its HCL has been reviewed against the Phase 0 inventory output. Do not open the execution branch until the skeleton branch is merged.

### 8.2 Import order

Import resources in this sequence. Stop after each plan check before proceeding.

| Step | Resource | Why this position |
|---|---|---|
| 1 | `google_logging_metric.worker_message_processed_count` | Lowest risk; filter-only resource; no live operational coupling |
| 2 | `google_logging_metric.worker_message_error_count` | Same rationale |
| 3 | `google_logging_metric.silver_refresh_success_count` | Same rationale |
| 4 | `google_logging_metric.silver_refresh_error_count` | Same rationale |
| 5 | `google_monitoring_dashboard.rtdp_pipeline_overview` | Medium risk; no alert coupling; dashboard JSON may drift |
| 6 | `google_monitoring_alert_policy.worker_error` | Medium risk; depends on metrics being stable in state |
| 7 | `google_monitoring_alert_policy.silver_refresh_error` | Medium risk; same rationale |
| 8 | `google_monitoring_notification_channel.operator_email` | **High caution; only if §4.4 criteria met** |

### 8.3 Plan checks after each import

After each `terraform import`, immediately run:

```bash
terraform -chdir=infra/terraform/gcp plan
```

Review the plan output for:

- Any `destroy` action on any resource — **stop immediately**.
- Any `-/+` replacement on any resource — **stop immediately**.
- Any change to a metric `filter` string — **stop immediately**.
- Any change to an alert policy `enabled` field — **stop immediately**.
- Any change to `notification_channels` on an alert policy — **stop immediately**.
- Any change to `dashboard_json` — **stop immediately; investigate JSON drift**.
- Any change to a notification channel `type`, `labels`, or `sensitive_labels` — **stop immediately**.

### 8.4 Absolute rules

- **Never run `terraform apply` during import validation.** Import puts resources into local state; apply would attempt to reconcile state against live resources and could mutate them.
- **Stop on any destroy or replacement.** Fix the HCL resource block to match the live resource exactly, then retry the import on a clean state (remove the resource from state with `terraform state rm`, re-import).
- **Stop if the dashboard JSON causes any diff.** Update `infra/monitoring/dashboards/rtdp-pipeline-overview.json` from the live API response and retry.
- **Stop if a metric filter differs.** Align the HCL heredoc to match the provider's canonical filter representation exactly.
- **Stop if the notification channel import causes a diff.** Do not apply; defer the notification channel and leave it unmanaged.

---

## 9. Acceptance Criteria

The monitoring import phase is accepted when the execution branch delivers all of the following:

- [ ] `monitoring.tf` created in `infra/terraform/gcp/` and reviewed against Phase 0 inventory
- [ ] All targeted resources imported into local Terraform state
- [ ] Final `terraform plan` exits with status 0
- [ ] Plan output shows **No changes. Your infrastructure matches the configuration.**
- [ ] No destroy, no replacement, no in-place update in the plan
- [ ] Alert policies remain `enabled = true`
- [ ] Both alert policies reference notification channel `1439157631105258885`
- [ ] Metric filters are identical to Phase 0 inventory values
- [ ] Dashboard JSON matches the live GCP resource (zero diff after import)
- [ ] Scheduler remains `PAUSED`
- [ ] Cloud SQL remains `NEVER / STOPPED`
- [ ] No `terraform apply` was run
- [ ] 116 tests pass (`uv run pytest -q`)
- [ ] Ruff clean (`uv run ruff check .`)
- [ ] Evidence document created in `docs/`

If the notification channel import cannot satisfy the zero-diff plan requirement, it is explicitly deferred — its deferral is documented in the evidence document and the channel is left unmanaged by Terraform in this phase.

---

## 10. Stop Conditions

Stop all Terraform work immediately if any of the following occur:

1. `terraform plan` proposes **destroy** of any resource.
2. `terraform plan` proposes **replacement** (`-/+`) of any resource.
3. Plan would change Cloud SQL `activation_policy` from `NEVER` to any other value.
4. Plan would change Scheduler state from `PAUSED` to `ENABLED`.
5. Plan shows any change to a logs-based metric `filter` string.
6. Plan shows `enabled = false` on any alert policy.
7. Plan would remove or modify `notification_channels` on either alert policy.
8. Plan would replace the notification channel `RTDP Operator Email Alerts` (ID `1439157631105258885`).
9. Plan shows any change to `dashboard_json` that is not explained by a known JSON normalisation.
10. Secrets or credential values appear in `terraform plan` or `terraform state show` output.
11. Terraform provider cannot import a resource in-place without proposing immediate changes that cannot be suppressed without `ignore_changes`.

When a stop condition is hit: do not apply, do not push state, investigate root cause, and update the HCL resource block before retrying.

---

## 11. Evidence Checklist

The execution branch evidence document must include:

| Evidence item | Required content |
|---|---|
| Branch name | e.g. `exec/terraform-monitoring-import-plan` |
| Terraform version | output of `terraform version` |
| Google provider version | from `.terraform.lock.hcl` |
| `terraform state list` output | After all imports — must include all targeted resources |
| `terraform plan` output | Final full plan output — must show zero changes |
| Inventory command outputs | `gcloud logging metrics describe` output for each metric |
| Alert policy describe outputs | REST API or gcloud alpha output confirming enabled + channel attached |
| Notification channel describe output | REST API output confirming enabled + type email |
| Dashboard diff result | Output of `diff` between exported JSON and live API response |
| Final Scheduler state | `PAUSED` confirmed |
| Final Cloud SQL state | `NEVER STOPPED` confirmed |
| `git status` output | Confirm no uncommitted state files |
| Test results | `uv run pytest -q` — 116 passed |
| Ruff result | `uv run ruff check .` — no issues |
| `terraform apply` confirmation | Explicit statement: not executed |
| Notification channel import outcome | Accepted or deferred with reason |

---

## 12. Explicit Non-Goals

This runbook does **not** cover:

| Non-goal | Notes |
|---|---|
| Cloud Run service/job import | Image digest drift strategy required first |
| Cloud SQL import | Deletion protection guardrails required first |
| IAM import | Full audit required first |
| Secret Manager import | State leakage risk must be resolved first |
| `terraform apply` | Forbidden in this phase |
| BigQuery / Dataflow work | Separate workstream |
| Automated deployment | Separate workstream |
| Slack or webhook notification channels | Not provisioned; out of scope |
| Remote Terraform backend | Deferred — local state only for exploratory import |

---

## 13. Next Branch Recommendations

| Branch | Purpose | Prerequisite |
|---|---|---|
| `feat/terraform-monitoring-skeleton` | Create `infra/terraform/gcp/monitoring.tf` with proposed HCL from §6; review against Phase 0 inventory; no `terraform import` or `terraform plan` | This runbook merged to `main` |
| `exec/terraform-monitoring-import-plan` | Import monitoring resources one at a time per §8; produce evidence document | `feat/terraform-monitoring-skeleton` merged and reviewed |

The skeleton branch is a safe documentation and HCL authoring step. The execution branch carries the operational risk and must not be opened until the skeleton HCL has been reviewed and accepted.

After a successful monitoring import, the remaining import candidates in priority order are:

1. Cloud Run services and jobs (requires `ignore_changes` image digest strategy)
2. Cloud SQL (requires explicit `deletion_protection = true` guardrail)
3. IAM bindings (requires full binding audit)
4. Secret Manager (requires state leakage risk assessment)

---

## 14. What This Runbook Does Not Do

This runbook explicitly does **not**:

- Create any Terraform files.
- Import any resource into Terraform state.
- Run `terraform init`, `terraform plan`, or `terraform apply`.
- Mutate any GCP resource.
- Start Cloud SQL.
- Resume or trigger the Cloud Scheduler job.
- Execute any Cloud Run Job.
- Publish any Pub/Sub messages.
- Deploy any service.

It is a planning and safety document only.
