# SLO Quality Gates Alignment

**Status:** DRAFTED - QUALITY GATES ALIGNED TO EXISTING SLO MODEL
**Date:** 2026-05-17
**Branch:** docs/slo-quality-gates-alignment

---

## 1. Scope

This document aligns the BigQuery Quality Checks workflow with the existing SLO and
incident response model defined in `docs/SLO_AND_INCIDENT_RESPONSE.md`. It defines how
each quality check maps to an SLI, assigns severity classifications, and describes how
quality failures integrate into the existing incident response runbooks.

This document does not modify `docs/SLO_AND_INCIDENT_RESPONSE.md`. It supplements it with
BigQuery quality gate definitions that were not present when the original SLO document was
written.

Components in scope:

- `scripts/run_bigquery_quality_checks.py` — read-only BigQuery quality check runner
- `.github/workflows/bigquery-quality-checks.yml` — GitHub Actions workflow (manual + schedule)
- `rtdp_analytics.market_events_raw` — target BigQuery analytical table
- `rtdp_analytics.market_events_raw_staging` — staging table (expected empty after merge)

Components explicitly out of scope in this document:

- Cloud Monitoring alert policies (existing policies cover pipeline errors, not quality checks)
- Cloud Scheduler jobs (both schedulers are PAUSED by default)
- Cloud SQL (NEVER / STOPPED outside bounded validation windows)
- Terraform or IaC changes

---

## 2. Current Proven Quality Workflow State

The following is the proven state as of 2026-05-17. Claims are bounded to what the
evidence record supports.

```
Workflow:  BigQuery Quality Checks
Trigger:   workflow_dispatch + schedule (cron: "15 6 * * *")
YAML:      .github/workflows/bigquery-quality-checks.yml
```

### What is proven

| Item                                         | Evidence                                                        |
|----------------------------------------------|-----------------------------------------------------------------|
| Read-only quality script implemented          | docs/bigquery-quality-checks-evidence.md                        |
| 6/6 quality checks pass (local)              | docs/bigquery-quality-checks-evidence.md                        |
| Manual workflow_dispatch run succeeded        | docs/bigquery-quality-workflow-proof-evidence.md (Run 25982120058) |
| OIDC / Workload Identity auth works in CI    | docs/bigquery-quality-workflow-proof-evidence.md                |
| schedule trigger merged to main (PR #141)    | docs/bigquery-quality-schedule-enabled-evidence.md              |
| Post-merge manual run succeeded (Run 25984483471) | docs/bigquery-quality-schedule-enabled-evidence.md         |
| row_count: 6120; staging_table_empty: 0      | Run 25984483471 artifact ci-report.json                        |
| BigQuery not mutated; Cloud SQL not started  | All evidence; all SQL is read-only SELECT                       |

### What is NOT proven

| Item                                               | Status           |
|----------------------------------------------------|------------------|
| Real scheduled event execution                     | NOT YET PROVEN   |
| Schedule fires reliably at 06:15 UTC daily         | NOT YET PROVEN   |
| Quality failure alerting / notification            | NOT YET PROVEN   |
| Cloud Monitoring receives BigQuery quality metrics | NOT YET PROVEN   |

Real scheduled event execution is NOT YET PROVEN. No run with `event: schedule` has been
observed. Only `event: workflow_dispatch` runs are evidenced.

Quality failure alerting is NOT YET PROVEN. The existing Cloud Monitoring alert policies
(`RTDP Worker Message Error Alert`, `RTDP Silver Refresh Error Alert`) cover pipeline
errors. No alert policy monitors BigQuery quality check results.

---

## 3. Quality SLIs

Each quality check is defined here as a formal SLI — a measurable signal that can be
evaluated against a pass/fail threshold.

### 3.1 row_count_positive

| Field             | Value                                                                     |
|-------------------|---------------------------------------------------------------------------|
| Source            | `rtdp_analytics.market_events_raw` via `SELECT COUNT(*)`                 |
| Check name        | `row_count_positive`                                                      |
| Pass condition    | `row_count > 0`                                                           |
| Failure meaning   | The analytical table is empty; no events are available for analysis       |
| Suggested severity | P2 / High                                                                |
| Current evidence  | PASS — row_count=6120 (Run 25984483471, 2026-05-17T07:20:30Z)            |

A row count of zero is unexpected unless a full-table truncation occurred or the append
pipeline has not run. It does not indicate corrupted data, but it makes the table
analytically useless until resolved.

---

### 3.2 required_columns_not_null

| Field             | Value                                                                         |
|-------------------|-------------------------------------------------------------------------------|
| Source            | `rtdp_analytics.market_events_raw`; null counts per required column           |
| Check name        | `required_columns_not_null`                                                   |
| Columns checked   | `event_id`, `event_timestamp`, `symbol`, `event_type`, `ingest_timestamp`, `bq_load_timestamp` |
| Pass condition    | All required column null counts = 0                                           |
| Failure meaning   | One or more required fields are missing; data contract is violated            |
| Suggested severity | P1 / Critical                                                                |
| Current evidence  | PASS — all required null counts = 0 (Run 25984483471)                        |

Required column nulls at any scale indicate a data contract breach. Downstream analytics,
dbt models, and any consumer relying on these fields cannot be trusted. This is the most
severe quality failure class.

---

### 3.3 event_id_unique

| Field             | Value                                                                     |
|-------------------|---------------------------------------------------------------------------|
| Source            | `rtdp_analytics.market_events_raw`; `COUNT(*) - COUNT(DISTINCT event_id)` |
| Check name        | `event_id_unique`                                                         |
| Pass condition    | Duplicate event_id count = 0                                              |
| Failure meaning   | Duplicate events exist; aggregations and deduplication assumptions invalid |
| Suggested severity | P1 / Critical                                                            |
| Current evidence  | PASS — duplicate_event_ids=0 (Run 25984483471)                           |

Duplicate `event_id` values corrupt any analytical query that assumes event uniqueness.
Counts, sums, and joins that depend on a primary key contract are invalid until duplicates
are resolved. The MERGE-based append job is designed to be idempotent; duplicates indicate
a cursor or merge key failure.

---

### 3.4 event_type_accepted_values

| Field             | Value                                                                        |
|-------------------|------------------------------------------------------------------------------|
| Source            | `rtdp_analytics.market_events_raw`; count of rows where `event_type NOT IN accepted_set` |
| Check name        | `event_type_accepted_values`                                                 |
| Accepted set      | `["trade"]` (default; configurable via `--accepted-event-types`)             |
| Pass condition    | invalid_event_type_rows = 0                                                  |
| Failure meaning   | Unknown event types ingested; schema or contract mismatch upstream           |
| Suggested severity | P1 / Critical at scale; P2 / High for isolated rows                        |
| Current evidence  | PASS — invalid_event_type_rows=0 (Run 25984483471)                          |

Invalid event types indicate that an upstream producer is emitting events outside the
defined contract, or that the accepted values list is stale. At scale, this means that a
significant portion of the table may be misclassified.

---

### 3.5 freshness_available

| Field             | Value                                                                              |
|-------------------|------------------------------------------------------------------------------------|
| Source            | `rtdp_analytics.market_events_raw`; `MAX(ingest_timestamp)` and `COUNT(*)`        |
| Check name        | `freshness_available`                                                              |
| Pass condition    | row_count > 0 AND max_ingest_timestamp is not null                                |
| Failure meaning   | No data or no ingest timestamp; freshness cannot be assessed                       |
| Suggested severity | P2 / High                                                                         |
| Current evidence  | PASS — max_ingest_timestamp=2026-05-16 10:08:49.141452+00, row_count=6120 (Run 25984483471) |

This SLI is a necessary precondition for any freshness SLA enforcement. It does not
currently enforce an SLA window (e.g., data must be no older than N hours). That
enforcement belongs in `feat/bigquery-quality-thresholds`. The current check only confirms
that a freshness signal is present and readable.

---

### 3.6 staging_table_empty

| Field             | Value                                                                       |
|-------------------|-----------------------------------------------------------------------------|
| Source            | `rtdp_analytics.market_events_raw_staging`; `SELECT COUNT(*)`              |
| Check name        | `staging_table_empty`                                                       |
| Pass condition    | staging row count = 0                                                       |
| Failure meaning   | Staged data was not merged; possible partial append or aborted job          |
| Suggested severity | P2 / High                                                                  |
| Current evidence  | PASS — staging_table_empty=0 (Run 25984483471)                             |

A non-empty staging table after the append workflow means either the MERGE step did not
complete or a partial load was interrupted. Staged rows are not yet visible in the
analytical table and represent pending or orphaned data.

---

## 4. Quality Gates

A quality gate is a hard stop condition: if any SLI fails, the workflow reports overall
`status: failed` and the branch error budget is consumed. The current implementation
fails fast on the first failing check within a run.

```
Quality Gate Evaluation Order (as implemented):
  1. row_count_positive         --> fail => status: failed
  2. required_columns_not_null  --> fail => status: failed
  3. event_id_unique            --> fail => status: failed
  4. event_type_accepted_values --> fail => status: failed
  5. freshness_available        --> fail => status: failed
  6. staging_table_empty        --> fail => status: failed

All 6 pass => status: ok
```

The current gate definition is binary: all checks must pass. There are no warning-only
checks yet. Threshold-based checks (e.g. row_count_minimum > N, freshness < M hours) are
proposed in `feat/bigquery-quality-thresholds` and are not yet implemented.

---

## 5. Severity Model

The following extends the existing incident severity model from `docs/SLO_AND_INCIDENT_RESPONSE.md`
to cover BigQuery quality check failures.

```
+-----------+-----------------------------------------------------------------+
| Severity  | BigQuery Quality Gate Triggers                                  |
+-----------+-----------------------------------------------------------------+
| P1/SEV1   | required_columns_not_null FAIL                                  |
| Critical  | event_id_unique FAIL                                            |
|           | event_type_accepted_values FAIL at scale (> threshold)          |
|           |                                                                 |
|           | Rationale: data contract breach; analytical table cannot be     |
|           | trusted; downstream consumers, dbt models, and reporting are    |
|           | invalid until resolved                                          |
+-----------+-----------------------------------------------------------------+
| P2/SEV2   | row_count_positive FAIL (unexpected zero count)                 |
| High      | freshness_available FAIL (no ingest timestamp)                  |
|           | staging_table_empty FAIL (non-empty staging after merge)        |
|           | event_type_accepted_values FAIL (isolated rows, small count)    |
|           |                                                                 |
|           | Rationale: data is present but analytically incomplete or       |
|           | stale; usable with caveats but operational investigation needed |
+-----------+-----------------------------------------------------------------+
| P3/SEV3   | Volume anomaly (row count significantly above/below baseline)   |
| Medium    | Distribution drift (future; not yet implemented)                |
|           | Freshness SLA breach by threshold (future; not yet implemented) |
|           |                                                                 |
|           | Rationale: warning signals; data may still be technically       |
|           | valid but quality confidence is reduced; investigation required |
+-----------+-----------------------------------------------------------------+
| P4/SEV4   | Documentation or evidence freshness gap                         |
| Low       | Evidence not yet committed for a completed run                  |
|           | Quality checks not yet proven on scheduled event                |
+-----------+-----------------------------------------------------------------+
```

Note: P3/SEV3 quality signals are not yet implemented. They are defined here as the
target model for `feat/bigquery-quality-thresholds`.

---

## 6. Incident Response Mapping

### Quality Gate Failure Runbook

When the BigQuery Quality Checks workflow reports `status: failed`:

1. Identify the failing check from `failed_checks` in the artifact `ci-report.json`.
2. Assign severity per the table in section 5.
3. For P1/SEV1 failures (required_columns_not_null, event_id_unique,
   event_type_accepted_values at scale):
   - Stop any scheduled re-runs immediately.
   - Preserve the failing artifact `ci-report.json` as evidence before any retry.
   - Do not truncate or modify `market_events_raw` without a scoped branch and runbook.
   - Investigate the upstream append job (`rtdp-bigquery-append-job`) for the root cause.
   - Do not start Cloud SQL outside a bounded validation window.
4. For P2/SEV2 failures (row_count_positive, freshness_available, staging_table_empty):
   - Preserve the failing artifact.
   - Check the `rtdp-bigquery-append-job` execution logs in Cloud Logging.
   - Confirm whether the MERGE step completed cleanly (staging should be empty post-merge).
   - If staging is non-empty, investigate whether the job was interrupted mid-run.
5. Document the root cause and resolution on a dedicated branch before any fix is merged.

### Mapping to Existing SLO Runbooks

The existing runbooks in `docs/SLO_AND_INCIDENT_RESPONSE.md` cover pipeline components.
BigQuery quality failures map to these existing runbooks as follows:

| Quality Failure              | Related Existing Runbook                | Notes                                   |
|------------------------------|-----------------------------------------|-----------------------------------------|
| row_count_positive FAIL      | Silver Refresh Failure                  | Append job or scheduler may be the root cause |
| required_columns_not_null    | Worker Error Alert (upstream)           | Null fields indicate upstream contract breach |
| event_id_unique FAIL         | Worker Error Alert (upstream)           | Duplicate IDs indicate deduplication failure |
| event_type_accepted_values   | Worker Error Alert (upstream)           | Invalid types indicate upstream schema drift |
| freshness_available FAIL     | Silver Refresh Failure                  | Append job has not run or failed silently |
| staging_table_empty FAIL     | Silver Refresh Failure                  | MERGE step did not complete cleanly     |

The existing runbooks do not include steps for inspecting BigQuery quality artifacts.
Those steps are defined in the Quality Gate Failure Runbook above and should be merged
into `docs/SLO_AND_INCIDENT_RESPONSE.md` in a future update.

---

## 7. Alerting Gap

Quality failure alerting is NOT YET PROVEN.

The existing Cloud Monitoring alert policies are:

| Policy                            | Condition                           | Scope                      |
|-----------------------------------|-------------------------------------|----------------------------|
| RTDP Worker Message Error Alert   | `worker_message_error_count > 0`    | Cloud Run revision          |
| RTDP Silver Refresh Error Alert   | `silver_refresh_error_count > 0`    | Cloud Run job               |

Neither policy monitors BigQuery quality check results. There is no proven path from a
failing `status: failed` quality report to a Cloud Monitoring alert, email notification,
or any other notification channel.

Cloud Monitoring does not receive BigQuery quality check metrics. The quality workflow
writes a JSON artifact to GitHub Actions; it does not push metrics to Cloud Monitoring.

The alerting gap is classified as P0 in the gap register (`docs/gaps-resolved-vs-remaining-report.md`).
The target branch is `feat/quality-alert-notification-proof`.

---

## 8. Scheduled Execution Gap

Real scheduled event execution is NOT YET PROVEN.

The workflow YAML on `main` includes:

```yaml
"on":
  workflow_dispatch:
  schedule:
    - cron: "15 6 * * *"
```

The `schedule` block was added by PR #141 and is present on `main`. A post-merge manual
`workflow_dispatch` run (Run ID: 25984483471) succeeded, confirming that both triggers
coexist without conflict.

However, no run with `event: schedule` has been observed. The cron expression (`15 6 * * *`)
targets 06:15 UTC daily. GitHub Actions may delay or skip scheduled runs during low-activity
periods or under infrastructure pressure.

The first real `event: schedule` execution should be captured in:

```
docs/bigquery-quality-scheduled-run-evidence.md
```

That document should include the GitHub Actions run URL, the `event` field confirming
`schedule`, the artifact `ci-report.json`, and the `generated_at_utc` timestamp.

Until that evidence exists, scheduled execution must not be claimed as proven.

---

## 9. Evidence Map

| Evidence Document                                     | What It Proves                                                        |
|-------------------------------------------------------|-----------------------------------------------------------------------|
| docs/bigquery-quality-checks-evidence.md              | Local read-only quality script; 6/6 checks pass; row_count=6120      |
| docs/bigquery-quality-workflow-proof-evidence.md      | Manual workflow Run 25982120058; OIDC auth; artifact confirmed        |
| docs/bigquery-quality-schedule-enabled-evidence.md    | schedule trigger merged (PR #141); post-merge Run 25984483471 passed |
| docs/gaps-resolved-vs-remaining-report.md             | Gap register; scheduled execution and alerting gaps documented        |
| docs/SLO_AND_INCIDENT_RESPONSE.md                     | Baseline SLO/SLI targets; incident runbooks; existing alert policies  |
| docs/cloud-alert-policies-evidence.md                 | Two Cloud Monitoring alert policies; not connected to quality checks  |
| docs/cloud-monitoring-dashboard-evidence.md           | 4-panel dashboard; pipeline and refresh metrics; no quality panels    |
| docs/cloud-observability-evidence.md                  | Logs-based metrics; Cloud Monitoring timeSeries datapoints            |

Key proof anchor: Post-merge manual run Run ID 25984483471

```
event:              workflow_dispatch
conclusion:         success
artifact status:    ok
checks passed:      6/6
row_count:          6120
staging_table_empty: 0
generated_at_utc:   2026-05-17T07:20:30.420792+00:00
Cloud SQL started:  no
Scheduler executed: no
BigQuery mutated:   no
```

---

## 10. Acceptance Matrix

| Criterion                                                        | Status      |
|------------------------------------------------------------------|-------------|
| row_count_positive SLI defined with source and severity          | ACCEPTED    |
| required_columns_not_null SLI defined with source and severity   | ACCEPTED    |
| event_id_unique SLI defined with source and severity             | ACCEPTED    |
| event_type_accepted_values SLI defined with source and severity  | ACCEPTED    |
| freshness_available SLI defined with source and severity         | ACCEPTED    |
| staging_table_empty SLI defined with source and severity         | ACCEPTED    |
| Quality gate evaluation order documented                         | ACCEPTED    |
| Severity model extended from existing SLO model                  | ACCEPTED    |
| Quality failure runbook defined                                  | ACCEPTED    |
| Mapping to existing runbooks documented                          | ACCEPTED    |
| Alerting gap explicitly stated as NOT YET PROVEN                 | ACCEPTED    |
| Scheduled execution gap explicitly stated as NOT YET PROVEN      | ACCEPTED    |
| Cloud Monitoring not claimed to receive quality metrics          | ACCEPTED    |
| Cloud SQL not started claim preserved                            | ACCEPTED    |
| Cloud Scheduler not executed claim preserved                     | ACCEPTED    |
| BigQuery not mutated claim preserved                             | ACCEPTED    |
| SLO_AND_INCIDENT_RESPONSE.md not modified                        | ACCEPTED    |
| No overclaim of production-grade operation                       | ACCEPTED    |
| Evidence map links to all relevant evidence documents            | ACCEPTED    |
| Run ID 25984483471 cited as primary evidence anchor              | ACCEPTED    |

---

## 11. Next Implementation Branches

The following branches are recommended to close the remaining gaps identified in this
document.

```
1. docs/index-slo-quality-gates-alignment
   Purpose: Index this document in docs/EVIDENCE_INDEX.md
   Scope:   docs-only; add one entry to EVIDENCE_INDEX.md

2. feat/bigquery-quality-thresholds
   Purpose: Add volume threshold checks, freshness SLA enforcement (e.g. max age in
            hours), and distribution anomaly detection to the quality script
   Scope:   scripts/run_bigquery_quality_checks.py + new unit tests
   Outcome: P3/SEV3 quality SLIs become provable, not just defined

3. feat/quality-alert-notification-proof
   Purpose: Prove that a quality check failure triggers a notification (Cloud Monitoring
            policy, GitHub Actions workflow failure notification, or email channel)
   Scope:   Alerting configuration + end-to-end failure test evidence
   Outcome: Closes the alerting gap; quality failure alerting becomes NOT YET PROVEN -> PROVEN

4. docs/bigquery-quality-scheduled-run-evidence
   Purpose: Capture the first real event:schedule run with generated_at_utc evidence
   Scope:   docs-only evidence document; written once a scheduled event fires
   Prerequisite: Must observe a GitHub Actions run with event: schedule (not workflow_dispatch)
   Outcome: Closes the scheduled execution gap
```

---

## 12. Final Conclusion

The BigQuery Quality Checks workflow is now aligned with the existing SLO and incident
response model. Six quality SLIs are formally defined — `row_count_positive`,
`required_columns_not_null`, `event_id_unique`, `event_type_accepted_values`,
`freshness_available`, and `staging_table_empty` — with severity classifications,
pass conditions, failure meanings, and current evidence status.

The quality gate is proven in manual `workflow_dispatch` mode. All 6 checks pass against
the production `rtdp_analytics.market_events_raw` table as of Run ID 25984483471
(2026-05-17T07:20:30Z).

Two gaps remain explicit and underclaimed:

- Real scheduled event execution is NOT YET PROVEN.
- Quality failure alerting is NOT YET PROVEN.

The recommended next step is `feat/quality-alert-notification-proof` or capturing the
first `event: schedule` run in `docs/bigquery-quality-scheduled-run-evidence.md` —
whichever fires first. No production-grade operation is claimed.
