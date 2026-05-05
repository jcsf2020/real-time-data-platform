# Cloud Monitoring Dashboard Runbook

## Status

**RUNBOOK ONLY — NOT EXECUTED**

This is an operational runbook. The Cloud Monitoring dashboard has **not been created**.
No GCP write operations have been performed. No Cloud SQL instance has been started. No
Pub/Sub messages have been published. No dashboard JSON has been exported. No infra files
have been created on this branch.

This runbook exists solely to define the precise, reviewable execution sequence for a future
branch or session. Read every command block as documentation, not as executed evidence.

This runbook builds on the accepted 1000-event cloud load test evidence documented in
[docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) and the Cloud
Monitoring datapoint validation in
[docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md).

---

## 1. Purpose

Define the controlled procedure to create a Cloud Monitoring dashboard named:

```
RTDP Pipeline Overview
```

The dashboard will expose the four validated logs-based metrics as visual panels, providing
operational observability that is visible to B2B reviewers and recruiters — not only queryable
via the Cloud Monitoring REST API.

This closes the dashboard gap identified in the Devil's Advocate audit:

- Metrics exist ✓
- Datapoints exist ✓
- Dashboard does not yet exist ✗
- Visual operational evidence does not yet exist ✗
- Dashboard JSON export does not yet exist ✗

---

## 2. Scope

### Covered by this runbook

- Dashboard creation in Cloud Monitoring Console or via dashboard JSON upload
- Minimum viable panel set using the four validated logs-based metrics
- Panel configuration and verification against non-zero load-test datapoints
- Dashboard JSON export and commit under `infra/monitoring/dashboards/`
- Screenshot capture guidance as non-versioned visual evidence
- Evidence document creation: `docs/cloud-monitoring-dashboard-evidence.md`

### Explicitly excluded from this runbook

- Alert policy creation or alert firing
- Cloud SQL start or any database mutation
- Pub/Sub message publishing
- Application code changes or redeployment
- Grafana or Looker Studio integration
- IaC-managed monitoring (Terraform)
- BigQuery or Dataflow integration
- 5 000-event load test
- Autoscaling or cold-start observation

---

## 3. Preconditions

All of the following must be true before any execution commands are run on the future
execution branch. Abort if any precondition cannot be confirmed.

| # | Precondition | How to verify |
|---|---|---|
| 1 | This must run on a **future execution/evidence branch** — not this runbook branch | `git branch --show-current` |
| 2 | `main` is clean and synced | `git status` on `main`; `git fetch && git log origin/main..main` |
| 3 | All tests pass | `uv run pytest -q` exits 0 |
| 4 | Ruff passes | `uv run ruff check .` exits 0 |
| 5 | Cloud SQL is `NEVER / STOPPED` and must remain so | `gcloud sql instances describe rtdp-postgres --format="value(settings.activationPolicy,state)"` → `NEVER   STOPPED` |
| 6 | `worker_message_processed_count` metric descriptor confirmed present | `gcloud logging metrics list --project=... --filter='name:worker_message_processed_count'` |
| 7 | `worker_message_error_count` metric descriptor confirmed present | `gcloud logging metrics list --project=... --filter='name:worker_message_error_count'` |
| 8 | `silver_refresh_success_count` metric descriptor confirmed present | `gcloud logging metrics list --project=... --filter='name:silver_refresh_success_count'` |
| 9 | `silver_refresh_error_count` metric descriptor confirmed present | `gcloud logging metrics list --project=... --filter='name:silver_refresh_error_count'` |
| 10 | 1000-event evidence confirms non-zero datapoints for `worker_message_processed_count` | [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) — metric sum = 1000 accepted |
| 11 | No active GCP writes other than dashboard creation are planned for this session | Confirm before proceeding |

### Placeholder reference

All future execution commands below use these placeholders. Replace every placeholder before
running any command:

| Placeholder | Meaning |
|---|---|
| `PROJECT_ID` | GCP project ID (e.g. `project-42987e01-2123-446b-ac7`) |
| `REGION` | Cloud Run region (e.g. `europe-west1`) |
| `DASHBOARD_ID` | The dashboard resource ID returned after creation |

---

## 4. Dashboard Panel Specification

The minimum viable dashboard must contain at least the four panels below. A fifth optional
panel may be added if native Cloud Run metrics are available for the API service.

| Panel title | Metric type | Expected signal | Source evidence | Why it matters |
|---|---|---|---|---|
| Worker Processed Messages / min | `logging.googleapis.com/user/worker_message_processed_count` | 850 in 21:42–21:43 window; 150 in 21:43–21:44 window (1000-event run) | [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) | Shows ingestion throughput and load-test scale to a B2B reviewer at a glance |
| Worker Error Count | `logging.googleapis.com/user/worker_message_error_count` | Zero during all load tests (expected flat line) | [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md), [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) | Confirms clean pipeline runs; flat zero is meaningful operational evidence |
| Silver Refresh Success Count | `logging.googleapis.com/user/silver_refresh_success_count` | At least one datapoint per refresh execution | [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Proves the silver layer refresh completed successfully in GCP |
| Silver Refresh Error Count | `logging.googleapis.com/user/silver_refresh_error_count` | Zero (expected flat line) | Implied by successful refresh logs | Confirms no silent refresh failures |
| Cloud Run API Request Count (optional) | Native Cloud Run metric: `run.googleapis.com/request_count` | Non-zero if API received requests during load test window | [docs/api-events-pagination-deploy-evidence.md](api-events-pagination-deploy-evidence.md) | Provides end-to-end serving evidence alongside ingest metrics |

**Panel configuration notes:**

- Use **DELTA / INT64** alignment for the four logs-based counter metrics (consistent with
  `metricKind: DELTA`, `valueType: INT64` confirmed in
  [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md)).
- Set the time range to cover at least the 1000-event load test execution window to ensure
  non-zero datapoints are visible.
- Group by `resource.labels.service_name` or `resource.labels.job_name` where applicable to
  distinguish worker vs. silver refresh metrics.

---

## 5. Execution Sequence

> **Future execution only — do not run during this runbook branch.**
>
> Every command block in this section is a template for a future execution session.
> No command here has been run. All placeholders must be resolved before execution.
> Stop if any step returns an unexpected result.

### Step 1 — Confirm repo and test state

```bash
git branch --show-current
uv run pytest -q
uv run ruff check .
```

Expected: branch is NOT `docs/cloud-monitoring-dashboard-runbook`; tests pass; ruff clean.

---

### Step 2 — Confirm Cloud SQL pre-execution state (read-only)

```bash
gcloud sql instances describe rtdp-postgres \
  --project=$PROJECT_ID \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

**Cloud SQL must remain NEVER / STOPPED throughout this entire runbook execution.
Do not proceed if the state is unexpected.**

---

### Step 3 — Confirm all four metric descriptors present

```bash
gcloud logging metrics list \
  --project=$PROJECT_ID \
  --format="table(name,metricDescriptor.metricKind,metricDescriptor.valueType)"
```

Expected output includes all four:

```
NAME                            METRIC_KIND  VALUE_TYPE
silver_refresh_error_count      DELTA        INT64
silver_refresh_success_count    DELTA        INT64
worker_message_error_count      DELTA        INT64
worker_message_processed_count  DELTA        INT64
```

**Abort if any of the four metrics is missing.**

---

### Step 4 — Confirm existing datapoints via Cloud Monitoring REST API (read-only)

Query `worker_message_processed_count` over the 1000-event load test window to confirm
non-zero datapoints are still visible before building the dashboard. This step is read-only.

```bash
START_TIME="2026-05-05T21:40:00Z"   # Adjust to the actual 1000-event run window
END_TIME="2026-05-05T21:50:00Z"
TOKEN="$(gcloud auth print-access-token)"

curl -s \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://monitoring.googleapis.com/v3/projects/$PROJECT_ID/timeSeries\
?filter=metric.type%3D%22logging.googleapis.com%2Fuser%2Fworker_message_processed_count%22\
&interval.startTime=${START_TIME}\
&interval.endTime=${END_TIME}"
```

Expected: response contains `int64Value` datapoints summing to approximately 1000 across the
window (850 in the 21:42–21:43 interval; 150 in 21:43–21:44 interval per accepted evidence).

Record the confirmed interval boundaries and values in the evidence document.

---

### Step 5 — Create dashboard in Cloud Monitoring Console

Navigate to:

```
Google Cloud Console → Monitoring → Dashboards → Create Dashboard
```

Dashboard name: **RTDP Pipeline Overview**

Add panels in the order defined in Section 4. For each panel:

1. Select **Metric** as the chart type.
2. Set the metric using the full metric type path (e.g.
   `logging.googleapis.com/user/worker_message_processed_count`).
3. Set alignment function to `sum` or `rate` as appropriate for a DELTA metric.
4. Set the time range to include the 1000-event load test window.
5. Confirm that the panel shows non-zero data for `worker_message_processed_count`.

**Abort criteria for this step:**

- If any metric selector cannot find the metric descriptor.
- If `worker_message_processed_count` panel shows no data after applying the correct time range.

---

### Step 6 — Alternatively: create dashboard via JSON upload

If the Console approach is not sufficient or reproducible evidence is preferred, create the
dashboard via the Cloud Monitoring REST API using a dashboard JSON definition:

```bash
TOKEN="$(gcloud auth print-access-token)"

curl -s -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d @infra/monitoring/dashboards/rtdp-pipeline-overview.json \
  "https://monitoring.googleapis.com/v1/projects/$PROJECT_ID/dashboards"
```

The JSON file must be committed as `infra/monitoring/dashboards/rtdp-pipeline-overview.json`
before this command is run. A minimal dashboard JSON skeleton is provided in Section 6 below.

Record the `name` field from the API response — this is the dashboard resource ID.

---

### Step 7 — Verify panels show non-zero data

After the dashboard is created and panels are configured, confirm in the Cloud Monitoring
Console that:

- `worker_message_processed_count` panel shows at least one non-zero bar or line within the
  1000-event load test window.
- The panel time range covers the load test execution window.
- Panel titles match the specification in Section 4.

**Abort if `worker_message_processed_count` cannot be shown as non-zero in the panel.**

---

### Step 8 — Export dashboard JSON

Export the created dashboard definition as JSON for version control.

**Option A — via gcloud (if `gcloud monitoring dashboards` supports export):**

```bash
gcloud monitoring dashboards describe $DASHBOARD_ID \
  --project=$PROJECT_ID \
  --format=json > infra/monitoring/dashboards/rtdp-pipeline-overview.json
```

**Option B — via Cloud Monitoring REST API:**

```bash
TOKEN="$(gcloud auth print-access-token)"

curl -s \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://monitoring.googleapis.com/v1/projects/$PROJECT_ID/dashboards/$DASHBOARD_ID" \
  > infra/monitoring/dashboards/rtdp-pipeline-overview.json
```

Verify the exported file is valid JSON and contains the expected panel definitions:

```bash
python -c "import json; d=json.load(open('infra/monitoring/dashboards/rtdp-pipeline-overview.json')); print(d.get('displayName'))"
```

Expected: `RTDP Pipeline Overview`

---

### Step 9 — Capture screenshot (manual, non-versioned)

Open the dashboard in the Cloud Monitoring Console and capture a screenshot showing:

- Dashboard name: **RTDP Pipeline Overview**
- At least one panel with non-zero data visible
- Time range covering the 1000-event load test window

Save the screenshot locally. Reference it in the evidence document as non-versioned evidence.
Do not commit binary screenshot files unless intentionally added.

---

### Step 10 — Confirm Cloud SQL final state (read-only)

```bash
gcloud sql instances describe rtdp-postgres \
  --project=$PROJECT_ID \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER   STOPPED`

**The execution window is not closed until this is confirmed and recorded.**

---

### Step 11 — Commit dashboard JSON and create evidence document

```bash
# Stage only the dashboard JSON and evidence document
git add infra/monitoring/dashboards/rtdp-pipeline-overview.json
git add docs/cloud-monitoring-dashboard-evidence.md

# Run final validation before committing
uv run pytest -q
uv run ruff check .

git commit -m "Add Cloud Monitoring dashboard JSON and evidence"
```

---

### Step 12 — Create evidence document

Create `docs/cloud-monitoring-dashboard-evidence.md` on the execution branch. See Section 7
for the required evidence checklist.

---

## 6. Dashboard JSON Skeleton

The following is a minimal skeleton for `infra/monitoring/dashboards/rtdp-pipeline-overview.json`.
Adjust `PROJECT_ID` and panel details as needed during execution. This file is not committed on
this runbook branch — it is provided here as a reference template for the execution branch.

```json
{
  "displayName": "RTDP Pipeline Overview",
  "mosaicLayout": {
    "columns": 12,
    "tiles": [
      {
        "width": 6,
        "height": 4,
        "widget": {
          "title": "Worker Processed Messages / min",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "metric.type=\"logging.googleapis.com/user/worker_message_processed_count\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE"
                    }
                  }
                }
              }
            ]
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "widget": {
          "title": "Worker Error Count",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "metric.type=\"logging.googleapis.com/user/worker_message_error_count\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE"
                    }
                  }
                }
              }
            ]
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "yPos": 4,
        "widget": {
          "title": "Silver Refresh Success Count",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "metric.type=\"logging.googleapis.com/user/silver_refresh_success_count\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE"
                    }
                  }
                }
              }
            ]
          }
        }
      },
      {
        "width": 6,
        "height": 4,
        "xPos": 6,
        "yPos": 4,
        "widget": {
          "title": "Silver Refresh Error Count",
          "xyChart": {
            "dataSets": [
              {
                "timeSeriesQuery": {
                  "timeSeriesFilter": {
                    "filter": "metric.type=\"logging.googleapis.com/user/silver_refresh_error_count\"",
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "perSeriesAligner": "ALIGN_RATE"
                    }
                  }
                }
              }
            ]
          }
        }
      }
    ]
  }
}
```

---

## 7. Evidence Checklist

All items below must be captured in `docs/cloud-monitoring-dashboard-evidence.md` on the
execution branch.

| # | Evidence item | Description |
|---|---|---|
| 1 | Execution branch name | Must not be this runbook branch |
| 2 | Pre-check Cloud SQL state | Output of `gcloud sql instances describe` — must be `NEVER   STOPPED` |
| 3 | All four metric descriptors confirmed | Output of `gcloud logging metrics list` showing all four metrics present |
| 4 | Pre-dashboard datapoint query result | Cloud Monitoring REST API response confirming non-zero `int64Value` for `worker_message_processed_count` over the 1000-event window |
| 5 | Dashboard creation method | Console or REST API — record which method was used |
| 6 | Dashboard name | Must be exactly `RTDP Pipeline Overview` |
| 7 | Dashboard resource ID | The `name` field returned by the creation API or Console |
| 8 | Panel list | All panel titles as they appear in the created dashboard |
| 9 | `worker_message_processed_count` panel non-zero confirmation | Screenshot description or API query confirming non-zero data visible in panel |
| 10 | Dashboard JSON export | File committed at `infra/monitoring/dashboards/rtdp-pipeline-overview.json` |
| 11 | Dashboard JSON `displayName` verification | Output of `python -c "..."` confirming `RTDP Pipeline Overview` |
| 12 | Screenshot reference | Local path or description — non-versioned unless file is intentionally added |
| 13 | Post-execution Cloud SQL state | Output of `gcloud sql instances describe` — must be `NEVER   STOPPED` |
| 14 | Tests after evidence doc | `uv run pytest -q` — must pass |
| 15 | Ruff after evidence doc | `uv run ruff check .` — must pass |

---

## 8. Acceptance Criteria

The execution run is accepted only if **all** of the following are true:

| Criterion | Required |
|---|---|
| Dashboard exists in Cloud Monitoring | Named exactly `RTDP Pipeline Overview` |
| Dashboard contains metric panels | At least 4 panels covering the four validated logs-based metrics |
| `worker_message_processed_count` panel | Shows non-zero data within the 1000-event load test window |
| Dashboard JSON exported and committed | `infra/monitoring/dashboards/rtdp-pipeline-overview.json` present and valid |
| Evidence document created | `docs/cloud-monitoring-dashboard-evidence.md` on the execution branch |
| Cloud SQL final state | `NEVER   STOPPED` — confirmed and recorded |
| No Pub/Sub messages published | Zero messages published during this execution |
| No deploy performed | No Cloud Run deploy or image push |
| Tests pass | `uv run pytest -q` exits 0 after evidence doc committed |
| Ruff passes | `uv run ruff check .` exits 0 after evidence doc committed |

---

## 9. Abort Criteria

Abort immediately and record the abort condition if any of the following are observed:

| Condition | Action |
|---|---|
| Branch is the runbook branch | Do not proceed — create a new execution branch |
| Cloud SQL is not `NEVER / STOPPED` at precondition check | Abort; do not perform any GCP writes; investigate |
| Cloud SQL state changes to anything other than `NEVER / STOPPED` during execution | Treat as abort signal; document the state and stop |
| Any metric descriptor is missing at precondition check | Abort; do not create dashboard without all four metrics |
| `worker_message_processed_count` panel shows no data after applying the correct time range | Abort; the dashboard would not prove visual observability |
| Dashboard cannot be exported as JSON | Treat as abort signal; document the failure |
| Cloud Monitoring Console or REST API returns an error during dashboard creation | Abort; record the error |
| Any GCP write operation other than dashboard creation occurs | Treat as abort signal; document and stop |
| Evidence cannot prove at least one non-zero panel for `worker_message_processed_count` | Do not claim acceptance |

On abort: record the abort condition, the last known Cloud SQL state, and which steps
completed. Do not attempt the same run again without diagnosing the cause.

---

## 10. What This Future Execution Will Prove

These claims are safe only after the evidence document has been captured and merged:

- Observability is **visible**, not only queryable: the four logs-based metrics can be
  presented as live panels in a Cloud Monitoring dashboard.
- Cloud Monitoring has a usable operational dashboard for the RTDP pipeline.
- Load-test metrics from the 100-event and 1000-event runs can be presented visually,
  including the 850 / 150 per-minute split from the 1000-event run.
- Dashboard JSON is version-controlled and reproducible.
- Stronger B2B and recruiter packaging: a named operational dashboard with visual evidence
  of a pipeline processing 1000 events.

---

## 11. What It Will Not Prove

Even after successful completion:

- Alert policy existence or alert firing
- DLQ safety or retry handling
- Sustained throughput or production SLA
- 5 000-event scale
- IaC-managed monitoring (Terraform)
- Grafana or Looker Studio dashboarding
- Latency metrics or latency distribution
- Missing-execution detection or scheduler alerting
- Multi-region resilience
- Autoscaling or cold-start behaviour under load

---

## 12. Relationship to Existing Documentation

| Document | Relationship |
|---|---|
| [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md) | Created and confirmed all four logs-based metric descriptors; precondition for this runbook |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Confirmed actual Cloud Monitoring datapoints for `worker_message_processed_count` and `silver_refresh_success_count`; provides the REST API query method used in Step 4 |
| [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) | 100-event baseline; metric sum = 100; early datapoint source for panel verification |
| [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) | 1000-event evidence; metric sum = 1000 with 850 / 150 per-minute split; primary non-zero evidence for panel verification |
| [docs/api-events-pagination-deploy-evidence.md](api-events-pagination-deploy-evidence.md) | API deployment evidence; relevant if the optional Cloud Run request count panel is added |
| [docs/cloud-observability-metrics-plan.md](cloud-observability-metrics-plan.md) | Original observability plan including dashboard, alerting, and metrics strategy (plan only) |

---

## 13. Roadmap Position

| Step | Status | Document |
|---|---|---|
| Cloud logs-based metrics creation | Complete | [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md) |
| Cloud logs-based metrics datapoint validation | Complete | [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) |
| 100-event cloud load test | Complete — evidence accepted | [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) |
| 1000-event cloud load test | Complete — evidence accepted | [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) |
| API `/events` pagination fix deployed | Complete — evidence accepted | [docs/api-events-pagination-deploy-evidence.md](api-events-pagination-deploy-evidence.md) |
| **Cloud Monitoring dashboard** | **This runbook — not yet executed** | Future: `docs/cloud-monitoring-dashboard-evidence.md` |
| Alert policy creation | Blocked — requires dashboard evidence | Future |
| 5 000-event cloud load test | Planned | Future |
| Error counter datapoint validation | Planned | [docs/cloud-error-counter-validation-plan.md](cloud-error-counter-validation-plan.md) |

**Successful completion of this runbook's execution enables:**

- Visual operational evidence in a named Cloud Monitoring dashboard
- Version-controlled dashboard JSON ready for IaC integration
- Stronger B2B and recruiter packaging: "Cloud Monitoring dashboard with non-zero metrics
  from a 1000-event end-to-end GCP pipeline run"

**This run still does not close:**

- Alerting gap
- Error counter datapoint gap
- IaC (Terraform) gap
- 5 000-event scale gap
- DLQ / retry safety gap
