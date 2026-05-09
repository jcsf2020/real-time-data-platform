resource "google_service_account" "rtdp_scheduler_sa" {
  account_id   = "rtdp-scheduler-sa"
  project      = var.project_id
  display_name = "RTDP Cloud Scheduler caller for silver refresh job"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account" "rtdp_worker_sa" {
  account_id   = "rtdp-worker-sa"
  project      = var.project_id
  display_name = "RTDP PubSub Worker"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account" "rtdp_pubsub_push_sa" {
  account_id   = "rtdp-pubsub-push-sa"
  project      = var.project_id
  display_name = "RTDP PubSub Push Invoker"

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account" "rtdp_terraform_plan_ci" {
  account_id   = "rtdp-terraform-plan-ci"
  project      = var.project_id
  display_name = "RTDP Terraform Plan CI"

  lifecycle {
    prevent_destroy = true
  }
}
