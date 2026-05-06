# Isolated Error Counter Validation Runbook

## Status

**RUNBOOK ONLY — NOT EXECUTED**

This is a future execution runbook. No GCP write operations have been performed. No messages
have been published. No Cloud SQL instance has been started. No topics, subscriptions, or Cloud
Run jobs have been created or deleted. No application code has been changed.

All command blocks below are templates for a future execution branch. No command here has been
run. Read every command block as documentation, not as evidence.

This runbook builds on:

- [docs/cloud-error-counter-validation-plan.md](cloud-error-counter-validation-plan.md) — the
  planning analysis that identified the isolated path requirement.
- [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) — the read-only
  inspection that confirmed no DLQ/deadLetterPolicy on the production push subscription and
  blocked unsafe message publishing.
- [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) — the success-counter datapoint evidence that establishes the baseline Cloud Monitoring query method.

---

## 1. Purpose

Validate the two remaining error-counter logs-based metrics:

- `worker_message_error_count`
- `silver_refresh_error_count`

Both are DELTA INT64 counters. They increment when a matching structured log entry is written to
Cloud Logging from a deployed Cloud Run service or job. Local `pytest` does not feed Cloud
Logging and therefore cannot produce Cloud Monitoring timeSeries datapoints. Cloud-level
validation through real GCP resource execution is required.

This runbook defines a controlled, bounded execution plan that:

- Uses fully isolated Pub/Sub resources (topic, DLQ, push subscription) with explicit
  `maxDeliveryAttempts` and `deadLetterPolicy` — never touching the production topic or
  subscription.
- Uses a temporary Cloud Run Job copy with an intentionally missing `DATABASE_URL` to trigger
  the silver refresh error path without mutating the production job.
- Requires mandatory cleanup of all temporary resources before the execution branch is merged.
- Keeps Cloud SQL in `NEVER / STOPPED` state throughout.

---

## 2. Current State

| Metric | Status |
|---|---|
| `worker_message_processed_count` | Has validated Cloud Monitoring datapoints — 1000 events confirmed in the 1000-event load test (sum = 1000, 850 + 150 per-minute split). |
| `worker_message_error_count` | Metric descriptor exists and filter is validated in code and tests; **no safe Cloud Monitoring datapoint yet**. |
| `silver_refresh_success_count` | Has validated Cloud Monitoring datapoints — confirmed in [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md). |
| `silver_refresh_error_count` | Metric descriptor exists and filter is validated in code and tests; **no safe Cloud Monitoring datapoint yet**. |

**Production subscription state (from [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md)):**

- `market-events-raw-worker-push` has an **active push endpoint** pointing at the live
  production worker.
- **No `deadLetterPolicy`** — no DLQ is configured.
- **No `maxDeliveryAttempts`** — retry count is unbounded within `messageRetentionDuration`.
- **No `retryPolicy`** field — backoff is governed by Pub/Sub defaults.

A malformed message published to `market-events-raw` would cause repeated HTTP 500 responses
from the worker and continuous unbounded Pub/Sub retries for up to 600 s, polluting production
metrics and logs.

**Therefore: malformed messages must not be sent to `market-events-raw` or via any subscription
of `market-events-raw`. This is an absolute constraint for all execution steps.**

---

## 3. Safety Rules

The following rules are absolute constraints for any future execution branch that follows this
runbook. Violation of any rule is grounds for immediate abort.

1. **Do not publish any message — malformed or otherwise — to `market-events-raw`.**
2. **Do not mutate `market-events-raw-worker-push` in any way** (no config changes, no
   additions of deadLetterPolicy, no updates to the push endpoint).
3. **Use isolated topic/subscription/DLQ only.** All malformed message publishing must target
   `market-events-raw-error-test` exclusively.
4. **Confirm bounded retry before publishing any malformed message.** Run
   `gcloud pubsub subscriptions describe market-events-raw-error-test-worker-push` and verify
   `deadLetterPolicy.maxDeliveryAttempts` is present and set to ≤ 5 before publishing.
5. **Capture evidence before cleanup.** Do not delete any temporary resource before the log
   query and Cloud Monitoring timeSeries query have been run and results recorded.
6. **Cleanup is mandatory.** All temporary resources (isolated topic, DLQ topic, push
   subscription, temporary silver refresh job) must be deleted and their deletion verified before
   the evidence document is committed.
7. **Cloud SQL must remain `NEVER / STOPPED` throughout.** Do not start `rtdp-postgres` at any
   point. Do not execute any step that requires a live database connection unless a specific
   future step of this runbook explicitly and intentionally requires it (none do).
8. **Confirm Cloud SQL `NEVER / STOPPED` as the final post-cleanup check.** The execution run
   is not complete until this is recorded.

---

## 4. Pre-Execution Checks

> **Future execution only — do not run during this runbook branch.**
>
> Run these checks on the future execution branch before any GCP write operation. Abort if any
> check fails or returns an unexpected result.

### Check 1 — Git and branch state

```bash
git status --short --branch
```

Expected: execution branch is not `docs/isolated-error-counter-validation-runbook`. Working tree
is clean or shows only the evidence document in progress.

---

### Check 2 — Tests

```bash
uv sync --all-packages
uv run pytest -q
```

Expected: 116 tests pass, exit 0.

---

### Check 3 — Ruff

```bash
uv run ruff check .
```

Expected: all checks passed, exit 0.

---

### Check 4 — Cloud SQL state (read-only)

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

**Abort if the output is anything other than `NEVER   STOPPED`.** Do not proceed with any GCP
write operation if Cloud SQL is not in this state.

---

### Check 5 — Existing metrics list (read-only)

```bash
gcloud logging metrics list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,metricDescriptor.metricKind,metricDescriptor.valueType)"
```

Expected output includes all four metrics:

```
NAME                            METRIC_KIND  VALUE_TYPE
silver_refresh_error_count      DELTA        INT64
silver_refresh_success_count    DELTA        INT64
worker_message_error_count      DELTA        INT64
worker_message_processed_count  DELTA        INT64
```

Abort if any of the four is missing.

---

### Check 6 — Production subscription state (read-only)

Confirm the current production subscription state before any further action, explicitly to
establish a pre-execution baseline and to verify that no mutation has occurred since
[docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md).

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

Expected:

- `pushConfig.pushEndpoint` is `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push`
- `topic` is `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw`
- `deadLetterPolicy` field is **absent**
- `maxDeliveryAttempts` field is **absent**
- `state` is `ACTIVE`

Record this output in the evidence document. This baseline confirms the production subscription
is not targeted in the steps that follow.

**Abort if `deadLetterPolicy` is present and points at any unexpected topic — the production
subscription must not have been mutated before this runbook began.**

---

## 5. Worker Error Counter Validation Design

This section defines the isolated Pub/Sub resources to create and the execution sequence for
validating `worker_message_error_count`.

### 5.1 Isolated resources

| Resource | Name |
|---|---|
| Isolated topic | `market-events-raw-error-test` |
| DLQ topic | `market-events-raw-error-test-dlq` |
| Push subscription | `market-events-raw-error-test-worker-push` |

The isolated push subscription must be configured with:

- Push endpoint: `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push`
- Push auth: OIDC token with service account `rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com`
- `maxDeliveryAttempts`: 5
- `deadLetterTopic`: `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-error-test-dlq`
- Retry policy with bounded backoff
- `messageRetentionDuration`: short enough for a controlled validation window (e.g., `600s`) but
  not so aggressively short that it expires before evidence can be captured

### 5.2 Pub/Sub service agent discovery

The Pub/Sub service agent needs `roles/pubsub.publisher` on the DLQ topic in order to forward
dead-lettered messages. Discover it as follows:

```bash
# Step 1 — get the project number
gcloud projects describe project-42987e01-2123-446b-ac7 \
  --format="value(projectNumber)"
```

The Pub/Sub service agent email is:

```
service-{PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com
```

Replace `{PROJECT_NUMBER}` with the value returned above.

### 5.3 Execution steps

> **Future execution only — do not run during this runbook branch.**

#### Step W-1 — Create isolated topic

```bash
gcloud pubsub topics create market-events-raw-error-test \
  --project=project-42987e01-2123-446b-ac7
```

#### Step W-2 — Create DLQ topic

```bash
gcloud pubsub topics create market-events-raw-error-test-dlq \
  --project=project-42987e01-2123-446b-ac7
```

#### Step W-3 — Grant Pub/Sub service agent publisher permission on DLQ

```bash
PROJECT_NUMBER="$(gcloud projects describe project-42987e01-2123-446b-ac7 --format='value(projectNumber)')"
PUBSUB_SA="service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"

gcloud pubsub topics add-iam-policy-binding market-events-raw-error-test-dlq \
  --project=project-42987e01-2123-446b-ac7 \
  --member="serviceAccount:${PUBSUB_SA}" \
  --role="roles/pubsub.publisher"
```

Record the resolved `PUBSUB_SA` value and the IAM binding output in the evidence document.

#### Step W-4 — Create isolated push subscription with dead-letter policy

```bash
gcloud pubsub subscriptions create market-events-raw-error-test-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --topic=market-events-raw-error-test \
  --push-endpoint=https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push \
  --push-auth-service-account=rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --max-delivery-attempts=5 \
  --dead-letter-topic=projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-error-test-dlq \
  --min-retry-delay=10s \
  --max-retry-delay=60s \
  --message-retention-duration=600s
```

#### Step W-5 — Describe isolated subscription and verify deadLetterPolicy before publishing

**This step is a hard gate. Do not publish until this check passes.**

```bash
gcloud pubsub subscriptions describe market-events-raw-error-test-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

Verify in the output:

- `deadLetterPolicy.deadLetterTopic` contains `market-events-raw-error-test-dlq`
- `deadLetterPolicy.maxDeliveryAttempts` is `5`
- `retryPolicy.minimumBackoff` is present
- `retryPolicy.maximumBackoff` is present
- `pushConfig.pushEndpoint` is `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push`
- `topic` contains `market-events-raw-error-test` (not `market-events-raw`)

**Abort if `deadLetterPolicy` is absent. Abort if `topic` contains `market-events-raw` without
the `-error-test` suffix — this would mean the subscription was accidentally attached to the
production topic.**

Record the full JSON output in the evidence document.

#### Step W-6 — Publish exactly one malformed message

The malformed payload must be base64-encoded non-JSON bytes. This is the minimal payload that
triggers a `JSONDecodeError` in the worker's `process_message` function, which emits
`status=error` in the structured log.

```bash
# Base64-encode a non-JSON string
MALFORMED_PAYLOAD="$(echo -n 'not-valid-json' | base64)"

gcloud pubsub topics publish market-events-raw-error-test \
  --project=project-42987e01-2123-446b-ac7 \
  --message="${MALFORMED_PAYLOAD}"
```

Record the message ID returned by this command in the evidence document.

**Do not publish more than one message. Do not target `market-events-raw`.**

#### Step W-7 — Wait for retry window

Wait approximately 2–3 minutes to allow up to 5 delivery attempts to complete and for the DELTA
window to close. The subscription `maxDeliveryAttempts` is 5 with `min-retry-delay=10s` and
`max-retry-delay=60s`, so the full retry window is bounded to well under 10 minutes.

#### Step W-8 — Query worker logs for status=error

```bash
gcloud logging read \
  'resource.type="cloud_run_revision"
   resource.labels.service_name="rtdp-pubsub-worker"
   jsonPayload.operation="process_message"
   jsonPayload.status="error"' \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=5 \
  --format=json
```

Expected: at least one log entry with `jsonPayload.status = "error"` and
`jsonPayload.operation = "process_message"`.

Record the relevant log entry JSON in the evidence document.

**Abort if no matching log entry appears within 5 minutes of the publish command. This indicates
the worker did not receive the message or the structured log fields do not match the metric
filter.**

#### Step W-9 — Query Cloud Monitoring timeSeries for worker_message_error_count

Wait at least one full minute after the log entry appears before querying, to allow the DELTA
window to close and the timeSeries to be written.

```bash
START_TIME="$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TOKEN="$(gcloud auth print-access-token)"

curl -s \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/timeSeries\
?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fworker_message_error_count%22\
&interval.startTime=${START_TIME}\
&interval.endTime=${END_TIME}"
```

Expected: response body contains at least one `timeSeries` entry with a `points` array
containing at least one entry where `value.int64Value` is a string representing a value `> 0`
(e.g., `"1"` or `"5"`).

Record the full JSON response in the evidence document.

**Abort (do not claim acceptance) if the response contains no `timeSeries` entries or all
`int64Value` values are `"0"`.**

---

## 6. Silver Refresh Error Counter Validation Design

This section defines the non-invasive strategy for validating `silver_refresh_error_count` using
a temporary Cloud Run Job copy.

### 6.1 Strategy

The `rtdp-silver-refresh-job` Cloud Run Job reads `DATABASE_URL` from Secret Manager. When
`DATABASE_URL` is missing, the job's `main()` function emits:

```json
{
  "component": "silver-refresh",
  "error_message": "DATABASE_URL environment variable is not set",
  "error_type": "EnvironmentError",
  "operation": "refresh_market_event_minute_aggregates",
  "service": "rtdp-silver-refresh-job",
  "status": "error"
}
```

This log entry matches the `silver_refresh_error_count` metric filter exactly. The job exits
without ever attempting a database connection, so no Cloud SQL start is required.

A temporary job named `rtdp-silver-refresh-job-error-test` will be created using the same
container image as the production job, but with `DATABASE_URL` deliberately absent.

### 6.2 Safety rules for this section

- **Do not run `gcloud run jobs update rtdp-silver-refresh-job`** or any command that mutates the
  production job definition.
- **Do not overwrite or delete production Secret Manager secrets.**
- The temporary job must use a distinct name (`rtdp-silver-refresh-job-error-test`) and must
  be deleted immediately after evidence is captured.
- Cloud SQL must remain `NEVER / STOPPED` throughout. The `DATABASE_URL` absent path is chosen
  precisely because it requires no database connection.

### 6.3 Execution steps

> **Future execution only — do not run during this runbook branch.**

#### Step S-1 — Inspect production job definition to obtain container image

The container image tag and any required non-secret environment variables must be discovered
from the production job before creating the temporary copy.

```bash
gcloud run jobs describe rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format=json
```

From the output, record:

- `spec.template.spec.template.spec.containers[0].image` — the container image URI to reuse.
- Any non-secret environment variables that are required for the job to reach the `DATABASE_URL`
  check (e.g., `LOG_LEVEL`, `SERVICE_NAME`).

**Do not copy the `DATABASE_URL` Secret Manager binding.** The temporary job must not have
`DATABASE_URL` set.

#### Step S-2 — Create temporary silver refresh job with missing DATABASE_URL

Replace `{IMAGE_URI}` with the image value from Step S-1.

```bash
gcloud run jobs create rtdp-silver-refresh-job-error-test \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --image={IMAGE_URI} \
  --max-retries=0 \
  --task-timeout=60s
```

Do not set `--set-secrets` or `--set-env-vars=DATABASE_URL=...`. The absence of `DATABASE_URL`
is what triggers the error path.

#### Step S-3 — Execute the temporary job once

```bash
gcloud run jobs execute rtdp-silver-refresh-job-error-test \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --wait
```

Record the execution name (e.g. `rtdp-silver-refresh-job-error-test-xxxxx`) in the evidence
document. The job should exit with a non-zero exit code after emitting the error log.

#### Step S-4 — Wait for the DELTA window to close

Wait at least one full minute after the job execution completes before querying Cloud Monitoring,
to allow the DELTA window to close.

#### Step S-5 — Query Cloud Logging for silver refresh status=error

```bash
gcloud logging read \
  'resource.type="cloud_run_job"
   resource.labels.job_name="rtdp-silver-refresh-job-error-test"
   jsonPayload.operation="refresh_market_event_minute_aggregates"
   jsonPayload.status="error"' \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=5 \
  --format=json
```

Expected: at least one log entry with `jsonPayload.status = "error"`,
`jsonPayload.operation = "refresh_market_event_minute_aggregates"`, and
`jsonPayload.error_type = "EnvironmentError"`.

Record the relevant log entry JSON in the evidence document.

**Note on metric filter matching:** The `silver_refresh_error_count` metric filter uses
`resource.labels.job_name="rtdp-silver-refresh-job"`. The temporary job is named
`rtdp-silver-refresh-job-error-test`, which may not match this filter exactly. If the log
query above returns results but the Cloud Monitoring timeSeries query (Step S-6) returns no
datapoints, the metric filter's `job_name` constraint is the likely cause.

**If this occurs, stop. Do not claim acceptance with log-only evidence.** The execution branch
must adjust the validation design before proceeding — for example, by inspecting the exact
`resource.labels.job_name` value emitted by Cloud Logging for the temporary job, and
determining whether the metric filter requires an exact literal match. If an exact match is
required, the execution branch must either rename the temporary job to match the filter or
create a separate short-lived job named exactly `rtdp-silver-refresh-job` for the duration of
the error injection, taking care not to conflict with the production job. Log entry evidence
confirms that the error code path runs correctly, but it does not substitute for a confirmed
`int64Value > 0` in the Cloud Monitoring timeSeries response.

#### Step S-6 — Query Cloud Monitoring timeSeries for silver_refresh_error_count

```bash
START_TIME="$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)"
END_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TOKEN="$(gcloud auth print-access-token)"

curl -s \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/timeSeries\
?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fsilver_refresh_error_count%22\
&interval.startTime=${START_TIME}\
&interval.endTime=${END_TIME}"
```

Expected: response body contains at least one `timeSeries` entry with `int64Value > 0`.

Record the full JSON response in the evidence document.

---

## 7. Cleanup

**Cleanup is mandatory before the evidence document is committed and before the branch is
merged.**

> **Future execution only — do not run during this runbook branch.**

### Cleanup W — Isolated worker error test resources

#### Step CW-1 — Delete isolated push subscription

```bash
gcloud pubsub subscriptions delete market-events-raw-error-test-worker-push \
  --project=project-42987e01-2123-446b-ac7 \
  --quiet
```

#### Step CW-2 — Delete isolated topic

```bash
gcloud pubsub topics delete market-events-raw-error-test \
  --project=project-42987e01-2123-446b-ac7 \
  --quiet
```

#### Step CW-3 — Delete DLQ topic

```bash
gcloud pubsub topics delete market-events-raw-error-test-dlq \
  --project=project-42987e01-2123-446b-ac7 \
  --quiet
```

#### Step CW-4 — Verify cleanup

```bash
gcloud pubsub topics list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name)"

gcloud pubsub subscriptions list \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name)"
```

Expected: `market-events-raw-error-test`, `market-events-raw-error-test-dlq`, and
`market-events-raw-error-test-worker-push` do not appear in the output.

Record the full list output in the evidence document.

---

### Cleanup S — Temporary silver refresh job

#### Step CS-1 — Delete temporary silver refresh job

```bash
gcloud run jobs delete rtdp-silver-refresh-job-error-test \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --quiet
```

#### Step CS-2 — Verify cleanup

```bash
gcloud run jobs list \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name)"
```

Expected: `rtdp-silver-refresh-job-error-test` does not appear in the output.

Record the full list output in the evidence document.

---

### Final cleanup check — Cloud SQL state

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

**The execution window is not closed until this is confirmed and recorded.**

---

## 8. Evidence to Capture

The future execution branch must create `docs/isolated-error-counter-validation-evidence.md`
and record all of the following before committing:

| # | Evidence item |
|---|---|
| 1 | Execution branch name |
| 2 | Pre-execution Cloud SQL state (`NEVER   STOPPED`) |
| 3 | All four metric descriptors confirmed present (`gcloud logging metrics list` output) |
| 4 | Pre-execution production subscription describe output (confirming no DLQ — baseline) |
| 5 | Pub/Sub service agent email resolved from `gcloud projects describe` output |
| 6 | DLQ IAM binding output (Pub/Sub service agent granted `roles/pubsub.publisher`) |
| 7 | Isolated push subscription describe output showing `deadLetterPolicy.maxDeliveryAttempts = 5` |
| 8 | Malformed message publish output, including the message ID |
| 9 | Worker error log query result (at least one entry with `status=error`) |
| 10 | `worker_message_error_count` timeSeries JSON output (at least one `int64Value > 0`) |
| 11 | Production job describe output (image URI, used to create the temporary job) |
| 12 | Temporary silver job execution name (e.g. `rtdp-silver-refresh-job-error-test-xxxxx`) |
| 13 | Silver refresh error log query result (at least one entry with `status=error`) |
| 14 | `silver_refresh_error_count` timeSeries JSON output (must contain at least one `int64Value > 0` — if not, stop and adjust the validation design per Section 6.3 before committing) |
| 15 | Isolated subscription/topic/DLQ cleanup verification (`gcloud pubsub topics list` and `gcloud pubsub subscriptions list` output) |
| 16 | Temporary silver job cleanup verification (`gcloud run jobs list` output) |
| 17 | Final Cloud SQL state (`NEVER   STOPPED`) |
| 18 | `uv run pytest -q` output after evidence doc is written |
| 19 | `uv run ruff check .` output after evidence doc is written |

---

## 9. Acceptance Criteria

The execution run is accepted only if **all** of the following are true:

| Criterion | Required |
|---|---|
| Production topic untouched | Zero messages published to `market-events-raw` |
| Production subscription untouched | `market-events-raw-worker-push` config unchanged — verified by pre/post describe comparison |
| `worker_message_error_count` datapoint | At least one `int64Value > 0` in Cloud Monitoring timeSeries response |
| `silver_refresh_error_count` datapoint | At least one `int64Value > 0` in Cloud Monitoring timeSeries response. Log-only evidence is not sufficient for acceptance. |
| Isolated resources deleted | `market-events-raw-error-test`, `market-events-raw-error-test-dlq`, and `market-events-raw-error-test-worker-push` confirmed absent from list outputs |
| Temporary silver job deleted | `rtdp-silver-refresh-job-error-test` confirmed absent from `gcloud run jobs list` output |
| Cloud SQL final state | `NEVER   STOPPED` — confirmed and recorded after cleanup |
| Tests pass | `uv run pytest -q` exits 0 after evidence doc is written |
| Ruff clean | `uv run ruff check .` exits 0 after evidence doc is written |
| Evidence document can be created | `docs/isolated-error-counter-validation-evidence.md` created on the execution branch |

---

## 10. Stop Conditions

Stop immediately and record the stop condition if any of the following are observed:

| Stop condition | Action |
|---|---|
| Isolated push subscription describe does not show `deadLetterPolicy` or `maxDeliveryAttempts` after creation | Abort; do not publish the malformed message; investigate the subscription creation command |
| Pub/Sub service agent permissions cannot be confirmed on the DLQ topic | Abort; do not publish the malformed message |
| Any publish command or subscription create command accidentally targets `market-events-raw` instead of `market-events-raw-error-test` | Abort immediately; assess production impact; do not proceed |
| The malformed publish command's `--topic` or subscription's `topic` field references `market-events-raw` without the `-error-test` suffix | Abort immediately |
| Cloud SQL is not `NEVER / STOPPED` at the pre-execution check | Abort; do not proceed with any GCP write operation |
| Worker error log query returns no `status=error` entries within 5 minutes of publish | Abort; do not claim acceptance; investigate whether the push subscription delivered the message |
| Cleanup of any resource fails | Investigate and resolve before committing the evidence document; do not merge with dangling resources |
| Any unexpected GCP write operation is about to occur that is not covered by this runbook | Stop and confirm intent before proceeding |

On stop: record the stop condition, the last known Cloud SQL state, and which steps completed.
Do not re-attempt the same run without diagnosing the cause.

---

## 11. What This Runbook Does Not Do

Even after successful execution of this runbook:

- Does not validate the production Pub/Sub DLQ — the production subscription has no DLQ and
  this runbook does not add one.
- Does not modify the production `market-events-raw-worker-push` subscription in any way.
- Does not deploy alert policies or alerting of any kind.
- Does not create Cloud Monitoring alerting channels.
- Does not start Cloud SQL.
- Does not publish messages now — all publishing is deferred to the future execution branch.
- Does not prove sustained pipeline reliability or production DLQ safety.
- Does not replace future Terraform/IaC management of Pub/Sub resources.
- Does not validate the 5 000-event load test scale tier.
- Does not close the alerting gap or the IaC gap.

---

## 12. Relationship to Existing Documentation

| Document | Relationship |
|---|---|
| [docs/cloud-error-counter-validation-plan.md](cloud-error-counter-validation-plan.md) | Planning analysis: identified the isolated path requirement, risk analysis for unbounded retries and production job mutation |
| [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) | Read-only inspection: confirmed no DLQ/`maxDeliveryAttempts` on production push subscription; established the block on production malformed-message publishing |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Success-counter datapoint evidence: provides the Cloud Monitoring REST API query method reused in Steps W-9 and S-6 |
| [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) | 1000-event evidence: confirms `worker_message_processed_count` datapoints; the baseline that motivates closing the error-counter gap |
| [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md) | Dashboard evidence: the four-panel dashboard includes `worker_message_error_count` and `silver_refresh_error_count` panels; this runbook's execution will produce the first non-zero datapoints for those panels |

---

## 13. Roadmap Position

| Step | Status | Document |
|---|---|---|
| Cloud logs-based metrics creation | Complete | [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md) |
| Cloud logs-based metrics datapoint validation (success counters) | Complete | [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) |
| 100-event cloud load test | Complete — evidence accepted | [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) |
| 1000-event cloud load test | Complete — evidence accepted | [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) |
| Pub/Sub retry/DLQ inspection | Complete — read-only | [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) |
| Cloud Monitoring dashboard | Complete — evidence accepted | [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md) |
| **Isolated error counter validation** | **This runbook — not yet executed** | Future: `docs/isolated-error-counter-validation-evidence.md` |
| Alert policy creation | Blocked — no error-counter datapoints yet | Future |
| 5 000-event cloud load test | Planned | Future |

**Successful execution of this runbook enables:**

- All four logs-based metrics having confirmed Cloud Monitoring datapoints (both success and
  error counters for both worker and silver refresh).
- The `worker_message_error_count` and `silver_refresh_error_count` dashboard panels having
  real non-zero data to display.
- A complete observability claim: "all four pipeline metrics — processed, error, refresh success,
  refresh error — are validated with real GCP timeSeries datapoints."

**This run still does not close:**

- Alerting gap
- Production DLQ safety gap
- IaC (Terraform) gap
- 5 000-event scale gap
