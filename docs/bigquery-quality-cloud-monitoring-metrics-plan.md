# BigQuery Quality Cloud Monitoring Metrics Plan

**Status:** PLANNED - QUALITY METRICS NOT YET IMPLEMENTED
**Date:** 2026-05-18
**Branch:** `docs/bigquery-quality-cloud-monitoring-metrics-plan`

---

## 1. Scope

This document is a planning document only. It describes the intended design for emitting
BigQuery quality check results as custom metrics to Google Cloud Monitoring. No code, tests,
workflows, Terraform, or dbt files are modified by this branch.

The plan targets `scripts/run_bigquery_quality_checks.py` and
`.github/workflows/bigquery-quality-checks.yml` as the integration points. A new separate
script `scripts/push_bigquery_quality_metrics.py` would be introduced in a future
implementation branch.

Cloud Monitoring quality metrics are NOT implemented. Cloud Monitoring alerting is NOT
proven. This document plans the path to close those gaps.

---

## 2. Current Proven State

The following capabilities are proven and evidenced as of 2026-05-18.

| Capability | Evidence | Status |
|---|---|---|
| Read-only BigQuery quality script | `docs/bigquery-quality-checks-evidence.md` | PROVEN |
| 6 baseline quality checks pass | `docs/bigquery-quality-checks-evidence.md` | PROVEN |
| `row_count_minimum` check (always included) | `docs/bigquery-quality-thresholds-evidence.md` | PROVEN |
| `freshness_max_age_hours` check (unit-tested only) | `docs/bigquery-quality-thresholds-evidence.md` | UNIT-PROVEN |
| Manual `workflow_dispatch` run (Run ID 25982120058) | `docs/bigquery-quality-workflow-proof-evidence.md` | PROVEN |
| Schedule cron `15 6 * * *` present on `main` | `docs/bigquery-quality-schedule-enabled-evidence.md` | PROVEN (cron present) |
| `workflow_dispatch` inputs wired end-to-end | `docs/bigquery-quality-alert-notification-proof-evidence.md` | PROVEN |
| Controlled failure run (Run ID 26007909020) | `docs/bigquery-quality-alert-notification-proof-evidence.md` | PROVEN |
| GitHub Actions UI failure surface observable | `docs/bigquery-quality-alert-notification-proof-evidence.md` | PROVEN |
| Artifact preserved despite workflow failure (`if: always()`) | `docs/bigquery-quality-alert-notification-proof-evidence.md` | PROVEN |
| `freshness_max_age_hours` live failure (Run ID 26020167461) | `docs/bigquery-freshness-live-validation-evidence.md` | PROVEN |
| JSON report written to `docs/evidence/bigquery-quality-checks/ci-report.json` | Multiple evidence docs | PROVEN |
| 210 tests passing | `docs/bigquery-quality-thresholds-evidence.md` | PROVEN |
| Ruff clean | `docs/bigquery-quality-thresholds-evidence.md` | PROVEN |
| 4 logs-based metrics with datapoints in Cloud Monitoring | `docs/cloud-monitoring-dashboard-evidence.md` | PROVEN |
| 4-panel RTDP Pipeline Overview dashboard | `docs/cloud-monitoring-dashboard-evidence.md` | PROVEN |
| 2 alert policies enabled (worker error, silver refresh error) | `docs/cloud-alert-policies-evidence.md` | PROVEN |
| Email notification channel attached to both alert policies | `docs/notification-channels-evidence.md` | PROVEN |

### Safety Assertions (All Proven)

| Assertion | State |
|---|---|
| BigQuery not mutated | All quality checks are read-only SELECT statements only |
| Cloud SQL not started | Confirmed across all quality workflow run IDs |
| Cloud Scheduler not executed | Confirmed across all quality workflow run IDs |
| no secrets printed | Confirmed in all evidence runs |

---

## 3. Gap Being Closed

The following gaps are the direct subject of this plan.

| Gap | Current State |
|---|---|
| Cloud Monitoring quality metrics | Cloud Monitoring quality metrics are NOT implemented. No custom time series exists for BigQuery quality check results. |
| Cloud Monitoring alerting on quality failure | Cloud Monitoring alerting is NOT proven. The existing alert policies cover pipeline errors only (`worker_message_error_count`, `silver_refresh_error_count`). No alert policy monitors quality check outcome. |
| Real scheduled event execution | real scheduled event execution is NOT YET PROVEN. The cron `15 6 * * *` trigger is present on `main` but no GitHub Actions run triggered by a real `event: schedule` has been observed. |

The existing observability gap (BigQuery quality signals not visible in Cloud Monitoring)
was first identified in the gaps-resolved-vs-remaining report as Gap #3 (P1, high B2B value).
Closing this gap requires:

1. A new Python script that reads the JSON report and pushes metrics to Cloud Monitoring.
2. A workflow step that runs this script after the quality check step.
3. IAM permission (`roles/monitoring.metricWriter`) on the GitHub Actions service account.
4. Optionally, a new Terraform-managed alert policy on `failed_checks_count > 0`.

---

## 4. Target Metric Design

Five custom metrics are planned for emission after each BigQuery quality workflow run.

### 4.1 `custom.googleapis.com/rtdp/bigquery_quality/status`

| Property | Value |
|---|---|
| Full metric type | `custom.googleapis.com/rtdp/bigquery_quality/status` |
| Kind | GAUGE |
| Value type | INT64 |
| Unit | 1 |
| Meaning | 1 = overall status ok; 0 = overall status error |
| Source | `report["status"] == "ok"` → 1, else 0 |
| Labels | None required at this level |

This is the primary health signal for the BigQuery quality workflow. An alert policy
condition of `status == 0` would fire on any quality failure run.

### 4.2 `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count`

| Property | Value |
|---|---|
| Full metric type | `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count` |
| Kind | GAUGE |
| Value type | INT64 |
| Unit | 1 |
| Meaning | Number of failed checks in the current run |
| Source | `len(report["failed_checks"])` |
| Labels | None required at this level |

This is the most actionable alert condition. An alert policy condition of
`failed_checks_count > 0` directly represents at least one quality gate failing.

### 4.3 `custom.googleapis.com/rtdp/bigquery_quality/check_pass`

| Property | Value |
|---|---|
| Full metric type | `custom.googleapis.com/rtdp/bigquery_quality/check_pass` |
| Kind | GAUGE |
| Value type | INT64 |
| Unit | 1 |
| Meaning | 1 = individual check passed; 0 = individual check failed |
| Source | Per-check result from `report["checks"]` |
| Labels | `check_name` (string) — e.g. `row_count_minimum`, `freshness_max_age_hours` |

This enables per-check visibility in Cloud Monitoring. Each check emits its own
time series with `check_name` as a label, allowing dashboard panels to show
individual check health over time.

### 4.4 `custom.googleapis.com/rtdp/bigquery_quality/row_count`

| Property | Value |
|---|---|
| Full metric type | `custom.googleapis.com/rtdp/bigquery_quality/row_count` |
| Kind | GAUGE |
| Value type | INT64 |
| Unit | 1 |
| Meaning | Observed `market_events_raw` row count when available |
| Source | `observed` field of `row_count_positive` or `row_count_minimum` check |
| Labels | None required |

This provides a longitudinal row count signal in Cloud Monitoring, enabling trend
visualization over time without re-querying BigQuery.

### 4.5 `custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours`

| Property | Value |
|---|---|
| Full metric type | `custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours` |
| Kind | GAUGE |
| Value type | DOUBLE |
| Unit | h |
| Meaning | Observed `age_hours` from the `freshness_max_age_hours` check when executed |
| Source | `check["observed"]["age_hours"]` when `check_name == "freshness_max_age_hours"` |
| Conditional | Emitted only when `freshness_max_age_hours` check is present in the report |
| Labels | None required |

This is emitted only when the `--freshness-max-age-hours` flag is supplied and the
check runs. When the check is skipped (default behavior), no data point is written.

---

## 5. Recommended Implementation Architecture

### Option A (Preferred): Separate Metric Emission Script

A new dedicated script `scripts/push_bigquery_quality_metrics.py` reads the JSON report
generated by `scripts/run_bigquery_quality_checks.py` and pushes custom metrics to Cloud
Monitoring.

**Advantages:**
- Preserves the read-only contract of `scripts/run_bigquery_quality_checks.py`. The quality
  checker remains responsible only for running checks and producing the report.
- Single responsibility: `scripts/push_bigquery_quality_metrics.py` is responsible only for
  observability signal emission.
- The metric emission step can fail independently without masking the original quality check
  outcome (workflow failure from the quality step is not overridden).
- Testable in isolation: unit tests for report parsing and metric payload construction do not
  require a live BigQuery connection.
- Easier to disable or replace the metric emission step without touching the quality script.

**Dependency approach — prefer `gcloud` first:**
- If the `gcloud monitoring` CLI supports writing time series without additional Python
  packages, use it to avoid any new `pip install` dependency in the workflow.
- If the Cloud Monitoring Python client (`google-cloud-monitoring`) is required, document
  the dependency impact (package size, install time, version pin) before implementation.

### Option B (Not Preferred): Extend Quality Checks Script

Add an optional `--push-monitoring-metrics` flag to
`scripts/run_bigquery_quality_checks.py`.

**Disadvantages:**
- Couples observability emission to the read-only quality checker.
- Increases the blast radius of changes to the quality script.
- Requires the quality script to carry a Cloud Monitoring dependency.
- Option B is explicitly not preferred. Option A is the recommended path.

### Implementation Approach for Option A

`scripts/push_bigquery_quality_metrics.py` will:

1. Accept `--report-path` (path to `ci-report.json`) and `--project-id` as arguments.
2. Parse the JSON report.
3. Construct Cloud Monitoring time series payloads for each of the 5 planned metrics.
4. Write time series using `gcloud` CLI or Python client.
5. Exit 0 on success; exit non-zero on failure.
6. Print no secrets. Print no credentials. Print no service account keys.

The script must not re-run BigQuery checks. It must not modify BigQuery. It must not start
Cloud SQL. It must not trigger schedulers.

---

## 6. Workflow Integration Plan

The planned workflow changes to `.github/workflows/bigquery-quality-checks.yml` are
described below. These are NOT implemented. This is a plan only.

### Current workflow structure (as of 2026-05-18)

```yaml
steps:
  - Checkout repository
  - Authenticate to Google Cloud via Workload Identity Federation
  - Set up Google Cloud SDK
  - Set up Python
  - Run BigQuery quality checks       # writes ci-report.json; exits 1 on failure
  - Upload quality check report       # if: always()
```

### Planned workflow structure

```yaml
steps:
  - Checkout repository
  - Authenticate to Google Cloud via Workload Identity Federation
  - Set up Google Cloud SDK
  - Set up Python
  - Run BigQuery quality checks       # writes ci-report.json; exits 1 on failure
  - Push quality metrics to Cloud Monitoring   # if: always()
  - Upload quality check report                # if: always()
```

### Key design constraints

1. The `Push quality metrics` step must use `if: always()` so that metrics are emitted
   even when the quality check step fails. This is the critical design requirement: a
   failed quality run must still produce a `status=0` / `failed_checks_count > 0` data
   point in Cloud Monitoring.

2. The metric emission step must not mask the original workflow failure. If the quality
   check step exits 1, the workflow conclusion must remain `failure`. The metric emission
   step outcome must not override this.

3. Artifact upload must also remain `if: always()` as currently implemented. Both the
   artifact upload and the metric emission are post-processing steps that must run
   regardless of quality check outcome.

4. The `Push quality metrics` step should use `continue-on-error: true` if metric emission
   failures should never block CI. Alternatively it can be left without that flag if
   metric emission failure is considered a hard signal. The implementation branch should
   decide this explicitly and document it.

### Planned step (illustrative, NOT implemented)

```yaml
- name: Push quality metrics to Cloud Monitoring
  if: always()
  run: |
    python3 scripts/push_bigquery_quality_metrics.py \
      --report-path docs/evidence/bigquery-quality-checks/ci-report.json \
      --project-id ${{ vars.GCP_PROJECT_ID }}
```

---

## 7. IAM and Terraform Plan

### Current IAM state

The GitHub Actions quality workflow authenticates via OIDC Workload Identity Federation
using service account `rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com`
(referenced via `vars.GCP_TERRAFORM_PLAN_SERVICE_ACCOUNT`).

As of 2026-05-18, the IAM bindings for this service account are defined in
`infra/terraform/gcp/iam.tf`. The existing roles granted are:

- `roles/viewer` (project-level)
- `roles/iam.workloadIdentityUser` (service account level)

Neither of these grants permission to write Cloud Monitoring time series.

### Required IAM addition

To write custom metrics to Cloud Monitoring, the service account needs:

```
roles/monitoring.metricWriter
```

This role grants `monitoring.timeSeries.create` at the project level and is the minimal
role required to write custom metric time series data points. It does not grant read access
to existing metrics or alert policy management.

### Terraform plan (NOT implemented)

In the future implementation branch, a new resource should be added to
`infra/terraform/gcp/iam.tf`:

```hcl
resource "google_project_iam_member" "terraform_plan_ci_monitoring_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = local.terraform_plan_ci_member
}
```

This binding follows the existing pattern for project-level IAM members in `iam.tf`. Before
any `terraform apply`, the binding must be validated with a zero-diff `terraform plan` on
the implementation branch.

### IAM decision required before implementation

Before implementing the Terraform binding, confirm whether the existing
`rtdp-terraform-plan-ci` service account is the correct identity for metric emission, or
whether a dedicated service account should be created for quality workflow CI steps.

Using the existing `rtdp-terraform-plan-ci` service account is the lowest-friction path
(no new service account, no new Workload Identity mapping). The tradeoff is that a service
account named `terraform-plan-ci` would accumulate `roles/monitoring.metricWriter` in
addition to its existing Terraform plan permissions, which is semantically broader than its
name implies.

---

## 8. Alert Policy Follow-Up Plan

### Planned alert: `RTDP BigQuery Quality Failure Alert`

This alert is NOT implemented. It is described here as the intended follow-up after the
metric emission step is proven.

| Property | Value |
|---|---|
| Display name | `RTDP BigQuery Quality Failure Alert` |
| Enabled | `true` |
| Notification channel | Existing email channel (same as worker error and silver refresh policies) |
| Condition | `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count > 0` |
| Alternative condition | `custom.googleapis.com/rtdp/bigquery_quality/status == 0` |

The alert policy would fire whenever any quality check in a run fails, using the same
email notification channel already attached to the existing two alert policies.

### Future branch

```
feat/bigquery-quality-cloud-monitoring-alert-policy
```

This branch should only be created after the metric emission step is proven (i.e., after
the implementation branch `feat/bigquery-quality-cloud-monitoring-metrics` has been
evidenced and accepted).

---

## 9. Dashboard Follow-Up Plan

The existing 4-panel RTDP Pipeline Overview dashboard at
`infra/monitoring/dashboards/rtdp-pipeline-overview.json` covers:

- `worker_message_processed_count`
- `worker_message_error_count`
- `silver_refresh_success_count`
- `silver_refresh_error_count`

After metric emission is proven, the dashboard should be extended with panels for:

| Proposed Panel | Metric |
|---|---|
| BigQuery Quality Status | `custom.googleapis.com/rtdp/bigquery_quality/status` |
| BigQuery Failed Checks Count | `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count` |
| BigQuery Row Count Trend | `custom.googleapis.com/rtdp/bigquery_quality/row_count` |
| BigQuery Freshness Age (hours) | `custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours` |

The dashboard update is not planned for the same branch as metric emission. It should
follow as a separate evidence branch after metric emission is proven.

### Future branch suggestion

```
docs/bigquery-quality-cloud-monitoring-metrics-evidence
docs/index-bigquery-quality-cloud-monitoring-metrics-evidence
```

---

## 10. Safety Constraints

The following constraints must hold throughout the implementation and evidence phases.
These constraints are identical to those proven throughout the existing quality workflow
evidence record.

| Constraint | Requirement |
|---|---|
| BigQuery not mutated | The metric emission script must not issue any BigQuery write, INSERT, UPDATE, DELETE, CREATE, or DROP statement. It reads only from the JSON report file. |
| Cloud SQL not started | Cloud SQL must remain in `NEVER / STOPPED` state. The metric emission script does not connect to Cloud SQL. |
| Cloud Scheduler not executed | No scheduler must be triggered as a side effect of metric emission. |
| no secrets printed | The metric emission script must not print service account keys, tokens, credentials, or any secret material to stdout or stderr. |
| Report file is the only input | The script reads `ci-report.json` only. It does not re-run BigQuery checks. |
| Artifact upload preserved | The `if: always()` upload step must remain in the workflow after the metric emission step is added. |
| Metric emission does not override workflow outcome | A failed quality check (exit code 1) must remain visible as a workflow failure. |

---

## 11. Acceptance Criteria for Future Implementation

The following criteria must all be satisfied before the implementation branch is accepted.

| Criterion | Requirement |
|---|---|
| `scripts/push_bigquery_quality_metrics.py` exists | New script committed on the implementation branch |
| Script parses `ci-report.json` correctly | Unit tests cover status=ok and status=error cases |
| All 5 metrics emitted correctly | Unit tests cover metric type, kind, value, and label construction |
| `if: always()` on metric emission step | Confirmed in workflow YAML |
| Metric emission runs on both pass and fail | Verified by running controlled failure + metric emission live |
| Cloud Monitoring receives at least one data point | `gcloud monitoring time-series list` or equivalent confirms data point for `custom.googleapis.com/rtdp/bigquery_quality/status` |
| Workflow failure not masked | A failed quality run still concludes as `failure` in GitHub Actions |
| Artifact upload still present and runs `if: always()` | Confirmed in workflow YAML |
| `roles/monitoring.metricWriter` binding applied | Confirmed via `gcloud projects get-iam-policy` |
| Terraform plan zero-diff after IAM binding | `PLAN_EXIT=0` confirmed |
| 210 tests still pass (no regressions) | `uv run pytest -q` baseline preserved |
| Ruff clean | `uv run ruff check .` passes |
| `dbt/profiles.yml` absent | `REPO_DBT_PROFILE_ABSENT=true` |
| BigQuery not mutated | Confirmed in implementation evidence |
| Cloud SQL not started | Confirmed in implementation evidence |
| Cloud Scheduler not executed | Confirmed in implementation evidence |
| no secrets printed | Confirmed in implementation evidence |

---

## 12. Evidence Required to Mark This as Proven

The following evidence must be committed to the repository before the gap can be marked
closed.

| Evidence Item | Format |
|---|---|
| Live Cloud Monitoring time series data point for `custom.googleapis.com/rtdp/bigquery_quality/status` | Screenshot or `gcloud` CLI output showing at least one data point |
| Live Cloud Monitoring time series data point for `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count` | Screenshot or `gcloud` CLI output |
| Live Cloud Monitoring time series data point for `custom.googleapis.com/rtdp/bigquery_quality/check_pass` with at least one `check_name` label | Screenshot or `gcloud` CLI output |
| GitHub Actions run ID for the passing metric emission run | Run ID and conclusion: success |
| GitHub Actions run ID for a failing quality run that still emits metrics | Run ID, conclusion: failure (quality check), metric data point confirmed |
| `terraform plan` zero-diff output after IAM binding | `PLAN_EXIT=0` |
| `uv run pytest -q` with 210+ tests passing | Console output |
| `uv run ruff check .` clean | Console output |

The evidence document should be committed on branch:

```
docs/bigquery-quality-cloud-monitoring-metrics-evidence
```

And indexed on:

```
docs/index-bigquery-quality-cloud-monitoring-metrics-evidence
```

---

## 13. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `gcloud monitoring` CLI does not support writing custom time series directly | Medium | Fall back to Python `google-cloud-monitoring` client; document the dependency before implementation; add to `pyproject.toml` with a pinned version |
| `roles/monitoring.metricWriter` is not sufficient to create a new custom metric descriptor | Low | Custom metric descriptors are auto-created on first write; `metricWriter` role covers descriptor creation in most cases. If not, `roles/monitoring.editor` may be required — confirm before implementation. |
| Metric emission step adds latency to the workflow | Low | Cloud Monitoring write operations are typically fast (< 5 seconds). Acceptable given the workflow already runs BigQuery queries. |
| IAM binding on `rtdp-terraform-plan-ci` is semantically misleading | Low | Document the intent explicitly in `iam.tf` comment. Consider a dedicated quality workflow service account if the team prefers tighter naming alignment. |
| Controlled failure run emits `failed_checks_count = 1` but Cloud Monitoring alert fires during evidence | Low | During the evidence phase, the alert policy does not yet exist. Data points are written but no alert fires. Alert policy is a separate follow-up branch. |
| Metric emission step failure masks quality check failure in CI | Medium | Use `continue-on-error: true` on the metric emission step if this is a concern, or verify that GitHub Actions workflow conclusion is determined by the quality check step exit code regardless of subsequent step outcomes. |
| Adding `if: always()` to the metric emission step changes workflow timing | Low | `if: always()` is already used for artifact upload; the pattern is established and tested in the existing workflow. |

---

## 14. Recommended Branch Sequence

```
feat/bigquery-quality-cloud-monitoring-metrics
├── Add scripts/push_bigquery_quality_metrics.py
├── Add unit tests for the script
├── Update .github/workflows/bigquery-quality-checks.yml
│     └── Add metric emission step with if: always()
├── Add Terraform IAM binding for roles/monitoring.metricWriter
│     └── In infra/terraform/gcp/iam.tf
├── Terraform plan zero-diff validation
└── Live evidence: both pass and fail runs emit metrics

docs/bigquery-quality-cloud-monitoring-metrics-evidence
├── Cloud Monitoring time series screenshots
├── GitHub Actions run IDs (pass and fail)
├── Terraform plan output (PLAN_EXIT=0)
└── Full safety assertion table

docs/index-bigquery-quality-cloud-monitoring-metrics-evidence
└── Update docs/EVIDENCE_INDEX.md

feat/bigquery-quality-cloud-monitoring-alert-policy   [after metrics are proven]
├── Terraform alert policy: failed_checks_count > 0
├── Attach existing notification channel
└── Live alert firing evidence

```

---

## 15. Final Conclusion

Cloud Monitoring quality metrics are NOT implemented. Cloud Monitoring alerting is NOT
proven. real scheduled event execution is NOT YET PROVEN.

The existing BigQuery quality workflow produces a rich JSON report (`ci-report.json`) after
every run. The report contains all the data needed to emit five meaningful custom metrics to
Cloud Monitoring: overall status, failed check count, per-check pass/fail, row count, and
freshness age. No BigQuery re-querying is required for metric emission — the report is the
sole input.

The preferred implementation path is a separate script (`scripts/push_bigquery_quality_metrics.py`)
invoked from the workflow with `if: always()` after the quality check step, so that metrics
are emitted on both passing and failing runs. This preserves the read-only contract of the
quality checker, keeps the two concerns separate, and allows metric emission failures to be
handled independently.

The IAM change is minimal: add `roles/monitoring.metricWriter` to the existing
`rtdp-terraform-plan-ci` service account via a single new `google_project_iam_member`
resource in `infra/terraform/gcp/iam.tf`. A Terraform zero-diff plan must be confirmed
before apply.

Once metrics are emitted and evidenced, a follow-up alert policy
(`feat/bigquery-quality-cloud-monitoring-alert-policy`) should be created on
`failed_checks_count > 0`, attached to the existing email notification channel. This would
close the observability gap and connect the BigQuery quality layer to the same alerting
infrastructure already proven for pipeline errors.

This plan document does not implement anything. Implementation begins on branch
`feat/bigquery-quality-cloud-monitoring-metrics`.

---

*Evidence status: PLANNED - QUALITY METRICS NOT YET IMPLEMENTED*
