# Silver Refresh Scheduler — Controlled Execution Proof Evidence

**Status:** VALIDATED — SCHEDULED EXECUTION PROOF
**Date:** 2026-05-07
**Branch:** `exec/silver-refresh-scheduler-execution-proof`
**Runbook:** [docs/silver-refresh-scheduler-execution-proof-runbook.md](silver-refresh-scheduler-execution-proof-runbook.md)

---

## Executive Summary

The end-to-end scheduled execution proof for `rtdp-silver-refresh-scheduler` was completed on
this branch:

- Cloud SQL (`rtdp-postgres`) was started temporarily and reached `ALWAYS / RUNNABLE`.
- `gcloud scheduler jobs run` on a `PAUSED` job failed with `FAILED_PRECONDITION` — the fallback
  resume → run → pause path was used instead.
- The Scheduler dispatched `rtdp-silver-refresh-job` successfully via the fallback path.
- A new execution `rtdp-silver-refresh-job-npcl6` was created, with `RUN BY` set to
  `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` — confirming the
  Scheduler service account, not a human operator, triggered the job.
- The execution succeeded: `SUCCEEDED_COUNT=1`, completed in 38.22 seconds.
- The application stdout log was found: `jsonPayload.status="ok"` (the app emits `ok`, not
  `success` — see Section 7 for details).
- The container exited cleanly: `Container called exit(0).`
- `silver_refresh_success_count` incremented: `TOTAL=1` in the Cloud Monitoring timeSeries
  query window `2026-05-07T06:18:00Z–06:19:00Z`.
- The Scheduler was paused immediately after the dispatch. Final state: `PAUSED`.
- Cloud SQL was stopped immediately after validation. Final state: `NEVER / STOPPED`.
- No Pub/Sub messages were published.
- No application code changes were made.
- No deployment occurred.

---

## 1. Pre-Execution Validation

All gates passed before any GCP write:

| Check | Result |
|---|---|
| Branch | `exec/silver-refresh-scheduler-execution-proof` |
| `uv sync --all-packages` | Succeeded |
| `uv run pytest -q` | 116 passed, 0 failed |
| `uv run ruff check .` | All checks passed |
| Cloud SQL state | `NEVER / STOPPED` |

### Scheduler Baseline

| Field | Value |
|---|---|
| State | `PAUSED` |
| Schedule | `*/15 * * * *` |
| Timezone | `UTC` |
| URI | `https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-silver-refresh-job:run` |
| HTTP method | `POST` |
| Auth | OAuth — `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |

### Cloud Run Job Baseline

| Field | Value |
|---|---|
| Job name | `rtdp-silver-refresh-job` |
| Image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest` |
| Service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Environment variable names | `DATABASE_URL` |
| `DATABASE_URL` present | Yes |

`CLOUD_RUN_JOB_BASELINE_VALIDATED=true`

### Recent Executions Baseline (Pre-Dispatch)

| Execution ID | Created | Run by |
|---|---|---|
| `rtdp-silver-refresh-job-5jx4x` | 2026-05-05 21:46:39 UTC | `crsetsolutions@gmail.com` |

This was the most recent execution before this proof. Any execution appearing after the dispatch
with `rtdp-scheduler-sa` as the caller constitutes new evidence of a scheduler-triggered run.

---

## 2. Controlled Cloud SQL Start

Cloud SQL was started immediately before the Scheduler dispatch to allow the Cloud Run Job to
connect to the database. This was a bounded window — Cloud SQL was stopped as soon as validation
was complete.

**Start command output:**

```
Patching Cloud SQL instance...done.
Updated [https://sqladmin.googleapis.com/sql/v1beta4/projects/project-42987e01-2123-446b-ac7/instances/rtdp-postgres].
```

**Confirmed state after start:**

```
ALWAYS  RUNNABLE
```

The Scheduler dispatch was not issued until Cloud SQL reported `RUNNABLE`.

---

## 3. Scheduler Dispatch Evidence

### Preferred path — failed

`gcloud scheduler jobs run` requires the job to be in `ENABLED` state. The first attempt while
the job was `PAUSED` returned:

```
ERROR: (gcloud.scheduler.jobs.run) FAILED_PRECONDITION: spanner.RunInTransaction:
generic::failed_precondition: Job.state must be ENABLED for RunJob.
```

This is a GCP API constraint — `jobs run` on a paused job is not supported. The fallback path
was used instead.

### Fallback path executed

The fallback sequence from the runbook was followed exactly:

1. Resume the Scheduler.
2. Trigger an immediate dispatch.
3. Pause the Scheduler again immediately.

**Command outputs:**

```
Job has been resumed.
```

The `gcloud scheduler jobs run` command produced no visible output. This is expected — the
command issues the dispatch asynchronously; the absence of output does not indicate failure. The
new execution `rtdp-silver-refresh-job-npcl6` confirmed the dispatch succeeded (Section 4).

```
Job has been paused.
```

**Scheduler state after fallback:**

```
PAUSED
```

The Scheduler was never left in `ENABLED` state after the controlled window. Total time between
resume and pause was minimal — one command in each direction.

---

## 4. Cloud Run Job Execution Evidence

A new execution appeared after the Scheduler dispatch with `rtdp-scheduler-sa` as the caller —
confirming this was a Scheduler-triggered execution, not a manual `gcloud run jobs execute` call.

### Execution list output

```
JOB                      EXECUTION                      REGION        RUNNING  COMPLETE  CREATED                  RUN BY
rtdp-silver-refresh-job  rtdp-silver-refresh-job-npcl6  europe-west1  0        1 / 1     2026-05-07 06:17:41 UTC  rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

### Execution describe validation

| Field | Value |
|---|---|
| Execution name | `rtdp-silver-refresh-job-npcl6` |
| Generation | `1` |
| Created | `2026-05-07T06:17:41.506460Z` |
| Start time | `2026-05-07T06:17:45.869808Z` |
| Completion time | `2026-05-07T06:18:24.090016Z` |
| Succeeded count | `1` |
| Failed count | — |
| Running count | — |

**Conditions:**

| Condition | Status | Message |
|---|---|---|
| Completed | True | Execution completed successfully in 38.22s. |
| ResourcesAvailable | True | Provisioned imported containers. |
| Started | True | Started deployed execution in 34.86s. |
| ContainerReady | True | Imported container image. |

`SCHEDULER_TRIGGERED_EXECUTION_SUCCEEDED=true`

---

## 5. Final Safe State After Execution

Cloud SQL and the Scheduler were returned to their safe resting states immediately after the
execution confirm step, before log and metric queries:

**Cloud SQL stop output:**

```
Patching Cloud SQL instance...done.
Updated [https://sqladmin.googleapis.com/sql/v1beta4/projects/project-42987e01-2123-446b-ac7/instances/rtdp-postgres].
```

**Final states confirmed:**

| Resource | Final state |
|---|---|
| Scheduler | `PAUSED` |
| Cloud SQL | `NEVER / STOPPED` |

---

## 6. Log Evidence

### Initial query — zero results

The runbook specified a log filter including `jsonPayload.status="success"`. This query returned
zero results. This was not an execution failure.

**Root cause:** The application (`apps/silver-refresh-job`) emits `status: "ok"`, not
`status: "success"`. The runbook log filter was written based on prior convention before the
actual application field value was confirmed in production logs.

### Corrected query — 3 log entries found

A corrected query filtered by `resource.labels.job_name="rtdp-silver-refresh-job"` and the
execution timestamp window. This returned 3 log entries.

**Relevant stdout entry:**

| Field | Value |
|---|---|
| `timestamp` | `2026-05-07T06:18:19.261494Z` |
| `insertId` | `69fc2eab0003fd762d5417b9` |
| `logName` | `projects/project-42987e01-2123-446b-ac7/logs/run.googleapis.com%2Fstdout` |
| `resource.labels.job_name` | `rtdp-silver-refresh-job` |
| `resource.labels.execution_name` | `rtdp-silver-refresh-job-npcl6` |
| `jsonPayload.component` | `silver-refresh` |
| `jsonPayload.operation` | `refresh_market_event_minute_aggregates` |
| `jsonPayload.processing_time_ms` | `380.198` |
| `jsonPayload.service` | `rtdp-silver-refresh-job` |
| `jsonPayload.status` | `ok` |
| `jsonPayload.timestamp_utc` | `2026-05-07T06:18:19.260802+00:00` |

**Container exit confirmation:**

```
timestamp: 2026-05-07T06:18:19.315427Z
textPayload: Container called exit(0).
```

The application executed `refresh_market_event_minute_aggregates`, logged `status: "ok"`, and
exited cleanly.

**Note on status field wording:** The `silver_refresh_success_count` metric filter matches on the
`status: "ok"` log field as configured. The runbook filter (`status="success"`) did not match
because the application uses `"ok"`. The runbook will be annotated on the documentation branch
to reflect the actual field value. This does not affect the validity of the execution proof —
the success metric incremented correctly (Section 7).

---

## 7. Metric Evidence

`silver_refresh_success_count` was queried via the Cloud Monitoring REST API after the success
log was confirmed.

**Metric:** `logging.googleapis.com/user/silver_refresh_success_count`

**Query window:** `2026-05-07T06:15:00Z` to `2026-05-07T06:30:00Z`

**TimeSeries response:**

| Interval | Value |
|---|---|
| `06:19:00Z – 06:20:00Z` | `0` |
| `06:18:00Z – 06:19:00Z` | `1` |
| `06:17:00Z – 06:18:00Z` | `0` |

**Summary:**

| Field | Value |
|---|---|
| `TIME_SERIES_COUNT` | `1` |
| `TOTAL` | `1` |
| Resource type | `cloud_run_job` |
| `location` | `europe-west1` |
| `project_id` | `project-42987e01-2123-446b-ac7` |
| `job_name` | `rtdp-silver-refresh-job` |

`SILVER_REFRESH_SUCCESS_METRIC_VALIDATED=true`

The metric datapoint at `06:18:00Z–06:19:00Z` corresponds to the execution completion at
`06:18:24Z`, within the 1-minute alignment period — confirming the metric is driven by the
log entry from execution `rtdp-silver-refresh-job-npcl6`.

---

## 8. Final Validation

| Check | Result |
|---|---|
| Scheduler state | `PAUSED` — `*/15 * * * *` UTC — URI points to `rtdp-silver-refresh-job:run` |
| Cloud SQL state | `NEVER / STOPPED` |
| `uv run pytest -q` | 116 passed, 0 failed |
| `uv run ruff check .` | All checks passed |
| Branch | `exec/silver-refresh-scheduler-execution-proof` |

---

## 9. What This Proves

- **Scheduled execution proof is closed.** Cloud Scheduler can dispatch `rtdp-silver-refresh-job`
  and the job executes successfully.
- **Scheduler service account works end-to-end.** The `RUN BY` field on the new execution
  confirms `rtdp-scheduler-sa` — not a human operator — triggered the job via OAuth.
- **Job connects to Cloud SQL under scheduler-triggered execution.** The application successfully
  opened a database connection, called `refresh_market_event_minute_aggregates`, and logged
  `status: "ok"` — proving the Cloud SQL Auth Proxy and Secret Manager injection work correctly
  under scheduler invocation.
- **Silver refresh succeeds under scheduler-triggered execution.** The function ran in 380ms,
  the job completed in 38.22 seconds end-to-end.
- **`silver_refresh_success_count` increments from a scheduler-triggered run.** The Cloud
  Monitoring timeSeries shows `TOTAL=1` in the correct 1-minute window, confirming the metric
  filter matches the application's `status: "ok"` field.
- **The cost-control protocol works at scheduler scale.** Cloud SQL was started, used for one
  job execution, and stopped — total exposure was a bounded window on a single branch.

---

## 10. What This Does Not Claim

- Does not leave the Scheduler enabled for recurring cron execution.
- Does not prove continuous cron operation over multiple 15-minute intervals.
- Does not create notification channels for alert policies.
- Does not add Terraform or IaC management for any GCP resource.
- Does not validate the 5,000-event load test tier.
- Does not add BigQuery or Dataflow analytical integration.
- Does not publish Pub/Sub messages to any topic.

---

## 11. Acceptance Matrix

| Criterion | Status |
|---|---|
| Cloud SQL started and became `RUNNABLE` | **ACCEPTED** |
| Scheduler dispatch succeeded via fallback resume → run → pause | **ACCEPTED** |
| New execution `rtdp-silver-refresh-job-npcl6` created by `rtdp-scheduler-sa` | **ACCEPTED** |
| Execution succeeded (`SUCCEEDED_COUNT=1`, completed 38.22s) | **ACCEPTED** |
| Stdout log found: `jsonPayload.status="ok"`, `operation="refresh_market_event_minute_aggregates"` | **ACCEPTED** |
| Container exited cleanly: `exit(0)` | **ACCEPTED** |
| `silver_refresh_success_count` incremented (`TOTAL=1`) | **ACCEPTED** |
| Scheduler final state `PAUSED` | **ACCEPTED** |
| Cloud SQL final state `NEVER / STOPPED` | **ACCEPTED** |
| No Pub/Sub messages published | **ACCEPTED** |
| No application code changes | **ACCEPTED** |
| No deployment | **ACCEPTED** |
| 116 tests passed | **ACCEPTED** |
| Ruff clean | **ACCEPTED** |

All criteria met. Evidence status: **VALIDATED — SCHEDULED EXECUTION PROOF**.

---

## 12. Remaining Gaps

| Gap | Priority | Notes |
|---|---|---|
| Notification channels | P1 | Alert policies exist but have no delivery targets; email or webhook channel needed before alerts are actionable |
| Terraform / IaC | P1 | All GCP resources created imperatively; no Terraform state |
| 5,000-event load test | P1 | 100 and 1,000 tiers accepted; 5,000-tier not yet executed |
| BigQuery / Dataflow analytical tier | P1 | Silver layer is operational only; no analytical tier |
| CI/CD deploy automation | P1/P2 | All deployments are manual; no automated pipeline |
| README stale GCP wording cleanup | P2 | GCP target architecture section wording predates several completed execution branches |
