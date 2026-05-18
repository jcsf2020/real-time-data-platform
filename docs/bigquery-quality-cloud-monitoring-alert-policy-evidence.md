# BigQuery Quality Cloud Monitoring Alert Policy Evidence

**Status:** VALIDATED - ALERT POLICY APPLIED; INCIDENT/NOTIFICATION DELIVERY NOT YET PROVEN
**Date:** 2026-05-18
**Branch:** docs/bigquery-quality-cloud-monitoring-alert-policy-evidence

---

## 1. Scope

This document records the evidence collected for the BigQuery quality Cloud Monitoring alert policy.

The Terraform implementation was delivered through PR #160 and added:

- `google_monitoring_alert_policy.bigquery_quality_failure`
- Display name: `RTDP BigQuery Quality Failure`
- Metric filter: `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count`
- Trigger condition: `failed_checks_count > 0`
- Notification channel: `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885`

This document proves:

- The alert policy exists.
- The alert policy is enabled.
- The alert policy has a notification channel configured.
- A controlled failing BigQuery quality workflow emitted `failed_checks_count = 1`.
- The metric datapoint exists in Cloud Monitoring.
- The metric emission step still ran after the quality step failed.
- The workflow failure was not masked.

This document does not prove:

- Incident creation.
- Email notification delivery.
- GitHub notification bell delivery.

Correct evidence status:

**BigQuery quality Cloud Monitoring alert policy is applied and has a valid triggering metric, but incident/notification delivery is NOT YET PROVEN.**

---

## 2. Terraform Implementation

PR #160 added one alert policy resource:

```hcl
google_monitoring_alert_policy.bigquery_quality_failure
```

Key fields:

| Field | Value |
|---|---|
| Display name | `RTDP BigQuery Quality Failure` |
| Metric | `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count` |
| Resource type | `global` |
| Comparison | `COMPARISON_GT` |
| Trigger condition | `failed_checks_count > 0` |
| Duration | `0s` |
| Alignment period | `300s` |
| Per-series aligner | `ALIGN_MAX` |
| Cross-series reducer | `REDUCE_SUM` |
| Notification channel | `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885` |
| Auto close | `604800s` |
| Enabled | `true` |

Terraform filter:

```text
metric.type="custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count" resource.type="global"
```

---

## 3. Terraform Apply Evidence

Terraform apply created exactly one resource:

```text
google_monitoring_alert_policy.bigquery_quality_failure: Creation complete after 2s
[id=projects/project-42987e01-2123-446b-ac7/alertPolicies/8645165149135590665]

Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

Post-apply plan:

```text
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

This proves:

- The alert policy was applied.
- Terraform state includes the alert policy.
- There is no Terraform drift after apply.

---

## 4. Post-Merge Validation

After PR #160 was merged to `main`, final validation passed:

| Check | Result |
|---|---|
| `uv run pytest -q` | 239 passed |
| `uv run ruff check .` | All checks passed |
| `terraform fmt -check -recursive infra/terraform/gcp` | clean |
| `terraform -chdir=infra/terraform/gcp validate` | success |
| `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false` | PLAN_EXIT=0 |
| `dbt/profiles.yml` absent | REPO_DBT_PROFILE_ABSENT=true |
| Git status | `main...origin/main` |

---

## 5. Failure Workflow Run Used for Alert Signal

A controlled failing BigQuery quality workflow was triggered manually.

| Field | Value |
|---|---|
| Workflow | BigQuery Quality Checks |
| Run ID | 26065876070 |
| Event | workflow_dispatch |
| Conclusion | failure |
| Status | completed |
| Created | 2026-05-18T23:12:58Z |
| Updated | 2026-05-18T23:13:49Z |
| URL | https://github.com/jcsf2020/real-time-data-platform/actions/runs/26065876070 |

Inputs:

| Input | Value |
|---|---|
| `min_row_count` | `999999999` |
| `freshness_max_age_hours` | `0` |

The impossible threshold `min_row_count=999999999` forced a controlled quality failure.

The failing check was:

| Check | Expected | Observed | Status |
|---|---:|---:|---|
| `row_count_minimum` | `row_count >= 999999999` | `6120` | fail |

The quality report confirmed:

```json
{
  "status": "error",
  "failed_checks": ["row_count_minimum"]
}
```

The quality step failed as expected:

```text
Process completed with exit code 1.
```

The workflow conclusion remained `failure`.

---

## 6. Metric Emission Evidence

The metric emission step ran after the failing quality step because the workflow uses `if: always()`.

Log proof:

```text
Push BigQuery quality metrics to Cloud Monitoring
Pushed 10 time series to Cloud Monitoring.
```

This proves:

- The quality step failed.
- The metric emission step still executed.
- Metric emission did not mask the workflow failure.
- The workflow conclusion remained `failure`.

---

## 7. Cloud Monitoring Metric Datapoint Evidence

Cloud Monitoring REST API was queried after the failing run.

Query window:

```text
WINDOW=2026-05-18T22:49:05Z/2026-05-18T23:19:05Z
```

Result:

```text
--- FAILED CHECKS METRIC ---
series_count=1
{
  "metric": "custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count",
  "value": {"int64Value": "1"},
  "endTime": "2026-05-18T23:13:44Z"
}
```

Confirmed metric signal:

| Metric | Value | endTime |
|---|---:|---|
| `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count` | `1` | 2026-05-18T23:13:44Z |

This proves the alert policy had a valid triggering metric available in Cloud Monitoring.

---

## 8. Alert Policy API Evidence

Cloud Monitoring REST API confirmed the alert policy exists and is enabled.

```text
--- ALERT POLICY ---
{
  "name": "projects/project-42987e01-2123-446b-ac7/alertPolicies/8645165149135590665",
  "displayName": "RTDP BigQuery Quality Failure",
  "enabled": true,
  "notificationChannels": [
    "projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885"
  ]
}
```

Confirmed facts:

| Field | Value |
|---|---|
| Policy ID | `8645165149135590665` |
| Display name | `RTDP BigQuery Quality Failure` |
| Enabled | `true` |
| Notification channel configured | yes |

---

## 9. Incident Access Attempt

The following Cloud Monitoring v3 incident endpoints were tested:

```text
https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/incidents
https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/locations/global/incidents
```

Both returned:

```text
HTTP Error 404: Not Found
```

The stable `gcloud monitoring` command group was checked and does not expose an incidents command.

`gcloud alpha monitoring` and `gcloud beta monitoring` would require installing extra SDK components:

```text
[alpha] not installed
[beta] not installed
```

Installation was declined intentionally to avoid changing local tooling during evidence collection.

Conclusion:

```text
alert policy exists and failed_checks_count=1 metric exists;
incident/notification delivery remains NOT YET PROVEN
```

---

## 10. Safety Assertions

| Assertion | Result |
|---|---|
| BigQuery not mutated | yes - quality workflow used read-only checks |
| Cloud SQL not started | yes - not involved |
| Cloud Scheduler not executed | yes - workflow_dispatch only |
| no secrets printed | yes - no credential values printed |
| No Terraform drift after apply | yes - PLAN_EXIT=0 |
| Workflow failure not masked | yes - run conclusion remained failure |

---

## 11. What This Proves

- PR #160 created the BigQuery quality Cloud Monitoring alert policy.
- Terraform applied exactly one alert policy.
- Post-apply Terraform plan returned PLAN_EXIT=0.
- The alert policy exists in Cloud Monitoring.
- The alert policy is enabled.
- The alert policy has a notification channel configured.
- A controlled failing workflow emitted `failed_checks_count = 1`.
- Cloud Monitoring stored the `failed_checks_count = 1` datapoint.
- The metric emission step ran after failure via `if: always()`.
- The workflow conclusion remained `failure`.

---

## 12. What This Does Not Prove

- Incident creation NOT YET PROVEN.
- Email notification delivery NOT YET PROVEN.
- GitHub notification bell delivery NOT YET PROVEN.
- Stable CLI incident listing NOT AVAILABLE.
- Monitoring API v3 incidents endpoint NOT AVAILABLE via tested paths.
- Alpha/beta gcloud components NOT installed.
- freshness_age_hours metric NOT YET PROVEN.
- Dataflow not implemented.

---

## 13. Acceptance Matrix

| Criterion | Met? |
|---|---|
| `google_monitoring_alert_policy.bigquery_quality_failure` exists | yes |
| Display name `RTDP BigQuery Quality Failure` | yes |
| Metric filter uses `failed_checks_count` | yes |
| Comparison `COMPARISON_GT` | yes |
| Aligner `ALIGN_MAX` | yes |
| Reducer `REDUCE_SUM` | yes |
| Notification channel configured | yes |
| Alert policy enabled | yes |
| Terraform apply succeeded | yes |
| Post-apply PLAN_EXIT=0 | yes |
| Failure run 26065876070 completed | yes |
| Failure run conclusion == failure | yes |
| `failed_checks_count = 1` metric datapoint found | yes |
| `Pushed 10 time series to Cloud Monitoring` | yes |
| Incident creation proven | no |
| Email notification delivery proven | no |
| GitHub notification bell delivery proven | no |

---

## 14. Final Conclusion

BigQuery quality Cloud Monitoring alerting is partially proven.

The alert policy is deployed, enabled, connected to a notification channel, and its input metric was observed with `failed_checks_count = 1` after a controlled failing workflow run.

However, incident creation and notification delivery are not yet proven because:

1. The tested Monitoring API v3 incidents endpoints returned HTTP 404.
2. The stable `gcloud monitoring` command group does not expose an incidents command.
3. Alpha/beta SDK components were not installed during evidence collection.

Therefore the correct evidence status is:

**VALIDATED - ALERT POLICY APPLIED; INCIDENT/NOTIFICATION DELIVERY NOT YET PROVEN**

---

*Evidence status: VALIDATED - ALERT POLICY APPLIED; INCIDENT/NOTIFICATION DELIVERY NOT YET PROVEN*
