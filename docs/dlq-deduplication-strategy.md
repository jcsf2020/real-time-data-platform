# DLQ Deduplication Strategy

## Status

| Field | State |
|---|---|
| Document type | STRATEGY ONLY |
| New GCP workload execution | No |
| New malformed message published | No |
| Cloud SQL started | No |
| Terraform apply executed | No |
| Production-grade DLQ consumer implemented | No |

This document is a strategy and design record. No GCP write operations have been
performed on this branch. No commands from this document should be run directly. Any
future implementation must be carried out in a separate execution branch with its own
preflight checks and evidence document.

---

## Executive Summary

DLQ malformed-message routing is validated. A single malformed publish to
`market-events-raw` was rejected by the worker, retried according to the configured
`deadLetterPolicy`, and routed to `market-events-raw-dlq`. The routing mechanism works.

However, one malformed publish produced multiple DLQ entries for the same original
message. Observed `CloudPubSubDeadLetterSourceDeliveryCount` values spanned 5 through 16
for the same `test_marker`. This is consistent with Pub/Sub's at-least-once dead-letter
forwarding semantics: after `maxDeliveryAttempts` is exceeded, Pub/Sub forwards a DLQ
copy on each subsequent delivery attempt, not just once.

Any future DLQ consumer must therefore be deduplication-aware. It cannot assume that
DLQ entry count equals original poison-message count, and it cannot use the DLQ
`messageId` as a business deduplication key. This document defines the deduplication
strategy, key hierarchy, proposed consumer behaviour, future schema, acceptance criteria,
risks, controls, and explicit non-claims.

---

## Observed Behaviour From Evidence

Source: `docs/dlq-malformed-message-validation-evidence.md`

| Parameter | Value |
|---|---|
| TEST_MARKER | dlq-malformed-20260520165636 |
| PAYLOAD_SHA256 | ac2f9c60edbf039b514a389c5345bf44ef30f9629b13fd48659389631243221c |
| Published message ID | 19574066311340908 |
| Source topic | market-events-raw |
| Source subscription | market-events-raw-worker-push |
| DLQ topic | market-events-raw-dlq |
| maxDeliveryAttempts | 5 |
| Delivery counts observed | 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 |
| Total distinct DLQ entries | 12 |
| Original malformed publishes | 1 |

Multiple DLQ entries were returned for the same `test_marker` across successive pulls.
Each entry was a distinct DLQ message with its own `messageId` but identical payload
content and the same `test_marker` and `PAYLOAD_SHA256`.

This behaviour confirms that:

- One original malformed message can produce many DLQ entries.
- DLQ `messageId` values differ across entries for the same original message.
- Payload content and hash remain consistent across all DLQ entries.
- The `test_marker` attribute is consistent and usable as a deduplication key in
  controlled validation scenarios.

---

## Deduplication Principles

**DLQ entry count does not equal original poison-message count.**
Pub/Sub dead-letter forwarding is at-least-once. After `maxDeliveryAttempts`, a copy is
forwarded to the DLQ topic on each additional delivery attempt. The number of DLQ entries
for a single original message is determined by how long the message remained un-acked in
the dead-letter subscription, not by the number of original publishes.

**DLQ consumers must deduplicate before remediation or replay.**
A naive DLQ consumer that processes every entry independently would classify one
malformed message as twelve distinct incidents, trigger twelve alerts, and potentially
attempt twelve replay operations. Deduplication must be applied as the first step in
any DLQ consumer pipeline.

**Deduplication must be deterministic.**
Two DLQ consumer instances processing the same DLQ entry independently must arrive at
the same deduplication key. Keys derived from payload content (payload hash) or stable
business identifiers (event_id) satisfy this requirement. Keys derived from message
delivery order or consumer state do not.

**Deduplication must be auditable.**
The deduplication record should preserve the full observed set of DLQ entries, the
derived dedup key, the classification reason, and all relevant timestamps. Discarded
duplicate entries must be acknowledged and logged, not silently dropped.

---

## Recommended Deduplication Key Hierarchy

When processing a DLQ entry, compute the deduplication key using the first applicable
rule in the following precedence order:

| Priority | Key | When to use |
|---|---|---|
| 1 | `event_id` | Use when the DLQ payload is a valid event payload that contains a parseable `event_id` field. The `event_id` is the canonical business identity of the event. |
| 2 | `payload_sha256` | Use when the payload is malformed, missing required fields, or does not conform to the event contract. The SHA-256 hash of the raw payload bytes is stable and deterministic. |
| 3 | `test_marker` | Use only in controlled validation scenarios where the payload contains a `test_marker` attribute inserted specifically for DLQ testing. Do not use `test_marker` as a deduplication key in production unless the payload is a confirmed validation message. |
| 4 | `source_subscription + publish_time + payload_hash` | Fallback composite key. Use when none of the above are available. Derived from the `CloudPubSubDeadLetterSourceSubscription` attribute, `CloudPubSubDeadLetterSourceTopicPublishTime` attribute, and SHA-256 of the payload bytes. |

**messageId must NOT be used as the business deduplication key.**
DLQ entries for the same original malformed message carry different `messageId` values.
Using `messageId` as the dedup key would classify each DLQ entry as a distinct incident
and defeat the purpose of deduplication.

---

## Proposed DLQ Consumer Behaviour

The following algorithm describes the intended behaviour of a future DLQ consumer. It is
a conceptual design, not an implementation. No code has been written and no production
consumer is deployed.

```
1. Pull one DLQ message from market-events-raw-dlq.

2. Decode the message payload safely.
   - If decoding fails: treat the raw bytes as the payload for hashing purposes.
   - Record the decode failure reason.

3. Compute payload_sha256.
   - Hash the raw payload bytes (not the decoded JSON).
   - This value is stable regardless of JSON key ordering.

4. Extract optional identifiers from the decoded payload.
   - Extract event_id if present and parseable.
   - Extract test_marker if present (validation messages only).

5. Extract DLQ message attributes.
   - CloudPubSubDeadLetterSourceSubscription
   - CloudPubSubDeadLetterSourceTopicPublishTime
   - CloudPubSubDeadLetterSourceDeliveryCount

6. Build dedup_key using the key hierarchy defined above.
   - Prefer event_id if valid.
   - Fall back to payload_sha256.
   - Fall back to test_marker only for validation messages.
   - Fall back to composite key if none of the above are available.

7. Check deduplication store (e.g., observability.dlq_poison_messages).
   - Query by dedup_key.

8. If dedup_key already exists in the deduplication store:
   - Increment observed_count.
   - Update last_seen_at and max_delivery_count if the current delivery count is higher.
   - Acknowledge the DLQ message.
   - Record duplicate_observed in the audit log.
   - Do NOT trigger a new alert.
   - Do NOT attempt replay.

9. If dedup_key is NOT in the deduplication store (first occurrence):
   - Create a canonical poison-message record with all fields.
   - Classify the rejection reason (missing fields, schema violation, unknown type, etc.).
   - Emit an alert or report to the operator.
   - Acknowledge the DLQ message.
   - Set replay_status = "pending_review".

10. Never replay automatically without explicit operator approval.
    - Set replay_status to "approved" only after operator review.
    - A separate replay process reads records with replay_status = "approved".
    - The replay process must itself be idempotent.
```

The deduplication store check in step 7 must be performed before acknowledging the
message. Acknowledging before checking would allow a race condition where a duplicate
entry is processed by a second consumer instance before the first instance has written
the dedup record.

---

## Suggested Future Schema

Proposed table: `observability.dlq_poison_messages`

This table is intended to serve as both the deduplication store and the operational
audit log for all poison messages observed on the DLQ.

| Column | Type | Description |
|---|---|---|
| dedup_key | STRING | Derived deduplication key (event_id, payload_sha256, test_marker, or composite). Primary deduplication identifier. |
| payload_sha256 | STRING | SHA-256 hash of the raw payload bytes. Always populated regardless of dedup_key source. |
| source_topic | STRING | Pub/Sub source topic (e.g., market-events-raw). |
| source_subscription | STRING | Pub/Sub source subscription that produced the DLQ entry (e.g., market-events-raw-worker-push). |
| dlq_topic | STRING | DLQ topic the entry was delivered to (e.g., market-events-raw-dlq). |
| first_seen_at | TIMESTAMP | Timestamp of the first DLQ entry processed for this dedup_key. |
| last_seen_at | TIMESTAMP | Timestamp of the most recently processed DLQ entry for this dedup_key. |
| observed_count | INTEGER | Total number of DLQ entries processed for this dedup_key. |
| max_delivery_count | INTEGER | Maximum CloudPubSubDeadLetterSourceDeliveryCount observed across all entries for this dedup_key. |
| payload_excerpt | STRING | Truncated and redacted payload excerpt for debugging. Must not contain PII or secrets. |
| validation_error | STRING | Structured classification of the rejection reason (e.g., missing_required_fields, schema_violation, decode_error). |
| replay_status | STRING | Operator-controlled replay state. One of: pending_review, approved, rejected, replayed, replay_failed. Default: pending_review. |
| operator_decision | STRING | Free-text field for operator notes or approval record. |
| created_at | TIMESTAMP | Row creation timestamp (first occurrence). |
| updated_at | TIMESTAMP | Row last-updated timestamp (updated on each duplicate entry). |

If BigQuery is chosen as the backing store, the table should be partitioned by
`first_seen_at` and clustered by `source_subscription` and `payload_sha256` to support
efficient deduplication lookups and time-bounded queries.

If Cloud SQL is chosen as the backing store, the table should have a unique index on
`dedup_key` and a non-unique index on `payload_sha256`.

---

## Acceptance Criteria for Future Implementation

A future DLQ consumer implementation is accepted only if all of the following hold:

| Criterion | Required |
|---|---|
| Duplicate DLQ entries for same payload increment observed_count | `observed_count` increases by 1 for each additional DLQ entry with the same dedup_key; no new canonical record is created |
| Only the first entry creates the canonical poison-message record | Exactly one row exists per dedup_key after N duplicate entries are processed |
| No automatic replay | `replay_status` remains `pending_review` until operator explicitly sets it to `approved` |
| No Cloud SQL mutation unless part of future implementation branch | Cloud SQL remains NEVER/STOPPED unless a separate implementation branch explicitly manages the lifecycle |
| No secrets printed | No credentials, tokens, or database URLs appear in any log output or stored payload |
| Final safe state preserved | Cloud SQL NEVER/STOPPED; schedulers PAUSED; Terraform apply not run; PLAN_EXIT=0 |
| Deduplication store check precedes ack | Consumer does not acknowledge a DLQ message before the dedup check completes |
| Duplicate entries are acknowledged and logged | Duplicate entries do not remain unacked; duplicate_observed is recorded in the audit log |

---

## Risks and Controls

| Risk | Control |
|---|---|
| Accidentally replaying malformed messages | Never replay without explicit `replay_status = "approved"` set by operator. Replay process must itself be idempotent and bounded. |
| Treating DLQ messageId as a unique business event | messageId must NOT be used as the deduplication key. Use event_id or payload_sha256 as defined in the key hierarchy. |
| Infinite poison-message loop | A replayed message that fails again will re-enter the DLQ. The consumer must detect re-entrant entries by checking payload_sha256 and incrementing observed_count rather than creating a new canonical record. Replay attempts must be counted and bounded. |
| Alert fatigue | Deduplication ensures only the first DLQ entry triggers an alert. Duplicate entries increment observed_count silently. Alerting rules should filter on first_seen_at and not on observed_count changes. |
| Storing PII or secrets in payload excerpts | payload_excerpt must be truncated to a safe maximum length and must not include known PII field names (e.g., email, phone, ssn, password, token). A redaction pass must be applied before writing to the deduplication store. |
| Remediating without operator approval | replay_status must be a controlled field with a restricted write path. No automated process may set replay_status = "approved". Only operator-initiated actions may do so. |

---

## Explicit Non-Claims

- Dataflow is not implemented.
- Sustained production throughput is not claimed.
- Exactly-once DLQ routing is not claimed.
- Clean single-message DLQ semantics are not claimed.
- Production-grade poison-message handling is not implemented.
- Automatic replay is not implemented.
- Enterprise incident response is not claimed.
- A DLQ consumer has not been written, deployed, or tested.
- The proposed schema has not been created in any database or BigQuery dataset.
- No deduplication logic has been executed against real DLQ data.
- No operator approval workflow has been implemented.

---

## Safe Interview Wording

"I validated malformed-message DLQ routing and then documented the operational caveat:
one malformed publish produced multiple DLQ entries for the same marker. I do not claim
exactly-once DLQ semantics; the next production step would be a deduplication-aware DLQ
consumer keyed by event_id or payload hash."

If challenged further:

"The strategy defines a key hierarchy: event_id for valid payloads, payload_sha256 for
malformed or non-contract payloads, and a composite fallback. The messageId from the DLQ
message itself must not be used as the business dedup key because different DLQ entries
for the same original message carry different messageIds. This is documented and the
evidence from the DLQ validation test confirms it."
