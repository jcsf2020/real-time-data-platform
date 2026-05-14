

# dbt Refresh Job Execution Proof Evidence

**Status:** ACCEPTED
**Branch:** `exec/dbt-refresh-job-execution-proof-v3`
**Date:** 2026-05-14
**Execution:** `rtdp-dbt-refresh-job-q6vxp`

---

## Summary

The Terraform-owned Cloud Run Job `rtdp-dbt-refresh-job` was executed successfully against Cloud SQL in a controlled validation window.

The job completed with exit code 0, executed the dbt operational transformation path, ran both silver and gold models, passed all dbt tests, and API readback confirmed that minute and daily aggregates are available through the deployed FastAPI service.

Cloud SQL was returned to `NEVER / STOPPED` immediately after the job execution and again after the API readback window.

---

## Pre-Execution State

| Check | Result |
|---|---|
| Branch | `exec/dbt-refresh-job-execution-proof-v3` |
| Cloud SQL before execution | `NEVER / STOPPED` |
| Cloud Run Job image | `rtdp-dbt-refresh-job:latest` |
| Artifact Registry latest digest | `sha256:ab84213e252dd9f445ef0d237c1a45ebf9f2a7ead4d6104025c70d32de033d95` |
| Terraform plan | `PLAN_EXIT=0` |

---

## Controlled Execution

Cloud SQL was started only for the validation window:

```text
CLOUD_SQL_READY=1
ALWAYS / RUNNABLE
```

Cloud Run Job execution:

```text
Execution [rtdp-dbt-refresh-job-q6vxp] has successfully completed.
JOB_EXIT=0
```

Execution details:

```text
1 task completed successfully
Image: europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-dbt-refresh-job@sha256:ab84213e252dd9f445ef0d237c1a45ebf9f2a7ead4d6104025c70d32de033d95
Task Timeout: 10m
Service account: rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
SQL connections: project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres
```

---

## dbt Run Evidence

The previous no-op selector issue was resolved. The dbt run executed both target models:

```text
dbt_run success
Done. PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=2

1 of 2 OK created sql table model gold.market_event_daily_aggregates ........... [SELECT 7 in 0.42s]
2 of 2 OK created sql table model silver.market_event_minute_aggregates ........ [SELECT 256 in 0.13s]
```

This confirms:

- Gold model ran and produced 7 rows.
- Silver model ran and produced 256 rows.
- `dbt run` was not a no-op.

---

## dbt Test Evidence

```text
dbt_test success
Done. PASS=22 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=22
Completed successfully
```

Final orchestration status:

```text
dbt_run_and_test success
```

---

## API Readback Evidence

API URL:

```text
https://rtdp-api-fpy4of3i5a-ew.a.run.app
```

Minute aggregate readback:

```text
HTTP_STATUS=200
MINUTE_TYPE=list
MINUTE_ROWS=5
MINUTE_SAMPLE=[{"avg_price": 0.45, "event_count": 1, "first_event_timestamp": "2026-05-05T14:00:00Z", "last_event_timestamp": "2026-05-05T14:00:00Z", "symbol": "ADAUSDT", "total_quantity": 100.0, "updated_at": "2026-05-14T16:51:52.071483Z", "window_start": "2026-05-05T14:00:00Z"}]
```

Daily aggregate readback:

```text
HTTP_STATUS=200
DAILY_TYPE=list
DAILY_ROWS=5
DAILY_SAMPLE=[{"avg_price": 0.45, "event_count": 1, "event_date": "2026-05-05", "first_event_timestamp": "2026-05-05T14:00:00Z", "last_event_timestamp": "2026-05-05T14:00:00Z", "max_price": 0.45, "min_price": 0.45, "symbol": "ADAUSDT", "total_quantity": 100.0, "updated_at": "2026-05-14T16:51:51.810347Z"}]
```

---

## Final Safety State

Cloud SQL was stopped immediately after execution and after API readback:

```text
CLOUD_SQL_STOPPED=1
NEVER / STOPPED
```

No scheduler change was made.

No stored functions were removed.

No dbt models were changed during this evidence branch.

No `dbt/profiles.yml` was committed.

No generated dbt artifacts were committed.

---

## Acceptance Criteria

| Criterion | Result |
|---|---|
| Cloud Run Job executed | Passed |
| Job exit code | `0` |
| `dbt run` executed real models | Passed |
| Silver model output | `SELECT 256` |
| Gold model output | `SELECT 7` |
| `dbt test` | `PASS=22 WARN=0 ERROR=0` |
| Final orchestration status | `dbt_run_and_test success` |
| API minute readback | `HTTP 200`, 5 rows |
| API daily readback | `HTTP 200`, 5 rows |
| Cloud SQL returned to stopped | `NEVER / STOPPED` |
| Scheduler unchanged | Confirmed |

---

## Next Step

The dbt operational execution proof is accepted.

Next branch: `feat/dbt-scheduler-switch`

Objective: switch Cloud Scheduler from `rtdp-silver-refresh-job:run` to `rtdp-dbt-refresh-job:run`, validate one scheduled execution, then return the scheduler to paused state.