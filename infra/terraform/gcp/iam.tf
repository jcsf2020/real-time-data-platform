locals {
  default_compute_service_account = "serviceAccount:892892382088-compute@developer.gserviceaccount.com"
  rtdp_worker_service_account     = "serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
  rtdp_scheduler_service_account  = "serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
  terraform_plan_ci_member        = "serviceAccount:rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
  cloud_run_deploy_ci_member      = "serviceAccount:rtdp-cloud-run-deploy-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
  github_actions_principal        = "principalSet://iam.googleapis.com/projects/892892382088/locations/global/workloadIdentityPools/github-actions/attribute.repository/jcsf2020/real-time-data-platform"
}

resource "google_project_iam_member" "compute_artifactregistry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = local.default_compute_service_account
}

resource "google_project_iam_member" "compute_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = local.default_compute_service_account
}

resource "google_project_iam_member" "worker_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = local.rtdp_worker_service_account
}

resource "google_project_iam_member" "worker_monitoring_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = local.rtdp_worker_service_account
}

resource "google_project_iam_member" "compute_logging_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = local.default_compute_service_account
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_bigquery_append_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.rtdp_bigquery_append_job.name
  role     = "roles/run.invoker"
  member   = local.rtdp_scheduler_service_account
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_dbt_refresh_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.rtdp_dbt_refresh_job.name
  role     = "roles/run.invoker"
  member   = local.rtdp_scheduler_service_account
}

resource "google_project_iam_member" "compute_storage_object_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = local.default_compute_service_account
}

resource "google_project_iam_member" "terraform_plan_ci_viewer" {
  project = var.project_id
  role    = "roles/viewer"
  member  = local.terraform_plan_ci_member
}

resource "google_project_iam_member" "terraform_plan_ci_monitoring_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = local.terraform_plan_ci_member
}

resource "google_service_account_iam_member" "terraform_plan_ci_workload_identity_user" {
  service_account_id = google_service_account.rtdp_terraform_plan_ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_actions_principal
}

resource "google_project_iam_member" "cloud_run_deploy_ci_artifactregistry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = local.cloud_run_deploy_ci_member

  depends_on = [
    google_service_account.rtdp_cloud_run_deploy_ci,
  ]
}

resource "google_project_iam_member" "cloud_run_deploy_ci_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = local.cloud_run_deploy_ci_member

  depends_on = [
    google_service_account.rtdp_cloud_run_deploy_ci,
  ]
}

resource "google_service_account_iam_member" "cloud_run_deploy_ci_workload_identity_user" {
  service_account_id = google_service_account.rtdp_cloud_run_deploy_ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_actions_principal
}

resource "google_service_account_iam_member" "cloud_run_deploy_ci_worker_service_account_user" {
  service_account_id = google_service_account.rtdp_worker_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.cloud_run_deploy_ci_member

  depends_on = [
    google_service_account.rtdp_cloud_run_deploy_ci,
  ]
}

resource "google_service_account_iam_member" "cloud_run_deploy_ci_api_service_account_user" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/892892382088-compute@developer.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = local.cloud_run_deploy_ci_member

  depends_on = [
    google_service_account.rtdp_cloud_run_deploy_ci,
  ]
}
