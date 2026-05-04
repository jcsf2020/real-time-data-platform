# GCP Worker Deployment Plan

> **STATUS: PLAN — NOT YET EXECUTED**
>
> This document defines the exact steps required to deploy the Pub/Sub worker HTTP runtime to
> Cloud Run and wire it to the `market-events-raw` topic via a push subscription.
> No GCP commands in this document have been run. All command blocks are reference material
> for the execution session only.

---

## Current Implemented State

| Component | State |
|---|---|
| Local Kafka/Redpanda pipeline | Running — unchanged, do not touch |
| Cloud Run API (`rtdp-api`) | Deployed and serving |
| Cloud SQL (`rtdp-postgres`) | Stopped (`activationPolicy=NEVER`, `state=STOPPED`) |
| Secret Manager (`rtdp-database-url`) | Valid DB URL — latest version only |
| Pub/Sub topic (`market-events-raw`) | Exists |
| Existing subscription (`market-events-raw-verify`) | Exists — do not modify |
| Worker core (`rtdp_pubsub_worker`) | Implemented and tested with mock DB |
| Worker HTTP runtime (`rtdp_pubsub_worker.http_app`) | Implemented and tested locally |
| Worker Dockerfile (`apps/pubsub-worker/Dockerfile`) | Local build succeeded |
| Cloud Run worker deployment | **Not yet executed** |
| Pub/Sub push subscription | **Not yet configured** |

---

## Target Runtime Path

```text
Pub/Sub topic: market-events-raw
  → push subscription: market-events-raw-worker-push
    → Cloud Run worker: rtdp-pubsub-worker  POST /pubsub/push
      → MarketEvent contract validation (Pydantic)
        → Cloud SQL: realtime_platform / bronze.market_events  (ON CONFLICT DO NOTHING)
          → Cloud Run API: rtdp-api  GET /events
```

---

## GCP Resource Inventory

### Fixed — already exist

| Resource | Identifier |
|---|---|
| GCP project | `project-42987e01-2123-446b-ac7` |
| GCP project number | `892892382088` |
| Region | `europe-west1` |
| Cloud SQL instance | `rtdp-postgres` |
| Cloud SQL database | `realtime_platform` |
| Cloud Run API | `rtdp-api` |
| Cloud Run API URL | `https://rtdp-api-892892382088.europe-west1.run.app` |
| Pub/Sub topic | `market-events-raw` |
| Secret Manager secret | `rtdp-database-url` (always use `latest` version) |

### New — to be created at execution time

| Resource | Identifier |
|---|---|
| Artifact Registry repo | `rtdp` (create if absent — check in Phase 0) |
| Worker container image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest` |
| Worker service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Push invoker service account | `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Cloud Run worker service | `rtdp-pubsub-worker` (region: `europe-west1`) |
| Pub/Sub push subscription | `market-events-raw-worker-push` |

---

## IAM Minimum Permissions

| Principal | Scope | Role | Purpose |
|---|---|---|---|
| `rtdp-worker-sa` | Project | `roles/cloudsql.client` | Connect to Cloud SQL via the Cloud SQL proxy |
| `rtdp-worker-sa` | Secret `rtdp-database-url` | `roles/secretmanager.secretAccessor` | Read DB URL at container startup |
| `rtdp-pubsub-push-sa` | Cloud Run service `rtdp-pubsub-worker` | `roles/run.invoker` | Authenticate Pub/Sub HTTP push requests |
| `service-892892382088@gcp-sa-pubsub.iam.gserviceaccount.com` | Project | `roles/iam.serviceAccountTokenCreator` | Mint OIDC tokens so Pub/Sub can invoke Cloud Run as `rtdp-pubsub-push-sa` |

No other IAM grants are required.

---

## Deployment Phases

### Phase 0 — Cost and Safety Pre-checks

> **DO NOT RUN YET** — Run these checks at the start of the execution session before anything else.

Verify Cloud SQL is stopped. If the output is not `NEVER  STOPPED`, abort and do not proceed.

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Expected: NEVER  STOPPED
```

Verify the Pub/Sub topic exists:

```bash
gcloud pubsub topics describe market-events-raw \
  --project=project-42987e01-2123-446b-ac7
```

List existing subscriptions to confirm `market-events-raw-worker-push` does not already exist:

```bash
gcloud pubsub subscriptions list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(name)"
```

Check whether the Artifact Registry repository already exists:

```bash
gcloud artifacts repositories describe rtdp \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
# NOT_FOUND → create it in Phase 1.
# FOUND → skip the create step in Phase 1.
```

---

### Phase 1 — Build and Push Worker Container

> **DO NOT RUN YET** — Run from the repository root. Cloud SQL does not need to be started.

Create the Artifact Registry repository only if Phase 0 reported NOT_FOUND:

```bash
gcloud artifacts repositories create rtdp \
  --repository-format=docker \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

Authenticate Docker with Artifact Registry:

```bash
gcloud auth configure-docker europe-west1-docker.pkg.dev
```

Build the worker image. The workspace root is required as the Docker build context:

```bash
docker build \
  -f apps/pubsub-worker/Dockerfile \
  -t europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest \
  .
```

Push the image:

```bash
docker push \
  europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-pubsub-worker:latest
```

Verify the image is available:

```bash
gcloud artifacts docker images list \
  europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp \
  --project=project-42987e01-2123-446b-ac7
```

---

### Phase 2 — Deploy Cloud Run Worker Service

> **DO NOT RUN YET** — Cloud SQL must remain stopped. The worker's `GET /health` liveness probe
> does not open a database connection, so Cloud Run deployment succeeds without Cloud SQL running.

Create the worker service account:

```bash
gcloud iam service-accounts create rtdp-worker-sa \
  --display-name="RTDP PubSub Worker" \
  --project=project-42987e01-2123-446b-ac7
```

Grant Cloud SQL client access:

```bash
gcloud projects add-iam-policy-binding project-42987e01-2123-446b-ac7 \
  --member="serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

Grant Secret Manager accessor on the database URL secret:

```bash
gcloud secrets add-iam-policy-binding rtdp-database-url \
  --project=project-42987e01-2123-446b-ac7 \
  --member="serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

Deploy the Cloud Run worker service:

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

`--no-allow-unauthenticated`: Pub/Sub will authenticate using OIDC in Phase 3.  
`--min-instances=0`: scales to zero when idle — no standing cost.  
`--max-instances=1`: prevents runaway scaling during initial validation.  
`--add-cloudsql-instances`: enables the Cloud SQL proxy sidecar required for Unix socket DB connections.

Retrieve and record the worker URL. This value is required in Phases 3 and 4:

```bash
gcloud run services describe rtdp-pubsub-worker \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(status.url)"
# Save this as WORKER_URL.
```

Confirm the liveness endpoint responds (Cloud SQL does not need to be running for this check):

```bash
curl -s "${WORKER_URL}/health" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
# Expected: {"status": "ok"}  HTTP 200
```

---

### Phase 3 — Configure Pub/Sub Push Subscription

> **DO NOT RUN YET** — Requires `WORKER_URL` from Phase 2. Cloud SQL still does not need to be started.

Create the Pub/Sub push invoker service account:

```bash
gcloud iam service-accounts create rtdp-pubsub-push-sa \
  --display-name="RTDP PubSub Push Invoker" \
  --project=project-42987e01-2123-446b-ac7
```

Grant the push service account permission to invoke the Cloud Run worker:

```bash
gcloud run services add-iam-policy-binding rtdp-pubsub-worker \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --member="serviceAccount:rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

Grant the Pub/Sub service agent permission to mint OIDC tokens on behalf of `rtdp-pubsub-push-sa`:

```bash
gcloud projects add-iam-policy-binding project-42987e01-2123-446b-ac7 \
  --member="serviceAccount:service-892892382088@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

Create the push subscription. Replace `WORKER_URL` with the value recorded in Phase 2:

```bash
gcloud pubsub subscriptions create market-events-raw-worker-push \
  --topic=market-events-raw \
  --project=project-42987e01-2123-446b-ac7 \
  --push-endpoint="${WORKER_URL}/pubsub/push" \
  --push-auth-service-account=rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --ack-deadline=30 \
  --message-retention-duration=10m
```

`--message-retention-duration=10m`: undelivered messages expire quickly — limits cost during validation.  
`--ack-deadline=30`: worker has 30 seconds to return 2xx before Pub/Sub retries.

---

### Phase 4 — Validate with One Event

> **DO NOT RUN YET** — This is the only phase that requires Cloud SQL to be started.
> Start it immediately before testing and stop it in Phase 5 before ending the session.

**Step 4a — Start Cloud SQL:**

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS \
  --project=project-42987e01-2123-446b-ac7
```

Wait for Cloud SQL to reach `RUNNABLE` (approximately 60–90 seconds):

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Wait until output is: ALWAYS  RUNNABLE
```

**Step 4b — Send one event directly to the worker endpoint:**

This bypasses Pub/Sub and tests the worker's HTTP interface in isolation.

```bash
WORKER_URL=<URL from Phase 2>
TOKEN=$(gcloud auth print-identity-token)

EVENT_JSON='{"schema_version":"1.0","event_id":"deploy-test-20260504","symbol":"BTCUSDT","event_type":"trade","price":"67500","quantity":"0.01","event_timestamp":"2026-05-04T09:00:00+00:00"}'
EVENT_B64=$(printf '%s' "$EVENT_JSON" | base64)

curl -s -w "\nHTTP %{http_code}\n" \
  -X POST "${WORKER_URL}/pubsub/push" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"message\":{\"data\":\"${EVENT_B64}\",\"messageId\":\"deploy-test-1\",\"publishTime\":\"2026-05-04T09:00:00Z\"},\"subscription\":\"projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push\"}"
# Expected: {"status":"ok","event_id":"deploy-test-20260504"}  HTTP 200
```

**Step 4c — Confirm via the Cloud Run API:**

```bash
curl -s 'https://rtdp-api-892892382088.europe-west1.run.app/events?limit=5'
# Expected: JSON array containing event_id "deploy-test-20260504"
```

**Step 4d — Publish one event via Pub/Sub and verify end-to-end:**

Use a distinct `event_id` to confirm a new write (not an idempotent no-op).

```bash
PUBSUB_EVENT='{"schema_version":"1.0","event_id":"pubsub-e2e-test-20260504","symbol":"ETHUSDT","event_type":"trade","price":"3200","quantity":"0.1","event_timestamp":"2026-05-04T09:05:00+00:00"}'

gcloud pubsub topics publish market-events-raw \
  --project=project-42987e01-2123-446b-ac7 \
  --message="${PUBSUB_EVENT}"
```

Wait 10–15 seconds for Pub/Sub push delivery, then confirm end-to-end:

```bash
curl -s 'https://rtdp-api-892892382088.europe-west1.run.app/events?limit=5'
# Expected: event_id "pubsub-e2e-test-20260504" appears in the response
```

---

### Phase 5 — Stop Cloud SQL

> **DO NOT RUN YET** — Run immediately after Phase 4, whether validation succeeded or failed.
> Cloud SQL accrues cost for every minute it remains in `RUNNABLE` state.

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER \
  --project=project-42987e01-2123-446b-ac7
```

Verify final state before ending the session:

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required output: NEVER  STOPPED
```

Do not close the terminal or end the session until this output is confirmed.

---

## Cost-Control Rules

1. Cloud SQL must be in `NEVER / STOPPED` state at all times except during the Phase 4 validation window.
2. Cloud Run worker uses `--min-instances=0` — no cost when idle (scales to zero between events).
3. Cloud Run worker uses `--max-instances=1` — prevents runaway scaling during initial validation.
4. Push subscription `--message-retention-duration=10m` — undelivered messages expire quickly.
5. Verify Cloud SQL state at the start and end of every session that involves Cloud SQL.
6. Artifact Registry image storage is negligible — no cost action needed.
7. Pub/Sub push at validation scale (a handful of messages) costs cents or less.

---

## Rollback Plan

If the deployment must be reversed after execution:

Delete the push subscription:

```bash
gcloud pubsub subscriptions delete market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7
```

Delete the Cloud Run worker service:

```bash
gcloud run services delete rtdp-pubsub-worker \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

Delete the service accounts:

```bash
gcloud iam service-accounts delete \
  rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --project=project-42987e01-2123-446b-ac7

gcloud iam service-accounts delete \
  rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --project=project-42987e01-2123-446b-ac7
```

The container image in Artifact Registry can remain — storage cost is negligible.

The project-level `roles/iam.serviceAccountTokenCreator` grant on the Pub/Sub service agent is not
automatically removed when service accounts are deleted. Revoke it separately if required:

```bash
gcloud projects remove-iam-policy-binding project-42987e01-2123-446b-ac7 \
  --member="serviceAccount:service-892892382088@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

The `market-events-raw` topic and the `market-events-raw-verify` subscription are unchanged
in all rollback scenarios.

Confirm Cloud SQL is stopped after rollback:

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required: NEVER  STOPPED
```

---

## Acceptance Criteria

All of the following must be true before the deployment is considered complete:

- [ ] Phase 0: Cloud SQL describes as `NEVER  STOPPED` before any work begins
- [ ] Phase 1: Image appears in `gcloud artifacts docker images list`
- [ ] Phase 2: `gcloud run services describe rtdp-pubsub-worker` returns a URL
- [ ] Phase 2: `GET /health` on the worker URL returns HTTP 200 `{"status": "ok"}`
- [ ] Phase 3: `gcloud pubsub subscriptions describe market-events-raw-worker-push` shows the correct push endpoint
- [ ] Phase 4b: Direct `POST /pubsub/push` returns HTTP 200
- [ ] Phase 4c: `GET /events` on the Cloud Run API returns `event_id=deploy-test-20260504`
- [ ] Phase 4d: `gcloud pubsub topics publish` followed by `GET /events` returns `event_id=pubsub-e2e-test-20260504`
- [ ] Phase 5: Cloud SQL describes as `NEVER  STOPPED` after the session ends

---

## Out of Scope

The following are explicitly excluded from this deployment plan:

- BigQuery export or Dataflow pipeline
- Cloud Monitoring dashboards or alerting policies
- Kubernetes or VPC networking changes
- Cloud Scheduler for recurring event publishing
- Autoscaling configuration beyond `--max-instances=1`
- Dead-letter topic for the push subscription
- `gold` schema population
- `silver` auto-refresh automation
- `ai.market_event_embeddings` population
- Terraform or any infrastructure-as-code tooling
- Any change to application source code
- Any change to the local Kafka/Redpanda pipeline
- Modification of the `market-events-raw-verify` subscription
- CI/CD pipeline for automated worker redeployment

---

## Documented vs Executed — Honest State

As of this document's creation (2026-05-04):

| Item | State |
|---|---|
| Worker core decode/validate/insert logic | Implemented and tested with mock DB |
| Worker HTTP runtime (`/health`, `POST /pubsub/push`) | Implemented and tested locally |
| Worker Dockerfile | Built locally — image not yet in Artifact Registry |
| Cloud SQL write path validation (manual JSON, direct worker) | Executed — see `docs/gcp-worker-cloud-validation.md` |
| Artifact Registry image push | **Not yet executed** |
| Cloud Run worker service deployment | **Not yet executed** |
| IAM bindings (worker SA, push SA, Pub/Sub service agent) | **Not yet executed** |
| Pub/Sub push subscription (`market-events-raw-worker-push`) | **Not yet configured** |
| End-to-end Pub/Sub → Cloud Run worker → Cloud SQL → API validation | **Not yet executed** |
