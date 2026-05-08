# monitoring.tf
# Aligned to Phase 0 inventory (docs/evidence/terraform-phase-0-inventory/).
# SKELETON ONLY — all resources must be imported and validated with
# terraform plan (zero-diff) before any terraform apply is attempted.

# ─── Logs-Based Metrics ──────────────────────────────────────────────────────

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
    unit        = "1"
  }

  lifecycle {
    prevent_destroy = true
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
    unit        = "1"
  }

  lifecycle {
    prevent_destroy = true
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
    unit        = "1"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Intentionally omits resource.labels.job_name — absent from Phase 0 inventory
# for this metric (contrast: silver_refresh_success_count includes it).
resource "google_logging_metric" "silver_refresh_error_count" {
  name        = "silver_refresh_error_count"
  description = "Count of failed silver refresh Cloud Run Job executions"
  filter      = <<-EOT
    resource.type="cloud_run_job"
    jsonPayload.service="rtdp-silver-refresh-job"
    jsonPayload.operation="refresh_market_event_minute_aggregates"
    jsonPayload.status="error"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# ─── Dashboard ───────────────────────────────────────────────────────────────

# Import ID caution: the exported JSON uses numeric project number 892892382088
# (field "name": "projects/892892382088/dashboards/1277f289-1f9a-4983-944f-913ce0f92622").
# The import command may require the textual project ID
# project-42987e01-2123-446b-ac7. Verify the import ID format against the
# monitoring import runbook before running terraform import.
resource "google_monitoring_dashboard" "rtdp_pipeline_overview" {
  dashboard_json = file("${path.module}/../../monitoring/dashboards/rtdp-pipeline-overview.json")

  lifecycle {
    prevent_destroy = true
  }
}

# ─── Notification Channel ────────────────────────────────────────────────────
# google_monitoring_notification_channel is intentionally NOT managed in this
# skeleton. The monitoring import runbook classifies the email notification
# channel as high caution: importing it places the operator email address in
# Terraform state, and any plan diff could silently suppress live alerts.
# Alert policies reference the channel by literal string until a dedicated
# import/plan cycle is validated for this resource.

# ─── Alert Policies ──────────────────────────────────────────────────────────

resource "google_monitoring_alert_policy" "worker_error" {
  display_name = "RTDP Worker Message Error Alert"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "worker_message_error_count > 0"

    condition_threshold {
      filter     = "metric.type=\"logging.googleapis.com/user/worker_message_error_count\" resource.type=\"cloud_run_revision\""
      comparison = "COMPARISON_GT"
      duration   = "0s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  # Notification channel managed outside Terraform — see comment above.
  notification_channels = [
    "projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885",
  ]

  alert_strategy {
    auto_close = "604800s"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_monitoring_alert_policy" "silver_refresh_error" {
  display_name = "RTDP Silver Refresh Error Alert"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "silver_refresh_error_count > 0"

    condition_threshold {
      filter     = "metric.type=\"logging.googleapis.com/user/silver_refresh_error_count\" resource.type=\"cloud_run_job\""
      comparison = "COMPARISON_GT"
      duration   = "0s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  # Notification channel managed outside Terraform — see comment above.
  notification_channels = [
    "projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885",
  ]

  alert_strategy {
    auto_close = "604800s"
  }

  lifecycle {
    prevent_destroy = true
  }
}
