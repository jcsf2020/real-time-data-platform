# Quality Alert Notification Proof Plan

**Status:** PLANNED - ALERT NOTIFICATION PROOF NOT YET EXECUTED
**Date:** 2026-05-17
**Branch:** docs/quality-alert-notification-proof-plan

---

## 1. Scope

This document defines the safest implementation path to prove that a BigQuery quality check
failure creates an observable notification signal. It is a plan only — no code has been
changed, no workflow has been executed, and no GCP resources have been modified.

Components in scope:

- `.github/workflows/bigquery-quality-checks.yml` — existing GitHub Actions workflow
- `scripts/run_bigquery_quality_checks.py` — existing read-only quality check runner
- GitHub Actions workflow failure notification surface (email / GitHub notification settings)

Components explicitly out of scope in this plan:

- Cloud Monitoring alert policies — existing policies cover pipeline errors, not quality
  check results; wiring quality metrics to Cloud Monitoring is a future step
- Cloud Scheduler — both schedulers remain PAUSED; no Cloud Scheduler jobs will be executed
- Cloud SQL — remains NEVER/STOPPED; no Cloud SQL will be started
- BigQuery data mutation — all SQL is read-only SELECT; no INSERT, UPDATE, DELETE, CREATE,
  or DROP will be issued

---

## 2. Current State

### What is proven as of 2026-05-17

| Item | Evidence |
|---|---|
| Read-only quality script (8 checks) | docs/bigquery-quality-thresholds-evidence.md |
| Manual workflow_dispatch run succeeded | docs/bigquery-quality-workflow-proof-evidence.md (Run 25982120058) |
| Post-merge manual run succeeded (Run 25984483471) | docs/bigquery-quality-schedule-enabled-evidence.md |
| schedule trigger merged to main (PR #141) | docs/bigquery-quality-schedule-enabled-evidence.md |
| row_count_minimum live-proven: 6120 >= 6000 | docs/bigquery-quality-thresholds-evidence.md |
| --min-row-count and --freshness-max-age-hours flags implemented | docs/bigquery-quality-thresholds-evidence.md |
| Artifact report uploaded via `if: always()` | .github/workflows/bigquery-quality-checks.yml:41 |
| BigQuery not mutated; Cloud SQL not started | All evidence; all SQL is read-only SELECT |

### What is NOT proven as of 2026-05-17

| Item | Status |
|---|---|
| Real scheduled event execution | NOT YET PROVEN |
| Quality failure alerting / notification | NOT YET PROVEN |
| Cloud Monitoring receives BigQuery quality metrics | NOT YET PROVEN |
| freshness_max_age_hours live pass/fail | NOT YET PROVEN (unit-tested only) |

Real scheduled event execution is NOT YET PROVEN. No run with `event: schedule` has been
observed. Only `event: workflow_dispatch` runs are evidenced.

Quality failure alerting is NOT YET PROVEN. No end-to-end path from a failing quality
check to a delivered notification has been demonstrated.

---

## 3. Alerting Gap

Quality failure alerting is NOT YET PROVEN.

The existing Cloud Monitoring alert policies are:

| Policy | Condition | Scope |
|---|---|---|
| RTDP Worker Message Error Alert | worker_message_error_count > 0 | Cloud Run revision |
| RTDP Silver Refresh Error Alert | silver_refresh_error_count > 0 | Cloud Run job |

Neither policy monitors BigQuery quality check results.

Cloud Monitoring does not currently receive BigQuery quality metrics. The quality workflow
writes a JSON artifact to GitHub Actions. It does not push metrics to Cloud Monitoring.
There is no proven path from a `status: failed` quality report to a Cloud Monitoring alert,
email notification, or any other notification channel.

The alerting gap is classified as P0 in `docs/gaps-resolved-vs-remaining-report.md`.

---

## 4. Recommended Proof Path

The first proof should be GitHub Actions failure notification surface, not Cloud Monitoring.

Rationale:

- The quality workflow already runs in GitHub Actions with OIDC auth proven.
- `scripts/run_bigquery_quality_checks.py` already exits non-zero when any check fails
  (`return 0 if report["status"] == "ok" else 1` at line 404).
- The artifact upload step already uses `if: always()` so the report is preserved on failure.
- GitHub Actions sends workflow failure notifications via email or GitHub notification
  settings by default — no new infrastructure is required.
- BigQuery remains read-only. No mutation is needed to trigger a failure.
- Cloud SQL must not be started. Cloud Scheduler jobs must not be executed.

The controlled failure is achieved by passing an intentionally impossible `--min-row-count`
threshold via a `workflow_dispatch` input, such as `999999999`. The real table has 6120
rows. A threshold of 999999999 guarantees `row_count_minimum` fails regardless of table
state.

Later optional step — map GitHub Actions failure to Cloud Monitoring or an external
notifier. Do not implement this now; only plan it.

---

## 5. Proposed Workflow Input Design

To support controlled failure triggering, a future update to
`.github/workflows/bigquery-quality-checks.yml` should add `workflow_dispatch` inputs:

```yaml
"on":
  workflow_dispatch:
    inputs:
      min_row_count:
        description: "Minimum row count threshold (default 1). Set to 999999999 for controlled failure."
        required: false
        default: "1"
      freshness_max_age_hours:
        description: "Max data age in hours. Set to 0 to skip (default). Set to 0.001 for controlled freshness failure."
        required: false
        default: "0"
  schedule:
    - cron: "15 6 * * *"
```

The `Run BigQuery quality checks` step would consume the inputs:

```yaml
- name: Run BigQuery quality checks
  run: |
    python3 scripts/run_bigquery_quality_checks.py \
      --min-row-count ${{ inputs.min_row_count || '1' }} \
      --freshness-max-age-hours ${{ inputs.freshness_max_age_hours || '0' }} \
      --report-output docs/evidence/bigquery-quality-checks/ci-report.json
```

When triggered by `schedule`, both inputs default to their safe values (`1` and `0`),
preserving the existing daily pass behaviour. When triggered by `workflow_dispatch` with
`min_row_count: 999999999`, the check fails deterministically.

This design change does not alter the existing `schedule` path behaviour. It does not
mutate BigQuery. It does not start Cloud SQL. It does not execute Cloud Scheduler jobs.

Implementation belongs in a future branch: `feat/quality-alert-notification-proof`.

---

## 6. Controlled Failure Scenario

The proof execution, once implemented, should follow this sequence:

```
Step 1  Confirm current main baseline
        uv run pytest -q        --> all tests pass
        uv run ruff check .     --> clean
        git status              --> no uncommitted workflow changes

Step 2  Trigger workflow_dispatch via GitHub Actions UI or gh CLI
        Workflow: BigQuery Quality Checks
        Input:    min_row_count = 999999999
        Input:    freshness_max_age_hours = 0 (skip)

Step 3  Observe workflow execution
        Expected: "Run BigQuery quality checks" step exits non-zero
        Expected: workflow conclusion = failure
        Expected: artifact still uploaded (if: always())
        Expected: ci-report.json contains:
                    "status": "error"
                    "failed_checks": ["row_count_minimum"]
                    row_count_minimum.observed = 6120
                    row_count_minimum.expected = "row_count >= 999999999"

Step 4  Capture GitHub notification
        Expected: GitHub sends workflow failure notification email
                  to repository owner (jcsf2020@gmail.com) via
                  GitHub notification settings, or notification
                  appears in GitHub notification bell

Step 5  Document evidence
        New file: docs/bigquery-quality-alert-notification-proof-evidence.md
        Contents: Run ID, conclusion=failure, artifact ci-report.json,
                  screenshot or log of GitHub failure notification,
                  generated_at_utc, safety assertions
```

The threshold value 999999999 is the controlled failure anchor. It is
intentionally impossible given the known table size (~6120 rows). No
data mutation, no Cloud SQL start, and no Cloud Scheduler execution is
required to trigger this failure.

---

## 7. Expected Evidence Artifacts

When the controlled failure scenario is executed, the following artifacts are expected:

| Artifact | Expected content |
|---|---|
| GitHub Actions run URL | Workflow: BigQuery Quality Checks; conclusion: failure |
| ci-report.json (from artifact upload) | status: error; failed_checks: ["row_count_minimum"]; row_count_minimum.observed: 6120; row_count_minimum.expected: row_count >= 999999999 |
| GitHub notification (email or bell) | Workflow failure notification for BigQuery Quality Checks run |
| docs/bigquery-quality-alert-notification-proof-evidence.md | Evidence document capturing all of the above with timestamps |

The artifact upload is guaranteed to run because the step uses `if: always()` in the
current workflow YAML (line 41). This means `ci-report.json` is available for download
even when the workflow exits non-zero.

---

## 8. Safety Assertions

The following assertions must hold throughout the proof execution:

| Assertion | Constraint |
|---|---|
| BigQuery must not be mutated | All SQL is read-only SELECT; no INSERT, UPDATE, DELETE, CREATE, or DROP will be issued |
| Cloud SQL must not be started | Cloud SQL remains NEVER/STOPPED; no connection attempt will be made |
| Cloud Scheduler jobs must not be executed | Both schedulers remain PAUSED; Cloud Scheduler jobs must not be executed |
| Real table data must not be altered | The controlled failure uses an impossible threshold against live read-only data |
| Existing passing checks must not be masked | The proof only adds a failing threshold check; the 6 baseline checks pass as before |
| No secrets printed in logs or artifacts | The script does not log credentials or auth tokens |
| Workflow_dispatch only; no schedule trigger | The controlled failure run must be triggered manually, not by a cron event |

These assertions are satisfied by design: the failure is produced by an impossible numeric
threshold, not by altering any data or infrastructure state.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| GitHub Actions does not send failure notification | Low | Verify repository notification settings are enabled before triggering the controlled failure run |
| Workflow YAML input change breaks the schedule path | Low | Default input values must preserve the existing daily pass behaviour; test with a post-change workflow_dispatch run before using 999999999 |
| freshness_max_age_hours live failure reveals stale data unintentionally | Medium | Do not use freshness_max_age_hours as the controlled failure vector; use min_row_count only |
| Evidence document written without a delivered notification captured | Medium | Do not close the alerting gap until an actual notification delivery (email or GitHub bell) is documented with a timestamp or screenshot |
| GitHub Actions skips or delays the controlled failure run | Low | Trigger only via workflow_dispatch, not schedule; manual dispatch is immediate |
| Threshold of 999999999 becomes passable if table grows dramatically | None | Table has 6120 rows; a threshold 163,000x the current count will not be crossed accidentally |

---

## 10. Acceptance Criteria

The alerting gap is NOT closed until all of the following criteria are met:

| Criterion | Required evidence |
|---|---|
| workflow_dispatch triggered with min_row_count = 999999999 | GitHub Actions run URL with event: workflow_dispatch |
| Workflow conclusion = failure | Run detail showing conclusion: failure |
| row_count_minimum check fails in ci-report.json | Artifact ci-report.json with failed_checks containing row_count_minimum |
| Artifact still uploaded despite workflow failure | ci-report.json downloadable from failed run |
| GitHub notification delivered | Email received at jcsf2020@gmail.com OR GitHub notification bell entry OR screenshot of notification |
| BigQuery not mutated | Confirmed in evidence document safety assertions |
| Cloud SQL not started | Confirmed in evidence document safety assertions |
| Cloud Scheduler not executed | Confirmed in evidence document safety assertions |
| Evidence document committed | docs/bigquery-quality-alert-notification-proof-evidence.md present on main |

Until all criteria are met: Quality failure alerting is NOT YET PROVEN.

---

## 11. Future Implementation Branches

The following branches are recommended after this plan is approved:

```
1. feat/quality-alert-notification-proof
   Purpose: Implement the workflow_dispatch inputs described in section 5
            and execute the controlled failure scenario from section 6
   Scope:   .github/workflows/bigquery-quality-checks.yml (inputs only)
            docs/bigquery-quality-alert-notification-proof-evidence.md (new)
   Outcome: Quality failure alerting becomes NOT YET PROVEN -> PROVEN at
            GitHub Actions notification surface level

2. feat/bigquery-quality-cloud-monitoring-metrics
   Purpose: Push quality check results as custom metrics to Cloud Monitoring
            after each run, so that alert policies can fire on quality failures
   Scope:   scripts/run_bigquery_quality_checks.py or a separate push script
            New Cloud Monitoring custom metric descriptors
            New or updated alert policy in Terraform
   Prerequisite: feat/quality-alert-notification-proof must complete first
   Outcome: Cloud Monitoring receives BigQuery quality metrics (closes the
            deeper observability gap documented in docs/slo-quality-gates-alignment.md)

3. docs/bigquery-quality-scheduled-run-evidence
   Purpose: Capture the first real event:schedule run
   Scope:   docs-only; written once a scheduled GitHub Actions event fires
   Prerequisite: schedule trigger already present on main; wait for first
                 natural cron fire and confirm event: schedule (not workflow_dispatch)
   Outcome: Real scheduled event execution becomes NOT YET PROVEN -> PROVEN
```

---

## 12. Final Conclusion

Quality failure alerting is NOT YET PROVEN. Real scheduled event execution is NOT YET PROVEN.
Cloud Monitoring does not currently receive BigQuery quality metrics.

The safest path to prove the notification surface is a controlled `workflow_dispatch` run
with `--min-row-count 999999999`. This produces a deterministic `row_count_minimum` failure
without mutating BigQuery, without starting Cloud SQL, and without executing Cloud Scheduler
jobs. GitHub Actions records `conclusion: failure`. The artifact upload (`if: always()`)
preserves `ci-report.json`. GitHub delivers a workflow failure notification by email or
notification bell.

This is the first proof layer: GitHub Actions failure notification surface. It does not
require Cloud Monitoring, custom metrics, or external notification channels. It proves the
signal exists and is observable. Cloud Monitoring integration is a subsequent, separate step.

The plan is ready to execute. Implementation begins on `feat/quality-alert-notification-proof`.
No code, workflow, Terraform, or GCP state has been modified by this planning document.
