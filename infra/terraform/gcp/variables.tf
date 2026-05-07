variable "project_id" {
  type        = string
  default     = "project-42987e01-2123-446b-ac7"
  description = "GCP project ID for the Real-Time Data Platform."
}

variable "region" {
  type        = string
  default     = "europe-west1"
  description = "GCP region for all regional resources."
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Deployment environment label (e.g. prod, staging, dev)."
}

variable "pubsub_push_oidc_service_account_email" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional OIDC service account email for the Pub/Sub push subscription. Must be confirmed during Phase 0 inventory before import/plan."
}
