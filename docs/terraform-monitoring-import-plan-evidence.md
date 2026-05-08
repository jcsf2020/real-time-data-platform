# Terraform Monitoring Import / Plan Evidence

## 1. Status

**VALIDATED - MONITORING IMPORT REACHED ZERO-DIFF PLAN**

This document records the Terraform import and plan evidence for the Cloud Monitoring resources in the Real-Time Data Platform.

No `terraform apply` was executed. No live GCP resources were intentionally modified. The final Terraform plan reached zero diff after all targeted imports.

## 2. Branch

`exec/terraform-monitoring-import-plan`

## 3. Scope

Imported into local Terraform state during this phase:

- `google_logging_metric.worker_message_processed_count`
- `google_logging_metric.worker_message_error_count`
- `google_logging_metric.silver_refresh_success_count`
- `google_logging_metric.silver_refresh_error_count`
- `google_monitoring_dashboard.rtdp_pipeline_overview`
- `google_monitoring_alert_policy.worker_error`
- `google_monitoring_alert_policy.silver_refresh_error`

Explicitly not imported in this phase:

- `google_monitoring_notification_channel.operator_email`
- Cloud SQL
- Cloud Run services/jobs
- IAM
- Secret Manager
- BigQuery / Dataflow
- Any deployment automation

## 4. Preflight State

Before the monitoring imports, the local Terraform state already contained the previously validated low-risk GCP resources:

```text
google_cloud_scheduler_job.silver_refresh_scheduler
google_pubsub_subscription.market_events_raw_worker_push
google_pubsub_topic.market_events_raw
google_pubsub_topic.market_events_raw_dlq
```

Preflight validation confirmed:

```text
terraform fmt -check -recursive infra/terraform/gcp: passed
terraform -chdir=infra/terraform/gcp validate: success
```

## 5. Imported Resources

| Terraform resource | Import ID | Result |
|---|---|---|
| `google_logging_metric.worker_message_processed_count` | `worker_message_processed_count` | Imported successfully |
| `google_logging_metric.worker_message_error_count` | `worker_message_error_count` | Imported successfully |
| `google_logging_metric.silver_refresh_success_count` | `silver_refresh_success_count` | Imported successfully |
| `google_logging_metric.silver_refresh_error_count` | `silver_refresh_error_count` | Imported successfully |
| `google_monitoring_dashboard.rtdp_pipeline_overview` | `projects/project-42987e01-2123-446b-ac7/dashboards/1277f289-1f9a-4983-944f-913ce0f92622` | Imported successfully |
| `google_monitoring_alert_policy.worker_error` | `projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129` | Imported successfully |
| `google_monitoring_alert_policy.silver_refresh_error` | `projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042` | Imported successfully |

## 6. Import Order

Resources were imported one at a time, with `terraform plan` checks between imports.

1. `google_logging_metric.worker_message_processed_count`
2. `google_logging_metric.worker_message_error_count`
3. `google_logging_metric.silver_refresh_success_count`
4. `google_logging_metric.silver_refresh_error_count`
5. `google_monitoring_dashboard.rtdp_pipeline_overview`
6. `google_monitoring_alert_policy.worker_error`
7. `google_monitoring_alert_policy.silver_refresh_error`

## 7. Drift Found and Resolution

### Logs-Based Metric Filter Drift

After importing `google_logging_metric.worker_message_processed_count`, the first `terraform plan` showed an in-place update on the metric `filter`.

Root cause:

```text
The original HCL used raw heredoc filters. Terraform/provider comparison detected filter string drift due to heredoc formatting / whitespace handling.
```

Resolution:

All `google_logging_metric` filter definitions in `infra/terraform/gcp/monitoring.tf` were patched to use `trimspace(<<-EOT ... EOT)`.

Example pattern:

```hcl
filter = trimspace(<<-EOT
  resource.type="cloud_run_revision"
  resource.labels.service_name="rtdp-pubsub-worker"
  jsonPayload.service="rtdp-pubsub-worker"
  jsonPayload.operation="process_message"
  jsonPayload.status="ok"
EOT
)
```

After the patch and `terraform fmt`, the already-imported metric no longer showed drift.

## 8. Final Terraform Plan Result

After all targeted imports, the final Terraform plan returned:

```text
No changes. Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your configuration and found no differences, so no changes are needed.
```

Final plan result:

```text
0 to add, 0 to change, 0 to destroy
```

## 9. Notification Channel Decision

The email notification channel was intentionally not imported:

```text
google_monitoring_notification_channel.operator_email
```

Reason:

`docs/terraform-monitoring-import-runbook.md` classifies the notification channel as high caution because of:

- sensitive operator email state exposure risk;
- provider drift risk around `labels`, `sensitive_labels`, and verification fields;
- alert policy coupling risk if a replacement were proposed.

The alert policies continue to reference the existing notification channel by literal resource name:

```text
projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885
```

## 10. Terraform State Coverage

After this import phase, Terraform local state covers:

```text
google_cloud_scheduler_job.silver_refresh_scheduler
google_logging_metric.silver_refresh_error_count
google_logging_metric.silver_refresh_success_count
google_logging_metric.worker_message_error_count
google_logging_metric.worker_message_processed_count
google_monitoring_alert_policy.silver_refresh_error
google_monitoring_alert_policy.worker_error
google_monitoring_dashboard.rtdp_pipeline_overview
google_pubsub_subscription.market_events_raw_worker_push
google_pubsub_topic.market_events_raw
google_pubsub_topic.market_events_raw_dlq
```

This means the current Terraform local state now represents:

- Pub/Sub raw topic;
- Pub/Sub DLQ topic;
- Pub/Sub push subscription;
- Cloud Scheduler job;
- four logs-based metrics;
- Cloud Monitoring dashboard;
- two Cloud Monitoring alert policies.

## 11. Explicit Non-Actions

The following actions were not performed:

- No `terraform apply`
- No Cloud SQL import
- No Cloud Run import
- No IAM import
- No Secret Manager import
- No notification channel import
- No GCP deployment
- No Cloud SQL start
- No Scheduler run
- No Cloud Run Job execution
- No Pub/Sub publishing
- No application code changes
- No test changes

## 12. Final Validation

Final validation was executed after all targeted imports.

```text
terraform fmt -check -recursive infra/terraform/gcp: passed
terraform -chdir=infra/terraform/gcp validate: success
terraform -chdir=infra/terraform/gcp state list: 11 resources
terraform -chdir=infra/terraform/gcp plan: No changes
uv run pytest -q: 116 passed
uv run ruff check .: clean
Scheduler final state: PAUSED
Cloud SQL final state: NEVER STOPPED
```

Final Terraform state list:

```text
google_cloud_scheduler_job.silver_refresh_scheduler
google_logging_metric.silver_refresh_error_count
google_logging_metric.silver_refresh_success_count
google_logging_metric.worker_message_error_count
google_logging_metric.worker_message_processed_count
google_monitoring_alert_policy.silver_refresh_error
google_monitoring_alert_policy.worker_error
google_monitoring_dashboard.rtdp_pipeline_overview
google_pubsub_subscription.market_events_raw_worker_push
google_pubsub_topic.market_events_raw
google_pubsub_topic.market_events_raw_dlq
```

Final git status before commit:

```text
## exec/terraform-monitoring-import-plan
 M infra/terraform/gcp/monitoring.tf
?? docs/terraform-monitoring-import-plan-evidence.md
```

## 13. Acceptance Result

Accepted.

The Terraform Monitoring import/plan phase is complete. All targeted monitoring resources were imported into local Terraform state and the final Terraform plan reached zero diff.

This closes the monitoring Terraform import/plan phase for the core observability layer.
