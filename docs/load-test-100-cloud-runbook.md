# Load-Test 100-Event Cloud Runbook

## Status

**RUNBOOK ONLY — NOT EXECUTED**

This is an operational runbook. The 100-event cloud load test has **not been executed**.
No Pub/Sub messages have been published. No Cloud SQL instance has been started. No GCP
resources have been mutated on this branch.

This runbook exists solely to define the precise, reviewable execution sequence for a future
branch or session. Read every command block as documentation, not as executed evidence.

---

## 1. Scope

### Covered by this runbook

- First controlled live GCP load test: exactly 100 valid Pub/Sub messages
- Pre-publish JSONL generation and local validation (deterministic generator path)
- Cloud SQL start / stop protocol
- Pub/Sub publish and backlog observation
- Worker structured log validation (success path only)
- `worker_message_processed_count` Cloud Monitoring timeSeries query
- API `/events` and `/aggregates/minute` readback
- Silver refresh job execution and log validation
- Cloud SQL final cost-control state confirmation
- Evidence checklist and acceptance criteria

### Explicitly excluded from this runbook

- Malformed or schema-invalid messages
- Retry / DLQ testing on the production push subscription
- 1 000-event or 5 000-event test runs
- IaC changes (Terraform or gcloud configuration mutations)
- Alert policy creation or Cloud Monitoring dashboard creation
- Production benchmark or SLA claims
- Autoscaling stress or concurrency limit testing
- Multi-region or failover testing

---

## 2. Objective

Execute the first controlled live GCP load test with exactly 100 valid Pub/Sub messages using
the already-validated local generator and validator path, then collect end-to-end evidence
across:

- Pub/Sub publish count and message IDs
- Pub/Sub backlog before, immediately after, and after drain
- Cloud Run worker structured logs (`jsonPayload.status=ok`) scoped to the test prefix
- `worker_message_processed_count` Cloud Monitoring timeSeries datapoints over the execution
  window
- API `/events` readback filtered to the test prefix
- Silver refresh job Cloud Logging success entry
- API `/aggregates/minute` readback confirming aggregate rows after refresh
- Cloud SQL final cost-control state (`NEVER / STOPPED`)

All evidence must be captured in `docs/load-test-100-cloud-evidence.md` on the execution
branch.

---

## 3. Preconditions

All of the following must be true before any execution commands are run. Abort if any
precondition cannot be confirmed.

| # | Precondition | How to verify |
|---|---|---|
| 1 | This must run on a **future execution/evidence branch** — not this runbook branch | `git branch --show-current` |
| 2 | `main` is clean and synced | `git status` on `main`; `git fetch && git log origin/main..main` |
| 3 | All tests pass | `uv run pytest -q` exits 0 |
| 4 | Ruff passes | `uv run ruff check .` exits 0 |
| 5 | Cloud SQL is currently `NEVER / STOPPED` (confirmed read-only) | See Section 7 — pre-execution describe |
| 6 | Worker health endpoint returns `{"status":"ok"}` | `curl $WORKER_URL/health` |
| 7 | API health endpoint returns `{"status":"ok"}` | `curl $API_URL/health` |
| 8 | Pub/Sub worker push subscription is `ACTIVE` | gcloud pubsub subscriptions describe |
| 9 | Pub/Sub subscription backlog is 0 or near 0 | gcloud pubsub subscriptions describe or Cloud Monitoring query |
| 10 | Local 100-event sample validates with `status=ok` | `uv run python scripts/validate_load_test_events.py ...` |
| 11 | No malformed messages will be published | This runbook — valid messages only |
| 12 | No other loadtest prefix is actively draining | Check Cloud Logging for recent `loadtest-` prefixes |

---

## 4. Fixed Test Inputs

| Parameter | Value |
|---|---|
| Event count | `100` |
| Prefix timestamp | Determined at execution time: `YYYYMMDDHHMMSS` wall-clock |
| Event ID prefix | `loadtest-100-<PREFIX_TIMESTAMP>-` |
| JSONL output path | `docs/evidence/load-test-100-cloud/events-100.jsonl` |
| Validator report path | `docs/evidence/load-test-100-cloud/local-validation-report-100.json` |
| Cloud evidence document | `docs/load-test-100-cloud-evidence.md` |

### Placeholder reference

All future execution commands below use these placeholders. Replace every placeholder before
running any command:

| Placeholder | Meaning |
|---|---|
| `PROJECT_ID` | GCP project ID (e.g. `rtdp-PROJECT`) |
| `REGION` | Cloud Run and Cloud SQL region (e.g. `europe-west1`) |
| `API_URL` | Cloud Run API base URL (e.g. `https://rtdp-api-XXXX.REGION.run.app`) |
| `WORKER_URL` | Cloud Run worker base URL |
| `PREFIX_TIMESTAMP` | `YYYYMMDDHHMMSS` determined at execution time |
| `START_TIME` | RFC3339 timestamp just before publish begins |
| `END_TIME` | RFC3339 timestamp at least 15 minutes after backlog drain confirmation |

---

## 5. Execution Sequence

> **Future execution only — do not run during this runbook branch.**
>
> Every command block in this section is a template for a future execution session.
> No command here has been run. All placeholders must be resolved before execution.
> Stop if any step returns an unexpected result.

### Step 1 — Confirm repo state

```bash
# Verify execution branch is NOT the runbook branch
git branch --show-current

# Verify tests and lint pass before any mutation
uv run pytest -q
uv run ruff check .
```

Expected: tests pass, ruff clean, branch is NOT `docs/load-test-100-cloud-runbook`.

---

### Step 2 — Generate JSONL locally

```bash
# Record prefix timestamp BEFORE running (wall-clock, YYYYMMDDHHMMSS)
PREFIX_TIMESTAMP=$(date +%Y%m%d%H%M%S)
echo "PREFIX_TIMESTAMP=$PREFIX_TIMESTAMP"

mkdir -p docs/evidence/load-test-100-cloud

uv run python scripts/generate_load_test_events.py \
  --size 100 \
  --prefix-timestamp $PREFIX_TIMESTAMP \
  --output docs/evidence/load-test-100-cloud/events-100.jsonl
```

Expected: file created with 100 lines.

---

### Step 3 — Validate JSONL locally

```bash
uv run python scripts/validate_load_test_events.py \
  --input docs/evidence/load-test-100-cloud/events-100.jsonl \
  --size 100 \
  --prefix-timestamp $PREFIX_TIMESTAMP \
  --report-output docs/evidence/load-test-100-cloud/local-validation-report-100.json
```

Expected: `{"status":"ok","observed_count":100,"unique_event_ids":100,"worker_contract_validation":"passed","errors":[],...}`

**Do not proceed if status is not `ok`.**

---

### Step 4 — Confirm Cloud SQL pre-execution state (read-only)

```bash
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

**Do not proceed if the state is unexpected.**

---

### Step 5 — Start Cloud SQL

> Cloud SQL must only be started immediately before publishing. Do not start it idle.

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS \
  --project=$PROJECT_ID
```

---

### Step 6 — Confirm Cloud SQL RUNNABLE

```bash
# Poll until RUNNABLE (typically 60–90 seconds)
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)" \
  --project=$PROJECT_ID
```

Expected: `ALWAYS   RUNNABLE`

**Do not publish any events while state is not RUNNABLE.**

---

### Step 7 — Confirm worker and API health

```bash
curl $WORKER_URL/health
curl $API_URL/health
```

Expected: both return `{"status":"ok"}`.

---

### Step 8 — Confirm Pub/Sub subscription state and backlog

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID \
  --format="value(pushConfig.pushEndpoint,state)"
```

Expected: subscription state `ACTIVE`, push endpoint confirmed.

Check backlog (should be 0 or near 0 before publish):

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID
```

Look for `numUndeliveredMessages` in the output. Abort if backlog is non-zero and
unexplained.

---

### Step 9 — Record START_TIME and publish 100 events

> Record `START_TIME` immediately before publishing.

```bash
START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "START_TIME=$START_TIME"
```

Publish exactly 100 events from the validated JSONL. The publish command is implementation-
dependent on the live publish tool or `apps/pubsub-publisher`. The key requirements are:

- Publish exactly the 100 lines from `docs/evidence/load-test-100-cloud/events-100.jsonl`.
- Each line must be published as a separate Pub/Sub message.
- Throttle to no more than 50 messages/second.
- Stop immediately on any publish error.
- Record the total number of `messageId` values returned.

Record the publish summary:

```bash
# After publishing completes:
# - Total messages published: should equal 100
# - Total messageId values returned: should equal 100
# - Total elapsed publish time: record in seconds
```

**Abort if any individual message does not return a `messageId`.**

---

### Step 10 — Observe Pub/Sub backlog immediately after publish

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID
```

Expected: `numUndeliveredMessages` close to 100 (messages not yet delivered to worker).

Record this value in the evidence document.

---

### Step 11 — Wait for backlog drain

Observe the backlog at intervals (e.g. every 30 seconds) until it reaches 0 or near 0.
Expected drain time for 100 events: under 2 minutes under normal conditions.

**If the backlog does not begin draining within 5 minutes, abort.**

```bash
# Repeat until near 0:
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID
```

Record the observation timestamps and backlog values in the evidence document.

---

### Step 12 — Query Cloud Logging for worker success logs

Filter for `status=ok` entries scoped to the test prefix:

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="ok"
jsonPayload.event_id =~ "^loadtest-100-PREFIX_TIMESTAMP-"
```

Expected: at least one `status=ok` entry per processed event. Count should approach 100.

Also check that the error filter returns zero results:

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="error"
jsonPayload.event_id =~ "^loadtest-100-PREFIX_TIMESTAMP-"
```

Expected: zero results. Any error entries are an abort signal.

---

### Step 13 — Query Cloud Monitoring for worker_message_processed_count

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://monitoring.googleapis.com/v3/projects/$PROJECT_ID/timeSeries\
?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fworker_message_processed_count%22\
&interval.startTime=$START_TIME\
&interval.endTime=$END_TIME"
```

Expected: datapoints distributed across DELTA intervals; sum of all `int64Value` values
within the window approximately equals 100.

Record the raw JSON response summary in the evidence document.

---

### Step 14 — Query API /events for prefix-related records

```bash
curl "$API_URL/events?limit=100"
```

Filter the response for records whose `event_id` starts with `loadtest-100-$PREFIX_TIMESTAMP-`.
At least one record must be present. For a complete run the count should approach 100
(subject to endpoint page limits — paginate with `limit` and `offset` if needed).

---

### Step 15 — Run silver refresh job

Run only after ingest and backlog drain are confirmed (Steps 11–12).

```bash
gcloud run jobs execute rtdp-silver-refresh-job \
  --region=$REGION \
  --project=$PROJECT_ID \
  --wait
```

Wait for the job execution to complete before proceeding to readback.

Record the execution name returned by the command.

---

### Step 16 — Query Cloud Logging for silver refresh success

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="ok"
```

Expected: one `status=ok` entry for the execution run triggered in Step 15.

---

### Step 17 — Query API /aggregates/minute

```bash
curl "$API_URL/aggregates/minute?limit=20"
```

Expected: at least one aggregate row for each symbol used in the test run (`BTCUSDT`,
`ETHUSDT`, `SOLUSDT`). Rows should reflect the minute buckets covered by the test
`event_timestamp` values.

---

### Step 18 — Stop Cloud SQL immediately after evidence collection

> This must be the first action after readback is complete. Do not defer.

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER \
  --project=$PROJECT_ID
```

---

### Step 19 — Confirm final Cloud SQL state

```bash
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)" \
  --project=$PROJECT_ID
```

Expected: `NEVER   STOPPED`

**The execution window is not closed until this is confirmed and recorded.**

---

### Step 20 — Document all evidence

Create `docs/load-test-100-cloud-evidence.md` on the execution branch. See Section 6 for the
required evidence checklist.

Run final validation on the execution branch after the evidence document is committed:

```bash
uv run pytest -q
uv run ruff check .
```

---

## 6. Evidence Checklist

All items below must be captured in `docs/load-test-100-cloud-evidence.md` on the execution
branch.

| # | Evidence item | Description |
|---|---|---|
| 1 | Generated file path | `docs/evidence/load-test-100-cloud/events-100.jsonl` — confirm exists |
| 2 | Local validator report status | `status=ok` from `local-validation-report-100.json` |
| 3 | Prefix timestamp | `PREFIX_TIMESTAMP` value recorded before publishing |
| 4 | Publish command output summary | Total messages published, total messageId count, elapsed time |
| 5 | Number of message IDs | Must equal 100 |
| 6 | Pub/Sub backlog before publish | Value from Step 8 |
| 7 | Pub/Sub backlog immediately after publish | Value from Step 10 |
| 8 | Pub/Sub backlog drain observation | Timestamps and values from Step 11 |
| 9 | Worker log sample | At least one `jsonPayload.status=ok` log entry for the prefix |
| 10 | Worker error log check | Confirm zero `status=error` entries for the prefix |
| 11 | `worker_message_processed_count` datapoint summary | Sum and interval breakdown from Cloud Monitoring response |
| 12 | API `/events` sample | Raw response excerpt showing prefix-matching `event_id` records |
| 13 | Silver refresh execution name | Execution name returned by `gcloud run jobs execute` |
| 14 | Silver refresh log sample | `jsonPayload.status=ok` log entry for the execution |
| 15 | API `/aggregates/minute` sample | Raw response excerpt showing aggregate rows after refresh |
| 16 | Cloud SQL final state | Output of `gcloud sql instances describe ... --format="value(settings.activationPolicy,state)"` — must be `NEVER   STOPPED` |
| 17 | Test and ruff validation after evidence doc | `uv run pytest -q` and `uv run ruff check .` output — both must pass |

---

## 7. Acceptance Criteria

The execution run is accepted only if **all** of the following are true:

| Criterion | Required |
|---|---|
| Publish acknowledgements / message IDs | Exactly 100 |
| Local validator report status | `ok` |
| Worker `status=error` logs for prefix | Zero |
| Worker `status=ok` logs for prefix | At least one (target: approaches 100) |
| `worker_message_processed_count` increment in window | Approximately 100 (sum of DELTA datapoints) |
| API `/events` prefix-related rows | At least one |
| Pub/Sub backlog final state | 0 or near 0 |
| Silver refresh job | Emits `status=ok` in Cloud Logging |
| API `/aggregates/minute` rows after refresh | At least one |
| Cloud SQL final state | `NEVER   STOPPED` |
| Tests after evidence doc | Pass |
| Ruff after evidence doc | Pass |

---

## 8. Abort Criteria

Abort execution immediately (stop publishing or stop the current step; do not proceed to
readback) if any of the following are observed:

| Condition | Action |
|---|---|
| Cloud SQL does not reach `RUNNABLE` within a reasonable window | Abort; record state; do not publish |
| Cloud SQL cannot be returned to `NEVER / STOPPED` | Do not close the execution window until resolved |
| Worker or API health check fails | Abort before publishing |
| Pub/Sub subscription is not `ACTIVE` | Abort before publishing |
| Pub/Sub backlog pre-publish is non-zero and unexplained | Investigate and abort |
| Any individual publish call fails to return a `messageId` | Stop publishing immediately |
| `worker_message_error_count` increases unexpectedly | Treat as abort signal |
| Worker `status=error` logs appear for the test prefix | Treat as abort signal |
| Pub/Sub backlog does not begin draining within 5 minutes of publish completion | Abort; record state |
| API readback fails or returns no records | Record as failure; do not claim acceptance |
| Cloud SQL cost-control state cannot be confirmed | Do not close the window |

On abort: record the abort condition, the last known published count, and the Cloud SQL
state at the time of abort. Do not attempt the same run again without diagnosing the cause.

---

## 9. What This Future Execution Will Prove

These claims are safe only after the evidence document has been captured and merged:

- First controlled live cloud run of exactly 100 valid Pub/Sub messages against the deployed
  GCP pipeline.
- End-to-end GCP processing demonstrated under bounded conditions: Pub/Sub → Cloud Run
  worker → Cloud SQL → silver refresh → API readback.
- Traceability by deterministic prefix: logs, metrics, and API readback are all scoped to
  the same `loadtest-100-<PREFIX_TIMESTAMP>-` prefix.
- Cost-control discipline: Cloud SQL started only for the execution window and confirmed
  `NEVER / STOPPED` after.

---

## 10. What It Will Not Prove

Even after successful completion:

- High throughput or sustained streaming performance
- Production scale or enterprise SLA
- 1 000-event or 5 000-event capacity
- DLQ or retry safety under failure conditions
- Malformed-message handling
- Autoscaling limits or cold-start latency under load
- Sustained streaming benchmark
- Multi-region resilience
- Worker concurrency ceiling

---

## 11. Relationship to Roadmap

| Step | Status | Document |
|---|---|---|
| Single-event end-to-end GCP validation | Complete | [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) |
| Pub/Sub retry / DLQ inspection | Complete | [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) |
| Load-test plan (all sizes) | Plan only | [docs/load-test-plan.md](load-test-plan.md) |
| Local pre-publish sample evidence (100 events) | Complete | [docs/load-test-local-sample-evidence.md](load-test-local-sample-evidence.md) |
| **100-event cloud load test** | **This runbook — not yet executed** | Future: `docs/load-test-100-cloud-evidence.md` |
| 1 000-event cloud load test | Blocked — requires 100-event run complete | Future |
| 5 000-event cloud load test | Blocked — requires 1 000-event run complete | Future |
| Dashboard and alerting | Blocked — requires load-test evidence | Future |

This runbook is the immediate next safe step after the local pre-publish sample evidence.
It advances Devil's Advocate gap #1 (single-event end-to-end does not demonstrate meaningful
volume). The run intentionally excludes DLQ / retry risk: the production push subscription
has no DLQ configured (confirmed in
[docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md)), and only valid
messages are published.

Successful completion of this runbook's execution enables:

- 1 000-event load test planning
- Cloud Monitoring dashboard work (can reference actual load-test datapoints)
- Refined acceptance criteria at higher event counts

---

## Related Documents

| Document | Relationship |
|---|---|
| [docs/load-test-plan.md](load-test-plan.md) | Full load-test plan covering all test sizes, backlog observation, cost-control protocol, and acceptance criteria |
| [docs/load-test-local-sample-evidence.md](load-test-local-sample-evidence.md) | Local pre-publish sample evidence for the 100-event size — the precondition this runbook depends on |
| [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) | Single-event baseline this runbook extends to 100 events |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Cloud Monitoring REST API query method used in Step 13 |
| [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) | Confirms no DLQ on production subscription; informs valid-messages-only constraint |
| [docs/silver-refresh-job-validation.md](silver-refresh-job-validation.md) | Silver refresh execution evidence; reference for expected response shapes |
| [docs/cloud-error-counter-validation-plan.md](cloud-error-counter-validation-plan.md) | Error counter plan; abort conditions in this runbook reference that work |
