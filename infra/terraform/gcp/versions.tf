terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  backend "gcs" {
    bucket = "rtdp-terraform-state-project-42987e01-2123-446b-ac7"
    prefix = "real-time-data-platform/gcp/prod"
  }
}
