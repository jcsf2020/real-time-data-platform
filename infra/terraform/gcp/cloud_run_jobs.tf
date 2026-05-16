# DATABASE_URL is used as the credential source; DBT_POSTGRES_HOST overrides the URL host to use the Cloud SQL Unix socket mount.
# Deployed: terraform apply executed on feat/dbt-refresh-cloud-run-deploy; zero-diff plan confirmed. Cloud Run Job exists in GCP.
resource "google_cloud_run_v2_job" "rtdp_dbt_refresh_job" {
  name     = "rtdp-dbt-refresh-job"
  location = var.region
  project  = var.project_id

  template {
    task_count = 1

    template {
      service_account = "rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
      timeout         = "600s"
      max_retries     = 0

      containers {
        image = "europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-dbt-refresh-job:latest"

        env {
          name  = "DBT_REFRESH_MODE"
          value = "run-and-test"
        }

        env {
          name  = "DBT_POSTGRES_HOST"
          value = "/cloudsql/project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres"
        }

        env {
          name  = "DBT_POSTGRES_PORT"
          value = "5432"
        }

        env {
          name  = "DBT_POSTGRES_USER"
          value = "rtdp"
        }

        env {
          name  = "DBT_POSTGRES_DBNAME"
          value = "realtime_platform"
        }

        env {
          name  = "DBT_TARGET"
          value = "cloudsql"
        }

        env {
          name  = "DBT_PROJECT_DIR"
          value = "/app/dbt"
        }

        env {
          name  = "DBT_PROFILES_DIR"
          value = "/tmp/rtdp-dbt-profiles"
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
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].template[0].containers[0].image,
      template[0].annotations,
      template[0].labels,
    ]
  }
}

resource "google_cloud_run_v2_job" "rtdp_bigquery_append_job" {
  name     = "rtdp-bigquery-append-job"
  location = var.region
  project  = var.project_id

  template {
    task_count = 1

    template {
      service_account = "rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
      timeout         = "600s"
      max_retries     = 0

      containers {
        image = "europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-bigquery-append-job:latest"

        env {
          name  = "PROJECT_ID"
          value = "project-42987e01-2123-446b-ac7"
        }

        env {
          name  = "BQ_DATASET"
          value = "rtdp_analytics"
        }

        env {
          name  = "BQ_TARGET_TABLE"
          value = "market_events_raw"
        }

        env {
          name  = "BQ_STAGING_TABLE"
          value = "market_events_raw_staging"
        }

        env {
          name  = "APPEND_BATCH_LIMIT"
          value = "1000"
        }

        env {
          name  = "APPEND_DRY_RUN"
          value = "false"
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
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].template[0].containers[0].image,
      template[0].annotations,
      template[0].labels,
    ]
  }
}

resource "google_cloud_run_v2_job" "rtdp_silver_refresh_job" {
  name     = "rtdp-silver-refresh-job"
  location = var.region
  project  = var.project_id

  template {
    task_count = 1

    template {
      service_account = "rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
      timeout         = "300s"
      max_retries     = 0

      containers {
        image = "europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest"

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

    annotations = {
      "run.googleapis.com/execution-environment" = "gen2"
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].template[0].containers[0].image,
      template[0].annotations,
      template[0].labels,
    ]
  }
}
