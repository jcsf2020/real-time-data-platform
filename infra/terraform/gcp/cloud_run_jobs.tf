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
      "run.googleapis.com/cloudsql-instances"    = "project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres"
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
