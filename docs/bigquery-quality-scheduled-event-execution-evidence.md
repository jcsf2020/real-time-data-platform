# BigQuery Quality Checks - Scheduled Event Execution Evidence

## Status

```text
VALIDATED - SCHEDULED EVENT EXECUTION PROVEN
Date: 2026-05-19
Branch: docs/bigquery-quality-scheduled-event-execution-evidence
```

## Scope

This document proves that the **BigQuery Quality Checks** workflow executes on a cron schedule, completes successfully, and uploads a quality report artifact. It does not cover freshness_age_hours metric emission (proven separately in [docs/bigquery-quality-freshness-age-hours-metric-evidence.md](bigquery-quality-freshness-age-hours-metric-evidence.md)), Incident creation, or notification delivery.

## Workflow Schedule Configuration

**File:** [.github/workflows/bigquery-quality-checks.yml](.github/workflows/bigquery-quality-checks.yml)

The workflow declares a `schedule` trigger:

```yaml
on:
  schedule:
    - cron: "15 6 * * *"
```

Fires daily at **06:15 UTC**. The `schedule` event type is the sole trigger proven in this document.

## Scheduled Run Evidence

| Field | Value |
| --- | --- |
| Run ID | `26028523804` |
| Event | `schedule` |
| Status | `completed` |
| Conclusion | `success` |
| Created at | `2026-05-18T10:41:30Z` |
| Updated at | `2026-05-18T10:42:18Z` |
| URL | <https://github.com/jcsf2020/real-time-data-platform/actions/runs/26028523804> |

## Scheduled Run Log Evidence

- **Commit SHA checked out:** `dce441d3040ac8fd72a204eaa2e4775c42d06169` (main branch)
- **Google Cloud auth:** Workload Identity Federation
- **Service account:** `rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com`
- **Quality command invoked with scheduled defaults:**
  - `min_row_count=1`
  - `freshness_max_age_hours=0`

## Quality Report Evidence

Artifact uploaded at run completion:

| Field | Value |
| --- | --- |
| Artifact name | `bigquery-quality-checks-report` |
| Artifact ID | `7055640475` |
| Artifact URL | <https://github.com/jcsf2020/real-time-data-platform/actions/runs/26028523804/artifacts/7055640475> |

**Report contents:**

```json
{
  "status": "ok",
  "failed_checks": [],
  "dataset": "rtdp_analytics",
  "table": "market_events_raw",
  "staging_table": "market_events_raw_staging",
  "row_count": 6120,
  "generated_at_utc": "2026-05-18T10:42:13.513728+00:00"
}
```

**Individual check results:**

| Check | Result | Detail |
| --- | --- | --- |
| `row_count_positive` | pass | observed 6120 |
| `required_columns_not_null` | pass | all required null counts = 0 |
| `event_id_unique` | pass | duplicate_event_ids = 0 |
| `event_type_accepted_values` | pass | invalid_event_type_rows = 0 |
| `freshness_available` | pass | max_ingest_timestamp = 2026-05-16 10:08:49.141452+00 |
| `staging_table_empty` | pass | staging_row_count = 0 |
| `row_count_minimum` | pass | 6120 >= 1 |

> **Note:** `freshness_age_hours` metric emission is proven separately in [docs/bigquery-quality-freshness-age-hours-metric-evidence.md](bigquery-quality-freshness-age-hours-metric-evidence.md). Visibility of the **Push BigQuery quality metrics to Cloud Monitoring** step result is not confirmed in this run's evidence and is not claimed here.

## Safety Notes

| Assertion | Result |
| --- | --- |
| BigQuery not mutated | yes - scheduled quality checks used read-only SQL |
| Cloud SQL not started | yes - not involved in this scheduled GitHub Actions run |
| Cloud Scheduler not executed | yes - GitHub Actions schedule only |
| Terraform not changed | yes - docs-only evidence branch |
| Terraform apply not executed | yes - no infrastructure mutation |
| no secrets printed | yes - Workload Identity Federation used; no key material printed |
| Artifact preserved | yes - artifact ID 7055640475 uploaded successfully |


## Conclusion

Run `26028523804` demonstrates end-to-end scheduled execution of the BigQuery Quality Checks workflow: the `schedule` trigger fired, the workflow authenticated to Google Cloud via Workload Identity Federation, ran quality checks against `rtdp_analytics.market_events_raw`, and uploaded a passing quality report artifact. All seven quality checks passed with `status: ok` and `failed_checks: []`.

## Remaining Gaps

- Incident creation NOT YET PROVEN.
- Email notification delivery NOT YET PROVEN.
- GitHub notification bell delivery NOT YET PROVEN.
- Dataflow not implemented.
