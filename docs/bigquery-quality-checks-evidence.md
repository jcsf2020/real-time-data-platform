# BigQuery Quality Checks Evidence

**Status:** VALIDATED - READ-ONLY BIGQUERY QUALITY CHECKS
**Date:** 2026-05-16
**Branch:** `feat/data-quality-checks-bigquery`

---

## Scope

This evidence documents a read-only BigQuery data quality validation layer for the
`rtdp_analytics.market_events_raw` analytical table.

The goal is to prove that the current BigQuery analytical layer has basic automated
quality checks for:

- positive row count
- required fields not null
- unique `event_id`
- accepted `event_type` values
- freshness signal available
- staging table empty after merge workflow

This branch does not modify Terraform. It does not start Cloud SQL. It does not run
any scheduler. It does not mutate BigQuery data.

---

## Files Added

| File | Purpose |
| --- | --- |
| `scripts/run_bigquery_quality_checks.py` | Read-only BigQuery quality check runner using the `bq` CLI |
| `tests/test_run_bigquery_quality_checks.py` | Unit tests for SQL construction, report contract, failures and output writing |
| `docs/evidence/bigquery-quality-checks/report.json` | Real BigQuery quality check output |
| `docs/bigquery-quality-checks-evidence.md` | Evidence summary |

---

## Script Design

The script intentionally avoids third-party Python dependencies.

It uses:

```sh
bq query --nouse_legacy_sql --format=json
```

Target table:

```text
project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw
```

Target staging table:

```text
project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw_staging
```

Default accepted event types:

```text
trade
```

---

## Quality Checks

| Check | Expected |
| --- | --- |
| `row_count_positive` | `row_count > 0` |
| `required_columns_not_null` | required column null counts equal 0 |
| `event_id_unique` | duplicate `event_id` count equals 0 |
| `event_type_accepted_values` | all `event_type` values are accepted |
| `freshness_available` | row count > 0 and max `ingest_timestamp` exists |
| `staging_table_empty` | staging table row count equals 0 |

Required fields checked:

| Column |
| --- |
| `event_id` |
| `event_timestamp` |
| `symbol` |
| `event_type` |
| `ingest_timestamp` |
| `bq_load_timestamp` |

---

## Unit Validation

Partial validation:

```sh
python3 -m py_compile scripts/run_bigquery_quality_checks.py
python3 -m py_compile tests/test_run_bigquery_quality_checks.py
uv run ruff check scripts/run_bigquery_quality_checks.py tests/test_run_bigquery_quality_checks.py
uv run pytest -q tests/test_run_bigquery_quality_checks.py
```

Observed result:

```text
All checks passed!
10 passed in 0.03s
```

Full repository validation before BigQuery execution:

```sh
uv run pytest -q
uv run ruff check .
test ! -f dbt/profiles.yml && echo "REPO_DBT_PROFILE_ABSENT=true"
```

Observed result:

```text
197 passed in 4.61s
All checks passed!
REPO_DBT_PROFILE_ABSENT=true
```

---

## Real BigQuery Execution

Command:

```sh
mkdir -p docs/evidence/bigquery-quality-checks

python3 scripts/run_bigquery_quality_checks.py \
  --report-output docs/evidence/bigquery-quality-checks/report.json
```

Report path:

```text
docs/evidence/bigquery-quality-checks/report.json
```

Execution mode:

| Item | Value |
| --- | --- |
| BigQuery mode | read-only |
| Cloud SQL started | No |
| Scheduler executed | No |
| BigQuery mutation | No |
| Secrets printed | No |

---

## BigQuery Quality Result

Overall status:

```text
ok
```

Summary:

| Check | Status | Observed |
| --- | --- | --- |
| `row_count_positive` | pass | 6120 |
| `required_columns_not_null` | pass | all required null counts = 0 |
| `event_id_unique` | pass | 0 duplicate event IDs |
| `event_type_accepted_values` | pass | 0 invalid event type rows |
| `freshness_available` | pass | max ingest timestamp available |
| `staging_table_empty` | pass | 0 staging rows |

Report excerpt:

```json
{
  "status": "ok",
  "project_id": "project-42987e01-2123-446b-ac7",
  "dataset": "rtdp_analytics",
  "table": "market_events_raw",
  "staging_table": "market_events_raw_staging",
  "accepted_event_types": [
    "trade"
  ],
  "failed_checks": []
}
```

---

## Observed Metrics

| Metric | Value |
| --- | --- |
| Raw table row count | 6120 |
| Required field nulls | 0 |
| Duplicate event IDs | 0 |
| Invalid event type rows | 0 |
| Max ingest timestamp | `2026-05-16 10:08:49.141452+00` |
| Staging table row count | 0 |

---

## Why This Matters

This closes a practical analytics-layer quality gap.

Before this branch, BigQuery data quality existed mainly through dbt tests and
manual validation evidence. This branch adds a lightweight executable quality gate
for the BigQuery analytical table itself.

For B2B evaluation, this demonstrates:

| Capability | Evidence |
| --- | --- |
| Data quality automation | executable read-only quality script |
| Warehouse validation | checks run directly against BigQuery |
| CI-compatible design | no cloud credentials needed for unit tests |
| Operational safety | no mutation, no scheduler run, no Cloud SQL start |
| Evidence-first delivery | JSON report committed under `docs/evidence` |

---

## What This Proves

The `market_events_raw` BigQuery table currently passes the defined baseline quality
checks:

- table is populated
- required fields are complete
- `event_id` is unique
- event types are within the expected contract
- freshness metadata is present
- staging table is empty after append/merge workflows

The quality check runner is deterministic, test-covered and safe to run as a
read-only validation step.

---

## What This Does Not Claim

This does not claim:

- continuous data quality monitoring
- alerting on quality failures
- scheduler-based execution of quality checks
- BigQuery mutation
- Cloud SQL validation
- dbt model execution
- production incident response automation

Those can be added in later branches if needed.

---

## Acceptance Matrix

| Criterion | Status |
| --- | --- |
| Read-only BigQuery quality script added | ACCEPTED |
| Unit tests added | ACCEPTED |
| Script compiles | ACCEPTED |
| Test file compiles | ACCEPTED |
| Ruff clean | ACCEPTED |
| New test file passes | ACCEPTED |
| Full test suite passes | ACCEPTED |
| `dbt/profiles.yml` absent | ACCEPTED |
| Real BigQuery quality report generated | ACCEPTED |
| 6/6 quality checks pass | ACCEPTED |
| Raw table row count positive | ACCEPTED |
| Required null count = 0 | ACCEPTED |
| Duplicate event IDs = 0 | ACCEPTED |
| Invalid event type rows = 0 | ACCEPTED |
| Staging table row count = 0 | ACCEPTED |
| Cloud SQL not started | ACCEPTED |
| Scheduler not executed | ACCEPTED |
| BigQuery not mutated | ACCEPTED |
| Secrets not printed | ACCEPTED |

---

## Final Conclusion

BigQuery baseline data quality checks are now implemented, unit-tested and validated
against the live analytical table in read-only mode.

Evidence status: **VALIDATED - READ-ONLY BIGQUERY QUALITY CHECKS**.