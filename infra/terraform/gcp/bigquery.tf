resource "google_bigquery_dataset" "rtdp_analytics" {
  dataset_id    = "rtdp_analytics"
  friendly_name = "RTDP Analytics"
  description   = "Analytical warehouse for Real-Time Data Platform event history"
  location      = var.region
  project       = var.project_id

  labels = {
    environment = var.environment
    platform    = local.platform_name
    tier        = "analytics"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "market_events_raw" {
  dataset_id          = google_bigquery_dataset.rtdp_analytics.dataset_id
  table_id            = "market_events_raw"
  project             = var.project_id
  deletion_protection = true

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  clustering = ["symbol", "event_type"]

  schema = file("${path.module}/schemas/market_events_raw.json")

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "market_events_raw_staging" {
  dataset_id          = google_bigquery_dataset.rtdp_analytics.dataset_id
  table_id            = "market_events_raw_staging"
  project             = var.project_id
  deletion_protection = false

  schema = file("${path.module}/schemas/market_events_raw.json")
}

resource "google_bigquery_table" "market_event_minute_aggregates" {
  dataset_id          = google_bigquery_dataset.rtdp_analytics.dataset_id
  table_id            = "market_event_minute_aggregates"
  project             = var.project_id
  deletion_protection = true

  time_partitioning {
    type  = "DAY"
    field = "window_start"
  }

  clustering = ["symbol", "event_type"]

  schema = file("${path.module}/schemas/market_event_minute_aggregates.json")

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "market_event_daily_aggregates" {
  dataset_id          = google_bigquery_dataset.rtdp_analytics.dataset_id
  table_id            = "market_event_daily_aggregates"
  project             = var.project_id
  deletion_protection = true

  time_partitioning {
    type  = "DAY"
    field = "event_date"
  }

  clustering = ["symbol"]

  schema = file("${path.module}/schemas/market_event_daily_aggregates.json")

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset_iam_member" "rtdp_worker_bigquery_data_editor" {
  dataset_id = google_bigquery_dataset.rtdp_analytics.dataset_id
  project    = var.project_id
  role       = "roles/bigquery.dataEditor"
  member     = local.rtdp_worker_service_account
}

resource "google_project_iam_member" "rtdp_worker_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = local.rtdp_worker_service_account
}
