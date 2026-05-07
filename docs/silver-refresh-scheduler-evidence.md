# Silver Refresh Cloud Scheduler — Execution Evidence

**Status:** VALIDATED — CONFIGURATION ONLY / PAUSED
**Date:** 2026-05-07
**Branch:** `exec/silver-refresh-scheduler-validation`
**Runbook:** [docs/silver-refresh-scheduler-runbook.md](silver-refresh-scheduler-runbook.md)

---

## Executive Summary

The Cloud Scheduler configuration for the silver refresh job was completed on this branch:

- Cloud Scheduler API (`cloudscheduler.googleapis.com`) was enabled — it was not previously enabled.
- Dedicated service account `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` was created.
- `roles/run.invoker` was granted to `rtdp-scheduler-sa` at project level.
- Scheduler job `rtdp-silver-refresh-scheduler` was created in `europe-west1`.
- Schedule is `*/15 * * * *` (every 15 minutes).
- Timezone is UTC.
- HTTP target points to the `rtdp-silver-refresh-job` Cloud Run Job run endpoint via OAuth.
- OAuth service account is `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com`.
- The scheduler job was **paused immediately after creation** to prevent automatic execution while Cloud SQL is stopped.
- Cloud SQL remained **NEVER / STOPPED** — was not started at any point.
- The scheduler was not manually triggered.
- The Cloud Run Job was not executed.

---

## Pre-Execution Validation

All gates passed before any GCP write:

| Check | Result |
|---|---|
| Branch | `exec/silver-refresh-scheduler-validation` |
| `uv sync --all-packages` | Succeeded |
| `uv run pytest -q` | 116 passed, 0 failed |
| `uv run ruff check .` | All checks passed |
| Cloud SQL state | `NEVER / STOPPED` |

### Cloud Run Job Baseline

| Field | Value |
|---|---|
| Job name | `rtdp-silver-refresh-job` |
| Region | `europe-west1` |
| Image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest` |
| Service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Environment variable names | `DATABASE_URL` |
| `DATABASE_URL` present | Yes |

`SILVER_REFRESH_JOB_BASELINE_VALIDATED=true`

### Scheduler Jobs Baseline Before Creation

No scheduler jobs existed in `europe-west1` before creation — the region had no listed jobs.

---

## GCP Write Evidence

### A. Cloud Scheduler API Enablement

The Cloud Scheduler API (`cloudscheduler.googleapis.com`) was **not enabled** prior to this branch.

**Operation ID:**

```
operations/acf.p2-892892382088-0dba144d-29c5-4b37-ac50-a36034294408
```

**Enabled service output:**

```
projects/892892382088/services/cloudscheduler.googleapis.com
```

---

### B. Scheduler Service Account Creation

**Before creation — describe output:**

```
NOT_FOUND
```

**Creation output:**

```
Created service account [rtdp-scheduler-sa].
```

**Follow-up validation:**

| Field | Value |
|---|---|
| Email | `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Display name | `RTDP Cloud Scheduler caller for silver refresh job` |
| Disabled | `False` |

**Describe output:**

```
rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
RTDP Cloud Scheduler caller for silver refresh job
```

---

### C. IAM Binding

| Field | Value |
|---|---|
| Role | `roles/run.invoker` |
| Member | `serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |

**IAM validation output:**

```
ROLE               MEMBERS
roles/run.invoker  serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

---

### D. Scheduler Creation and Immediate Pause

**Creation command output:**

```yaml
attemptDeadline: 180s
httpTarget:
  headers:
    User-Agent: Google-Cloud-Scheduler
  httpMethod: POST
  oauthToken:
    scope: https://www.googleapis.com/auth/cloud-platform
    serviceAccountEmail: rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
  uri: https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-silver-refresh-job:run
name: projects/project-42987e01-2123-446b-ac7/locations/europe-west1/jobs/rtdp-silver-refresh-scheduler
retryConfig:
  maxBackoffDuration: 3600s
  maxDoublings: 5
  maxRetryDuration: 0s
  minBackoffDuration: 5s
schedule: '*/15 * * * *'
scheduleTime: '2026-05-07T06:00:00Z'
state: ENABLED
status:
  code: -1
timeZone: UTC
userUpdateTime: '2026-05-07T05:46:25.029067Z'
```

**Pause output:**

```
Job has been paused.
```

The job was paused **immediately after creation** to avoid automatic execution while Cloud SQL is stopped. Cloud SQL cannot safely be started without a controlled start/run/stop sequence; pausing the scheduler preserves the cost-control invariant until a dedicated scheduled-execution validation branch is executed.

---

## Post-Change Validation

`SILVER_REFRESH_SCHEDULER_CONFIG_VALIDATED=true`

### Verification Table

| Field | Required value | Observed value | Pass |
|---|---|---|---|
| Scheduler name | `rtdp-silver-refresh-scheduler` | `projects/project-42987e01-2123-446b-ac7/locations/europe-west1/jobs/rtdp-silver-refresh-scheduler` | **Yes** |
| State | `PAUSED` | `PAUSED` | **Yes** |
| Schedule | `*/15 * * * *` | `*/15 * * * *` | **Yes** |
| Timezone | `UTC` | `UTC` | **Yes** |
| URI | `rtdp-silver-refresh-job:run` endpoint | `https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-silver-refresh-job:run` | **Yes** |
| HTTP method | `POST` | `POST` | **Yes** |
| OAuth service account | `rtdp-scheduler-sa@...` | `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | **Yes** |
| OAuth scope | `cloud-platform` | `https://www.googleapis.com/auth/cloud-platform` | **Yes** |
| `attemptDeadline` | `180s` | `180s` | **Yes** |
| Cloud SQL | `NEVER / STOPPED` | `NEVER / STOPPED` | **Yes** |

### Scheduler List

```
ID                             STATE   SCHEDULE      TIME_ZONE
rtdp-silver-refresh-scheduler  PAUSED  */15 * * * *  UTC
```

---

## What This Proves

The **Cloud Scheduler configuration gap is closed at configuration level**.

There is now a configured Scheduler job (`rtdp-silver-refresh-scheduler`) capable of dispatching the `rtdp-silver-refresh-job` Cloud Run Job on a `*/15 * * * *` UTC cadence via authenticated HTTP POST with a dedicated service account holding `roles/run.invoker`. The job is paused intentionally to preserve the cost-control invariant while Cloud SQL is stopped.

---

## What This Does Not Claim

- Does not prove scheduled execution succeeded — the scheduler was not triggered.
- Does not prove `silver_refresh_success_count` increments from a Scheduler dispatch.
- Does not start Cloud SQL.
- Does not manually trigger the scheduler job.
- Does not execute the `rtdp-silver-refresh-job` Cloud Run Job.
- Does not create notification channels for alert policies.
- Does not add Terraform or IaC management for any GCP resource.
- Does not validate the 5,000-event load test tier.
- Does not add BigQuery or Dataflow integration.

---

## Acceptance Matrix

| Criterion | Status |
|---|---|
| Cloud Scheduler API enabled | **ACCEPTED** |
| Scheduler service account `rtdp-scheduler-sa` exists | **ACCEPTED** |
| `roles/run.invoker` binding exists for `rtdp-scheduler-sa` | **ACCEPTED** |
| Scheduler job `rtdp-silver-refresh-scheduler` exists | **ACCEPTED** |
| Scheduler target points to `rtdp-silver-refresh-job:run` | **ACCEPTED** |
| Schedule is `*/15 * * * *` | **ACCEPTED** |
| Timezone is UTC | **ACCEPTED** |
| Scheduler job is paused intentionally | **ACCEPTED** |
| Cloud SQL `NEVER / STOPPED` throughout | **ACCEPTED** |
| Scheduler was not manually triggered | **ACCEPTED** |
| Cloud Run Job was not executed | **ACCEPTED** |
| 116 tests passed | **ACCEPTED** |
| Ruff clean | **ACCEPTED** |

All criteria met. Evidence status: **VALIDATED — CONFIGURATION ONLY / PAUSED**.

---

## Remaining Gaps

| Gap | Priority | Notes |
|---|---|---|
| Scheduled execution proof — controlled Cloud SQL start/run/stop | P1 | Scheduler is paused; end-to-end scheduled execution not yet validated |
| Notification channels | P1 | Alert policies exist but have no delivery targets; email or webhook channel needed |
| Terraform / IaC | P1 | All GCP resources created imperatively; no Terraform state |
| 5,000-event load test | P1 | 100 and 1,000 tiers accepted; 5,000-tier not executed |
| BigQuery / Dataflow analytical tier | P1 | Silver layer is operational only; analytical tier not implemented |
| CI/CD deploy automation | P1/P2 | Deployments are manual; no automated pipeline |
| README stale GCP wording cleanup | P2 | GCP target architecture section wording predates several completed execution branches |
