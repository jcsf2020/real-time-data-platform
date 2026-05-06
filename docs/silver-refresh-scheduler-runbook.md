# Silver Refresh Scheduler Runbook

> **STATUS: RUNBOOK ONLY — NOT EXECUTED**
>
> No GCP commands in this document have been run. No Cloud Scheduler jobs have been created.
> No Cloud Run jobs have been updated. No IAM changes have been made. No Cloud SQL has been
> started. No Pub/Sub messages have been published. Nothing has been deployed.
>
> This runbook is a reference template for a future execution branch only.

---

## 1. Purpose

This runbook prepares automated scheduling for `rtdp-silver-refresh-job`.

**Goal:** move the silver refresh from manual `gcloud run jobs execute` invocations to a
Cloud Scheduler-triggered recurring execution — keeping `silver.market_event_minute_aggregates`
fresh, making the bronze → silver path operationally automated, and supporting API aggregate
endpoints (`/aggregates/minute`) with regularly refreshed data.

The `rtdp-silver-refresh-job` Cloud Run Job already exists and has been validated through manual
execution (see [docs/silver-refresh-job-validation.md](silver-refresh-job-validation.md)). The
only remaining gap is the absence of a Cloud Scheduler job to trigger it automatically.

---

## 2. Current State

| Property | Value |
|---|---|
| Cloud Run Job | `rtdp-silver-refresh-job` |
| Region | `europe-west1` |
| GCP project | `project-42987e01-2123-446b-ac7` |
| Function | `SELECT silver.refresh_market_event_minute_aggregates();` |
| Trigger mode today | Manual — `gcloud run jobs execute rtdp-silver-refresh-job` |
| Success metric | `silver_refresh_success_count` — validated Cloud Monitoring timeSeries datapoints exist |
| Error metric | `silver_refresh_error_count` — validated Cloud Monitoring timeSeries datapoints exist |
| Alert policy for silver errors | `RTDP Silver Refresh Error Alert` — exists and is enabled |
| Scheduler | **Absent — not configured** |

### Operational gaps addressed before this runbook

The following gaps have been closed on prior execution branches:

- All four logs-based metrics have validated Cloud Monitoring timeSeries datapoints.
- Cloud Monitoring dashboard (RTDP Pipeline Overview — 4 panels) exists.
- Cloud Monitoring alert policies exist and are enabled for both error counters.
- Production Pub/Sub DLQ (`deadLetterPolicy`) exists on `market-events-raw-worker-push`
  (`maxDeliveryAttempts=5`, 10s/60s backoff, DLQ topic `market-events-raw-dlq`).

The remaining P1 gap addressed by this runbook is the absence of Cloud Scheduler for the silver
refresh job.

---

## 3. Proposed Schedule Design

### Cloud Scheduler Job Definition

| Property | Value |
|---|---|
| Scheduler job name | `rtdp-silver-refresh-scheduler` |
| Region | `europe-west1` |
| Cron | `*/15 * * * *` |
| Cadence | Every 15 minutes |
| Timezone | `UTC` |
| HTTP method | `POST` |
| Target | Cloud Run Jobs API endpoint (see below) |
| Auth mode | OAuth 2.0 with OIDC token for Google APIs (verify at execution time — see Section 6.E) |

**Timezone rationale:** UTC is preferred for infrastructure scheduling. The project uses UTC
timestamps throughout (Cloud Run logs, Cloud Monitoring, API responses). Using UTC avoids
daylight-saving-time offsets and keeps the scheduler consistent with other infrastructure clocks.
Europe/Lisbon would shift the schedule by one hour twice a year; UTC does not.

**Cadence rationale:** Every 15 minutes is a reasonable initial frequency for refreshing minute
aggregates. The silver refresh function is an idempotent upsert — running it when no new bronze
events exist is safe and produces no-op writes. The cadence can be increased to 5 minutes or
decreased to 30 minutes without other changes. Start at 15 minutes and adjust after observing
Cloud Run Job execution latency and Cloud SQL query duration in logs.

### Target URL

Cloud Scheduler triggers Cloud Run Jobs via the Cloud Run Admin API:

```
https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-silver-refresh-job:run
```

This is the standard Cloud Run Jobs run endpoint. The region (`europe-west1`) and job name
(`rtdp-silver-refresh-job`) match the deployed job.

### Service Account Strategy

**Recommended: create a dedicated scheduler service account.**

Using a dedicated service account for the scheduler caller follows least-privilege principles and
keeps the scheduler IAM binding separate from the worker service account (`rtdp-worker-sa`), which
has Cloud SQL and Secret Manager access. The scheduler caller only needs permission to execute the
Cloud Run Job — it does not need database or secret access.

Proposed dedicated service account:

```
rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

If the execution branch confirms that `rtdp-worker-sa` is already appropriate (e.g., it already
has `roles/run.invoker`) and the team prefers reuse over proliferation of service accounts, reuse
is acceptable — document the decision in the evidence file.

### IAM Requirements

The scheduler caller service account must have permission to execute the Cloud Run Job.

Likely required role:

```
roles/run.invoker
```

This role grants permission to submit job execution requests to Cloud Run. Verify the exact
required role at execution time — the Cloud Run Jobs API may require a more specific permission.
If `roles/run.invoker` is insufficient, check whether `roles/run.developer` or a custom role is
needed, and document the resolution in the execution evidence file.

---

## 4. Safety Constraints

These constraints are **absolute** for this runbook branch and any execution branch that follows:

- Do not start Cloud SQL during this runbook branch — this is a documentation-only branch.
- Do not execute scheduler creation commands on this docs branch.
- Do not trigger `rtdp-silver-refresh-job` during this docs branch.
- Do not change the Cloud Run Job image.
- Do not change the Cloud Run Job `DATABASE_URL` secret binding.
- Do not modify worker or Pub/Sub resources (`market-events-raw-worker-push`, `market-events-raw`,
  `market-events-raw-dlq`).
- Do not publish Pub/Sub messages to any topic.
- Do not create notification channels on this branch.
- Capture `gcloud run jobs describe rtdp-silver-refresh-job` output before creating the scheduler
  (pre-creation baseline).
- Capture `gcloud scheduler jobs list` output before creating the scheduler (confirms no
  conflicting job exists).
- Document the rollback command (Section 8) before executing any scheduler creation.

---

## 5. What This Runbook Does Not Do

- Does not execute now.
- Does not create a Cloud Scheduler job now.
- Does not trigger the silver refresh job.
- Does not start Cloud SQL.
- Does not validate scheduled execution end-to-end (that requires a controlled Cloud SQL
  start/run/stop branch).
- Does not add Terraform or IaC.
- Does not create notification channels.
- Does not validate the 5,000-event load test.
- Does not add BigQuery or Dataflow integration.

---

## 6. Future Execution Commands

> **Do not run any of the following commands on this docs branch.**
> All commands below are templates for a future execution branch only.

### A. Pre-Execution Checks

Run all checks before any GCP write. Abort if any check fails.

**Check 1 — Working tree clean:**

```bash
git status --short --branch
# Expected: docs/silver-refresh-scheduler-runbook or a dedicated exec/ branch, no uncommitted changes
```

**Check 2 — Dependencies and tests pass:**

```bash
uv sync --all-packages
uv run pytest -q
# Expected: 116 passed, 0 failed
```

**Check 3 — Ruff clean:**

```bash
uv run ruff check .
# Expected: All checks passed!
```

**Check 4 — Cloud SQL is stopped:**

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required output: NEVER  STOPPED
# Abort if output is anything else. Do NOT start Cloud SQL for scheduler creation.
```

**Check 5 — Describe the existing Cloud Run Job (pre-creation baseline):**

```bash
gcloud run jobs describe rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
# Capture full output. Verify image, service account, and DATABASE_URL secret binding are unchanged.
# Abort if job is missing or DATABASE_URL binding is absent.
```

**Check 6 — List existing Cloud Scheduler jobs (pre-creation baseline):**

```bash
gcloud scheduler jobs list \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
# Capture full output. Confirm rtdp-silver-refresh-scheduler does NOT exist.
# Abort if a scheduler job with this name already exists unexpectedly.
```

**Check 7 — Confirm Cloud Run Job image and DATABASE_URL are unchanged:**

From the `gcloud run jobs describe` output above, verify:

- Image: `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest`
- Env var `DATABASE_URL` sourced from `rtdp-database-url:latest`
- Cloud SQL instance annotation: `project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres`
- Service account: `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com`

Abort if any of these differ from the expected values.

---

### B. Check Cloud Scheduler API

Before creating the scheduler job, verify the Cloud Scheduler API is enabled:

```bash
gcloud services list --enabled \
  --project=project-42987e01-2123-446b-ac7 \
  --filter="name:cloudscheduler.googleapis.com" \
  --format="value(name)"
# Expected: cloudscheduler.googleapis.com
```

If the output is empty, the API is not enabled. Enabling it is a GCP write:

```bash
# FUTURE EXECUTION ONLY — GCP write — marks Cloud Scheduler API as a used service
gcloud services enable cloudscheduler.googleapis.com \
  --project=project-42987e01-2123-446b-ac7
```

Document whether enabling was required in the execution evidence file.

---

### C. Service Account Creation (if dedicated account does not exist)

Check whether the dedicated scheduler service account exists:

```bash
gcloud iam service-accounts describe \
  rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --project=project-42987e01-2123-446b-ac7
# If this returns an error (404 / NOT_FOUND), the account does not exist — create it below.
# If it returns a descriptor, the account exists — skip creation.
```

If the account does not exist, create it:

```bash
# FUTURE EXECUTION ONLY — GCP write
gcloud iam service-accounts create rtdp-scheduler-sa \
  --display-name="RTDP Cloud Scheduler caller for silver refresh job" \
  --project=project-42987e01-2123-446b-ac7
```

Capture the creation output and include it in the execution evidence file.

---

### D. IAM Binding — Grant Scheduler SA Permission to Execute the Cloud Run Job

```bash
# FUTURE EXECUTION ONLY — GCP write
gcloud projects add-iam-policy-binding project-42987e01-2123-446b-ac7 \
  --member="serviceAccount:rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

> **Verification note:** `roles/run.invoker` is the standard role for triggering Cloud Run
> services and jobs. If this role is insufficient for the Cloud Run Jobs run API endpoint, the
> execution branch must determine the correct role (e.g., `roles/run.developer` or a custom role)
> and document the resolution. Do not proceed to scheduler creation until the IAM binding is
> confirmed.

Capture the IAM binding output and include it in the execution evidence file.

---

### E. Create Cloud Scheduler Job

> **Auth mode note:** Cloud Scheduler supports two auth modes for HTTP targets:
> - `--oidc-service-account-email` — issues an OIDC token (suitable for Cloud Run services and
>   some Google APIs).
> - `--oauth-service-account-email` — issues an OAuth 2.0 access token (required for some Google
>   Admin APIs).
>
> For the Cloud Run Jobs Admin API endpoint (`run.googleapis.com`), **OIDC is typically correct**
> because Cloud Run validates OIDC tokens issued by the Google identity service. However, the
> execution branch must verify the correct auth mode before running this command. If OIDC fails
> at execution time, switch to `--oauth-service-account-email` and document the resolution.

```bash
# FUTURE EXECUTION ONLY — GCP write
gcloud scheduler jobs create http rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --schedule="*/15 * * * *" \
  --time-zone="UTC" \
  --uri="https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-silver-refresh-job:run" \
  --http-method=POST \
  --oidc-service-account-email="rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com" \
  --oidc-token-audience="https://europe-west1-run.googleapis.com/"
```

If the OIDC audience must match the exact request URL rather than the API root, use the full URI
as the audience value. Verify at execution time.

---

### F. Verify Scheduler After Creation

After creation, verify the scheduler job configuration:

```bash
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

Required fields to confirm in the output:

| Field | Expected value |
|---|---|
| `name` | `projects/project-42987e01-2123-446b-ac7/locations/europe-west1/jobs/rtdp-silver-refresh-scheduler` |
| `schedule` | `*/15 * * * *` |
| `timeZone` | `UTC` |
| `httpTarget.uri` | `https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-silver-refresh-job:run` |
| `httpTarget.httpMethod` | `POST` |
| Auth service account | `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| `state` | `ENABLED` |

Abort and invoke the rollback plan (Section 8) if any field does not match expected values, or if
the scheduler is created in a `DISABLED` or `PAUSED` state.

List all scheduler jobs to confirm only the expected job exists:

```bash
gcloud scheduler jobs list \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

---

### G. Optional Manual Trigger (Do Not Require Unless Cloud SQL Is Running)

The scheduler can be triggered manually to test the dispatch path:

```bash
# OPTIONAL — FUTURE EXECUTION ONLY
gcloud scheduler jobs run rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

> **Important:** The scheduler dispatch will invoke `rtdp-silver-refresh-job`, which will attempt
> to connect to Cloud SQL. Since the cost-control invariant keeps Cloud SQL in `NEVER / STOPPED`
> state, triggering the scheduler without first starting Cloud SQL will result in a job execution
> failure (connection refused). This is expected and does not invalidate the scheduler
> configuration — the scheduler is correctly configured even if the job fails when Cloud SQL is
> stopped.
>
> **Do not trigger the scheduler** during this docs branch or the initial scheduler creation
> branch. Only trigger it if a separate controlled Cloud SQL start/run/stop plan is in place and
> explicitly approved. Capture the scheduler dispatch log and Cloud Run Job execution log in the
> evidence file if triggered.

---

## 7. Rollback Plan

If the scheduler job must be removed after creation:

```bash
gcloud scheduler jobs delete rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --quiet
```

Confirm the scheduler job is gone:

```bash
gcloud scheduler jobs list \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
# Expected: rtdp-silver-refresh-scheduler no longer appears.
```

**Service account cleanup (optional):**

If `rtdp-scheduler-sa` was created only for this scheduler and is no longer needed, it can be
deleted:

```bash
# Optional — only if the service account has no other bindings
gcloud iam service-accounts delete \
  rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --project=project-42987e01-2123-446b-ac7 \
  --quiet
```

The Cloud Run Job (`rtdp-silver-refresh-job`) and its IAM bindings are unaffected by deleting the
scheduler job — do not delete or modify the job as part of scheduler rollback.

**Confirm Cloud SQL is stopped after rollback:**

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required: NEVER  STOPPED
```

---

## 8. Evidence to Capture in Future Execution Branch

The execution evidence document must include:

- [ ] Branch name (use an `exec/` prefix, e.g. `exec/silver-refresh-scheduler-creation`)
- [ ] Pre-execution `uv run pytest -q` output (116 tests passed)
- [ ] Pre-execution `uv run ruff check .` output (All checks passed)
- [ ] Pre-execution Cloud SQL state (`NEVER  STOPPED`)
- [ ] `gcloud run jobs describe rtdp-silver-refresh-job` output (pre-creation baseline)
- [ ] `gcloud scheduler jobs list` output before creation (confirms no conflicting job)
- [ ] Cloud Scheduler API enabled check output
- [ ] Service account creation output OR confirmation that an existing account was reused
- [ ] IAM binding command output (role granted to scheduler SA)
- [ ] `gcloud scheduler jobs create` output
- [ ] `gcloud scheduler jobs describe rtdp-silver-refresh-scheduler` output (all fields verified)
- [ ] `gcloud scheduler jobs list` output after creation
- [ ] Final Cloud SQL state (`NEVER  STOPPED`)
- [ ] Final `uv run pytest -q` output (116 tests passed)
- [ ] Final `uv run ruff check .` output (All checks passed)
- [ ] Explicit statement: no Pub/Sub messages were published
- [ ] Explicit statement: Cloud SQL was not started during this branch
- [ ] Explicit statement: scheduler was not manually triggered (or, if triggered, a controlled
     Cloud SQL start/run/stop plan was followed and documented separately)

---

## 9. Acceptance Criteria

The execution branch is accepted when **all** of the following are true:

| Criterion | Required value |
|---|---|
| Scheduler job exists | `rtdp-silver-refresh-scheduler` visible in `gcloud scheduler jobs list` |
| Scheduler schedule | `*/15 * * * *` |
| Timezone | `UTC` |
| Target URL | `https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-silver-refresh-job:run` |
| Auth service account | Documented (either `rtdp-scheduler-sa` or an explicitly justified alternative) |
| Scheduler state | `ENABLED` |
| Cloud Run Job definition unchanged | Image, `DATABASE_URL` binding, Cloud SQL annotation, and service account identical to pre-creation baseline |
| Cloud SQL state | `NEVER  STOPPED` throughout — never started on this branch |
| No Pub/Sub messages published | Explicitly stated in evidence |
| Tests pass | 116 passed |
| Ruff clean | All checks passed |
| Evidence document created | `docs/silver-refresh-scheduler-evidence.md` (or equivalent) |

---

## 10. Stop Conditions

Abort execution immediately if any of the following occur:

- Cloud SQL is not in `NEVER / STOPPED` state at the start of the session.
- `rtdp-silver-refresh-job` Cloud Run Job does not exist.
- `rtdp-silver-refresh-job` `DATABASE_URL` secret binding is absent or has changed.
- `rtdp-silver-refresh-scheduler` already exists unexpectedly in the scheduler job list.
- Auth mode (OIDC vs. OAuth) is uncertain and has not been verified — do not create the scheduler
  with an unverified auth mode.
- IAM binding command fails (non-zero exit, permission denied, invalid SA email).
- `gcloud scheduler jobs create` fails for any reason.
- The scheduler `describe` output shows the target URL pointing to the wrong job name or region.
- The scheduler is created in `DISABLED` or `PAUSED` state unexpectedly.
- Any command would execute `rtdp-silver-refresh-job` without a controlled Cloud SQL plan.
- Any command would mutate Pub/Sub resources (`market-events-raw`, `market-events-raw-worker-push`,
  `market-events-raw-dlq`) or the Pub/Sub worker Cloud Run service.

---

## 11. Roadmap Position

### What this runbook closes (after execution)

Creating and validating the Cloud Scheduler job closes the **Cloud Scheduler gap** at the
configuration level:

```
Cloud Scheduler rtdp-silver-refresh-scheduler (*/15 * * * * UTC)
  -> Cloud Run Jobs API
    -> rtdp-silver-refresh-job
      -> silver.refresh_market_event_minute_aggregates()
        -> silver.market_event_minute_aggregates
          -> /aggregates/minute
```

### What remains after scheduler configuration

Scheduler configuration confirms the dispatch path is wired correctly. It does not prove that
scheduled execution succeeds end-to-end — that requires a controlled Cloud SQL start/run/stop
branch specifically for scheduler execution validation.

**Remaining gaps after this runbook is executed:**

| Gap | Priority | Notes |
|---|---|---|
| Scheduled execution proof | P1 | Requires a controlled Cloud SQL start/run/stop plan to validate that a scheduler-triggered job execution completes successfully |
| Notification channels | P1 | Alert policies exist but have no delivery targets; email or webhook channel needed before alerts are actionable |
| Terraform / IaC | P1 | All GCP resources created imperatively; no Terraform state |
| 5,000-event load test | P1 | 100 and 1,000 tiers accepted; 5,000-tier not yet executed |
| BigQuery / Dataflow analytical tier | P1 | Silver layer is operational only; no analytical tier |
| CI/CD deploy automation | P1/P2 | All deployments are manual; no automated pipeline |
| README stale GCP wording cleanup | P2 | GCP target architecture section wording predates several completed execution branches |
