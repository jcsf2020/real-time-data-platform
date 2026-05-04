# GCP End-to-End Validation

## Status

Validated on: 2026-05-04

This is the first full GCP end-to-end validation of the real-time ingestion pipeline.
A `MarketEvent` was published to Pub/Sub, routed automatically through a push subscription
to the Cloud Run worker, persisted into Cloud SQL, and confirmed via the Cloud Run API.

## Validation objective

Prove that a Pub/Sub message published to a managed GCP topic is automatically delivered
to the Cloud Run worker via a push subscription, passes contract validation, is persisted
into Cloud SQL `bronze.market_events`, and is subsequently readable through the Cloud Run
API — without any manual curl or direct worker invocation in the hot path.

## Validated path

```text
Pub/Sub topic
  -> push subscription
    -> Cloud Run worker
      -> POST /pubsub/push
        -> Pub/Sub envelope decode
          -> MarketEvent validation
            -> Cloud SQL bronze.market_events
              -> Cloud Run API /events
```

## GCP resources involved

| Resource | Name |
|---|---|
| GCP project | project-42987e01-2123-446b-ac7 |
| Region | europe-west1 |
| Pub/Sub topic | market-events-raw |
| Pub/Sub push subscription | market-events-raw-worker-push |
| Worker Cloud Run service | rtdp-pubsub-worker |
| API Cloud Run service | rtdp-api |
| API URL | https://rtdp-api-892892382088.europe-west1.run.app |
| Cloud SQL instance | rtdp-postgres |
| Cloud SQL database | realtime_platform |
| Secret Manager secret | rtdp-database-url |
| Worker runtime service account | rtdp-worker-sa |
| Pub/Sub push service account | rtdp-pubsub-push-sa |
| Artifact Registry repository | rtdp |
| Worker image | europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest |

## Deployment evidence

**Service:** `rtdp-pubsub-worker`
**Revision:** `rtdp-pubsub-worker-00002-xp7`
**Worker URL:** `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app`

Health check command and output:

```bash
WORKER_URL="https://rtdp-pubsub-worker-892892382088.europe-west1.run.app" && \
curl -s -w "\nHTTP %{http_code}\n" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$WORKER_URL/health"
```

```text
{"status":"ok"}
HTTP 200
```

## Pub/Sub push subscription evidence

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --format="value(name,pushConfig.pushEndpoint,pushConfig.oidcToken.serviceAccountEmail)"
```

```text
projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push     https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push  rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

The subscription is configured with OIDC authentication. GCP attaches an identity token
signed by `rtdp-pubsub-push-sa` to every push request. Cloud Run validates the token
before routing the request to the worker container.

## End-to-end validation evidence

```bash
EVENT_ID="pubsub-e2e-test-$(date +%Y%m%d%H%M%S)" && \
EVENT_JSON="{\"schema_version\":\"1.0\",\"event_id\":\"${EVENT_ID}\",\"symbol\":\"ETHUSDT\",\"event_type\":\"trade\",\"price\":\"3200.00\",\"quantity\":\"0.10\",\"event_timestamp\":\"2026-05-04T09:05:00+00:00\"}" && \
echo "Publishing event_id=${EVENT_ID}" && \
gcloud pubsub topics publish market-events-raw \
  --message="${EVENT_JSON}" && \
sleep 10 && \
curl -s "https://rtdp-api-892892382088.europe-west1.run.app/events?limit=5" && \
echo
```

```text
Publishing event_id=pubsub-e2e-test-20260504213833
messageIds:
- '19533913978763804'
[{"event_id":"pubsub-e2e-test-20260504213833","symbol":"ETHUSDT","event_type":"trade","price":3200.0,"quantity":0.1,"event_timestamp":"2026-05-04T09:05:00Z","ingested_at":"2026-05-04T20:38:39.151222Z","source_topic":"market-events-raw"},{"event_id":"cloud-worker-test-20260504090458","symbol":"BTCUSDT","event_type":"trade","price":67500.0,"quantity":0.01,"event_timestamp":"2026-05-04T06:30:00Z","ingested_at":"2026-05-04T08:05:00.233750Z","source_topic":"market-events-raw"}]
```

The event `pubsub-e2e-test-20260504213833` was persisted with
`ingested_at: 2026-05-04T20:38:39.151222Z`, approximately 6 seconds after the event
timestamp encoded in the test ID. The API readback was executed after a 10-second wait
to allow Pub/Sub push delivery.

## Cost-control final state

Cloud SQL was started only for the validation window and stopped immediately after.

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER && \
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"
```

```text
NEVER   STOPPED
```

## What this proves

- The Cloud Run worker (`rtdp-pubsub-worker`) is deployed with an HTTPS endpoint and protected by OIDC-authenticated invocation.
- The Pub/Sub push subscription (`market-events-raw-worker-push`) is wired to the worker `/pubsub/push` endpoint with the correct push service account.
- A message published to the `market-events-raw` topic is automatically delivered to the worker without manual intervention.
- The worker decodes the Pub/Sub envelope, validates the `MarketEvent` contract, and writes the record into Cloud SQL `bronze.market_events`.
- The Cloud Run API (`rtdp-api`) serves the persisted event correctly via `/events`.
- The full managed GCP stack — Pub/Sub, Cloud Run (worker + API), Cloud SQL, Secret Manager, IAM, Artifact Registry — works together end-to-end.

## What this does not prove yet

- No high-throughput benchmark: only a single event was published per test run.
- No production-scale load handling: worker concurrency and Cloud SQL connection limits are untested under load.
- No Cloud Monitoring dashboard: no alerting, latency metrics, or error-rate tracking is configured.
- No DLQ validation: dead-letter queue behaviour on malformed or rejected messages has not been tested.
- No BigQuery or Dataflow integration: the GCP path does not yet include managed analytical processing, and silver/gold refresh automation is not implemented.
- No automated CI/CD deployment: worker and API images are built and pushed manually.
- No continuous silver/gold refresh automation: downstream aggregation is out of scope for this milestone.

## Honest architecture claim

> Validated GCP real-time ingestion MVP using Pub/Sub, Cloud Run worker, Cloud SQL PostgreSQL, Secret Manager, IAM, Artifact Registry, Docker, FastAPI, and Pydantic event contracts.

Do not claim:

- production-scale streaming platform
- fully managed analytics platform
- BigQuery/Dataflow pipeline
- high-throughput event-processing system

## Recruiter-facing summary

The project demonstrates a working GCP real-time ingestion MVP. A market event published
to a Pub/Sub topic is automatically routed through a push subscription to a Cloud Run
worker, validated against a Pydantic contract, and persisted into Cloud SQL PostgreSQL.
The same event is then readable via a Cloud Run API. All infrastructure runs on managed
GCP services with OIDC-authenticated service accounts and Secret Manager for credentials.
This is an MVP proving the end-to-end path — not a production-scale or analytics platform.
