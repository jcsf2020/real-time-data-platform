# Production Pub/Sub Dead-Letter Policy Runbook

## Status

**RUNBOOK ONLY — NOT EXECUTED**

This is an operational runbook. No GCP write operations have been performed on this branch.

| Constraint | State |
|---|---|
| GCP writes performed | **No** |
| Pub/Sub topics created | **No** |
| Pub/Sub subscriptions updated | **No** |
| Pub/Sub messages published | **No** |
| Cloud SQL started | **No** |
| Application code modified | **No** |
| Anything deployed | **No** |

All command blocks below are templates for a future execution branch. Read every command
block as documentation, not as executed evidence.

---

## 1. Purpose

This runbook prepares the safe addition of a production dead-letter policy
(`deadLetterPolicy`) to the existing production Pub/Sub push subscription:

**`market-events-raw-worker-push`**

The current subscription has no `deadLetterPolicy`, no `maxDeliveryAttempts`, and no
`retryPolicy`. As established by the read-only inspection in
[docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md), this means that any
malformed or unprocessable message delivered to the production worker will be retried by
Pub/Sub with default exponential backoff until `messageRetentionDuration` (600 s) expires —
with no bounded teardown path.

**Goals of adding the DLQ policy:**

- Bound failed delivery attempts to a fixed maximum (5 attempts)
- Prevent unbounded retry loops on malformed or unprocessable messages
- Protect worker logs, metrics, and Cloud Monitoring alert policies from repeated error noise
  during transient or permanent processing failures
- Improve production safety by ensuring failed messages are routed to a dead-letter topic
  rather than retried indefinitely

This runbook builds on the completed observability stack:

- All four logs-based metrics have validated Cloud Monitoring timeSeries datapoints
- Cloud Monitoring dashboard (RTDP Pipeline Overview) is created and exported
- Both alert policies are enabled:
  - **RTDP Worker Message Error Alert** — fires on `worker_message_error_count > 0`
  - **RTDP Silver Refresh Error Alert** — fires on `silver_refresh_error_count > 0`

Adding the DLQ policy is the final P0 production safety gap.

---

## 2. Current Production Subscription Baseline

Observed during the read-only inspection on branch `docs/pubsub-retry-dlq-inspection`
(evidence: [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md)).

| Field | Observed value |
|---|---|
| Subscription name | `market-events-raw-worker-push` |
| Topic | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw` |
| Push endpoint | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` |
| Push auth service account | `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| State | `ACTIVE` |
| `ackDeadlineSeconds` | 30 |
| `messageRetentionDuration` | 600s |
| `deadLetterPolicy` | **absent** |
| `maxDeliveryAttempts` | **absent** |
| `retryPolicy` | **absent** |

**Gaps:**

- No dead-letter topic configured — failed messages are not routed anywhere safe
- No `maxDeliveryAttempts` — retry count is unbounded within the 600 s retention window
- No explicit `retryPolicy` — backoff is governed by Pub/Sub defaults, not a configured bound

---

## 3. Proposed Production DLQ Design

### New resource to create

| Resource | Name |
|---|---|
| Dead-letter topic | `market-events-raw-dlq` |

### Subscription update (in-place)

| Field | Proposed value |
|---|---|
| Subscription to update | `market-events-raw-worker-push` |
| `deadLetterPolicy.deadLetterTopic` | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq` |
| `deadLetterPolicy.maxDeliveryAttempts` | **5** |
| `retryPolicy.minimumBackoff` | **10s** |
| `retryPolicy.maximumBackoff` | **60s** |
| Push endpoint | **unchanged** |
| Push auth service account | **unchanged** |

### Rationale for 5 delivery attempts

Five attempts is enough to absorb transient Cloud Run cold-start latency, brief Cloud SQL
connection spikes, or short-lived network hiccups — all of which can cause a single-push
delivery to return HTTP 500 without the message being inherently unprocessable. At the same
time, five attempts is a tight enough bound to prevent 600 s of repeated retry noise against
the live worker when a message is genuinely malformed or unprocessable. Under the proposed
`10s`/`60s` retry policy, five attempts would take at most a few minutes before Pub/Sub
routes the message to the dead-letter topic, at which point the alert policies can detect
the error without continued retries polluting logs or metrics.

### What is not changing

- Push endpoint URL remains `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push`
- OIDC push auth service account remains `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com`
- Topic attachment remains `market-events-raw`
- Subscription is updated in-place — it is not deleted and recreated
- No test malformed messages are published during the DLQ configuration branch

---

## 4. Safety Constraints

The following constraints are absolute for this runbook and any execution branch that follows it:

| Constraint | Rule |
|---|---|
| No malformed messages | Do not publish any message to `market-events-raw` during DLQ configuration |
| No push endpoint change | Push endpoint must remain unchanged after the update |
| No push auth change | OIDC service account must remain unchanged after the update |
| No Cloud SQL start | Cloud SQL `rtdp-postgres` must remain `NEVER / STOPPED` throughout |
| No worker deployment | Do not deploy or redeploy the Cloud Run worker |
| No subscription deletion | Do not delete `market-events-raw-worker-push` |
| No subscription recreation | Update in-place only — do not recreate the subscription |
| Capture before state | Run `gcloud pubsub subscriptions describe` before any update |
| Capture after state | Run `gcloud pubsub subscriptions describe` after the update |
| Rollback documented first | Rollback command must be written and reviewed before the update is run |

---

## 5. Required Pub/Sub Service Agent IAM

Pub/Sub requires the Pub/Sub service agent to have `roles/pubsub.publisher` on the DLQ
topic in order to route failed messages there. Without this binding, the dead-letter policy
will be accepted by the API but failed messages will not be forwarded to the DLQ topic.

**Resolve the project number:**

```bash
PROJECT_NUMBER="$(gcloud projects describe project-42987e01-2123-446b-ac7 \
  --format='value(projectNumber)')"
PUBSUB_SA="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
echo "Pub/Sub service agent: ${PUBSUB_SA}"
```

**Grant publisher role on the DLQ topic:**

```bash
gcloud pubsub topics add-iam-policy-binding market-events-raw-dlq \
  --project=project-42987e01-2123-446b-ac7 \
  --member="serviceAccount:${PUBSUB_SA}" \
  --role="roles/pubsub.publisher"
```

This IAM binding must be applied before the subscription update is run. The binding is on
the DLQ topic, not the source topic — it does not affect `market-events-raw`.

---

## 6. Exact Future Execution Commands

> **Future execution only — do not run on this runbook branch.**
>
> All command blocks are templates for a future execution session. No command below has been
> run. Resolve all placeholders before execution. Stop immediately if any step returns an
> unexpected result — see Section 8 (Stop Conditions).

---

### Step 0 — Pre-execution checks

```bash
# Confirm branch is NOT this runbook branch
git status --short --branch

# Confirm tests pass
uv sync --all-packages
uv run pytest -q

# Confirm ruff clean
uv run ruff check .

# Confirm Cloud SQL is NEVER / STOPPED — must be true before any GCP write
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Expected: NEVER   STOPPED

# Describe production subscription BEFORE any change — capture this output in evidence
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json

# List all topics — confirm no market-events-raw-dlq topic exists yet (or document if it does)
gcloud pubsub topics list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name)"

# List all subscriptions — baseline before change
gcloud pubsub subscriptions list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,topic,pushConfig.pushEndpoint,deadLetterPolicy.deadLetterTopic,deadLetterPolicy.maxDeliveryAttempts)"
```

**Abort if any of the following:**

- Branch is `docs/production-pubsub-dlq-runbook`
- Cloud SQL is not `NEVER   STOPPED`
- Production subscription is not `ACTIVE`
- Production subscription topic is not `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw`
- Push endpoint differs from `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push`
- Push auth service account is missing or unexpected

---

### Step 1 — Create DLQ topic

```bash
gcloud pubsub topics create market-events-raw-dlq \
  --project=project-42987e01-2123-446b-ac7
```

Expected output:

```
Created topic [projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq].
```

If `market-events-raw-dlq` already exists, document that in the evidence and skip this step.
Do not delete and recreate an existing DLQ topic without investigating whether messages are
already present.

---

### Step 2 — Grant Pub/Sub service agent publisher role on DLQ topic

```bash
PROJECT_NUMBER="$(gcloud projects describe project-42987e01-2123-446b-ac7 \
  --format='value(projectNumber)')"
PUBSUB_SA="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

gcloud pubsub topics add-iam-policy-binding market-events-raw-dlq \
  --project=project-42987e01-2123-446b-ac7 \
  --member="serviceAccount:${PUBSUB_SA}" \
  --role="roles/pubsub.publisher"
```

Expected output includes a policy binding block confirming the new member and role.

---

### Step 3 — Update production subscription in-place

> **This is the only write that touches `market-events-raw-worker-push`.** Review the
> rollback command in Section 7 before running this step.

```bash
gcloud pubsub subscriptions update market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --dead-letter-topic=projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq \
  --max-delivery-attempts=5 \
  --min-retry-delay=10s \
  --max-retry-delay=60s
```

Expected output:

```
Updated subscription [projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push].
```

---

### Step 4 — Verify subscription after update

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

The output **must** confirm all of the following before the execution is accepted:

| Field | Required value |
|---|---|
| `topic` | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw` |
| `pushConfig.pushEndpoint` | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` |
| `pushConfig.oidcToken.serviceAccountEmail` | `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| `deadLetterPolicy.deadLetterTopic` | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq` |
| `deadLetterPolicy.maxDeliveryAttempts` | `5` |
| `retryPolicy.minimumBackoff` | `10s` |
| `retryPolicy.maximumBackoff` | `60s` |
| `state` | `ACTIVE` |

If any field is missing, wrong, or the push endpoint or auth has changed — execute the
rollback in Section 7 immediately.

---

### Step 5 — List topics and subscriptions after update

```bash
gcloud pubsub topics list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name)"

gcloud pubsub subscriptions list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,topic,pushConfig.pushEndpoint,deadLetterPolicy.deadLetterTopic,deadLetterPolicy.maxDeliveryAttempts)"
```

Expected: `market-events-raw-dlq` topic appears in the topic list. The subscription list
shows `market-events-raw-worker-push` now has `deadLetterPolicy.deadLetterTopic` and
`maxDeliveryAttempts` populated.

---

### Step 6 — Final Cloud SQL state check

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

This check closes the execution window. Record the output in the evidence document.

---

## 7. Rollback Plan

> **Read and understand this section before running Step 3.**

If the subscription update produces an incorrect state (wrong topic, changed endpoint, wrong
delivery attempts, or any other unexpected result), execute this rollback immediately:

```bash
gcloud pubsub subscriptions update market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --clear-dead-letter-policy \
  --clear-retry-policy
```

Expected output:

```
Updated subscription [projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push].
```

After rollback, verify:

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

The output **must** confirm:

| Field | Required post-rollback value |
|---|---|
| `deadLetterPolicy` | absent |
| `retryPolicy` | absent |
| `topic` | `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw` |
| `pushConfig.pushEndpoint` | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` |
| `state` | `ACTIVE` |

### Whether to delete `market-events-raw-dlq` after rollback

Only delete `market-events-raw-dlq` after rollback if **both** of the following are true:

1. The execution branch explicitly confirms that zero messages were routed to the DLQ topic
   (i.e. the subscription update was rolled back before any failed delivery attempts occurred).
2. The execution branch decides that cleanup is safe and complete.

If there is any uncertainty about whether messages reached the DLQ topic, do not delete it.
Inspect the topic's subscription and any attached pull consumers first.

---

## 8. Evidence to Capture in Future Execution Branch

The future execution evidence document must capture all of the following:

| # | Evidence item |
|---|---|
| 1 | Branch name — must not be `docs/production-pubsub-dlq-runbook` |
| 2 | Pre-execution `git status --short --branch` |
| 3 | Pre-execution `uv run pytest -q` — must pass |
| 4 | Pre-execution `uv run ruff check .` — must be clean |
| 5 | Pre-execution Cloud SQL state — must be `NEVER   STOPPED` |
| 6 | Pre-change production subscription JSON (`gcloud pubsub subscriptions describe ... --format=json`) |
| 7 | Pre-change topic list output |
| 8 | Pre-change subscription list output |
| 9 | Resolved project number and Pub/Sub service agent email |
| 10 | DLQ topic creation output (or note if it already existed) |
| 11 | DLQ IAM binding output |
| 12 | Subscription update command output |
| 13 | Post-change production subscription JSON |
| 14 | Post-change verification table (all fields from Step 4 confirmed) |
| 15 | Post-change topic list output |
| 16 | Post-change subscription list output |
| 17 | Final Cloud SQL state — must be `NEVER   STOPPED` |
| 18 | Final `uv run pytest -q` — must pass |
| 19 | Final `uv run ruff check .` — must be clean |
| 20 | Explicit statement: zero Pub/Sub messages published during execution |
| 21 | Explicit statement: Cloud SQL was not started during execution |
| 22 | Rollback command documented but not executed (unless rollback was triggered) |

---

## 9. Acceptance Criteria

The future execution is accepted only if **all** of the following are true:

| Criterion | Required |
|---|---|
| `market-events-raw-dlq` topic exists | Confirmed in `gcloud pubsub topics list` |
| `market-events-raw-worker-push` topic unchanged | `topic` field is `market-events-raw` |
| Push endpoint unchanged | `pushConfig.pushEndpoint` matches expected URL |
| Push auth service account unchanged | `pushConfig.oidcToken.serviceAccountEmail` matches expected SA |
| `deadLetterPolicy.deadLetterTopic` correct | Points to `market-events-raw-dlq` |
| `maxDeliveryAttempts` correct | `5` |
| `retryPolicy.minimumBackoff` correct | `10s` |
| `retryPolicy.maximumBackoff` correct | `60s` |
| Subscription state | `ACTIVE` |
| Cloud SQL | `NEVER / STOPPED` throughout — never started |
| No Pub/Sub messages published | Zero messages published during this execution window |
| Tests pass | `uv run pytest -q` exits 0 |
| Ruff clean | `uv run ruff check .` exits 0 |
| Evidence document created | `docs/production-pubsub-dlq-evidence.md` committed on the execution branch |

---

## 10. Stop Conditions

Abort immediately and record the stop reason if any of the following are observed:

| Stop condition | Required action |
|---|---|
| Cloud SQL is not `NEVER / STOPPED` before execution | Abort; do not perform any GCP writes; investigate |
| Production subscription is not `ACTIVE` before change | Abort; do not update; investigate |
| Production subscription topic is not `market-events-raw` | Abort; do not update; the baseline has changed |
| Push endpoint differs from expected | Abort; the subscription may have been modified since inspection |
| Push auth service account missing or unexpected | Abort; the subscription may have been modified since inspection |
| DLQ topic creation fails | Abort; do not attempt subscription update |
| Pub/Sub service agent IAM binding fails | Abort; without this binding, the DLQ will not receive failed messages |
| Subscription update command returns an error | Abort; run rollback if the subscription is in an unknown state |
| Post-update `describe` shows wrong `topic` field | Execute rollback immediately |
| Post-update `describe` shows changed push endpoint | Execute rollback immediately |
| Post-update `describe` shows changed push auth service account | Execute rollback immediately |
| Any command would delete or recreate `market-events-raw-worker-push` | Abort; in-place update only |
| Any command would publish messages to `market-events-raw` | Abort; no message publishing on this runbook |

On abort: record the stop condition, the last known Cloud SQL state, and which steps
completed. Do not retry the same run without diagnosing the root cause.

---

## 11. What This Runbook Does Not Do

This runbook does **not**:

- Execute any GCP write commands now
- Publish malformed or test messages to `market-events-raw`
- Test DLQ routing with synthetic error messages in this branch
- Create Cloud Monitoring alert policies (already completed)
- Create notification channels (deferred P1)
- Start Cloud SQL
- Deploy or redeploy the Cloud Run worker
- Add Terraform or IaC management for any GCP resource
- Add Cloud Scheduler for silver refresh
- Validate the 5,000-event load test
- Implement BigQuery or Dataflow integration

---

## 12. Roadmap Position

After this runbook's future execution evidence is accepted and merged, the P0 production DLQ
gap will be closed. The remaining gaps are:

| Gap | Priority | Notes |
|---|---|---|
| Notification channels | P1 | Alert policies exist but have no delivery targets; email or webhook channel needed |
| Cloud Scheduler for silver refresh | P1 | Silver refresh is manually triggered; no recurring scheduler |
| Terraform / IaC | P1 | All GCP resources created imperatively; no Terraform state |
| 5,000-event load test | P1 | 100 and 1,000 tiers accepted; 5,000-tier not executed |
| BigQuery / Dataflow analytical tier | P1 | Silver layer is operational only; analytical tier not implemented |

### Full roadmap summary

| Step | Status | Document |
|---|---|---|
| Logs-based metrics creation | Complete | [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md) |
| Success counter datapoint validation | Complete | [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) |
| Error counter datapoint validation | Complete | [docs/isolated-error-counter-validation-evidence.md](isolated-error-counter-validation-evidence.md), [docs/silver-refresh-error-metric-filter-evidence.md](silver-refresh-error-metric-filter-evidence.md) |
| Cloud Monitoring dashboard | Complete | [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md) |
| Alert policies | Complete | [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) |
| **Production Pub/Sub DLQ** | **This runbook — not yet executed** | Future: `docs/production-pubsub-dlq-evidence.md` |
| Notification channels | P1 gap — not addressed | Future |
| Cloud Scheduler for silver refresh | P1 gap — not addressed | Future |
| Terraform / IaC | P1 gap — not addressed | Future |
| 5,000-event load test | P1 gap — not executed | [docs/load-test-plan.md](load-test-plan.md) |
| BigQuery / Dataflow analytical tier | P1 gap — not implemented | Future |
