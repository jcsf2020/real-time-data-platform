# ---------------------------------------------------------------------------
# Dataflow Proof Service Account
# ---------------------------------------------------------------------------

resource "google_service_account" "rtdp_dataflow_sa" {
  account_id   = "rtdp-dataflow-sa"
  project      = var.project_id
  display_name = "RTDP Dataflow Proof Service Account"

  lifecycle {
    prevent_destroy = true
  }
}

# ---------------------------------------------------------------------------
# GCS Staging / Temp Bucket
# Deterministic name: rtdp-dataflow-staging-<project_id>.
# Lifecycle rule deletes all objects after 7 days.
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "rtdp_dataflow_staging" {
  name                        = "rtdp-dataflow-staging-${var.project_id}"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
}

# ---------------------------------------------------------------------------
# Pub/Sub Proof Subscription (pull only)
# Separate from the production worker push subscription.
# Does not affect existing market-events-raw-worker-push.
# ---------------------------------------------------------------------------

resource "google_pubsub_subscription" "market_events_raw_beam_proof_sub" {
  name    = "market-events-raw-beam-proof-sub"
  topic   = google_pubsub_topic.market_events_raw.name
  project = var.project_id

  ack_deadline_seconds       = 60
  message_retention_duration = "600s"
}

# ---------------------------------------------------------------------------
# BigQuery Proof Table
# Proof-only; deletion_protection = false.
# Schema is a minimal subset of market_events_raw matching pipeline output.
# Partitioned on event_timestamp; clustered on symbol, event_type (same
# pattern as market_events_raw).
# ---------------------------------------------------------------------------

resource "google_bigquery_table" "market_events_beam_proof" {
  dataset_id          = google_bigquery_dataset.rtdp_analytics.dataset_id
  table_id            = "market_events_beam_proof"
  project             = var.project_id
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  clustering = ["symbol", "event_type"]

  schema = file("${path.module}/schemas/market_events_beam_proof.json")
}

# ---------------------------------------------------------------------------
# IAM -- Least-privilege bindings for rtdp-dataflow-sa
#
# Two bindings are unavoidably project-scoped:
#   roles/dataflow.worker   -- GCP requires this at project level; no
#                              resource-scoped equivalent exists for worker
#                              process startup.
#   roles/bigquery.jobUser  -- Required to submit BQ write jobs; GCP does
#                              not support resource-level scoping for this
#                              role.
# All other bindings are scoped to the specific proof resource.
# ---------------------------------------------------------------------------

# Project-level: required by GCP; no resource-scoped equivalent for Dataflow workers.
resource "google_project_iam_member" "dataflow_sa_dataflow_worker" {
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.rtdp_dataflow_sa.email}"
}

# Project-level: required by GCP to submit BigQuery write jobs.
resource "google_project_iam_member" "dataflow_sa_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.rtdp_dataflow_sa.email}"
}

# Scoped to the staging bucket only.
resource "google_storage_bucket_iam_member" "dataflow_sa_staging_object_admin" {
  bucket = google_storage_bucket.rtdp_dataflow_staging.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.rtdp_dataflow_sa.email}"
}

# Scoped to the proof subscription only.
resource "google_pubsub_subscription_iam_member" "dataflow_sa_proof_sub_subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.market_events_raw_beam_proof_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.rtdp_dataflow_sa.email}"
}

# Scoped to the proof table only; production market_events_raw is untouched.
resource "google_bigquery_table_iam_member" "dataflow_sa_proof_table_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.rtdp_analytics.dataset_id
  table_id   = google_bigquery_table.market_events_beam_proof.table_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.rtdp_dataflow_sa.email}"
}
