# Pub/Sub Alert Notification Proof Plan

**Status:** PLAN -- controlled proof plan for Pub/Sub backlog and DLQ alert incident/email delivery
**Date:** 2026-05-25
**Branch:** docs/pubsub-alert-notification-proof-plan

---

## 1. Summary

Three Pub/Sub and DLQ Cloud Monitoring alert policies are implemented, enabled, and attached
to the operator notification channel:

- **RTDP PubSub Worker Oldest Unacked Message Age** -- fires when the oldest unacknowledged
  message on the worker push subscription exceeds 120 seconds.
- **RTDP PubSub Worker Undelivered Messages Backlog** -- fires when the undelivered message
  count on the worker push subscription exceeds 500 for five consecutive minutes.
- **RTDP PubSub DLQ Message Count** -- fires when any message is sent to the DLQ topic.

Policy existence, enablement, and notification channel attachment are validated in
[docs/pubsub-backlog-dlq-alert-policies-evidence.md](pubsub-backlog-dlq-alert-policies-evidence.md).

**What is not yet proven:** Cloud Monitoring incident creation and email notification
delivery for these three specific policies. No synthetic signal has been published, no
policy threshold has been triggered, and no incident has been opened on this branch.
This document defines the controlled approach for proving incident and email delivery in a
future execution branch.

---

## 2. Scope

### In Scope

- Define how to safely prove Cloud Monitoring incident creation for each of the three
  Pub/Sub and DLQ alert policies.
- Define how to capture email notification delivery evidence.
- Define recovery and cleanup requirements after each proof step.
- Define evidence artifacts to collect before closing each gap.

### Out of Scope

The following actions are explicitly excluded from this branch and from any plan described
in this document unless otherwise noted in a separate approved runbook:

- No Terraform apply on this branch.
- No Pub/Sub messages published on this branch.
- No Cloud SQL start on this branch.
- No Cloud Scheduler state change on this branch.
- No production scaling change.
- No Dataflow production streaming change.

---

## 3. Existing Alert Policies

The following three policies are managed in `infra/terraform/gcp/monitoring.tf` and are
currently live in Cloud Monitoring.

| Display Name | Terraform Resource | Trigger Metric | Threshold | Current Evidence |
|---|---|---|---|---|
| RTDP PubSub Worker Oldest Unacked Message Age | `google_monitoring_alert_policy.pubsub_worker_oldest_unacked_message_age` | `pubsub.googleapis.com/subscription/oldest_unacked_message_age` | > 120s for 120s | [pubsub-backlog-dlq-alert-policies-evidence.md](pubsub-backlog-dlq-alert-policies-evidence.md) |
| RTDP PubSub Worker Undelivered Messages Backlog | `google_monitoring_alert_policy.pubsub_worker_num_undelivered_messages` | `pubsub.googleapis.com/subscription/num_undelivered_messages` | > 500 messages for 300s | [pubsub-backlog-dlq-alert-policies-evidence.md](pubsub-backlog-dlq-alert-policies-evidence.md) |
| RTDP PubSub DLQ Message Count | `google_monitoring_alert_policy.pubsub_dlq_message_count` | `pubsub.googleapis.com/topic/send_message_operation_count` | > 0 over 300s | [pubsub-backlog-dlq-alert-policies-evidence.md](pubsub-backlog-dlq-alert-policies-evidence.md) |

All three policies share the operator notification channel:
`projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885`

No new notification channel is required. Channel existence and email type are validated in
[docs/notification-channels-evidence.md](notification-channels-evidence.md).

---

## 4. Recommended Proof Strategy

Proof paths are ranked from safest to highest operational risk.

### Rank 1 (Preferred) -- DLQ Alert Proof

**Why preferred:** The DLQ alert requires the smallest possible signal to trigger: a single
message routed to the DLQ topic. The DLQ policy condition evaluates
`pubsub.googleapis.com/topic/send_message_operation_count` on the DLQ topic. One bounded
synthetic malformed message, routed through the existing DLQ path, is sufficient to satisfy
the threshold (> 0 over 300s).

The DLQ malformed-message routing path is already validated in
[docs/dlq-malformed-message-validation-evidence.md](dlq-malformed-message-validation-evidence.md).
The existing procedure demonstrates that a malformed payload reaches the DLQ. The proof
strategy builds on this validated path.

**Prerequisite:** An isolated DLQ validation procedure must be reviewed and approved before
any execution branch is opened. This ensures cleanup steps are defined before the test
signal is published.

### Rank 2 -- Backlog Alert Proof

**Why deferred:** The backlog alert requires the `num_undelivered_messages` metric to exceed
500 messages for at least 300 seconds. Accumulating 500+ undelivered messages requires
either publishing a sustained burst or making the worker temporarily unavailable. Both
approaches carry higher operational risk than a single DLQ message.

This proof should not be attempted until a safe method is designed and a separate runbook
is approved.

### Rank 3 (Deferred) -- Oldest Unacked Age Proof

**Why deferred:** This alert requires a message to remain unacknowledged for more than 120
consecutive seconds. Triggering this condition without creating uncontrolled retries or
message loss requires careful subscription management. This proof carries the highest
operational risk and should be deferred until both the DLQ and backlog proofs are complete.

---

## 5. Pre-Execution Safety Gates

All of the following conditions must be verified and recorded before any future execution
branch begins:

| Gate | Required State |
|---|---|
| `git status` | Clean -- no uncommitted changes |
| Cloud SQL (`rtdp-postgres`) | STOPPED / activation policy NEVER unless a separate runbook explicitly authorises a start |
| Cloud Scheduler (`rtdp-silver-refresh-scheduler`, `rtdp-bigquery-append-scheduler`) | PAUSED |
| `terraform plan -detailed-exitcode` | PLAN_EXIT=0 (zero diff) |
| Alert policies | Enabled and attached to notification channel (confirmed via `gcloud monitoring policies describe`) |
| Open incidents | No unrelated alert incidents open in Cloud Monitoring |
| Test marker | Unique string defined before any message is published (e.g. `PUBSUBDLQPROOFV1-<YYYYMMDDTHHMMSSZ>`) |
| Cleanup commands | Subscription drain and delete commands prepared and reviewed |
| Evidence directory | Target directory for screenshots and CLI outputs defined |
| Notification inbox | Operator actively monitoring Gmail inbox for the operator email address |

No execution branch should open until every gate above is explicitly confirmed.

---

## 6. Future Execution Plan -- DLQ Alert Proof

This section describes the intended steps for a future branch named
`exec/pubsub-dlq-alert-notification-proof`. These are planning steps, not executable
commands. No step in this section has been executed on this branch.

**Step 1 -- Create a unique test marker.**
Define a test marker string (e.g. `PUBSUBDLQPROOFV1-20260525T000000Z`) that will appear
in the synthetic message payload. The marker allows test-generated data to be distinguished
from any legitimate traffic in Cloud Monitoring logs.

**Step 2 -- Confirm DLQ alert policy exists and is enabled.**
Run `gcloud monitoring policies describe` against the DLQ alert policy ID from
[pubsub-backlog-dlq-alert-policies-evidence.md](pubsub-backlog-dlq-alert-policies-evidence.md)
and record the output. Confirm `enabled: true` and notification channel attached.

**Step 3 -- Confirm notification channel is attached and active.**
Confirm that `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885`
is present in the policy describe output and matches the email channel validated in
[docs/notification-channels-evidence.md](notification-channels-evidence.md).

**Step 4 -- Publish one bounded synthetic malformed payload.**
Using the existing DLQ malformed-message validation procedure (approved and documented in
[docs/dlq-malformed-message-validation-evidence.md](dlq-malformed-message-validation-evidence.md)),
publish exactly one malformed message to the production input topic. The payload must
include the test marker. This step must only proceed if the isolated DLQ validation
procedure has been reviewed and approved for the execution branch.

**Step 5 -- Wait for the policy evaluation window.**
The DLQ policy evaluates `send_message_operation_count` over a 300-second window. Wait
at least 300 seconds after the message reaches the DLQ before checking for an incident.
Record the wait start time.

**Step 6 -- Capture Cloud Monitoring alert incident OPEN state.**
Run `gcloud alpha monitoring incidents list` or equivalent to confirm that an incident has
been opened for the DLQ alert policy. Record the incident ID, incident creation time, and
policy display name.

**Step 7 -- Capture email notification evidence.**
Check the operator Gmail inbox for a notification email from Google Cloud Alerting. Record
the delivery timestamp, subject line, and policy name from the email. Screenshot or
forward the email as evidence.

**Step 8 -- Confirm incident close behaviour.**
After the DLQ metric window clears (no further DLQ traffic), confirm whether the incident
closes automatically. Record the closed state and timestamp if observed. Do not claim
auto-close behaviour if it is not observed.

**Step 9 -- Document all outputs in a new evidence file.**
Create `docs/pubsub-dlq-alert-notification-proof-evidence.md` with:
- test marker value
- policy describe output
- DLQ message publish confirmation (message ID)
- wait window timestamps
- incident ID and OPEN state evidence
- email notification screenshot or delivery record
- post-test Terraform plan output (PLAN_EXIT=0)
- Cloud SQL final state (STOPPED/NEVER)
- Scheduler final states (PAUSED)
- `git status` output

**Step 10 -- Do not claim success unless incident and email are both observed.**
If the incident is opened but no email is received, or if no incident is opened within two
evaluation windows, record the partial result honestly and do not close the gap.

---

## 7. Future Execution Plan -- Backlog Alert Proof

The backlog alert requires more than 500 messages to remain undelivered on the
`market-events-raw-worker-push` subscription for at least 300 consecutive seconds. This
represents a materially higher operational risk than the DLQ proof because it may require
either sustained message publishing or temporary worker unavailability.

This proof is deferred until a safe method is reviewed and approved. Possible methods to
evaluate in a future design session:

- **Temporary push endpoint disablement:** Disable the push subscription endpoint in a
  controlled maintenance window, publish a bounded burst, then re-enable. Risk: messages
  accumulate against the production subscription; cleanup requires careful draining.
- **Controlled worker response delay:** Introduce a configurable artificial delay in the
  worker response path for a proof-only deployment. Risk: requires a worker code change
  and a separate deployment; not suitable for a docs-only branch.
- **Proof-only subscription mirroring pattern:** Create a separate proof-only subscription
  on the same topic with no active push endpoint, then publish to a proof-only topic. Risk:
  requires Terraform changes; does not trigger the production subscription metric.
- **Avoid production subscription pressure unless explicitly approved:** Any approach that
  touches the `market-events-raw-worker-push` production subscription directly should be
  treated as high-risk and must be approved by a separate runbook before execution.

A dedicated design document should be written before any backlog alert proof branch is
opened.

---

## 8. Evidence to Capture

The following checklist applies to any future execution branch for these proofs:

- [ ] Branch name recorded
- [ ] Timestamp recorded (UTC)
- [ ] Alert policy ID confirmed (from `gcloud monitoring policies describe`)
- [ ] Metric filter confirmed (from policy describe output)
- [ ] Test marker value recorded
- [ ] `gcloud monitoring policies describe` output saved
- [ ] Cloud Monitoring incident ID or alert resource output captured
- [ ] Notification email screenshot or Gmail delivery record captured
- [ ] Post-test `terraform plan -detailed-exitcode` output: PLAN_EXIT=0
- [ ] Cloud SQL final state confirmed: STOPPED / NEVER
- [ ] Cloud Scheduler final states confirmed: PAUSED
- [ ] `git status` output: clean
- [ ] Non-claims table completed (see section 9)

---

## 9. Non-Claims

| Item | Status |
|---|---|
| Pub/Sub and DLQ alert policies implemented | VALIDATED |
| Incident creation for Pub/Sub and DLQ alerts | NOT YET PROVEN |
| Email notification delivery for Pub/Sub and DLQ alerts | NOT YET PROVEN |
| Synthetic DLQ alert proof executed | NOT EXECUTED |
| Synthetic backlog alert proof executed | NOT EXECUTED |
| Cloud SQL started | NOT STARTED |
| Pub/Sub messages published on this branch | NOT PUBLISHED |
| Cloud Scheduler state changed | NOT CHANGED |
| Terraform apply on this branch | NOT EXECUTED |
| Production scaling changed | NOT CHANGED |
| Dataflow production streaming changed | NOT CHANGED |

---

## 10. Recommended Next Branch

**Branch name:** `exec/pubsub-dlq-alert-notification-proof`

**Purpose:** Execute the lowest-risk DLQ alert notification proof. Publish exactly one
bounded synthetic malformed message using the approved DLQ validation procedure, wait for
the Cloud Monitoring evaluation window, confirm incident creation, and capture email
notification delivery evidence. All safety gates in section 5 must be confirmed before
the branch opens.

**Prerequisite:** The DLQ malformed-message validation procedure documented in
[docs/dlq-malformed-message-validation-evidence.md](dlq-malformed-message-validation-evidence.md)
must be reviewed and approved for reuse in the execution branch. A unique test marker
must be defined before any message is published.

**Outcome:** If both incident creation and email delivery are observed and documented, the
gap "Incident creation and email notification delivery for Pub/Sub and DLQ alerts: NOT YET
PROVEN" can be updated to VALIDATED.

---

## 11. Evidence Links

- [docs/pubsub-backlog-dlq-alert-policies-evidence.md](pubsub-backlog-dlq-alert-policies-evidence.md)
  -- three alert policies applied and enabled; APPLY_EXIT=0; post-apply PLAN_EXIT=0
- [docs/back-pressure-queue-depth-analysis.md](back-pressure-queue-depth-analysis.md)
  -- back-pressure and queue-depth analysis; covers failure modes, metric selection rationale, and proposed alert thresholds
- [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md)
  -- DLQ topic and deadLetterPolicy configured; maxDeliveryAttempts=5; 10s/60s backoff
- [docs/dlq-malformed-message-validation-evidence.md](dlq-malformed-message-validation-evidence.md)
  -- validated DLQ routing path; one malformed payload reached DLQ; observed caveat on multiple DLQ entries per test marker
- [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md)
  -- two baseline alert policies enabled; email notification channel attached
- [docs/notification-channels-evidence.md](notification-channels-evidence.md)
  -- email notification channel created and attached to alert policies
- [docs/bigquery-quality-incident-notification-delivery-proof.md](bigquery-quality-incident-notification-delivery-proof.md)
  -- precedent proof: Cloud Monitoring incident creation and email delivery proven for the BigQuery quality alert policy
- [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md)
  -- master evidence index
