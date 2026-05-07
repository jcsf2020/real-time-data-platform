# Load-Test 5000-Event Cloud Runbook

## Status

**RUNBOOK ONLY — NOT EXECUTED**

This is an operational runbook. The 5000-event cloud load test has **not been executed**.
No Pub/Sub messages have been published. No Cloud SQL instance has been started. No GCP
resources have been mutated on this branch.

This runbook exists solely to define the precise, reviewable execution sequence for a future
branch or session. Read every command block as documentation, not as executed evidence.

This runbook builds on the **accepted 1000-event cloud evidence** documented in
[docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md). All acceptance
criteria from that run were met. The preconditions and execution sequence below incorporate
all lessons learned from both the 100-event and 1000-event runs.

---

## 1. Scope

### Covered by this runbook

- Third controlled live GCP load test: exactly 5000 valid Pub/Sub messages
- Pre-publish JSONL generation and local validation (deterministic generator path)
- Cloud SQL start / stop protocol (bounded window)
- Pub/Sub publish and backlog observation
- Worker structured log validation (success path only)
- `worker_message_processed_count` Cloud Monitoring timeSeries query
- `worker_message_error_count` verification (must remain 0)
- DLQ topic / subscription backlog verification (must remain empty)
- API `/events` readback (API offset pagination is non-functional — see Section 3 limitations)
- API `/aggregates/minute` readback with field-level and row capture
- Silver refresh job execution and log validation
- Cloud SQL final cost-control state confirmation (`NEVER / STOPPED`)
- Evidence checklist and acceptance criteria

### Explicitly excluded from this runbook

- Malformed or schema-invalid messages
- Intentional DLQ delivery testing
- Any event count beyond 5000 per run
- IaC changes (Terraform or gcloud configuration mutations)
- Alert policy creation or modification
- Notification channel creation or modification
- Production benchmark or SLA claims
- Autoscaling stress or concurrency limit testing
- Multi-region or failover testing
- BigQuery or Dataflow integration
- Worker redeployment or schema changes

---

## 2. Purpose

This runbook prepares the controlled 5000-event cloud load test. The goals are:

- Validate the higher-volume ingest path end-to-end: Pub/Sub → Cloud Run worker → Postgres bronze
- Prove the pipeline holds up under 5000-event pressure with the production DLQ now configured
- Measure processing count, error count, lag, timing, and API visibility at the upper bound of
  the validated test plan
- Preserve cost and risk controls (bounded Cloud SQL window, Scheduler PAUSED, valid events only)
- Avoid synthetic error triggering — no malformed messages, no intentional alert incidents

---

## 3. Current State

| Item | State |
|---|---|
| 100-event cloud load test | Validated — [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) |
| 1000-event cloud load test | Validated — [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) |
| 5000-event cloud load test | **Not executed** — this runbook |
| Worker Cloud Run | Deployed — `rtdp-pubsub-worker` (europe-west1) |
| Pub/Sub topic | `market-events-raw` (ACTIVE) |
| Pub/Sub push subscription | `market-events-raw-worker-push` (ACTIVE, push to worker) |
| DLQ topic | `market-events-raw-dlq` (configured; `maxDeliveryAttempts=5`, 10s/60s backoff) |
| Alert policies | RTDP Worker Message Error Alert, RTDP Silver Refresh Error Alert — both **enabled** |
| Email notification channel | RTDP Operator Email Alerts — **configured**, ID `1439157631105258885` |
| Cloud SQL (`rtdp-postgres`) | Expected `NEVER / STOPPED` before execution |
| Cloud Scheduler (`rtdp-silver-refresh-scheduler`) | **PAUSED** |

### Key differences from the 1000-event run

| Dimension | 1000-event run | 5000-event run |
|---|---|---|
| Event count | 1000 | 5000 |
| Publish time at ≤50 msg/s | ~53 seconds | ~100 seconds |
| DLQ configuration | Not present | Configured (`maxDeliveryAttempts=5`); verify remains empty |
| Scheduler state | N/A | PAUSED — must remain PAUSED throughout |
| Alert policies | Not present | Active — must not fire during valid test |
| Cloud Monitoring DELTA intervals | 2 active intervals | Will spread across 2–4 intervals |
| API `/events` pagination | Non-functional (offset ignored) | Same limitation; ingest confirmed via logs/metric |
| Backlog drain window | ~2–5 minutes | Allow at least 10 minutes |

---

## 4. Proposed Test Design

| Parameter | Value |
|---|---|
| Event count | `5000` |
| Event type | Valid `MarketEvent` objects only — `event_type: "trade"` |
| Malformed messages | None — zero |
| Symbols | `BTCUSDT`, `ETHUSDT`, `SOLUSDT` (same as prior runs) |
| Event ID prefix format | `loadtest-5000-<YYYYMMDDHHMMSS>-` |
| JSONL generation script | `scripts/generate_load_test_events.py --size 5000 --prefix-timestamp <TIMESTAMP>` |
| Publish path | Inline Python script using `google-cloud-pubsub` (same approach as 100/1000-event runs) |
| Target Pub/Sub topic | `market-events-raw` |
| Worker path | Cloud Run push subscription → `rtdp-pubsub-worker` → `bronze.market_events` |
| Database target | `bronze.market_events` (idempotent write, `ON CONFLICT DO NOTHING`) |
| JSONL output path | `docs/evidence/load-test-5000-cloud/events-5000.jsonl` |
| Validator report path | `docs/evidence/load-test-5000-cloud/local-validation-report-5000.json` |
| Evidence document | `docs/load-test-5000-cloud-evidence.md` |

### Observability targets

| Metric / signal | Expected result |
|---|---|
| `worker_message_processed_count` | Increases by approximately 5000 during the run window |
| `worker_message_error_count` | Remains 0 throughout |
| DLQ topic `market-events-raw-dlq` | No messages delivered; backlog remains 0 |
| API `/metrics` | Responsive before and after test |
| API `/events` | Responsive; top rows show prefix-matching event IDs |
| Worker `status=ok` logs | Approach 5000 unique event IDs for the prefix |
| Worker `status=error` logs | Zero for the prefix |
| `bronze.market_events` delta | Approximately +5000 (exact +5000 if no duplicate event IDs exist) |

---

## 5. Safety Constraints

The following are absolute constraints. Do not proceed if any cannot be satisfied.

- **This docs branch does not execute the test.** All command blocks are templates for a future
  execution branch only.
- **Execution branch must start Cloud SQL only for a bounded window.** Cloud SQL must be
  confirmed `NEVER / STOPPED` before and after the test window.
- **Cloud SQL final state must be `NEVER / STOPPED`.** This is a hard cost-control requirement.
- **Scheduler must remain `PAUSED` throughout.** Do not resume, trigger manually, or modify
  the Scheduler during this test.
- **Do not publish malformed messages.** Every published message must be schema-valid
  (`MarketEvent`, `schema_version: "1.0"`, known symbols, positive values).
- **Do not intentionally trigger alert policies.** Valid messages only; error metrics must
  remain 0.
- **Do not change alert policy definitions.** The two enabled policies must remain unchanged.
- **Do not change notification channel configuration.** Channel ID `1439157631105258885` must
  remain attached to both policies.
- **Do not change the DLQ policy.** `market-events-raw-worker-push` dead-letter policy
  (`maxDeliveryAttempts=5`, 10s/60s backoff, routes to `market-events-raw-dlq`) must remain
  unchanged.
- **Do not deploy the worker.** The existing `rtdp-pubsub-worker` revision is the target.
- **Do not change the database schema.** No DDL during the execution window.
- **Do not truncate or delete data.** `bronze.market_events` is append-only; do not truncate
  between or after runs.
- **Do not exceed 5000 events.** If more events are needed, create a new runbook.
- **Stop if worker errors spike.** Any non-zero `worker_message_error_count` or
  `status=error` log for the prefix is an abort signal.
- **Stop if DLQ receives messages.** Any message appearing in `market-events-raw-dlq` is an
  abort signal.
- **Stop if Cloud SQL cost window exceeds the planned bound.** Do not leave Cloud SQL running
  after readback completes.

---

## 6. Placeholders

All future execution commands below use these placeholders. Replace every placeholder before
running any command:

| Placeholder | Meaning |
|---|---|
| `PROJECT_ID` | `project-42987e01-2123-446b-ac7` |
| `REGION` | `europe-west1` |
| `API_URL` | `https://rtdp-api-fpy4of3i5a-ew.a.run.app` |
| `WORKER_URL` | `https://rtdp-pubsub-worker-fpy4of3i5a-ew.a.run.app` |
| `PREFIX_TIMESTAMP` | `YYYYMMDDHHMMSS` determined at execution time (wall-clock before first publish) |
| `START_TIME` | RFC3339 timestamp recorded immediately before publishing begins |
| `END_TIME` | RFC3339 timestamp at least 15 minutes after processing is confirmed complete |

---

## 7. Known Limitations from Prior Runs

These limitations were documented in the 100-event and 1000-event evidence and apply to the
5000-event run unless resolved:

| Limitation | Detail |
|---|---|
| `numUndeliveredMessages` not exposed | `gcloud pubsub subscriptions describe` does not surface backlog for this push subscription. Use worker logs and metric sum as primary drain evidence. |
| Worker health requires OIDC identity token | `GET /health` on the worker returns HTTP 403 without a token. Use `gcloud auth print-identity-token` to authenticate. |
| API `/events` offset pagination non-functional | The `offset` query parameter is accepted but ignored; all calls return the same top 100 rows. At 5000 events, full readback via the API is not possible. Ingest count must be confirmed via worker logs and Cloud Monitoring metric. |

---

## 8. Future Execution Sequence

> **Future execution only — do not run during this runbook branch.**
>
> Every command block in this section is a template for a future execution session.
> No command here has been run. All placeholders must be resolved before execution.
> Stop if any step returns an unexpected result.

---

### A. Pre-flight checks

#### Step 1 — Confirm repo state and branch

```bash
# Verify execution branch is NOT the runbook branch
git branch --show-current

# Confirm git status is clean
git status

# Verify workspace dependencies are resolved
uv sync --all-packages
```

Expected: branch is NOT `docs/load-test-5000-cloud-runbook`; status clean; sync succeeds.

---

#### Step 2 — Run tests and lint

```bash
uv run pytest -q
uv run ruff check .
```

Expected: all tests pass; ruff clean. Abort if either fails.

---

#### Step 3 — Confirm Cloud SQL pre-execution state (read-only)

```bash
gcloud sql instances describe rtdp-postgres \
  --project=$PROJECT_ID \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

**Do not proceed if the state is unexpected.**

---

#### Step 4 — Confirm Scheduler is PAUSED

```bash
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=$REGION \
  --project=$PROJECT_ID \
  --format="value(state)"
```

Expected: `PAUSED`

**Do not proceed if the Scheduler is not PAUSED.**

---

#### Step 5 — Describe Pub/Sub topic

```bash
gcloud pubsub topics describe market-events-raw \
  --project=$PROJECT_ID
```

Expected: topic exists with name `projects/$PROJECT_ID/topics/market-events-raw`.

---

#### Step 6 — Describe push subscription and confirm ACTIVE

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID \
  --format="value(pushConfig.pushEndpoint,state)"
```

Expected: subscription state `ACTIVE`; push endpoint confirmed pointing to worker URL.

---

#### Step 7 — Confirm DLQ dead-letter policy exists

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID \
  --format="value(deadLetterPolicy.deadLetterTopic,deadLetterPolicy.maxDeliveryAttempts)"
```

Expected:
```
projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-dlq   5
```

Abort if the DLQ policy is absent — this is a safety guardrail for bounded failure delivery.

---

#### Step 8 — Confirm alert policies are enabled

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://monitoring.googleapis.com/v3/projects/$PROJECT_ID/alertPolicies" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for p in data.get('alertPolicies', []):
    print(p.get('displayName'), '| enabled:', p.get('enabled'))
"
```

Expected: both `RTDP Worker Message Error Alert` and `RTDP Silver Refresh Error Alert`
are listed with `enabled: True`. Abort if either is missing or disabled.

---

#### Step 9 — Confirm notification channel exists

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://monitoring.googleapis.com/v3/projects/$PROJECT_ID/notificationChannels/1439157631105258885" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('displayName:', data.get('displayName'))
print('enabled:', data.get('enabled'))
print('type:', data.get('type'))
"
```

Expected: `RTDP Operator Email Alerts`, `enabled: True`, `type: email`.

---

#### Step 10 — Capture bronze row count before

```bash
# Requires Cloud SQL to be RUNNABLE — run this step immediately after starting Cloud SQL
# (see Step B below), before publishing.
# Record the count as BRONZE_BEFORE.
```

This step must be executed after Cloud SQL is started (Step B) and before any messages are
published. Record the output as `BRONZE_BEFORE` in the evidence document.

---

#### Step 11 — Capture API health before

```bash
curl $API_URL/health
curl $API_URL/readiness
```

Expected: both return `{"status":"ok"}` or equivalent. Abort if either fails.

---

#### Step 12 — Capture worker logs baseline timestamp

```bash
# Record the timestamp immediately before publish begins.
# This timestamp will be used to scope Cloud Logging queries to the run window.
BASELINE_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "BASELINE_TIMESTAMP=$BASELINE_TIMESTAMP"
```

---

#### Step 13 — Generate 5000-event JSONL locally

```bash
# Record prefix timestamp BEFORE running (wall-clock, YYYYMMDDHHMMSS)
PREFIX_TIMESTAMP=$(date +%Y%m%d%H%M%S)
echo "PREFIX_TIMESTAMP=$PREFIX_TIMESTAMP"

mkdir -p docs/evidence/load-test-5000-cloud

uv run python scripts/generate_load_test_events.py \
  --size 5000 \
  --prefix-timestamp $PREFIX_TIMESTAMP \
  --output docs/evidence/load-test-5000-cloud/events-5000.jsonl
```

Expected: file created with exactly 5000 lines. Verify with `wc -l`.

---

#### Step 14 — Validate JSONL locally

```bash
uv run python scripts/validate_load_test_events.py \
  --input docs/evidence/load-test-5000-cloud/events-5000.jsonl \
  --size 5000 \
  --prefix-timestamp $PREFIX_TIMESTAMP \
  --report-output docs/evidence/load-test-5000-cloud/local-validation-report-5000.json
```

Expected:
```json
{
  "status": "ok",
  "observed_count": 5000,
  "unique_event_ids": 5000,
  "worker_contract_validation": "passed",
  "errors": []
}
```

**Do not proceed if status is not `ok`.**

---

### B. Start Cloud SQL

> Cloud SQL must only be started immediately before publishing. Do not start it idle.
> This opens the cost window. Stop Cloud SQL as soon as all readback evidence is captured.

#### Step 15 — Start Cloud SQL

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS \
  --project=$PROJECT_ID
```

---

#### Step 16 — Poll until RUNNABLE

```bash
# Poll until RUNNABLE (typically 60–90 seconds)
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)" \
  --project=$PROJECT_ID
```

Expected: `ALWAYS   RUNNABLE`

**Do not publish any events while the state is not RUNNABLE.**

---

#### Step 17 — Confirm worker and API health after Cloud SQL starts

```bash
# API health (no auth required)
curl $API_URL/health

# Worker health (identity token required — known Cloud Run IAM behaviour)
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  $WORKER_URL/health
```

Expected: both return `{"status":"ok"}`.

---

#### Step 18 — Capture bronze row count before (BRONZE_BEFORE)

Record the result of this API call as `BRONZE_BEFORE`:

```bash
# Use the API /events to observe the current ingested count baseline
# (exact SQL row count requires direct DB access; use worker logs and metric delta instead)
curl "$API_URL/events?limit=1"
```

Alternatively, note that the authoritative delta will be confirmed via worker logs and
Cloud Monitoring metric sum for the prefix. Record this observation as `BRONZE_BEFORE` in the
evidence document.

---

### C. Publish 5000 valid events

#### Step 19 — Record START_TIME and publish 5000 events

> Record `START_TIME` immediately before publishing.

```bash
START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "START_TIME=$START_TIME"
```

Publish exactly 5000 events from the validated JSONL. The publish command must follow the
same approach used in the 100-event and 1000-event runs (inline Python script using
`google-cloud-pubsub`). Locate or reproduce that script on the execution branch before
running. The key requirements are:

- Publish exactly the 5000 lines from
  `docs/evidence/load-test-5000-cloud/events-5000.jsonl`.
- Each line must be published as a separate Pub/Sub message.
- Throttle to no more than 50 messages/second (estimated publish time: ~100 seconds).
- Stop immediately on any publish error.
- Record the total number of `messageId` values returned.

```python
# Template — execution branch must implement or reproduce this inline script:
#
# import json, time
# from google.cloud import pubsub_v1
#
# publisher = pubsub_v1.PublisherClient()
# topic_path = f"projects/{PROJECT_ID}/topics/market-events-raw"
# count, errors = 0, 0
# with open("docs/evidence/load-test-5000-cloud/events-5000.jsonl") as f:
#     for line in f:
#         future = publisher.publish(topic_path, line.strip().encode("utf-8"))
#         msg_id = future.result()  # stop on exception
#         count += 1
#         if count % 100 == 0:
#             print(f"{count}/5000: {msg_id}")
#         time.sleep(1/50)  # ≤50 msg/s
# print(f"Done: {count} published, {errors} errors")
```

Record the publish summary:

```
# After publishing completes:
# - Total messages published: should equal 5000
# - Total messageId values returned: should equal 5000
# - Total elapsed publish time: record in seconds
# - Error count: must be 0
```

**Abort if any individual message does not return a `messageId`.**

---

#### Step 20 — Record end timestamp

```bash
PUBLISH_END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "PUBLISH_END_TIME=$PUBLISH_END_TIME"
```

---

### D. Observe ingestion

#### Step 21 — Observe Pub/Sub subscription state immediately after publish

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID
```

Note: `numUndeliveredMessages` is not exposed for this push subscription (known limitation
from both prior runs). Record the full output. Drain will be confirmed via worker logs and
metric sum.

---

#### Step 22 — Observe DLQ subscription backlog

Verify the DLQ remains empty throughout the test. Check if a subscription exists on the DLQ
topic:

```bash
gcloud pubsub topics list-subscriptions market-events-raw-dlq \
  --project=$PROJECT_ID
```

If a subscription exists, describe it:

```bash
gcloud pubsub subscriptions describe <DLQ_SUBSCRIPTION_NAME> \
  --project=$PROJECT_ID
```

Expected: no messages delivered to the DLQ. **Abort if any DLQ messages are observed.**

---

#### Step 23 — Wait for processing window

Monitor Cloud Logging for worker `status=ok` entries accumulating for the prefix. At 5000
events the drain window may take 5–15 minutes depending on Cloud Run concurrency and push
subscription delivery rate.

**If no worker logs appear within 5 minutes of publish completion, abort.**

Allow at least 10 minutes from publish end before asserting that drain is complete.

---

#### Step 24 — Query Cloud Logging for worker success logs

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="ok"
jsonPayload.event_id =~ "^loadtest-5000-PREFIX_TIMESTAMP-"
```

Expected: count should approach 5000. Record total count and unique `event_id` count.

---

#### Step 25 — Query Cloud Logging for worker error logs

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="error"
jsonPayload.event_id =~ "^loadtest-5000-PREFIX_TIMESTAMP-"
```

Expected: **zero results.** Any error entries are an abort signal.

---

#### Step 26 — Query Cloud Monitoring for worker_message_processed_count

```bash
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "END_TIME=$END_TIME"

curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://monitoring.googleapis.com/v3/projects/$PROJECT_ID/timeSeries\
?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fworker_message_processed_count%22\
&interval.startTime=$START_TIME\
&interval.endTime=$END_TIME"
```

Expected: datapoints distributed across multiple DELTA intervals; sum of all `int64Value`
values within the window approximately equals 5000. Record the raw JSON response summary —
interval boundaries, per-interval values, and total sum — in the evidence document.

---

#### Step 27 — Query Cloud Monitoring for worker_message_error_count

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://monitoring.googleapis.com/v3/projects/$PROJECT_ID/timeSeries\
?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fworker_message_error_count%22\
&interval.startTime=$START_TIME\
&interval.endTime=$END_TIME"
```

Expected: either no timeSeries returned, or all datapoints equal 0. Any non-zero value is an
abort signal.

---

#### Step 28 — Query API /metrics

```bash
curl "$API_URL/metrics"
```

Expected: endpoint responds with pipeline metric time-series. Record the result.

---

#### Step 29 — Query API /events for prefix-related records

```bash
# API enforces a maximum of 100 rows regardless of limit (known from 1000-event run)
curl "$API_URL/events?limit=100"
```

Filter the response for records whose `event_id` starts with `loadtest-5000-$PREFIX_TIMESTAMP-`.
Record the count of prefix-matching rows in the top 100. Full ingest count is confirmed via
worker logs (Step 24) and Cloud Monitoring metric (Step 26).

---

#### Step 30 — Run silver refresh job

Run only after ingest and processing window are confirmed (Steps 23–25).

```bash
gcloud run jobs execute rtdp-silver-refresh-job \
  --region=$REGION \
  --project=$PROJECT_ID \
  --wait
```

Wait for the job execution to complete before proceeding to readback. Record the execution
name returned by the command.

---

#### Step 31 — Query Cloud Logging for silver refresh success

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="ok"
```

Expected: one `status=ok` entry for the execution triggered in Step 30.

---

#### Step 32 — Query API /aggregates/minute

```bash
curl "$API_URL/aggregates/minute?limit=50"
```

Capture:
- Total row count returned
- All field names present in the response objects
- At least one complete row sample as raw JSON
- Symbols present in the response
- Whether the number of rows is greater than the 1000-event run (50 rows returned in that run)

**Do not stop Cloud SQL before this evidence is captured.**

---

### E. Stop Cloud SQL

> This must be the first action after all readback evidence is collected. Do not defer.

#### Step 33 — Stop Cloud SQL

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER \
  --project=$PROJECT_ID
```

---

#### Step 34 — Poll until STOPPED

```bash
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)" \
  --project=$PROJECT_ID
```

Expected: `NEVER   STOPPED`

**The execution window is not closed until this is confirmed and recorded.**

---

### F. Final validation

#### Step 35 — Run tests and lint after evidence collection

```bash
uv run pytest -q
uv run ruff check .
```

Expected: all tests pass; ruff clean.

---

#### Step 36 — Confirm Scheduler is still PAUSED

```bash
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=$REGION \
  --project=$PROJECT_ID \
  --format="value(state)"
```

Expected: `PAUSED`

---

#### Step 37 — Confirm Cloud SQL is NEVER / STOPPED (final)

```bash
gcloud sql instances describe rtdp-postgres \
  --project=$PROJECT_ID \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

---

#### Step 38 — Record git status

```bash
git status --short --branch
```

Expected: only the new evidence file and any generated JSONL / validator report files are
changed. No application code, test files, or infrastructure files are modified.

---

## 9. Metrics to Collect

Capture all of the following in the evidence document:

| Metric | Value (to be filled on execution branch) |
|---|---|
| `started_at` UTC (START_TIME) | |
| `finished_at` UTC (PUBLISH_END_TIME) | |
| `duration_seconds` (publish elapsed) | |
| `publish_count` | |
| `message_id_count` | |
| `publish_error_count` | |
| `bronze_before` (row count or API baseline) | |
| `bronze_after` (API + worker log count) | |
| `bronze_delta` (should be ≈ +5000) | |
| `processed_metric_delta` (sum of DELTA intervals) | |
| `error_metric_delta` (must be 0) | |
| `DLQ_messages` (must be 0) | |
| `API_health_status_before` | |
| `API_metrics_result` | |
| `API_events_prefix_matching_rows` (top 100 visible) | |
| `worker_ok_log_count` | |
| `worker_error_log_count` (must be 0) | |
| `cloud_sql_final_state` | |
| `scheduler_final_state` | |

---

## 10. Acceptance Criteria

The execution run is accepted only if **all** of the following are true:

| Criterion | Required |
|---|---|
| Pub/Sub publish acknowledgements / message IDs | Exactly 5000 |
| Local validator report status | `ok` |
| Worker `status=error` logs for prefix | Zero |
| Worker `status=ok` logs for prefix | Approach 5000; target exactly 5000 if logs fully returned |
| `worker_message_processed_count` metric sum in window | Approximately 5000 (sum across all DELTA intervals) |
| `worker_message_error_count` in window | 0 (no non-zero datapoints) |
| DLQ topic `market-events-raw-dlq` | No messages delivered |
| API `/events` responds and returns prefix-matching rows | At least one row visible in top 100 |
| API `/metrics` responds | Yes |
| Pub/Sub backlog final state | 0 or near 0 (confirmed via 5000 ok logs + metric sum if not directly observable) |
| Silver refresh job | Emits `status=ok` in Cloud Logging |
| API `/aggregates/minute` rows after refresh | At least one; more rows than 1000-event run |
| API `/aggregates/minute` field names | Captured |
| Cloud SQL final state | `NEVER   STOPPED` |
| Scheduler final state | `PAUSED` |
| Alert policies not triggered | No unexpected incident fired during test |
| Tests after evidence doc | Pass |
| Ruff after evidence doc | Pass |
| Evidence document created | `docs/load-test-5000-cloud-evidence.md` committed on execution branch |

---

## 11. Stop Conditions

Abort execution immediately (stop publishing or stop the current step; do not proceed to
readback) if any of the following are observed:

| Condition | Action |
|---|---|
| Cloud SQL fails to start or does not reach `RUNNABLE` | Abort; record state; do not publish |
| Cloud SQL cannot be returned to `NEVER / STOPPED` | Do not close execution window until resolved |
| Pub/Sub topic `market-events-raw` is missing or inactive | Abort before publishing |
| Push subscription `market-events-raw-worker-push` is not `ACTIVE` | Abort before publishing |
| DLQ policy is absent on push subscription | Abort — policy must exist before running |
| Worker or API health check fails before test | Abort before publishing |
| API unavailable before test begins | Abort before publishing |
| Any individual publish call fails to return a `messageId` | Stop publishing immediately |
| Message ID count after publish != 5000 | Treat as failure |
| `worker_message_error_count` metric increases | Stop immediately; record state |
| Worker `status=error` logs appear for the prefix | Stop immediately; record state |
| DLQ receives any messages | Stop immediately; record state |
| Alert incidents fire unexpectedly | Investigate before continuing |
| Worker `status=ok` log count stalls far below expected after 10 minutes | Investigate; abort if not recovering |
| Publish script would generate or could generate malformed events | Abort; do not run |
| Publish rate exceeds 50 msg/s or scope exceeds 5000 events | Abort; do not run |
| Row count delta is inconsistent and unexplained after drain | Record as failure; investigate before retrying |
| Cloud SQL cost window runs unexpectedly long | Stop; patch NEVER immediately |
| Scheduler is not `PAUSED` before or during execution | Abort; do not start Cloud SQL |
| Any command would deploy, mutate infrastructure, or modify alert policies | Abort |

On abort: record the abort condition, the last known published count, and the Cloud SQL
state at the time of abort. Do not attempt the same run again without diagnosing the cause.

---

## 12. Rollback and Cleanup

If the test must be aborted or rolled back:

- **Stop publishing immediately.** Do not attempt to complete the run if any stop condition
  fires.
- **Do not delete ingested data.** Leave any partially-ingested events in `bronze.market_events`.
  The `event_id` prefix is a unique traceable scope — partial data does not corrupt other data.
- **Do not truncate bronze.** The table is append-only and idempotent.
- **Stop Cloud SQL immediately.** Issue `--activation-policy=NEVER` and poll until `STOPPED`
  regardless of the abort cause.
- **Keep any DLQ messages for inspection.** If the DLQ received messages, do not purge them
  before diagnosing the root cause.
- **Capture errors and logs.** Record the error state, last published count, Cloud Logging
  query results, and Cloud SQL state in the evidence document before closing the branch.
- **Do not retry blindly.** Diagnose the abort cause before attempting another run. Update
  this runbook or create a new one if the scope changes.
- **Document partial results.** If 3000 of 5000 events were published before abort, record
  that clearly. Partial evidence is better than silence.

---

## 13. Evidence to Capture in Future Execution Branch

The execution branch must create `docs/load-test-5000-cloud-evidence.md` containing all of
the following:

| # | Evidence item |
|---|---|
| 1 | Branch name (must not be `docs/load-test-5000-cloud-runbook`) |
| 2 | Pre-flight: git status, uv sync, pytest, ruff, Cloud SQL NEVER/STOPPED, Scheduler PAUSED |
| 3 | DLQ policy confirmed on push subscription |
| 4 | Alert policies confirmed enabled |
| 5 | Notification channel confirmed |
| 6 | Generated JSONL file path and line count |
| 7 | Local validator report — `status=ok`, `observed_count=5000` |
| 8 | PREFIX_TIMESTAMP value recorded before publishing |
| 9 | Cloud SQL start command output and RUNNABLE confirmation |
| 10 | Worker and API health check responses before test |
| 11 | Bronze row count / baseline before publish |
| 12 | Exact publish command or script used |
| 13 | START_TIME (RFC3339, recorded before first publish) |
| 14 | PUBLISH_END_TIME (RFC3339, recorded after last publish) |
| 15 | Publish summary: count, message ID count, error count, elapsed seconds |
| 16 | Sample message IDs at intervals (every 500 events) |
| 17 | Pub/Sub subscription describe output immediately after publish |
| 18 | DLQ backlog verification (must be 0) |
| 19 | Worker `status=ok` log count and unique event_id count for prefix |
| 20 | Worker `status=error` log count for prefix (must be 0) |
| 21 | Cloud Monitoring `worker_message_processed_count` raw timeSeries JSON (sum must ≈ 5000) |
| 22 | Cloud Monitoring `worker_message_error_count` timeSeries (must be 0) |
| 23 | API `/metrics` response |
| 24 | API `/events` response (prefix-matching rows in top 100) |
| 25 | Silver refresh execution name (from `gcloud run jobs execute`) |
| 26 | Silver refresh Cloud Logging `status=ok` entry |
| 27 | API `/aggregates/minute` row count, field names, and at least one row sample |
| 28 | Cloud SQL final state: `NEVER   STOPPED` |
| 29 | Scheduler final state: `PAUSED` |
| 30 | Final tests: `uv run pytest -q` — pass |
| 31 | Final ruff: `uv run ruff check .` — pass |
| 32 | Explicit confirmation: no deployment performed |
| 33 | Explicit confirmation: no schema change performed |
| 34 | Explicit confirmation: no data deletion performed |
| 35 | Explicit confirmation: no alert policy or notification channel modified |
| 36 | Explicit confirmation: DLQ policy unchanged |

---

## 14. What This Runbook Does Not Do

This document is a runbook only. It does not:

- Execute the 5000-event test now
- Publish Pub/Sub messages now
- Start Cloud SQL now
- Validate 5000 events now
- Change the DLQ policy, alert policies, or notification channels
- Add BigQuery or Dataflow integration
- Add Terraform or IaC
- Deploy the worker
- Modify any GCP resource

---

## 15. Roadmap Position

After this runbook is executed on a future branch and the evidence document is merged:

- The **5000-event load test gap will be closed** — the final tier of the bounded throughput
  validation plan (100 / 1000 / 5000) will be complete.
- The **scale and throughput story becomes stronger**: 50× the 100-event baseline, with full
  log, metric, and API readback evidence.
- Recruiter and B2B positioning improves: the project will demonstrate controlled throughput
  at 5000 events with DLQ safety, active alert policies, and email notification channels — all
  validated on a real GCP MVP.

### Remaining gaps after future 5000-event execution

| Gap | Priority | Notes |
|---|---|---|
| Terraform / IaC | P1 | All GCP resources created imperatively; no Terraform state |
| BigQuery / Dataflow analytical tier | P1 | Silver layer is operational only; no analytical tier |
| CI/CD deploy automation | P1/P2 | All deployments are manual; no automated pipeline |
| README stale GCP wording cleanup | P2 | GCP section wording predates several completed execution branches |

---

## Related Documents

| Document | Relationship |
|---|---|
| [docs/load-test-plan.md](load-test-plan.md) | Full load-test plan covering all test sizes, backlog observation, cost-control protocol, and acceptance criteria |
| [docs/load-test-100-cloud-runbook.md](load-test-100-cloud-runbook.md) | Runbook for the 100-event run |
| [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) | Accepted 100-event cloud evidence |
| [docs/load-test-1000-cloud-runbook.md](load-test-1000-cloud-runbook.md) | Runbook for the 1000-event run |
| [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) | Accepted 1000-event cloud evidence — immediate precondition for this runbook |
| [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) | DLQ configuration evidence — confirms `deadLetterPolicy` on push subscription |
| [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) | Alert policies evidence — both policies enabled; must remain enabled during test |
| [docs/notification-channels-evidence.md](notification-channels-evidence.md) | Notification channel evidence — email channel attached to both alert policies |
| [docs/silver-refresh-scheduler-execution-proof-evidence.md](silver-refresh-scheduler-execution-proof-evidence.md) | Scheduler execution proof — Scheduler PAUSED after validated execution |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Cloud Monitoring REST API query method used for metric timeSeries steps |
| [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) | Original DLQ inspection — pre-DLQ baseline |
| [docs/gcp-architecture.md](gcp-architecture.md) | Full GCP architecture reference |
| [docs/gcp-worker-cloud-validation.md](gcp-worker-cloud-validation.md) | Worker deployment and Cloud validation reference |
