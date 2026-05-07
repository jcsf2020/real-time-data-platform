# Cloud Monitoring Notification Channels — Validation Evidence

**Status:** VALIDATED — NOTIFICATION CHANNELS ENABLED
**Date:** 2026-05-07
**Branch:** `exec/notification-channels-validation`
**Runbook:** [docs/notification-channels-runbook.md](notification-channels-runbook.md)

---

## Executive Summary

The Cloud Monitoring notification channel was created and attached to both existing alert
policies on this branch:

- Email notification channel **RTDP Operator Email Alerts** created via Cloud Monitoring REST
  API (channel ID `1439157631105258885`).
- Channel ID captured and confirmed enabled with the correct email label.
- **RTDP Worker Message Error Alert** now references the notification channel.
- **RTDP Silver Refresh Error Alert** now references the notification channel.
- Both policies remain enabled with all metric filters and thresholds unchanged.
- Cloud SQL was not started — final state `NEVER / STOPPED`.
- Cloud Scheduler was not run — final state `PAUSED`.
- No Pub/Sub messages were published.
- No Cloud Run Jobs were executed.
- No deployment occurred.

---

## 1. Pre-Execution Validation

All gates passed before any GCP write:

| Check | Result |
|---|---|
| Branch | `exec/notification-channels-validation` |
| `uv sync --all-packages` | Succeeded |
| `uv run pytest -q` | 116 passed, 0 failed |
| `uv run ruff check .` | All checks passed |
| Cloud SQL state | `NEVER / STOPPED` |
| Scheduler state | `PAUSED` |

### Notification Channel Baseline

```
CHANNEL_COUNT: 0
```

No notification channels existed before execution.

`NOTIFICATION_CHANNELS_BASELINE_CAPTURED=true`

### Alert Policy Baseline

Both alert policies confirmed with `notificationChannels: []` before any update:

| Policy | Name | Enabled | notificationChannels | Metric filter |
|---|---|---|---|---|
| RTDP Worker Message Error Alert | `projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129` | `True` | `[]` | `metric.type="logging.googleapis.com/user/worker_message_error_count" resource.type="cloud_run_revision"` |
| RTDP Silver Refresh Error Alert | `projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042` | `True` | `[]` | `metric.type="logging.googleapis.com/user/silver_refresh_error_count" resource.type="cloud_run_job"` |

`ALERT_POLICIES_BASELINE_VALIDATED=true`

---

## 2. Notification Channel Creation

### CLI note

`gcloud monitoring channels list` failed because the `gcloud` CLI does not expose
`monitoring channels` subcommands without the beta component. The beta component was not
installed. All notification channel operations (create, list, describe) were performed via
the **Cloud Monitoring REST API** directly. This is a valid and equivalent path — the REST
API is the underlying interface that `gcloud` wraps.

### Created channel

| Field | Value |
|---|---|
| Resource name | `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885` |
| Display name | `RTDP Operator Email Alerts` |
| Type | `email` |
| Enabled | `True` |
| `labels.email_address` | `crsetsolutions@gmail.com` |

`NOTIFICATION_CHANNEL_CREATED=true`

---

## 3. Alert Policy Update Evidence

### Updated policy JSON — pre-update verification

Before issuing the update, both policy JSON payloads were prepared and verified:

**Worker policy (pre-update verification):**

| Field | Value |
|---|---|
| `displayName` | `RTDP Worker Message Error Alert` |
| `enabled` | `True` |
| `notificationChannels` | `['projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885']` |
| `metric_found` | `True` |

**Silver policy (pre-update verification):**

| Field | Value |
|---|---|
| `displayName` | `RTDP Silver Refresh Error Alert` |
| `enabled` | `True` |
| `notificationChannels` | `['projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885']` |
| `metric_found` | `True` |

`UPDATED_POLICY_JSON_PREPARED=true`

---

### Worker alert policy — post-update validation

| Field | Value |
|---|---|
| `displayName` | `RTDP Worker Message Error Alert` |
| `enabled` | `True` |
| `notificationChannels` | `['projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885']` |
| `filters` | `metric.type="logging.googleapis.com/user/worker_message_error_count" resource.type="cloud_run_revision"` |

`WORKER_ALERT_POLICY_CHANNEL_VALIDATED=true`

---

### Silver alert policy — post-update validation

| Field | Value |
|---|---|
| `displayName` | `RTDP Silver Refresh Error Alert` |
| `enabled` | `True` |
| `notificationChannels` | `['projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885']` |
| `filters` | `metric.type="logging.googleapis.com/user/silver_refresh_error_count" resource.type="cloud_run_job"` |

`SILVER_ALERT_POLICY_CHANNEL_VALIDATED=true`

---

## 4. Final Validation

### Notification channel — final state

| Field | Value |
|---|---|
| Resource name | `projects/project-42987e01-2123-446b-ac7/notificationChannels/1439157631105258885` |
| Display name | `RTDP Operator Email Alerts` |
| Type | `email` |
| Enabled | `True` |
| `labels.email_address` | `crsetsolutions@gmail.com` |

`NOTIFICATION_CHANNEL_FINAL_VALIDATED=true`

### Final safe state

| Resource | Final state |
|---|---|
| Scheduler | `PAUSED` |
| Cloud SQL | `NEVER / STOPPED` |

### Final tests

| Check | Result |
|---|---|
| `uv run pytest -q` | 116 passed, 0 failed |
| `uv run ruff check .` | All checks passed |

---

## 5. What This Proves

- **Notification channels gap is closed.** The project now has an active email notification
  channel attached to both Cloud Monitoring alert policies.
- **Alert policies are operator-actionable.** When `worker_message_error_count > 0` or
  `silver_refresh_error_count > 0`, Cloud Monitoring will deliver an email notification to
  the configured operator address — no manual console monitoring required.
- **Existing alert conditions were fully preserved.** Both metric filters, thresholds,
  alignment windows, and enabled states are unchanged from the values set during the alert
  policy creation branch (`exec/cloud-alert-policies-validation`).
- **No compute or data pipeline execution was required.** The notification channel and policy
  updates are control-plane operations only — no Cloud SQL, no Scheduler, no Cloud Run Job,
  no Pub/Sub.

---

## 6. What This Does Not Claim

- Does not test real incident firing — no synthetic errors were introduced and no alert
  incident was triggered.
- Does not prove email delivery — channel verification was not performed; delivery will be
  confirmed when the first real incident fires.
- Does not create a Slack or webhook notification channel.
- Does not add Terraform or IaC management for notification channels or alert policies.
- Does not validate the 5,000-event load test tier.
- Does not add BigQuery or Dataflow analytical integration.
- Does not run the Scheduler or execute any Cloud Run Job.

---

## 7. Acceptance Matrix

| Criterion | Status |
|---|---|
| Email notification channel exists | **ACCEPTED** |
| Channel enabled | **ACCEPTED** |
| Channel email | `crsetsolutions@gmail.com` — **ACCEPTED** |
| Channel ID captured | `1439157631105258885` — **ACCEPTED** |
| Worker alert policy references channel | **ACCEPTED** |
| Silver alert policy references channel | **ACCEPTED** |
| Worker policy remains enabled | **ACCEPTED** |
| Silver policy remains enabled | **ACCEPTED** |
| Worker metric filter unchanged | `worker_message_error_count`, `cloud_run_revision` — **ACCEPTED** |
| Silver metric filter unchanged | `silver_refresh_error_count`, `cloud_run_job` — **ACCEPTED** |
| Cloud SQL `NEVER / STOPPED` throughout | **ACCEPTED** |
| Scheduler `PAUSED` throughout | **ACCEPTED** |
| No Pub/Sub messages published | **ACCEPTED** |
| No Cloud Run Job execution | **ACCEPTED** |
| No deployment | **ACCEPTED** |
| 116 tests passed | **ACCEPTED** |
| Ruff clean | **ACCEPTED** |

All criteria met. Evidence status: **VALIDATED — NOTIFICATION CHANNELS ENABLED**.

---

## 8. Remaining Gaps

| Gap | Priority | Notes |
|---|---|---|
| Terraform / IaC | P1 | All GCP resources created imperatively; no Terraform state |
| 5,000-event load test | P1 | 100 and 1,000 tiers accepted; 5,000-tier not yet executed |
| BigQuery / Dataflow analytical tier | P1 | Silver layer is operational only; no analytical tier |
| CI/CD deploy automation | P1/P2 | All deployments are manual; no automated pipeline |
| README stale GCP wording cleanup | P2 | GCP target architecture section wording predates several completed execution branches |
