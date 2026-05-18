# BigQuery Quality Alert Notification Proof Evidence

**Status:** VALIDATED - CONTROLLED FAILURE AND GITHUB ACTIONS FAILURE SURFACE PROVEN
**Date:** 2026-05-18
**Branch:** docs/bigquery-quality-alert-notification-proof-evidence

---

## 1. Scope

This document records proof that the `BigQuery Quality Checks` workflow can be triggered with
controlled inputs to produce both a passing outcome and a deliberate quality failure. It
establishes that:

- The workflow supports parameterised `workflow_dispatch` inputs (merged in PR #149).
- A safe run with permissive thresholds completes with `conclusion: success`.
- A controlled run with an impossible threshold (`min_row_count=999999999`) produces
  `conclusion: failure`, an `exit code 1`, and a preserved artifact containing the failure
  report.
- The GitHub Actions UI failure surface is observable.

This does **not** prove email notification delivery, GitHub notification bell delivery, Cloud
Monitoring alerting, or real scheduled event execution.

---

## 2. Safe Input Run Proof

| Field       | Value                                                                         |
|-------------|-------------------------------------------------------------------------------|
| Run ID      | 26007825072                                                                   |
| Event       | workflow_dispatch                                                             |
| Conclusion  | success                                                                       |
| Status      | completed                                                                     |
| Created     | 2026-05-18T00:54:04Z                                                          |
| Updated     | 2026-05-18T00:54:55Z                                                          |
| URL         | https://github.com/jcsf2020/real-time-data-platform/actions/runs/26007825072 |

### Dispatch Inputs

| Input                    | Value |
|--------------------------|-------|
| min_row_count            | 1     |
| freshness_max_age_hours  | 0     |

### Artifact Result

| Field               | Value                                  |
|---------------------|----------------------------------------|
| status              | ok                                     |
| failed_checks       | []                                     |
| generated_at_utc    | 2026-05-18T00:54:51.075794+00:00       |
| row_count_minimum   | pass                                   |
| observed            | 6120                                   |
| expected            | row_count >= 1                         |
| staging_table_empty | 0                                      |

All checks passed. `status: ok`, `failed_checks: []`.

---

## 3. Controlled Failure Run Proof

| Field       | Value                                                                         |
|-------------|-------------------------------------------------------------------------------|
| Run ID      | 26007909020                                                                   |
| Event       | workflow_dispatch                                                             |
| Conclusion  | failure                                                                       |
| Status      | completed                                                                     |
| Created     | 2026-05-18T00:57:19Z                                                          |
| Updated     | 2026-05-18T00:58:14Z                                                          |
| URL         | https://github.com/jcsf2020/real-time-data-platform/actions/runs/26007909020 |

### Dispatch Inputs

| Input                    | Value     |
|--------------------------|-----------|
| min_row_count            | 999999999 |
| freshness_max_age_hours  | 0         |

`min_row_count=999999999` is an impossible threshold: the table contains 6120 rows.

---

## 4. Artifact Proof (Controlled Failure Run)

Artifact preserved despite `conclusion: failure`.

| Field             | Value                                  |
|-------------------|----------------------------------------|
| status            | error                                  |
| failed_checks     | ["row_count_minimum"]                  |
| generated_at_utc  | 2026-05-18T00:58:09.742821+00:00       |
| row_count_minimum | fail                                   |
| observed          | 6120                                   |
| expected          | row_count >= 999999999                 |

### Baseline Checks — All Passed

| Check                      | Status |
|----------------------------|--------|
| row_count_positive         | pass   |
| required_columns_not_null  | pass   |
| event_id_unique            | pass   |
| event_type_accepted_values | pass   |
| freshness_available        | pass   |
| staging_table_empty        | pass   |

The artifact confirms exactly one check failed (`row_count_minimum`) and all others passed,
proving the threshold injection mechanism is precise and does not corrupt unrelated checks.

---

## 5. Failed Log Proof

Command visible in failed run logs:

```
python3 scripts/run_bigquery_quality_checks.py \
  --min-row-count 999999999 \
  --freshness-max-age-hours 0 \
  --report-output docs/evidence/bigquery-quality-checks/ci-report.json
```

Exit signal visible in failed run logs:

```
Process completed with exit code 1.
```

The non-zero exit code causes GitHub Actions to mark the step and workflow as failed.

---

## 6. UI Failure Surface Proof

GitHub Actions UI (mobile screenshot) shows:

```
BigQuery Quality Checks
status:   Failure
step:     Run BigQuery quality checks
duration: ~50s
artifact: 1 artifact preserved
```

The failure surface is observable in the GitHub Actions web UI. The failed workflow is
distinguishable from a passing run by its red failure badge and step-level failure annotation.

---

## 7. Safety Assertions

| Assertion                          | Verified |
|------------------------------------|----------|
| BigQuery not mutated               | yes      |
| Cloud SQL not started              | yes      |
| Cloud Scheduler jobs not executed  | yes      |
| No secrets printed in logs         | yes      |
| No Terraform changes applied       | yes      |
| All checks were read-only SELECTs  | yes      |
| Artifact preserved despite failure | yes      |

Both runs used only read-only `SELECT` statements against existing tables. No `INSERT`,
`UPDATE`, `DELETE`, `CREATE`, or `DROP` statements were issued.

---

## 8. What This Proves

- `workflow_dispatch` inputs (`min_row_count`, `freshness_max_age_hours`) are wired end-to-end
  into the quality check script (PR #149).
- A safe threshold run produces `conclusion: success` and `status: ok`.
- An impossible threshold run produces `conclusion: failure` and `status: error`.
- `failed_checks: ["row_count_minimum"]` is recorded in the artifact with the correct
  observed/expected values (6120 vs 999999999).
- Baseline checks continue to pass during a controlled failure, confirming check isolation.
- The artifact is preserved even when the workflow concludes as failure.
- `exit code 1` is visible in the failed run logs.
- The GitHub Actions UI failure surface is observable and distinguishable.

---

## 9. What This Does Not Prove

- Email notification delivery (email not proven).
- GitHub notification bell delivery (bell not proven).
- Cloud Monitoring alerting (Cloud Monitoring not proven).
- Cloud Monitoring quality metrics being emitted.
- Real scheduled event execution (only `workflow_dispatch` was tested).
- Cloud SQL was started or queried.
- Any Cloud Scheduler job was executed.
- Any BigQuery table was modified.

---

## 10. Acceptance Matrix

| Criterion                                              | Result |
|--------------------------------------------------------|--------|
| workflow_dispatch inputs merged (PR #149)              | PASS   |
| Safe run: conclusion == success                        | PASS   |
| Safe run: status == ok                                 | PASS   |
| Safe run: failed_checks == []                          | PASS   |
| Controlled run: conclusion == failure                  | PASS   |
| Controlled run: status == error                        | PASS   |
| Controlled run: failed_checks == ["row_count_minimum"] | PASS   |
| Controlled run: observed 6120 < expected 999999999     | PASS   |
| Artifact preserved despite failure                     | PASS   |
| exit code 1 visible in logs                            | PASS   |
| GitHub Actions UI failure surface observable           | PASS   |
| Baseline checks unaffected by injected failure         | PASS   |
| BigQuery not mutated                                   | PASS   |
| Cloud SQL not started                                  | PASS   |
| Cloud Scheduler not executed                           | PASS   |

---

## 11. Remaining Notification Gap

The following notification paths have not been exercised and remain unproven:

| Gap                              | Status   | Notes                                          |
|----------------------------------|----------|------------------------------------------------|
| Email notification on failure    | NOT PROVEN | Requires GitHub notification settings + SMTP |
| GitHub bell notification         | NOT PROVEN | Requires verified subscriber on workflow     |
| Cloud Monitoring alert policy    | NOT PROVEN | Requires metric emission + alert firing      |
| Cloud Monitoring quality metrics | NOT PROVEN | No metric emission plumbed to workflow       |
| Scheduled trigger (cron)         | NOT PROVEN | Only workflow_dispatch tested                |

---

## 12. Final Conclusion

Two `workflow_dispatch` runs were executed against the `BigQuery Quality Checks` workflow on
2026-05-18:

1. **Run 26007825072** — safe inputs (`min_row_count=1`): completed with `conclusion: success`,
   `status: ok`, `failed_checks: []`, observed 6120 rows against threshold >= 1.

2. **Run 26007909020** — controlled failure inputs (`min_row_count=999999999`): completed with
   `conclusion: failure`, `status: error`, `failed_checks: ["row_count_minimum"]`, observed
   6120 rows against impossible threshold >= 999999999. Artifact was preserved. `exit code 1`
   was recorded in logs. GitHub Actions UI failure surface was observable.

The controlled failure mechanism is validated. No production state was mutated. Notification
delivery paths (email, bell, Cloud Monitoring) remain unproven and are captured as the
remaining gap.
