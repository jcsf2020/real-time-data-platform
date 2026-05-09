resource "google_sql_database_instance" "rtdp_postgres" {
  name                = "rtdp-postgres"
  project             = var.project_id
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = true

  settings {
    tier                         = "db-custom-1-3840"
    availability_type            = "ZONAL"
    edition                      = "ENTERPRISE"
    disk_type                    = "PD_HDD"
    disk_size                    = 10
    disk_autoresize              = false
    activation_policy            = "NEVER"
    enable_dataplex_integration  = true
    enable_google_ml_integration = false

    backup_configuration {
      enabled                        = false
      binary_log_enabled             = false
      point_in_time_recovery_enabled = false
      start_time                     = "00:00"
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    data_cache_config {
      data_cache_enabled = false
    }

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"

      authorized_networks {
        value = "37.189.31.189/32"
      }
    }

    location_preference {
      zone = "europe-west1-b"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
