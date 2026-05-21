# Evidence Index

This document is a curated map of project evidence for the Real-Time Data Platform.
It is intended for technical review of architecture, infrastructure-as-code, CI/CD,
observability, load testing, and production-readiness evidence. It indexes existing
documentation; it does not summarize or vouch for the project beyond what the linked
documents contain.

---

## Review Path

For a recruiter or B2B entry point, start with
[docs/portfolio-b2b-narrative.md](portfolio-b2b-narrative.md) for an executive summary,
validated capabilities, intentional non-claims, and 2026-2027 relevance.

Recommended deep technical review path:

1. [README.md](../README.md) -- project overview, local quickstart, GCP status summary
2. [docs/gcp-architecture.md](gcp-architecture.md) -- GCP service mapping and target flow
3. [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) -- this document (evidence categories and links)
4. [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) -- end-to-end cloud validation
5. [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) -- bounded throughput evidence

---

## Current Validated Capabilities

| Area | Evidence | Status |
|---|---|---|
| Local Kafka-compatible pipeline | README.md, Docker Compose stack | Implemented |
| GCP Pub/Sub ingestion | gcp-end-to-end-validation.md | Validated |
| Cloud Run worker | gcp-worker-cloud-validation.md | Validated |
| Cloud Run API | gcp-end-to-end-validation.md | Validated |
| Cloud SQL PostgreSQL | cloud-sql-terraform-import-plan-evidence.md | Implemented, NEVER/STOPPED |
| Terraform-managed infrastructure | All *-import-plan-evidence.md files | Zero-diff plan verified |
| Terraform remote backend | terraform-remote-backend-migration-evidence.md | GCS backend active |
| Workload Identity Federation | workload-identity-terraform-import-plan-evidence.md | Imported, zero-diff |
| Artifact Registry | artifact-registry-terraform-import-plan-evidence.md | Imported, zero-diff |
| Manual deploy workflow -- worker | cloud-run-worker-manual-deploy-evidence.md | workflow_dispatch validated |
| Manual deploy workflow -- API | api-manual-deploy-evidence.md | workflow_dispatch validated |
| Cloud Monitoring metrics | cloud-logs-based-metrics-datapoint-validation.md | 4 metrics, datapoints confirmed |
| Alert policies | cloud-alert-policies-evidence.md | 2 policies, email channel attached |
| Monitoring dashboard | cloud-monitoring-dashboard-evidence.md | 4-panel dashboard, GCP-created |
| Load test evidence | load-test-100/1000/5000-cloud-evidence.md | 100 / 1,000 / 5,000 events accepted |
| DLQ and retry configuration | production-pubsub-dlq-evidence.md | deadLetterPolicy, maxDeliveryAttempts=5 |
| Scheduler and silver refresh | silver-refresh-scheduler-execution-proof-evidence.md | Scheduled execution validated |
| dbt Cloud Run Job deployment | dbt-refresh-cloud-run-deploy-evidence.md | Terraform apply confirmed; zero-diff plan |
| dbt refresh job execution | dbt-refresh-job-execution-proof-evidence.md | dbt run PASS=2, dbt test PASS=22, API readback HTTP 200 |
| Scheduler switch to dbt job | dbt-scheduler-switch-evidence.md | Scheduler-triggered dbt execution accepted; PAUSED by default |
| dbt silver incremental model | dbt-incremental-silver-evidence.md | silver_market_event_minute_aggregates converted to incremental (delete+insert, unique_key=[symbol, window_start], 10-min lookback); LOCAL CODE ONLY; Cloud SQL live execution NOT YET PROVEN |
| dbt gold incremental model | dbt-incremental-gold-evidence.md | gold_market_event_daily_aggregates converted to incremental (delete+insert, unique_key=[symbol, event_date], 3-day lookback); 239 pytest passed; 8 dbt tests passed; LOCAL DISPOSABLE POSTGRES VALIDATION PASSED; Cloud SQL live execution NOT YET PROVEN |
| dbt Cloud SQL incremental execution | dbt-cloud-sql-incremental-execution-proof.md | VALIDATED -- CLOUD SQL LIVE INCREMENTAL DBT EXECUTION PROVEN; execution rtdp-dbt-refresh-job-gqrl8; image built from commit 91cf94b2 (Run ID 26117517140); dbt run PASS=2; gold INSERT 0 7; silver INSERT 0 13; dbt test PASS=22; Cloud SQL restored to STOPPED/NEVER; schedulers PAUSED; PLAN_EXIT=0 |
| BigQuery analytical tier scaffold | bigquery-terraform-apply-evidence.md | Dataset rtdp_analytics + 3 tables + IAM applied via Terraform; PLAN_EXIT=0; Cloud SQL NEVER/STOPPED |
| BigQuery bounded backfill | bigquery-bounded-backfill-evidence.md | 6,104 rows from Cloud SQL bronze.market_events to BigQuery market_events_raw; source/target count match accepted; analytical query by symbol/event_type confirmed; PLAN_EXIT=0; Cloud SQL NEVER/STOPPED |
| BigQuery incremental append | bigquery-incremental-append-evidence.md | Cloud Run Job + staging table via Terraform; cursor-based MERGE; 10 evidence rows appended (6104→6114); second run idempotent (6114 unchanged); 0 duplicates; PLAN_EXIT=0; Cloud SQL NEVER/STOPPED |
| BigQuery append scheduler | bigquery-append-scheduler-evidence.md | `rtdp-bigquery-append-scheduler` created via Terraform; PAUSED; targets `rtdp-bigquery-append-job:run`; `0 * * * *` Europe/Lisbon; no execution; PLAN_EXIT=0; Cloud SQL NEVER/STOPPED |
| BigQuery append scheduler proof | bigquery-append-scheduler-proof-evidence.md | Corrected-image proof (SHA `3e0db6f`): executions `p9hkt` + `7pn6g`; BQ 6117→6120 (+3 exact); second run idempotent (6120 unchanged); SCHEDULERPROOFV2USDT=3; duplicate_count=0; logs confirm `source_rows_exported` (not `rows_appended`); staging numRows=0; both schedulers PAUSED; Cloud SQL NEVER/STOPPED; PLAN_EXIT=0; 187 tests passed |
| Scheduler IAM hardening | scheduler-job-invoker-iam-hardening-evidence.md | Replaced project-level `roles/run.invoker` with two `google_cloud_run_v2_job_iam_member` bindings scoped to `rtdp-bigquery-append-job` and `rtdp-dbt-refresh-job`; Google provider 6.50.0 confirmed to support resource; Plan: 2 add, 1 destroy, 0 change; both schedulers PAUSED; Cloud SQL NEVER/STOPPED; PLAN_EXIT=2 (pending apply) |
| Scheduler IAM scoped proof | scheduler-job-scoped-iam-proof-evidence.md | Live GCP proof: project-level `roles/run.invoker` removed for `rtdp-scheduler-sa`; job-scoped `roles/run.invoker` confirmed on `rtdp-bigquery-append-job` and `rtdp-dbt-refresh-job`; `rtdp-silver-refresh-job` has no invoker binding; PLAN_EXIT=0; both schedulers PAUSED; Cloud SQL NEVER/STOPPED |
| BigQuery quality checks | bigquery-quality-checks-evidence.md | Read-only quality script for `rtdp_analytics.market_events_raw`; 6/6 checks pass; row_count=6120; staging=0; no BigQuery mutation; no Cloud SQL start; 197 tests pass; ruff clean |
| BigQuery quality workflow | bigquery-quality-workflow-proof-evidence.md | `workflow_dispatch` Run ID 25982120058; conclusion: success; artifact status: ok; 6/6 checks passed; row_count=6120; staging=0; no BigQuery mutation; no Cloud SQL start; no scheduler execution; manual dispatch only |
| BigQuery quality schedule enabled | bigquery-quality-schedule-enabled-evidence.md | schedule `15 6 * * *` enabled on `main` (PR #141); `workflow_dispatch` Run ID 25984483471 post-merge: success; 6/6 checks passed; row_count=6120; staging=0; scheduled event real execution NOT YET PROVEN |
| BigQuery quality thresholds | bigquery-quality-thresholds-evidence.md | `--min-row-count` and `--freshness-max-age-hours` flags added (PR #145); `row_count_minimum` live pass: observed 6120 >= 6000; `freshness_max_age_hours` skipped as expected (unit-tested only, not live-proven); 210 tests passed; no BigQuery mutation; no Cloud SQL start; no scheduler execution; scheduled event real execution NOT YET PROVEN |
| BigQuery quality alert proof | bigquery-quality-alert-notification-proof-evidence.md | Controlled failure proven (PR #150): Run 26007825072 success (min_row_count=1; observed 6120 >= 1); Run 26007909020 failure (min_row_count=999999999; observed 6120 < 999999999); `row_count_minimum` fail; exit code 1; artifact preserved; GitHub Actions UI failure surface observable; email/bell/Cloud Monitoring NOT PROVEN; scheduled event NOT YET PROVEN |
| BigQuery freshness live failure | bigquery-freshness-live-validation-evidence.md | Run ID 26020167461; `workflow_dispatch`; `freshness_max_age_hours` fail (age_hours 45.5496 > 1.0; max_ingest_timestamp 2026-05-16 10:08:49.141452+00); `row_count_minimum` pass (6120 >= 1); `staging_table_empty` pass (0); artifact preserved; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; passing `freshness_max_age_hours` live run NOT YET PROVEN |
| BigQuery quality Cloud Monitoring metrics plan | bigquery-quality-cloud-monitoring-metrics-plan.md | PLANNED - QUALITY METRICS NOT YET IMPLEMENTED; 5 planned metrics (`custom.googleapis.com/rtdp/bigquery_quality/status`, `failed_checks_count`, `check_pass`, `row_count`, `freshness_age_hours`); preferred script `scripts/push_bigquery_quality_metrics.py`; metric emission step with `if: always()`; `roles/monitoring.metricWriter` required; Cloud Monitoring quality metrics NOT implemented; Cloud Monitoring alerting NOT proven; real scheduled event execution NOT YET PROVEN |
| BigQuery quality Cloud Monitoring metrics | bigquery-quality-cloud-monitoring-metrics-evidence.md | VALIDATED - QUALITY METRICS EMITTED TO CLOUD MONITORING; PR #157 + PR #158; safe run 26061129567 (status = 1; failed_checks_count = 0; row_count = 6120); failure run 26061541771 (status = 0; failed_checks_count = 1; check_pass row_count_minimum = 0; row_count = 6120); Pushed 10 time series to Cloud Monitoring; roles/monitoring.metricWriter applied; PLAN_EXIT=0; 239 passed; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed; freshness_age_hours metric NOT YET PROVEN; Cloud Monitoring alerting NOT YET PROVEN |
| BigQuery quality Cloud Monitoring alert policy | bigquery-quality-cloud-monitoring-alert-policy-evidence.md | VALIDATED - ALERT POLICY APPLIED; INCIDENT/NOTIFICATION DELIVERY NOT YET PROVEN; PR #160 + PR #161; google_monitoring_alert_policy.bigquery_quality_failure; display name RTDP BigQuery Quality Failure; failed_checks_count = 1; Run ID 26065876070; Pushed 10 time series to Cloud Monitoring; PLAN_EXIT=0; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed; Incident creation NOT YET PROVEN; Email notification delivery NOT YET PROVEN; GitHub notification bell delivery NOT YET PROVEN |
| BigQuery quality alert incident notification proof | bigquery-quality-alert-incident-notification-proof.md | PARTIAL - ALERT POLICY AND EMAIL CHANNEL VALIDATED; INCIDENT/EMAIL DELIVERY NOT YET PROVEN; PR #163; RTDP BigQuery Quality Failure alert policy existence validated; RTDP Operator Email Alerts channel existence validated; failed_checks_count = 1; Run ID 26065876070; Pushed 10 time series to Cloud Monitoring; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed; Incident creation NOT YET PROVEN; Email notification delivery NOT YET PROVEN; GitHub notification bell delivery NOT YET PROVEN |
| BigQuery quality freshness_age_hours metric | bigquery-quality-freshness-age-hours-metric-evidence.md | VALIDATED - FRESHNESS AGE HOURS METRIC EMITTED TO CLOUD MONITORING; PR #165; Run ID 26069840695; freshness_max_age_hours=999999; age_hours = 62.9712; metric custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours; doubleValue=62.9712; series_count=1; Pushed 12 time series to Cloud Monitoring; endTime 2026-05-19T01:07:08Z; previous failed attempt 26069153131 (HTTP 500; series_count=0); BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed; Incident creation NOT YET PROVEN; Email notification delivery NOT YET PROVEN; GitHub notification bell delivery NOT YET PROVEN |
| BigQuery quality scheduled event execution | bigquery-quality-scheduled-event-execution-evidence.md | VALIDATED - SCHEDULED EVENT EXECUTION PROVEN; PR #167; Run ID 26028523804; Event schedule; cron 15 6 * * *; workflow BigQuery Quality Checks; commit dce441d3040ac8fd72a204eaa2e4775c42d06169; service account rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com; min_row_count=1; freshness_max_age_hours=0; artifact ID 7055640475; status ok; failed_checks []; row_count 6120; staging_table_empty pass; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; Terraform not changed; Terraform apply not executed; no secrets printed; Artifact preserved; Incident creation NOT YET PROVEN; Email notification delivery NOT YET PROVEN; GitHub notification bell delivery NOT YET PROVEN |
| BigQuery quality incident and email notification delivery | bigquery-quality-incident-notification-delivery-proof.md | VALIDATED - INCIDENT CREATION AND EMAIL NOTIFICATION DELIVERY PROVEN; PR #169; Run ID 26089332693; workflow_dispatch controlled failure; row_count_minimum failed as expected; artifact ID 7080086765; 10 time series pushed to Cloud Monitoring; alert policy RTDP BigQuery Quality Failure produced OPEN incident; email notification delivery proven by Gmail inbox screenshot evidence; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; Terraform not changed; Terraform apply not executed; no secrets printed; GitHub notification bell delivery NOT YET PROVEN; Dataflow not implemented |
| DLQ malformed-message routing | dlq-malformed-message-validation-evidence.md | VALIDATED WITH OBSERVED CAVEAT -- malformed payload reached DLQ; multiple DLQ entries observed for same test_marker (delivery counts 5-16); exactly-once DLQ routing NOT claimed; initial ack cleanup failed (--ack-ids-file unsupported); subscription drained via --auto-ack and deleted; Cloud SQL NEVER/STOPPED; Schedulers PAUSED; Terraform apply NOT run; no secrets printed |
| Cost-control state | Cloud SQL NEVER/STOPPED, Scheduler PAUSED (multiple docs) | Verified throughout |

---

## Architecture Evidence

| Document | Purpose | What It Proves |
|---|---|---|
| [docs/gcp-architecture.md](gcp-architecture.md) | GCP service mapping | Maps local components to Cloud Run, Pub/Sub, Cloud SQL, BigQuery, Dataflow |
| [docs/gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) | End-to-end cloud validation | Full Pub/Sub -> Cloud Run worker -> Cloud SQL -> API readback path confirmed |
| [docs/gcp-worker-cloud-validation.md](gcp-worker-cloud-validation.md) | Cloud Run worker validation | Worker deployment, Pub/Sub push subscription, idempotent bronze writes |
| [docs/worker-structured-logs-validation.md](worker-structured-logs-validation.md) | Structured log validation | Cloud Logging jsonPayload structure confirmed for the deployed worker |

---

## Infrastructure as Code Evidence

Terraform import operations were performed against a GCS-backed remote state.
Import batches were validated with zero-diff plans. Apply operations, where present in
separate evidence branches, are documented in their specific evidence files.

| Document | Scope |
|---|---|
| [docs/terraform-iac-baseline-runbook.md](terraform-iac-baseline-runbook.md) | Strategy document: phased import approach |
| [docs/terraform-remote-backend-migration-evidence.md](terraform-remote-backend-migration-evidence.md) | GCS remote backend active, local state migrated |
| [docs/terraform-pubsub-scheduler-import-plan-evidence.md](terraform-pubsub-scheduler-import-plan-evidence.md) | Pub/Sub topics, push subscription, Cloud Scheduler imported |
| [docs/terraform-monitoring-import-plan-evidence.md](terraform-monitoring-import-plan-evidence.md) | Logs-based metrics, dashboard, alert policies imported |
| [docs/cloud-run-terraform-import-plan-evidence.md](cloud-run-terraform-import-plan-evidence.md) | rtdp-api, rtdp-pubsub-worker, rtdp-silver-refresh-job imported |
| [docs/cloud-sql-terraform-import-plan-evidence.md](cloud-sql-terraform-import-plan-evidence.md) | Cloud SQL rtdp-postgres imported, NEVER/STOPPED preserved |
| [docs/secret-manager-terraform-import-plan-evidence.md](secret-manager-terraform-import-plan-evidence.md) | Secret Manager rtdp-database-url metadata imported |
| [docs/service-accounts-terraform-import-plan-evidence.md](service-accounts-terraform-import-plan-evidence.md) | Custom RTDP service accounts imported |
| [docs/iam-members-terraform-import-plan-evidence.md](iam-members-terraform-import-plan-evidence.md) | Project and service-account IAM members imported |
| [docs/workload-identity-terraform-import-plan-evidence.md](workload-identity-terraform-import-plan-evidence.md) | GitHub Actions Workload Identity Pool and OIDC Provider imported |
| [docs/artifact-registry-terraform-import-plan-evidence.md](artifact-registry-terraform-import-plan-evidence.md) | Artifact Registry rtdp Docker repository imported |
| [docs/cloud-resource-manager-api-enablement-evidence.md](cloud-resource-manager-api-enablement-evidence.md) | cloudresourcemanager API enabled; Terraform Plan CI rerun green |
| [docs/api-deploy-ci-service-account-user-evidence.md](api-deploy-ci-service-account-user-evidence.md) | CI service account user binding for API deploy validated |
| [docs/bigquery-analytical-tier-plan.md](bigquery-analytical-tier-plan.md) | BigQuery analytical tier design: dataset, table schema, partitioning, clustering strategy, IAM plan |
| [docs/bigquery-terraform-apply-evidence.md](bigquery-terraform-apply-evidence.md) | BigQuery dataset rtdp_analytics + 3 tables + 2 IAM resources created via Terraform apply (6 resources total); PLAN_EXIT=0; Cloud SQL NEVER/STOPPED throughout |
| [docs/bigquery-bounded-backfill-evidence.md](bigquery-bounded-backfill-evidence.md) | Bounded backfill: 6,104 rows exported from Cloud SQL bronze.market_events and loaded into BigQuery market_events_raw; source/target count match accepted; analytical query by symbol/event_type confirmed; PLAN_EXIT=0; Cloud SQL NEVER/STOPPED |

---

## CI/CD and Deployment Evidence

| Workflow | Trigger | Scope |
|---|---|---|
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | Push to main / PR | Lint (ruff), tests (pytest), import smoke test; dbt compile/run/test against ephemeral Postgres service container |
| [.github/workflows/terraform-plan.yml](../.github/workflows/terraform-plan.yml) | PR / push to main (infra path) | Terraform plan via Workload Identity; no apply |
| [.github/workflows/deploy-worker-cloud-run.yml](../.github/workflows/deploy-worker-cloud-run.yml) | workflow_dispatch (manual) | Builds and deploys worker image to Cloud Run |
| [.github/workflows/deploy-api-cloud-run.yml](../.github/workflows/deploy-api-cloud-run.yml) | workflow_dispatch (manual) | Builds and deploys API image to Cloud Run |
| [.github/workflows/deploy-dbt-refresh-cloud-run.yml](../.github/workflows/deploy-dbt-refresh-cloud-run.yml) | workflow_dispatch (manual) | Builds and pushes dbt refresh job image to Artifact Registry only -- no Cloud Run mutation; Terraform owns `google_cloud_run_v2_job.rtdp_dbt_refresh_job`; job deployed via Terraform apply; execution evidence accepted |
| [.github/workflows/bigquery-quality-checks.yml](../.github/workflows/bigquery-quality-checks.yml) | workflow_dispatch (manual) | Runs 6 read-only BigQuery quality checks against `rtdp_analytics.market_events_raw`; authenticates via OIDC Workload Identity; uploads `ci-report.json` artifact; no BigQuery mutation; no Cloud SQL start |

Supporting evidence:

- [docs/cloud-run-worker-manual-deploy-evidence.md](cloud-run-worker-manual-deploy-evidence.md) -- validated worker manual deploy run
- [docs/api-deploy-ci-runbook.md](api-deploy-ci-runbook.md) -- API deploy CI runbook
- [docs/api-manual-deploy-evidence.md](api-manual-deploy-evidence.md) -- validated API manual deploy run
- [docs/dbt-refresh-cloud-run-deploy-evidence.md](dbt-refresh-cloud-run-deploy-evidence.md) -- `rtdp-dbt-refresh-job` deployed via Terraform apply; zero-diff plan confirmed
- [docs/dbt-refresh-job-execution-proof-evidence.md](dbt-refresh-job-execution-proof-evidence.md) -- `rtdp-dbt-refresh-job` executed against Cloud SQL; dbt run PASS=2, dbt test PASS=22, API readback HTTP 200; accepted
- [docs/dbt-scheduler-switch-evidence.md](dbt-scheduler-switch-evidence.md) -- scheduler switched to `rtdp-dbt-refresh-job:run`; scheduler-triggered execution (`rtdp-dbt-refresh-job-6zb52`) accepted; scheduler PAUSED by default
- [docs/dbt-refresh-cloud-run-job-plan.md](dbt-refresh-cloud-run-job-plan.md) -- Terraform resource definition for `google_cloud_run_v2_job.rtdp_dbt_refresh_job`; credential contract; scheduler target; Cloud SQL NEVER/STOPPED by default
- [docs/dbt-operational-migration-plan.md](dbt-operational-migration-plan.md) -- migration plan executed; dbt is now the operational scheduled transformation path
- [docs/dbt-incremental-silver-evidence.md](dbt-incremental-silver-evidence.md) -- `silver_market_event_minute_aggregates` converted from `materialized='table'` to `materialized='incremental'` with `incremental_strategy='delete+insert'`, `unique_key=['symbol', 'window_start']`, and a 10-minute `is_incremental()` lookback guard; LOCAL CODE ONLY; Cloud SQL live execution NOT YET PROVEN; no Terraform, CI, or workflow changes
- [docs/dbt-incremental-gold-evidence.md](dbt-incremental-gold-evidence.md) -- `gold_market_event_daily_aggregates` converted from `materialized='table'` to `materialized='incremental'` with `incremental_strategy='delete+insert'`, `unique_key=['symbol', 'event_date']`, and a 3-day `is_incremental()` lookback guard; COALESCE DATE '1900-01-01' fallback for empty target; dbt compile/run/test: 8/8 tests PASS; 239 pytest PASS; ruff clean; PLAN_EXIT=0; LOCAL DISPOSABLE POSTGRES VALIDATION PASSED; Cloud SQL live execution NOT YET PROVEN; no Terraform, CI, or workflow changes
- [docs/dbt-cloud-sql-incremental-execution-proof.md](dbt-cloud-sql-incremental-execution-proof.md) -- VALIDATED -- CLOUD SQL LIVE INCREMENTAL DBT EXECUTION PROVEN; image built from commit `91cf94b2` (workflow run 26117517140; `:latest` tag updated; Cloud Run Job not mutated); execution `rtdp-dbt-refresh-job-gqrl8` completed successfully in 1m17.25s (2026-05-19T18:51:50Z); dbt run PASS=2 (gold INSERT 0 7; silver INSERT 0 13); dbt test PASS=22; Cloud SQL `rtdp-postgres` started temporarily and restored to STOPPED/NEVER; both schedulers PAUSED throughout; PLAN_EXIT=0; docs-only branch; no Terraform, SQL, Python, or workflow changes
- [docs/bigquery-quality-checks-evidence.md](bigquery-quality-checks-evidence.md) -- read-only quality script; 6/6 checks pass against `rtdp_analytics.market_events_raw`; row_count=6120; staging=0; no mutation
- [docs/bigquery-quality-workflow-proof-evidence.md](bigquery-quality-workflow-proof-evidence.md) -- `workflow_dispatch` Run ID 25982120058; conclusion: success; artifact status: ok; 6/6 checks passed; manual dispatch only
- [docs/bigquery-quality-schedule-enabled-evidence.md](bigquery-quality-schedule-enabled-evidence.md) -- schedule `15 6 * * *` enabled via PR #141; `workflow_dispatch` Run ID 25984483471 post-merge: success; 6/6 checks passed; scheduled event real execution NOT YET PROVEN
- [docs/bigquery-quality-thresholds-evidence.md](bigquery-quality-thresholds-evidence.md) -- threshold checks (PR #145): `row_count_minimum` live pass (6120 >= 6000); `freshness_max_age_hours` skipped as expected (unit-tested only, not live-proven); 210 tests passed; no mutation; scheduled event real execution NOT YET PROVEN
- [docs/bigquery-quality-alert-notification-proof-evidence.md](bigquery-quality-alert-notification-proof-evidence.md) -- controlled failure proof (PR #150): Run 26007825072 success (min_row_count=1; 6120 >= 1); Run 26007909020 failure (min_row_count=999999999; 6120 < 999999999); `row_count_minimum` fail; exit code 1; artifact preserved despite failure; GitHub Actions UI failure surface observable; email not proven; bell not proven; Cloud Monitoring not proven; scheduled event NOT YET PROVEN
- [docs/bigquery-freshness-live-validation-evidence.md](bigquery-freshness-live-validation-evidence.md) -- freshness live failure proof (PR #153): Run ID 26020167461; `freshness_max_age_hours` fail (age_hours 45.5496 > 1.0; max_ingest_timestamp 2026-05-16 10:08:49.141452+00); `row_count_minimum` pass (6120 >= 1); `staging_table_empty` pass (0); artifact preserved; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; passing `freshness_max_age_hours` live run NOT YET PROVEN; scheduled event NOT YET PROVEN
- [docs/bigquery-quality-cloud-monitoring-metrics-plan.md](bigquery-quality-cloud-monitoring-metrics-plan.md) -- Cloud Monitoring quality metrics plan (PR #155): PLANNED - QUALITY METRICS NOT YET IMPLEMENTED; 5 planned metric types (`custom.googleapis.com/rtdp/bigquery_quality/status`, `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count`, `custom.googleapis.com/rtdp/bigquery_quality/check_pass`, `custom.googleapis.com/rtdp/bigquery_quality/row_count`, `custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours`); preferred script `scripts/push_bigquery_quality_metrics.py`; metric emission step with `if: always()`; `roles/monitoring.metricWriter` required; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed; Cloud Monitoring quality metrics NOT implemented; Cloud Monitoring alerting NOT proven; real scheduled event execution NOT YET PROVEN
- [docs/bigquery-quality-cloud-monitoring-metrics-evidence.md](bigquery-quality-cloud-monitoring-metrics-evidence.md) -- VALIDATED - QUALITY METRICS EMITTED TO CLOUD MONITORING; PR #157 (metric emission script + workflow step + Terraform IAM); PR #158 (evidence indexed); safe run 26061129567 (conclusion success; status = 1; failed_checks_count = 0; row_count = 6120); failure run 26061541771 (conclusion failure; status = 0; failed_checks_count = 1; check_pass row_count_minimum = 0; row_count = 6120); Pushed 10 time series to Cloud Monitoring; roles/monitoring.metricWriter applied; PLAN_EXIT=0; 239 passed; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed; freshness_age_hours metric NOT YET PROVEN; Cloud Monitoring alerting NOT YET PROVEN; email notification delivery NOT PROVEN; GitHub notification bell delivery NOT PROVEN
- [docs/bigquery-quality-cloud-monitoring-alert-policy-evidence.md](bigquery-quality-cloud-monitoring-alert-policy-evidence.md) -- VALIDATED - ALERT POLICY APPLIED; INCIDENT/NOTIFICATION DELIVERY NOT YET PROVEN; PR #160 (Terraform `google_monitoring_alert_policy.bigquery_quality_failure`; display name `RTDP BigQuery Quality Failure`); PR #161 (evidence indexed); Run ID 26065876070 (workflow_dispatch; conclusion failure; controlled failure min_row_count=999999999); `failed_checks_count = 1`; Pushed 10 time series to Cloud Monitoring; PLAN_EXIT=0; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed; Incident creation NOT YET PROVEN; Email notification delivery NOT YET PROVEN; GitHub notification bell delivery NOT YET PROVEN; freshness_age_hours metric NOT YET PROVEN
- [docs/bigquery-quality-alert-incident-notification-proof.md](bigquery-quality-alert-incident-notification-proof.md) -- PARTIAL - ALERT POLICY AND EMAIL CHANNEL VALIDATED; INCIDENT/EMAIL DELIVERY NOT YET PROVEN; PR #163; alert policy `RTDP BigQuery Quality Failure` exists and is enabled; notification channel `RTDP Operator Email Alerts` exists and is enabled (email type); Run ID 26065876070 (workflow_dispatch; conclusion failure; controlled failure min_row_count=999999999); `failed_checks_count = 1`; Pushed 10 time series to Cloud Monitoring; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed; Incident creation NOT YET PROVEN; Email notification delivery NOT YET PROVEN; GitHub notification bell delivery NOT YET PROVEN; freshness_age_hours metric NOT YET PROVEN
- [docs/bigquery-quality-freshness-age-hours-metric-evidence.md](bigquery-quality-freshness-age-hours-metric-evidence.md) -- VALIDATED - FRESHNESS AGE HOURS METRIC EMITTED TO CLOUD MONITORING; PR #165; Run ID 26069840695 (workflow_dispatch; conclusion success; freshness_max_age_hours=999999); age_hours = 62.9712; metric custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours; doubleValue=62.9712; series_count=1; Pushed 12 time series to Cloud Monitoring; endTime 2026-05-19T01:07:08Z; previous failed attempt 26069153131 (HTTP 500; series_count=0); BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed; Incident creation NOT YET PROVEN; Email notification delivery NOT YET PROVEN; GitHub notification bell delivery NOT YET PROVEN
- [docs/bigquery-quality-scheduled-event-execution-evidence.md](bigquery-quality-scheduled-event-execution-evidence.md) -- VALIDATED - SCHEDULED EVENT EXECUTION PROVEN; PR #167; Run ID 26028523804 (event schedule; conclusion success); cron `15 6 * * *`; workflow `BigQuery Quality Checks`; commit `dce441d3040ac8fd72a204eaa2e4775c42d06169`; service account `rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com`; `min_row_count=1`; `freshness_max_age_hours=0`; artifact ID 7055640475; `status: ok`; `failed_checks: []`; row_count 6120; `staging_table_empty` pass; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; Terraform not changed; Terraform apply not executed; no secrets printed; Artifact preserved; Incident creation NOT YET PROVEN; Email notification delivery NOT YET PROVEN; GitHub notification bell delivery NOT YET PROVEN
- [docs/bigquery-quality-incident-notification-delivery-proof.md](bigquery-quality-incident-notification-delivery-proof.md) -- VALIDATED - INCIDENT CREATION AND EMAIL NOTIFICATION DELIVERY PROVEN; PR #169; Run ID 26089332693 (workflow_dispatch; conclusion failure; controlled failure min_row_count=999999999); artifact ID 7080086765; `failed_checks: ["row_count_minimum"]`; 10 time series pushed to Cloud Monitoring; Cloud Monitoring alert incident OPEN state proven by CLI; email notification delivery proven by Gmail inbox screenshot evidence; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; Terraform not changed; Terraform apply not executed; no secrets printed; GitHub notification bell delivery NOT YET PROVEN; Dataflow not implemented
- [docs/evidence/bigquery-quality-checks/report.json](evidence/bigquery-quality-checks/report.json) -- machine-readable quality report committed under docs/evidence

Neither deploy workflow triggers automatically on merge to main; both require explicit manual dispatch.

---

## Observability Evidence

| Document | What It Proves |
|---|---|
| [docs/cloud-observability-evidence.md](cloud-observability-evidence.md) | Cloud Logging structured logs across services and jobs |
| [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md) | Four logs-based metrics created and configured in Cloud Monitoring |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | timeSeries datapoints confirmed for worker and silver refresh success counters |
| [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) | Two alert policies enabled; email notification channel attached |
| [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md) | 4-panel RTDP Pipeline Overview dashboard created in GCP and exported to JSON |
| [docs/notification-channels-evidence.md](notification-channels-evidence.md) | Email notification channel created and attached to both alert policies |

---

## Load and Throughput Evidence

All load tests were bounded and deterministic. Cloud SQL was started only during each test
window and returned to `NEVER / STOPPED` on completion. This is bounded validation evidence,
not a claim of enterprise-scale throughput.

| Document | Scope |
|---|---|
| [docs/load-test-plan.md](load-test-plan.md) | Test plan: event sizes, acceptance criteria, safety protocol |
| [docs/load-test-local-sample-evidence.md](load-test-local-sample-evidence.md) | 100-event JSONL generated and validated locally before cloud publish |
| [docs/load-test-100-cloud-evidence.md](load-test-100-cloud-evidence.md) | 100 events: 100 acks, 100 worker ok logs, metric sum=100, API readback confirmed |
| [docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md) | 1,000 events: all acceptance criteria met |
| [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) | 5,000 events: 5,000 acks, metric sum=4,963, DLQ empty, silver refresh succeeded |
| [docs/load-test-10000-cloud-evidence.md](load-test-10000-cloud-evidence.md) | VALIDATED -- 10,000-event cloud load test passed; published_total=10000; unique_message_ids=10000; publish_error_count=0; worker OK logs=10000; worker errors=0; Cloud Monitoring processed metric=10000; error metric=0; Cloud SQL prefix rows=10000; duplicate event_id count=0; DLQ subscriptions=0; Cloud SQL restored to STOPPED/NEVER; schedulers PAUSED; Dataflow not implemented |
| [docs/cloud-load-test-50000-plan.md](cloud-load-test-50000-plan.md) | PLANNED -- 50,000-event cloud load test plan; execution NOT YET PROVEN; no events published; no Cloud SQL start; no Terraform apply; Dataflow not implemented |
| [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md) | VALIDATED -- 50,000-event cloud load test passed; published_total=50000; unique_message_ids=50000; publish_error_count=0; worker OK logs=50000; worker errors=0; Cloud Monitoring processed metric=50002; error metric=0; Cloud SQL prefix rows=50000; duplicate event_id count=0; DLQ subscriptions=0; Cloud SQL restored to STOPPED/NEVER; schedulers PAUSED; Dataflow not implemented |

---

## Reliability and Safety Evidence

| Document | What It Proves |
|---|---|
| [docs/pubsub-retry-dlq-inspection.md](pubsub-retry-dlq-inspection.md) | Read-only inspection of production Pub/Sub retry and DLQ configuration before mutation |
| [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) | Production DLQ topic and deadLetterPolicy configured (maxDeliveryAttempts=5, 10s/60s backoff) |
| [docs/dlq-malformed-message-validation-plan.md](dlq-malformed-message-validation-plan.md) | PLANNED -- DLQ malformed-message validation plan; defines a bounded one-message poison payload procedure to prove Pub/Sub retry and DLQ routing in a future execution branch; no malformed message published; no Cloud SQL start; no Terraform apply; DLQ malformed-message routing NOT YET PROVEN |
| [docs/dlq-deduplication-strategy.md](dlq-deduplication-strategy.md) | STRATEGY -- DLQ deduplication strategy after malformed-message validation; defines deduplication key hierarchy, future DLQ consumer behaviour, proposed poison-message schema, risks, controls, and explicit non-claims; no GCP workload execution; no Cloud SQL start; no Terraform apply |
| [docs/silver-refresh-scheduler-evidence.md](silver-refresh-scheduler-evidence.md) | Cloud Scheduler job configured and paused; service account and invoker role validated |
| [docs/silver-refresh-scheduler-execution-proof-evidence.md](silver-refresh-scheduler-execution-proof-evidence.md) | Scheduler dispatched silver refresh job; execution succeeded; success metric confirmed |
| [docs/silver-refresh-job-validation.md](silver-refresh-job-validation.md) | Cloud Run Job silver refresh execution validated |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | Production-light SLO targets, error budget definition, incident severity levels, and incident response runbooks for all RTDP components |
| [docs/gold-cloud-sql-deployment-evidence.md](gold-cloud-sql-deployment-evidence.md) | Cloud SQL deployment evidence for gold daily aggregates: SQL applied, refresh returned 7 rows, API /aggregates/daily returned HTTP 200, Cloud SQL returned to NEVER / STOPPED |
| [docs/gold-cloud-sql-deployment-runbook.md](gold-cloud-sql-deployment-runbook.md) | Controlled runbook used to deploy the gold daily aggregates layer to Cloud SQL |
| [docs/dbt-ci-validation-evidence.md](dbt-ci-validation-evidence.md) | dbt transformation layer (PR #104) and CI validation (PR #105): 22 dbt tests, 117 pytest, ruff clean; ephemeral pgvector container; no Cloud SQL mutation |
| [docs/dbt-cloud-sql-migration-runbook.md](dbt-cloud-sql-migration-runbook.md) | Controlled runbook used to validate dbt silver and gold models against Cloud SQL and reconcile output with the stored-function baseline |
| [docs/dbt-cloud-sql-validation-evidence.md](dbt-cloud-sql-validation-evidence.md) | dbt compile/run/test succeeded against Cloud SQL; stored-function output matched; API readback returned HTTP 200 |

---

## Cost Control Evidence

Cost-control state is recorded throughout the evidence documents. The following practices
are verified across the evidence base:

- Cloud SQL (`rtdp-postgres`) is kept at activation policy `NEVER / STOPPED` and started only
  during bounded validation windows. This state is confirmed in every load test and Terraform
  import evidence document.
- Cloud Scheduler (`rtdp-silver-refresh-scheduler`) targets `rtdp-dbt-refresh-job:run` and is
  kept `PAUSED` by default; resumed only during controlled execution proofs. Final state
  confirmed as `PAUSED` in [docs/dbt-scheduler-switch-evidence.md](dbt-scheduler-switch-evidence.md).
- Terraform state uses a GCS-backed remote backend. No `terraform apply` was executed during
  import operations; all changes were import-only with verified zero-diff plans.

---

## Platform Audit

| Document | Summary |
| --- | --- |
| [docs/executive-platform-audit-after-50k.md](executive-platform-audit-after-50k.md) | EXECUTIVE AUDIT -- post-50k platform assessment; translates bounded 50,000-event Pub/Sub -> Cloud Run -> Cloud SQL evidence into recruitment/B2B positioning; includes proven evidence, remaining gaps, devil-advocate review, and next steps; Dataflow not implemented; sustained production throughput not claimed. |
| [docs/recruiter-facing-platform-summary.md](recruiter-facing-platform-summary.md) | RECRUITER SUMMARY -- one-page hiring/B2B translation of the Real-Time Data Platform; explains the 50,000-event bounded GCP milestone, proven capabilities, safe interview positioning, best-fit roles, and explicit non-claims; Dataflow not implemented; sustained production throughput not claimed. |
| [docs/latency-throughput-analysis-after-50k.md](latency-throughput-analysis-after-50k.md) | ANALYSIS -- latency and throughput analysis after 50,000-event bounded cloud load test; derives conservative publish rates from existing evidence, compares 10k vs 50k runs, explains Cloud Monitoring 50,002 DELTA alignment, and documents remaining latency/sustained-throughput gaps; no new events published; no Cloud SQL start; no p50/p95/p99 claim. |
| [docs/gap-closure-snapshot-after-dlq.md](gap-closure-snapshot-after-dlq.md) | SNAPSHOT -- post-50k and post-DLQ gap closure snapshot; summarizes closed gaps, remaining gaps, production-likeness, safe interview positioning, and next branch priorities; Dataflow not implemented; sustained throughput not claimed; exactly-once DLQ semantics not claimed. |
| [docs/steady-state-throughput-test-plan.md](steady-state-throughput-test-plan.md) | PLAN -- steady-state throughput test plan after 50k bounded load; defines a safe 10 events/sec for 30 minutes validation, acceptance criteria, instrumentation, preflight checks, scale-up path, and explicit non-claims; no events published; no Cloud SQL start; no Terraform apply; sustained throughput NOT YET PROVEN. |
| [docs/latency-instrumentation-plan.md](latency-instrumentation-plan.md) | PLAN -- latency instrumentation plan; defines producer, worker, and database timestamps required for p50/p95/p99 latency evidence; no events published; no Cloud SQL start; no schema migration; no Terraform apply; latency percentiles NOT YET PROVEN. |
| [docs/latency-artifact-instrumentation-evidence.md](latency-artifact-instrumentation-evidence.md) | LOCAL VALIDATION -- latency artifact/log instrumentation implemented for Option B; producer artifact and worker stage timestamps are unit-tested; no events published; no Cloud SQL start; no schema migration; no Terraform apply; cloud p50/p95/p99 latency NOT YET PROVEN. |

---

## Known Remaining Gaps

- BigQuery analytical tier, bounded backfill, incremental append, and append scheduler are
  implemented and accepted. Read-only quality checks are implemented and validated both
  locally and via manual GitHub Actions dispatch; schedule `15 6 * * *` is enabled on `main`
  (PR #141) but scheduled event real execution is NOT YET PROVEN. Threshold checks
  (`row_count_minimum` always included; `freshness_max_age_hours` unit-tested only, not
  live-proven) merged via PR #145. Controlled failure and GitHub Actions UI failure surface
  proven via PR #150 (Run 26007909020: `row_count_minimum` fail; observed 6120 vs threshold
  999999999; exit code 1; artifact preserved); email notification delivery NOT PROVEN;
  GitHub notification bell delivery NOT PROVEN. `freshness_max_age_hours` live failure
  proven via PR #153 (Run 26020167461: age_hours 45.5496 > 1.0; max_ingest_timestamp
  2026-05-16 10:08:49.141452+00; BigQuery not mutated; Cloud SQL not started; Cloud
  Scheduler not executed); passing `freshness_max_age_hours` live run PROVEN (PR #165; Run ID 26069840695; age_hours = 62.9712; freshness_max_age_hours=999999; conclusion success). Cloud
  Monitoring quality metrics PROVEN via PR #157 + PR #158
  (`docs/bigquery-quality-cloud-monitoring-metrics-evidence.md`): safe run 26061129567
  (status = 1; failed_checks_count = 0; row_count = 6120); failure run 26061541771
  (status = 0; failed_checks_count = 1; check_pass row_count_minimum = 0;
  row_count = 6120); Pushed 10 time series to Cloud Monitoring;
  roles/monitoring.metricWriter applied; PLAN_EXIT=0; 239 passed; BigQuery not mutated;
  Cloud SQL not started; Cloud Scheduler not executed; no secrets printed;
  freshness_age_hours metric VALIDATED (PR #165; Run ID 26069840695; age_hours = 62.9712; metric custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours; doubleValue=62.9712; series_count=1; Pushed 12 time series to Cloud Monitoring; endTime 2026-05-19T01:07:08Z; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed); Cloud Monitoring alert policy APPLIED via
  PR #160 (`google_monitoring_alert_policy.bigquery_quality_failure`; display name RTDP
  BigQuery Quality Failure; Run ID 26065876070; failed_checks_count = 1; Pushed 10 time
  series to Cloud Monitoring; PLAN_EXIT=0); alert policy existence VALIDATED; email
  notification channel `RTDP Operator Email Alerts` existence VALIDATED;
  `failed_checks_count = 1` triggering metric VALIDATED (PR #163; Run ID 26065876070;
  Pushed 10 time series to Cloud Monitoring); Incident creation PROVEN and Email
  notification delivery PROVEN by PR #169 (`docs/bigquery-quality-incident-notification-delivery-proof.md`;
  Run ID 26089332693; alert OPEN state via CLI; Gmail inbox screenshot evidence for delivered
  Google Cloud Alerting email). GitHub notification bell delivery NOT YET PROVEN.
  Scheduled event execution PROVEN (PR #167; Run ID 26028523804; event schedule; cron 15 6 * * *; status ok; failed_checks []; row_count 6120; artifact ID 7055640475; BigQuery not mutated; Cloud SQL not started; Cloud Scheduler not executed; no secrets printed). Remaining BigQuery work: GitHub notification bell delivery proof; Dataflow is
  not yet implemented.
- dbt is the operational scheduled transformation path (accepted as of
  `docs/post-dbt-scheduler-audit-refresh`). Silver incremental model implemented (PR #172;
  see `docs/dbt-incremental-silver-evidence.md`). Gold incremental model implemented (PR #173;
  see `docs/dbt-incremental-gold-evidence.md`; 239 pytest passed; 8/8 dbt tests passed;
  PLAN_EXIT=0). Cloud SQL live incremental execution PROVEN (execution `rtdp-dbt-refresh-job-gqrl8`;
  dbt run PASS=2; gold INSERT 0 7; silver INSERT 0 13; dbt test PASS=22; Cloud SQL restored
  to NEVER/STOPPED; PLAN_EXIT=0; see `docs/dbt-cloud-sql-incremental-execution-proof.md`).
  Remaining dbt work: dbt-specific observability metrics.
- Sustained throughput validation above 5,000 events now has a 50,000-event bounded cloud proof: see [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md). Dataflow remains deferred until higher-scale limits, latency requirements, replay semantics, or sustained-throughput requirements justify it.
- Automatic deploy-on-merge: both deploy workflows require manual dispatch.
