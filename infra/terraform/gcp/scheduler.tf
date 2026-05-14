resource "google_cloud_scheduler_job" "silver_refresh_scheduler" {
  name      = local.scheduler_silver_refresh
  region    = var.region
  schedule  = "*/15 * * * *"
  time_zone = "UTC"
  paused    = true

  http_target {
    # Scheduler remains paused by default; URI now targets the accepted dbt refresh job.
    uri         = "https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-dbt-refresh-job:run"
    http_method = "POST"

    oauth_token {
      service_account_email = "rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
    }
  }

  retry_config {
    retry_count          = 0
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }

  lifecycle {
    prevent_destroy = true
  }
}
