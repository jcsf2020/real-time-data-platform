# Cloud Load Test -- 10,000-Event Plan

## Status

**PLANNED -- 10,000-EVENT CLOUD LOAD TEST NOT YET EXECUTED**

This document is a forward-looking plan only. No events have been published, no Cloud SQL
instance has been started, no Terraform apply has been executed, and no GCP resources have
been mutated. All execution commands are written for a future controlled execution branch.
Do not act on these commands in this docs branch.

---

## 1. Purpose

The accepted 100 / 1,000 / 5,000-event bounded load tests
([docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md)) establish a
measured baseline for the current Pub/Sub → Cloud Run worker → Cloud SQL path. The 5,000-event
run validated deterministic end-to-end ingest with zero errors and a clean DLQ under observed
GCP managed-service conditions.

This plan extends that baseline to 10,000 events. The specific goals are:

- Demonstrate that the platform handles a sustained publish volume of 10,000 events
  without worker errors, DLQ delivery, or Cloud SQL write failures.
- Capture a measured ingest throughput data point above the 5,000-event ceiling.
- Validate the idempotency contract at scale: zero duplicate `event_id` values in
  `bronze.market_events` after the run.
- Establish the current-stack throughput limit range before any architectural change
  is introduced.

### Why this comes before Dataflow

Dataflow is not yet implemented in this repository (see
[docs/portfolio-b2b-narrative.md](portfolio-b2b-narrative.md) for the explicit non-claim).
Introducing Dataflow before the current stack is better characterised would replace an
unmeasured bottleneck with a new architecture: the resulting evidence would describe the
Dataflow pipeline, not the current stack, and the comparison baseline would be lost.

The correct sequencing is:

1. Validate 10,000 events on the current Pub/Sub → Cloud Run → Cloud SQL path.
2. Validate 50,000 events on the current stack (or identify the throughput ceiling).
3. Introduce Dataflow after the current-stack limit is measured and documented.

This order means any future Dataflow evidence can reference a concrete prior baseline,
rather than comparing against an assumption.

---

## 2. Scope

### In scope

- Generate 10,000 deterministic `MarketEvent`-compatible events using the existing
  load-test generator script (with `ALLOWED_SIZES` extended to include `10000` in the
  execution branch — see Preconditions, section 5).
- Validate the generated JSONL file locally using the existing validator script.
- Publish all 10,000 events to the production Pub/Sub topic `market-events-raw`.
- Observe Cloud Run worker processing via structured logs and Cloud Monitoring metric.
- Confirm the DLQ (`market-events-raw-dlq`) received zero messages.
- Confirm `bronze.market_events` row count increases by the expected amount.
- Confirm zero duplicate `event_id` values in `bronze.market_events` after the run.
- Confirm Cloud SQL is restored to `NEVER / STOPPED` after the run.
- Confirm both schedulers remain `PAUSED` throughout.
- Confirm Terraform plan returns `PLAN_EXIT=0` after the run.

### Out of scope

- Malformed or schema-invalid messages
- Retry or DLQ testing on the production push subscription
- Any event count beyond 10,000 in this plan
- Schema changes, migration testing, or dbt model changes
- Dataflow implementation or testing
- Autoscaling stress or concurrency limit testing
- IaC changes (Terraform or gcloud config mutations)
- Alert policy creation or modification
- Multi-region validation

---

## 3. Explicit Non-Claims

This plan document makes none of the following claims:

- **This plan does not execute the test.** Execution happens in a future branch named
  `exec/cloud-load-test-10000-evidence` or equivalent.
- **This plan does not prove 10,000-event throughput.** No events have been published
  and no metrics have been captured.
- **This plan does not prove sustained production throughput.** Each run is a bounded
  burst, not a continuous streaming workload.
- **This plan does not implement Dataflow.** The Cloud Run worker remains the processing
  path. No Dataflow pipeline exists in this repository.
- **This plan does not prove 50,000 / 100,000 / 500,000 events.** Those are future plans
  contingent on the 10,000-event evidence outcome.
- **This plan does not mutate GCP resources.** No `gcloud` mutation commands, no
  `terraform apply`, no event publishing, and no Cloud SQL start are performed in this
  docs branch.

---

## 4. Script Constraint: ALLOWED_SIZES

The generator and validator scripts currently only accept sizes in `{100, 1000, 5000}`:

- `scripts/generate_load_test_events.py:11` — `ALLOWED_SIZES = frozenset({100, 1000, 5000})`
- `scripts/validate_load_test_events.py:11` — `ALLOWED_SIZES = frozenset({100, 1000, 5000})`

The execution branch must add `10000` to `ALLOWED_SIZES` in both scripts and update the
corresponding tests in `tests/test_generate_load_test_events.py` and
`tests/test_validate_load_test_events.py` before any generate or validate commands can run.
This is a code change — it must not be made in this docs-only branch.

---

## 5. Preconditions

All of the following must be confirmed before execution begins in the future branch.

| Precondition | How to verify | Required state |
|---|---|---|
| Execution branch is correct | `git branch --show-current` | `exec/cloud-load-test-10000-evidence` (or documented equivalent) |
| Working tree is clean | `git status` | No uncommitted changes |
| `ALLOWED_SIZES` extended | grep ALLOWED_SIZES in both scripts | `{100, 1000, 5000, 10000}` |
| All tests pass | `uv run pytest -q` | All tests pass |
| Ruff clean | `uv run ruff check .` | `All checks passed!` |
| Cloud SQL initial state | `gcloud sql instances describe rtdp-postgres` | `NEVER STOPPED` |
| Both schedulers | `gcloud scheduler jobs list` | Both `PAUSED` |
| Pub/Sub topic exists | `gcloud pubsub topics describe market-events-raw` | Topic present |
| Push subscription active | `gcloud pubsub subscriptions describe market-events-raw-worker-push` | `state: ACTIVE` |
| DLQ dead-letter policy | subscription describe output | `deadLetterTopic`, `maxDeliveryAttempts=5` present |
| DLQ topic exists | `gcloud pubsub topics describe market-events-raw-dlq` | Topic present |
| Cloud Run worker deployed | `gcloud run services describe rtdp-pubsub-worker` | Service exists |
| Terraform zero-diff | `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode` | `PLAN_EXIT=0` |
| gcloud authenticated | `gcloud auth print-identity-token` | Token returned |
| Cost-control accepted | Operator confirms understanding | Cloud SQL must be returned to `NEVER / STOPPED` |

---

## 6. Future Execution Commands

> **These commands are for the future execution branch only.**
> Do not run them in this docs branch. Do not run them before all preconditions are confirmed.
> Each block is labelled with its step. Run sequentially unless otherwise noted.

---

### Step 0 — Inspect branch and working tree

```bash
git branch --show-current
git status
```

Expected: branch is the execution branch; status is clean.

---

### Step 1 — Run pre-execution checks

```bash
uv run pytest -q
uv run ruff check .
```

Expected: all tests pass, ruff clean.

---

### Step 2 — Inspect Cloud SQL state (read-only)

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

Record as: `CLOUD_SQL_PRE_10000_BASELINE=NEVER_STOPPED`

---

### Step 3 — Inspect scheduler state (read-only)

```bash
gcloud scheduler jobs list \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state,schedule)"
```

Expected: both `rtdp-silver-refresh-scheduler` and `rtdp-bigquery-append-scheduler`
show `PAUSED`.

Record as: `SCHEDULERS_PRE_10000_BASELINE=BOTH_PAUSED`

---

### Step 4 — Inspect Pub/Sub topic, push subscription, and DLQ state (read-only)

```bash
# Production topic
gcloud pubsub topics describe market-events-raw \
  --project=project-42987e01-2123-446b-ac7

# Push subscription (confirm ACTIVE and DLQ policy)
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7

# DLQ topic
gcloud pubsub topics describe market-events-raw-dlq \
  --project=project-42987e01-2123-446b-ac7

# DLQ subscriptions (should be 0)
gcloud pubsub topics list-subscriptions market-events-raw-dlq \
  --project=project-42987e01-2123-446b-ac7
```

Expected:
- `market-events-raw` topic is present.
- `market-events-raw-worker-push` subscription `state: ACTIVE` with `deadLetterTopic`
  and `maxDeliveryAttempts: 5`.
- `market-events-raw-dlq` topic is present.
- DLQ subscription list returns 0 items.

Record as: `DLQ_POLICY_PRE_10000_VALIDATED=true`

---

### Step 5 — Inspect Cloud Run worker service (read-only)

```bash
gcloud run services describe rtdp-pubsub-worker \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(status.url,status.conditions[0].type,status.conditions[0].status)"
```

Also confirm worker health (requires identity token):

```bash
TOKEN=$(gcloud auth print-identity-token)
curl -sf -H "Authorization: Bearer ${TOKEN}" \
  https://rtdp-pubsub-worker-fpy4of3i5a-ew.a.run.app/health
```

Expected: `{"status":"ok"}`

---

### Step 6 — Confirm Terraform zero-diff (read-only)

```bash
terraform -chdir=infra/terraform/gcp plan \
  -detailed-exitcode \
  -input=false
echo "PLAN_EXIT=$?"
```

Expected: `PLAN_EXIT=0`

Do not proceed if `PLAN_EXIT` is not `0`.

---

### Step 7 — Generate 10,000 deterministic events (local, no GCP contact)

```bash
# Record the prefix timestamp before generating
PREFIX_TIMESTAMP=$(date -u +%Y%m%d%H%M%S)
echo "PREFIX_TIMESTAMP=${PREFIX_TIMESTAMP}"

mkdir -p docs/evidence/load-test-10000-cloud

uv run python scripts/generate_load_test_events.py \
  --size 10000 \
  --prefix-timestamp ${PREFIX_TIMESTAMP} \
  --output docs/evidence/load-test-10000-cloud/events-10000.jsonl

wc -l docs/evidence/load-test-10000-cloud/events-10000.jsonl
```

Expected: 10000 lines.

> Note: requires `10000` to be in `ALLOWED_SIZES` in the generator script — see section 4.

---

### Step 8 — Validate generated events (local, no GCP contact)

```bash
uv run python scripts/validate_load_test_events.py \
  --input docs/evidence/load-test-10000-cloud/events-10000.jsonl \
  --size 10000 \
  --prefix-timestamp ${PREFIX_TIMESTAMP} \
  --report-output docs/evidence/load-test-10000-cloud/local-validation-report-10000.json

cat docs/evidence/load-test-10000-cloud/local-validation-report-10000.json
```

Expected: `"status": "ok"`, `"observed_count": 10000`, `"unique_event_ids": 10000`,
`"worker_contract_validation": "passed"`, `"errors": []`.

Record as: `LOAD_TEST_10000_LOCAL_VALIDATION_PASSED=true`

---

### Step 9 — Start Cloud SQL (bounded window begins here)

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS \
  --project=project-42987e01-2123-446b-ac7
```

---

### Step 10 — Wait until Cloud SQL is RUNNABLE

```bash
# Poll until RUNNABLE
until gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)" | grep -q "RUNNABLE"; do
  echo "Waiting for RUNNABLE..."; sleep 10
done

gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `ALWAYS   RUNNABLE`

Also confirm API readiness:

```bash
curl -sf https://rtdp-api-fpy4of3i5a-ew.a.run.app/readiness
```

Expected: `{"status":"ready","service":"rtdp-api","database":"reachable"}`

---

### Step 11 — Publish 10,000 events to Pub/Sub

```bash
# Record publish start time before first message
START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "START_TIME=${START_TIME}"

# Publish using google-cloud-pubsub Python client at ≤50 msg/s
# The inline publish script (or equivalent to the 5k run) reads events-10000.jsonl
# and publishes each event as a JSON-encoded Pub/Sub message, printing progress
# checkpoints every 500 messages.
#
# Example inline publish loop (adapt from the 5k runbook approach):
python3 - <<'EOF'
import json, time
from google.cloud import pubsub_v1

PROJECT_ID = "project-42987e01-2123-446b-ac7"
TOPIC_ID   = "market-events-raw"
INPUT_FILE = "docs/evidence/load-test-10000-cloud/events-10000.jsonl"
RATE_LIMIT = 50  # messages per second

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

with open(INPUT_FILE) as fh:
    lines = [l.strip() for l in fh if l.strip()]

published = 0
message_ids = []
errors = 0
start = time.monotonic()

for i, line in enumerate(lines, 1):
    future = publisher.publish(topic_path, line.encode("utf-8"))
    try:
        message_ids.append(future.result(timeout=30))
        published += 1
    except Exception as e:
        print(f"ERROR at line {i}: {e}")
        errors += 1
        raise SystemExit(1)

    elapsed = time.monotonic() - start
    expected_elapsed = published / RATE_LIMIT
    if expected_elapsed > elapsed:
        time.sleep(expected_elapsed - elapsed)

    if i % 500 == 0:
        print(f"PUBLISHED {i}/{len(lines)}  latest_message_id={message_ids[-1]}")

print(f"PUBLISHED_TOTAL={published}")
print(f"UNIQUE_MESSAGE_IDS={len(set(message_ids))}")
print(f"PUBLISH_ERROR_COUNT={errors}")
PUBLISH_END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "PUBLISH_END_TIME=${PUBLISH_END_TIME}"
EOF
```

Expected: `PUBLISHED_TOTAL=10000`, `UNIQUE_MESSAGE_IDS=10000`, `PUBLISH_ERROR_COUNT=0`.

Record `PUBLISH_END_TIME` immediately after the script exits.

---

### Step 12 — Query worker logs (success path)

Wait for at least 5 minutes after `PUBLISH_END_TIME` before querying to allow the Pub/Sub
push subscription to drain.

```bash
# Adjust START_TIME and PUBLISH_END_TIME window as recorded in step 11.
# Add 15 minutes to PUBLISH_END_TIME for the query end window.

gcloud logging read \
  "resource.type=\"cloud_run_revision\"
   resource.labels.service_name=\"rtdp-pubsub-worker\"
   jsonPayload.operation=\"process_message\"
   jsonPayload.status=\"ok\"
   jsonPayload.event_id =~ \"^loadtest-10000-${PREFIX_TIMESTAMP}-\"" \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(jsonPayload.event_id)" \
  --limit=10000 | sort -u | wc -l
```

Expected: 10000 unique `event_id` values.

Query error path (must return 0):

```bash
gcloud logging read \
  "resource.type=\"cloud_run_revision\"
   resource.labels.service_name=\"rtdp-pubsub-worker\"
   jsonPayload.operation=\"process_message\"
   jsonPayload.status=\"error\"
   jsonPayload.event_id =~ \"^loadtest-10000-${PREFIX_TIMESTAMP}-\"" \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=1
```

Expected: zero results.

---

### Step 13 — Query worker processed and error metrics via Cloud Monitoring REST API

The `gcloud monitoring` CLI does not expose `time-series` subcommands in the installed SDK
version (confirmed in prior load tests). Use the Cloud Monitoring REST API directly:

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT_ID=project-42987e01-2123-446b-ac7

# Adjust interval to START_TIME and at least 15 minutes after PUBLISH_END_TIME
START_QUERY="<START_TIME>"
END_QUERY="<END_TIME>"

curl -s \
  "https://monitoring.googleapis.com/v3/projects/${PROJECT_ID}/timeSeries" \
  "?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fworker_message_processed_count%22" \
  "&interval.startTime=${START_QUERY}" \
  "&interval.endTime=${END_QUERY}" \
  -H "Authorization: Bearer ${TOKEN}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
total = sum(
    int(p['value']['int64Value'])
    for ts in data.get('timeSeries', [])
    for p in ts.get('points', [])
)
print(f'PROCESSED_TOTAL: {total}')
print(f'TIME_SERIES_COUNT: {len(data.get(\"timeSeries\", []))}')
"

# Error metric (should return 0 timeSeries or TOTAL=0)
curl -s \
  "https://monitoring.googleapis.com/v3/projects/${PROJECT_ID}/timeSeries" \
  "?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fworker_message_error_count%22" \
  "&interval.startTime=${START_QUERY}" \
  "&interval.endTime=${END_QUERY}" \
  -H "Authorization: Bearer ${TOKEN}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
total = sum(
    int(p['value']['int64Value'])
    for ts in data.get('timeSeries', [])
    for p in ts.get('points', [])
)
print(f'ERROR_TOTAL: {total}')
print(f'TIME_SERIES_COUNT: {len(data.get(\"timeSeries\", []))}')
"
```

Expected:
- `PROCESSED_TOTAL` approximately 10,000 (DELTA window boundaries may cause a small gap
  from the log count; worker structured logs are the authoritative ingest count — see the
  5k run explanation in [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md)
  section 6.3).
- `ERROR_TOTAL: 0`

---

### Step 14 — Inspect DLQ count

```bash
gcloud pubsub topics list-subscriptions market-events-raw-dlq \
  --project=project-42987e01-2123-446b-ac7
```

Expected: `Listed 0 items.`

If any subscriptions are listed, inspect the subscription's undelivered message count before
restoring Cloud SQL.

---

### Step 15 — Query Cloud SQL row count

```bash
TOKEN=$(gcloud auth print-identity-token)
curl -sf \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://rtdp-api-fpy4of3i5a-ew.a.run.app/events?limit=1"
```

For exact row counts, connect directly via Cloud SQL Auth Proxy or the Cloud SQL Admin API.
Record the row count in `bronze.market_events` before and after the run.

Alternatively, query via the Cloud SQL Admin API or note the count via API `/events` pagination.

---

### Step 16 — Query duplicate event_id count in Cloud SQL

```bash
# Via Cloud SQL Auth Proxy (once connected):
psql -c "
SELECT COUNT(*) AS duplicate_event_id_count
FROM (
    SELECT event_id, COUNT(*) AS n
    FROM bronze.market_events
    WHERE event_id LIKE 'loadtest-10000-${PREFIX_TIMESTAMP}-%'
    GROUP BY event_id
    HAVING COUNT(*) > 1
) t;
"
```

Expected: `duplicate_event_id_count = 0`

---

### Step 17 — Restore Cloud SQL to NEVER (cost-control — mandatory)

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER \
  --project=project-42987e01-2123-446b-ac7
```

---

### Step 18 — Wait until Cloud SQL is STOPPED/NEVER

```bash
until gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)" | grep -q "STOPPED"; do
  echo "Waiting for STOPPED..."; sleep 10
done

gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

---

### Step 19 — Confirm schedulers PAUSED

```bash
gcloud scheduler jobs list \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state)"
```

Expected: both schedulers show `PAUSED`.

---

### Step 20 — Confirm Terraform plan PLAN_EXIT=0

```bash
terraform -chdir=infra/terraform/gcp plan \
  -detailed-exitcode \
  -input=false
echo "PLAN_EXIT=$?"
```

Expected: `PLAN_EXIT=0`

---

## 7. Acceptance Criteria

All criteria must be met before this test is accepted. Any unmet criterion must be explicitly
documented with a root cause before the evidence document is closed.

| Criterion | Required |
|---|---|
| 10,000 events generated | JSONL file contains exactly 10,000 lines |
| Local validation passes | Validator exits `status: ok`, `unique_event_ids: 10000`, `errors: []` |
| Publish command succeeds | 10,000 unique `messageId` values returned, `PUBLISH_ERROR_COUNT=0` |
| Worker processed count increases by 10,000 | Worker `status=ok` log count for the run prefix = 10,000; Cloud Monitoring metric sum ≥ 9,900 or deviations explained |
| Worker error count remains 0 | `worker_message_error_count` metric `TOTAL=0`; zero `status=error` logs for the prefix |
| DLQ remains 0 | `gcloud pubsub topics list-subscriptions market-events-raw-dlq` returns 0 items |
| Cloud SQL row count increases by expected amount | Row count in `bronze.market_events` increases by 10,000 or duplicate / idempotent re-run behaviour is explicitly documented |
| Duplicate event_id count remains 0 | `duplicate_event_id_count = 0` for the run prefix |
| Cloud SQL final state is STOPPED/NEVER | `NEVER   STOPPED` confirmed before evidence doc is closed |
| Schedulers final state is PAUSED | Both schedulers `PAUSED` after the run |
| Terraform plan returns PLAN_EXIT=0 | Post-run plan confirms no drift |
| No secrets printed | No credentials, tokens, or secrets appear in any captured output |
| Evidence document created | New `docs/load-test-10000-cloud-evidence.md` committed in the execution branch |

---

## 8. Evidence Fields to Capture

The execution evidence document must include a table with at least the following fields.

| Field | Value (fill at execution time) |
|---|---|
| Branch | `exec/cloud-load-test-10000-evidence` |
| Date / time UTC | YYYY-MM-DD HH:MM:SSZ |
| Operator | (name) |
| Event count | 10000 |
| Generated event file path | `docs/evidence/load-test-10000-cloud/events-10000.jsonl` |
| Validation result | `ok` / `error` |
| Publish result | `PUBLISHED_TOTAL=10000`, `UNIQUE_MESSAGE_IDS=10000`, `PUBLISH_ERROR_COUNT=0` |
| Pub/Sub topic | `market-events-raw` |
| Worker service | `rtdp-pubsub-worker` |
| Cloud SQL state before | `NEVER STOPPED` |
| Cloud SQL state after | `NEVER STOPPED` |
| Scheduler state before | Both `PAUSED` |
| Scheduler state after | Both `PAUSED` |
| Worker `status=ok` log count | (observed value) |
| Worker `status=error` log count | 0 |
| `worker_message_processed_count` metric total | (observed sum) |
| `worker_message_error_count` metric total | 0 |
| DLQ subscription count | 0 |
| Cloud SQL row count before | (observed value) |
| Cloud SQL row count after | (observed value) |
| Row count delta | (after minus before; expected 10000) |
| Duplicate `event_id` count | 0 |
| Terraform plan exit code | 0 |
| GCP log query time window | `START_TIME` to `END_TIME` |
| Known anomalies | (none / documented deviations) |
| PREFIX_TIMESTAMP | `YYYYMMDDHHMMSS` (actual value) |
| Publish elapsed seconds | (observed value) |

---

## 9. Risks

| Risk | Description | Mitigation |
|---|---|---|
| Pub/Sub backlog risk | 10,000 messages may accumulate faster than the worker drains them. If the push subscription backlog does not begin draining within 5 minutes of publish completion, treat as an abort condition. | Wait at least 10 minutes after `PUBLISH_END_TIME` before asserting drain; abort if backlog is not draining. |
| Cloud Run cold start / scaling delay | The worker scales from 0 and has `max_instance_count=1`. At sustained 50 msg/s the single worker instance may experience queue pressure. | Publish at ≤50 msg/s; monitor error logs; abort on any `status=error` entries. |
| Cloud SQL write pressure | 10,000 idempotent inserts into `bronze.market_events` are significantly more than prior runs. Row lock contention or disk pressure is possible on the `db-custom-1-3840` instance. | Monitor via worker error logs; confirm row count post-run. |
| Duplicate publish / idempotency risk | A publish retry after a timeout could send the same message twice. The `ON CONFLICT(event_id) DO NOTHING` constraint absorbs duplicates at the bronze layer. | Check `duplicate_event_id_count = 0` in the post-run Cloud SQL query. |
| Log query time-window mismatch | If the Cloud Logging query window is too narrow, valid log entries may be missed. | Set the end query window to at least 15 minutes after `PUBLISH_END_TIME`. |
| DELTA metric window boundary gap | Cloud Monitoring `DELTA` intervals may not align exactly with the publish window boundaries (observed 37-event gap in the 5k run). | Worker structured logs are the authoritative ingest count. Document any metric gap with the same explanation used in the 5k evidence. |
| Cloud SQL cost window | Each minute Cloud SQL is `ALWAYS / RUNNABLE` incurs cost. The 5k run required approximately 12 minutes of active Cloud SQL time; the 10k run may require 20–25 minutes. | Restore to `NEVER` immediately after all readback evidence is captured. Do not leave Cloud SQL running between evidence steps. |
| Accidental scheduler activation | If either scheduler is accidentally resumed during the run, it may trigger a dbt or BigQuery append job that writes to Cloud SQL while a load test is in progress. | Confirm both schedulers `PAUSED` before and after the run. Do not resume schedulers for any reason during the execution window. |
| Terraform drift if Cloud SQL is not restored | If Cloud SQL is left in `ALWAYS` state, the next Terraform plan will show a diff (`activation_policy: "NEVER"` vs `"ALWAYS"`). | Always restore Cloud SQL before running the post-run Terraform plan check. |

---

## 10. Decision Gate After 10,000 Events

### If the 10,000-event run passes cleanly

All acceptance criteria met, zero errors, DLQ empty, Cloud SQL row count delta = 10,000,
duplicate count = 0, Terraform zero-diff:

- Next branch: `exec/cloud-load-test-10000-evidence` (execution and evidence commit).
- Then: `docs/cloud-load-test-50000-plan` (plan for the next scale tier).
- The 10,000-event evidence becomes the new throughput baseline.

### If the 10,000-event run exposes bottlenecks

Worker errors, DLQ routing, Cloud SQL write failures, or metric anomalies beyond the known
DELTA window boundary behaviour:

- Next branch: `docs/worker-backpressure-observability-plan` or
  `feat/worker-backpressure-observability` to instrument and address the bottleneck
  before attempting higher volumes.
- The 10,000-event attempt is documented as a partial run with explicit root causes.

### Dataflow decision gate

Dataflow remains deferred until at least the 10,000-event cloud run is accepted with clean
evidence, and preferably until the 50,000-event tier is also accepted on the current stack.
The rationale: Dataflow should be introduced as an evidenced improvement over a measured
baseline, not as a replacement for an unknown one.

---

## 11. B2B Relevance

**10,000 events is not enterprise scale.** No claim of production-grade sustained throughput
is made. This run is bounded and deterministic, identical in approach to the accepted 100,
1,000, and 5,000-event runs.

**What it does prove:**

- The platform is no longer constrained to the 5,000-event ceiling. Extending the validated
  range to 10,000 events demonstrates measurable progression, not a step-change.
- The evidence chain (100 → 1,000 → 5,000 → 10,000) shows a disciplined incremental
  validation approach that a technical reviewer can follow from first principles.
- At 10,000 events with zero errors and a clean DLQ, the idempotency contract, the
  dead-letter policy, and the cost-control protocol are validated at a scale that is
  defensible in an interview context.

**What it prepares for Dataflow:**

The 5,000-event run was the first sign that the current Cloud Run worker (single instance,
`max_instance_count=1`, `max_instance_request_concurrency=1`) may approach its delivery
capacity at scale. The 10,000-event run either confirms that the current stack handles double
the prior ceiling cleanly, or identifies the throughput limit. Either outcome provides the
measured baseline that a Dataflow introduction requires: without this evidence, a Dataflow
claim can only say "we replaced the current worker with Dataflow" — not "the current worker
reached its limit at N events and Dataflow addresses that specific constraint."

**Interview-ready signals this run creates:**

- Controlled throughput progression with traceable prefixes.
- Idempotency verification at scale (duplicate `event_id` count = 0).
- DLQ health verification (dead-letter policy functional and unused).
- Cost-control discipline (Cloud SQL started for a bounded window and immediately restored).
- Terraform zero-diff pre- and post-run (no infrastructure drift from a bounded load test).

---

## 12. Related Documents

| Document | Relationship |
|---|---|
| [docs/load-test-plan.md](load-test-plan.md) | Original bounded load test plan (100 / 1,000 / 5,000) — this plan extends the series |
| [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) | Accepted 5,000-event evidence — direct predecessor to this run |
| [docs/load-test-local-sample-evidence.md](load-test-local-sample-evidence.md) | Local dry-run sample evidence approach |
| [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) | DLQ configuration evidence — confirmed policy intact |
| [docs/dbt-cloud-sql-incremental-execution-proof.md](dbt-cloud-sql-incremental-execution-proof.md) | Most recent Cloud SQL activation and restoration evidence (2026-05-19) |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Cloud Monitoring REST API query method reference |
| [docs/portfolio-b2b-narrative.md](portfolio-b2b-narrative.md) | B2B positioning and explicit non-claims (Dataflow, sustained throughput) |
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog |
