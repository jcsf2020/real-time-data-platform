# Production Pub/Sub DLQ Configuration — Execution Evidence

**Status:** VALIDATED
**Date:** 2026-05-06
**Branch:** `exec/production-pubsub-dlq-validation`
**Runbook:** [docs/production-pubsub-dlq-runbook.md](production-pubsub-dlq-runbook.md)

---

## Executive Summary

The production Pub/Sub dead-letter policy was successfully applied on this branch:

- DLQ topic `market-events-raw-dlq` was created in the project.
- The Pub/Sub service agent (`service-892892382088@gcp-sa-pubsub.iam.gserviceaccount.com`) was granted `roles/pubsub.publisher` on `market-events-raw-dlq`.
- Production subscription `market-events-raw-worker-push` was updated **in-place** — it was not deleted or recreated.
- Topic remained `market-events-raw` — unchanged.
- Push endpoint remained `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` — unchanged.
- Push auth service account remained `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` — unchanged.
- `deadLetterPolicy` now points to `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq`.
- `maxDeliveryAttempts` = **5**.
- `retryPolicy.minimumBackoff` = **10s**.
- `retryPolicy.maximumBackoff` = **60s**.
- Subscription state remained **ACTIVE** throughout.
- Cloud SQL remained **NEVER / STOPPED** — was not started at any point.
- Zero Pub/Sub messages were published during execution.

---

## Pre-Execution Validation

All gates passed before any GCP write:

| Check | Result |
|---|---|
| Branch | `exec/production-pubsub-dlq-validation` |
| `uv sync --all-packages` | Succeeded |
| `uv run pytest -q` | 116 passed, 0 failed |
| `uv run ruff check .` | All checks passed |
| Cloud SQL state | `NEVER / STOPPED` |

### Pre-Change Production Subscription Baseline

| Field | Observed value |
|---|---|
| Subscription name | `market-events-raw-worker-push` |
| Topic | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw` |
| State | `ACTIVE` |
| Push endpoint | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` |
| Push auth service account | `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| `ackDeadlineSeconds` | 30 |
| `messageRetentionDuration` | 600s |
| `deadLetterPolicy` | **absent** |
| `maxDeliveryAttempts` | **absent** |
| `retryPolicy` | **absent** |

`PRODUCTION_SUBSCRIPTION_BASELINE_VALIDATED=true`

---

## GCP Write Evidence

### A. DLQ Topic Creation

**Command output:**

```
Created topic [projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq].
```

**Topic list after creation:**

```
projects/project-42987e01-2123-446b-ac7/topics/market-events-raw
projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq
```

---

### B. Pub/Sub Service Agent IAM

| Field | Value |
|---|---|
| Project number | `892892382088` |
| Pub/Sub service agent | `service-892892382088@gcp-sa-pubsub.iam.gserviceaccount.com` |
| Role granted | `roles/pubsub.publisher` |
| Resource | `market-events-raw-dlq` topic |

**IAM binding command output:**

```
Updated IAM policy for topic [market-events-raw-dlq].
bindings:
- members:
  - serviceAccount:service-892892382088@gcp-sa-pubsub.iam.gserviceaccount.com
  role: roles/pubsub.publisher
etag: BwZRJ4dwyuU=
version: 1
```

---

### C. Production Subscription Update

**Command output:**

```
Updated subscription [projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push].
```

This was an **in-place update** — `market-events-raw-worker-push` was not deleted or recreated. The push endpoint, push auth service account, and topic attachment were not touched by the update command.

---

## Post-Change Validation

### Verification Table

| Field | Required value | Observed value | Pass |
|---|---|---|---|
| Subscription name | `market-events-raw-worker-push` | `market-events-raw-worker-push` | **Yes** |
| Topic | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw` | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw` | **Yes** |
| State | `ACTIVE` | `ACTIVE` | **Yes** |
| Push endpoint | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` | **Yes** |
| Push auth service account | `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | **Yes** |
| `deadLetterTopic` | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq` | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq` | **Yes** |
| `maxDeliveryAttempts` | `5` | `5` | **Yes** |
| `minimumBackoff` | `10s` | `10s` | **Yes** |
| `maximumBackoff` | `60s` | `60s` | **Yes** |
| `ackDeadlineSeconds` | `30` | `30` | **Yes** |
| `messageRetentionDuration` | `600s` | `600s` | **Yes** |

`PRODUCTION_DLQ_VALIDATED=true`

### Raw Post-Change Subscription State

```
name: projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push
topic: projects/project-42987e01-2123-446b-ac7/topics/market-events-raw
state: ACTIVE
pushEndpoint: https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push
pushServiceAccount: rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
deadLetterTopic: projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq
maxDeliveryAttempts: 5
minimumBackoff: 10s
maximumBackoff: 60s
ackDeadlineSeconds: 30
messageRetentionDuration: 600s
```

---

## Final State

### Topics

```
projects/project-42987e01-2123-446b-ac7/topics/market-events-raw
projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq
```

### Subscriptions

```
projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push  projects/project-42987e01-2123-446b-ac7/topics/market-events-raw  ACTIVE
projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-verify       projects/project-42987e01-2123-446b-ac7/topics/market-events-raw  ACTIVE
```

### Cloud SQL

```
NEVER   STOPPED
```

Cloud SQL was **not started** at any point during execution.

---

## What This Proves

The **Production Pub/Sub DLQ / deadLetterPolicy P0 gap is closed**.

Production failed message delivery is now bounded: messages that fail delivery 5 times will be routed to the `market-events-raw-dlq` topic rather than retried indefinitely within the `messageRetentionDuration` window. Combined with the existing alert policies on `worker_message_error_count`, the system now has both a bounded failure path and active alerting on error conditions.

---

## What This Does Not Claim

- Does not test DLQ routing with synthetic malformed messages — no messages were published.
- Does not publish any Pub/Sub messages to `market-events-raw` or any other topic.
- Does not inspect DLQ message contents — the `market-events-raw-dlq` topic was created but has received no messages.
- Does not create notification channels — alert policies remain without delivery targets.
- Does not add Terraform or IaC management for any GCP resource.
- Does not add Cloud Scheduler for silver refresh automation.
- Does not validate the 5,000-event load test tier.
- Does not add BigQuery or Dataflow integration.

---

## Acceptance Matrix

| Criterion | Status |
|---|---|
| DLQ topic `market-events-raw-dlq` exists | **ACCEPTED** |
| Pub/Sub service agent IAM granted (`roles/pubsub.publisher`) | **ACCEPTED** |
| Production subscription updated in-place | **ACCEPTED** |
| Topic unchanged (`market-events-raw`) | **ACCEPTED** |
| Push endpoint unchanged | **ACCEPTED** |
| Push auth service account unchanged | **ACCEPTED** |
| `deadLetterPolicy` set | **ACCEPTED** |
| `maxDeliveryAttempts` = 5 | **ACCEPTED** |
| `retryPolicy` minimumBackoff = 10s | **ACCEPTED** |
| `retryPolicy` maximumBackoff = 60s | **ACCEPTED** |
| Subscription state `ACTIVE` | **ACCEPTED** |
| Cloud SQL `NEVER / STOPPED` throughout | **ACCEPTED** |
| Zero Pub/Sub messages published | **ACCEPTED** |
| 116 tests passed | **ACCEPTED** |
| Ruff clean | **ACCEPTED** |

All criteria met. Evidence status: **VALIDATED**.

---

## Remaining Gaps

| Gap | Priority | Notes |
|---|---|---|
| Notification channels | P1 | Alert policies exist but have no delivery targets; email or webhook channel needed |
| Cloud Scheduler for silver refresh | P1 | Silver refresh is manually triggered; no recurring scheduler |
| Terraform / IaC | P1 | All GCP resources created imperatively; no Terraform state |
| 5,000-event load test | P1 | 100 and 1,000 tiers accepted; 5,000-tier not executed |
| BigQuery / Dataflow analytical tier | P1 | Silver layer is operational only; analytical tier not implemented |
| CI/CD deploy automation | P1/P2 | Deployments are manual; no automated pipeline |
| README stale GCP wording cleanup | P2 | GCP target architecture section wording predates several completed execution branches |
