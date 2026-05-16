# BigQuery Append Scheduler Proof Evidence

**Branch:** `exec/bigquery-append-scheduler-proof`  
**Date:** 2026-05-16  
**Author:** João Fonseca

---

## Scope

This document proves that Cloud Scheduler can dispatch the existing BigQuery append
Cloud Run Job (`rtdp-bigquery-append-job`). It does NOT claim autonomous hourly
execution over time — only that a manual scheduler-triggered dispatch succeeds and
is idempotent.

---

## Claims

| Claim | Result |
|---|---|
| Scheduler dispatches Cloud Run Job | **Proved** (two manual triggers, both successful) |
| Append is idempotent (no duplicates) | **Proved** (BQ count unchanged on second run; duplicate_count=0) |
| Scheduler remained PAUSED before and after each trigger | **Confirmed** |
| Cloud SQL bounded to proof window only | **Confirmed** (NEVER/STOPPED before and after) |
| No secrets printed | **Confirmed** |
| dbt/profiles.yml absent from repo | **Confirmed** |
| Terraform PLAN_EXIT=0 (final) | **Confirmed** |

---

## Preflight State

| Item | Value |
|---|---|
| Git branch | `exec/bigquery-append-scheduler-proof` |
| Git status | Clean |
| Terraform PLAN_EXIT | 0 |
| Cloud SQL `rtdp-postgres` | NEVER / STOPPED |
| `rtdp-bigquery-append-scheduler` state | PAUSED |
| Scheduler target | `rtdp-bigquery-append-job:run` |
| Scheduler schedule | `0 * * * *` Europe/Lisbon |
| `rtdp-silver-refresh-scheduler` state | PAUSED |
| Silver scheduler target | `rtdp-dbt-refresh-job:run` |
| BigQuery `market_events_raw` baseline | 6,114 rows |
| Staging table `market_events_raw_staging` | exists, numRows=0 |

---

## Procedure

### 1. Cloud SQL Started (bounded window)

```
gcloud sql instances patch rtdp-postgres --activation-policy=ALWAYS --quiet
```

Polled until `state=RUNNABLE` at 2026-05-16T10:46:04 WEST.

### 2. Evidence Rows Inserted

Three deterministic rows inserted into `bronze.market_events` via Cloud SQL Auth Proxy
(port 5434 → `project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres`):

| event_id | symbol | event_type | event_timestamp |
|---|---|---|---|
| `scheduler-proof-20260516-1` | SCHEDULERPROOFUSDT | trade | 2026-05-16 10:00:00+00 |
| `scheduler-proof-20260516-2` | SCHEDULERPROOFUSDT | trade | 2026-05-16 10:00:01+00 |
| `scheduler-proof-20260516-3` | SCHEDULERPROOFUSDT | trade | 2026-05-16 10:00:02+00 |

Inserted with `ON CONFLICT DO NOTHING`. Cloud SQL Auth Proxy used; no credential
values printed.

Verification from Cloud SQL before trigger:
```sql
SELECT COUNT(*) FROM bronze.market_events WHERE event_id LIKE 'scheduler-proof-20260516-%'
-- Result: 3
```

### 3. BigQuery Count Before First Trigger

```
SELECT COUNT(*) FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`
-- Result: 6,114
```

---

## First Scheduler Trigger

**Trigger time:** 2026-05-16T09:54:28Z UTC

Because `gcloud scheduler jobs run` requires `state=ENABLED`, the scheduler was
temporarily resumed, triggered, then immediately re-paused:

```
gcloud scheduler jobs resume rtdp-bigquery-append-scheduler --location=europe-west1
gcloud scheduler jobs run    rtdp-bigquery-append-scheduler --location=europe-west1
gcloud scheduler jobs pause  rtdp-bigquery-append-scheduler --location=europe-west1
```

Scheduler state confirmed PAUSED immediately after trigger.

### Cloud Run Job Execution 1

| Field | Value |
|---|---|
| Execution name | `rtdp-bigquery-append-job-rfsmz` |
| Created | 2026-05-16T09:54:30.409006Z |
| Status | `Completed / True` |
| Duration | 7,323 ms |

### Application Logs (Execution 1)

```
cursor_resolved:             cursor_ts=2026-05-16T00:26:19.990326+00:00
source_export_complete:      row_count=4
staging_cleanup_before:      TRUNCATE market_events_raw_staging
staging_load_complete:       row_count=4
merge_complete:              status=success
duplicate_check_complete:    duplicate_count=0
staging_cleanup_after:       TRUNCATE market_events_raw_staging
append_job_complete:         rows_appended=4, status=success, duration_ms=7323.633
```

Note: 4 rows were exported from Cloud SQL (3 SCHEDULERPROOFUSDT + 1 pre-existing row
whose `ingested_at` exceeded the cursor but whose `event_id` already existed in BQ).
The MERGE `WHEN NOT MATCHED` condition inserted only the 3 net-new rows, producing
an exact +3 increase.

### BigQuery After First Trigger

| Metric | Value |
|---|---|
| Total count | **6,117** (+3 from baseline 6,114) |
| SCHEDULERPROOFUSDT rows | **3** |
| Duplicate check (HAVING cnt > 1) | **0 rows** |
| Staging table numRows | **0** |
| Scheduler state | **PAUSED** |
| Silver scheduler state | **PAUSED** |

---

## Second Scheduler Trigger (Idempotency)

**Trigger time:** 2026-05-16T09:57:10Z UTC

Same resume → run → pause sequence:

```
gcloud scheduler jobs resume rtdp-bigquery-append-scheduler --location=europe-west1
gcloud scheduler jobs run    rtdp-bigquery-append-scheduler --location=europe-west1
gcloud scheduler jobs pause  rtdp-bigquery-append-scheduler --location=europe-west1
```

Scheduler state confirmed PAUSED immediately after trigger.

### Cloud Run Job Execution 2

| Field | Value |
|---|---|
| Execution name | `rtdp-bigquery-append-job-s6fdg` |
| Created | 2026-05-16T09:57:11.482322Z |
| Status | `Completed / True` |
| Duration | 7,005 ms |

### Application Logs (Execution 2)

```
cursor_resolved:             cursor_ts=2026-05-16T09:47:44.222493+00:00
source_export_complete:      row_count=3
staging_cleanup_before:      TRUNCATE market_events_raw_staging
staging_load_complete:       row_count=3
merge_complete:              status=success
duplicate_check_complete:    duplicate_count=0
staging_cleanup_after:       TRUNCATE market_events_raw_staging
append_job_complete:         rows_appended=3, status=success, duration_ms=7005.138
```

The cursor advanced to the `ingest_timestamp` of the SCHEDULERPROOFUSDT rows
(~09:47 UTC). The MERGE found all 3 already present (`event_id` matched) and
inserted 0 new rows.

### BigQuery After Second Trigger

| Metric | Value |
|---|---|
| Total count | **6,117** (unchanged) |
| SCHEDULERPROOFUSDT rows | **3** (unchanged) |
| Duplicate check (HAVING cnt > 1) | **0 rows** |
| Staging table numRows | **0** |
| Scheduler state | **PAUSED** |
| Silver scheduler state | **PAUSED** |

---

## Cloud SQL Returned to Safe State

```
gcloud sql instances patch rtdp-postgres --activation-policy=NEVER --quiet
```

Final state verified:

```
settings.activationPolicy: NEVER
state:                     STOPPED
```

---

## Final Validations

| Check | Result |
|---|---|
| `terraform fmt -check -recursive infra/terraform/gcp` | FMT_EXIT=0 |
| `terraform -chdir=infra/terraform/gcp validate` | Success, configuration is valid |
| `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode` | **PLAN_EXIT=0** |
| `uv run pytest -q` | **187 passed** |
| `uv run ruff check .` | All checks passed |
| `test ! -f dbt/profiles.yml` | **REPO_DBT_PROFILE_ABSENT=true** |
| `rtdp-bigquery-append-scheduler` state | **PAUSED** |
| `rtdp-silver-refresh-scheduler` state | **PAUSED** |
| Cloud SQL `rtdp-postgres` | **NEVER / STOPPED** |
| Git status | **clean** |

---

## Summary

| Item | Value |
|---|---|
| Proof type | Manual Cloud Scheduler dispatch of `rtdp-bigquery-append-job` |
| Executions | 2 (`rtdp-bigquery-append-job-rfsmz`, `rtdp-bigquery-append-job-s6fdg`) |
| BQ before | 6,114 |
| BQ after first trigger | 6,117 (+3 exactly) |
| BQ after second trigger | 6,117 (unchanged — idempotent) |
| SCHEDULERPROOFUSDT rows | 3 |
| Duplicate check | 0 |
| Staging table | exists, numRows=0 |
| Scheduler state (final) | PAUSED |
| Silver scheduler state (final) | PAUSED |
| Cloud SQL final state | NEVER / STOPPED |
| Terraform final PLAN_EXIT | 0 |
| Tests | 187 passed |
| Secrets printed | None |
| dbt/profiles.yml | Absent |

This evidence proves a single, controlled, manually-triggered dispatch of the
BigQuery append job via Cloud Scheduler. It does not claim scheduled autonomous
hourly execution has run or been validated over a sustained period.
