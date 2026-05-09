resource "google_artifact_registry_repository" "rtdp" {
  project       = var.project_id
  location      = var.region
  repository_id = "rtdp"
  format        = "DOCKER"
  description   = "Real-Time Data Platform container images"

  lifecycle {
    prevent_destroy = true
  }
}
