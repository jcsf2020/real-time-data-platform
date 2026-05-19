# BigQuery Quality Freshness Age Hours Metric Evidence

**Status:** VALIDATED - FRESHNESS AGE HOURS METRIC EMITTED TO CLOUD MONITORING
**Date:** 2026-05-19
**Branch:** docs/bigquery-quality-freshness-age-hours-metric-evidence

---

## 1. Scope

This document records the evidence that the
`custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours` metric is emitted to
Cloud Monitoring by the BigQuery Quality Checks workflow.

The previous metrics proof document
(`bigquery-quality-cloud-monitoring-metrics-evidence.md`) acknowledged that
`freshness_age_hours` was **not yet proven** because both proof runs used
`freshness_max_age_hours=0`, which prevented the freshness check from activating and
suppressed the metric value.

This document closes that gap by running the workflow with `freshness_max_age_hours=999999`
— a permissive threshold that activates the freshness check without triggering a failure —
and confirming the metric datapoint in Cloud Monitoring.

This document does **not** prove:

- Incident creation NOT YET PROVEN.
- Email notification delivery NOT YET PROVEN.
- GitHub notification bell delivery NOT YET PROVEN.

---

## 2. Workflow Run Evidence

| Field | Value |
| --- | --- |
| Workflow | BigQuery Quality Checks |
| Run ID | 26069840695 |
| Event | workflow_dispatch |
| Conclusion | success |
| Created | 2026-05-19T01:06:20Z |
| Updated | 2026-05-19T01:07:12Z |
| URL | <https://github.com/jcsf2020/real-time-data-platform/actions/runs/26069840695> |

### Dispatch Inputs

| Input | Value |
| --- | --- |
| `min_row_count` | 1 |
| `freshness_max_age_hours` | 999999 |

`freshness_max_age_hours=999999` is a permissive threshold that activates the freshness
check and causes `age_hours` to be computed and emitted, while avoiding a failure for any
realistic table age.

---

## 3. Quality Report Evidence

| Field | Value |
| --- | --- |
| status | ok |
| failed_checks | [] |
| row_count | 6120 |
| freshness_max_age_hours | pass |
| age_hours | 62.9712 |
| max_ingest_timestamp | 2026-05-16 10:08:49.141452+00 |
| staging_table_empty | pass |
| staging observed | 0 |

All checks passed. `status: ok`, `failed_checks: []`.

The `age_hours` value of `62.9712` confirms the freshness check was active and computed a
concrete floating-point value, which was then included in the metric push payload.

### Metric Emission Log Evidence

The "Push BigQuery quality metrics to Cloud Monitoring" step log confirmed:

```text
Pushed 12 time series to Cloud Monitoring.
```

The count increased from 10 (previous runs) to 12, consistent with the addition of
`freshness_age_hours` (double) and one additional freshness-related time series compared
to runs where `freshness_max_age_hours=0`.

---

## 4. Cloud Monitoring REST Evidence

The Cloud Monitoring REST API was queried after Run 26069840695 to confirm the
`freshness_age_hours` datapoint was recorded.

| Field | Value |
| --- | --- |
| Metric | `custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours` |
| series_count | 1 |
| value | `doubleValue = 62.9712` |
| endTime | 2026-05-19T01:07:08Z |
| labels | {} |

The datapoint matches the `age_hours` value from the quality report exactly, confirming
end-to-end propagation from the BigQuery freshness check through the metric push script to
Cloud Monitoring storage.

---

## 5. Previous Failed Attempt

An earlier run attempted the same validation but failed before metric emission completed.

| Field | Value |
| --- | --- |
| Run ID | 26069153131 |
| Conclusion | failure |
| Quality report status | ok |
| Artifact age_hours | 62.622 |
| Failure reason | HTTP 500 Internal Server Error from Cloud Monitoring API |
| Cloud Monitoring freshness_age_hours series_count | 0 |

The metric push step exited with a non-zero code due to the HTTP 500, preventing any time
series from being recorded. The quality report itself was valid and the artifact was
preserved.

Run 26069840695 supersedes this attempt. The HTTP 500 was transient; the retry succeeded
without any code changes.

---

## 6. Safety Notes

| Assertion | Result |
| --- | --- |
| BigQuery not mutated | Quality SQL uses read-only SELECT; metric script reads the JSON report only |
| Cloud SQL not started | Not involved in this run |
| Cloud Scheduler not executed | Run triggered via workflow_dispatch only |
| Terraform not changed | No Terraform files modified for this proof run |
| Terraform apply not executed | No infrastructure changes were applied |
| no secrets printed | Credentials used via Workload Identity Federation; no keys in logs |
| Artifact preserved | ci-report.json artifact retained from the successful run |

---

## 7. Validation Commands

To reproduce the Cloud Monitoring query that confirmed the datapoint:

```bash
# Query freshness_age_hours time series (adjust project and time window as needed)
gcloud monitoring time-series list \
  --filter='metric.type="custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours"' \
  --interval-start-time="2026-05-19T01:00:00Z" \
  --interval-end-time="2026-05-19T01:15:00Z"
```

Expected: `series_count=1`, `doubleValue=62.9712`, `endTime=2026-05-19T01:07:08Z`.

---

## 8. Conclusion

Run 26069840695 (`workflow_dispatch`, `freshness_max_age_hours=999999`, conclusion: success)
proves that the `freshness_age_hours` metric is emitted to Cloud Monitoring with the correct
double value.

Key facts:

- Quality report: `age_hours = 62.9712`, `freshness_max_age_hours: pass`, `status: ok`.
- Step log: `Pushed 12 time series to Cloud Monitoring.`
- Cloud Monitoring REST: `freshness_age_hours`, `series_count=1`,
  `doubleValue=62.9712`, `endTime=2026-05-19T01:07:08Z`.
- A prior run (26069153131) failed with HTTP 500 and recorded zero series; that attempt is
  superseded.

The `freshness_age_hours` gap identified in the previous metrics evidence document is now
closed. The remaining open items are:

- Incident creation NOT YET PROVEN.
- Email notification delivery NOT YET PROVEN.
- GitHub notification bell delivery NOT YET PROVEN.

---

Evidence status: VALIDATED - FRESHNESS AGE HOURS METRIC EMITTED TO CLOUD MONITORING
