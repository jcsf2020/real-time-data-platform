# BigQuery Freshness Live Validation Evidence

**Status:** VALIDATED - FRESHNESS MAX AGE LIVE FAILURE PROVEN
**Date:** 2026-05-18
**Branch:** docs/bigquery-freshness-live-validation-evidence

---

## Scope

This document provides evidence that `freshness_max_age_hours` is live-executed in GitHub Actions and that its failure path is proven end-to-end. The check ran against a real BigQuery table, produced a structured artifact, and returned a non-zero exit code that set the workflow conclusion to `failure`.

---

## Run Metadata

| Field       | Value                                                                                          |
|-------------|------------------------------------------------------------------------------------------------|
| Run ID      | 26020167461                                                                                    |
| Event       | workflow_dispatch                                                                              |
| Conclusion  | failure                                                                                        |
| Status      | completed                                                                                      |
| Created     | 2026-05-18T07:41:03Z                                                                           |
| Updated     | 2026-05-18T07:41:53Z                                                                           |
| URL         | https://github.com/jcsf2020/real-time-data-platform/actions/runs/26020167461                  |

---

## Dispatch Inputs

| Input                    | Value |
|--------------------------|-------|
| `min_row_count`          | 1     |
| `freshness_max_age_hours`| 1     |

The threshold of 1 hour was chosen to guarantee a freshness failure given that no new data has been ingested recently.

---

## Artifact Proof

The quality script emitted a structured JSON artifact captured by the workflow:

```json
{
  "status": "error",
  "failed_checks": ["freshness_max_age_hours"],
  "generated_at_utc": "2026-05-18T07:41:50.304811+00:00",
  "project_id": "project-42987e01-2123-446b-ac7",
  "dataset": "rtdp_analytics",
  "table": "market_events_raw",
  "staging_table": "market_events_raw_staging",
  "accepted_event_types": ["trade"]
}
```

`failed_checks: ["freshness_max_age_hours"]` confirms exactly one check failed and it is `freshness_max_age_hours`.

---

## Freshness Failure Detail

| Field                  | Value                              |
|------------------------|------------------------------------|
| Check name             | `freshness_max_age_hours`          |
| Expected               | `age_hours <= 1.0`                 |
| Observed `age_hours`   | 45.5496                            |
| `max_ingest_timestamp` | 2026-05-16 10:08:49.141452+00      |
| Status                 | **fail**                           |

The observed age of 45.5496 hours far exceeds the 1-hour threshold. The `max_ingest_timestamp` of `2026-05-16 10:08:49.141452+00` confirms that no data was ingested in the ~45.5 hours preceding the run.

---

## Control Checks Passed

All baseline and control checks passed, proving the freshness failure is isolated:

| Check                       | Expected                        | Observed          | Status |
|-----------------------------|---------------------------------|-------------------|--------|
| `row_count_positive`        | row_count > 0                   | 6120              | pass   |
| `row_count_minimum`         | row_count >= 1                  | 6120              | pass   |
| `required_columns_not_null` | no nulls in required columns    | —                 | pass   |
| `event_id_unique`           | no duplicate event_ids          | —                 | pass   |
| `event_type_accepted_values`| all events in ["trade"]         | —                 | pass   |
| `freshness_available`       | max_ingest_timestamp present    | row_count 6120    | pass   |
| `staging_table_empty`       | staging row_count == 0          | 0                 | pass   |

The passing `row_count_minimum` (6120 >= 1) and `freshness_available` (timestamp present, 6120 rows) confirm the table is reachable and populated — the freshness threshold is the only failure.

---

## Safety Assertions

| Assertion                        | Result                                   |
|----------------------------------|------------------------------------------|
| BigQuery not mutated             | All quality SQL used read-only SELECT    |
| Cloud SQL not started            | Not involved in this run                 |
| Cloud Scheduler not executed     | Triggered via workflow_dispatch only     |
| No secrets printed               | Credentials used via Workload Identity   |

---

## What This Proves

- `freshness_max_age_hours` is live-executed in GitHub Actions via `workflow_dispatch`
- The live failure path for `freshness_max_age_hours` is proven end-to-end
- The failure is isolated to `freshness_max_age_hours`; all other checks pass
- A structured artifact is produced and preserved by the workflow
- The BigQuery quality script correctly evaluates freshness thresholds at runtime against a real dataset

---

## What This Does Not Prove

- A **passing** `freshness_max_age_hours` live run
- Email notification delivery
- GitHub notification bell delivery
- Cloud Monitoring alerting
- Real scheduled event execution — NOT YET PROVEN

---

## Acceptance Matrix

| Criterion                                              | Met? |
|--------------------------------------------------------|------|
| Run executed in GitHub Actions                         | yes  |
| Event type is `workflow_dispatch`                      | yes  |
| Conclusion is `failure`                                | yes  |
| `freshness_max_age_hours` in `failed_checks`           | yes  |
| `age_hours <= 1.0` threshold documented                | yes  |
| Observed `age_hours` (45.5496) documented              | yes  |
| `max_ingest_timestamp` documented                      | yes  |
| All control/baseline checks pass                       | yes  |
| `staging_table_empty` passes (0 rows)                  | yes  |
| `row_count_minimum` passes (6120 >= 1)                 | yes  |
| BigQuery not mutated                                   | yes  |
| Cloud SQL not started                                  | yes  |
| Cloud Scheduler not executed                           | yes  |
| Artifact JSON preserved                                | yes  |

---

## Final Conclusion

The `freshness_max_age_hours` check is proven live in GitHub Actions. The workflow dispatched against `rtdp_analytics.market_events_raw` with a 1-hour threshold, observed an actual data age of 45.5496 hours, and correctly reported `status: error` with `failed_checks: ["freshness_max_age_hours"]`. All control checks passed, isolating the failure to the freshness threshold. The artifact is preserved and the run URL is recorded above.

The live failure path for `freshness_max_age_hours` is fully evidenced.
