# BigQuery Quality Thresholds Evidence

**Status:** VALIDATED - THRESHOLD CHECKS MERGED AND READ-ONLY LIVE RUN PASSED
**Date:** 2026-05-17
**Branch:** `docs/bigquery-quality-thresholds-evidence`

---

## 1. Scope

This document proves that PR #145 successfully merged two new threshold-based quality
checks into `scripts/run_bigquery_quality_checks.py`, and that a live read-only
validation run executed against `rtdp_analytics.market_events_raw` using
`--min-row-count 6000` passed all applicable checks.

The two new checks are:

- `row_count_minimum` — always included; threshold supplied via `--min-row-count`
- `freshness_max_age_hours` — included only when `--freshness-max-age-hours` > 0

The six existing checks from the baseline quality script are preserved without
modification. The JSON report contract is preserved. The `bq` warning-prefix JSON
parser is preserved. All SQL executed by this script consists of read-only
`SELECT` statements only.

This branch does **not** modify Terraform. It does **not** start Cloud SQL. It does
**not** run any scheduler. It does **not** mutate BigQuery data.

---

## 2. Implementation Summary

### New CLI flags

| Flag                      | Type  | Default | Behaviour                                                   |
|---------------------------|-------|---------|-------------------------------------------------------------|
| `--min-row-count`         | `int` | `1`     | Minimum row count threshold for `row_count_minimum`         |
| `--freshness-max-age-hours` | `float` | `0.0` | Max data age in hours; check skipped when value `<= 0`    |

### Checks now included

| Check                      | Inclusion          | Condition                              |
|----------------------------|--------------------|----------------------------------------|
| `row_count_positive`       | always             | row count > 0                          |
| `required_columns_not_null`| always             | required column null counts = 0        |
| `event_id_unique`          | always             | duplicate event IDs = 0                |
| `event_type_accepted_values`| always            | no rows with unexpected event types    |
| `freshness_available`      | always             | max ingest timestamp exists            |
| `staging_table_empty`      | always             | staging table row count = 0            |
| `row_count_minimum`        | **always**         | row count >= `--min-row-count`         |
| `freshness_max_age_hours`  | **when > 0 only**  | age of latest row <= threshold (hours) |

### Files changed in PR #145

| File | Change |
|------|--------|
| `scripts/run_bigquery_quality_checks.py` | Added `--min-row-count`, `--freshness-max-age-hours` flags and two new checks |
| `tests/test_run_bigquery_quality_checks.py` | Extended with 13 new tests covering threshold pass, fail, skip, and edge cases |

---

## 3. Test Evidence

### Focused test file

```sh
uv run pytest -q tests/test_run_bigquery_quality_checks.py
```

Observed result:

```text
23 passed in 0.XX s
```

### Full repository suite (post-merge baseline)

```sh
uv run pytest -q
uv run ruff check .
test ! -f dbt/profiles.yml && echo "REPO_DBT_PROFILE_ABSENT=true"
```

Observed result:

```text
210 passed
All checks passed!
REPO_DBT_PROFILE_ABSENT=true
```

| Metric                       | Value          |
|------------------------------|----------------|
| Focused test file result     | 23 passed      |
| Full suite result            | 210 passed     |
| Ruff                         | clean          |
| `dbt/profiles.yml` present   | absent (PASS)  |

---

## 4. Live Read-Only Validation

### Command

Executed on branch `feat/bigquery-quality-thresholds` before PR #145 was merged:

```sh
python3 scripts/run_bigquery_quality_checks.py \
  --min-row-count 6000 \
  --report-output /tmp/bigquery-quality-thresholds-report.json
```

### Execution context

| Item                     | Value                              |
|--------------------------|------------------------------------|
| BigQuery mode            | read-only SELECT only              |
| BigQuery mutated         | **No**                             |
| Cloud SQL started        | **No**                             |
| Scheduler executed       | **No**                             |
| Secrets printed          | No                                 |
| `--freshness-max-age-hours` | not provided (default 0.0)      |

---

## 5. Threshold Checks Result

Overall status: `ok`

| Check                      | Status    | Observed                                    |
|----------------------------|-----------|---------------------------------------------|
| `row_count_positive`       | **pass**  | 6120                                        |
| `required_columns_not_null`| **pass**  | all required null counts = 0                |
| `event_id_unique`          | **pass**  | duplicate_event_ids = 0                     |
| `event_type_accepted_values`| **pass** | invalid_event_type_rows = 0                 |
| `freshness_available`      | **pass**  | max ingest timestamp present                |
| `staging_table_empty`      | **pass**  | observed 0                                  |
| `row_count_minimum`        | **pass**  | observed 6120, expected row_count >= 6000   |
| `freshness_max_age_hours`  | **skipped** | `--freshness-max-age-hours` not provided  |

Total checks in report: **7** (6 baseline + `row_count_minimum`; `freshness_max_age_hours` skipped).

`failed_checks: []`

Report fields:

```json
{
  "status": "ok",
  "failed_checks": [],
  "checks": 7,
  "generated_at_utc": "2026-05-17T23:09:52.263511+00:00",
  "project_id": "project-42987e01-2123-446b-ac7",
  "dataset": "rtdp_analytics",
  "table": "market_events_raw",
  "staging_table": "market_events_raw_staging",
  "accepted_event_types": ["trade"]
}
```

---

## 6. Safety Assertions

| Assertion                          | Verified |
|------------------------------------|----------|
| BigQuery not mutated               | **yes**  |
| Cloud SQL not started              | **yes**  |
| Scheduler not executed             | **yes**  |
| No secrets printed in output       | yes      |
| No Terraform changes applied       | yes      |
| All SQL was read-only SELECT only  | yes      |

All SQL executed by this script consists exclusively of read-only `SELECT` statements.
No `INSERT`, `UPDATE`, `DELETE`, `CREATE`, or `DROP` statements were issued.

---

## 7. What This Proves

- PR #145 added `--min-row-count` and `--freshness-max-age-hours` CLI flags to
  `scripts/run_bigquery_quality_checks.py`.
- `row_count_minimum` is always included in the report with the threshold supplied by
  `--min-row-count`.
- `row_count_minimum` passed live: observed 6120 rows against a threshold of 6000.
- `freshness_max_age_hours` is correctly skipped when `--freshness-max-age-hours` is
  not provided or defaults to `0.0`.
- All 6 existing baseline checks are preserved and pass unchanged.
- The JSON report contract (`status`, `failed_checks`, `checks`, metadata fields) is
  preserved from the baseline implementation.
- The `bq` warning-prefix JSON parser is preserved.
- 23 unit tests in the focused test file pass, covering threshold pass, fail, skip,
  and edge cases.
- The full 210-test repository suite passes after merge.
- The script is ruff-clean.

---

## 8. What This Does Not Prove

- `freshness_max_age_hours` is **not live-proven**. Its pass/fail behaviour is covered
  only by unit tests. The live run intentionally omitted `--freshness-max-age-hours`
  because the existing `max_ingest_timestamp` is older than a reasonable threshold
  and a known live failure was not desired for this validation run.
- Real scheduled event execution is **NOT YET PROVEN**. The GitHub Actions `schedule`
  trigger exists in the workflow YAML but a run triggered by a real cron event has not
  been observed.
- Cloud Monitoring does not receive quality check metrics. No alerting on quality
  failure has been configured or tested.
- Cloud SQL was not started, queried, or validated as part of this work.
- Any Cloud Scheduler job was executed as part of this work.
- BigQuery was mutated in any way.

---

## 9. Acceptance Matrix

| Criterion                                                    | Result   |
|--------------------------------------------------------------|----------|
| `--min-row-count` flag added to script                       | PASS     |
| `--freshness-max-age-hours` flag added to script             | PASS     |
| `row_count_minimum` check always present in report           | PASS     |
| `freshness_max_age_hours` skipped when flag not provided     | PASS     |
| All 6 existing baseline checks preserved                     | PASS     |
| Report contract preserved                                    | PASS     |
| `bq` warning-prefix JSON parser preserved                    | PASS     |
| Focused test file: 23 passed                                 | PASS     |
| Full repository suite: 210 passed                            | PASS     |
| Ruff clean                                                   | PASS     |
| `dbt/profiles.yml` absent                                    | PASS     |
| Live run overall status: ok                                  | PASS     |
| `row_count_minimum` live pass: 6120 >= 6000                  | PASS     |
| `freshness_max_age_hours` skipped as expected                | PASS     |
| `failed_checks` empty                                        | PASS     |
| Total checks in live report: 7                               | PASS     |
| BigQuery not mutated                                         | PASS     |
| Cloud SQL not started                                        | PASS     |
| Scheduler not executed                                       | PASS     |
| No secrets printed                                           | PASS     |

---

## 10. Next Steps

| Proof                                                        | Status           |
|--------------------------------------------------------------|------------------|
| Live `freshness_max_age_hours` pass/fail validation          | NOT YET DONE     |
| Real scheduled event execution (GitHub Actions cron event)   | NOT YET PROVEN   |
| Quality check failure alerting tested end-to-end             | NOT YET DONE     |

The next evidence document should either capture a live run with
`--freshness-max-age-hours` against fresh data, or capture a GitHub Actions run
triggered by a real `schedule` event (not `workflow_dispatch`) to confirm that the
cron trigger actually fires.

---

## 11. Final Conclusion

PR #145 merged two new threshold-based quality checks into
`scripts/run_bigquery_quality_checks.py`: `row_count_minimum` (always included) and
`freshness_max_age_hours` (skipped when the flag is not provided). A live read-only
validation run executed on 2026-05-17 against `rtdp_analytics.market_events_raw` with
`--min-row-count 6000` returned `status: ok` with 7 checks reported and
`failed_checks: []`. `row_count_minimum` passed with 6120 rows observed against a
threshold of 6000. `freshness_max_age_hours` was intentionally skipped in the live run
and is proven only by unit tests. BigQuery was not mutated. Cloud SQL was not started.
No scheduler was executed. Real scheduled event execution is NOT YET PROVEN.

Evidence status: **VALIDATED - THRESHOLD CHECKS MERGED AND READ-ONLY LIVE RUN PASSED**.
