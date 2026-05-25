# Pub/Sub DLQ Alert Notification Proof Evidence

**Status:** VALIDATED -- Pub/Sub DLQ and oldest-unacked alert incident/email delivery observed
**Date:** 2026-05-25
**Branch:** `exec/pubsub-dlq-alert-notification-proof`

---

## 1. Summary

This execution branch performed a bounded Pub/Sub DLQ alert notification proof using one intentionally malformed synthetic Pub/Sub message.

The proof produced Cloud Monitoring alert incidents and Gmail notification evidence for:

- `RTDP PubSub DLQ Message Count`
- `RTDP PubSub Worker Oldest Unacked Message Age`
- `RTDP Worker Message Error Alert`

The primary objective was the DLQ alert notification proof. The oldest-unacked alert also fired during the same controlled malformed-message retry window because the message remained unacknowledged long enough to exceed the configured threshold.

No Cloud SQL start was required. Cloud Scheduler jobs remained paused. Terraform remained zero-diff after the test.

---

## 2. Test Marker

| Field | Value |
|---|---|
| Test marker | `PUBSUBDLQPROOFV1-20260525T113446Z` |
| Evidence directory | `docs/evidence/pubsub-dlq-alert-notification-proof/PUBSUBDLQPROOFV1-20260525T113446Z` |
| Marker creation UTC | `20260525T113446Z` |
| Publish UTC | `2026-05-25T11:38:17Z` |
| Published Pub/Sub message ID | `19606156514351070` |

Synthetic malformed payload used:

```text
MALFORMED_JSON_PUBSUBDLQPROOFV1-20260525T113446Z_SCHEMA_FAILURE
```

---

## 3. Pre-Test Safety Gates

| Gate | Result |
|---|---|
| Branch | `exec/pubsub-dlq-alert-notification-proof` |
| Git status before proof | Clean branch before evidence capture |
| Cloud SQL state | `NEVER STOPPED` |
| `rtdp-silver-refresh-scheduler` | `PAUSED` |
| `rtdp-bigquery-append-scheduler` | `PAUSED` |
| Terraform pre-test plan | `PLAN_EXIT=0` |
| Alert policies enabled | Confirmed via `gcloud monitoring policies describe` |
| Notification channel attached | Confirmed on all three Pub/Sub/DLQ policies |

Notification channel attached to the policies:

```text
projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885
```

No notification channel email address is recorded in this repository.

---

## 4. Alert Policies Checked

| Alert policy | Policy ID | Evidence file |
|---|---|---|
| RTDP PubSub DLQ Message Count | `projects/project-42987e01-2123-446b-ac7/alertPolicies/3401029857159467149` | `dlq-alert-policy-baseline.json` |
| RTDP PubSub Worker Oldest Unacked Message Age | `projects/project-42987e01-2123-446b-ac7/alertPolicies/8034401405279476713` | `oldest-unacked-alert-policy-baseline.json` |
| RTDP PubSub Worker Undelivered Messages Backlog | `projects/project-42987e01-2123-446b-ac7/alertPolicies/9931906580558855386` | `undelivered-backlog-alert-policy-baseline.json` |

All three policies were enabled and attached to the existing notification channel before the synthetic message was published.

---

## 5. Execution

One malformed message was published to the production input topic:

```text
market-events-raw
```

The worker received the message through the existing push subscription:

```text
market-events-raw-worker-push
```

The worker returned repeated `500 Internal Server Error` responses because the payload was not valid JSON. This caused Pub/Sub retry behaviour and eventual DLQ routing according to the existing dead-letter policy.

Relevant worker error logs were captured in:

- `recent-worker-logs-after-publish.json`
- `recent-worker-logs-after-publish-summary.json`

The worker logs showed repeated `JSONDecodeError` records for the malformed message processing path.

---

## 6. Cloud Monitoring Incident Evidence

The following alert incidents were observed through `gcloud alpha monitoring alerts list` and saved in:

- `all-alerts-raw-after-test.json`
- `all-alerts-raw-after-test.pretty.json`
- `proven-alert-incidents-summary.json`
- `alert-describes-summary.json`

| Alert | State | Open time UTC | Close time UTC | Metric |
|---|---|---|---|---|
| RTDP PubSub DLQ Message Count | CLOSED | `2026-05-25T11:46:22Z` | `2026-05-25T12:00:23Z` | `pubsub.googleapis.com/topic/send_message_operation_count` |
| RTDP PubSub Worker Oldest Unacked Message Age | CLOSED | `2026-05-25T11:48:35Z` | `2026-05-25T11:55:35Z` | `pubsub.googleapis.com/subscription/oldest_unacked_message_age` |
| RTDP Worker Message Error Alert | CLOSED | `2026-05-25T11:41:16Z` | `2026-05-25T11:57:42Z` | `logging.googleapis.com/user/worker_message_error_count` |

The DLQ alert incident proves that the `RTDP PubSub DLQ Message Count` policy fired for the controlled DLQ signal.

The oldest-unacked incident was also observed during the same controlled retry window. It is recorded as additional evidence, but the branch objective remains the DLQ alert notification proof.

---

## 7. Gmail Notification Delivery Evidence

Gmail delivery evidence was observed for this proof window and recorded in:

```text
gmail-delivery-summary.txt
```

Observed Google Cloud Alerting emails:

| # | Type | Alert condition | Received timestamp |
|---|---|---|---|
| 1 | ALERT | `market-events-raw-dlq messages > 0` | `2026-05-25T04:46:22-07:00` |
| 2 | RESOLVED | `market-events-raw-dlq messages > 0` | `2026-05-25T05:00:23-07:00` |
| 3 | ALERT | `oldest_unacked_message_age > 120s` | `2026-05-25T04:48:35-07:00` |
| 4 | RESOLVED | `oldest_unacked_message_age > 120s` | `2026-05-25T04:55:35-07:00` |
| 5 | ALERT | `worker_message_error_count > 0` | `2026-05-25T04:41:16-07:00` |
| 6 | RESOLVED | `worker_message_error_count > 0` | `2026-05-25T04:57:42-07:00` |

This proves email delivery for the DLQ alert and oldest-unacked alert in this controlled proof window.

No email address is recorded in this document.

---

## 8. Final Safe State

Final post-test state was captured in the evidence directory.

| Resource | Final state | Evidence file |
|---|---|---|
| Cloud SQL `rtdp-postgres` | `NEVER STOPPED` | `final-cloudsql-state.txt` |
| `rtdp-silver-refresh-scheduler` | `PAUSED` | `final-silver-scheduler-state.txt` |
| `rtdp-bigquery-append-scheduler` | `PAUSED` | `final-bigquery-scheduler-state.txt` |
| Terraform plan | `PLAN_EXIT=0` | `final-terraform-plan.txt`, `final-terraform-plan-exit.txt` |

No Cloud SQL start was performed. No scheduler state change was performed. No Terraform apply was performed on this branch.

---

## 9. Evidence Files

Evidence directory:

```text
docs/evidence/pubsub-dlq-alert-notification-proof/PUBSUBDLQPROOFV1-20260525T113446Z
```

Key files:

| File | Purpose |
|---|---|
| `test-marker.txt` | Test marker, evidence directory, UTC creation timestamp |
| `malformed-payload.txt` | Synthetic malformed payload |
| `pubsub-publish-output.json` | Pub/Sub publish message ID |
| `publish-timestamp.txt` | Publish timestamp |
| `dlq-alert-policy-baseline.json` | DLQ policy baseline |
| `oldest-unacked-alert-policy-baseline.json` | Oldest-unacked policy baseline |
| `undelivered-backlog-alert-policy-baseline.json` | Undelivered backlog policy baseline |
| `pre-test-cloudsql-state.txt` | Pre-test Cloud SQL safe state |
| `pre-test-silver-scheduler-state.txt` | Pre-test silver scheduler state |
| `pre-test-bigquery-scheduler-state.txt` | Pre-test BigQuery scheduler state |
| `recent-worker-logs-after-publish.json` | Worker logs after malformed publish |
| `all-alerts-raw-after-test.json` | Raw alert list after test |
| `proven-alert-incidents-summary.json` | Summarised proven alert incidents |
| `gmail-delivery-summary.txt` | Gmail notification delivery summary |
| `final-cloudsql-state.txt` | Final Cloud SQL state |
| `final-silver-scheduler-state.txt` | Final silver scheduler state |
| `final-bigquery-scheduler-state.txt` | Final BigQuery scheduler state |
| `final-terraform-plan.txt` | Final zero-diff Terraform plan output |
| `final-terraform-plan-exit.txt` | Final Terraform plan exit code |

---

## 10. Non-Claims

| Claim | Status |
|---|---|
| DLQ alert policy implemented | VALIDATED |
| DLQ alert incident creation | VALIDATED |
| DLQ alert email delivery | VALIDATED |
| Oldest-unacked alert incident creation | VALIDATED |
| Oldest-unacked alert email delivery | VALIDATED |
| Worker error alert incident creation during this proof | VALIDATED |
| Worker error alert email delivery during this proof | VALIDATED |
| Undelivered backlog alert incident creation | NOT EXECUTED |
| Undelivered backlog alert email delivery | NOT EXECUTED |
| Synthetic malformed Pub/Sub message published | VALIDATED -- one bounded malformed message |
| Cloud SQL started | NOT STARTED |
| Cloud Scheduler changed | NOT CHANGED |
| Terraform apply on this branch | NOT EXECUTED |
| Production scaling changed | NOT CHANGED |
| Dataflow production streaming changed | NOT CHANGED |
| End-user production traffic tested | NOT CLAIMED |

---

## 11. Recruitment Value

This proof closes a practical platform observability gap: a controlled malformed event produced a Cloud Monitoring alert incident and delivered Google Cloud Alerting email notifications.

The evidence demonstrates:

- Pub/Sub/DLQ alert policy configuration is live.
- Cloud Monitoring incident creation works for the DLQ path.
- Email notification delivery works for the DLQ path.
- Safe-state controls were preserved after the proof.
- The result is evidence-backed and non-overclaimed.

This is materially stronger than merely stating that alert policies exist.

---

## 12. Evidence Links

- [docs/pubsub-alert-notification-proof-plan.md](pubsub-alert-notification-proof-plan.md) -- prior controlled proof plan
- [docs/pubsub-backlog-dlq-alert-policies-evidence.md](pubsub-backlog-dlq-alert-policies-evidence.md) -- alert policies applied and verified
- [docs/back-pressure-queue-depth-analysis.md](back-pressure-queue-depth-analysis.md) -- back-pressure and queue-depth rationale
- [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) -- production Pub/Sub DLQ configuration
- [docs/dlq-malformed-message-validation-evidence.md](dlq-malformed-message-validation-evidence.md) -- earlier malformed-message DLQ validation
- [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) -- baseline alert policy evidence
- [docs/notification-channels-evidence.md](notification-channels-evidence.md) -- notification channel evidence
- [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) -- master evidence index
