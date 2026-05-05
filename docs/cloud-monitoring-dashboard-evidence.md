# Cloud Monitoring Dashboard — Creation Evidence

**Status:** CREATED — VALIDATED
**Branch:** `feat/cloud-monitoring-dashboard`
**Date:** 2026-05-06

---

## Context

The Devil's Advocate audit identified a gap: the **RTDP Pipeline Overview** Cloud Monitoring dashboard had a runbook but had never been executed. This evidence record closes that gap by documenting the single GCP write (dashboard creation) performed on this branch, preceded by full pre-execution validation.

Runbook: [docs/cloud-monitoring-dashboard-runbook.md](cloud-monitoring-dashboard-runbook.md)

---

## Pre-Execution Validation

### Branch and Tests

| Check | Result |
|---|---|
| Branch | `feat/cloud-monitoring-dashboard` |
| pytest | 116 passed |
| Ruff | All checks passed |
| Cloud SQL state | `NEVER / STOPPED` |

### Logs-Based Metric Descriptors Confirmed

All four required metric descriptors were present before dashboard creation:

```
silver_refresh_error_count      DELTA  INT64
silver_refresh_success_count    DELTA  INT64
worker_message_error_count      DELTA  INT64
worker_message_processed_count  DELTA  INT64
```

### Worker Processed Datapoints (Non-Zero Operational Data)

Timeseries datapoints confirmed for `worker_message_processed_count` before dashboard creation (aligns with the 1000-event load test):

```
2026-05-05T21:44:00Z -> 2026-05-05T21:45:00Z:    0
2026-05-05T21:43:00Z -> 2026-05-05T21:44:00Z:  150
2026-05-05T21:42:00Z -> 2026-05-05T21:43:00Z:  850
2026-05-05T21:41:00Z -> 2026-05-05T21:42:00Z:    0
TOTAL = 1000
```

---

## Dashboard Creation

### GCP API Response

```
DASHBOARD_NAME=projects/892892382088/dashboards/1277f289-1f9a-4983-944f-913ce0f92622
DISPLAY_NAME=RTDP Pipeline Overview
TILE_COUNT=4
```

### Dashboard Panels

| Panel | Metric |
|---|---|
| Worker Processed Messages / min | `worker_message_processed_count` |
| Worker Error Count | `worker_message_error_count` |
| Silver Refresh Success Count | `silver_refresh_success_count` |
| Silver Refresh Error Count | `silver_refresh_error_count` |

---

## Dashboard Export Validation

The dashboard was exported immediately after creation and validated:

**Export path:** `infra/monitoring/dashboards/rtdp-pipeline-overview.json`

**Export validation output:**

```
infra/monitoring/dashboards/rtdp-pipeline-overview.json
NAME=projects/892892382088/dashboards/1277f289-1f9a-4983-944f-913ce0f92622
DISPLAY_NAME=RTDP Pipeline Overview
TILE_COUNT=4
```

**JSON validation:** `python3 -m json.tool` — valid

---

## Acceptance Criteria

| Criterion | Result |
|---|---|
| Dashboard created in GCP Cloud Monitoring | PASS |
| Display name is `RTDP Pipeline Overview` | PASS |
| Dashboard has exactly 4 tiles | PASS |
| Dashboard exported to `infra/monitoring/dashboards/rtdp-pipeline-overview.json` | PASS |
| Exported JSON is valid | PASS |
| All four logs-based metrics present before creation | PASS |
| Non-zero datapoints confirmed before creation | PASS |
| pytest 116 passed | PASS |
| Ruff clean | PASS |
| Cloud SQL `NEVER / STOPPED` throughout | PASS |

---

## Claims Now Allowed

- The **RTDP Pipeline Overview** Cloud Monitoring dashboard exists in GCP project `892892382088`.
- Dashboard ID: `projects/892892382088/dashboards/1277f289-1f9a-4983-944f-913ce0f92622`
- The dashboard visualises all four validated logs-based metrics.
- The dashboard definition is version-controlled at `infra/monitoring/dashboards/rtdp-pipeline-overview.json`.

## Claims Still Not Allowed

- That the dashboard has received live traffic since creation (no additional load test was run on this branch).
- That alerting policies are configured (out of scope for this branch).

---

## Exclusions Confirmed

| Exclusion | Confirmed |
|---|---|
| No Cloud SQL start | YES — Cloud SQL remained `NEVER / STOPPED` throughout |
| No Pub/Sub messages published | YES |
| No deployment performed | YES |
| No application code changes | YES |
| No test changes | YES |

The only GCP write performed on this branch was the dashboard creation call.
