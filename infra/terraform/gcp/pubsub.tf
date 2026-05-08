resource "google_pubsub_topic" "market_events_raw" {
  name = local.pubsub_topic_market_events_raw

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_pubsub_topic" "market_events_raw_dlq" {
  name = local.pubsub_topic_market_events_raw_dlq

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_pubsub_subscription" "market_events_raw_worker_push" {
  name                       = local.pubsub_subscription_worker_push
  topic                      = google_pubsub_topic.market_events_raw.name
  message_retention_duration = "600s"

  push_config {
    push_endpoint = local.cloud_run_worker_url

    # OIDC service account confirmed by Terraform Phase 0 inventory.
    # Keep aligned with the live Pub/Sub push subscription before import/plan.
    dynamic "oidc_token" {
      for_each = var.pubsub_push_oidc_service_account_email == null ? [] : [var.pubsub_push_oidc_service_account_email]

      content {
        service_account_email = oidc_token.value
      }
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.market_events_raw_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "60s"
  }

  lifecycle {
    prevent_destroy = true
  }
}
