# dbt Observability Metrics Plan

**Status:** PLAN -- dbt transformation-layer observability metrics for the validated GCP data platform
**Date:** 2026-05-22
**Branch:** `docs/dbt-observability-metrics-plan`
**Author intent:** Rigorous analytics engineering strategy. No unsupported claims. No implementation on this branch.

---

## 1. Context

### Current Validated dbt Path

The Real-Time Data Platform operates on the following proven transformation path:

```
Cloud SQL PostgreSQL (rtdp-postgres, bronze.market_events)
  → rtdp-dbt-refresh-job (Cloud Run Job, delete+insert incremental strategy)
    → Cloud SQL silver.market_event_minute_aggregates
    → Cloud SQL gold.market_event_daily_aggregates
```

The silver model (`silver_market_event_minute_aggregates`) aggregates `bronze.market_events` by
`(symbol, minute window)` using a 10-minute lookback guard. The gold model
(`gold_market_event_daily_aggregates`) aggregates `bronze.market_events` by `(symbol, calendar date)`
using a 3-day lookback guard. Both models use `materialized='incremental'`,
`incremental_strategy='delete+insert'`, and a `COALESCE` fallback to ensure cold-start safety.

The `rtdp-dbt-refresh-job` Cloud Run Job executes `dbt run` followed by `dbt test` against
the `cloudsql` dbt profile target. The job is deployed via Terraform and is triggered either
manually (`gcloud run jobs execute --wait`) or by the `rtdp-silver-refresh-scheduler` Cloud
Scheduler job (currently `PAUSED` by default).

### Current Evidence

| Evidence item | Value |
|---|---|
| dbt run result | `PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=2` |
| dbt test result | `PASS=22 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=22` |
| Execution ID | `rtdp-dbt-refresh-job-gqrl8` |
| Execution duration | `1m17.25s` |
| Gold model output | `INSERT 0 7` (7 daily aggregate rows) |
| Silver model output | `INSERT 0 13` (13 minute aggregate rows) |
| Cloud SQL final state | `STOPPED / NEVER` |
| Schedulers final state | `PAUSED` |
| Terraform PLAN_EXIT | `0` |

All dbt execution evidence is documented in
[docs/dbt-cloud-sql-incremental-execution-proof.md](dbt-cloud-sql-incremental-execution-proof.md).

### Why dbt Observability Matters

dbt provides the transformation layer that converts raw, append-only `bronze.market_events`
into analytically useful silver and gold tables. Without observability:

- A failed `dbt run` may go undetected until a downstream consumer reads stale data.
- A model that produces fewer rows than expected (due to a lookback gap, a schema drift, or a
  source truncation) is invisible without a row-count metric.
- A dbt test failure on `unique_combination_of_columns` means the silver or gold uniqueness
  contract has been violated — but without alerting, no operator is notified.
- Model freshness lag accumulates silently. An analyst querying
  `silver.market_event_minute_aggregates` two hours after the last successful run does not
  know whether the data is fresh or stale.

For a portfolio project, documented dbt observability demonstrates analytics engineering
credibility: the ability to not only build transformation models but also specify how those
models should be monitored in production.

### This Is a Docs-Only Branch

This branch (`docs/dbt-observability-metrics-plan`) is documentation only. It does not:

- Implement any Cloud Monitoring custom metrics.
- Modify any dbt model, schema, or test files.
- Modify any Terraform resource definitions.
- Start Cloud SQL or resume Cloud Scheduler jobs.
- Execute any `terraform apply` operations.
- Push any metric time series to Cloud Monitoring.
- Create any alert policies or dashboards in GCP.

All metric names, alert policies, dashboard panels, and runbook skeletons in this document
are proposed future implementation targets. None are implemented.

---

## 2. Definitions

| Term | Definition |
|---|---|
| **dbt observability** | The practice of collecting, emitting, and monitoring signals from dbt job execution so that model failures, staleness, data drift, and test violations are detected promptly by operators rather than discovered by downstream consumers. |
| **Model freshness** | The elapsed time between the last successful incremental run for a given model and the current wall-clock time. A freshness lag above a defined threshold indicates that the silver or gold table may reflect a stale state of the source data. |
| **Model row count** | The total number of rows in a silver or gold model table after a successful dbt run. Used as a baseline health signal; unexpected drops or anomalous changes indicate source data issues or lookback window misconfiguration. |
| **Test pass rate** | The fraction of dbt tests that passed in a given execution, expressed as a percentage: `(passed_tests / total_tests) * 100`. A test pass rate below 100% indicates a data contract violation on at least one model or source. |
| **Transformation health** | The combined signal of run success rate, test pass rate, model freshness, and row-count stability across the dbt layer. A transformation layer is considered healthy when all runs pass, all tests pass, freshness lag is within threshold, and row counts are stable. |
| **Source-to-target drift** | The difference between the row count (or aggregate values) in the source table (`bronze.market_events`) and the expected downstream count in silver or gold after a successful run. Drift indicates data loss, lookback misconfiguration, or schema skew. |
| **Run duration** | The wall-clock elapsed time for a `dbt run` or `dbt test` execution. Anomalous increases in run duration signal database performance degradation, lookback window growth, or unexpected full-table scans. |
| **Artifact-based observability** | The practice of parsing dbt's output artifacts (`run_results.json`, `manifest.json`) after each execution to extract structured signals (model-level status, test-level status, row counts, durations) rather than relying solely on job-level exit codes. |
| **Metric emission** | The act of pushing a named, typed, labelled time-series data point to a monitoring backend (Cloud Monitoring in this platform) after each dbt execution, enabling threshold alerting and dashboard visualisation. |
| **Alert threshold** | The numeric boundary at which a metric value triggers a notification to an operator. Example: model freshness lag exceeding 90 minutes triggers a SEV2 alert. |
| **SLO for transformation layer** | An internal engineering target specifying acceptable dbt job success rates, model freshness bounds, test pass targets, and row-count drift tolerances. These are aspirational operational targets, not contractual commitments. |

---

## 3. Current dbt Evidence Baseline

| Capability | Evidence | Current status | Limitation |
|---|---|---|---|
| dbt incremental execution against Cloud SQL | `rtdp-dbt-refresh-job-gqrl8`; execution `2026-05-19T18:51:50Z`; `dbt-cloud-sql-incremental-execution-proof.md` | VALIDATED | Bounded controlled validation; not a sustained production workload claim; 7 gold rows and 13 silver rows reflect existing test data set |
| dbt run PASS=2 | `Done. PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=2`; `dbt-cloud-sql-incremental-execution-proof.md` | VALIDATED | Two models only (`silver_market_event_minute_aggregates`, `gold_market_event_daily_aggregates`); no staging/prod split; single bounded execution |
| dbt test PASS=22 | `Done. PASS=22 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=22`; `dbt-cloud-sql-incremental-execution-proof.md` | VALIDATED | 22 tests passing on current test data set; no test failure injection proof; no ongoing test execution monitoring |
| silver model | `silver.market_event_minute_aggregates`; `delete+insert`; `unique_key=['symbol', 'window_start']`; 10-minute lookback; `dbt-incremental-silver-evidence.md` | VALIDATED -- CLOUD SQL LIVE | Lookback window covers 10 minutes; late-arriving events outside this window are not reprocessed; no freshness alert implemented |
| gold model | `gold.market_event_daily_aggregates`; `delete+insert`; `unique_key=['symbol', 'event_date']`; 3-day lookback; `dbt-incremental-gold-evidence.md` | VALIDATED -- CLOUD SQL LIVE | Lookback window covers 3 days; events older than 3 days since last run are not reprocessed; no freshness alert implemented |
| Cloud Run job execution path | `rtdp-dbt-refresh-job`; Terraform-managed; Cloud Run Job v2; region `europe-west1`; `dbt-refresh-cloud-run-deploy-evidence.md` | VALIDATED | Job-level exit code is the only currently observable signal; no model-level metrics emitted |
| BigQuery quality checks | 6/6 checks pass against `rtdp_analytics.market_events_raw`; Cloud Monitoring custom metrics emitted; alert policy OPEN incident and email notification proven; `bigquery-quality-incident-notification-delivery-proof.md` | VALIDATED | BigQuery quality observability is adjacent to dbt; it monitors the BigQuery analytical tier, not the dbt transformation layer; no cross-layer row-count comparison |
| Cloud Monitoring alerting capability | Alert policy `RTDP BigQuery Quality Failure`; email channel `RTDP Operator Email Alerts`; incident OPEN state proven via CLI; email delivery proven via Gmail inbox screenshot; `bigquery-quality-incident-notification-delivery-proof.md` | VALIDATED | This is the *platform* alerting capability; no dbt-specific alert policy exists yet |
| Replay/backfill strategy | `docs/replay-backfill-strategy.md`; documents Cloud SQL as operational source of truth; dbt rebuild path skeleton documented | DOCUMENTED -- DOCS-ONLY | No automated replay consumer implemented; dbt full-refresh rebuild runbook is a skeleton, not an executed command |

---

## 4. dbt Observability Gap Register

| Gap | Current status | Operational risk | Recruitment value | Priority | Recommended future branch/action |
|---|---|---|---|---|---|
| No dbt run duration metric | Not implemented | Silent performance degradation goes undetected; long-running jobs indicate full scans or lookback growth | Medium -- shows production-readiness thinking | P1 | `feat/dbt-metric-emission-script` -- emit `dbt_run_duration_seconds` from artifact parse |
| No dbt test pass/fail metric in Cloud Monitoring | Not implemented | Test failures are invisible to Cloud Monitoring; no alert is triggered; no operator notification | High -- test observability is a core analytics engineering signal | P1 | `feat/dbt-metric-emission-script` -- emit `dbt_test_pass_count`, `dbt_test_failure_count` |
| No model freshness metric | Not implemented | Stale silver and gold tables are invisible; downstream analysts query outdated aggregates without warning | High -- freshness is the most interview-critical dbt observability concept | P1 | `feat/dbt-freshness-metric` -- compute elapsed time since last successful run; emit to Cloud Monitoring |
| No silver/gold row-count drift metric | Not implemented | Row-count drops caused by lookback misconfiguration or source truncation are undetected | High -- silent data loss is a critical production failure | P1 | `feat/dbt-metric-emission-script` -- parse `run_results.json` for row counts; emit `dbt_model_rows_total` |
| No dbt artifact ingestion | Not implemented | Structured model-level and test-level signals are discarded after each execution; no history, no trend | Medium -- artifact ingestion is a senior-level analytics engineering practice | P2 | `feat/dbt-artifact-store` -- copy `run_results.json` to GCS after each execution |
| No dbt run history table | Not implemented | Cannot answer "how many times did the dbt job fail last week?" without manual log inspection | Medium -- run history supports SLO burn-rate calculation | P2 | `feat/dbt-run-history` -- append parsed run metadata to a BigQuery `dbt_run_log` table |
| No dbt-specific alert policy | Not implemented | No Cloud Monitoring alert is triggered by dbt failures; operator is not notified | High -- alert coverage gap in the transformation layer | P1 | `feat/dbt-alert-policies` -- add Terraform `google_monitoring_alert_policy` for `dbt_run_failure_count > 0` |
| No model-level SLO | Not implemented | Cannot determine whether the transformation layer is within or outside an error budget | Medium -- model SLOs support production credibility claims | P3 | `docs/dbt-model-slo-definition` -- define freshness, test pass, and row-count SLOs per model |
| No failed model ownership mapping | Not implemented | When a model fails, there is no documented mapping from model name to responsible team or engineer | Low -- relevant for multi-team platform scenarios | P3 | `docs/dbt-ownership-register` -- document model-to-owner mapping |
| No source-to-target reconciliation metric | Not implemented | Row-count differences between `bronze.market_events` and `silver`/`gold` targets are not measured | High -- source-to-target drift is a data quality correctness signal | P2 | `feat/dbt-reconciliation-script` -- compare bronze count vs silver/gold counts after each run |
| No dbt full-refresh validation evidence | Not executed | The incremental path is proven; the full-refresh path (required for schema changes or historical rebuilds) has no live execution evidence | Medium -- full-refresh safety is expected to be demonstrable in production | P2 | `exec/dbt-full-refresh-validation` -- execute `dbt run --full-refresh` under controlled window; capture evidence |
| No model staleness detection | Not implemented | A model whose `updated_at` column has not advanced within a threshold is not automatically flagged | Medium -- staleness detection prevents silent freshness failures | P2 | `feat/dbt-freshness-metric` -- compare `MAX(updated_at)` from model against current time |
| No transformation-layer dashboard | Not implemented | There is no Cloud Monitoring or third-party dashboard panel showing dbt model health, freshness, or test status | Medium -- dashboard demonstrates production-readiness posture | P3 | `feat/dbt-dashboard` -- add Cloud Monitoring dashboard JSON with dbt metric panels |

---

## 5. Proposed Metrics

The following metrics are proposed future implementation targets. None are currently implemented.
All metric names follow the convention `custom.googleapis.com/rtdp/dbt/<metric_name>`.

| Metric name | Metric type | Source | Labels | Collection method | Alert threshold | Why it matters |
|---|---|---|---|---|---|---|
| `dbt_run_success_count` | CUMULATIVE / INT64 | `run_results.json` `.results[].status == "success"` aggregated to run level | `job_name`, `environment` | Parse artifact post-run; push via `push_dbt_metrics.py` | N/A (counter; alert on absence) | Confirms a successful end-to-end dbt run completed |
| `dbt_run_failure_count` | CUMULATIVE / INT64 | `run_results.json` run-level status `error` | `job_name`, `environment` | Parse artifact post-run; push via `push_dbt_metrics.py` | `> 0` → SEV2 alert | Primary signal for "dbt job failed" alert policy |
| `dbt_run_duration_seconds` | GAUGE / DOUBLE | `run_results.json` `elapsed_time` | `job_name`, `environment` | Parse artifact post-run; push via `push_dbt_metrics.py` | `> 300s` → SEV3 anomaly | Detects performance degradation or unexpected full-table scans |
| `dbt_model_rows_total` | GAUGE / INT64 | `run_results.json` `.results[].adapter_response.rows_affected` | `job_name`, `model_name`, `schema`, `environment` | Parse artifact post-run; push per model | Model-specific; alert if drops `> 50%` vs baseline | Detects row-count collapse caused by lookback gap or source truncation |
| `dbt_model_freshness_lag_minutes` | GAUGE / DOUBLE | `MAX(updated_at)` from target table vs `NOW()` | `model_name`, `schema`, `environment` | Separate freshness query script; run after each dbt execution | `> 90 minutes` → SEV2 alert | Detects stale silver/gold tables before downstream consumers do |
| `dbt_test_pass_count` | GAUGE / INT64 | `run_results.json` `.results[].status == "pass"` where `node_type == "test"` | `job_name`, `environment` | Parse artifact post-run; push via `push_dbt_metrics.py` | N/A (used in pass rate calculation) | Tracks test health trend over executions |
| `dbt_test_failure_count` | GAUGE / INT64 | `run_results.json` `.results[].status == "fail"` where `node_type == "test"` | `job_name`, `environment` | Parse artifact post-run; push via `push_dbt_metrics.py` | `> 0` → SEV1 alert | Any dbt test failure is a data contract violation; immediate operator action required |
| `dbt_test_pass_rate` | GAUGE / DOUBLE | Derived: `dbt_test_pass_count / (dbt_test_pass_count + dbt_test_failure_count) * 100` | `job_name`, `environment` | Compute at push time | `< 100%` → SEV1 alert | Single metric capturing the overall test contract health |
| `dbt_model_row_count_delta` | GAUGE / INT64 | Difference between current `dbt_model_rows_total` and previous run's value | `model_name`, `schema`, `environment` | Compute from consecutive artifact observations | `< -20% vs prior run` → SEV2 alert | Detects unexpected row-count regression between runs |
| `dbt_source_to_target_drift_count` | GAUGE / INT64 | Absolute difference: `COUNT(*) FROM bronze.market_events` minus expected coverage in silver/gold | `source_table`, `target_model`, `environment` | Separate reconciliation script post-run | `> 0 unexplained rows` → SEV2 alert | Detects rows present in bronze that are not covered by the target model |
| `dbt_full_refresh_required_flag` | GAUGE / INT64 | Manual or heuristic signal: `0` = incremental is healthy; `1` = full-refresh is required | `model_name`, `environment` | Set by operator or by staleness detection script | `== 1` → SEV2 alert | Signals that the incremental path is insufficient and a controlled full-refresh window must be opened |
| `dbt_artifact_parse_error_count` | GAUGE / INT64 | Exception count from the metric emission script when parsing `run_results.json` | `job_name`, `environment` | Emitted by `push_dbt_metrics.py` on exception | `> 0` → SEV3 alert | Detects malformed or missing artifacts; prevents silent loss of observability |

---

## 6. Artifact Strategy

### Overview

dbt produces a set of structured output artifacts after each execution. These artifacts
contain model-level execution metadata, compiled SQL, test results, and source freshness
information. Artifact-based observability is more granular than job-level exit codes and
is the standard approach used in production dbt environments.

### Artifact Inventory

| Artifact | Location (default) | What it provides | What should NOT be logged |
|---|---|---|---|
| `run_results.json` | `dbt/target/run_results.json` | Per-node execution status (`success`, `error`, `fail`), elapsed time, row counts from `adapter_response`, error messages | Raw SQL query results, credential values, database connection strings, PII from row data |
| `manifest.json` | `dbt/target/manifest.json` | Node graph: model names, test names, sources, dependencies, compiled SQL references, schema/alias config | Compiled SQL queries may contain literal filter values; do not log full compiled SQL in high-cardinality environments |
| `sources.json` | `dbt/target/sources.json` | Source freshness results if `dbt source freshness` is run; `max_loaded_at`, `snapshotted_at`, `criteria`, `status` | Not applicable unless `dbt source freshness` is explicitly added to the job |
| Compiled SQL (`target/compiled/`) | `dbt/target/compiled/` | Rendered SQL for each model and test, useful for debugging | Must not be committed to source control unreviewed; may contain schema names, filter literals, and hardcoded values |
| Structured logs (`logs/dbt.log`) | `dbt/logs/dbt.log` | Verbose execution log; model timing, SQL execution, test output | Full SQL execution output; connection debug logs; may contain row-level data samples on test failures |

### Where Artifacts Could Be Stored

Proposed future storage path (not implemented):

- After each `rtdp-dbt-refresh-job` execution, the Cloud Run container could copy
  `target/run_results.json` and `target/manifest.json` to a GCS bucket
  (`gs://rtdp-dbt-artifacts/{execution_id}/`).
- A post-execution script (`scripts/push_dbt_metrics.py`) would parse the artifacts from GCS
  and push structured time-series to Cloud Monitoring.
- Optionally, a BigQuery `dbt_run_log` table could receive one row per execution with
  aggregated metadata (execution ID, run time, pass/fail counts, model-level row counts).

### How Artifacts Could Be Parsed

`run_results.json` is a JSON file with the following structure:

```json
{
  "metadata": {"generated_at": "...", "dbt_schema_version": "..."},
  "elapsed_time": 77.25,
  "results": [
    {
      "unique_id": "model.rtdp.silver_market_event_minute_aggregates",
      "status": "success",
      "execution_time": 12.3,
      "adapter_response": {"rows_affected": 13},
      "failures": null,
      "message": "INSERT 0 13"
    }
  ]
}
```

A parsing script would iterate over `results`, extract `status`, `execution_time`,
`adapter_response.rows_affected`, and `unique_id`, and emit corresponding Cloud Monitoring
time-series data points per model.

### Why No Artifact Ingestion Is Implemented Yet

Artifact ingestion is not implemented on this branch. The rationale:

1. This branch is docs-only. No Python, Terraform, or workflow changes are in scope.
2. The Cloud Run Job container does not currently copy artifacts out of the execution
   environment. Artifacts are ephemeral and lost when the container exits.
3. A GCS artifact bucket and a Cloud Monitoring metric emission step in the job would require
   a new Terraform resource (`google_storage_bucket.dbt_artifacts`) and a new IAM binding
   (`roles/storage.objectCreator` for the dbt job service account). This must be scoped to
   a future implementation branch.
4. A `push_dbt_metrics.py` script analogous to the existing
   `scripts/push_bigquery_quality_metrics.py` is the recommended implementation pattern; it
   does not exist yet.

---

## 7. Cloud Monitoring Design

### Proposed Integration Architecture

The following describes the proposed future Cloud Monitoring integration for dbt metrics.
Nothing described here is currently implemented.

```
rtdp-dbt-refresh-job (Cloud Run Job)
  → dbt run + dbt test
    → target/run_results.json (artifact, ephemeral in container)
      → scripts/push_dbt_metrics.py (post-execution step in container entrypoint)
        → Cloud Monitoring custom metrics (custom.googleapis.com/rtdp/dbt/*)
          → Alert policies (google_monitoring_alert_policy)
            → email channel (RTDP Operator Email Alerts)
```

### Monitored Resource Type

Proposed resource type: `generic_task` with labels:
- `project_id`: `project-42987e01-2123-446b-ac7`
- `location`: `europe-west1`
- `namespace`: `rtdp`
- `job`: `rtdp-dbt-refresh-job`
- `task_id`: Cloud Run execution ID (e.g., `rtdp-dbt-refresh-job-gqrl8`)

This mirrors the approach proven in `scripts/push_bigquery_quality_metrics.py`, which uses
`generic_task` for BigQuery quality metric emission.

### Metric Labels

All proposed dbt metrics would carry:

| Label key | Example value | Purpose |
|---|---|---|
| `job_name` | `rtdp-dbt-refresh-job` | Disambiguates from other future dbt jobs |
| `environment` | `cloud_sql_prod` | Maps to the dbt profile target |
| `model_name` | `silver_market_event_minute_aggregates` | Per-model granularity |
| `schema` | `silver` | Schema layer (bronze / silver / gold) |
| `execution_id` | `rtdp-dbt-refresh-job-gqrl8` | Links metric to Cloud Run execution log |

### Proposed Alert Policies

| Policy name | Condition | Severity | Notification channel |
|---|---|---|---|
| `RTDP dbt Run Failure` | `dbt_run_failure_count > 0` in any 5-minute window | SEV2 | `RTDP Operator Email Alerts` (existing channel) |
| `RTDP dbt Test Failure` | `dbt_test_failure_count > 0` in any 5-minute window | SEV1 | `RTDP Operator Email Alerts` |
| `RTDP dbt Model Freshness Lag` | `dbt_model_freshness_lag_minutes > 90` for any model | SEV2 | `RTDP Operator Email Alerts` |
| `RTDP dbt Row Count Drop` | `dbt_model_row_count_delta < -20%` vs prior run | SEV2 | `RTDP Operator Email Alerts` |
| `RTDP dbt Run Duration Anomaly` | `dbt_run_duration_seconds > 300` | SEV3 | `RTDP Operator Email Alerts` |
| `RTDP dbt Artifact Parse Error` | `dbt_artifact_parse_error_count > 0` | SEV3 | `RTDP Operator Email Alerts` |

All alert policies would be managed as `google_monitoring_alert_policy` Terraform resources,
analogous to the existing `google_monitoring_alert_policy.bigquery_quality_failure`.

### Dashboards

A proposed dbt observability dashboard would include the panels described in Section 10.

### Notification Channel Reuse

The existing `RTDP Operator Email Alerts` notification channel (proven in
`bigquery-quality-incident-notification-delivery-proof.md`) can be reused for dbt alert
policies without additional IAM or Terraform changes. The notification channel resource
name is already in Terraform state.

### Relation to Existing BigQuery Quality Alerting

The existing BigQuery quality alerting monitors `rtdp_analytics.market_events_raw` for
row count and freshness. The proposed dbt alerting monitors the dbt transformation layer
(silver and gold) within Cloud SQL. These are complementary but distinct:

- BigQuery quality alerting detects failures in the analytical tier append/MERGE path.
- dbt alerting detects failures in the transformation layer (bronze → silver/gold).
- Cross-layer reconciliation (bronze row count vs gold row count vs BigQuery row count) is
  a separate proposed capability (see `dbt_source_to_target_drift_count` in Section 5).

---

## 8. Model Freshness and Row-Count Drift

### silver.market_event_minute_aggregates Freshness

| Property | Value |
|---|---|
| Model | `silver.market_event_minute_aggregates` |
| Freshness column | `updated_at` (set to `NOW()` at run time) |
| Lookback window | 10 minutes from `MAX(window_start)` |
| Expected run frequency | Every 15 minutes (when `rtdp-silver-refresh-scheduler` is running) |
| Proposed freshness threshold | `> 30 minutes since MAX(updated_at)` → SEV2 alert |
| Cold-start safety | `COALESCE(MAX(window_start) - INTERVAL '10 minutes', TIMESTAMP '1900-01-01')` |
| Late-arriving event caveat | Events arriving more than 10 minutes after their `event_timestamp` may fall outside the lookback window; they will not be picked up until a full-refresh or a wider lookback window is configured |

### gold.market_event_daily_aggregates Freshness

| Property | Value |
|---|---|
| Model | `gold.market_event_daily_aggregates` |
| Freshness column | `updated_at` (set to `NOW()` at run time) |
| Lookback window | 3 days from `MAX(event_date)` |
| Expected run frequency | Every 15 minutes (same scheduler as silver) |
| Proposed freshness threshold | `> 60 minutes since MAX(updated_at)` → SEV2 alert (gold is less latency-sensitive) |
| Cold-start safety | `COALESCE(MAX(event_date) - 3, DATE '1900-01-01')` |
| Late-arriving event caveat | Events arriving more than 3 days after their `event_timestamp::date` will not be reprocessed by incremental runs; a full-refresh would be required |

### Bronze-to-Silver Row Coverage

| Signal | Formula | Current status |
|---|---|---|
| Bronze total events | `SELECT COUNT(*) FROM bronze.market_events` | Not continuously monitored |
| Silver coverage (approximate) | `SELECT SUM(event_count) FROM silver.market_event_minute_aggregates` | Not monitored |
| Coverage gap | `bronze_count - SUM(silver.event_count)` | Not computed |
| Accepted gap reason | Silver aggregates recent windows only; very old events intentionally excluded by lookback guard | Documented caveat, not a metric |
| Alert condition | Coverage gap exceeds 5% of bronze count unexpectedly | Not implemented |

The silver model aggregates events by minute window. The sum of `event_count` across all
silver rows should equal the total distinct-timestamp-bucketed event count from bronze.
A non-trivial gap indicates either a lookback misconfiguration or a bronze truncation event.

### Bronze-to-Gold Row Coverage

| Signal | Formula | Current status |
|---|---|---|
| Bronze daily event count | `SELECT COUNT(*) FROM bronze.market_events WHERE event_timestamp::date = <date>` | Not continuously monitored |
| Gold daily event count | `SELECT event_count FROM gold.market_event_daily_aggregates WHERE event_date = <date>` | Not monitored |
| Coverage match | Bronze and gold per-day counts should match | Not verified automatically |
| Alert condition | Per-day coverage mismatch above 1% | Not implemented |

### Cloud SQL to BigQuery Row-Count Drift

| Source | Target | Row count (last validated) | Status |
|---|---|---|---|
| `bronze.market_events` (Cloud SQL) | `rtdp_analytics.market_events_raw` (BigQuery) | 6,120 rows in BigQuery; Cloud SQL bronze count at validation time matches per `bigquery-bounded-backfill-evidence.md` | Validated at a point in time; no continuous drift monitoring |
| `silver.market_event_minute_aggregates` (Cloud SQL) | No BigQuery target | N/A | Silver has no BigQuery counterpart currently |
| `gold.market_event_daily_aggregates` (Cloud SQL) | No BigQuery target | N/A | Gold has no BigQuery counterpart currently |

A cross-system row-count drift check between Cloud SQL bronze and BigQuery would require
reading from both systems in a single reconciliation script. This is proposed but not
implemented.

### Stale Model Detection

Stale model detection involves querying `MAX(updated_at)` from each silver/gold table
and comparing it against the current time. This query is safe (read-only) and could be
executed as a post-run step in the dbt job container or as a standalone scheduled script.

Proposed detection logic (not implemented):

```sql
-- silver freshness check (not implemented; proposed only)
SELECT
    'silver.market_event_minute_aggregates' AS model,
    EXTRACT(EPOCH FROM (NOW() - MAX(updated_at))) / 60 AS lag_minutes
FROM silver.market_event_minute_aggregates;
```

If `lag_minutes` exceeds the threshold (proposed: 30 minutes for silver), the script would
emit `dbt_model_freshness_lag_minutes` to Cloud Monitoring and trigger the freshness alert
policy.

### Late-Arriving Event Caveats

Both models use `is_incremental()` lookback guards to avoid full table scans. This means:

- Silver processes events in the trailing 10 minutes from `MAX(window_start)`. An event
  arriving 15 minutes late (after the lookback window) will not appear in the silver table
  until the next full-refresh run or until the lookback window is explicitly widened.
- Gold processes events in the trailing 3 days from `MAX(event_date)`. An event arriving
  4 days late will not appear in gold until a full-refresh.
- These are accepted operational limitations of the `delete+insert` incremental strategy.
  They must be documented in any SLO or data contract for the silver and gold tables.
- For production environments with guaranteed ordering requirements, a wider lookback window
  or a Dataflow windowing strategy would be more appropriate.

---

## 9. Alerting Plan

The following alert policies are proposed future implementation targets. None are currently
active in Cloud Monitoring. Terraform resources for these policies do not yet exist.

| Alert name | Trigger | Severity | Detection query / metric | Expected operator action | Evidence required after recovery |
|---|---|---|---|---|---|
| `RTDP dbt Run Failure` | `dbt_run_failure_count > 0` in last 5 minutes | SEV2 | Cloud Monitoring: `custom.googleapis.com/rtdp/dbt/dbt_run_failure_count` | Inspect Cloud Logging for `rtdp-dbt-refresh-job` execution; check `run_results.json` error node; determine if Cloud SQL was available; re-execute after fix | Successful `dbt run PASS=2` log line; zero `dbt_run_failure_count` metric point |
| `RTDP dbt Test Failure` | `dbt_test_failure_count > 0` in last 5 minutes | SEV1 | Cloud Monitoring: `custom.googleapis.com/rtdp/dbt/dbt_test_failure_count` | Check which test failed (unique_combination_of_columns, not_null, accepted_values, custom); inspect failing rows; determine if source data violates the contract; escalate if data loss suspected | Successful `dbt test PASS=22` log line; zero `dbt_test_failure_count`; root cause documented in incident record |
| `RTDP dbt Model Freshness Lag` | `dbt_model_freshness_lag_minutes > 90` for any model | SEV2 | Cloud Monitoring: `custom.googleapis.com/rtdp/dbt/dbt_model_freshness_lag_minutes` | Check if scheduler is paused; check if last dbt run succeeded; check Cloud SQL state; if Cloud SQL is STOPPED outside a controlled window, do not start without a scoped runbook | Freshness lag below threshold; `MAX(updated_at)` advanced; successful run log captured |
| `RTDP dbt Row Count Drop` | `dbt_model_row_count_delta < -20%` vs prior run | SEV2 | Cloud Monitoring: `custom.googleapis.com/rtdp/dbt/dbt_model_row_count_delta` | Compare `COUNT(*)` from silver/gold tables against expected baseline; check bronze source for truncation or schema change; check lookback window alignment | Row count returned to expected level; source-to-target reconciliation script clean; incident documented |
| `RTDP dbt Run Duration Anomaly` | `dbt_run_duration_seconds > 300s` | SEV3 | Cloud Monitoring: `custom.googleapis.com/rtdp/dbt/dbt_run_duration_seconds` | Inspect run log for full-table scans; check if `is_incremental()` guard activated correctly; check Cloud SQL query plan for missing indexes | Run duration returned to baseline (< 120s); explain plan reviewed |
| `RTDP dbt No Run Observed` | No `dbt_run_success_count` or `dbt_run_failure_count` increment within expected window (e.g., 30 minutes after scheduler trigger time) | SEV2 | Cloud Monitoring absence alert on `custom.googleapis.com/rtdp/dbt/dbt_run_success_count` | Check Cloud Scheduler state (may be PAUSED); check Cloud Run job trigger log; check Pub/Sub Cloud Scheduler invoker IAM; restart job manually under a scoped runbook | Confirmed execution log; metric point emitted; scheduler state documented |
| `RTDP dbt Artifact Parse Failure` | `dbt_artifact_parse_error_count > 0` | SEV3 | Cloud Monitoring: `custom.googleapis.com/rtdp/dbt/dbt_artifact_parse_error_count` | Check `push_dbt_metrics.py` error log; check if `run_results.json` was produced; check container exit code; verify GCS write permission | Artifact parse script exits cleanly; metric emission confirmed; `run_results.json` accessible |

---

## 10. Dashboard Plan

A future dbt observability dashboard (`RTDP dbt Transformation Health`) would be created
as a `google_monitoring_dashboard` Terraform resource. It would be exported to
`infra/terraform/gcp/dashboards/dbt_observability_dashboard.json`.

### Proposed Dashboard Panels

| Panel | Metric / source | Visualisation | Notes |
|---|---|---|---|
| dbt Job Status (last run) | `dbt_run_success_count` + `dbt_run_failure_count` | Scorecard: PASS / FAIL | Shows the most recent run result as a binary signal |
| dbt Run Duration (seconds) | `dbt_run_duration_seconds` | Line chart; 24h window | Trend chart for performance regression detection |
| dbt Test Pass Rate (%) | `dbt_test_pass_rate` | Gauge; 0–100% | Red below 100%; yellow between 95–100% |
| Model Freshness Lag (minutes) | `dbt_model_freshness_lag_minutes` per model | Stacked line chart; per-model labels | Separate lines for silver and gold |
| Model Row Count | `dbt_model_rows_total` per model | Line chart; 7-day window | Detects row-count drift over time |
| Source-to-Target Drift Count | `dbt_source_to_target_drift_count` | Line chart; 7-day window | Should be zero or within tolerance |
| Test Failure Count | `dbt_test_failure_count` | Scorecard; alert threshold indicator | Non-zero triggers red alert state |
| Last Successful Run | Derived from `dbt_run_success_count` timestamp | Text tile or scorecard | Shows wall-clock time of last successful execution |
| Incident Links | Cloud Monitoring incident list filter by `rtdp-dbt` | Table tile | Links open incidents to the relevant alert policy |
| SLO Status | Derived from freshness lag + test pass rate + run success | SLO widget (if burn-rate alerting implemented) | Shows whether transformation layer is within SLO |

### Relationship to Existing Dashboard

The current `RTDP Pipeline Overview` dashboard (4 panels; documented in
`cloud-monitoring-dashboard-evidence.md`) monitors the ingestion and worker layer. The
proposed dbt dashboard is a separate, transformation-layer-specific dashboard. In a
future state, both dashboards could be linked from a single `RTDP Platform Status` index
dashboard.

---

## 11. Operational Runbook Skeletons

The following runbooks are design skeletons for future implementation branches. Commands
described are design targets, not approved for immediate execution. No command here has
been run against a live GCP resource on this branch.

---

### RB-DBT-01: dbt Run Failed

**Preconditions:**
- `RTDP dbt Run Failure` alert is OPEN in Cloud Monitoring.
- Cloud SQL state is unknown; do not assume it is running.
- Last successful run timestamp is available from `dbt_run_success_count` time-series.

**Future command sketch (not approved for execution):**
```bash
# Read Cloud Run job execution log (read-only)
gcloud logging read \
  'resource.type="cloud_run_job" resource.labels.job_name="rtdp-dbt-refresh-job"' \
  --limit=100 --project=project-42987e01-2123-446b-ac7

# Inspect last execution status (read-only)
gcloud run jobs executions list \
  --job=rtdp-dbt-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=5

# If re-execution required: open a scoped runbook branch first
# gcloud run jobs execute rtdp-dbt-refresh-job --wait
```

**Safety controls:**
- Do not start Cloud SQL outside a scoped runbook branch.
- Do not resume the scheduler without documenting the reason.
- Do not run `dbt run --full-refresh` without confirming it is safe (irreversible schema change path).

**Validation evidence to capture:**
- Execution ID of the new run.
- `dbt run PASS=2` log line.
- `dbt test PASS=22` log line.
- Cloud SQL `STOPPED / NEVER` state after completion.
- Zero `dbt_run_failure_count` metric point.

**Rollback / stop condition:**
- If Cloud SQL cannot be reached or returns connection errors, stop the execution attempt.
- If `dbt run` produces `ERROR > 0`, do not proceed to `dbt test`; escalate to SEV1.
- Document all actions in the incident record before closing.

**Non-claims:**
- This runbook does not guarantee that the upstream source data is correct after recovery.
- Re-executing the dbt job does not repair data loss in `bronze.market_events`.

---

### RB-DBT-02: dbt Test Failed

**Preconditions:**
- `RTDP dbt Test Failure` alert is OPEN in Cloud Monitoring.
- `dbt_test_failure_count > 0` has been confirmed.
- The specific failing test name is unknown until logs are inspected.

**Future command sketch (not approved for execution):**
```bash
# Read test failure details from Cloud Logging
gcloud logging read \
  'resource.type="cloud_run_job" resource.labels.job_name="rtdp-dbt-refresh-job" \
   jsonPayload.message=~"FAIL"' \
  --limit=50 --project=project-42987e01-2123-446b-ac7

# If artifact store is implemented:
# gsutil cp gs://rtdp-dbt-artifacts/<execution_id>/run_results.json /tmp/run_results.json
# python3 scripts/parse_run_results.py /tmp/run_results.json
```

**Safety controls:**
- Do not modify source data to "fix" a test failure without root-cause confirmation.
- A `unique_combination_of_columns` test failure indicates a duplicate key in silver or gold;
  investigate bronze source duplicates before any write operation.
- Do not disable or widen a failing test without documenting the decision.

**Validation evidence to capture:**
- Name of the failing test node from `run_results.json` or Cloud Logging.
- SQL query that caused the failure, if available from artifact logs.
- Row count of failing rows, if identifiable.
- `dbt test PASS=22` log line after the issue is resolved.

**Rollback / stop condition:**
- If the test failure indicates a data contract violation (e.g., duplicate symbol+event_date in gold),
  pause all downstream consumers of the affected model immediately.
- Do not promote a partial fix without a full `dbt test PASS=22` confirmation.

**Non-claims:**
- Resolving the dbt test does not guarantee the downstream BigQuery data is unaffected.

---

### RB-DBT-03: Model Freshness Lag Exceeded

**Preconditions:**
- `RTDP dbt Model Freshness Lag` alert is OPEN.
- `dbt_model_freshness_lag_minutes > 90` has been confirmed for at least one model.
- The scheduler state is unknown.

**Future command sketch (not approved for execution):**
```bash
# Check scheduler state (read-only)
gcloud scheduler jobs list \
  --project=project-42987e01-2123-446b-ac7 \
  --location=europe-west1

# Check freshness lag directly (read-only; requires Cloud SQL to be running)
# SELECT 'silver' AS model, EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/60 AS lag_minutes
# FROM silver.market_event_minute_aggregates
# UNION ALL
# SELECT 'gold', EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/60
# FROM gold.market_event_daily_aggregates;
```

**Safety controls:**
- If the scheduler is PAUSED (default), freshness lag is expected behaviour. Do not raise
  an alert in environments where the scheduler is intentionally paused.
- Do not start Cloud SQL to check freshness without a scoped runbook branch.
- Freshness lag above threshold does not, by itself, mean data has been lost.

**Validation evidence to capture:**
- Scheduler state (PAUSED or ENABLED).
- Last confirmed dbt execution timestamp.
- `MAX(updated_at)` from silver and gold after successful re-execution.
- `dbt_model_freshness_lag_minutes` metric returning below threshold.

**Rollback / stop condition:**
- If freshness lag is due to scheduler being intentionally paused, close the alert without
  executing any recovery action.

**Non-claims:**
- A freshness lag does not confirm data loss; it confirms that the model has not been updated
  recently.

---

### RB-DBT-04: Row-Count Drift Detected

**Preconditions:**
- `RTDP dbt Row Count Drop` alert is OPEN.
- `dbt_model_row_count_delta < -20%` has been confirmed.
- Previous run row count is available from Cloud Monitoring history.

**Future command sketch (not approved for execution):**
```bash
# Count rows in silver and gold (read-only; requires Cloud SQL running)
# SELECT 'silver' AS model, COUNT(*) AS row_count FROM silver.market_event_minute_aggregates
# UNION ALL SELECT 'gold', COUNT(*) FROM gold.market_event_daily_aggregates;

# Count rows in bronze
# SELECT COUNT(*) FROM bronze.market_events;
```

**Safety controls:**
- Do not run `dbt run --full-refresh` without confirming the drift is not caused by a
  transient lookback window issue that would be resolved by the next incremental run.
- A full-refresh is irreversible at the model level; it truncates and rebuilds the table.

**Validation evidence to capture:**
- Bronze row count at time of investigation.
- Silver and gold row counts at time of investigation.
- Source-to-target reconciliation query results.
- Root cause (schema change, lookback misconfiguration, source truncation).

**Rollback / stop condition:**
- If bronze is intact and the drift is confirmed to be a lookback window gap, widen the
  lookback window in a new branch before executing.
- Document the drift range (earliest affected `event_timestamp`) before any corrective run.

**Non-claims:**
- A row-count drop in silver does not automatically mean rows are lost; they may be recoverable
  via full-refresh from bronze.

---

### RB-DBT-05: Artifact Parse Failed

**Preconditions:**
- `RTDP dbt Artifact Parse Failure` alert is OPEN.
- `push_dbt_metrics.py` has raised an exception (not yet implemented).
- Cloud Monitoring has received zero metric points from the last dbt execution.

**Future command sketch (not approved for execution):**
```bash
# Check push script logs in Cloud Logging
gcloud logging read \
  'resource.type="cloud_run_job" resource.labels.job_name="rtdp-dbt-refresh-job" \
   jsonPayload.script="push_dbt_metrics.py"' \
  --limit=20 --project=project-42987e01-2123-446b-ac7
```

**Safety controls:**
- An artifact parse failure does not mean the dbt run failed; check job exit code separately.
- Metric emission failures must not cause the dbt job itself to fail; the push script should
  run with `if: always()` semantics and should not block on parse errors.

**Validation evidence to capture:**
- Exception traceback from push script logs.
- Confirmation that `run_results.json` was produced in the artifact store.
- Zero `dbt_artifact_parse_error_count` after fix.

**Rollback / stop condition:**
- If `run_results.json` is not produced, escalate to RB-DBT-01 (dbt run failed).

**Non-claims:**
- Artifact parse failure does not imply model data is incorrect.

---

### RB-DBT-06: Full-Refresh Required

**Preconditions:**
- `dbt_full_refresh_required_flag == 1` has been emitted, OR operator has determined that
  the incremental path cannot recover (e.g., schema change in `bronze.market_events`,
  missing index, corrupt lookback state).
- Cloud SQL is STOPPED; starting it requires a scoped runbook branch.

**Future command sketch (not approved for execution):**
```bash
# Full-refresh execution (not approved; requires scoped branch and Cloud SQL start)
# gcloud sql instances patch rtdp-postgres --activation-policy=ALWAYS
# gcloud run jobs execute rtdp-dbt-refresh-job \
#   --update-env-vars="DBT_FLAGS=--full-refresh" --wait
# gcloud sql instances patch rtdp-postgres --activation-policy=NEVER
```

**Safety controls:**
- A full-refresh truncates and rebuilds the silver and gold tables. If downstream processes
  query these tables, they will observe an empty or rebuilding state during the execution window.
- A full-refresh does not affect `bronze.market_events` (source table is read-only by dbt).
- Confirm that the dbt profile target (`cloudsql`) is pointing to the correct Cloud SQL instance
  before executing.
- Cloud SQL must be returned to `NEVER / STOPPED` after completion.

**Validation evidence to capture:**
- `dbt run PASS=2` with full-refresh flag in logs.
- `dbt test PASS=22` after full-refresh.
- Silver and gold row counts post-rebuild.
- Cloud SQL `STOPPED / NEVER` state after completion.
- Terraform PLAN_EXIT=0 confirming no drift.

**Rollback / stop condition:**
- If `dbt run --full-refresh` errors on either model, do not proceed to `dbt test`.
- Document the reason for the full-refresh in the incident record.
- Set `dbt_full_refresh_required_flag` back to `0` after successful validation.

**Non-claims:**
- This runbook does not prove that full-refresh execution is safe under concurrent writes.

---

### RB-DBT-07: Post-Replay dbt Validation

**Preconditions:**
- A replay or backfill operation has completed per the procedure in
  [docs/replay-backfill-strategy.md](replay-backfill-strategy.md).
- `bronze.market_events` has been repopulated or corrected.
- Cloud SQL is still in the bounded activation window opened for the replay.

**Future command sketch (not approved for execution):**
```bash
# Step 1: Run dbt incrementally to pick up the replayed events
# gcloud run jobs execute rtdp-dbt-refresh-job --wait

# Step 2: If replayed events fall outside the lookback window, run full-refresh
# gcloud run jobs execute rtdp-dbt-refresh-job \
#   --update-env-vars="DBT_FLAGS=--full-refresh" --wait

# Step 3: Verify silver/gold row counts match expected post-replay state
# SELECT COUNT(*) FROM silver.market_event_minute_aggregates;
# SELECT COUNT(*) FROM gold.market_event_daily_aggregates;

# Step 4: Confirm dbt tests pass
# (included in standard job execution; check logs for PASS=22)
```

**Safety controls:**
- Post-replay validation must be performed in the same bounded Cloud SQL activation window
  as the replay operation.
- Do not close the Cloud SQL activation window until both dbt run and dbt test have passed.
- Document the pre-replay and post-replay row counts for silver and gold as evidence.

**Validation evidence to capture:**
- `dbt run PASS=2` log line after replay.
- `dbt test PASS=22` log line after replay.
- Silver and gold row counts before and after replay.
- Cloud SQL `STOPPED / NEVER` state after completion.

**Rollback / stop condition:**
- If dbt tests fail after replay, the replay data may contain violations of the uniqueness
  contract. Investigate bronze before concluding that the replay is safe.

**Non-claims:**
- Post-replay dbt validation does not confirm that downstream BigQuery data has been updated;
  the BigQuery append job must be re-executed separately.

---

## 12. Relationship to Replay/Backfill

### Replay/Backfill Strategy Is Now Documented

The replay and backfill strategy for the Real-Time Data Platform is fully documented in
[docs/replay-backfill-strategy.md](replay-backfill-strategy.md). That document covers:

- Cloud SQL as the current operational source of truth for all transformation rebuilds.
- The proven BigQuery bounded backfill path (6,104 rows) and cursor-based incremental append.
- The dbt refresh/rebuild paths as documented skeletons.
- DLQ recovery considerations and idempotency boundaries.
- Explicit non-claims (no automated production replay; no exactly-once DLQ consumer).

### dbt Observability Detects When Transformed Layers Are Stale or Wrong

The primary value of dbt observability relative to replay is detection. Without a
freshness metric and row-count drift metric:

- A replay operation may complete successfully in bronze but the dbt refresh job may not
  have run yet. Silver and gold remain stale. No operator is notified.
- A partial replay (e.g., only some symbols replayed) may produce row-count drift in
  silver that is invisible without a row-count metric.
- A post-replay dbt job failure would be invisible without `dbt_run_failure_count` alerting.

With dbt observability metrics, the post-replay validation path becomes measurable:
an operator can confirm that silver and gold row counts increased by the expected amount
after a replay, and that all 22 dbt tests still pass.

### dbt Metrics Should Support Post-Replay Validation

Specifically:

- `dbt_model_rows_total` before and after replay should show an increase matching the
  replayed event count.
- `dbt_model_freshness_lag_minutes` should drop to near zero after the post-replay dbt run.
- `dbt_test_pass_rate` must remain 100% after the post-replay run; a drop indicates the
  replayed events violate a data contract (e.g., duplicate `event_id` reached bronze).
- `dbt_source_to_target_drift_count` should be zero or within tolerance after the replay.

### dbt Observability Does Not Replace Replay/Backfill

dbt observability is a detection layer. It surfaces the symptoms (stale model, row-count drop,
test failure) but does not provide the recovery mechanism. Recovery requires:

1. A documented replay or backfill procedure (see `docs/replay-backfill-strategy.md`).
2. A controlled Cloud SQL activation window.
3. A dbt execution (incremental or full-refresh) within that window.
4. Post-replay validation evidence captured per RB-DBT-07.

### Cloud SQL Remains Source of Truth for Transformation Rebuilds

Cloud SQL `bronze.market_events` is the authoritative source for all dbt transformation
rebuilds. If silver or gold is wrong, the correct recovery path is always:

1. Verify bronze is correct.
2. Execute dbt against bronze.
3. Confirm with `dbt test PASS=22` and row-count checks.

No recovery path should skip bronze and write directly to silver or gold.

---

## 13. Relationship to SLOs and Incident Response

### How dbt Metrics Map to Transformation-Layer SLOs

The existing [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) defines
SLOs for the ingestion and worker layer. The following proposed SLOs extend that framework
to the transformation layer.

### Proposed Transformation-Layer SLOs

| SLO | SLI | Target | Measurement source | Notes |
|---|---|---|---|---|
| dbt job success rate | `dbt_run_success_count / (dbt_run_success_count + dbt_run_failure_count)` | >= 95% over rolling 7 days | Cloud Monitoring `dbt_run_success_count`, `dbt_run_failure_count` | During controlled validation windows only; scheduler is PAUSED by default |
| Model freshness target | `dbt_model_freshness_lag_minutes` | < 30 minutes for silver; < 60 minutes for gold (when scheduler is running) | Cloud Monitoring `dbt_model_freshness_lag_minutes` | Only meaningful when the scheduler is ENABLED; not applicable when intentionally paused |
| Test pass target | `dbt_test_pass_rate` | 100% on every execution | Cloud Monitoring `dbt_test_pass_rate` | Any failure below 100% is immediately SEV1; no tolerance window |
| Row-count drift tolerance | `dbt_model_row_count_delta` | < 20% drop vs prior run | Cloud Monitoring `dbt_model_row_count_delta` | Drops of up to 20% may be legitimate if source data volume decreased; drops above 20% trigger SEV2 investigation |

### How Alerts Map to Existing Incident Severity Levels

The incident severity classification in `SLO_AND_INCIDENT_RESPONSE.md` maps to the proposed
dbt alert policies as follows:

| Proposed alert | Severity mapping | Rationale |
|---|---|---|
| `RTDP dbt Run Failure` | SEV2 | Same level as `silver_refresh_error_count > 0`; transformation layer failure with data impact |
| `RTDP dbt Test Failure` | SEV1 | Data contract violation; potential data integrity issue; escalated above run failure |
| `RTDP dbt Model Freshness Lag` | SEV2 | Downstream consumers may receive stale data; requires operator action |
| `RTDP dbt Row Count Drop` | SEV2 | Potential silent data loss; requires investigation before downstream impact |
| `RTDP dbt Run Duration Anomaly` | SEV3 | Performance warning; no immediate data impact |
| `RTDP dbt No Run Observed` | SEV2 | Transformation layer silently failing to execute; operator investigation required |
| `RTDP dbt Artifact Parse Failure` | SEV3 | Observability layer degraded; dbt run status unknown |

### What Evidence Must Be Captured During Incident Response

For any incident involving a dbt alert, the following evidence must be captured before
the incident is closed:

1. Cloud Run execution ID of the failing or missing execution.
2. Full `dbt run` and `dbt test` log output (structured logs from Cloud Logging).
3. `run_results.json` artifact content (if artifact store is implemented).
4. Silver and gold row counts at time of incident.
5. Bronze row count at time of incident (requires Cloud SQL to be running).
6. Cloud SQL final state after resolution (`STOPPED / NEVER`).
7. Terraform PLAN_EXIT=0 confirmation.
8. Zero `dbt_run_failure_count` and zero `dbt_test_failure_count` metric points after recovery.

---

## 14. Implementation Roadmap

### P0 -- Docs-Only (This Branch)

| Item | Branch | Files changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| dbt observability metrics plan | `docs/dbt-observability-metrics-plan` | `docs/dbt-observability-metrics-plan.md`, `docs/EVIDENCE_INDEX.md` | NO | NO | NONE | This document; EVIDENCE_INDEX updated |

### P1 -- Light Implementation (Next Implementation Branch)

| Item | Branch | Files likely changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| dbt metric emission script | `feat/dbt-metric-emission-script` | `scripts/push_dbt_metrics.py`, `dbt/entrypoint.sh` or job Dockerfile | NO (metrics emitted without run) | YES (IAM: `roles/monitoring.metricWriter` for dbt job SA) | LOW (IAM Terraform apply; metric ingestion cost negligible) | Script parses `run_results.json`; pushes `dbt_run_success_count`, `dbt_run_failure_count`, `dbt_run_duration_seconds`, `dbt_test_pass_count`, `dbt_test_failure_count` to Cloud Monitoring; Cloud SQL NOT started |
| GCS artifact copy | `feat/dbt-artifact-store` | `dbt/entrypoint.sh`, `infra/terraform/gcp/storage.tf` | NO | YES (new `google_storage_bucket.dbt_artifacts`; IAM `roles/storage.objectCreator`) | LOW (GCS storage cost for small JSON files) | `run_results.json` and `manifest.json` persisted to GCS per execution; bucket created via Terraform apply |

### P2 -- Cloud Monitoring Metrics

| Item | Branch | Files likely changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| dbt model rows metric | `feat/dbt-model-rows-metric` | `scripts/push_dbt_metrics.py` (extend) | YES (freshness query runs against Cloud SQL) | MINOR (no new Terraform resources if metric descriptor is auto-created) | LOW (Cloud SQL start for < 2 minutes per metric collection) | `dbt_model_rows_total` time series in Cloud Monitoring; silver and gold model row counts visible |
| dbt freshness metric | `feat/dbt-freshness-metric` | `scripts/push_dbt_freshness.py` (new) | YES (requires `MAX(updated_at)` query) | MINOR | LOW | `dbt_model_freshness_lag_minutes` time series in Cloud Monitoring |
| Source-to-target reconciliation | `feat/dbt-reconciliation-script` | `scripts/push_dbt_reconciliation.py` (new) | YES | MINOR | LOW | `dbt_source_to_target_drift_count` time series; bronze vs silver/gold count comparison |

### P3 -- Dashboard and Alert Policies

| Item | Branch | Files likely changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| dbt alert policies | `feat/dbt-alert-policies` | `infra/terraform/gcp/monitoring.tf` | NO | YES | LOW (Terraform apply for alert policies only) | Alert policies deployed; controlled failure and recovery runs evidence; email notification delivery proven |
| dbt observability dashboard | `feat/dbt-dashboard` | `infra/terraform/gcp/dashboards/dbt_observability_dashboard.json` | NO | YES | LOW | Dashboard visible in Cloud Monitoring; dbt metric panels populated |
| Model-level SLO definition | `docs/dbt-model-slo-definition` | `docs/dbt-model-slo-definition.md` | NO | NO | NONE | SLO targets for silver freshness, gold freshness, test pass rate, run success rate documented |

---

## 15. Explicit Non-Claims

The following capabilities are **NOT** implemented and must not be claimed in interviews,
portfolio reviews, or technical discussions:

| Non-claim | Status |
|---|---|
| No dbt-specific Cloud Monitoring metrics are implemented | CONFIRMED NOT IMPLEMENTED |
| No dbt dashboard exists | CONFIRMED NOT IMPLEMENTED |
| No dbt alert policy exists | CONFIRMED NOT IMPLEMENTED |
| No dbt artifact ingestion exists | CONFIRMED NOT IMPLEMENTED -- `run_results.json` is ephemeral in the container |
| No dbt run history table exists | CONFIRMED NOT IMPLEMENTED |
| No automated model freshness alert exists | CONFIRMED NOT IMPLEMENTED |
| No automated row-count drift alert exists | CONFIRMED NOT IMPLEMENTED |
| No dbt full-refresh live validation has been executed | CONFIRMED NOT EXECUTED -- only incremental execution is proven |
| No staging/prod dbt split exists | CONFIRMED -- single Cloud SQL instance; single dbt profile target `cloudsql` |
| No transformation-layer SLO burn-rate alerting exists | CONFIRMED NOT IMPLEMENTED |
| No cross-layer row-count comparison between Cloud SQL bronze, dbt silver/gold, and BigQuery is automated | CONFIRMED NOT IMPLEMENTED |
| No dbt failure notification path beyond generic Cloud Run job exit code is proven | CONFIRMED -- job-level exit code is the only currently observable signal |
| No deploy-on-merge for dbt job | CONFIRMED -- image deploy requires manual `workflow_dispatch` |
| No Cloud SQL persisted latency columns | CONFIRMED NOT IMPLEMENTED |
| No exact cost per event calculated from billing export | CONFIRMED NOT CALCULATED |
| Dataflow not implemented | CONFIRMED -- deferred per `docs/dataflow-decision-record.md` |

---

## 16. Safe Recruitment Positioning

### Recruiter-Facing Paragraph

The Real-Time Data Platform includes a validated dbt transformation layer running against
Cloud SQL PostgreSQL, with live execution evidence: dbt run PASS=2 (silver and gold
incremental models), dbt test PASS=22, and a Cloud Run Job deployment path managed entirely
by Terraform. This branch documents the strategy for extending that foundation with
Cloud Monitoring metrics, model freshness alerting, row-count drift detection, and
artifact-based observability -- the same patterns used in production analytics engineering
platforms. The observability metrics are proposed and designed here; implementation is
staged across documented future branches.

### Technical Interview Paragraph

The dbt transformation layer is proven at the execution level: both incremental models
(`delete+insert`, `unique_key` enforced, COALESCE cold-start guard) ran successfully against
a live Cloud SQL instance, and all 22 dbt tests passed. This plan documents the observability
gap: there are currently no custom Cloud Monitoring metrics emitted from dbt execution, no
model freshness or row-count drift alerts, and no artifact ingestion. The proposed metric
catalog covers run success/failure counts, test pass rate, model-level row counts, freshness
lag (computed from `MAX(updated_at)` against current time), and source-to-target drift. The
implementation pattern follows the existing BigQuery quality metric emission approach
(`push_bigquery_quality_metrics.py`), which has already proven Cloud Monitoring custom metric
emission and incident-to-email alert delivery end-to-end. The gap between what is designed
here and what is implemented is deliberate and documented; it is not concealed.

### Senior Reviewer Caveat Paragraph

A senior reviewer should note the following honest constraints. The dbt execution evidence is
bounded (7 gold rows, 13 silver rows, reflecting a small test dataset). The incremental models
have not been tested under concurrent writes, high-volume late-arriving events, or schema drift
conditions. There is no staging/prod environment split, no deploy-on-merge, and no
transformation-layer SLO burn-rate calculation. The observability plan described here is
forward-looking strategy, not a description of a running production system. The Cloud Run
worker runs with `maxScale=1` and `concurrency=1`, meaning the platform is single-threaded
and not horizontally scaled. All of this is accurately represented in the evidence record and
should be discussed openly in technical review rather than inferred from absence of claim.

---

## 17. Final Recommendation

### This Branch

This branch (`docs/dbt-observability-metrics-plan`) closes the dbt observability strategy
gap as documentation. It:

- Defines all relevant dbt observability terms.
- Establishes the current evidence baseline (dbt run PASS=2, dbt test PASS=22, Cloud SQL
  live execution proven).
- Registers 13 specific observability gaps with priorities and recommended future branches.
- Proposes a 12-metric catalog with types, labels, collection methods, and alert thresholds.
- Defines an artifact strategy aligned with existing patterns (`push_bigquery_quality_metrics.py`).
- Designs a Cloud Monitoring integration architecture reusing the existing notification channel.
- Provides model freshness and row-count drift analysis for both silver and gold models.
- Proposes a 7-alert alerting plan mapped to existing incident severity levels.
- Describes a 10-panel dbt observability dashboard.
- Documents 7 operational runbook skeletons with safety controls and non-claims.
- Explains the relationship to the documented replay/backfill strategy.
- Maps proposed metrics to SLOs and incident response procedures.
- Provides an honest P0–P3 implementation roadmap.
- States 16 explicit non-claims.
- Provides safe and accurate recruitment positioning.

### Recommended Next Branches

| Priority | Branch | Rationale |
|---|---|---|
| Next (docs) | `docs/staging-environment-plan` OR `docs/deploy-on-merge-decision-record` | These gaps (no staging/prod split, manual deploy-only) are the remaining high-recruitment-value documentation gaps after dbt observability is addressed. Choose based on current priority: staging is more production-credible; deploy-on-merge is more CI/CD credible. |
| P1 implementation | `feat/dbt-metric-emission-script` | Implements `push_dbt_metrics.py`; follows the proven `push_bigquery_quality_metrics.py` pattern; no Cloud SQL start required; Terraform apply scope is limited to IAM binding for `roles/monitoring.metricWriter`. |
| P2 implementation | `feat/dbt-freshness-metric` | Implements freshness lag metric; requires Cloud SQL bounded window; most interview-visible dbt observability signal. |
| Deferred | Any Dataflow / Apache Beam implementation | Do not implement Dataflow until higher-scale requirements, latency requirements, replay semantics, or streaming window requirements justify the operational complexity. Deferred per `docs/dataflow-decision-record.md`. |

### Do Not Implement Dataflow Yet

Dataflow remains deferred. The validated Pub/Sub → Cloud Run worker path handles the current
scale with proven correctness. Dataflow introduces significant operational complexity, billing
exposure, and IAM surface area without measured justification at the current scale. The
decision record is in `docs/dataflow-decision-record.md`.

Later branches may implement dbt metric emission (`push_dbt_metrics.py`), a dbt observability
dashboard in Cloud Monitoring, and dbt-specific alert policies following the P1–P3 roadmap
defined in Section 14.
