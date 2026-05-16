# BigQuery Append Scheduler Proof Evidence

**Branch:** `exec/bigquery-append-scheduler-proof`  
**Date:** 2026-05-16  
**Author:** João Fonseca

---

## Scope

This document proves that Cloud Scheduler can dispatch the existing BigQuery append
Cloud Run Job (`rtdp-bigquery-append-job`) using the current deployed image. It does
NOT claim autonomous hourly execution over time — only that manual scheduler-triggered
dispatches succeed and are idempotent.

---

## Structure

This document records two attempts:

| Attempt | Status | Reason |
|---|---|---|
| Attempt 1 | **SUPERSEDED** | Executed stale image; logs showed `rows_appended` (old field), violating the current logging contract |
| Attempt 2 | **ACCEPTED** | Executed corrected image; logs show `source_rows_exported` (current field) |

---

## Attempt 1 — SUPERSEDED (Stale Image)

### What happened

The scheduler was triggered twice against the live `rtdp-bigquery-append-job:latest`
image at the time. Executions succeeded and BQ count increased correctly, but the
`append_job_complete` log entry used the field name `rows_appended` instead of
`source_rows_exported`. This is the old log contract; the repository source code
and tests require `source_rows_exported`.

```
apps/bigquery-append-job/src/rtdp_bigquery_append_job/__init__.py:479
    "source_rows_exported": len(bq_rows_json),

tests/test_bigquery_append_job.py:436
    assert "rows_appended" not in source
```

The deployed image was therefore outdated relative to merged main code.

### Attempt 1 executions

| Field | Execution A | Execution B |
|---|---|---|
| Name | `rtdp-bigquery-append-job-rfsmz` | `rtdp-bigquery-append-job-s6fdg` |
| Created | 2026-05-16T09:54:30Z | 2026-05-16T09:57:11Z |
| Status | Completed / True | Completed / True |
| Log field | `rows_appended` ❌ | `rows_appended` ❌ |

### Attempt 1 BigQuery results

| Checkpoint | Count |
|---|---|
| Baseline | 6,114 |
| After execution A | 6,117 (+3) |
| After execution B | 6,117 (unchanged) |

Scheduler dispatch and idempotency mechanics were correct; only the deployed image
was stale. Attempt 1 is retained as partial evidence of the dispatch mechanism but
is NOT the accepted proof.

---

## Image Rebuild and Deployment

The corrected image was built from the current branch (SHA `3e0db6f`) and pushed
to Artifact Registry:

```
docker build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -f apps/bigquery-append-job/Dockerfile \
  -t europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-bigquery-append-job:3e0db6f \
  -t europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-bigquery-append-job:latest \
  .
```

Image manifest verified as single-arch (`application/vnd.docker.distribution.manifest.v2+json`,
not an OCI index). Both tags pushed with digest:

```
sha256:3567572d27fffa4c663ad0dedcb89c7ca7a15b2ccee229ac9bdfd5aefe65fd69
```

Cloud Run Job updated:

```
gcloud run jobs update rtdp-bigquery-append-job \
  --region=europe-west1 \
  --image=europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-bigquery-append-job:latest
```

---

## Attempt 2 — ACCEPTED (Corrected Image)

### Preflight state for Attempt 2

| Item | Value |
|---|---|
| Git branch | `exec/bigquery-append-scheduler-proof` |
| Git status | Clean |
| Terraform PLAN_EXIT | 0 |
| Cloud SQL `rtdp-postgres` | NEVER / STOPPED (before start) |
| `rtdp-bigquery-append-scheduler` | PAUSED |
| Scheduler target | `rtdp-bigquery-append-job:run` |
| `rtdp-silver-refresh-scheduler` | PAUSED |
| Silver scheduler target | `rtdp-dbt-refresh-job:run` |
| BigQuery baseline for Attempt 2 | 6,117 rows |
| Staging table `market_events_raw_staging` | exists, numRows=0 |

### Evidence rows inserted

Three deterministic rows inserted into `bronze.market_events` via Cloud SQL Auth
Proxy (no credential values printed):

| event_id | symbol | event_type | event_timestamp |
|---|---|---|---|
| `scheduler-proof-v2-20260516-1` | SCHEDULERPROOFV2USDT | trade | 2026-05-16 11:00:00+00 |
| `scheduler-proof-v2-20260516-2` | SCHEDULERPROOFV2USDT | trade | 2026-05-16 11:00:01+00 |
| `scheduler-proof-v2-20260516-3` | SCHEDULERPROOFV2USDT | trade | 2026-05-16 11:00:02+00 |

Inserted with `ON CONFLICT DO NOTHING`. Verified: 3 rows in `bronze.market_events`.

### Scheduler dispatch procedure

Because `gcloud scheduler jobs run` requires `state=ENABLED`, each trigger used
the sequence: **resume → run → pause**. The scheduler was re-paused immediately
after each trigger and confirmed PAUSED before the execution completed.

```
# Each trigger:
gcloud scheduler jobs resume rtdp-bigquery-append-scheduler --location=europe-west1
gcloud scheduler jobs run    rtdp-bigquery-append-scheduler --location=europe-west1
gcloud scheduler jobs pause  rtdp-bigquery-append-scheduler --location=europe-west1
```

---

### V2 Trigger 1

**Trigger time:** 2026-05-16T10:09:00Z UTC

**Execution:**

| Field | Value |
|---|---|
| Execution name | `rtdp-bigquery-append-job-p9hkt` |
| Created | 2026-05-16T10:09:44Z |
| Status | `Completed / True` |
| Duration | 7,444 ms |

**Application logs (corrected image):**

```
cursor_resolved:                cursor_ts=2026-05-16T09:47:44.222493+00:00
source_export_complete:         row_count=6
staging_cleanup_before:         TRUNCATE market_events_raw_staging  [success]
staging_load_complete:          row_count=6
merge_complete:                 status=success
duplicate_check_complete:       duplicate_count=0
staging_cleanup_after:          TRUNCATE market_events_raw_staging  [success]
append_job_complete:            source_rows_exported=6, status=success, duration_ms=7444.775
```

`rows_appended` does NOT appear. `source_rows_exported` is confirmed. ✓

Note: 6 rows exported (3 SCHEDULERPROOFV2USDT + 3 SCHEDULERPROOFUSDT still within
cursor window). MERGE `WHEN NOT MATCHED` inserted only the 3 net-new v2 rows;
the 3 v1 rows were already in BQ.

**BigQuery after V2 Trigger 1:**

| Metric | Value |
|---|---|
| Total count | **6,120** (+3 from 6,117) |
| SCHEDULERPROOFV2USDT rows | **3** |
| Duplicate check (HAVING cnt > 1) | **0 rows** |
| Staging table numRows | **0** |
| Scheduler state | **PAUSED** |
| Silver scheduler state | **PAUSED** |

---

### V2 Trigger 2 (Idempotency)

**Trigger time:** 2026-05-16T10:10:57Z UTC

**Execution:**

| Field | Value |
|---|---|
| Execution name | `rtdp-bigquery-append-job-7pn6g` |
| Created | 2026-05-16T10:11:31Z |
| Status | `Completed / True` |
| Duration | 6,668 ms |

**Application logs (corrected image):**

```
cursor_resolved:                cursor_ts=2026-05-16T10:08:49.141452+00:00
source_export_complete:         row_count=3
staging_cleanup_before:         TRUNCATE market_events_raw_staging  [success]
staging_load_complete:          row_count=3
merge_complete:                 status=success
duplicate_check_complete:       duplicate_count=0
staging_cleanup_after:          TRUNCATE market_events_raw_staging  [success]
append_job_complete:            source_rows_exported=3, status=success, duration_ms=6668.226
```

`rows_appended` does NOT appear. `source_rows_exported` confirmed. ✓
Cursor advanced past the v2 rows; MERGE found all 3 matched, inserted 0 new rows.

**BigQuery after V2 Trigger 2:**

| Metric | Value |
|---|---|
| Total count | **6,120** (unchanged — idempotent) |
| SCHEDULERPROOFV2USDT rows | **3** (unchanged) |
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
| Silver scheduler target | `rtdp-dbt-refresh-job:run` (unchanged) |
| Cloud SQL `rtdp-postgres` | **NEVER / STOPPED** |
| Staging table `market_events_raw_staging` | exists, numRows=0 |
| Git status | **clean** |
| Secrets printed | **None** |

---

## Accepted Proof Summary

| Item | Value |
|---|---|
| Proof type | Manual Cloud Scheduler dispatch of `rtdp-bigquery-append-job` |
| Deployed image SHA | `3e0db6f` (built from current branch) |
| Accepted executions | `rtdp-bigquery-append-job-p9hkt`, `rtdp-bigquery-append-job-7pn6g` |
| BQ before Attempt 2 | 6,117 |
| BQ after V2 trigger 1 | **6,120** (+3 exactly) |
| BQ after V2 trigger 2 | **6,120** (unchanged — idempotent) |
| SCHEDULERPROOFV2USDT rows | **3** |
| Duplicate check | **0** |
| Staging table | exists, numRows=0 |
| Log field confirmed | `source_rows_exported` ✓ (`rows_appended` absent) |
| Scheduler state (final) | **PAUSED** |
| Silver scheduler state (final) | **PAUSED** |
| Cloud SQL final state | **NEVER / STOPPED** |
| Terraform final PLAN_EXIT | **0** |
| Tests | **187 passed** |
| Secrets printed | **None** |
| dbt/profiles.yml | **Absent** |

This evidence proves two successful, controlled, manually-triggered dispatches of the
BigQuery append job via Cloud Scheduler using the corrected deployed image. It does
not claim scheduled autonomous hourly execution has run or been validated over a
sustained period. Attempt 1 is retained in this document for transparency but is
explicitly superseded by Attempt 2.
