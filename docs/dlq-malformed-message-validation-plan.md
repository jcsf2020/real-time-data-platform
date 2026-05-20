# DLQ Malformed Message Validation Plan

## Status

| Field | State |
|---|---|
| Plan state | PLANNED ONLY |
| Malformed message published | No |
| DLQ execution performed | No |
| Cloud SQL started | No |
| Terraform apply executed | No |
| DLQ malformed-message routing | NOT YET PROVEN |

No GCP write operations have been performed on this branch. All procedure blocks below
are planning documentation only. Do not copy and run any command from this document
without first creating a separate execution branch and completing all preflight checks.

---

## Purpose

Existing load-test evidence proves that the worker correctly processes valid messages at
50,000-event scale with zero errors. Existing DLQ evidence confirms that the dead-letter
policy, DLQ topic, and retry parameters are configured and Terraform-managed.

The remaining reviewer gap is: **a controlled malformed (poison) Pub/Sub message has never
been published to the production topic, the worker has never been observed to reject a live
message, and DLQ routing has never been exercised against a real payload.**

This plan defines a bounded one-message validation procedure to close that gap in a future
execution branch. It documents the procedure, preflight requirements, acceptance criteria,
abort conditions, and risk controls. It does not execute any GCP operations.

---

## Current Evidence Baseline

| Area | Current Evidence | Source |
|---|---|---|
| Pub/Sub topic exists: `market-events-raw` | Confirmed -- GCP list output in evidence | docs/production-pubsub-dlq-evidence.md |
| Push subscription exists: `market-events-raw-worker-push` | Confirmed -- ACTIVE state in post-change validation | docs/production-pubsub-dlq-evidence.md |
| DLQ topic exists: `market-events-raw-dlq` | Confirmed -- created and listed in execution evidence | docs/production-pubsub-dlq-evidence.md |
| `deadLetterPolicy` configured | Confirmed -- `deadLetterTopic` = `market-events-raw-dlq` | docs/production-pubsub-dlq-evidence.md, infra/terraform/gcp/pubsub.tf |
| `maxDeliveryAttempts=5` | Confirmed in subscription describe output and Terraform | docs/production-pubsub-dlq-evidence.md, infra/terraform/gcp/pubsub.tf |
| `retryPolicy.minimumBackoff=10s` | Confirmed in subscription describe output and Terraform | docs/production-pubsub-dlq-evidence.md, infra/terraform/gcp/pubsub.tf |
| `retryPolicy.maximumBackoff=60s` | Confirmed in subscription describe output and Terraform | docs/production-pubsub-dlq-evidence.md, infra/terraform/gcp/pubsub.tf |
| Worker valid-message path proven at 50,000 events | `worker OK logs=50000`, `worker errors=0`, `publish_error_count=0` | docs/load-test-50000-cloud-evidence.md |
| Worker errors for 50k run | 0 | docs/load-test-50000-cloud-evidence.md |
| Cloud SQL rows for 50k prefix | 50,000 | docs/load-test-50000-cloud-evidence.md |
| Cloud SQL restored to STOPPED / NEVER | Confirmed post-50k run | docs/load-test-50000-cloud-evidence.md |
| Schedulers PAUSED | Confirmed throughout all evidence branches | docs/load-test-50000-cloud-evidence.md |
| Terraform PLAN_EXIT=0 | Confirmed post-50k | docs/load-test-50000-cloud-evidence.md |
| DLQ pull subscription for readback | to confirm during preflight |  |
| Worker service current revision and Ready state | to confirm during preflight |  |
| DLQ message baseline count | to confirm during preflight |  |

---

## Validation Scope

### What the future validation will prove

- Exactly one intentionally malformed message is published to `market-events-raw`
- The worker rejects the message and returns HTTP 500 (error log emitted with `status=error`)
- Pub/Sub retries message delivery according to the configured subscription policy
  (`maxDeliveryAttempts=5`, backoff 10s to 60s)
- After 5 failed delivery attempts the message is routed to `market-events-raw-dlq`
- The healthy worker message path is unaffected during and after the test window
- No Cloud SQL write occurs for the malformed event (worker returns error before DB insert)
- Final state is safe: Cloud SQL STOPPED/NEVER, schedulers PAUSED, no residual retry activity

### What it will NOT prove

- Sustained DLQ throughput or high-volume poison-message behaviour
- Large batch poison-message volume behaviour
- Dataflow behaviour (Dataflow is not implemented)
- Exactly-once production semantics
- End-to-end recovery automation
- Enterprise incident response or on-call paging paths
- DLQ alerting pipeline (alert policies exist for worker errors but DLQ-specific alerting
  is not configured)
- Automatic DLQ draining or replay procedures

---

## Malformed Message Candidate

The safest malformed shape is **valid JSON that is missing all required `MarketEvent` fields**.

This choice is safer than invalid JSON because:

- A valid Pub/Sub push envelope with well-formed base64 data passes envelope parsing in the
  worker HTTP layer (`extract_pubsub_data` succeeds, data bytes are returned).
- The decoded payload fails `validate_event` (Pydantic `model_validate` raises
  `ValidationError`), which causes `process_message` to catch the exception, emit a
  structured error log with `status=error`, and return `{"status": "error"}`.
- The HTTP handler returns **HTTP 500**, which Pub/Sub treats as a retriable failure and
  counts toward `maxDeliveryAttempts=5` before routing to DLQ.
- No Cloud SQL connection attempt is made -- the error path exits before `insert_bronze_event`.

An invalid JSON string (non-base64 or raw malformed bytes) would cause the HTTP handler to
return **HTTP 400** for envelope or base64 errors. Pub/Sub treats 400 as a successful ack
(no retry, no DLQ routing). That path does not exercise the retry/DLQ mechanism.

### Recommended payload

The data field must be the base64 encoding of the JSON string below.

```json
{"test_marker": "dlq-malformed-20260520-plan-only", "invalid": true}
```

This payload is:

- Valid JSON (passes `json.loads` in `decode_message`)
- Missing all required `MarketEvent` fields (`event_id`, `symbol`, `event_type`, `price`,
  `quantity`, `event_timestamp`)
- Non-sensitive (no PII, no credentials, no production-like values)
- Clearly invalid for the worker contract (Pydantic will raise `ValidationError`)
- Uniquely identifiable by the `test_marker` attribute in worker error logs

The full Pub/Sub push envelope would wrap this payload. Construct the envelope in the
execution branch -- do not construct it here to avoid any risk of accidental execution.

---

## Preflight Checks

Run all of the following before the future execution. Abort if any check fails.

| # | Check | Required result | Abort if |
|---|---|---|---|
| 1 | `git status --short --branch` | Branch is the execution branch (not this plan branch) | Branch contains any non-doc change or is this plan branch |
| 2 | Cloud SQL activation policy | `NEVER   STOPPED` | Cloud SQL is not NEVER / STOPPED |
| 3 | Cloud Scheduler state | Both schedulers PAUSED | Either scheduler is ACTIVE |
| 4 | Pub/Sub topic `market-events-raw` exists | Topic present in `gcloud pubsub topics list` | Topic missing |
| 5 | Subscription `market-events-raw-worker-push` exists and is ACTIVE | State ACTIVE | Subscription missing or not ACTIVE |
| 6 | DLQ topic `market-events-raw-dlq` exists | Topic present in topic list | DLQ topic missing |
| 7 | `deadLetterPolicy` present on subscription | `deadLetterTopic` and `maxDeliveryAttempts` visible in `describe` output | `deadLetterPolicy` absent |
| 8 | `maxDeliveryAttempts=5` | Value is 5 | Value differs from 5 |
| 9 | DLQ subscription / read mechanism known | A pull subscription on `market-events-raw-dlq` exists, or a temporary read mechanism is approved before execution | No read mechanism exists and none has been approved |
| 10 | DLQ message baseline count | Recorded (may be 0) | Baseline unavailable (would make proof ambiguous) |
| 11 | Worker service Ready | `gcloud run services describe rtdp-pubsub-worker` shows Ready | Worker not Ready |
| 12 | Current worker error metric baseline | `worker_message_error_count` baseline recorded | Baseline unavailable |
| 13 | `uv run pytest -q` | All tests pass | Any test fails |
| 14 | `uv run ruff check .` | Clean | Any ruff error |
| 15 | Terraform plan | `PLAN_EXIT=0` | Any Terraform diff |

---

## Future Execution Procedure

> **DO NOT RUN IN THIS PLAN BRANCH.**
>
> The steps below are a planning record for a future execution branch. They must not be
> run until a separate branch has been created, all preflight checks have passed, and the
> procedure has been reviewed.

---

**FUTURE EXECUTION ONLY - DO NOT RUN NOW**

```
Step 1 -- Capture timestamp window

  Record the UTC timestamp immediately before publishing the malformed message.
  This timestamp bounds the worker log query window.

Step 2 -- Publish exactly one malformed message to market-events-raw

  Construct a Pub/Sub push-compatible JSON envelope with the test payload base64-encoded
  in the message.data field. Publish using gcloud pubsub topics publish with the
  --message flag. Use the exact test_marker value from the Malformed Message Candidate
  section. Confirm publish output shows exactly one message ID. Stop immediately if
  more than one message would be published.

  Confirm: published_count=1, unique test_marker visible in publish output.

Step 3 -- Wait for retry / DLQ routing window

  Allow sufficient time for Pub/Sub to deliver and retry 5 times under the configured
  backoff policy (10s minimum, 60s maximum). Estimated window: approximately 5 to 10
  minutes. Do not publish additional messages during the wait.

Step 4 -- Query worker error logs for the test marker

  Use gcloud logging read with a filter on the test_marker value and the timestamp
  captured in Step 1. Confirm at least one structured log entry with status=error and
  the test_marker attribute is present.

Step 5 -- Query DLQ for the message

  If a pull subscription exists on market-events-raw-dlq: use gcloud pubsub subscriptions
  pull to read the message. Confirm the test_marker attribute is present. Acknowledge the
  message to clean up the DLQ.

  If no pull subscription exists: create a temporary read-only pull subscription on
  market-events-raw-dlq only if explicitly approved in the execution branch. Do not
  create it speculatively. An alternative is to inspect delivery attempt count via
  Cloud Monitoring or Pub/Sub metrics if pull is not available.

Step 6 -- Confirm no healthy load test messages were involved

  Verify that no 50k-prefix event IDs appear in the error logs. The malformed message
  test should be the only error-path activity in the log window.

Step 7 -- Confirm no Cloud SQL start was required

  Query Cloud SQL activation policy and state. Must remain NEVER / STOPPED. The malformed
  path exits before insert_bronze_event; no database connection should have been attempted.

Step 8 -- Confirm final safe state

  Cloud SQL: NEVER / STOPPED
  Schedulers: PAUSED
  No residual retry activity in DLQ (message acked in Step 5)
  Worker error metric returned to baseline after test window
  PLAN_EXIT=0

Step 9 -- Write evidence document

  Create docs/dlq-malformed-message-validation-evidence.md on the execution branch.
  Do not write an evidence document until all prior steps are confirmed. The evidence
  document must not be created on this plan branch.
```

**END FUTURE EXECUTION ONLY**

---

## Acceptance Criteria For Future Evidence

The future execution is accepted only if all of the following are true:

| Criterion | Required |
|---|---|
| Exactly one malformed test message published | `published_count=1` confirmed |
| Malformed marker appears in worker error logs | `test_marker=dlq-malformed-20260520-plan-only` in at least one `status=error` log entry |
| Pub/Sub retry behaviour observed or inferred | Delivery attempt count >= 2, or DLQ routing confirmed directly |
| Message appears in DLQ or DLQ path proven | Message pulled from DLQ subscription, or Pub/Sub state confirms message routed to `market-events-raw-dlq` |
| No Cloud SQL start | Cloud SQL remains `NEVER / STOPPED` throughout |
| No Terraform apply | `PLAN_EXIT=0` at close of execution |
| Schedulers remain PAUSED | Both schedulers PAUSED at close of execution |
| Healthy 50k evidence untouched | No 50k-prefix events appear in error logs; Cloud SQL prefix row count unchanged |
| Evidence document created separately | `docs/dlq-malformed-message-validation-evidence.md` committed on the execution branch, not this plan branch |

---

## Abort Conditions

Abort the future execution immediately if any of the following are observed:

| Condition | Required action |
|---|---|
| Cloud SQL is not STOPPED / NEVER before test | Abort; do not publish; investigate |
| Either scheduler is not PAUSED | Abort; do not publish; pause schedulers and review |
| `deadLetterPolicy` absent on subscription | Abort; without DLQ policy the message will retry indefinitely |
| Worker service is not Ready | Abort; do not publish until worker is confirmed Ready |
| DLQ read mechanism is unknown or unverified | Abort; without readback path the test cannot be confirmed |
| More than one malformed message would be published | Abort; one-message scope must be preserved |
| Any command would print secrets or credentials | Abort; rewrite the command to redact secrets |
| Terraform plan shows non-zero diff | Abort; resolve the Terraform diff before publishing |
| Branch contains non-doc changes | Abort; this procedure applies only to a clean execution branch |
| Post-publish message count exceeds 1 | Abort; investigate source of extra messages |

---

## Risk Controls

| Control | Detail |
|---|---|
| One-message test only | Procedure publishes exactly one message; multi-message scenarios are abort conditions |
| Unique test marker | `test_marker=dlq-malformed-20260520-plan-only` distinguishes the test from any production message |
| No valid production-like payload | Payload contains none of the required `MarketEvent` fields; it cannot be mistaken for a real event |
| No load test batch | No batch publishing; no JSONL file; no loop |
| No Cloud SQL dependency | Worker error path exits before `insert_bronze_event`; Cloud SQL remains STOPPED/NEVER |
| No secrets printed | All commands must redact credentials; abort condition if any secret would appear in output |
| No Terraform apply | Terraform plan must be zero-diff before and after execution |
| Explicit final safe-state check | Cloud SQL, schedulers, DLQ clean-up, and PLAN_EXIT=0 are all required before closing the execution |
| Separate evidence branch required | This plan must be reviewed and merged before execution begins; evidence is committed to a different branch |

---

## Evidence Document To Create Later

File: `docs/dlq-malformed-message-validation-evidence.md`

The evidence document must include:

- Execution branch name
- Publish timestamp (UTC, captured before publish in Step 1)
- Malformed payload hash (SHA-256 of the payload bytes) or redacted payload
- Worker error log sample showing `test_marker` and `status=error`
- DLQ confirmation (pull output or Pub/Sub delivery-attempt count evidence)
- Confirmation that no Cloud SQL start occurred
- Confirmation that no Terraform apply occurred
- Confirmation that schedulers remained PAUSED
- Confirmation that 50k healthy evidence is untouched
- Final safe state: Cloud SQL NEVER/STOPPED, PLAN_EXIT=0
- Explicit non-claims (see non-claims list in Validation Scope)

---

## Production-Like Value

| Reviewer Concern | How This Plan Addresses It |
|---|---|
| Poison message handling | Defines an exact one-message procedure that exercises the worker reject path, retry cycle, and DLQ routing without speculation |
| DLQ configuration not just declared | Future execution will produce observable evidence: worker error log, DLQ message pull or delivery-attempt count, final safe state -- not just Terraform output |
| Operational safety | Preflight checklist, abort conditions, and risk controls are written down and reviewable before any execution occurs |
| Rollback / abort discipline | Thirteen explicit abort conditions are enumerated; no execution is permitted if any preflight check fails |
| No pollution of validated 50k evidence | Malformed test uses a unique marker and a non-production payload; 50k prefix rows and error log baseline are confirmed as part of acceptance criteria |
| No overclaiming | Status section explicitly states DLQ malformed-message routing NOT YET PROVEN; evidence document is deferred until execution is actually performed |

---

## Safe Interview Wording

"The DLQ policy is already configured and documented. The next validation is a bounded
one-message malformed payload test to prove retry and DLQ routing without starting Cloud
SQL or affecting the healthy 50,000-event evidence path. Until that execution is performed,
malformed-message DLQ routing remains planned, not proven."

---

## Final Verdict

| Item | Assessment |
|---|---|
| Current DLQ configuration evidence | Present -- deadLetterPolicy, maxDeliveryAttempts=5, retryPolicy confirmed in GCP execution evidence and Terraform |
| Malformed-message execution evidence | Not yet proven -- no malformed message has been published; no DLQ routing has been exercised |
| Risk level of future validation | Low if one-message procedure is followed with all preflight checks passing |
| Recruitment value after execution | High -- closes the only remaining gap in the full Pub/Sub reliability story |
| Current branch status | Plan only -- docs-only change; no code, Terraform, dbt, or workflow modifications |
