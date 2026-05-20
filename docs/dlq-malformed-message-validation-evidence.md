# DLQ Malformed-Message Validation -- Execution Evidence

**Status:** VALIDATED WITH OBSERVED CAVEAT -- malformed payload reached DLQ; multiple DLQ entries were observed for the same test_marker; final safe state restored/preserved.
**Date:** 2026-05-20
**Branch:** `exec/dlq-malformed-message-validation`
**Plan:** [docs/dlq-malformed-message-validation-plan.md](dlq-malformed-message-validation-plan.md)

---

## Executive Summary

A single malformed message was published to `market-events-raw`. The worker rejected
it repeatedly (operation=process_message, status=error). After exceeding
`maxDeliveryAttempts=5`, the Pub/Sub dead-letter policy forwarded the message to
`market-events-raw-dlq`. The DLQ readback confirmed the malformed payload reached the
dead-letter topic with correct attributes.

**Planned expectation:** one malformed message -> one DLQ entry after 5 delivery
attempts. **Actual observed:** multiple DLQ entries were returned for the same
`test_marker` across successive pulls. Observed `CloudPubSubDeadLetterSourceDeliveryCount`
values spanned 5 through 16 inclusive. This is consistent with Pub/Sub's at-least-once
delivery guarantee applying to dead-letter forwarding as well as source delivery -- it is
NOT consistent with exactly-once DLQ semantics and is not claimed as such.

The initial ack cleanup attempted by the assistant failed because the installed `gcloud`
version does not support `--ack-ids-file`. A script incorrectly printed `ACK_DONE=true`
despite the failure. This is documented accurately and not hidden.

Final cleanup was performed by draining the temporary pull subscription via `--auto-ack`
pulls and then deleting the subscription. Cloud SQL remained NEVER/STOPPED throughout.
Schedulers remained PAUSED throughout. Terraform apply was not run.

---

## Test Parameters

| Parameter | Value |
|---|---|
| RUN_TS | 20260520165636 |
| TEST_MARKER | dlq-malformed-20260520165636 |
| PAYLOAD_SHA256 | ac2f9c60edbf039b514a389c5345bf44ef30f9629b13fd48659389631243221c |
| Payload (decoded) | `{"test_marker":"dlq-malformed-20260520165636","invalid":true}` |
| Published message ID | 19574066311340908 |
| Source topic | market-events-raw |
| Source subscription | market-events-raw-worker-push |
| DLQ topic | market-events-raw-dlq |
| Temp pull subscription | market-events-raw-dlq-validation-pull (DELETED) |
| DLQ topic publish time | 2026-05-20T16:56:38.873+00:00 |

No secrets were printed at any point.

---

## Preflight State (Observed Before Test)

- Cloud SQL `rtdp-postgres`: STOPPED / NEVER
- Schedulers: PAUSED
- Pub/Sub topic `market-events-raw`: exists
- DLQ topic `market-events-raw-dlq`: exists
- Push subscription `market-events-raw-worker-push`: ACTIVE
- `deadLetterPolicy`: present; DLQ topic = `market-events-raw-dlq`
- `maxDeliveryAttempts`: 5
- `retryPolicy.minimumBackoff`: 10s
- `retryPolicy.maximumBackoff`: 60s
- Worker `rtdp-pubsub-worker`: Ready
- pytest: 241 passed
- ruff: clean
- terraform fmt: clean
- terraform validate: success
- terraform plan: PLAN_EXIT=0

---

## Temporary Subscription

Created before test:

```
market-events-raw-dlq-validation-pull
  topic: market-events-raw-dlq
  ackDeadlineSeconds: 60
  expirationPolicy.ttl: 86400s
  state: ACTIVE
```

Initial baseline pull returned 0 messages as expected.

---

## Malformed Publish

One message published to `market-events-raw`:

```
Publish output message ID: 19574066311340908
```

---

## Worker Error Logs

Worker logs showed repeated failures:

```
operation=process_message  status=error
```

Errors repeated as Pub/Sub retried delivery with backoff (10s min, 60s max).

---

## DLQ Readback -- Observed Behaviour

### DLQ message attributes (consistent across all pulled messages)

| Attribute | Value |
|---|---|
| CloudPubSubDeadLetterSourceSubscription | market-events-raw-worker-push |
| CloudPubSubDeadLetterSourceSubscriptionProject | project-42987e01-2123-446b-ac7 |
| CloudPubSubDeadLetterSourceTopicPublishTime | 2026-05-20T16:56:38.873+00:00 |
| purpose | dlq-malformed-validation |
| test_marker | dlq-malformed-20260520165636 |

### Observed delivery counts

Across all DLQ pulls (initial + cleanup pulls), the following
`CloudPubSubDeadLetterSourceDeliveryCount` values were observed:

```
5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
```

Each was a distinct DLQ message entry for the same original malformed publish.

### Explanation

Pub/Sub dead-letter forwarding is itself at-least-once. After `maxDeliveryAttempts=5`,
the service forwards a copy to the DLQ topic on each subsequent delivery attempt. This
produces multiple DLQ entries per original message. This behaviour is compatible with
Pub/Sub's at-least-once delivery model but means:

- DLQ entry count does NOT equal original message count.
- Deduplication by `test_marker` or payload hash is required for poison-message
  analysis.
- Exactly-once DLQ routing is NOT claimed.
- Production-grade poison-message handling (idempotent DLQ consumers) is NOT claimed.

---

## Cleanup Failures -- Accurately Documented

### Failed ack attempt

The assistant attempted:

```
gcloud pubsub subscriptions ack \
  --ack-ids-file=/tmp/dlq-ack-ids.txt \
  projects/.../subscriptions/market-events-raw-dlq-validation-pull
```

This failed with:

```
ERROR: (gcloud.pubsub.subscriptions.ack) unrecognized arguments:
  --ack-ids-file=/tmp/dlq-ack-ids.txt (did you mean '--ack-ids'?)
```

The installed `gcloud` version does not support `--ack-ids-file`. The ack did NOT
complete. A script in the session incorrectly printed `ACK_DONE=true` despite the
failure. This is documented here and not hidden.

### After failed ack

A subsequent pull returned `DLQ_AFTER_ACK_PULL_COUNT=4` -- confirming messages remained
unacked/redeliverable.

---

## Final Cleanup

Three `--auto-ack` pulls were performed to drain the subscription:

- Pull 1: 1 message (delivery count 10) -- acked
- Pull 2: 11 messages (delivery counts 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16) -- all acked
- Pull 3: 0 messages -- subscription confirmed empty

Subscription deleted:

```
gcloud pubsub subscriptions delete market-events-raw-dlq-validation-pull \
  --project=project-42987e01-2123-446b-ac7 --quiet
```

Output:

```
Deleted subscription [projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-dlq-validation-pull].
```

---

## Final Safe State

| Resource | State |
|---|---|
| Cloud SQL `rtdp-postgres` | STOPPED / NEVER |
| Cloud Scheduler jobs | PAUSED (both jobs) |
| Temp subscription `market-events-raw-dlq-validation-pull` | DELETED |
| `market-events-raw-dlq` topic | intact (not modified) |
| `market-events-raw-worker-push` subscription | intact (not modified) |
| Terraform apply | NOT run |
| Secrets printed | NONE |

---

## Validation Results

```
git diff --check          clean
uv run pytest -q          241 passed
uv run ruff check .       clean
terraform fmt -check      clean
terraform validate        success
terraform plan            PLAN_EXIT=0
```

---

## What Is Validated

- Malformed payload (`{"test_marker":"...","invalid":true}`) published to
  `market-events-raw` was rejected by the worker and routed to `market-events-raw-dlq`
  via the configured `deadLetterPolicy`.
- DLQ messages carried correct source attributes: subscription, project, publish time,
  custom purpose and test_marker labels.
- Worker error logs appeared as expected for each delivery attempt.
- DLQ topic and production subscription are intact and unmodified.
- Temporary pull subscription was created, used for validation, drained, and deleted.
- Cloud SQL never started.
- Schedulers stayed PAUSED.
- No Terraform apply was performed.
- No secrets were printed.

## What Is NOT Claimed

- Exactly-once DLQ routing (multiple DLQ entries observed for same original message).
- Clean single-message DLQ semantics.
- Production-grade poison-message handling.
- Sustained production throughput.
- Dataflow (not implemented).

---

## Open Caveat -- Requires Later Investigation

Multiple DLQ entries were observed for a single original malformed publish. The
`CloudPubSubDeadLetterSourceDeliveryCount` spanned 5 through 16. This is consistent
with Pub/Sub at-least-once dead-letter forwarding semantics, but any operational DLQ
consumer must deduplicate by payload hash or test_marker. This must be investigated
before any production poison-message handler is built against this DLQ topic.
