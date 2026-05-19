# BigQuery Quality — Incident Creation & Email Notification Delivery Proof

## Status

> VALIDATED - INCIDENT CREATION AND EMAIL NOTIFICATION DELIVERY PROVEN

---

## Scope

This document provides evidence that a controlled quality failure on the BigQuery Quality Checks
workflow successfully triggered a Cloud Monitoring alert incident and delivered an email notification
to the operator channel. No production data was mutated.

| Field | Value |
| --- | --- |
| Branch | `docs/bigquery-quality-incident-notification-delivery-proof` |
| Date | 2026-05-19 |
| Workflow | BigQuery Quality Checks |
| Run ID | `26089332693` |
| Event | `workflow_dispatch` |
| Conclusion | `failure` |
| Created at | `2026-05-19T09:44:26Z` |
| Updated at | `2026-05-19T09:45:16Z` |
| Commit SHA | `2bc65a564795873fb82b269041e2659285dd23f7` |
| Service account | `rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Run URL | <https://github.com/jcsf2020/real-time-data-platform/actions/runs/26089332693> |

---

## Controlled Failure Workflow Evidence

The workflow was triggered manually (`workflow_dispatch`) with inputs designed to guarantee a quality
failure:

| Input | Value | Purpose |
| --- | --- | --- |
| `min_row_count` | `999999999` | Forces row count check to fail against real table |
| `freshness_max_age_hours` | `0` | Extreme threshold; not the check that triggered the alert |

Workflow concluded with `failure` as expected, confirming the controlled failure path executed.

---

## Quality Report Evidence

The quality check step produced a report artifact confirming the failure.

| Field | Value |
| --- | --- |
| Status | `error` |
| Failed checks | `["row_count_minimum"]` |
| Observed row count | `6120` |
| Expected row count | `>= 999999999` |
| `staging_table_empty` | `pass` |
| Generated at (UTC) | `2026-05-19T09:45:11.679552+00:00` |
| Artifact ID | `7080086765` |
| Artifact URL | <https://github.com/jcsf2020/real-time-data-platform/actions/runs/26089332693/artifacts/7080086765> |

The `row_count_minimum` check failed because the observed row count (`6120`) did not meet the
artificially high threshold (`999999999`). All other checks passed. The artifact is preserved.

---

## Metric Push Evidence

After the quality report was generated, the workflow pushed metrics to Cloud Monitoring.

- **10 time series** pushed to Cloud Monitoring.
- The `failed_checks_count` metric was included in the push.
- `failed_checks_count` had already been validated in a prior session as the trigger input for the
  alert policy condition.

---

## Alert Incident Evidence

`gcloud alpha monitoring alerts list` was executed and returned two alert incidents for the policy
with display name **RTDP BigQuery Quality Failure**.

| Alert name | State |
| --- | --- |
| `projects/project-42987e01-2123-446b-ac7/alerts/0.o81br4aj3ps8` | OPEN |
| `projects/project-42987e01-2123-446b-ac7/alerts/0.o80gcc6mhnoc` | CLOSED |

- The **OPEN** alert proves incident creation triggered by the `failed_checks_count` metric push.
- The **CLOSED** alert is a prior incident and confirms the policy has fired more than once.
- The Google Cloud Console incident detail page failed to load in the browser; CLI output is the
  authoritative evidence.

---

## Alert Policy Evidence

| Field | Value |
| --- | --- |
| Policy name | `projects/project-42987e01-2123-446b-ac7/alertPolicies/8645165149135590665` |
| Display name | RTDP BigQuery Quality Failure |
| Enabled | `true` |
| Condition display name | BigQuery quality failed checks count > 0 |
| Metric filter | `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count` |
| Resource type | `global` |
| Comparison | `COMPARISON_GT` |
| Threshold | `0` |
| Duration | `0s` |
| Alignment period | `300s` |
| Cross-series reducer | `REDUCE_SUM` |
| Per-series aligner | `ALIGN_MAX` |
| Notification channel | `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885` |

---

## Notification Channel Evidence

| Field | Value |
| --- | --- |
| Channel name | `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885` |
| Display name | RTDP Operator Email Alerts |
| Type | `email` |
| Enabled | `true` |
| Label keys | `["email_address"]` |

The actual email address is intentionally omitted from this document.

---

## Email Delivery Evidence

Gmail inbox screenshot evidence confirms that Google Cloud Alerting delivered email notifications.

| Field | Detail |
| --- | --- |
| Email subject | `[ALERT - No severity] BigQuery quality failed checks count > 0 on project-42987e01-2123-446b-ac7` |
| Visible timestamps | 10:46 AM and 1:48 AM |
| Emails visible | At least two Google Cloud Alerting messages |
| Screenshot files | `Screenshot 2026-05-19 at 10.54.13.png`, `Screenshot 2026-05-19 at 10.54.43.png` |

**Email notification delivery is PROVEN by Gmail inbox screenshot evidence.**

Notes:

- Email body content was not inspected; only subject line and timestamps are claimed.
- Recipient address is not disclosed in this document.

---

## Safety Notes

| Assertion | Result |
| --- | --- |
| BigQuery not mutated | yes - controlled quality validation used read-only BigQuery checks |
| Cloud SQL not started | yes - not involved in this validation |
| Cloud Scheduler not executed | yes - workflow_dispatch was used |
| Terraform not changed | yes - docs-only evidence branch |
| Terraform apply not executed | yes - no infrastructure mutation |
| no secrets printed | yes - Workload Identity Federation used; no key material printed |
| Artifact preserved | yes - artifact ID 7080086765 uploaded successfully |
| Controlled failure only | yes - min_row_count=999999999 triggered expected failure |
| No production data mutation | yes - no production data was changed |

---

## Remaining Gaps

- GitHub notification bell delivery NOT YET PROVEN.
- Dataflow not implemented.

---

## Conclusion

The end-to-end path from a controlled quality failure → metric push → Cloud Monitoring alert
incident → email notification delivery has been proven by CLI evidence (alert OPEN state) and Gmail
inbox screenshot evidence (email subject and timestamps visible). No production data was mutated
during this validation.
