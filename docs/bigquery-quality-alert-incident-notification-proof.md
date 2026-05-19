# BigQuery Quality Alert Incident Notification Proof

**Status:** PARTIAL - ALERT POLICY AND EMAIL CHANNEL VALIDATED; INCIDENT/EMAIL DELIVERY NOT YET PROVEN
**Date:** 2026-05-19
**Branch:** docs/bigquery-quality-alert-incident-notification-proof

---

## 1. Scope

This document records the proof attempt for the BigQuery quality Cloud Monitoring alert path.

The goal is to validate whether a controlled BigQuery quality failure produces an alert incident and/or notification delivery.

Proven:

- Alert policy exists.
- Alert policy is enabled.
- Alert policy is connected to an email notification channel.
- Email notification channel exists.
- Email notification channel is enabled.
- Controlled failing workflow emitted `failed_checks_count = 1`.
- Workflow failed as expected.
- Metric emission still ran after failure.
- Workflow failure was not masked.
- Cloud Monitoring stored the `failed_checks_count = 1` datapoint.

Not proven:

- Incident creation NOT YET PROVEN.
- Email notification delivery NOT YET PROVEN.
- GitHub notification bell delivery NOT YET PROVEN.
- `freshness_age_hours` metric NOT YET PROVEN.

---

## 2. Alert Policy Baseline

Command executed:

    gcloud monitoring policies list \
      --project=project-42987e01-2123-446b-ac7 \
      --filter='displayName="RTDP BigQuery Quality Failure"' \
      --format='yaml(name,displayName,enabled,notificationChannels,conditions.displayName,conditions.conditionThreshold.filter,conditions.conditionThreshold.comparison,conditions.conditionThreshold.aggregations)'

Observed output:

    displayName: RTDP BigQuery Quality Failure
    enabled: true
    name: projects/project-42987e01-2123-446b-ac7/alertPolicies/8645165149135590665
    notificationChannels:
    - projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885

This confirms:

- Alert policy name: `RTDP BigQuery Quality Failure`
- Alert policy ID: `projects/project-42987e01-2123-446b-ac7/alertPolicies/8645165149135590665`
- Alert policy enabled: `true`
- Notification channel attached: `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885`

The stable local `gcloud monitoring` CLI did not expose notification channel listing:

    ERROR: (gcloud.monitoring) Invalid choice: 'channels'.

Notification channel validation was therefore performed through the Cloud Monitoring REST API.

---

## 3. Alert Policy and Notification Channel REST Proof

Observed alert policy via REST:

    {
      "name": "projects/project-42987e01-2123-446b-ac7/alertPolicies/8645165149135590665",
      "displayName": "RTDP BigQuery Quality Failure",
      "enabled": true,
      "notificationChannels": [
        "projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885"
      ],
      "combiner": "OR",
      "conditions": [
        {
          "displayName": "BigQuery quality failed checks count > 0",
          "filter": "metric.type=\"custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count\" resource.type=\"global\"",
          "comparison": "COMPARISON_GT",
          "duration": "0s",
          "aggregations": [
            {
              "alignmentPeriod": "300s",
              "perSeriesAligner": "ALIGN_MAX",
              "crossSeriesReducer": "REDUCE_SUM"
            }
          ]
        }
      ]
    }

Observed notification channel via REST:

    {
      "name": "projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885",
      "displayName": "RTDP Operator Email Alerts",
      "type": "email",
      "enabled": true,
      "verificationStatus": null,
      "labels": {
        "email_address": "crsetsolutions@gmail.com"
      }
    }

This proves:

- Alert policy exists.
- Alert policy is enabled.
- Alert policy has condition `failed_checks_count > 0`.
- Alert policy uses `COMPARISON_GT`.
- Alert policy uses `ALIGN_MAX`.
- Alert policy uses `REDUCE_SUM`.
- Alert policy has an attached notification channel.
- Notification channel exists.
- Notification channel is enabled.
- Notification channel type is `email`.
- Notification email is `crsetsolutions@gmail.com`.

This does not prove email delivery.

---

## 4. Controlled Failure Workflow Run

A controlled failing workflow was triggered manually.

Command executed:

    gh workflow run "BigQuery Quality Checks" \
      --ref main \
      -f min_row_count=999999999 \
      -f freshness_max_age_hours=0

Observed run:

    Run ID: 26065876070
    Event: workflow_dispatch
    Created: 2026-05-18T23:12:58Z
    Updated: 2026-05-18T23:13:49Z
    Conclusion: failure
    URL: https://github.com/jcsf2020/real-time-data-platform/actions/runs/26065876070

Purpose:

- Force `row_count_minimum` failure using `min_row_count=999999999`.
- Confirm quality workflow failure.
- Confirm metric emission still runs via `if: always()`.
- Confirm Cloud Monitoring receives `failed_checks_count = 1`.
- Attempt to verify incident and notification evidence.

---

## 5. Workflow Failure and Metric Emission Proof

Observed workflow metadata:

    {
      "conclusion": "failure",
      "createdAt": "2026-05-18T23:12:58Z",
      "event": "workflow_dispatch",
      "status": "completed",
      "updatedAt": "2026-05-18T23:13:49Z",
      "url": "https://github.com/jcsf2020/real-time-data-platform/actions/runs/26065876070"
    }

Observed quality step failure:

    Process completed with exit code 1.

Observed metric emission:

    Pushed 10 time series to Cloud Monitoring.

This proves:

- The workflow failed as expected.
- The failure was controlled.
- Metric emission still ran after failure.
- Metric emission did not mask the workflow failure.
- The metric step pushed 10 time series to Cloud Monitoring.

---

## 6. Artifact Report Proof

Downloaded artifact:

    bigquery-quality-checks-report

Observed report summary:

    status: error
    failed_checks:
      - row_count_minimum
    generated_at_utc: 2026-05-18T23:13:44.387286+00:00
    project_id: project-42987e01-2123-446b-ac7
    dataset: rtdp_analytics
    table: market_events_raw
    staging_table: market_events_raw_staging

Failing check:

    name: row_count_minimum
    expected: row_count >= 999999999
    observed: 6120
    status: fail

Passing checks:

- `row_count_positive`
- `required_columns_not_null`
- `event_id_unique`
- `event_type_accepted_values`
- `freshness_available`
- `staging_table_empty`

This proves:

- Failure was intentional and controlled.
- `row_count_minimum` failed because `6120 < 999999999`.
- Artifact was preserved.
- Report status was `error`.
- `failed_checks` contained `row_count_minimum`.

---

## 7. Cloud Monitoring Metric Datapoint Proof

Observed metric query window:

    WINDOW=2026-05-18T22:49:05Z/2026-05-18T23:19:05Z

Observed datapoint:

    metric: custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count
    value: {"int64Value": "1"}
    endTime: 2026-05-18T23:13:44Z
    series_count: 1

This proves:

- Cloud Monitoring received the triggering metric.
- Metric type: `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count`
- Value: `1`
- End time: `2026-05-18T23:13:44Z`
- This matches the alert condition `failed_checks_count > 0`.

This does not prove incident creation or email notification delivery.

---

## 8. Incident Lookup Attempt

Incident lookup was attempted through likely Cloud Monitoring REST paths.

Corrected REST attempts returned:

    https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/incidents
    ERROR: HTTP Error 404: Not Found

    https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/locations/global/incidents
    ERROR: HTTP Error 404: Not Found

Conclusion:

- These REST endpoints were not usable for incident retrieval in this context.
- This does not prove that no incident exists.
- Incident creation remains NOT YET PROVEN.

---

## 9. gcloud Incident Command Availability

Stable command check:

    gcloud monitoring --help | grep -i "incident"

Observed:

    No stable incident command found.

Alpha and beta commands prompted for component installation:

    [alpha] required
    [beta] required

Installation was not performed.

Conclusion:

- Stable `gcloud monitoring` did not expose incident listing.
- Alpha and beta components were not installed.
- Incident creation remains NOT YET PROVEN.
- Email notification delivery remains NOT YET PROVEN.
- GitHub notification bell delivery remains NOT YET PROVEN.

---

## 10. Safety Assertions

| Assertion | Result |
|---|---|
| BigQuery not mutated | yes - quality workflow used read-only quality SQL |
| Cloud SQL not started | yes - not involved |
| Cloud Scheduler not executed | yes - workflow_dispatch only |
| Terraform not changed | yes - docs-only branch |
| Terraform apply not executed on this branch | yes |
| no secrets printed | yes |
| Workflow failure masked | no - workflow conclusion remained failure |
| Metric emission after failure | yes - `Pushed 10 time series to Cloud Monitoring` |

---

## 11. What This Proves

This proof establishes:

- Alert policy `RTDP BigQuery Quality Failure` exists.
- Alert policy ID is `projects/project-42987e01-2123-446b-ac7/alertPolicies/8645165149135590665`.
- Alert policy is enabled.
- Alert policy is attached to notification channel `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885`.
- Alert policy condition watches `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count`.
- Alert policy comparison is `COMPARISON_GT`.
- Alert policy aligner is `ALIGN_MAX`.
- Alert policy reducer is `REDUCE_SUM`.
- Email notification channel exists.
- Email notification channel is enabled.
- Email notification channel type is `email`.
- Email notification channel display name is `RTDP Operator Email Alerts`.
- Email notification channel target is `crsetsolutions@gmail.com`.
- Controlled failure run `26065876070` completed with `conclusion: failure`.
- Failure run `26065876070` produced `failed_checks_count = 1`.
- Failure run `26065876070` preserved the quality report artifact.
- Metric emission ran after the quality failure.
- Metric emission pushed `10 time series` to Cloud Monitoring.
- Cloud Monitoring stored `failed_checks_count = 1` at `2026-05-18T23:13:44Z`.
- The workflow failure was not masked.

---

## 12. What This Does Not Prove

This proof does not establish:

- Incident creation.
- Email notification delivery.
- GitHub notification bell delivery.
- Any human received or acknowledged an alert notification.
- Any alert incident was opened, visible, or closed in Cloud Monitoring.
- Any notification delivery latency.
- Any escalation policy.
- Any alert routing beyond the configured email channel.
- `freshness_age_hours` metric emission.

Important status:

- Incident creation NOT YET PROVEN.
- Email notification delivery NOT YET PROVEN.
- GitHub notification bell delivery NOT YET PROVEN.
- `freshness_age_hours` metric NOT YET PROVEN.

---

## 13. Acceptance Matrix

| Criterion | Status |
|---|---|
| Alert policy exists | yes |
| Alert policy enabled | yes |
| Alert policy attached to notification channel | yes |
| Notification channel exists | yes |
| Notification channel enabled | yes |
| Notification channel type email | yes |
| Notification channel email recorded | yes |
| Controlled workflow failure executed | yes |
| Failure run ID recorded | yes - `26065876070` |
| Quality workflow failed as expected | yes |
| Metric emission ran after failure | yes |
| `Pushed 10 time series to Cloud Monitoring` observed | yes |
| `failed_checks_count = 1` observed in Cloud Monitoring | yes |
| Workflow failure not masked | yes |
| Incident creation proven | no |
| Email notification delivery proven | no |
| GitHub notification bell delivery proven | no |
| BigQuery not mutated | yes |
| Cloud SQL not started | yes |
| Cloud Scheduler not executed | yes |
| no secrets printed | yes |

---

## 14. Final Conclusion

The BigQuery quality alert path is partially proven.

Validated:

1. The alert policy `RTDP BigQuery Quality Failure` exists and is enabled.
2. The alert policy is connected to the enabled email notification channel `RTDP Operator Email Alerts`.
3. The notification channel points to `crsetsolutions@gmail.com`.
4. Controlled failure Run ID `26065876070` executed.
5. The workflow failed as expected and was not masked.
6. The metric emission step executed and pushed `10 time series` to Cloud Monitoring.
7. Cloud Monitoring stored the triggering datapoint: `failed_checks_count = 1`.

Still open:

1. Incident creation NOT YET PROVEN.
2. Email notification delivery NOT YET PROVEN.
3. GitHub notification bell delivery NOT YET PROVEN.
4. `freshness_age_hours` metric NOT YET PROVEN.

Correct final status:

**PARTIAL - ALERT POLICY AND EMAIL CHANNEL VALIDATED; INCIDENT/EMAIL DELIVERY NOT YET PROVEN**

---

*Evidence status: PARTIAL - ALERT POLICY AND EMAIL CHANNEL VALIDATED; INCIDENT/EMAIL DELIVERY NOT YET PROVEN*