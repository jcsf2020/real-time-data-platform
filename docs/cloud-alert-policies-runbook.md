# Cloud Monitoring Alert Policies Runbook

## Status

**RUNBOOK ONLY — NOT EXECUTED**

This is an operational runbook. No GCP write operations have been performed.

| Constraint | State |
|---|---|
| Alert policies created | **No** |
| Notification channels created | **No** |
| Cloud SQL started | **No** |
| Pub/Sub messages published | **No** |
| Application code modified | **No** |
| Anything deployed | **No** |

This runbook exists solely to define the precise, reviewable execution sequence for a future
branch or session. Read every command block as documentation, not as executed evidence.

---

## 1. Purpose

This runbook defines the controlled procedure to create Cloud Monitoring alert policies on top
of the four logs-based metrics that now have validated Cloud Monitoring timeSeries datapoints:

- `worker_message_processed_count`
- `worker_message_error_count`
- `silver_refresh_success_count`
- `silver_refresh_error_count`

The goal is to move from **passive observability** — metrics and a dashboard exist and can be
queried — to **active operational alerting** — an automated notification fires when the
pipeline fails or degrades. Without alert policies, error conditions are only visible to a
human who happens to be watching the dashboard. Alert policies close that gap.

This runbook builds on the complete four-metric validation cycle:

- Metric descriptors created:
  [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md)
- Success counter datapoints validated:
  [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md)
- Dashboard created and exported:
  [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md)
- Error counter datapoints validated:
  [docs/isolated-error-counter-validation-evidence.md](isolated-error-counter-validation-evidence.md)
  and [docs/silver-refresh-error-metric-filter-evidence.md](silver-refresh-error-metric-filter-evidence.md)

---

## 2. Current Validated Metric Baseline

All four logs-based metrics have confirmed Cloud Monitoring timeSeries datapoints. This
runbook depends on that validation being complete before any alert policy is created.

| Metric name | Full type | Validation status | Evidence document |
|---|---|---|---|
| `worker_message_processed_count` | `logging.googleapis.com/user/worker_message_processed_count` | **Validated** (TOTAL=1000, load test) | [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) |
| `worker_message_error_count` | `logging.googleapis.com/user/worker_message_error_count` | **Validated** (TOTAL=13, isolated error test) | [docs/isolated-error-counter-validation-evidence.md](isolated-error-counter-validation-evidence.md) |
| `silver_refresh_success_count` | `logging.googleapis.com/user/silver_refresh_success_count` | **Validated** (int64Value=1) | [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) |
| `silver_refresh_error_count` | `logging.googleapis.com/user/silver_refresh_error_count` | **Validated** (TOTAL=1, isolated error test) | [docs/silver-refresh-error-metric-filter-evidence.md](silver-refresh-error-metric-filter-evidence.md) |

### Validation dependencies

This runbook depends on all four of the following evidence documents confirming successful
datapoint validation before execution:

| Evidence document | Required status |
|---|---|
| [docs/silver-refresh-error-metric-filter-evidence.md](silver-refresh-error-metric-filter-evidence.md) | VALIDATED |
| [docs/isolated-error-counter-validation-evidence.md](isolated-error-counter-validation-evidence.md) | WORKER ERROR VALIDATED |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | VALIDATED |
| [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) | ACCEPTED |

If any of the above is missing or not accepted, abort and complete the outstanding validation
before proceeding with alert policy creation.

---

## 3. Proposed Alert Policies

### A. Worker Message Error Alert

**Purpose:** Detect malformed message processing, schema validation failures, or worker
runtime failures in the Pub/Sub push consumer. Without this alert, error conditions are
visible only on the dashboard — no automated signal reaches an operator.

| Field | Value |
|---|---|
| Policy name | `RTDP Worker Message Error Alert` |
| Metric type | `logging.googleapis.com/user/worker_message_error_count` |
| Condition type | Threshold on DELTA sum |
| Threshold | `> 0` |
| Alignment window | 1–5 minutes (start with 5 minutes; tighten to 1 minute if false positives are rare) |
| Duration | 0 minutes (fire immediately when threshold is crossed) |
| Comparison | Any time series in the alignment window exceeds the threshold |
| Notification channels | See Section 5 |

**Rationale:** The error counter should be zero during normal operation. Any non-zero value
means at least one Pub/Sub message was not processed successfully. Even a single error is
worth alerting on given the idempotent, low-volume nature of this pipeline. Set duration=0
to avoid missing transient spikes that resolve within the alignment window.

---

### B. Silver Refresh Error Alert

**Purpose:** Detect failed silver aggregation job runs. If `silver_refresh_error_count`
fires, the silver layer is not being updated and stale data is being served by the API.

| Field | Value |
|---|---|
| Policy name | `RTDP Silver Refresh Error Alert` |
| Metric type | `logging.googleapis.com/user/silver_refresh_error_count` |
| Condition type | Threshold on DELTA sum |
| Threshold | `> 0` |
| Alignment window | 1–5 minutes |
| Duration | 0 minutes |
| Comparison | Any time series in the alignment window exceeds the threshold |
| Notification channels | See Section 5 |

**Rationale:** A silver refresh failure means the aggregation pipeline is broken. Since the
refresh job is currently executed manually (no Cloud Scheduler), a failure could go unnoticed
indefinitely. The alert provides coverage until a recurring scheduler is added.

---

### C. Worker Processed Message Absence Alert (Optional / Future)

**Status: OPTIONAL — NOT RECOMMENDED UNTIL A SCHEDULED PUBLISHER OR HEARTBEAT EXISTS**

**Purpose:** Detect extended periods where no messages are processed by the worker —
signalling that the pipeline has stalled or is not receiving input.

| Field | Value |
|---|---|
| Policy name | `RTDP Worker Processed Absence Alert` |
| Metric type | `logging.googleapis.com/user/worker_message_processed_count` |
| Condition type | Absence / below threshold |
| Threshold | `< 1` (no processed messages) |
| Alignment window | 30–60 minutes |
| Duration | 30–60 minutes |
| Notification channels | See Section 5 |

**Why this is optional:** The current pipeline receives no continuous input — events are
published only during manual load tests. Under normal idle conditions, `worker_message_processed_count`
is zero because no messages are being sent, not because the pipeline is broken. Alerting
on absence would fire continuously during idle periods and produce only noise.

This policy becomes useful only after one of the following is in place:

- A Cloud Scheduler job or heartbeat that publishes at least one test message per interval
- A sustained production event stream with a known minimum throughput baseline

Do not create this policy until a scheduled publisher exists that guarantees regular traffic.

---

## 4. Notification Channel Strategy

No notification channels are created by this runbook. Notification channels are optional for
initial alert policy creation — Cloud Monitoring will capture the alert state and incident
timeline even without a channel configured.

### Options (for future execution)

| Option | Complexity | Recommendation |
|---|---|---|
| No channel — alert policy only | Lowest | Start here. Alerts fire and are visible in the Cloud Monitoring console; no external delivery needed initially. |
| Email channel | Low | Add after verifying the policies fire correctly. Requires one `gcloud alpha monitoring channels create` command. |
| Webhook / Slack | Medium | Add later if real-time team notification is needed. Requires an existing Slack webhook URL or alertmanager endpoint. |

**Recommendation:** Create alert policies first with no notification channel. Confirm the
policies appear in `gcloud monitoring policies list` and that the conditions and metric
types are correct. Add an email channel in a follow-up step once the policies are confirmed
working. This avoids blocking policy creation on channel setup and keeps the initial
execution surface small.

---

## 5. Exact Future Execution Commands

> **Future execution only — do not run on this runbook branch.**
>
> All command blocks below are templates for a future execution session. No command here has
> been run. All placeholders must be resolved before execution. Stop if any step returns an
> unexpected result.

### Placeholder reference

| Placeholder | Meaning |
|---|---|
| `PROJECT_ID` | GCP project ID — e.g. `project-42987e01-2123-446b-ac7` |
| `REGION` | Cloud Run region — e.g. `europe-west1` |

---

### Step 0 — Pre-execution checks

```bash
# Confirm branch is NOT this runbook branch
git branch --show-current

# Confirm tests pass
uv run pytest -q

# Confirm ruff clean
uv run ruff check .

# Confirm Cloud SQL is NEVER / STOPPED
gcloud sql instances describe rtdp-postgres \
  --project=$PROJECT_ID \
  --format="value(settings.activationPolicy,state)"
# Expected: NEVER   STOPPED

# Confirm all four metric descriptors exist
gcloud logging metrics list \
  --project=$PROJECT_ID \
  --format="table(name,metricDescriptor.metricKind,metricDescriptor.valueType)"
# Expected: all four metrics present as DELTA / INT64

# List existing alert policies (pre-creation baseline)
gcloud monitoring policies list \
  --project=$PROJECT_ID \
  --format="table(name,displayName,enabled)"
```

Abort if any of the following:

- Branch is `docs/cloud-alert-policies-runbook`
- Cloud SQL is not `NEVER   STOPPED`
- Any of the four metric descriptors is missing
- Any unexpected alert policy already exists that duplicates the intended policies

---

### Step 1 — Create worker error alert policy

Write the policy JSON to a temporary file (not committed to the repo):

```bash
cat > /tmp/rtdp-worker-error-alert.json << 'EOF'
{
  "displayName": "RTDP Worker Message Error Alert",
  "conditions": [
    {
      "displayName": "worker_message_error_count > 0",
      "conditionThreshold": {
        "filter": "metric.type=\"logging.googleapis.com/user/worker_message_error_count\" resource.type=\"cloud_run_revision\"",
        "comparison": "COMPARISON_GT",
        "thresholdValue": 0,
        "duration": "0s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_DELTA",
            "crossSeriesReducer": "REDUCE_SUM"
          }
        ]
      }
    }
  ],
  "alertStrategy": {
    "autoClose": "604800s"
  },
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": []
}
EOF
```

Create the policy:

```bash
gcloud monitoring policies create \
  --project=$PROJECT_ID \
  --policy-from-file=/tmp/rtdp-worker-error-alert.json
```

Expected output includes:
```
Created alert policy [projects/$PROJECT_ID/alertPolicies/<POLICY_ID>].
```

Record the returned policy ID.

---

### Step 2 — Create silver refresh error alert policy

```bash
cat > /tmp/rtdp-silver-error-alert.json << 'EOF'
{
  "displayName": "RTDP Silver Refresh Error Alert",
  "conditions": [
    {
      "displayName": "silver_refresh_error_count > 0",
      "conditionThreshold": {
        "filter": "metric.type=\"logging.googleapis.com/user/silver_refresh_error_count\" resource.type=\"cloud_run_job\"",
        "comparison": "COMPARISON_GT",
        "thresholdValue": 0,
        "duration": "0s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_DELTA",
            "crossSeriesReducer": "REDUCE_SUM"
          }
        ]
      }
    }
  ],
  "alertStrategy": {
    "autoClose": "604800s"
  },
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": []
}
EOF
```

```bash
gcloud monitoring policies create \
  --project=$PROJECT_ID \
  --policy-from-file=/tmp/rtdp-silver-error-alert.json
```

Expected output includes:
```
Created alert policy [projects/$PROJECT_ID/alertPolicies/<POLICY_ID>].
```

Record the returned policy ID.

---

### Step 3 — Verify policies after creation

```bash
# List all alert policies
gcloud monitoring policies list \
  --project=$PROJECT_ID \
  --format="table(name,displayName,enabled)"
```

Expected: both `RTDP Worker Message Error Alert` and `RTDP Silver Refresh Error Alert`
appear in the list with `enabled: true`.

```bash
# Describe worker error policy (replace POLICY_ID with returned ID)
gcloud monitoring policies describe projects/$PROJECT_ID/alertPolicies/WORKER_POLICY_ID \
  --project=$PROJECT_ID
```

Verify the described policy references `logging.googleapis.com/user/worker_message_error_count`.

```bash
# Describe silver error policy (replace POLICY_ID with returned ID)
gcloud monitoring policies describe projects/$PROJECT_ID/alertPolicies/SILVER_POLICY_ID \
  --project=$PROJECT_ID
```

Verify the described policy references `logging.googleapis.com/user/silver_refresh_error_count`.

---

### Step 4 — Confirm Cloud SQL final state

```bash
gcloud sql instances describe rtdp-postgres \
  --project=$PROJECT_ID \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

This check must be recorded in the evidence document. The execution window is not closed
until this is confirmed.

---

### Optional future command — create processed absence alert

**Do not run until a scheduled publisher or heartbeat exists.**

```bash
cat > /tmp/rtdp-processed-absence-alert.json << 'EOF'
{
  "displayName": "RTDP Worker Processed Message Absence Alert",
  "conditions": [
    {
      "displayName": "worker_message_processed_count absent for 30 min",
      "conditionAbsent": {
        "filter": "metric.type=\"logging.googleapis.com/user/worker_message_processed_count\" resource.type=\"cloud_run_revision\"",
        "duration": "1800s",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_DELTA"
          }
        ]
      }
    }
  ],
  "alertStrategy": {
    "autoClose": "604800s"
  },
  "combiner": "OR",
  "enabled": false,
  "notificationChannels": []
}
EOF
```

This template sets `enabled: false` intentionally — the policy should remain disabled until
a scheduled publisher guarantees regular traffic.

---

## 6. Evidence to Capture in Future Execution Branch

The future execution evidence document (`docs/cloud-alert-policies-evidence.md`) must
capture all of the following:

| # | Evidence item | Description |
|---|---|---|
| 1 | Pre-execution branch name | Must not be `docs/cloud-alert-policies-runbook` |
| 2 | Pre-execution git status | Output of `git status --short --branch` |
| 3 | Pre-execution pytest | Output of `uv run pytest -q` — must pass |
| 4 | Pre-execution ruff | Output of `uv run ruff check .` — must be clean |
| 5 | Pre-execution Cloud SQL state | Output of `gcloud sql instances describe` — must be `NEVER   STOPPED` |
| 6 | Pre-creation alert policy list | Output of `gcloud monitoring policies list` — baseline before any creation |
| 7 | All four metric descriptors confirmed | Output of `gcloud logging metrics list` showing all four metrics present |
| 8 | Worker error policy create output | Full output of `gcloud monitoring policies create` for the worker error policy |
| 9 | Silver error policy create output | Full output of `gcloud monitoring policies create` for the silver error policy |
| 10 | Post-creation alert policy list | Output of `gcloud monitoring policies list` after both policies are created |
| 11 | Worker error policy describe output | Full output of `gcloud monitoring policies describe` — must reference `worker_message_error_count` |
| 12 | Silver error policy describe output | Full output of `gcloud monitoring policies describe` — must reference `silver_refresh_error_count` |
| 13 | Post-execution Cloud SQL state | Output of `gcloud sql instances describe` — must be `NEVER   STOPPED` |
| 14 | Post-execution pytest | Output of `uv run pytest -q` after evidence doc committed |
| 15 | Post-execution ruff | Output of `uv run ruff check .` after evidence doc committed |
| 16 | No Pub/Sub publishing statement | Explicit statement that zero Pub/Sub messages were published during execution |
| 17 | No Cloud SQL start statement | Explicit statement that Cloud SQL was not started during execution |

---

## 7. Acceptance Criteria

The future execution is accepted only if **all** of the following are true:

| Criterion | Required |
|---|---|
| Worker error alert policy exists | `RTDP Worker Message Error Alert` present in `gcloud monitoring policies list` |
| Worker error policy references correct metric | `describe` output includes `logging.googleapis.com/user/worker_message_error_count` |
| Silver error alert policy exists | `RTDP Silver Refresh Error Alert` present in `gcloud monitoring policies list` |
| Silver error policy references correct metric | `describe` output includes `logging.googleapis.com/user/silver_refresh_error_count` |
| Policies are enabled | Both policies have `enabled: true` (or explicitly documented as disabled if that is chosen) |
| Cloud SQL state | `NEVER   STOPPED` — confirmed before and after execution |
| No Pub/Sub messages published | Zero messages published during this execution window |
| No application code changes | No `.py` files modified |
| Tests pass | `uv run pytest -q` exits 0 |
| Ruff clean | `uv run ruff check .` exits 0 |
| Evidence document created | `docs/cloud-alert-policies-evidence.md` committed on the execution branch |

---

## 8. Stop Conditions

Abort immediately and record the stop reason if any of the following are observed:

| Stop condition | Required action |
|---|---|
| Cloud SQL is not `NEVER / STOPPED` before execution | Abort; do not perform any GCP writes; investigate why Cloud SQL is running |
| Any of the four metric descriptors is missing | Abort; re-validate the missing metric before creating any alert policies |
| `gcloud monitoring policies create` fails with an error | Abort; record the full error; do not retry without diagnosing the root cause |
| Created policy `describe` output references the wrong metric type | Abort; delete the incorrectly created policy immediately; diagnose before retrying |
| Notification channel requirement blocks policy creation | Skip the channel; create the policy with `notificationChannels: []` first |
| An existing alert policy with the same `displayName` already exists | Abort; do not create a duplicate; investigate and decide to update or skip |
| Any command would mutate unrelated GCP resources | Abort; record which command and what it would have mutated |
| Cloud SQL state changes from `NEVER / STOPPED` during execution | Treat as abort signal; stop all writes; document the state change |

On abort: record the stop condition, the last known Cloud SQL state, and which steps
completed. Do not attempt the same run again without diagnosing the cause.

---

## 9. What This Runbook Does Not Do

This runbook does **not**:

- Create alert policies now (no GCP writes on this branch)
- Create notification channels (email, Slack, webhook) now
- Add a production Pub/Sub dead-letter policy on `market-events-raw-worker-push`
- Add Terraform or IaC management for the alert policies
- Add Cloud Scheduler for automated silver refresh
- Validate the 5,000-event load test
- Start Cloud SQL
- Publish test messages to any Pub/Sub topic
- Modify any application code
- Create latency or distribution metrics
- Create a missing-execution absence alert (see Section 3C — deferred until heartbeat exists)

---

## 10. Roadmap Position

After this runbook's future execution evidence is merged, the alert policy gap will be
closed. The remaining P0 gap at that point will be:

**P0 — Production Pub/Sub DLQ**

```
market-events-raw-worker-push has no deadLetterPolicy configured.
```

Malformed messages delivered to the production push subscription currently cause unbounded
retries against the Cloud Run worker. No dead-letter topic exists to absorb failed messages.
This is the highest-priority safety gap in the current GCP architecture.

**P1 — Cloud Scheduler for Silver Refresh**

The silver refresh Cloud Run Job is currently triggered manually. No Cloud Scheduler or
recurring trigger exists. Without automation, the silver layer goes stale unless manually
refreshed.

**P1 — Terraform / IaC**

All GCP resources (metrics, dashboard, alert policies, Cloud Run services, Cloud SQL,
Pub/Sub topics) were created imperatively via `gcloud` commands. No Terraform state exists.
Adding IaC would make the infrastructure reproducible and reviewable as code.

**P1 — 5,000-Event Load Test**

The load test plan covers three tiers: 100 events (complete), 1,000 events (complete), and
5,000 events (planned). The 5,000-tier has not been executed. This tier would demonstrate
sustained throughput at a higher volume and confirm metric aggregation behaviour under load.

**P1 — BigQuery / Dataflow Analytical Tier**

The silver layer is implemented in Cloud SQL (operational). A BigQuery/Dataflow analytical
tier for long-horizon analytics has not been implemented.

### Full roadmap summary

| Step | Status | Document |
|---|---|---|
| Logs-based metrics creation | Complete | [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md) |
| Success counter datapoint validation | Complete | [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) |
| Error counter datapoint validation | Complete | [docs/isolated-error-counter-validation-evidence.md](isolated-error-counter-validation-evidence.md), [docs/silver-refresh-error-metric-filter-evidence.md](silver-refresh-error-metric-filter-evidence.md) |
| Cloud Monitoring dashboard | Complete | [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md) |
| **Alert policies** | **This runbook — not yet executed** | Future: `docs/cloud-alert-policies-evidence.md` |
| Production Pub/Sub DLQ | P0 gap — not addressed | Future |
| Cloud Scheduler for silver refresh | P1 gap — not addressed | Future |
| Terraform / IaC | P1 gap — not addressed | Future |
| 5,000-event load test | P1 gap — not executed | [docs/load-test-plan.md](load-test-plan.md) |
| BigQuery / Dataflow analytical tier | P1 gap — not implemented | Future |
