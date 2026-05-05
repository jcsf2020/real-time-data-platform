# Load-Test 1000-Event Cloud Runbook

## Status

**RUNBOOK ONLY — NOT EXECUTED**

This is an operational runbook. The 1000-event cloud load test has **not been executed**.
No Pub/Sub messages have been published. No Cloud SQL instance has been started. No GCP
resources have been mutated on this branch.

This runbook exists solely to define the precise, reviewable execution sequence for a future
branch or session. Read every command block as documentation, not as executed evidence.

This runbook builds on the **accepted 100-event cloud evidence** documented in
[docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md). All acceptance
criteria from that run were met. The preconditions below incorporate lessons learned from
that execution.

---

## 1. Scope

### Covered by this runbook

- Second controlled live GCP load test: exactly 1000 valid Pub/Sub messages
- Pre-publish JSONL generation and local validation (deterministic generator path)
- Cloud SQL start / stop protocol
- Pub/Sub publish and backlog observation
- Worker structured log validation (success path only)
- `worker_message_processed_count` Cloud Monitoring timeSeries query
- API `/events` readback (with pagination if needed)
- API `/aggregates/minute` readback with field-level capture
- Silver refresh job execution and log validation
- Cloud SQL final cost-control state confirmation
- Evidence checklist and acceptance criteria

### Explicitly excluded from this runbook

- Malformed or schema-invalid messages
- Retry / DLQ testing on the production push subscription
- 5 000-event test runs
- IaC changes (Terraform or gcloud configuration mutations)
- Alert policy creation or Cloud Monitoring dashboard creation
- Production benchmark or SLA claims
- Autoscaling stress or concurrency limit testing
- Multi-region or failover testing

---

## 2. Objective

Execute exactly 1000 valid Pub/Sub messages through the deployed GCP pipeline using the
already-validated local generator and validator path, then collect end-to-end evidence
across:

- Pub/Sub publish count and message IDs
- Publish elapsed seconds
- Pub/Sub backlog observation (if exposed — see Section 3 limitations)
- Cloud Run worker structured logs (`jsonPayload.status=ok`) scoped to the test prefix
- Worker `status=error` log count for the test prefix
- `worker_message_processed_count` Cloud Monitoring timeSeries datapoints over the execution
  window
- API `/events` readback filtered to the test prefix (with pagination or limit/offset)
- Silver refresh job Cloud Logging success entry
- API `/aggregates/minute` readback with field names and row samples captured before Cloud SQL
  is stopped
- Cloud SQL final cost-control state (`NEVER / STOPPED`)

All evidence must be captured in `docs/load-test-1000-cloud-evidence.md` on the execution
branch.

---

## 3. Preconditions

All of the following must be true before any execution commands are run. Abort if any
precondition cannot be confirmed.

| # | Precondition | How to verify |
|---|---|---|
| 1 | `docs/load-test-100-cloud-evidence.md` must be merged into `main` | `git log main --oneline -- docs/load-test-100-cloud-evidence.md` |
| 2 | This must run on a **future execution/evidence branch** — not this runbook branch | `git branch --show-current` |
| 3 | `main` is clean and synced | `git status` on `main`; `git fetch && git log origin/main..main` |
| 4 | All tests pass | `uv run pytest -q` exits 0 |
| 5 | Ruff passes | `uv run ruff check .` exits 0 |
| 6 | Local 1000-event JSONL validates with `status=ok` before publish | `uv run python scripts/validate_load_test_events.py ...` |
| 7 | Cloud SQL is currently `NEVER / STOPPED` (confirmed read-only) | `gcloud sql instances describe rtdp-postgres --format="value(settings.activationPolicy,state)"` |
| 8 | Worker health endpoint returns `{"status":"ok"}` (requires identity token — see known limitation) | `curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" $WORKER_URL/health` |
| 9 | API health endpoint returns `{"status":"ok"}` | `curl $API_URL/health` |
| 10 | Pub/Sub subscription `market-events-raw-worker-push` is `ACTIVE` | `gcloud pubsub subscriptions describe market-events-raw-worker-push --format="value(state)"` |
| 11 | No active loadtest prefix is draining (check Cloud Logging for recent `loadtest-` prefixes) | Cloud Logging query for recent `loadtest-1000-` prefix entries |
| 12 | 100-event evidence limitations understood (see below) | Review before execution |

### Known limitations from the 100-event run

These limitations were documented in
[docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) and apply to the
1000-event run unless resolved:

| Limitation | Detail |
|---|---|
| `numUndeliveredMessages` not exposed | `gcloud pubsub subscriptions describe` does not surface backlog for this push subscription. Use worker logs and metric sum as primary drain evidence. |
| Worker health requires identity token | `GET /health` on the worker returns HTTP 403 without an identity token. Use `gcloud auth print-identity-token` to authenticate. |
| `/aggregates/minute` field structure not fully captured | In the 100-event run, response field names were not recorded before Cloud SQL was stopped. **This run must capture field names and at least one row sample before stopping Cloud SQL.** |

---

## 4. Fixed Test Inputs

| Parameter | Value |
|---|---|
| Event count | `1000` |
| Prefix timestamp | Determined at execution time: `YYYYMMDDHHMMSS` wall-clock |
| Event ID prefix | `loadtest-1000-<PREFIX_TIMESTAMP>-` |
| JSONL output path | `docs/evidence/load-test-1000-cloud/events-1000.jsonl` |
| Validator report path | `docs/evidence/load-test-1000-cloud/local-validation-report-1000.json` |
| Cloud evidence document | `docs/load-test-1000-cloud-evidence.md` |

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
| `END_TIME` | RFC3339 timestamp at least 15 minutes after processing is confirmed |

---

## 5. Scaling Differences from the 100-Event Run

These differences must be understood before execution and reflected in evidence capture.

| Dimension | 100-event run | 1000-event run |
|---|---|---|
| Publish time | 6.38 seconds observed | Longer — expect ~60–90 seconds at ≤50 msg/s |
| Cloud SQL uptime window | Short (minutes) | Longer to allow full drain and readback |
| Worker `status=ok` log entries | 100 | Target exactly 1000; approach 1000 if partial logging |
| Cloud Monitoring DELTA intervals | Distributed across 2 intervals observed | Will spread across more 1-minute intervals |
| API `/events` pagination | Single call with `limit=100` returned all 100 rows | May require `limit` and `offset` iteration to retrieve all 1000 rows |
| Aggregate minute buckets | 10 rows observed (spanning ~2 minutes) | More rows expected — events span more minute buckets |
| Backlog observation | Not directly observable via gcloud CLI | Same limitation expected; use logs/metrics as primary drain evidence |
| Evidence capture | Field names not recorded for `/aggregates/minute` | **Must capture field names and row samples this run** |

---

## 6. Execution Sequence

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

Expected: tests pass, ruff clean, branch is NOT `docs/load-test-1000-cloud-runbook`.

---

### Step 2 — Generate 1000-event JSONL locally

```bash
# Record prefix timestamp BEFORE running (wall-clock, YYYYMMDDHHMMSS)
PREFIX_TIMESTAMP=$(date +%Y%m%d%H%M%S)
echo "PREFIX_TIMESTAMP=$PREFIX_TIMESTAMP"

mkdir -p docs/evidence/load-test-1000-cloud

uv run python scripts/generate_load_test_events.py \
  --size 1000 \
  --prefix-timestamp $PREFIX_TIMESTAMP \
  --output docs/evidence/load-test-1000-cloud/events-1000.jsonl
```

Expected: file created with exactly 1000 lines.

---

### Step 3 — Validate 1000-event JSONL locally

```bash
uv run python scripts/validate_load_test_events.py \
  --input docs/evidence/load-test-1000-cloud/events-1000.jsonl \
  --size 1000 \
  --prefix-timestamp $PREFIX_TIMESTAMP \
  --report-output docs/evidence/load-test-1000-cloud/local-validation-report-1000.json
```

Expected: `{"status":"ok","observed_count":1000,"unique_event_ids":1000,"worker_contract_validation":"passed","errors":[],...}`

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
# API health (no auth required)
curl $API_URL/health

# Worker health (identity token required — known Cloud Run IAM behaviour)
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  $WORKER_URL/health
```

Expected: both return `{"status":"ok"}`.

---

### Step 8 — Confirm Pub/Sub subscription state

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID \
  --format="value(pushConfig.pushEndpoint,state)"
```

Expected: subscription state `ACTIVE`, push endpoint confirmed.

Backlog check:

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID
```

Note: `numUndeliveredMessages` may not be exposed (known limitation from 100-event run).
Abort if backlog is non-zero and unexplained by a prior test. If not visible, record the
CLI limitation and proceed only if no prior active prefix is draining.

---

### Step 9 — Record START_TIME and publish 1000 events

> Record `START_TIME` immediately before publishing.

```bash
START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "START_TIME=$START_TIME"
```

Publish exactly 1000 events from the validated JSONL. The publish command is implementation-
dependent on the live publish tool or `apps/pubsub-publisher`. The key requirements are:

- Publish exactly the 1000 lines from `docs/evidence/load-test-1000-cloud/events-1000.jsonl`.
- Each line must be published as a separate Pub/Sub message.
- Throttle to no more than 50 messages/second (estimated publish time: ~60–90 seconds).
- Stop immediately on any publish error.
- Record the total number of `messageId` values returned.

Record the publish summary:

```bash
# After publishing completes:
# - Total messages published: should equal 1000
# - Total messageId values returned: should equal 1000
# - Total elapsed publish time: record in seconds
# - Error count: must be 0
```

**Abort if any individual message does not return a `messageId`.**

---

### Step 10 — Observe Pub/Sub backlog immediately after publish

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=$PROJECT_ID
```

Note: `numUndeliveredMessages` may not be exposed (known CLI limitation). Record the output.
If not visible, document the limitation and use worker logs and metric sum as primary drain
evidence.

---

### Step 11 — Wait for processing window

Monitor Cloud Logging for worker `status=ok` entries accumulating for the prefix. At 1000
events the drain window is expected to be longer than the 100-event run (~24 seconds observed).
Allow at least 5–10 minutes before asserting drain completion.

**If no worker logs appear within 5 minutes of publish completion, abort.**

---

### Step 12 — Query Cloud Logging for worker success logs

Filter for `status=ok` entries scoped to the test prefix:

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="ok"
jsonPayload.event_id =~ "^loadtest-1000-PREFIX_TIMESTAMP-"
```

Expected: count should approach 1000. Record total count and unique `event_id` count.

Also confirm zero error logs:

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="error"
jsonPayload.event_id =~ "^loadtest-1000-PREFIX_TIMESTAMP-"
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

Expected: datapoints distributed across more DELTA intervals than the 100-event run; sum of
all `int64Value` values within the window approximately equals 1000.

Record the raw JSON response summary — interval boundaries, per-interval values, and total
sum — in the evidence document.

---

### Step 14 — Query API /events for prefix-related records

```bash
# First call — try a sufficient limit
curl "$API_URL/events?limit=1000"
```

Filter the response for records whose `event_id` starts with `loadtest-1000-$PREFIX_TIMESTAMP-`.
Count the matching records. If the endpoint has a lower page limit (e.g. 100 or 200), paginate
using `limit` and `offset`:

```bash
# Paginate if limit is enforced below 1000
curl "$API_URL/events?limit=100&offset=0"
curl "$API_URL/events?limit=100&offset=100"
# ... continue until all prefix-matching rows are accounted for
```

Record the total prefix-matching count and the pagination method used.

---

### Step 15 — Run silver refresh job

Run only after ingest and processing window are confirmed (Steps 11–12).

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

Expected: one `status=ok` entry for the execution triggered in Step 15.

---

### Step 17 — Query API /aggregates/minute and capture field names

```bash
curl "$API_URL/aggregates/minute?limit=50"
```

**This step must capture:**
- Total row count
- All field names present in the response objects (not recorded in 100-event run)
- At least one complete row sample as raw JSON
- Symbols present in the response

Expected: more rows than the 100-event run; rows span more minute buckets. At least one
aggregate row per expected symbol (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`).

**Do not stop Cloud SQL before this evidence is captured.**

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

Create `docs/load-test-1000-cloud-evidence.md` on the execution branch. See Section 7 for
the required evidence checklist.

Run final validation on the execution branch after the evidence document is committed:

```bash
uv run pytest -q
uv run ruff check .
```

---

## 7. Evidence Checklist

All items below must be captured in `docs/load-test-1000-cloud-evidence.md` on the execution
branch.

| # | Evidence item | Description |
|---|---|---|
| 1 | Generated file path | `docs/evidence/load-test-1000-cloud/events-1000.jsonl` — confirm exists and line count = 1000 |
| 2 | Local validator report status | `status=ok` from `local-validation-report-1000.json` |
| 3 | Prefix timestamp | `PREFIX_TIMESTAMP` value recorded before publishing |
| 4 | Publish command output summary | Total messages published, total messageId count, elapsed seconds, error count |
| 5 | Number of message IDs | Must equal 1000 |
| 6 | Publish elapsed seconds | Record actual elapsed time |
| 7 | Pub/Sub backlog observation | Value from gcloud describe, or documented CLI limitation if not exposed |
| 8 | Worker log sample | At least one `jsonPayload.status=ok` log entry for the prefix |
| 9 | Worker `status=ok` log count | Total count and unique `event_id` count for the prefix |
| 10 | Worker error log check | Confirm zero `status=error` entries for the prefix |
| 11 | `worker_message_processed_count` datapoint summary | Interval boundaries, per-interval values, total sum from Cloud Monitoring response |
| 12 | API `/events` prefix-matching count | Total matching rows and pagination method used |
| 13 | API `/events` sample | Raw response excerpt showing prefix-matching `event_id` records |
| 14 | Silver refresh execution name | Execution name returned by `gcloud run jobs execute` |
| 15 | Silver refresh log sample | `jsonPayload.status=ok` log entry for the execution |
| 16 | API `/aggregates/minute` row count | Total rows returned |
| 17 | API `/aggregates/minute` field names | All field names present in the response objects |
| 18 | API `/aggregates/minute` row sample | At least one complete row as raw JSON |
| 19 | Cloud SQL final state | Output of `gcloud sql instances describe ... --format="value(settings.activationPolicy,state)"` — must be `NEVER   STOPPED` |
| 20 | Tests after evidence doc | `uv run pytest -q` — must pass |
| 21 | Ruff after evidence doc | `uv run ruff check .` — must pass |

---

## 8. Acceptance Criteria

The execution run is accepted only if **all** of the following are true:

| Criterion | Required |
|---|---|
| Publish acknowledgements / message IDs | Exactly 1000 |
| Local validator report status | `ok` |
| Worker `status=error` logs for prefix | Zero |
| Worker `status=ok` logs for prefix | Approach 1000; target exactly 1000 if logs fully returned |
| `worker_message_processed_count` metric sum in window | Approximately 1000 (sum across all DELTA intervals) |
| API `/events` prefix-related rows | At least one; target 1000 if pagination allows full retrieval |
| Pub/Sub backlog final state | 0 or near 0 if observable; confirmed via 1000 ok logs and metric sum if not directly observable |
| Silver refresh job | Emits `status=ok` in Cloud Logging |
| API `/aggregates/minute` rows after refresh | At least one; more rows than 100-event run |
| API `/aggregates/minute` field names | Captured |
| Cloud SQL final state | `NEVER   STOPPED` |
| Tests after evidence doc | Pass |
| Ruff after evidence doc | Pass |

---

## 9. Abort Criteria

Abort execution immediately (stop publishing or stop the current step; do not proceed to
readback) if any of the following are observed:

| Condition | Action |
|---|---|
| Cloud SQL does not reach `RUNNABLE` within a reasonable window | Abort; record state; do not publish |
| Cloud SQL cannot be returned to `NEVER / STOPPED` | Do not close the execution window until resolved |
| Worker or API health check fails | Abort before publishing |
| Pub/Sub subscription is not `ACTIVE` | Abort before publishing |
| Any individual publish call fails to return a `messageId` | Stop publishing immediately |
| Message ID count after publish != 1000 | Treat as abort signal |
| Worker `status=error` logs appear for the test prefix | Treat as abort signal |
| `worker_message_error_count` increases unexpectedly | Treat as abort signal |
| Worker `status=ok` log count stalls far below expected after reasonable window | Investigate; abort if not recovering |
| No worker logs appear within 5 minutes of publish completion | Abort; record state |
| API readback fails completely | Record as failure; do not claim acceptance |
| Cloud SQL cost-control state cannot be confirmed | Do not close the window |

On abort: record the abort condition, the last known published count, and the Cloud SQL
state at the time of abort. Do not attempt the same run again without diagnosing the cause.

---

## 10. What This Future Execution Will Prove

These claims are safe only after the evidence document has been captured and merged:

- Second controlled live cloud run under this validation programme: exactly 1000 valid Pub/Sub
  messages processed end-to-end through the deployed GCP pipeline.
- Stronger bounded scale evidence than the 100-event run: 10× the message count under
  observed GCP managed-service conditions.
- Traceability by deterministic prefix: logs, metrics, and API readback all scoped to
  `loadtest-1000-<PREFIX_TIMESTAMP>-`.
- Cloud Monitoring metric datapoints distributed across multiple DELTA intervals at sustained
  multi-second publish volume.
- Cost-control discipline maintained: Cloud SQL started only for the execution window and
  confirmed `NEVER / STOPPED` after.

---

## 11. What It Will Not Prove

Even after successful completion:

- High throughput or sustained streaming performance
- Production scale or enterprise SLA
- 5 000-event capacity
- DLQ or retry safety under failure conditions
- Malformed-message handling
- Autoscaling limits or cold-start latency under load
- Sustained streaming benchmark
- Multi-region resilience
- Worker concurrency ceiling
- Latency SLO or SLA
- Any claim beyond controlled bounded ingest under observed conditions

---

## 12. Relationship to Roadmap

| Step | Status | Document |
|---|---|---|
| Single-event end-to-end GCP validation | Complete | [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) |
| Pub/Sub retry / DLQ inspection | Complete | [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) |
| Load-test plan (all sizes) | Plan only | [docs/load-test-plan.md](load-test-plan.md) |
| Local pre-publish sample evidence (100 events) | Complete | [docs/load-test-local-sample-evidence.md](load-test-local-sample-evidence.md) |
| 100-event cloud load test | **Complete — evidence accepted** | [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) |
| **1000-event cloud load test** | **This runbook — not yet executed** | Future: `docs/load-test-1000-cloud-evidence.md` |
| 5 000-event cloud load test | Blocked — requires 1 000-event run complete | Future |
| Dashboard and alerting | Blocked — requires load-test evidence | Future |

The 1000-event run is the immediate next safe step after the accepted 100-event cloud
evidence. It advances Devil's Advocate gap #1 (scale and throughput evidence) beyond the
100-event baseline. This run publishes only valid messages and excludes DLQ / retry risk
(the production push subscription has no DLQ configured, confirmed in
[docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md)).

**Successful completion of this runbook's execution enables:**

- Dashboard work with richer metric data across more DELTA intervals
- 5 000-event load test planning
- Stronger B2B and recruiter claims: "controlled load test at 1 000-event scale with
  full log, metric, and API readback evidence"

**This run still does not close:**

- DLQ / retry gap
- IaC (Terraform / gcloud configuration mutations) gap
- Analytics (BigQuery / Dataflow) gap
- Alerting and dashboard gap
- Multi-region or autoscaling gap

---

## Related Documents

| Document | Relationship |
|---|---|
| [docs/load-test-plan.md](load-test-plan.md) | Full load-test plan covering all test sizes, backlog observation, cost-control protocol, and acceptance criteria |
| [docs/load-test-100-cloud-runbook.md](load-test-100-cloud-runbook.md) | Runbook for the 100-event run; this runbook extends that execution sequence to 1000 events |
| [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) | Accepted 100-event cloud evidence; precondition for this runbook |
| [docs/load-test-local-sample-evidence.md](load-test-local-sample-evidence.md) | Local pre-publish sample evidence for the 100-event size |
| [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) | Single-event baseline extended progressively by 100- and 1000-event runs |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Cloud Monitoring REST API query method used in Step 13 |
| [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) | Confirms no DLQ on production subscription; informs valid-messages-only constraint |
| [docs/silver-refresh-job-validation.md](silver-refresh-job-validation.md) | Silver refresh execution evidence; reference for expected response shapes |
| [docs/cloud-error-counter-validation-plan.md](cloud-error-counter-validation-plan.md) | Error counter plan; abort conditions in this runbook reference that work |
