# Cloud Monitoring Alert Policies — Validation Evidence

**Status:** VALIDATED
**Date:** 2026-05-06
**Branch:** `exec/cloud-alert-policies-validation`
**Runbook:** [docs/cloud-alert-policies-runbook.md](cloud-alert-policies-runbook.md)

---

## Executive Summary

Two Cloud Monitoring alert policies were created and validated on this branch:

- **RTDP Worker Message Error Alert** — fires when `worker_message_error_count > 0`
- **RTDP Silver Refresh Error Alert** — fires when `silver_refresh_error_count > 0`

Both policies are enabled and reference the correct validated logs-based metrics. `notificationChannels` is intentionally empty on both policies — channel configuration is a separate P1 step. Cloud SQL was not started, no Pub/Sub messages were published, and no application code or test changes were made.

---

## Pre-Execution Validation

All gates passed before any GCP write:

| Check | Result |
|---|---|
| Branch | `exec/cloud-alert-policies-validation` |
| `uv sync --all-packages` | Succeeded |
| `uv run pytest -q` | 116 passed, 0 failed |
| `uv run ruff check .` | All checks passed |
| Cloud SQL state | `NEVER / STOPPED` |
| `silver_refresh_error_count` metric exists | **True** (DELTA INT64) |
| `silver_refresh_success_count` metric exists | **True** (DELTA INT64) |
| `worker_message_error_count` metric exists | **True** (DELTA INT64) |
| `worker_message_processed_count` metric exists | **True** (DELTA INT64) |

---

## Alert Policy Creation Evidence

### Worker Message Error Alert

| Field | Value |
|---|---|
| Display name | `RTDP Worker Message Error Alert` |
| Policy ID | `projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129` |
| Enabled | `True` |
| Notification channels | `[]` |
| Condition | `worker_message_error_count > 0` |
| Metric filter | `metric.type="logging.googleapis.com/user/worker_message_error_count" resource.type="cloud_run_revision"` |

**Create command output:**

```
Created alert policy [projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129].
```

---

### Silver Refresh Error Alert

| Field | Value |
|---|---|
| Display name | `RTDP Silver Refresh Error Alert` |
| Policy ID | `projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042` |
| Enabled | `True` |
| Notification channels | `[]` |
| Condition | `silver_refresh_error_count > 0` |
| Metric filter | `metric.type="logging.googleapis.com/user/silver_refresh_error_count" resource.type="cloud_run_job"` |

**Create command output:**

```
Created alert policy [projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042].
```

---

## Post-Creation Validation

Full validation output:

```
--- WORKER POLICY ---
name: projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129
displayName: RTDP Worker Message Error Alert
enabled: True
notificationChannels: []
condition: worker_message_error_count > 0
filter: metric.type="logging.googleapis.com/user/worker_message_error_count" resource.type="cloud_run_revision"
VALIDATED: True

--- SILVER POLICY ---
name: projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042
displayName: RTDP Silver Refresh Error Alert
enabled: True
notificationChannels: []
condition: silver_refresh_error_count > 0
filter: metric.type="logging.googleapis.com/user/silver_refresh_error_count" resource.type="cloud_run_job"
VALIDATED: True
```

### Validation Table

| Criterion | Result |
|---|---|
| Worker policy exists | **True** |
| Worker policy enabled | **True** |
| Worker policy references `worker_message_error_count` | **True** |
| Silver policy exists | **True** |
| Silver policy enabled | **True** |
| Silver policy references `silver_refresh_error_count` | **True** |
| `notificationChannels` empty on worker policy | **True** |
| `notificationChannels` empty on silver policy | **True** |

---

## What This Proves

The project now has:

- **Validated logs-based metrics** — all four metrics (`worker_message_error_count`, `worker_message_processed_count`, `silver_refresh_error_count`, `silver_refresh_success_count`) have confirmed Cloud Monitoring timeSeries datapoints.
- **Cloud Monitoring dashboard** — the RTDP Pipeline Overview 4-panel dashboard is created in GCP and exported to `infra/monitoring/dashboards/rtdp-pipeline-overview.json`.
- **Active Cloud Monitoring alert policies** — two enabled alert policies now fire on any non-zero value of the error counters, moving the project from passive observability to active operational alerting.

This closes the **Alert Policies** gap identified in the audit.

---

## What This Does Not Claim

- Does not create notification channels — `notificationChannels` remains empty; channel configuration is a separate optional step.
- Does not test incident firing with synthetic errors in this branch — policy existence and configuration-level correctness is the scope here.
- Does not add a production Pub/Sub DLQ (`deadLetterPolicy`) to the push subscription.
- Does not add Cloud Scheduler to trigger the silver refresh job automatically.
- Does not add Terraform or IaC management of any GCP resource.
- Does not validate the 5,000-event load test tier.
- Does not implement BigQuery or Dataflow integration.

---

## Remaining Gaps

| Gap | Priority | Notes |
|---|---|---|
| Production Pub/Sub DLQ | P0 | `market-events-raw-worker-push` has no `deadLetterPolicy`; malformed messages cause unbounded retries |
| Notification channels | P1 | Alert policies exist but have no delivery targets; must be configured before alerts are actionable |
| Cloud Scheduler for silver refresh | P1 | Silver refresh is only triggered manually; no recurring execution |
| Terraform / IaC | P1 | All GCP resources were created imperatively; no Terraform state |
| 5,000-event load test | P1 | Load test plan exists; 100 and 1,000 tiers passed; 5,000 tier not executed |
| BigQuery / Dataflow | P1 | Analytical tier not implemented; silver layer is operational only |

---

## Acceptance Matrix

| Criterion | Status |
|---|---|
| Worker policy created | **ACCEPTED** |
| Silver policy created | **ACCEPTED** |
| Both policies enabled | **ACCEPTED** |
| Worker policy references `worker_message_error_count` | **ACCEPTED** |
| Silver policy references `silver_refresh_error_count` | **ACCEPTED** |
| No notification channel required for acceptance | **ACCEPTED** |
| Cloud SQL `NEVER / STOPPED` throughout | **ACCEPTED** |
| No Pub/Sub messages published | **ACCEPTED** |
| 116 tests passed | **ACCEPTED** |
| Ruff clean | **ACCEPTED** |

All criteria met. Evidence status: **VALIDATED**.
