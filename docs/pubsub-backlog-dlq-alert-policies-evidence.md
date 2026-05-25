# Pub/Sub Backlog and DLQ Alert Policies Evidence

**Status:** VALIDATED -- Pub/Sub backlog and DLQ Cloud Monitoring alert policies applied via Terraform

---

## 1. Summary

This branch implements three Terraform-managed Cloud Monitoring alert policies for the Real-Time Data Platform:

- **Oldest unacked message age** -- alerts when the oldest unacknowledged message on the `market-events-raw-worker-push` subscription exceeds 120 seconds, indicating a stalled or slow worker.
- **Undelivered message backlog** -- alerts when the number of undelivered messages on `market-events-raw-worker-push` exceeds 500, indicating sustained back-pressure.
- **DLQ message count** -- alerts when any message is sent to the `market-events-raw-dlq` topic, indicating poison-pill or repeatedly-failing messages have been routed to the dead-letter queue.

All three policies are managed in `infra/terraform/gcp/monitoring.tf` and were applied via a saved Terraform plan. The policies are enabled and attached to the existing operator notification channel.

---

## 2. Applied Resources

| Terraform Resource | Display Name | Live Alert Policy ID |
|---|---|---|
| `google_monitoring_alert_policy.pubsub_worker_oldest_unacked_message_age` | RTDP PubSub Worker Oldest Unacked Message Age | `projects/project-42987e01-2123-446b-ac7/alertPolicies/8034401405279476713` |
| `google_monitoring_alert_policy.pubsub_worker_num_undelivered_messages` | RTDP PubSub Worker Undelivered Messages Backlog | `projects/project-42987e01-2123-446b-ac7/alertPolicies/9931906580558855386` |
| `google_monitoring_alert_policy.pubsub_dlq_message_count` | RTDP PubSub DLQ Message Count | `projects/project-42987e01-2123-446b-ac7/alertPolicies/3401029857159467149` |

---

## 3. Notification Channel

All three alert policies are attached to the existing operator notification channel:

```
projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885
```

No new notification channel was created on this branch.

---

## 4. Alert Conditions

### A. Oldest Unacked Message Age

Triggers when the oldest unacknowledged message on the worker push subscription has been waiting longer than 120 seconds for two consecutive minutes.

| Field | Value |
|---|---|
| Metric | `pubsub.googleapis.com/subscription/oldest_unacked_message_age` |
| Resource type | `pubsub_subscription` |
| Subscription | `market-events-raw-worker-push` |
| Comparison | `COMPARISON_GT` |
| Threshold | 120 seconds |
| Duration | 120s |
| Alignment | `ALIGN_MAX` over 60s |
| Reducer | `REDUCE_MAX` |

**Filter:**
```
metric.type="pubsub.googleapis.com/subscription/oldest_unacked_message_age" resource.type="pubsub_subscription" resource.labels.subscription_id="market-events-raw-worker-push"
```

### B. Undelivered Messages Backlog

Triggers when more than 500 messages have been waiting for delivery on the worker push subscription for at least 5 minutes.

| Field | Value |
|---|---|
| Metric | `pubsub.googleapis.com/subscription/num_undelivered_messages` |
| Resource type | `pubsub_subscription` |
| Subscription | `market-events-raw-worker-push` |
| Comparison | `COMPARISON_GT` |
| Threshold | 500 messages |
| Duration | 300s |
| Alignment | `ALIGN_MAX` over 60s |
| Reducer | `REDUCE_MAX` |

**Filter:**
```
metric.type="pubsub.googleapis.com/subscription/num_undelivered_messages" resource.type="pubsub_subscription" resource.labels.subscription_id="market-events-raw-worker-push"
```

### C. DLQ Message Count

Triggers immediately when any message is sent to the DLQ topic, providing a zero-tolerance signal for poison-pill or failed-delivery messages.

| Field | Value |
|---|---|
| Metric | `pubsub.googleapis.com/topic/send_message_operation_count` |
| Resource type | `pubsub_topic` |
| Topic | `market-events-raw-dlq` |
| Comparison | `COMPARISON_GT` |
| Threshold | 0 |
| Duration | 0s |
| Alignment | `ALIGN_DELTA` over 300s |
| Reducer | `REDUCE_SUM` |

**Filter:**
```
metric.type="pubsub.googleapis.com/topic/send_message_operation_count" resource.type="pubsub_topic" resource.labels.topic_id="market-events-raw-dlq"
```

---

## 5. Validation

| Step | Result |
|---|---|
| `terraform fmt -check -recursive infra/terraform/gcp` | Passed |
| `terraform -chdir=infra/terraform/gcp validate` | Passed |
| `terraform plan` before apply | 3 to add, 0 to change, 0 to destroy |
| `terraform apply` (saved plan) | `APPLY_EXIT=0` |
| Post-apply `terraform plan -detailed-exitcode` | `PLAN_EXIT=0` |
| `gcloud monitoring policies list` | All three policies present |
| `gcloud monitoring policies describe` (each policy) | `enabled: true`; notification channel attached |

Live `gcloud` verification confirmed that all three policies are enabled and attached to the operator notification channel `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885`.

---

## 6. Non-Claims

| Claim | Status |
|---|---|
| Alert policies implemented | VALIDATED |
| Terraform apply executed | VALIDATED |
| Post-apply zero-diff | VALIDATED |
| Alert incident triggered | NOT EXECUTED |
| Email notification delivery for these new policies | NOT YET PROVEN |
| Synthetic Pub/Sub backlog event generated | NOT EXECUTED |
| Synthetic DLQ message generated on this branch | NOT EXECUTED |
| Cloud SQL started | NOT STARTED |
| Pub/Sub messages published | NOT PUBLISHED |
| Cloud Scheduler changed | NOT CHANGED |
| Production scaling changed | NOT CHANGED |
| Dataflow production streaming changed | NOT CHANGED |

---

## 7. Evidence Links

- [docs/back-pressure-queue-depth-analysis.md](back-pressure-queue-depth-analysis.md) -- analysis motivating these alert thresholds
- [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) -- DLQ topic and deadLetterPolicy configuration
- [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) -- existing alert policies and notification channel
- [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) -- full evidence index
