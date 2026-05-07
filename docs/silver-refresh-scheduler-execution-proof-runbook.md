# Silver Refresh Scheduler — Controlled Execution Proof Runbook

> **STATUS: RUNBOOK ONLY — NOT EXECUTED**
>
> No GCP commands in this document have been run. Cloud SQL has not been started. The scheduler
> has not been resumed. The scheduler has not been manually triggered. The Cloud Run Job has not
> been executed. No Pub/Sub messages have been published. Nothing has been deployed. No GCP write
> commands have been performed.
>
> This runbook is a reference template for a future controlled execution branch only.

---

## 1. Purpose

This runbook prepares a controlled proof that Cloud Scheduler (`rtdp-silver-refresh-scheduler`)
can dispatch `rtdp-silver-refresh-job` successfully and that the silver refresh path completes
end-to-end under scheduled invocation.

**Goals:**

- Validate that the scheduler dispatch path reaches the Cloud Run Job.
- Validate that the Cloud Run Job executes successfully when triggered by the Scheduler.
- Validate that the success log (`jsonPayload.status="ok"`) appears in Cloud Logging.
- Validate that `silver_refresh_success_count` increments after the Scheduler dispatch.
- Preserve the cost-control invariant by starting Cloud SQL only for a short, bounded window.
- Pause the Scheduler again immediately after validation.
- Stop Cloud SQL immediately after validation.

**What this runbook closes (after execution):**

Scheduler configuration was proven on `exec/silver-refresh-scheduler-validation`
(see [docs/silver-refresh-scheduler-evidence.md](silver-refresh-scheduler-evidence.md)). That
branch confirmed the scheduler is wired, authenticated, and paused intentionally. The remaining
open gap is that no Scheduler-triggered execution has ever been observed succeeding. This runbook
closes that gap.

---

## 2. Current State

| Property | Value |
|---|---|
| Scheduler | `rtdp-silver-refresh-scheduler` |
| Scheduler state | `PAUSED` (intentionally — cost control) |
| Schedule | `*/15 * * * *` |
| Timezone | `UTC` |
| HTTP method | `POST` |
| Target | `https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-silver-refresh-job:run` |
| Auth | OAuth 2.0 — `rtdp-scheduler-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Auth scope | `https://www.googleapis.com/auth/cloud-platform` |
| Cloud Run Job | `rtdp-silver-refresh-job` |
| Job region | `europe-west1` |
| Job service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Cloud SQL | `rtdp-postgres` — expected `NEVER / STOPPED` before execution |
| Success metric | `silver_refresh_success_count` — validated timeSeries datapoints exist |
| Error metric | `silver_refresh_error_count` — validated timeSeries datapoints exist |
| Alert policy | `RTDP Silver Refresh Error Alert` — exists and enabled |

**Prior evidence:**

- [docs/silver-refresh-scheduler-evidence.md](silver-refresh-scheduler-evidence.md) — scheduler
  configuration validated (configuration only, no execution).
- [docs/silver-refresh-job-validation.md](silver-refresh-job-validation.md) — manual job
  execution validated; Cloud SQL start/stop protocol proven.
- [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md)
  — `silver_refresh_success_count` timeSeries confirmed.
- [docs/silver-refresh-error-metric-filter-evidence.md](silver-refresh-error-metric-filter-evidence.md)
  — `silver_refresh_error_count` timeSeries confirmed.
- [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) — `RTDP Silver
  Refresh Error Alert` exists and enabled.

---

## 3. Proposed Execution Strategy

Use a controlled manual Scheduler dispatch (`gcloud scheduler jobs run`) rather than waiting for
the next cron window. This avoids a 15-minute wait and gives a predictable execution time that is
easy to correlate with logs and metrics.

**Sequence:**

```
A. Pre-flight checks
B. Start Cloud SQL (NEVER → ALWAYS / RUNNABLE)
C. Trigger Scheduler (manual dispatch while job remains PAUSED if supported)
D. Verify Cloud Run Job execution succeeded
E. Confirm success log in Cloud Logging
F. Confirm silver_refresh_success_count incremented
G. Pause Scheduler (ensure PAUSED)
H. Stop Cloud SQL (ALWAYS → NEVER / STOPPED)
I. Final checks
```

**Key design decision — `gcloud scheduler jobs run` on a PAUSED job:**

The `gcloud scheduler jobs run` command forces an immediate dispatch regardless of the scheduled
cron window. Based on GCP documentation, this command works on a `PAUSED` job — it triggers a
one-time dispatch without resuming the recurring schedule. If this behaviour is confirmed at
execution time, the scheduler never needs to be set to `ENABLED`. If `jobs run` requires
`ENABLED` state, the fallback is: resume → run → pause immediately. Both paths are documented
in Section 6.C.

---

## 4. Safety Constraints

These constraints are **absolute**. Any deviation is a stop condition.

- Cloud SQL must be started only for the controlled validation window and stopped immediately after.
- Cloud SQL must be `NEVER / STOPPED` before execution begins and after execution ends.
- The Scheduler must end in `PAUSED` state — do not leave it `ENABLED`.
- Do not publish Pub/Sub messages to any topic.
- Do not modify Pub/Sub resources (`market-events-raw`, `market-events-raw-worker-push`,
  `market-events-raw-dlq`).
- Do not deploy code or update the Cloud Run Job image.
- Do not change the `DATABASE_URL` secret binding on the Cloud Run Job.
- Do not change the Scheduler target, auth, or schedule.
- Do not run load tests.
- Do not create notification channels on this branch.
- Do not retry a failed Cloud Run Job execution repeatedly — capture logs and stop Cloud SQL.
- If the Scheduler is accidentally left `ENABLED`, pause it immediately before any other action.

---

## 5. What This Runbook Does Not Do

- Does not execute now.
- Does not start Cloud SQL now.
- Does not run or resume the Scheduler now.
- Does not validate now.
- Does not create notification channels.
- Does not add Terraform or IaC.
- Does not validate the 5,000-event load test.
- Does not add BigQuery or Dataflow integration.

---

## 6. Future Execution Commands

> **Do not run any of the following commands on this docs branch.**
> All commands below are templates for a future execution branch only.

---

### A. Pre-Flight Checks

Run all checks before any GCP write. Abort if any check fails.

**Check 1 — Working tree clean:**

```bash
git status --short --branch
# Expected: current branch, no uncommitted changes
```

**Check 2 — Dependencies sync:**

```bash
uv sync --all-packages
# Expected: no errors
```

**Check 3 — Tests pass:**

```bash
uv run pytest -q
# Expected: 116 passed, 0 failed
```

**Check 4 — Ruff clean:**

```bash
uv run ruff check .
# Expected: All checks passed!
```

**Check 5 — Cloud SQL is NEVER / STOPPED:**

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required output: NEVER  STOPPED
# Abort if output is anything else.
```

**Check 6 — Scheduler is PAUSED:**

```bash
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state,schedule,timeZone,httpTarget.uri)"
# Required: state=PAUSED
# Confirm schedule=*/15 * * * *, timeZone=UTC, URI points to rtdp-silver-refresh-job:run
```

**Check 7 — Cloud Run Job baseline unchanged:**

```bash
gcloud run jobs describe rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
# Verify: image, DATABASE_URL binding, Cloud SQL annotation, service account unchanged
# Required image: europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest
# Required service account: rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

**Check 8 — List recent Cloud Run Job executions (pre-run baseline):**

```bash
gcloud run jobs executions list \
  --job=rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=5
# Capture the list. The newest execution ID in this output is the pre-run baseline.
# Any execution that appears after the scheduler dispatch is new.
```

**Check 9 — Pre-run `silver_refresh_success_count` baseline:**

Query the Cloud Monitoring REST API to record the current cumulative total before the run. This
is the baseline against which post-run increment will be measured.

```bash
ACCESS_TOKEN=$(gcloud auth print-access-token)

curl -s -X POST \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/timeSeries:query" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "fetch logging_metric :: logging.googleapis.com/user/silver_refresh_success_count | within 1h"
  }'
# Record the TOTAL value from the response. This is the pre-run baseline.
```

---

### B. Start Cloud SQL

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS \
  --project=project-42987e01-2123-446b-ac7
```

Poll until Cloud SQL reports `RUNNABLE`:

```bash
# Poll every 10 seconds until RUNNABLE (typically 30–90 seconds)
until gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)" | grep -q "RUNNABLE"; do
  echo "Waiting for Cloud SQL to become RUNNABLE..."
  sleep 10
done

gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required: ALWAYS  RUNNABLE
```

Do not proceed to the scheduler dispatch until Cloud SQL reports `RUNNABLE`.

---

### C. Trigger Scheduler

#### Preferred path — dispatch while PAUSED

```bash
gcloud scheduler jobs run rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

This command forces an immediate one-time dispatch. If the scheduler is `PAUSED`, verify at
execution time whether this command succeeds without resuming the recurring schedule.

**Expected outcome if the command succeeds on a PAUSED job:**

- The scheduler remains `PAUSED` after the dispatch.
- `rtdp-silver-refresh-job` receives a trigger and starts a new execution.
- The recurring schedule does not begin firing.

If the command succeeds: proceed to Section 6.D without resuming the scheduler.

#### Fallback path — resume, run, pause immediately

If `gcloud scheduler jobs run` fails because the job is `PAUSED`, use this fallback:

```bash
# Step 1 — resume
gcloud scheduler jobs resume rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# Step 2 — trigger immediately (do not wait for cron window)
gcloud scheduler jobs run rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# Step 3 — pause again immediately
gcloud scheduler jobs pause rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

After the fallback, confirm the scheduler is `PAUSED`:

```bash
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)"
# Required: PAUSED
```

If the scheduler shows `ENABLED` after the fallback pause command, pause it again and document
the issue. Do not proceed while the scheduler is `ENABLED`.

---

### D. Verify Cloud Run Job Execution

Wait approximately 60–120 seconds after the scheduler dispatch for the execution to start and
complete, then check:

**List executions — confirm a new execution appeared:**

```bash
gcloud run jobs executions list \
  --job=rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=5
# Confirm a new execution ID appears that was not in the pre-run baseline list.
# Note the newest execution ID (e.g. rtdp-silver-refresh-job-xxxxx).
```

**Describe the latest execution — confirm success:**

```bash
gcloud run jobs executions describe <EXECUTION_ID> \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
# Required: SUCCEEDED condition with status True
# Capture the full describe output.
```

Replace `<EXECUTION_ID>` with the actual execution ID from the list above.

If the execution is still running: wait and retry. If the execution failed: capture the full
describe output and logs, stop Cloud SQL (Section 6.H), and do not retry.

---

### E. Confirm Success Log in Cloud Logging

Allow 2–5 minutes after job execution for logs to propagate, then query:

```bash
gcloud logging read \
  'resource.type="cloud_run_job"
   AND resource.labels.job_name="rtdp-silver-refresh-job"
   AND jsonPayload.operation="refresh_market_event_minute_aggregates"
   AND jsonPayload.status="ok"' \
  --project=project-42987e01-2123-446b-ac7 \
  --freshness=30m \
  --limit=5 \
  --format=json
# Required: at least one log entry with jsonPayload.status="ok"
# Confirm jsonPayload.service="rtdp-silver-refresh-job"
# Confirm the timestamp is after the scheduler dispatch time.
```

If the success log is absent after 10 minutes: capture the full log output (remove the
`jsonPayload.status="ok"` filter to see all entries for the job), stop Cloud SQL, and do
not proceed.

---

### F. Confirm `silver_refresh_success_count` Incremented

Allow 5–10 minutes after the success log appears for the Cloud Monitoring metric to propagate
(DELTA metrics are aggregated over 1-minute alignment periods and may lag logs).

```bash
ACCESS_TOKEN=$(gcloud auth print-access-token)

curl -s -X POST \
  "https://monitoring.googleapis.com/v3/projects/project-42987e01-2123-446b-ac7/timeSeries:query" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "fetch logging_metric :: logging.googleapis.com/user/silver_refresh_success_count | within 1h"
  }'
# Required: TOTAL value > pre-run baseline captured in Check 9.
# If the metric has not incremented after 15 minutes, document the delay and check whether
# the log entry was ingested (Section 6.E). Do not retry the job.
```

---

### G. Pause Scheduler

If the preferred path in Section 6.C succeeded (dispatch while PAUSED, scheduler remained
PAUSED), skip this step — the scheduler is already paused.

If the fallback path was used and there is any doubt about the current state:

```bash
gcloud scheduler jobs pause rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)"
# Required: PAUSED
```

Do not proceed to Cloud SQL stop until the scheduler is confirmed `PAUSED`.

---

### H. Stop Cloud SQL

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER \
  --project=project-42987e01-2123-446b-ac7
```

Poll until `STOPPED`:

```bash
until gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)" | grep -q "STOPPED"; do
  echo "Waiting for Cloud SQL to stop..."
  sleep 10
done

gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required: NEVER  STOPPED
```

---

### I. Final Checks

```bash
# 1. Scheduler state
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)"
# Required: PAUSED

# 2. Cloud SQL final state
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required: NEVER  STOPPED

# 3. Tests
uv run pytest -q
# Expected: 116 passed, 0 failed

# 4. Ruff
uv run ruff check .
# Expected: All checks passed!

# 5. Working tree
git status --short --branch
# Expected: execution branch, changes only in evidence doc
```

---

## 7. Rollback Plan

If any step fails, execute the following in order:

**Step 1 — Pause Scheduler immediately (even if no other step has been taken):**

```bash
gcloud scheduler jobs pause rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(state)"
# Confirm: PAUSED
```

**Step 2 — Stop Cloud SQL immediately:**

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER \
  --project=project-42987e01-2123-446b-ac7

gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Confirm: NEVER  STOPPED
```

**Additional guidance:**

- If the Scheduler target was accidentally changed, do not attempt to repair it blindly. Stop
  Cloud SQL, pause the Scheduler, and document the exact state for manual review.
- If the Cloud Run Job execution failed, do not retry. Capture logs from the execution, stop
  Cloud SQL, and document the failure in the evidence file.
- If Cloud SQL fails to stop, check for active connections and retry. Do not leave the session
  without confirming Cloud SQL is stopped.
- Do not publish Pub/Sub messages as part of any troubleshooting or retry.

---

## 8. Evidence to Capture in Future Execution Branch

The evidence document (`docs/silver-refresh-scheduler-execution-proof-evidence.md`) must include:

- [ ] Branch name
- [ ] Pre-execution `uv run pytest -q` output (116 tests passed)
- [ ] Pre-execution `uv run ruff check .` output (All checks passed)
- [ ] Pre-execution Cloud SQL state (`NEVER  STOPPED`)
- [ ] Pre-execution Scheduler state (`PAUSED`) — full `describe` output
- [ ] Pre-execution Cloud Run Job baseline (`gcloud run jobs describe` — key fields)
- [ ] Pre-run executions list baseline (list of existing execution IDs before dispatch)
- [ ] Pre-run `silver_refresh_success_count` metric baseline (TOTAL value from API query)
- [ ] Cloud SQL start command output
- [ ] Cloud SQL `ALWAYS  RUNNABLE` confirmation
- [ ] Scheduler dispatch command used (preferred or fallback path — document which)
- [ ] `gcloud scheduler jobs run` output
- [ ] New execution ID from `gcloud run jobs executions list` after dispatch
- [ ] `gcloud run jobs executions describe <EXECUTION_ID>` output (must show SUCCEEDED)
- [ ] `gcloud logging read` output — success log entry (jsonPayload.status="ok")
- [ ] `silver_refresh_success_count` metric after run (TOTAL > pre-run baseline)
- [ ] Scheduler final state (`PAUSED`) — `describe` output
- [ ] Cloud SQL stop command output
- [ ] Cloud SQL `NEVER  STOPPED` final state confirmation
- [ ] Final `uv run pytest -q` output (116 tests passed)
- [ ] Final `uv run ruff check .` output (All checks passed)
- [ ] Explicit statement: no Pub/Sub messages were published
- [ ] Explicit statement: no deployment occurred
- [ ] Explicit statement: Cloud Run Job image was not changed
- [ ] Explicit statement: Scheduler did not remain `ENABLED` after validation

---

## 9. Acceptance Criteria

The execution branch is accepted when **all** of the following are true:

| Criterion | Required value |
|---|---|
| Cloud SQL started and became RUNNABLE | `ALWAYS  RUNNABLE` confirmed before dispatch |
| Scheduler dispatched Cloud Run Job | `gcloud scheduler jobs run` succeeded |
| New execution appeared after dispatch | Execution ID not present in pre-run baseline |
| Execution succeeded | SUCCEEDED condition confirmed in `describe` output |
| Success log confirmed | `jsonPayload.status="ok"` entry exists in Cloud Logging |
| Log timestamp after dispatch | Log entry is newer than the scheduler dispatch time |
| `silver_refresh_success_count` incremented | TOTAL > pre-run baseline from Check 9 |
| Scheduler final state | `PAUSED` |
| Cloud SQL final state | `NEVER  STOPPED` |
| No Pub/Sub publishing | Explicitly stated in evidence |
| No application code changes | Explicitly stated in evidence |
| No deployment | Explicitly stated in evidence |
| Tests pass | 116 passed, 0 failed |
| Ruff clean | All checks passed |
| Evidence document created | `docs/silver-refresh-scheduler-execution-proof-evidence.md` |

---

## 10. Stop Conditions

Abort execution immediately if any of the following occur:

- Cloud SQL is not `NEVER / STOPPED` at the start of the session.
- Cloud SQL fails to start or does not reach `RUNNABLE` within 5 minutes.
- Cloud SQL starts but the Cloud Run Job fails to connect (connection refused in logs).
- The Scheduler is not `PAUSED` at the start of the session.
- `gcloud scheduler jobs run` fails and the fallback also fails.
- The Scheduler remains or transitions to `ENABLED` unexpectedly and cannot be paused.
- No new Cloud Run Job execution appears within 5 minutes of the dispatch command.
- The Cloud Run Job execution fails (non-SUCCEEDED status in `describe`).
- The success log (`jsonPayload.status="ok"`) is absent after 10 minutes.
- `silver_refresh_success_count` does not increment after a 15-minute propagation window.
- Cloud SQL fails to stop — do not leave the session without resolving this.
- Any command would mutate Pub/Sub resources (`market-events-raw`, `market-events-raw-worker-push`,
  `market-events-raw-dlq`).
- Any command would deploy code or update the Cloud Run Job image.
- Repeated retries of a failed execution would increase cost or create metric noise.

---

## 11. What This Runbook Does Not Do

- Does not execute now.
- Does not start Cloud SQL now.
- Does not run or resume the Scheduler now.
- Does not validate anything now.
- Does not create notification channels.
- Does not add Terraform or IaC for any GCP resource.
- Does not validate the 5,000-event load test tier.
- Does not add BigQuery or Dataflow analytical integration.

---

## 12. Roadmap Position

### What this runbook closes (after execution)

After a successful execution branch following this runbook:

- **Scheduled execution proof is closed.** The scheduler configuration gap was closed on
  `exec/silver-refresh-scheduler-validation` (configuration only). This runbook closes the
  remaining gap: a confirmed end-to-end scheduled dispatch with observed success log and metric
  increment.
- **Silver refresh automation is both configured and validated end-to-end.** The full path from
  Cloud Scheduler → Cloud Run Job → `silver.refresh_market_event_minute_aggregates()` →
  `silver.market_event_minute_aggregates` → `/aggregates/minute` will have been exercised under
  real scheduled invocation.

### Remaining gaps after future execution

| Gap | Priority | Notes |
|---|---|---|
| Notification channels | P1 | Alert policies exist but have no delivery targets; email or webhook channel needed before alerts are actionable |
| Terraform / IaC | P1 | All GCP resources created imperatively; no Terraform state |
| 5,000-event load test | P1 | 100 and 1,000 tiers accepted; 5,000-tier not yet executed |
| BigQuery / Dataflow analytical tier | P1 | Silver layer is operational only; no analytical tier |
| CI/CD deploy automation | P1/P2 | All deployments are manual; no automated pipeline |
| README stale GCP wording cleanup | P2 | GCP target architecture section wording predates several completed execution branches |
