resource "google_cloud_run_v2_service" "rtdp_api" {
  name     = "rtdp-api"
  location = var.region
  project  = var.project_id

  build_config {
    enable_automatic_updates = false
    environment_variables    = {}
    image_uri                = "europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/cloud-run-source-deploy/rtdp-api"
    source_location          = "gs://run-sources-project-42987e01-2123-446b-ac7-europe-west1/services/rtdp-api/1777840602.276835-7532328e85304d869a77c598b1a26941.zip#1777840602567858"
  }

  scaling {
    manual_instance_count = 0
    min_instance_count    = 0
  }

  template {
    service_account                  = "892892382088-compute@developer.gserviceaccount.com"
    timeout                          = "300s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 20
    }

    containers {
      image = "europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/cloud-run-source-deploy/rtdp-api@sha256:0b44c36a71b305653dfe85a74d98075ae238bf19458917412d95a3a29515af78"

      ports {
        name           = "http1"
        container_port = 8080
      }

      env {
        name = "DATABASE_URL"

        value_source {
          secret_key_ref {
            secret  = "rtdp-database-url"
            version = "latest"
          }
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = "gcp-cloud-run"
      }

      env {
        name  = "SERVICE_NAME"
        value = "rtdp-api"
      }

      env {
        name  = "SERVICE_VERSION"
        value = "0.1.0-pagination-fix"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }

        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        failure_threshold = 1
        period_seconds    = 240
        timeout_seconds   = 240

        tcp_socket {
          port = 8080
        }
      }

      volume_mounts {
        mount_path = "/cloudsql"
        name       = "cloudsql"
      }
    }

    volumes {
      name = "cloudsql"

      cloud_sql_instance {
        instances = [
          "project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres",
        ]
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      build_config,
      client,
      client_version,
      template[0].containers[0].image,
      template[0].labels,
      traffic,
    ]
  }
}

resource "google_cloud_run_v2_service" "rtdp_pubsub_worker" {
  name     = "rtdp-pubsub-worker"
  location = var.region
  project  = var.project_id

  scaling {
    manual_instance_count = 0
    min_instance_count    = 0
  }

  template {
    service_account                  = "rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
    timeout                          = "60s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = "europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest"

      ports {
        name           = "http1"
        container_port = 8080
      }

      env {
        name = "DATABASE_URL"

        value_source {
          secret_key_ref {
            secret  = "rtdp-database-url"
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }

        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        failure_threshold = 1
        period_seconds    = 240
        timeout_seconds   = 240

        tcp_socket {
          port = 8080
        }
      }

      volume_mounts {
        mount_path = "/cloudsql"
        name       = "cloudsql"
      }
    }

    volumes {
      name = "cloudsql"

      cloud_sql_instance {
        instances = [
          "project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres",
        ]
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
      template[0].labels,
      traffic,
    ]
  }
}
