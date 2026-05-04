

# GCP Worker Cloud Validation

## Status

Validated on: 2026-05-04

This document records the first real Cloud SQL validation of the Pub/Sub worker path.

## Validation objective

Prove that a Pub/Sub-style `MarketEvent` JSON payload can be processed by the worker and persisted into the managed GCP operational database.

## Validated path

```text
Manual MarketEvent JSON
  -> rtdp-pubsub-worker
    -> MarketEvent contract validation
      -> Cloud SQL PostgreSQL bronze.market_events
        -> Cloud Run API /events
```

## GCP resources involved

```text
Project: project-42987e01-2123-446b-ac7
Region: europe-west1
Cloud SQL instance: rtdp-postgres
Database: realtime_platform
Cloud Run API: rtdp-api
Pub/Sub topic: market-events-raw
Secret Manager secret: rtdp-database-url
```

## Cost-control procedure

Cloud SQL was started only for the validation window:

```text
Before validation: activationPolicy=NEVER, state=STOPPED
During validation: activationPolicy=ALWAYS, state=RUNNABLE
After validation: activationPolicy=NEVER, state=STOPPED
```

Final verified state:

```text
NEVER   STOPPED
```

## Worker validation outcome

The worker processed one controlled event:

```json
{"status": "ok", "event_id": "cloud-worker-test-20260504090458"}
```

Cloud SQL confirmed the row:

```text
event_id                          | symbol  | source_topic
cloud-worker-test-20260504090458  | BTCUSDT | market-events-raw
```

## API validation outcome

The Cloud Run API returned the inserted event from Cloud SQL:

```json
[
  {
    "event_id": "cloud-worker-test-20260504090458",
    "symbol": "BTCUSDT",
    "event_type": "trade",
    "price": 67500.0,
    "quantity": 0.01,
    "event_timestamp": "2026-05-04T06:30:00Z",
    "ingested_at": "2026-05-04T08:05:00.233750Z",
    "source_topic": "market-events-raw"
  }
]
```

## What this proves

This validates the critical cloud write path:

```text
Pub/Sub-compatible payload
  -> worker validation
    -> idempotent operational write
      -> managed Cloud SQL
        -> API readback
```

## What this does not prove yet

This is not yet a fully automated GCP real-time ingestion pipeline.

Not implemented yet:

```text
Pub/Sub push subscription
  -> deployed Cloud Run worker
    -> automatic Cloud SQL write
```

## Recruiter-facing claim

Accurate claim:

> The project includes a local Kafka-compatible real-time pipeline and a GCP serving/database layer. It also validates a Pub/Sub-compatible worker path where contract-valid event payloads are written into Cloud SQL and exposed through a Cloud Run API.

Do not yet claim:

> Full GCP real-time pipeline in production.

## Next milestone

Deploy the worker as a Cloud Run service and connect it to Pub/Sub through a push subscription:

```text
Pub/Sub topic
  -> push subscription
    -> Cloud Run worker endpoint
      -> Cloud SQL bronze.market_events
        -> Cloud Run API /events
```