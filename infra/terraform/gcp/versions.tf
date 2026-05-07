terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Backend is intentionally local-only until a GCS backend strategy is approved.
  # A remote backend (GCS bucket, IAM permissions, locking strategy) must be
  # explicitly decided and documented before this block is populated.
  # See docs/terraform-iac-baseline-runbook.md §9 for the state strategy.
}
