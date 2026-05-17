# BigQuery Quality Schedule Enabled Evidence

**Status:** VALIDATED - SCHEDULE ENABLED, POST-MERGE MANUAL RUN PASSED
**Date:** 2026-05-17
**Branch:** docs/bigquery-quality-schedule-enabled-evidence

---

## 1. Scope

This document proves that PR #141 successfully added a `schedule` trigger to the
`BigQuery Quality Checks` workflow, and that a manual `workflow_dispatch` run executed
after the merge confirms the workflow still passes end-to-end with the schedule trigger
present in the YAML.

It does **not** prove that a real scheduled event has fired or that the schedule is
reliable over time.

---

## 2. Workflow Trigger State

File: `.github/workflows/bigquery-quality-checks.yml`

```yaml
"on":
  workflow_dispatch:
  schedule:
    - cron: "15 6 * * *"
```

| Field            | Value                          |
|------------------|--------------------------------|
| PR that added it | #141                           |
| Cron expression  | `15 6 * * *`                   |
| Interpretation   | 06:15 UTC daily                |
| Manual trigger   | `workflow_dispatch` (retained) |

The `schedule` block was merged to `main` via PR #141. Both triggers coexist: the
workflow can be invoked manually or run automatically at 06:15 UTC each day.

---

## 3. Post-Merge Manual Validation Proof

A `workflow_dispatch` run was executed against `main` after PR #141 was merged, to verify
that the workflow continues to function with the `schedule` trigger present.

| Field      | Value                                                                         |
|------------|-------------------------------------------------------------------------------|
| Workflow   | BigQuery Quality Checks                                                       |
| Run ID     | 25984483471                                                                   |
| Event      | workflow_dispatch                                                             |
| Status     | completed                                                                     |
| Conclusion | success                                                                       |
| URL        | https://github.com/jcsf2020/real-time-data-platform/actions/runs/25984483471 |
| Created    | 2026-05-17T07:19:46Z                                                          |
| Updated    | 2026-05-17T07:20:34Z                                                          |

---

## 4. Artifact Proof

Artifact: `bigquery-quality-checks-report / ci-report.json`

| Field               | Value                                      |
|---------------------|--------------------------------------------|
| status              | ok                                         |
| failed_checks       | []                                         |
| checks              | 6                                          |
| generated_at_utc    | 2026-05-17T07:20:30.420792+00:00           |
| project_id          | project-42987e01-2123-446b-ac7             |
| dataset             | rtdp_analytics                             |
| table               | market_events_raw                          |
| staging_table       | market_events_raw_staging                  |
| accepted_event_types | ["trade"]                                 |

### Quality Checks Detail

| Check                      | Status | Observed                                                        |
|----------------------------|--------|-----------------------------------------------------------------|
| row_count_positive         | pass   | 6120                                                            |
| required_columns_not_null  | pass   | all required null counts 0                                      |
| event_id_unique            | pass   | duplicate_event_ids 0                                           |
| event_type_accepted_values | pass   | invalid_event_type_rows 0                                       |
| freshness_available        | pass   | max_ingest_timestamp 2026-05-16 10:08:49.141452+00, row_count 6120 |
| staging_table_empty        | pass   | observed 0                                                      |

All 6 checks passed. `failed_checks: []`.

---

## 5. Safety Assertions

| Assertion                         | Verified |
|-----------------------------------|----------|
| Cloud SQL not started             | yes      |
| Scheduler not executed            | yes      |
| BigQuery not mutated              | yes      |
| No secrets printed in logs        | yes      |
| No Terraform changes applied      | yes      |
| All checks were read-only SELECTs | yes      |

All SQL executed by this workflow consists of read-only `SELECT` statements. No `INSERT`,
`UPDATE`, `DELETE`, `CREATE`, or `DROP` statements were issued.

---

## 6. What This Proves

- The `schedule` trigger (`15 6 * * *`) is present in `.github/workflows/bigquery-quality-checks.yml` on `main` after merge of PR #141.
- `workflow_dispatch` (manual) still succeeds after the `schedule` block was added — the two triggers coexist without conflict.
- GCP Workload Identity Federation / OIDC authentication succeeds from GitHub Actions.
- The `bq` CLI is available and functional in the GitHub Actions runner.
- Six read-only quality checks execute successfully against `rtdp_analytics.market_events_raw`.
- The artifact report (`ci-report.json`) is generated and downloadable from the Actions run.
- `market_events_raw` contains 6120 rows as of `2026-05-16 10:08:49 UTC`.
- `market_events_raw_staging` is empty (0 rows), confirming no pending staged data.

---

## 7. What This Does Not Prove

- A real GitHub Actions **scheduled event** has executed — scheduled event real execution is **NOT YET PROVEN**.
- The schedule fires reliably at 06:15 UTC daily.
- Cloud SQL was started or queried.
- Any Cloud Scheduler job was executed.
- BigQuery was mutated — BigQuery not mutated; all operations were read-only.
- Cloud SQL was started — Cloud SQL not started by this workflow.
- Any alerting on quality failure has been tested.
- Any Terraform configuration was changed or applied.

---

## 8. Acceptance Matrix

| Criterion                                              | Result |
|--------------------------------------------------------|--------|
| `schedule` cron `15 6 * * *` present in workflow YAML | PASS   |
| `workflow_dispatch` trigger retained after PR #141     | PASS   |
| Post-merge `workflow_dispatch` run conclusion: success | PASS   |
| All 6 quality checks report status: pass               | PASS   |
| `failed_checks` is empty                               | PASS   |
| Artifact `ci-report.json` is downloadable              | PASS   |
| `row_count_positive` observed > 0 (6120)               | PASS   |
| `staging_table_empty` observed == 0                    | PASS   |
| No secrets in artifact or logs                         | PASS   |
| Cloud SQL not started                                  | PASS   |
| BigQuery not mutated                                   | PASS   |

---

## 9. Next Proof Required

| Proof                                    | Status       |
|------------------------------------------|--------------|
| Scheduled event real execution           | NOT YET DONE |
| Schedule fires at correct UTC time       | NOT YET DONE |
| Alert triggered on quality check failure | NOT YET DONE |

The next evidence document should capture a run with `event: schedule` (not
`workflow_dispatch`) to confirm the cron trigger actually fires in GitHub Actions.

---

## 10. Final Conclusion

The `BigQuery Quality Checks` workflow has the `schedule` trigger (`15 6 * * *`) enabled
on `main` following the merge of PR #141. A post-merge manual `workflow_dispatch` run
(Run ID: 25984483471) completed successfully on 2026-05-17, confirming that both triggers
coexist and the workflow remains fully functional. All 6 read-only quality checks passed
against `rtdp_analytics.market_events_raw`. No production state was mutated. Real
scheduled event execution is NOT YET PROVEN.
