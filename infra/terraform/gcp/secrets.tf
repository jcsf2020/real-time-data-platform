resource "google_secret_manager_secret" "rtdp_database_url" {
  secret_id = "rtdp-database-url"
  project   = var.project_id

  replication {
    auto {}
  }

  lifecycle {
    prevent_destroy = true
  }
}
