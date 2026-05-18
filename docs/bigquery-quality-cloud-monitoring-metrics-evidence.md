# BigQuery Quality Cloud Monitoring Metrics Evidence

**Status:** VALIDATED - QUALITY METRICS EMITTED TO CLOUD MONITORING
**Date:** 2026-05-18
**Branch:** docs/bigquery-quality-cloud-monitoring-metrics-evidence

---

## 1. Scope

This document provides evidence that BigQuery quality check results are emitted as custom
metrics to Google Cloud Monitoring after each workflow run, on both successful and failing
conclusions.

The implementation was delivered in PR #157 ("Emit BigQuery quality metrics to Cloud
Monitoring"), which introduced:

- `scripts/push_bigquery_quality_metrics.py` — reads `ci-report.json` and pushes custom
  time series to Cloud Monitoring.
- `tests/test_push_bigquery_quality_metrics.py` — unit tests for report parsing and metric
  payload construction.
- A new workflow step "Push BigQuery quality metrics to Cloud Monitoring" with `if: always()`
  so metrics are emitted on both passing and failing quality runs.
- A Terraform IAM binding granting `roles/monitoring.metricWriter` to the GitHub Actions
  service account.

Two `workflow_dispatch` runs are evidenced below:

- **Run 26061129567** — safe inputs, conclusion: success — Cloud Monitoring receives
  `status = 1`, `failed_checks_count = 0`, `row_count = 6120`.
- **Run 26061541771** — impossible threshold, conclusion: failure — Cloud Monitoring receives
  `status = 0`, `failed_checks_count = 1`, `check_pass row_count_minimum = 0`.

This document does **not** prove Cloud Monitoring alerting, email notification delivery,
GitHub notification bell delivery, or freshness_age_hours metric emission.

---

## 2. Implementation Proven

PR #157 was merged to `main`. The following artefacts were introduced:

| Artefact | Description |
|---|---|
| `scripts/push_bigquery_quality_metrics.py` | Reads `ci-report.json`; pushes 10 time series to Cloud Monitoring |
| `tests/test_push_bigquery_quality_metrics.py` | Unit tests for metric payload construction |
| Workflow step (if: always()) | "Push BigQuery quality metrics to Cloud Monitoring" |
| `infra/terraform/gcp/iam.tf` | `google_project_iam_member.terraform_plan_ci_monitoring_metric_writer` |

Post-merge validation on `main`:

| Check | Result |
|---|---|
| `uv run pytest -q` | 239 passed |
| `uv run ruff check .` | clean |
| `terraform validate` | success |
| `terraform plan -detailed-exitcode` | PLAN_EXIT=0 |
| `dbt/profiles.yml` absent | REPO_DBT_PROFILE_ABSENT=true |
| `main == origin/main` | confirmed |

---

## 3. IAM / Terraform Proof

The Terraform IAM binding was applied before the merge of PR #157. The apply output
confirmed:

```
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
google_project_iam_member.terraform_plan_ci_monitoring_metric_writer created
```

The resource grants `roles/monitoring.metricWriter` at project level to the
`rtdp-terraform-plan-ci` service account — the identity used by the BigQuery quality
workflow via OIDC Workload Identity Federation.

A post-apply `terraform plan` returned PLAN_EXIT=0, confirming the applied state matches
the declared Terraform configuration exactly and no drift exists.

| Field | Value |
|---|---|
| Role granted | `roles/monitoring.metricWriter` |
| Resource | `google_project_iam_member.terraform_plan_ci_monitoring_metric_writer` |
| Apply result | 1 added, 0 changed, 0 destroyed |
| Post-apply plan | PLAN_EXIT=0 |

---

## 4. Safe Run Proof

| Field | Value |
|---|---|
| Run ID | 26061129567 |
| Event | workflow_dispatch |
| Conclusion | success |
| Status | completed |
| Created | 2026-05-18T21:20:15Z |
| Updated | 2026-05-18T21:21:06Z |
| URL | https://github.com/jcsf2020/real-time-data-platform/actions/runs/26061129567 |

### Dispatch Inputs

| Input | Value |
|---|---|
| `min_row_count` | 1 |
| `freshness_max_age_hours` | 0 |

### Artifact Report

| Field | Value |
|---|---|
| status | ok |
| failed_checks | [] |
| row_count_minimum | pass |
| observed rows | 6120 |
| staging_table_empty | 0 |
| generated_at_utc | 2026-05-18T21:20:58.190566+00:00 |

All checks passed. `status: ok`, `failed_checks: []`.

### Metric Emission Log Evidence

The following line appeared in the "Push BigQuery quality metrics to Cloud Monitoring" step
log for Run 26061129567:

```
Pushed 10 time series to Cloud Monitoring.
```

The step ran with `if: always()` and completed successfully.

---

## 5. Failure Run Proof

| Field | Value |
|---|---|
| Run ID | 26061541771 |
| Event | workflow_dispatch |
| Conclusion | failure |
| Status | completed |
| Created | 2026-05-18T21:29:04Z |
| Updated | 2026-05-18T21:29:56Z |
| URL | https://github.com/jcsf2020/real-time-data-platform/actions/runs/26061541771 |

### Dispatch Inputs

| Input | Value |
|---|---|
| `min_row_count` | 999999999 |
| `freshness_max_age_hours` | 0 |

`min_row_count=999999999` is an impossible threshold: the table contains 6120 rows.

### Quality Step Exit

The "Run BigQuery quality checks" step exited with exit code 1, setting workflow
conclusion to `failure`.

### Artifact Report

| Field | Value |
|---|---|
| status | error |
| failed_checks | ["row_count_minimum"] |
| row_count_minimum | fail |
| expected | row_count >= 999999999 |
| observed | 6120 |
| staging_table_empty | 0 |
| generated_at_utc | 2026-05-18T21:29:51.089169+00:00 |

### Metric Emission Log Evidence

The "Push BigQuery quality metrics to Cloud Monitoring" step ran via `if: always()` despite
the quality step failure. The step log confirmed:

```
Pushed 10 time series to Cloud Monitoring.
Artifact uploaded successfully after failure.
```

Metrics were emitted. The workflow conclusion remained `failure` — metric emission did not
mask the quality check failure.

---

## 6. Cloud Monitoring Datapoint Proof

The Cloud Monitoring REST API was queried after each run to confirm actual time series
datapoints were recorded.

### 6.1 Safe Run (26061129567) — Cloud Monitoring REST Confirmation

| Metric | series_count | Value | endTime |
|---|---|---|---|
| `status` | 1 | `{"int64Value": "1"}` | 2026-05-18T21:20:58Z |
| `failed_checks_count` | 1 | `{"int64Value": "0"}` | 2026-05-18T21:20:58Z |
| `check_pass` | 7 | all `{"int64Value": "1"}` | 2026-05-18T21:20:58Z |
| `row_count` | 1 | `{"int64Value": "6120"}` | 2026-05-18T21:20:58Z |

Summary of key values confirmed in Cloud Monitoring for the safe run:

- status = 1
- failed_checks_count = 0
- row_count = 6120
- All 7 `check_pass` series returned `int64Value: 1`, including `row_count_minimum = 1`

### 6.2 Failure Run (26061541771) — Cloud Monitoring REST Confirmation

| Metric | series_count | Value | endTime |
|---|---|---|---|
| `status` | 1 | `{"int64Value": "0"}` | 2026-05-18T21:29:51Z |
| `failed_checks_count` | 1 | `{"int64Value": "1"}` | 2026-05-18T21:29:51Z |
| `check_pass` | 7 | mixed (see below) | 2026-05-18T21:29:51Z |
| `row_count` | 1 | `{"int64Value": "6120"}` | 2026-05-18T21:29:51Z |

Summary of key values confirmed in Cloud Monitoring for the failure run:

- status = 0
- failed_checks_count = 1
- row_count = 6120
- check_pass row_count_minimum = 0
- check_pass row_count_positive = 1
- check_pass required_columns_not_null = 1
- check_pass event_id_unique = 1
- check_pass event_type_accepted_values = 1
- check_pass freshness_available = 1
- check_pass staging_table_empty = 1

Exactly one check failed (`row_count_minimum`); all six others returned `int64Value: 1`.

---

## 7. Metric Coverage Matrix

| Metric type | Emitted? | Series count | Notes |
|---|---|---|---|
| `custom.googleapis.com/rtdp/bigquery_quality/status` | yes | 1 | 1 = ok, 0 = error |
| `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count` | yes | 1 | count of failed checks |
| `custom.googleapis.com/rtdp/bigquery_quality/check_pass` | yes | 7 | per-check label `check_name` |
| `custom.googleapis.com/rtdp/bigquery_quality/row_count` | yes | 1 | observed row count |
| `custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours` | NOT PROVEN | — | see note below |

**Note on freshness_age_hours:** Both metric-emission proof runs used
`freshness_max_age_hours=0`, so the `freshness_max_age_hours` check was not active and
`freshness_age_hours` was not emitted. The metric is implemented in the script but
freshness_age_hours metric NOT YET PROVEN in Cloud Monitoring.

The total confirmed emission count of 10 time series per run is:
`status (1) + failed_checks_count (1) + check_pass (7) + row_count (1) = 10`.

This matches the log line `Pushed 10 time series to Cloud Monitoring.` observed in both runs.

---

## 8. Safety Assertions

| Assertion | Result |
|---|---|
| BigQuery not mutated | All quality SQL used read-only SELECT; metric script reads only the JSON report |
| Cloud SQL not started | Not involved in either run |
| Cloud Scheduler not executed | Both runs triggered via workflow_dispatch only |
| no secrets printed | Credentials used via Workload Identity Federation; no keys in logs |

---

## 9. What This Proves

- PR #157 delivers a working metric emission script (`scripts/push_bigquery_quality_metrics.py`)
  and workflow step with `if: always()`.
- `roles/monitoring.metricWriter` is applied via Terraform (PLAN_EXIT=0 post-apply).
- On a safe run (Run 26061129567), Cloud Monitoring receives `status = 1`,
  `failed_checks_count = 0`, `row_count = 6120`, and all seven `check_pass` series as `1`.
- On a failing run (Run 26061541771), Cloud Monitoring receives `status = 0`,
  `failed_checks_count = 1`, `row_count = 6120`, and `check_pass row_count_minimum = 0`
  while all other six checks remain `1`.
- Metric emission runs in both cases via `if: always()` without masking the workflow failure.
- `Pushed 10 time series to Cloud Monitoring.` is confirmed in the step log for both runs.
- 239 tests pass post-merge with ruff clean and PLAN_EXIT=0.
- BigQuery quality signals are now visible in Google Cloud Monitoring.

---

## 10. What This Does Not Prove

- **freshness_age_hours metric NOT YET PROVEN** — both proof runs used
  `freshness_max_age_hours=0`; the metric is implemented but no Cloud Monitoring datapoint
  exists for it.
- **Cloud Monitoring alerting NOT YET PROVEN** — no alert policy on
  `failed_checks_count > 0` or `status == 0` exists yet. Metric data is written but no alert
  has fired.
- **email notification delivery NOT PROVEN** — no email notification was triggered or
  confirmed by these runs.
- **GitHub notification bell delivery NOT PROVEN** — no GitHub bell notification was
  triggered or confirmed.
- Scheduled (cron) event execution — both runs used `workflow_dispatch`. However,
  scheduled event execution already observed via Run ID 26028523804 (documented separately).
- Cloud SQL was started or queried.
- Any Cloud Scheduler job was executed.
- Dataflow pipelines exist or are proven.
- Production continuous traffic is proven.

---

## 11. Acceptance Matrix

| Criterion | Met? |
|---|---|
| PR #157 merged to main | yes |
| `scripts/push_bigquery_quality_metrics.py` exists | yes |
| `tests/test_push_bigquery_quality_metrics.py` exists | yes |
| `if: always()` on metric emission step | yes |
| `roles/monitoring.metricWriter` binding applied via Terraform | yes |
| Terraform apply: 1 added, 0 changed, 0 destroyed | yes |
| Post-apply PLAN_EXIT=0 | yes |
| 239 passed (post-merge pytest) | yes |
| Ruff clean post-merge | yes |
| dbt/profiles.yml absent | yes |
| Safe run 26061129567: conclusion == success | yes |
| Safe run: status = 1 in Cloud Monitoring | yes |
| Safe run: failed_checks_count = 0 in Cloud Monitoring | yes |
| Safe run: row_count = 6120 in Cloud Monitoring | yes |
| Safe run: all check_pass series = 1 | yes |
| Safe run: Pushed 10 time series to Cloud Monitoring | yes |
| Failure run 26061541771: conclusion == failure | yes |
| Failure run: status = 0 in Cloud Monitoring | yes |
| Failure run: failed_checks_count = 1 in Cloud Monitoring | yes |
| Failure run: check_pass row_count_minimum = 0 | yes |
| Failure run: all other check_pass series = 1 | yes |
| Failure run: row_count = 6120 in Cloud Monitoring | yes |
| Failure run: Pushed 10 time series to Cloud Monitoring | yes |
| Workflow failure not masked by metric emission | yes |
| BigQuery not mutated | yes |
| Cloud SQL not started | yes |
| Cloud Scheduler not executed | yes |
| no secrets printed | yes |
| freshness_age_hours metric NOT YET PROVEN | acknowledged |
| Cloud Monitoring alerting NOT YET PROVEN | acknowledged |
| email notification delivery NOT PROVEN | acknowledged |
| GitHub notification bell delivery NOT PROVEN | acknowledged |

---

## 12. Final Conclusion

PR #157 introduced a fully operational metric emission pipeline for BigQuery quality check
results. The implementation is proven end-to-end:

1. **IAM** — `roles/monitoring.metricWriter` was granted to the GitHub Actions service
   account via Terraform. Apply confirmed 1 resource added, PLAN_EXIT=0 post-apply.

2. **Safe run (26061129567)** — `workflow_dispatch` with `min_row_count=1` completed with
   `conclusion: success`. Cloud Monitoring received `status = 1`, `failed_checks_count = 0`,
   `row_count = 6120`, and all seven `check_pass` series as `1`. Step log confirmed
   `Pushed 10 time series to Cloud Monitoring.`

3. **Failure run (26061541771)** — `workflow_dispatch` with `min_row_count=999999999`
   completed with `conclusion: failure`. Cloud Monitoring received `status = 0`,
   `failed_checks_count = 1`, `check_pass row_count_minimum = 0`, and all remaining
   `check_pass` series as `1`. Step log confirmed `Pushed 10 time series to Cloud Monitoring.`
   The workflow failure was not masked.

4. **Post-merge validation** — 239 passed, ruff clean, PLAN_EXIT=0,
   `dbt/profiles.yml` absent, `main == origin/main`.

BigQuery quality signals are now observable in Google Cloud Monitoring. The remaining open
items are freshness_age_hours metric emission (requires a run with `freshness_max_age_hours > 0`),
Cloud Monitoring alerting (separate future branch), email notification delivery, and GitHub
notification bell delivery — none of which are claimed proven here.

---

*Evidence status: VALIDATED - QUALITY METRICS EMITTED TO CLOUD MONITORING*
