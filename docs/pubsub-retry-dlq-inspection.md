# Pub/Sub Retry and DLQ Inspection

## Status

| Field | Value |
|---|---|
| State | READ-ONLY INSPECTION — COMPLETED |
| Branch | `docs/pubsub-retry-dlq-inspection` |
| Date | 2026-05-05 |
| Tests | 75 passed |
| Ruff | All checks passed |
| Cloud SQL | NEVER STOPPED |
| GCP writes | None |
| Messages published | None |
| Deployments | None |

No messages published, no Cloud SQL start, no deploy, no GCP write commands.

---

## Objective

Before attempting to validate `worker_message_error_count` by sending a synthetic malformed message, the full Pub/Sub retry and dead-letter queue (DLQ) configuration must be known. Sending a malformed message to a subscription with no DLQ/`maxDeliveryAttempts` and a live production push endpoint could cause repeated HTTP 500 errors as Pub/Sub retries indefinitely. This inspection captures the exact observed configuration so that the risk decision is grounded in facts, not assumptions.

---

## Resources Inspected

| Resource type | Name |
|---|---|
| Topic | `market-events-raw` |
| Subscription | `market-events-raw-worker-push` |
| Subscription | `market-events-raw-verify` |
| Cloud Run service | `rtdp-pubsub-worker` |

---

## Topic Inventory

**Command:**

```bash
gcloud pubsub topics list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name)"
```

**Output:**

```
projects/project-42987e01-2123-446b-ac7/topics/market-events-raw
```

Only one topic exists: `market-events-raw`. There is no isolated test topic.

---

## Subscription Inventory

**Command:**

```bash
gcloud pubsub subscriptions list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,topic,pushConfig.pushEndpoint,ackDeadlineSeconds,retryPolicy.minimumBackoff,retryPolicy.maximumBackoff,deadLetterPolicy.deadLetterTopic,deadLetterPolicy.maxDeliveryAttempts)"
```

**Output summary:**

| Field | `market-events-raw-worker-push` | `market-events-raw-verify` |
|---|---|---|
| Topic | `market-events-raw` | `market-events-raw` |
| Push endpoint | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` | _(empty)_ |
| `ackDeadlineSeconds` | 30 | 10 |
| `retryPolicy.minimumBackoff` | _(empty)_ | _(empty)_ |
| `retryPolicy.maximumBackoff` | _(empty)_ | _(empty)_ |
| `deadLetterPolicy.deadLetterTopic` | _(empty)_ | _(empty)_ |
| `deadLetterPolicy.maxDeliveryAttempts` | _(empty)_ | _(empty)_ |

---

## Worker Push Subscription Detail

**Command:**

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

**Output:**

```json
{
  "ackDeadlineSeconds": 30,
  "expirationPolicy": {
    "ttl": "2678400s"
  },
  "messageRetentionDuration": "600s",
  "name": "projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push",
  "pushConfig": {
    "oidcToken": {
      "serviceAccountEmail": "rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com"
    },
    "pushEndpoint": "https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push"
  },
  "state": "ACTIVE",
  "topic": "projects/project-42987e01-2123-446b-ac7/topics/market-events-raw"
}
```

**Interpretation:**

- This is an **ACTIVE** push subscription delivering to the real production worker endpoint.
- Authentication uses OIDC with `rtdp-pubsub-push-sa`.
- There is **no `retryPolicy` field** in the observed JSON — Pub/Sub defaults apply.
- There is **no `deadLetterPolicy` field** in the observed JSON — no DLQ is configured.
- There is **no `maxDeliveryAttempts`** — delivery retries are unbounded by an explicit cap.
- Malformed messages published to this topic would be delivered to the live production worker and retried by Pub/Sub according to default exponential backoff until `messageRetentionDuration` (600 s) expires.

---

## Verify Subscription Detail

**Command:**

```bash
gcloud pubsub subscriptions describe market-events-raw-verify \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

**Output:**

```json
{
  "ackDeadlineSeconds": 10,
  "expirationPolicy": {
    "ttl": "2678400s"
  },
  "messageRetentionDuration": "604800s",
  "name": "projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-verify",
  "pushConfig": {},
  "state": "ACTIVE",
  "topic": "projects/project-42987e01-2123-446b-ac7/topics/market-events-raw"
}
```

**Interpretation:**

- This is a **pull/verify subscription** — no push endpoint is configured.
- It also has **no `retryPolicy`** and **no `deadLetterPolicy`** in the observed JSON.
- It subscribes to the same `market-events-raw` topic as `market-events-raw-worker-push`; it does **not** isolate traffic away from the production worker push subscription — both receive every message published to the topic.

---

## Cloud Run Worker Service Detail

**Command:**

```bash
gcloud run services describe rtdp-pubsub-worker \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(status.latestReadyRevisionName,status.url,spec.template.spec.serviceAccountName)"
```

**Output:**

| Field | Value |
|---|---|
| Latest ready revision | `rtdp-pubsub-worker-00003-dh6` |
| Service URL | `https://rtdp-pubsub-worker-fpy4of3i5a-ew.a.run.app` |
| Service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |

The worker service is deployed and serving. Push messages delivered by `market-events-raw-worker-push` reach this live revision.

---

## Risk Decision

**Do NOT send malformed messages to `market-events-raw` at this stage.**

Reasons:

- The `market-events-raw-worker-push` subscription has an **active push endpoint** pointing to the live production worker (`rtdp-pubsub-worker-00003-dh6`).
- **No `deadLetterPolicy`** is observed — there is no DLQ to absorb failed deliveries.
- **No `maxDeliveryAttempts`** is observed — retry count is unbounded within `messageRetentionDuration`.
- **No `retryPolicy`** is observed — backoff is governed by Pub/Sub defaults, not a configured bound.
- The `market-events-raw-verify` pull subscription **does not isolate traffic** — publishing to the topic reaches both subscriptions simultaneously.
- A malformed message would cause repeated HTTP 500 responses from the worker and continuous Pub/Sub retries for up to 600 s, polluting production metrics and logs without a controlled teardown path.

---

## Safe Next Path

To safely validate `worker_message_error_count` with a single controlled malformed message:

1. **Create an isolated test topic** (e.g., `market-events-raw-test-error`).
2. **Create an isolated dead-letter topic** (e.g., `market-events-raw-test-dlq`).
3. **Create an isolated push subscription** against the test topic with:
   - A bounded `maxDeliveryAttempts` (e.g., 5).
   - A `deadLetterPolicy` pointing at the DLQ topic.
   - A `retryPolicy` with explicit `minimumBackoff` / `maximumBackoff`.
   - OIDC auth — verify that `rtdp-pubsub-push-sa` has `roles/run.invoker` on the worker before pointing at it.
4. **Publish exactly one malformed message** to the isolated test topic.
5. **Validate** Cloud Logging for `status=error` log entries from the worker.
6. **Validate** `worker_message_error_count` datapoint appears in Cloud Monitoring.
7. **Delete** the temporary topic, DLQ topic, and subscription.

---

## Alternative

Running `uv run pytest` locally confirms that the worker code emits the correct error log on malformed input. However, local pytest **does not feed Cloud Logging** and therefore **does not produce a `worker_message_error_count` Cloud Monitoring datapoint**. Local testing validates code correctness; production Cloud Monitoring validation requires a live GCP message flow through the isolated bounded path described above.

---

## What This Proves

- The current production `market-events-raw-worker-push` subscription is **not safe** for malformed-message validation without first establishing an isolated, DLQ-bounded path.
- The full Pub/Sub and DLQ state is now known from observed GCP output — no assumptions were made.
- Cloud SQL was **never stopped** throughout this inspection.
- The error-counter datapoint validation must proceed through the isolated bounded path described in the safe next path.

---

## What This Does Not Prove

- `worker_message_error_count` Cloud Monitoring datapoint — not yet validated.
- `silver_refresh_error_count` Cloud Monitoring datapoint — not yet validated.
- Alerting policy trigger — not yet validated.
- Cloud Monitoring dashboard rendering — not yet validated.
- Grafana integration — not yet validated.

---

## Honest Architecture Claim

> Pub/Sub retry/DLQ configuration inspected; malformed production message validation is intentionally blocked until an isolated bounded path exists.

---

## Next Recommended Branch

**`feat/isolated-worker-error-counter-validation`**

**Objective:** Create temporary isolated Pub/Sub resources (test topic, DLQ topic, bounded push subscription with `maxDeliveryAttempts` and `deadLetterPolicy`) for one controlled malformed message, then validate the `worker_message_error_count` Cloud Monitoring datapoint, and clean up all temporary resources.
