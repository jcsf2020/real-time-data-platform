resource "google_cloud_scheduler_job" "silver_refresh_scheduler" {
  name        = local.scheduler_silver_refresh
  region      = var.region
  description = "Triggers rtdp-silver-refresh-job every 15 minutes to populate silver.market_event_minute_aggregates. Kept PAUSED except during bounded execution windows."
  schedule    = "*/15 * * * *"
  time_zone   = "UTC"
  paused      = true

  http_target {
    uri         = "https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-silver-refresh-job:run"
    http_method = "POST"

    oauth_token {
      service_account_email = "rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
