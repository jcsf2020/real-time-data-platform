locals {
  platform_name = "rtdp"

  pubsub_topic_market_events_raw     = "market-events-raw"
  pubsub_topic_market_events_raw_dlq = "market-events-raw-dlq"
  pubsub_subscription_worker_push    = "market-events-raw-worker-push"

  scheduler_silver_refresh = "rtdp-silver-refresh-scheduler"

  cloud_run_worker_url = "https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push"
}
