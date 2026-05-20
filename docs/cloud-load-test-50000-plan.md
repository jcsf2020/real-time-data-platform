# Cloud Load Test -- 50,000-Event Plan

## Status

**PLANNED -- 50,000-EVENT CLOUD LOAD TEST NOT YET EXECUTED**

This document is a forward-looking plan only. No events have been published, no Cloud SQL
instance has been started, no Terraform apply has been executed, and no GCP resources have
been mutated. All execution commands are written for a future controlled execution branch.
Do not act on these commands in this docs branch.

---

## 1. Purpose

The validated 100 / 1,000 / 5,000 / 10,000-event bounded load tests establish a measured
baseline for the current Pub/Sub → Cloud Run worker → Cloud SQL path. The 10,000-event run
([docs/load-test-10000-cloud-evidence.md](load-test-10000-cloud-evidence.md)) confirmed
zero errors, a clean DLQ, and exact Cloud SQL row-count alignment at double the prior
5,000-event ceiling.

This plan extends that baseline to 50,000 events. The specific goals are:

- Demonstrate whether the platform handles a sustained publish volume of 50,000 events
  without worker errors, DLQ delivery, or Cloud SQL write failures.
- Capture a measured ingest throughput data point five times above the 10,000-event
  ceiling, covering a significantly longer publish and drain window.
- Validate the idempotency contract at scale: zero duplicate `event_id` values in
  `bronze.market_events` after the run.
- Establish the current-stack throughput limit range before introducing any architectural
  change.
- Gather evidence on Cloud SQL write pressure, Cloud Run single-instance concurrency
  behaviour, and Pub/Sub push delivery reliability at sustained load.

### Why 50k before Dataflow

Dataflow is not yet implemented in this repository (see
[docs/portfolio-b2b-narrative.md](portfolio-b2b-narrative.md) for the explicit non-claim).
The 10,000-event run passed cleanly, but a single doubling from 5,000 is a relatively
narrow signal for the current architecture. A 50,000-event bounded run gives a much stronger
signal across multiple dimensions:

- **Worker throughput**: a single Cloud Run instance with `max_instance_count=1` and
  `max_instance_request_concurrency=1` must drain a five times larger Pub/Sub backlog.
- **Cloud SQL write pressure**: 50,000 idempotent inserts stress the `db-custom-1-3840`
  instance far more than the 10,000-event run.
- **Pub/Sub push delivery**: a longer publish window tests whether push subscription
  behaviour remains consistent over a 16+ minute duration.
- **Metrics and observability**: the Cloud Monitoring DELTA window alignment and log
  pagination behaviour are exercised at higher volume.

If the 50,000-event run passes cleanly, the current Pub/Sub → Cloud Run → Cloud SQL stack
remains viable for bounded burst workloads and the evidence base for Dataflow changes from
"architecturally preferred" to "not yet required at validated scale." If the 50,000-event
run fails or degrades, Dataflow becomes justified by specific, observed bottleneck evidence
rather than architectural preference.

This is the decision gate before Dataflow, not a replacement for Dataflow. The correct
sequencing is:

1. Validate 10,000 events on the current stack. ✓ Proven.
2. Validate 50,000 events on the current stack (or identify the throughput ceiling).
3. Introduce Dataflow after the current-stack limit is measured and documented.

---

## 2. Scope

### In scope

- Generate 50,000 deterministic `MarketEvent`-compatible events using the existing
  load-test generator script (with `ALLOWED_SIZES` extended to include `50000` in the
  execution branch — see section 4).
- Validate the generated JSONL file locally using the existing validator script.
- Publish all 50,000 events to the production Pub/Sub topic `market-events-raw`.
- Observe Cloud Run worker processing via structured logs and Cloud Monitoring metric.
- Confirm the DLQ (`market-events-raw-dlq`) received zero messages.
- Confirm `bronze.market_events` row count increases by the expected amount.
- Confirm zero duplicate `event_id` values in `bronze.market_events` after the run.
- Confirm Cloud SQL is restored to `NEVER / STOPPED` after the run.
- Confirm both schedulers remain `PAUSED` throughout.
- Confirm Terraform plan returns `PLAN_EXIT=0` after the run.
- Capture publish elapsed time and approximate effective throughput.

### Out of scope

- Malformed or schema-invalid messages
- Retry or DLQ testing on the production push subscription
- Any event count beyond 50,000 in this plan
- Schema changes, migration testing, or dbt model changes
- Dataflow implementation or testing
- Autoscaling stress testing (worker is constrained to `max_instance_count=1`)
- IaC changes (Terraform or gcloud config mutations)
- Alert policy creation or modification
- Multi-region validation

---

## 3. Explicit Non-Claims

This plan document makes none of the following claims:

- **This plan does not execute the test.** Execution happens in a future branch named
  `exec/cloud-load-test-50000-evidence` or equivalent.
- **This plan does not prove 50,000-event throughput.** No events have been published
  and no metrics have been captured.
- **This plan does not prove sustained production throughput.** Each run is a bounded
  burst, not a continuous streaming workload.
- **This plan does not implement Dataflow.** The Cloud Run worker remains the processing
  path. No Dataflow pipeline exists in this repository.
- **This plan does not prove 100,000 / 500,000 events.** Those are future plans
  contingent on the 50,000-event evidence outcome.
- **This plan does not mutate GCP resources.** No `gcloud` mutation commands, no
  `terraform apply`, no event publishing, and no Cloud SQL start are performed in this
  docs branch.
- **This plan does not claim enterprise-scale streaming.** 50,000 bounded events is a
  portfolio throughput signal, not a production SLA.

---

## 4. Script Constraint: ALLOWED_SIZES

After the 10,000-event execution branch, the generator and validator scripts currently
accept sizes in `{100, 1000, 5000, 10000}`:

- `scripts/generate_load_test_events.py:11` — `ALLOWED_SIZES = frozenset({100, 1000, 5000, 10000})`
- `scripts/validate_load_test_events.py:11` — `ALLOWED_SIZES = frozenset({100, 1000, 5000, 10000})`

The execution branch must add `50000` to `ALLOWED_SIZES` in both scripts and update the
corresponding tests in `tests/test_generate_load_test_events.py` and
`tests/test_validate_load_test_events.py` before any generate or validate commands can run.
These are code changes — they must not be made in this docs-only branch.

---

## 5. Preconditions

All of the following must be confirmed before execution begins in the future branch.

| Precondition | How to verify | Required state |
|---|---|---|
| Execution branch is correct | `git branch --show-current` | `exec/cloud-load-test-50000-evidence` (or documented equivalent) |
| Working tree is clean | `git status` | No uncommitted changes |
| `ALLOWED_SIZES` extended | `grep ALLOWED_SIZES scripts/generate_load_test_events.py scripts/validate_load_test_events.py` | `{100, 1000, 5000, 10000, 50000}` in both files |
| All tests pass | `uv run pytest -q` | All tests pass |
| Ruff clean | `uv run ruff check .` | `All checks passed!` |
| Cloud SQL initial state | `gcloud sql instances describe rtdp-postgres` | `NEVER   STOPPED` |
| Both schedulers | `gcloud scheduler jobs list --location=europe-west1` | Both `PAUSED` |
| Secret byte check | `gcloud secrets versions access latest --secret=rtdp-database-url \| wc -c` | No trailing newline (value byte count matches expected URL length exactly) |
| API/worker revisions | Confirm revisions use DATABASE_URL normalization code from PR #176 | Current deployed revisions |
| API readiness gate | Start Cloud SQL temporarily, check `/readiness` before publish | HTTP 200, `{"status":"ready","service":"rtdp-api","database":"reachable"}` |
| Pub/Sub topic exists | `gcloud pubsub topics describe market-events-raw` | Topic present |
| Push subscription active | `gcloud pubsub subscriptions describe market-events-raw-worker-push` | `state: ACTIVE` |
| DLQ dead-letter policy | Push subscription describe output | `deadLetterTopic`, `maxDeliveryAttempts=5` present |
| DLQ topic exists | `gcloud pubsub topics describe market-events-raw-dlq` | Topic present |
| Cloud Run worker deployed | `gcloud run services describe rtdp-pubsub-worker --region=europe-west1` | Service exists and `Ready` |
| Terraform zero-diff | `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false` | `PLAN_EXIT=0` |
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

### Step 1 — Inspect current script ALLOWED_SIZES

```bash
grep ALLOWED_SIZES scripts/generate_load_test_events.py
grep ALLOWED_SIZES scripts/validate_load_test_events.py
```

Expected: both lines show `frozenset({100, 1000, 5000, 10000, 50000})`.

If `50000` is absent, do not proceed — update the scripts and tests first, then rerun the
full test suite and linter before continuing.

---

### Step 2 — Run pre-execution checks

```bash
uv run pytest -q
uv run ruff check .
```

Expected: all tests pass, ruff clean.

---

### Step 3 — Inspect Cloud SQL state (read-only)

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

Record as: `CLOUD_SQL_PRE_50000_BASELINE=NEVER_STOPPED`

---

### Step 4 — Inspect scheduler state (read-only)

```bash
gcloud scheduler jobs list \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state,schedule)"
```

Expected: both `rtdp-silver-refresh-scheduler` and `rtdp-bigquery-append-scheduler`
show `PAUSED`.

Record as: `SCHEDULERS_PRE_50000_BASELINE=BOTH_PAUSED`

---

### Step 5 — Inspect secret byte count (read-only, no secret value printed)

```bash
gcloud secrets versions access latest \
  --secret=rtdp-database-url \
  --project=project-42987e01-2123-446b-ac7 \
  | wc -c
```

Do not print the secret value. The byte count should match the expected URL length with no
trailing newline. If the count looks suspicious (e.g., one byte higher than expected), the
secret may contain a trailing newline — rotate the secret before proceeding, following the
same procedure used in PR #176.

---

### Step 6 — Temporarily start Cloud SQL for API readiness gate

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS \
  --project=project-42987e01-2123-446b-ac7
```

---

### Step 7 — Wait until Cloud SQL is RUNNABLE

```bash
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

---

### Step 8 — API readiness check

```bash
curl -sf https://rtdp-api-fpy4of3i5a-ew.a.run.app/readiness
```

Expected: HTTP 200, `{"status":"ready","service":"rtdp-api","database":"reachable"}`

**If readiness does not return HTTP 200 after Cloud SQL is RUNNABLE:**

This is an abort condition. Restore Cloud SQL immediately before diagnosing:

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER \
  --project=project-42987e01-2123-446b-ac7
```

Wait until `STOPPED`, then diagnose the readiness failure separately. Do not publish events
if readiness is not confirmed.

---

### Step 9 — Inspect Pub/Sub topic, push subscription, and DLQ state (read-only)

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

Record as: `DLQ_POLICY_PRE_50000_VALIDATED=true`

---

### Step 10 — Inspect Cloud Run worker service (read-only)

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

### Step 11 — Confirm Terraform zero-diff baseline (read-only)

```bash
terraform -chdir=infra/terraform/gcp plan \
  -detailed-exitcode \
  -input=false
echo "PLAN_EXIT=$?"
```

Expected: `PLAN_EXIT=0`

Do not proceed if `PLAN_EXIT` is not `0`.

---

### Step 12 — Generate 50,000 deterministic events (local, no GCP contact)

```bash
# Record the prefix timestamp before generating
PREFIX_TIMESTAMP=$(date -u +%Y%m%d%H%M%S)
echo "PREFIX_TIMESTAMP=${PREFIX_TIMESTAMP}"

mkdir -p docs/evidence/load-test-50000-cloud

uv run python scripts/generate_load_test_events.py \
  --size 50000 \
  --prefix-timestamp ${PREFIX_TIMESTAMP} \
  --output docs/evidence/load-test-50000-cloud/events-50000.jsonl

wc -l docs/evidence/load-test-50000-cloud/events-50000.jsonl
```

Expected: 50000 lines.

> Note: requires `50000` to be in `ALLOWED_SIZES` in the generator script — see section 4.

---

### Step 13 — Validate generated events (local, no GCP contact)

```bash
uv run python scripts/validate_load_test_events.py \
  --input docs/evidence/load-test-50000-cloud/events-50000.jsonl \
  --size 50000 \
  --prefix-timestamp ${PREFIX_TIMESTAMP} \
  --report-output docs/evidence/load-test-50000-cloud/local-validation-report-50000.json

cat docs/evidence/load-test-50000-cloud/local-validation-report-50000.json
```

Expected: `"status": "ok"`, `"observed_count": 50000`, `"unique_event_ids": 50000`,
`"worker_contract_validation": "passed"`, `"errors": []`.

Record as: `LOAD_TEST_50000_LOCAL_VALIDATION_PASSED=true`

---

### Step 14 — Publish 50,000 events to Pub/Sub

> **Publish rate recommendation:** Start at 50 msg/s. A more aggressive rate of 100 msg/s
> may be used if the 50 msg/s run is later deemed too conservative, but the chosen rate
> must be explicitly documented in the evidence record. Do not change the rate mid-publish.
>
> **Timing note:** At a theoretical 50 msg/s, publishing 50,000 events takes approximately
> 16–17 minutes of wall time before drain and validation begin. The actual elapsed time
> may be higher depending on network latency and blocking future.result() behaviour (the
> 10,000-event run at 50 msg/s took approximately 8 minutes of actual wall time). Budget
> at least 45 minutes total for the Cloud SQL active window (publish + drain + validation
> + restoration).

```bash
# Record publish start time before first message
START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "START_TIME=${START_TIME}"

# Publish using google-cloud-pubsub Python client at ≤50 msg/s
python3 - <<'EOF'
import json, time
from google.cloud import pubsub_v1

PROJECT_ID = "project-42987e01-2123-446b-ac7"
TOPIC_ID   = "market-events-raw"
INPUT_FILE = "docs/evidence/load-test-50000-cloud/events-50000.jsonl"
RATE_LIMIT = 50  # messages per second -- document this value in evidence

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

    if i % 2500 == 0:
        print(f"PUBLISHED {i}/{len(lines)}  latest_message_id={message_ids[-1]}")

print(f"PUBLISHED_TOTAL={published}")
print(f"UNIQUE_MESSAGE_IDS={len(set(message_ids))}")
print(f"PUBLISH_ERROR_COUNT={errors}")
EOF

PUBLISH_END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "PUBLISH_END_TIME=${PUBLISH_END_TIME}"
```

Expected: `PUBLISHED_TOTAL=50000`, `UNIQUE_MESSAGE_IDS=50000`, `PUBLISH_ERROR_COUNT=0`.

Record `START_TIME`, `PUBLISH_END_TIME`, `PUBLISHED_TOTAL`, `UNIQUE_MESSAGE_IDS`,
`PUBLISH_ERROR_COUNT`, and elapsed seconds.

**Abort conditions during publish:**

- Any `PUBLISH_ERROR_COUNT > 0`: halt immediately, do not continue, restore Cloud SQL.
- Any Python exception or `SystemExit(1)`: treat as publish failure; restore Cloud SQL.
- Laptop interruption / network loss mid-publish: document partial count, restore Cloud SQL,
  do not count a partial run as evidence.

---

### Step 15 — Query worker logs (success path)

Wait for at least 10 minutes after `PUBLISH_END_TIME` before querying to allow the Pub/Sub
push subscription to drain at the `max_instance_count=1` / `max_instance_request_concurrency=1`
worker capacity.

```bash
# Adjust PREFIX_TIMESTAMP to the value recorded in step 12.
# Adjust the time window to START_TIME and at least 30 minutes after PUBLISH_END_TIME.

gcloud logging read \
  "resource.type=\"cloud_run_revision\"
   resource.labels.service_name=\"rtdp-pubsub-worker\"
   jsonPayload.operation=\"process_message\"
   jsonPayload.status=\"ok\"
   jsonPayload.event_id =~ \"^loadtest-50000-${PREFIX_TIMESTAMP}-\"" \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(jsonPayload.event_id)" \
  --limit=50000 | sort -u | wc -l
```

Expected: 50000 unique `event_id` values.

> **Log pagination note:** `--limit=50000` may not return all results in one call if Cloud
> Logging applies server-side pagination. If the returned count is lower than expected, run
> the query again with a narrower time window, or use `--page-size` and paginate manually.
> Worker structured logs are the authoritative ingest count.

Query error path (must return 0):

```bash
gcloud logging read \
  "resource.type=\"cloud_run_revision\"
   resource.labels.service_name=\"rtdp-pubsub-worker\"
   jsonPayload.operation=\"process_message\"
   jsonPayload.status=\"error\"
   jsonPayload.event_id =~ \"^loadtest-50000-${PREFIX_TIMESTAMP}-\"" \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=1
```

Expected: zero results. Any error result is an abort condition — document the error log
entry before restoring Cloud SQL.

---

### Step 16 — Query worker processed and error metrics via Cloud Monitoring REST API

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT_ID=project-42987e01-2123-446b-ac7

# Replace with the actual START_TIME and END_TIME (at least 30 minutes after PUBLISH_END_TIME)
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
- `PROCESSED_TOTAL` approximately 50,000. A small gap from the log count is acceptable due
  to DELTA window boundary alignment — this behaviour was observed in the 5,000-event run
  (metric sum 4,963 vs log count 5,000) and explained in
  [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) section 6.3.
  Worker structured logs are the authoritative ingest count. Any metric gap larger than
  ~0.5% of the event count must be explicitly explained in the evidence document.
- `ERROR_TOTAL: 0`

---

### Step 17 — Inspect DLQ count

```bash
gcloud pubsub topics list-subscriptions market-events-raw-dlq \
  --project=project-42987e01-2123-446b-ac7
```

Expected: `Listed 0 items.`

If any subscriptions are listed, inspect the subscription's undelivered message count before
restoring Cloud SQL. A non-zero DLQ count is an abort condition.

---

### Step 18 — Query Cloud SQL prefix row count

```bash
# Via Cloud SQL Auth Proxy (once connected):
psql -c "
SELECT COUNT(*) AS prefix_row_count
FROM bronze.market_events
WHERE event_id LIKE 'loadtest-50000-${PREFIX_TIMESTAMP}-%';
"
```

Expected: `prefix_row_count = 50000`

Record as: `CLOUD_SQL_PREFIX_ROW_COUNT=50000`

---

### Step 19 — Query duplicate event_id count in Cloud SQL

```bash
# Via Cloud SQL Auth Proxy (once connected):
psql -c "
SELECT COUNT(*) AS duplicate_event_id_count
FROM (
    SELECT event_id, COUNT(*) AS n
    FROM bronze.market_events
    WHERE event_id LIKE 'loadtest-50000-${PREFIX_TIMESTAMP}-%'
    GROUP BY event_id
    HAVING COUNT(*) > 1
) t;
"
```

Expected: `duplicate_event_id_count = 0`

---

### Step 20 — Restore Cloud SQL to NEVER (cost-control -- mandatory)

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER \
  --project=project-42987e01-2123-446b-ac7
```

This step is mandatory regardless of whether all acceptance criteria have been met.

---

### Step 21 — Wait until Cloud SQL is STOPPED/NEVER

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

Record as: `CLOUD_SQL_POST_50000_STATE=NEVER_STOPPED`

---

### Step 22 — Confirm schedulers PAUSED

```bash
gcloud scheduler jobs list \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state)"
```

Expected: both schedulers show `PAUSED`.

---

### Step 23 — Confirm Terraform plan PLAN_EXIT=0

```bash
terraform -chdir=infra/terraform/gcp plan \
  -detailed-exitcode \
  -input=false
echo "PLAN_EXIT=$?"
```

Expected: `PLAN_EXIT=0`

If `PLAN_EXIT=2`, the most likely cause is Cloud SQL `activation_policy` not fully reverted.
Confirm Cloud SQL state is `NEVER / STOPPED` before diagnosing Terraform drift.

---

## 7. Acceptance Criteria

All criteria must be met before this test is accepted. Any unmet criterion must be explicitly
documented with a root cause before the evidence document is closed.

| Criterion | Required |
|---|---|
| 50,000 events generated | JSONL file contains exactly 50,000 lines |
| Local validation passes | Validator exits `status: ok`, `unique_event_ids: 50000`, `errors: []` |
| Publish command succeeds | 50,000 unique `messageId` values returned, `PUBLISH_ERROR_COUNT=0` |
| Worker OK log count | Worker `status=ok` log count for the run prefix = 50,000, or equivalent documented proof of full drain |
| Worker error count remains 0 | Zero `status=error` logs for the prefix; if any errors appear they must be documented with root cause |
| Cloud Monitoring processed metric | `PROCESSED_TOTAL` approximates or equals 50,000; any DELTA window gap must be explained using the same methodology as the 5k/10k runs |
| Cloud Monitoring error metric | `ERROR_TOTAL=0` |
| DLQ remains 0 | `gcloud pubsub topics list-subscriptions market-events-raw-dlq` returns `Listed 0 items.` |
| Cloud SQL prefix row count | `prefix_row_count = 50000` in `bronze.market_events` |
| Duplicate event_id count | `duplicate_event_id_count = 0` for the run prefix |
| Cloud SQL final state | `NEVER   STOPPED` confirmed before evidence doc is closed |
| Schedulers final state | Both schedulers `PAUSED` after the run |
| Terraform plan | `PLAN_EXIT=0` post-run |
| No secrets printed | No credentials, tokens, or secrets appear in any captured output |
| Evidence document created | New `docs/load-test-50000-cloud-evidence.md` committed in the execution branch |

---

## 8. Evidence Fields to Capture

The execution evidence document must include a table with at least the following fields.

| Field | Value (fill at execution time) |
|---|---|
| Branch | `exec/cloud-load-test-50000-evidence` |
| Date / time UTC | YYYY-MM-DD HH:MM:SSZ |
| Operator | (name) |
| Event count | 50000 |
| Prefix timestamp | `YYYYMMDDHHMMSS` (actual value) |
| Event prefix | `loadtest-50000-<PREFIX_TIMESTAMP>-` |
| Generated event file path | `docs/evidence/load-test-50000-cloud/events-50000.jsonl` |
| Local validation report path | `docs/evidence/load-test-50000-cloud/local-validation-report-50000.json` |
| Validation result | `ok` / `error` |
| Publish result | `PUBLISHED_TOTAL=50000`, `UNIQUE_MESSAGE_IDS=50000`, `PUBLISH_ERROR_COUNT=0` |
| Publish start UTC | `START_TIME` |
| Publish end UTC | `PUBLISH_END_TIME` |
| Publish elapsed seconds | (observed value) |
| Effective publish throughput | (observed value msg/s) |
| Rate limit used | `50 msg/s` (or documented value) |
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
| DLQ count | 0 |
| Cloud SQL row count before (if queried) | (observed value or N/A) |
| Cloud SQL row count after (if queried) | (observed value or N/A) |
| Cloud SQL prefix row count | 50000 |
| Duplicate `event_id` count | 0 |
| Terraform plan exit code | 0 |
| GCP log query time window | `START_TIME` to `END_TIME` |
| Known anomalies | (none / documented deviations) |
| Abort condition triggered | (none / description if triggered) |

---

## 9. Risks

| Risk | Description | Mitigation |
|---|---|---|
| Pub/Sub backlog risk | 50,000 messages may accumulate faster than the worker drains them at `max_instance_count=1`. The backlog may persist for 20+ minutes after publish completes. | Wait at least 15 minutes after `PUBLISH_END_TIME` before asserting drain. Abort if backlog is not draining after 30 minutes. |
| Cloud Run single-instance bottleneck | The worker is constrained to `max_instance_count=1` and `max_instance_request_concurrency=1`. At 50,000 messages the drain window is significantly longer than at 10,000. | Publish at conservative rate (50 msg/s); monitor error logs; do not abort on backlog alone — drain may just take longer. |
| Cloud Run max_instance_count / concurrency limits | The current Terraform config hard-codes `max_instance_count=1`. If Pub/Sub push retries fire during a slow drain, the single instance may experience queue pressure beyond its timeout (60s per request). | Monitor for worker error logs during drain window; abort if `status=error` entries appear for the run prefix. |
| Cloud SQL write pressure | 50,000 idempotent inserts into `bronze.market_events` sustained over the drain window stress the `db-custom-1-3840` instance (1 vCPU, 3.84 GB RAM). Row lock contention or disk pressure is possible. | Monitor via worker error logs; confirm prefix row count post-run. |
| Cloud SQL connection pressure | The worker reconnects to Cloud SQL via Unix socket. High request concurrency from Pub/Sub retries during drain could saturate the connection pool. | The `max_instance_request_concurrency=1` setting limits this risk; monitor for worker errors. |
| Publish script timeout / laptop interruption | Publishing 50,000 messages takes 16–42 minutes depending on effective rate. A laptop sleep, network interruption, or terminal close mid-publish leaves a partial batch. | Keep terminal active and laptop awake. If interrupted, document the partial count, restore Cloud SQL, and treat the run as failed. |
| Metrics delay and DELTA window mismatch | Cloud Monitoring DELTA intervals may not align exactly with the publish window boundaries. A gap between metric total and log count was observed at 5,000 events (37 events). At 50,000 events the gap may be larger in absolute terms. | Worker structured logs are the authoritative ingest count. Document any metric gap with the DELTA window explanation from prior evidence. |
| Log query result limit / pagination risk | `gcloud logging read --limit=50000` may not return all results in one call. Cloud Logging may paginate or apply server-side limits. | Use `sort -u | wc -l` to deduplicate before counting. If count is low, narrow the time window and requery. |
| Duplicate publish / idempotency risk | A publish retry after a timeout could send the same message twice. The `ON CONFLICT(event_id) DO NOTHING` constraint absorbs duplicates at the bronze layer. | Check `duplicate_event_id_count = 0` in the post-run Cloud SQL query. |
| DLQ routing risk | If the push subscription exhausts `maxDeliveryAttempts=5` for any message, it is routed to `market-events-raw-dlq`. At 50,000 messages the probability of at least one retry is higher than at 10,000. | Check DLQ subscription count post-publish. A non-zero DLQ count is an abort condition. |
| Cloud SQL cost window | Each minute Cloud SQL is `ALWAYS / RUNNABLE` incurs cost. The 10,000-event run required approximately 20+ minutes of active Cloud SQL time. The 50,000-event run may require 45–60 minutes (publish + drain + validation). | Restore to `NEVER` immediately after all readback evidence is captured. Do not leave Cloud SQL running between evidence steps. |
| Accidental scheduler activation | If either scheduler is resumed during the run, it may trigger a dbt or BigQuery append job that writes to Cloud SQL while the load test is in progress. | Confirm both schedulers `PAUSED` before and after the run. Do not resume schedulers for any reason during the execution window. |
| Terraform drift if Cloud SQL is not restored | If Cloud SQL is left in `ALWAYS` state, the next Terraform plan will show a diff (`activation_policy: "NEVER"` vs `"ALWAYS"`). | Always restore Cloud SQL before running the post-run Terraform plan check. |
| Evidence artifact size growth | A 50,000-line JSONL file is approximately 10–15 MB. Committing this to the repository may increase clone time and CI duration. | Evaluate whether the JSONL file should be committed or referenced by hash only. The 10k JSONL was committed; apply consistent policy. |

---

## 10. Abort Conditions

Stop execution immediately and restore Cloud SQL if any of the following occur:

| Condition | Action |
|---|---|
| API readiness returns HTTP != 200 after Cloud SQL is RUNNABLE | Restore Cloud SQL; do not publish; diagnose separately |
| Cloud SQL cannot reach RUNNABLE within 5 minutes | Restore (or attempt to); do not publish; log instance state |
| Worker error logs appear for the run prefix | Stop; document error log entries; restore Cloud SQL |
| Publish errors occur (`PUBLISH_ERROR_COUNT > 0`) | Stop; document error; restore Cloud SQL |
| DLQ subscriptions or messages appear | Stop; document DLQ state; restore Cloud SQL |
| Cloud SQL prefix row count stalls far below expected after a 30-minute drain window | Document observed count; restore Cloud SQL; treat as partial run |
| Terraform plan becomes non-zero after Cloud SQL restoration | Do not close evidence; diagnose drift before committing |
| Cloud SQL cannot be restored to STOPPED/NEVER | Escalate immediately; do not commit evidence until resolved |

---

## 11. Decision Gate After 50,000 Events

### If the 50,000-event run passes cleanly

All acceptance criteria met, zero errors, DLQ empty, Cloud SQL prefix row count = 50,000,
duplicate count = 0, Terraform zero-diff:

- Next branch: `docs/cloud-load-test-100000-plan` — plan for the next scale tier.
- Alternatively: `docs/dataflow-decision-record` — if the 50k run's elapsed time or
  observed worker pressure provides sufficient motivation for Dataflow.
- The 50,000-event evidence becomes the new throughput baseline.
- Dataflow remains optional at this point but now has a much stronger comparison baseline.

### If the 50,000-event run exposes bottlenecks

Worker errors, DLQ routing, Cloud SQL write failures, or metric anomalies beyond the
known DELTA window boundary behaviour:

- Next branch: `docs/dataflow-decision-record` — document the observed bottleneck as
  the specific evidence that justifies Dataflow introduction.
- Alternatively: `docs/worker-backpressure-observability-plan` — if the bottleneck
  is observable but not yet fully characterised.
- The 50,000-event attempt is documented as a partial or failed run with explicit root
  causes. Dataflow becomes justified by the observed evidence, not architectural preference.

### If the failure is caused by operational procedure rather than architecture

For example: laptop interruption, incorrect `PREFIX_TIMESTAMP`, incomplete Cloud SQL
drain time, or log query pagination error:

- Fix the procedure first (update this plan if necessary), then retry the 50,000-event
  run on a new execution branch.
- Do not use a procedural failure as evidence for architectural change.

---

## 12. B2B Relevance

**50,000 events is still bounded, not sustained enterprise streaming.** No claim of
production-grade continuous throughput is made. This run is a controlled, deterministic
burst, identical in approach to the 100 / 1,000 / 5,000 / 10,000-event runs before it.

**Why 50k is a much stronger portfolio signal than 10k:**

- The publish-and-drain window spans approximately 45–60 minutes of active Cloud SQL time.
  This tests operational discipline under longer-running load: the operator must keep the
  terminal active, avoid accidental scheduler activation, and execute a cost-control
  restoration at the end.
- At 50,000 events, Cloud SQL write pressure, Pub/Sub push delivery consistency, Cloud Run
  single-instance drain behaviour, and Cloud Monitoring DELTA metric alignment are all
  exercised at a scale where deviations are more likely to surface than at 10,000 events.
- A clean 50k pass creates evidence around throughput, idempotency, DLQ health, Cloud SQL
  pressure tolerance, cost-control discipline, and observability completeness — all in a
  single bounded run.

**Interview-ready narrative this run supports:**

> "I did not jump to Dataflow. I ran the existing Pub/Sub → Cloud Run → Cloud SQL path at
> increasing scale — 100, 1,000, 5,000, 10,000, and then 50,000 events — measuring
> throughput, idempotency, and DLQ behaviour at each tier. The 50,000-event run either
> confirmed that the current stack is viable for bounded burst workloads, or surfaced the
> specific bottleneck that makes Dataflow the right next step. Either way, the architectural
> decision is backed by measurement rather than preference."

This is a meaningful signal in a B2B technical review: it shows the ability to measure
before replacing, to operate cost-controlled cloud infrastructure responsibly, and to build
an evidence chain that a reviewer can follow from first principles.

---

## 13. Related Documents

| Document | Relationship |
|---|---|
| [docs/load-test-plan.md](load-test-plan.md) | Original bounded load test plan (100 / 1,000 / 5,000) — this plan continues the series |
| [docs/load-test-10000-cloud-evidence.md](load-test-10000-cloud-evidence.md) | Accepted 10,000-event evidence — direct predecessor to this run |
| [docs/cloud-load-test-10000-plan.md](cloud-load-test-10000-plan.md) | 10,000-event plan — structural template for this document |
| [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) | 5,000-event evidence — DELTA window gap explanation used as reference |
| [docs/load-test-local-sample-evidence.md](load-test-local-sample-evidence.md) | Local dry-run sample evidence approach |
| [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) | DLQ configuration evidence — confirmed policy intact |
| [docs/dbt-cloud-sql-incremental-execution-proof.md](dbt-cloud-sql-incremental-execution-proof.md) | Most recent Cloud SQL activation and restoration evidence |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Cloud Monitoring REST API query method reference |
| [docs/portfolio-b2b-narrative.md](portfolio-b2b-narrative.md) | B2B positioning and explicit non-claims (Dataflow, sustained throughput) |
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog |
