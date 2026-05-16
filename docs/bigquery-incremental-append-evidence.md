# BigQuery Incremental Append Evidence

**Date:** 2026-05-16
**Branch:** `exec/bigquery-incremental-append-evidence`
**Status:** ACCEPTED

---

## Summary

A cursor-based incremental append job was implemented, deployed, and validated end-to-end.
The job exports delta rows from Cloud SQL `bronze.market_events` into BigQuery
`rtdp_analytics.market_events_raw` using an `ingested_at`-cursor and a BigQuery MERGE for
idempotent, deduplication-safe appends.

Two executions were run within a bounded Cloud SQL window:
- First execution: appended 10 new rows; BigQuery count moved from 6,104 to 6,114.
- Second execution: idempotent; BigQuery count remained 6,114.

---

## Infrastructure Changes

### Terraform — Cloud Run Job (`rtdp-bigquery-append-job`)

New Cloud Run v2 Job added to `infra/terraform/gcp/cloud_run_jobs.tf`:

- Service account: `rtdp-worker-sa`
- Cloud SQL attachment: `project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres` (via `volumes.cloud_sql_instance`)
- `DATABASE_URL` sourced from Secret Manager (`rtdp-database-url`)
- `lifecycle.ignore_changes` on image, annotations, labels to allow independent deploys

### Terraform — BigQuery Staging Table (`market_events_raw_staging`)

New table added to `infra/terraform/gcp/bigquery.tf`:

- `deletion_protection = false` (staging table, cleared between runs)
- Schema identical to `market_events_raw`
- `lifecycle { prevent_destroy }` intentionally omitted (staging table is ephemeral between merges)

Terraform plan after apply:

```
PLAN_EXIT=0
No changes. Your infrastructure matches the configuration.
```

---

## Docker Image

Image: `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-bigquery-append-job:latest`

- Built with `--platform linux/amd64 --provenance=false --sbom=false`
- Manifest type: `application/vnd.docker.distribution.manifest.v2+json` (single manifest)
- Architecture: `linux/amd64`

---

## Code

Package: `apps/bigquery-append-job/src/rtdp_bigquery_append_job/`

Key design decisions:

| Decision | Rationale |
|---|---|
| `DATABASE_URL.strip()` in `resolve_config()` | Secret Manager may append a trailing `\n`; stripping prevents socket path corruption in Cloud SQL unix socket connections |
| `Decimal` → `str` for `price` / `quantity` | psycopg returns PostgreSQL NUMERIC as `decimal.Decimal`; BigQuery `insert_rows_json` requires JSON-serializable types; `str` preserves NUMERIC precision |
| `TRUNCATE TABLE` staging before load and after merge | Staging table is Terraform-managed; `delete_table` / `DROP` would destroy the schema and break subsequent job runs |
| Cursor: `MAX(ingest_timestamp)` from BigQuery | Avoids re-exporting already-synced rows; cursor re-includes the boundary row for idempotent MERGE handling |
| MERGE: `WHEN NOT MATCHED BY TARGET` only | Target is append-only; no `WHEN MATCHED` clause means no updates to existing rows |

---

## Test Suite

30 tests pass (`uv run pytest -q`):

Additions for this feature:
- `test_resolve_config_strips_database_url_trailing_newline` — DATABASE_URL with `\n` produces clean config
- `test_resolve_config_strips_socket_url_trailing_newline` — Cloud SQL socket URL with trailing newline stripped
- `test_resolve_config_strips_env_var_whitespace` — all string env vars stripped
- `test_bq_row_serialization_converts_decimal_to_str` — `Decimal` price/quantity serializes to str for BigQuery NUMERIC
- `test_staging_cleanup_sql_uses_truncate_not_drop` — staging cleanup uses TRUNCATE not DROP/DELETE
- `test_staging_cleanup_sql_references_correct_table` — correct table reference in cleanup SQL
- `test_run_function_does_not_call_delete_table_for_staging` — source code inspection confirms no `delete_table` call

---

## Bounded Validation Window

Cloud SQL was started for the duration of this validation only and returned to `NEVER / STOPPED`
immediately after.

### Evidence Rows (pre-inserted)

10 deterministic rows were inserted into Cloud SQL `bronze.market_events` before any job run:

```
symbol:      EVIDENCEUSDT
event_type:  trade
event_ids:   bq-append-evidence-20260516012325-0001 through -0010
price:       99001.11 to 99011.10
```

Cloud SQL count after insert: **6,114** (was 6,104)

### First Job Execution

Execution: `rtdp-bigquery-append-job-s6ff5`

```
[cursor_resolved]              cursor_ts: 2026-05-07T16:05:37.834191+00:00
[source_export_complete]       row_count: 11
[staging_cleanup_before_load]  TRUNCATE market_events_raw_staging
[staging_load_complete]        row_count: 11
[merge_complete]               success
[duplicate_check_complete]     duplicate_count: 0
[staging_cleanup_after_merge]  TRUNCATE market_events_raw_staging
[append_job_complete]          source_rows_exported: 11, duration_ms: 6061.549
```

`source_rows_exported` is the number of rows exported from Cloud SQL and loaded to staging.
It is not the number of rows inserted into the BigQuery target — the MERGE decides that.

11 rows were exported because the cursor query uses `ingested_at >= cursor` (inclusive), which
re-includes one row already present in BigQuery at the exact cursor boundary. That row was
correctly skipped by the MERGE `WHEN NOT MATCHED BY TARGET` clause.

BigQuery net count: 6,104 → 6,114 (+10 new rows)

### Second Job Execution (Idempotency)

Execution: `rtdp-bigquery-append-job-g49nv`

```
[cursor_resolved]              cursor_ts: 2026-05-16T00:26:19.990326+00:00
[source_export_complete]       row_count: 1
[staging_load_complete]        row_count: 1
[merge_complete]               success
[duplicate_check_complete]     duplicate_count: 0
[append_job_complete]          source_rows_exported: 1, duration_ms: 6454.58
```

1 row was exported from Cloud SQL at the cursor boundary; it was already in the BigQuery target
and was correctly skipped by the MERGE. No new rows were inserted.

BigQuery net count: 6,114 → 6,114 (unchanged, 0 net inserts)

### EVIDENCEUSDT Rows in BigQuery

```sql
SELECT COUNT(*) AS count, symbol
FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`
WHERE symbol = 'EVIDENCEUSDT'
GROUP BY symbol
```

Result: `count=10, symbol=EVIDENCEUSDT`

### Staging Table Post-Job

```
table_id:  market_events_raw_staging
num_rows:  0
```

Staging table exists, empty — correctly truncated after merge.

---

## Safety State

| Resource | State |
|---|---|
| Cloud SQL `rtdp-postgres` | `NEVER / STOPPED` |
| Cloud Scheduler `rtdp-silver-refresh-scheduler` | `PAUSED`, targeting `rtdp-dbt-refresh-job:run` (unchanged) |
| Terraform plan | `PLAN_EXIT=0` |
| BigQuery duplicate check | `0 rows` |
| Staging table | Exists, `num_rows=0` |

---

## Acceptance Criteria

| Criterion | Result |
|---|---|
| Cloud Run Job exists in GCP | PASS — `rtdp-bigquery-append-job` created by Terraform |
| Staging table exists in BigQuery | PASS — `market_events_raw_staging` created by Terraform |
| PLAN_EXIT=0 after apply | PASS |
| First run: BigQuery count = 6,114 | PASS |
| Second run: BigQuery count unchanged (6,114) | PASS |
| Duplicate check returns 0 rows | PASS |
| EVIDENCEUSDT rows present in BigQuery | PASS — 10 rows |
| Staging table survives job run | PASS — table exists, `num_rows=0` |
| Cloud SQL returned to NEVER/STOPPED | PASS |
| Scheduler target unchanged, PAUSED | PASS |
| No credentials in logs | PASS — DATABASE_URL stripped before use; not logged |
