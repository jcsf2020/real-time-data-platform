# Worker Structured Logs Validation

## Status

Validated on: 2026-05-05

The worker structured logs gap documented in [docs/cloud-observability-evidence.md](cloud-observability-evidence.md) is now closed. Revision `rtdp-pubsub-worker-00003-dh6` emits structured `jsonPayload` application logs to Cloud Logging.

---

## Validation Objective

Prove that the redeployed `rtdp-pubsub-worker` Cloud Run service, built from the current branch, emits structured JSON application logs (`jsonPayload`) to Cloud Logging when processing a real Pub/Sub message end-to-end.

---

## Previous Known Gap

`docs/cloud-observability-evidence.md` documented that the Cloud Logging query:

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.service="rtdp-pubsub-worker"
```

returned `[]` for the previously deployed revision `rtdp-pubsub-worker-00002-xp7`. The likely cause was that revision predating the structured logging code added to the worker. The fix was to rebuild and redeploy from the current branch.

---

## Validated Path

```text
Pub/Sub topic market-events-raw
  -> Cloud Run worker rtdp-pubsub-worker
    -> process_message()
      -> structured JSON stdout
        -> Cloud Logging jsonPayload
```

---

## Resources Validated

| Resource | Identifier |
|---|---|
| Cloud Run service | `rtdp-pubsub-worker` |
| Revision | `rtdp-pubsub-worker-00003-dh6` |
| Region | `europe-west1` |
| Pub/Sub topic | `market-events-raw` |
| Cloud SQL instance | `project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres` |
| Artifact Registry image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker` |
| Service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |

---

## Pre-Checks Before Redeploy

| Check | Result |
|---|---|
| Branch | `feat/redeploy-worker-structured-logs` |
| Test suite | 75 passed |
| Ruff | All checks passed |
| Cloud SQL | Never stopped — was already `NEVER / STOPPED` before this session |
| Previous revision | `rtdp-pubsub-worker-00002-xp7` |
| Previous service URL | `https://rtdp-pubsub-worker-fpy4of3i5a-ew.a.run.app` |

---

## Image Build and Artifact Registry Evidence

### Build command

```bash
docker buildx build \
  --platform linux/amd64 \
  -f apps/pubsub-worker/Dockerfile \
  -t europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest \
  --push \
  .
```

### Digest confirmed in Artifact Registry

| Field | Value |
|---|---|
| Image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker` |
| Tag | `latest` |
| Digest | `sha256:74a541abe379c94b2c6eaba8b69ba79a2866f9c49a269b7cc0280e91fcda1413` |

Build and push succeeded. Artifact Registry confirmed the `latest` tag resolves to the digest above.

---

## Redeploy Evidence

### Deploy command

```bash
gcloud run deploy rtdp-pubsub-worker \
  --image=europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --service-account=rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --set-secrets=DATABASE_URL=rtdp-database-url:latest \
  --add-cloudsql-instances=project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres \
  --no-allow-unauthenticated \
  --min-instances=0 \
  --max-instances=1 \
  --concurrency=1 \
  --timeout=60s \
  --port=8080
```

### Deploy output

```
Service [rtdp-pubsub-worker] revision [rtdp-pubsub-worker-00003-dh6] has been deployed
and is serving 100 percent of traffic.
Service URL: https://rtdp-pubsub-worker-892892382088.europe-west1.run.app
```

---

## Runtime Config Evidence

Confirmed from `gcloud run services describe rtdp-pubsub-worker`:

| Config | Value |
|---|---|
| `latestReadyRevisionName` | `rtdp-pubsub-worker-00003-dh6` |
| `status.url` | `https://rtdp-pubsub-worker-fpy4of3i5a-ew.a.run.app` |
| Image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest` |
| `serviceAccountName` | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| `DATABASE_URL` source | Secret Manager — `secretKeyRef.name: rtdp-database-url`, `key: latest` |
| Cloud SQL connector | `run.googleapis.com/cloudsql-instances: project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres` |
| `maxScale` | `1` |

---

## Pub/Sub Processing Evidence

### Command

```bash
EVENT_ID="worker-structured-log-test-$(date +%Y%m%d%H%M%S)" && \
EVENT_JSON="{\"schema_version\":\"1.0\",\"event_id\":\"${EVENT_ID}\",\"symbol\":\"SOLUSDT\",\"event_type\":\"trade\",\"price\":\"145.50\",\"quantity\":\"2.00\",\"event_timestamp\":\"2026-05-05T06:30:00+00:00\"}" && \
echo "Publishing event_id=${EVENT_ID}" && \
gcloud pubsub topics publish market-events-raw \
  --message="${EVENT_JSON}" && \
sleep 10 && \
curl -s "https://rtdp-api-892892382088.europe-west1.run.app/events?limit=5" && \
echo
```

### Output

```
Publishing event_id=worker-structured-log-test-20260505112347
messageIds:
- '18800294059119771'
```

### API `/events` response (trimmed to relevant entry)

```json
[
  {
    "event_id": "worker-structured-log-test-20260505112347",
    "symbol": "SOLUSDT",
    "event_type": "trade",
    "price": 145.5,
    "quantity": 2.0,
    "event_timestamp": "2026-05-05T06:30:00Z",
    "ingested_at": "2026-05-05T10:23:49.450653Z",
    "source_topic": "market-events-raw"
  }
]
```

The event published to `market-events-raw` was received by the worker, validated against the `MarketEvent` schema, persisted to `bronze.market_events`, and is returned by the API — confirming the full Pub/Sub → worker → Cloud SQL → API path after redeploy.

---

## Structured Log Evidence

### Cloud Logging query

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" resource.labels.service_name="rtdp-pubsub-worker" jsonPayload.service="rtdp-pubsub-worker"' \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=10 \
  --format=json
```

### Result

```json
[
  {
    "jsonPayload": {
      "component": "pubsub-worker",
      "event_id": "worker-structured-log-test-20260505112347",
      "operation": "process_message",
      "processing_time_ms": 295.135,
      "service": "rtdp-pubsub-worker",
      "source_topic": "market-events-raw",
      "status": "ok",
      "symbol": "SOLUSDT",
      "timestamp_utc": "2026-05-05T10:23:49.563769+00:00"
    },
    "logName": "projects/project-42987e01-2123-446b-ac7/logs/run.googleapis.com%2Fstdout",
    "resource": {
      "labels": {
        "revision_name": "rtdp-pubsub-worker-00003-dh6",
        "service_name": "rtdp-pubsub-worker",
        "location": "europe-west1",
        "project_id": "project-42987e01-2123-446b-ac7"
      },
      "type": "cloud_run_revision"
    },
    "timestamp": "2026-05-05T10:23:49.563032Z"
  }
]
```

Cloud Run received the structured JSON written to stdout and automatically parsed it into `jsonPayload`. No log agent or sidecar was required. The `jsonPayload` fields (`event_id`, `symbol`, `status`, `processing_time_ms`, `source_topic`, `operation`) are individually queryable in Cloud Logging — this is parsed structured logging, not plain text.

The query that previously returned `[]` for revision `rtdp-pubsub-worker-00002-xp7` now returns a populated log entry for revision `rtdp-pubsub-worker-00003-dh6`.

---

## Cost-Control Final State

Cloud SQL was started only for the duration of this validation.

### Stop command

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER && \
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"
```

### Output

```
NEVER   STOPPED
```

Cloud SQL is stopped and will not incur compute charges.

---

## What This Proves

- Worker structured JSON logs are now observable in Cloud Logging via `jsonPayload`.
- The fields `event_id`, `symbol`, `status`, `processing_time_ms`, and `source_topic` are individually queryable in Cloud Logging.
- Redeployed revision `rtdp-pubsub-worker-00003-dh6` processed the test event end-to-end.
- The Pub/Sub → worker → Cloud SQL → API path still works correctly after the redeploy.
- Cloud SQL was stopped immediately after validation; final state is `NEVER / STOPPED`.

---

## What This Does Not Prove Yet

- Logs-based metrics (no metrics configured or validated).
- Alerting policies (none configured).
- Grafana dashboard (not configured).
- Cloud Monitoring dashboard (not configured).
- High-throughput logging volume (single test message only).
- Failed-message log path (only the `status: ok` path was exercised).

---

## Honest Architecture Claim

> Cloud worker structured application logs validated in Cloud Logging.

Do not claim logs-based metrics or alerting until they are configured and validated.

---

## Next Recommended Branch

**`docs/cloud-observability-metrics-plan`**

Objective: design logs-based metrics and alerting for:

- Worker `status=error` events
- Silver refresh job `status=error` events
- Job execution missing or failure
- `processing_time_ms` latency thresholds
