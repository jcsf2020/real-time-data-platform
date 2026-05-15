# Architecture Review

This document is a production-light architecture review for the Real-Time Data Platform.
It summarizes implemented capabilities, infrastructure approach, operational controls,
trade-offs, and remaining gaps based solely on evidence present in this repository.
It does not overstate maturity beyond what the evidence record supports.

---

## System Purpose

- Ingests synthetic market-style trade events via an event broker (Redpanda locally,
  Pub/Sub on GCP).
- Validates events against a versioned Pydantic contract and persists them idempotently
  into PostgreSQL.
- Exposes read-back and aggregate endpoints through a FastAPI serving layer.
- Demonstrates parallel local (Docker Compose) and GCP (Cloud Run + Cloud SQL + Pub/Sub)
  deployment paths.
- Operates as a cost-controlled, evidence-backed production-light platform, not a
  continuously running production service.

---

## Architecture At A Glance

Local path:

```
Producer --> Redpanda/Kafka --> Consumer --> PostgreSQL --> FastAPI
```

GCP path:

```
Pub/Sub topic (market-events-raw)
  --> push subscription
        --> Cloud Run Worker (rtdp-pubsub-worker)
              --> Cloud SQL PostgreSQL (bronze.market_events)
                    --> Cloud Run API (rtdp-api)

Cloud Scheduler (rtdp-silver-refresh-scheduler)
  --> Cloud Run Job (rtdp-dbt-refresh-job)  [accepted operational scheduled path]
        --> dbt run: silver_market_event_minute_aggregates
                     gold_market_event_daily_aggregates
        --> dbt test (22 tests)

Cloud Run Job (rtdp-silver-refresh-job)  [legacy rollback path; not actively scheduled]
  --> silver.refresh_market_event_minute_aggregates()

Cloud SQL (rtdp-postgres) bronze.market_events
  --> bounded batch export (COPY --> CSV --> bq load; bounded validation window only)
        --> BigQuery rtdp_analytics.market_events_raw
              [6,104 rows; bounded backfill accepted; no continuous streaming path]

Cloud Logging --> logs-based metrics --> alert policies / dashboard
```

---

## Implemented Runtime Components

| Component | Runtime | Responsibility | Evidence |
|---|---|---|---|
| Python producer | Local Docker Compose | Publishes MarketEvent records to Redpanda topic | README.md |
| Local consumer | Local Docker Compose | Validates and persists events; writes observability metrics | README.md |
| FastAPI API | Cloud Run (rtdp-api) | Serves /health /readiness /events /aggregates/minute /metrics | gcp-end-to-end-validation.md |
| Pub/Sub worker | Cloud Run (rtdp-pubsub-worker) | Receives push messages, validates MarketEvent, writes to bronze | gcp-worker-cloud-validation.md |
| dbt refresh job | Cloud Run Job (rtdp-dbt-refresh-job) | Runs dbt deps → dbt run (silver + gold models) → dbt test (22 tests) against Cloud SQL; accepted operational scheduled transformation path | dbt-refresh-job-execution-proof-evidence.md, dbt-scheduler-switch-evidence.md |
| Silver refresh job (legacy) | Cloud Run Job (rtdp-silver-refresh-job) | Calls silver.refresh_market_event_minute_aggregates(); preserved as rollback path; not actively scheduled | silver-refresh-scheduler-execution-proof-evidence.md |
| Cloud Scheduler | GCP Managed | Dispatches dbt refresh job (rtdp-dbt-refresh-job:run) on */15 * * * * UTC (PAUSED by default) | dbt-scheduler-switch-evidence.md |
| Cloud SQL | GCP Managed PostgreSQL 16 (rtdp-postgres) | Durable operational store for medallion schemas; NEVER / STOPPED outside bounded validation windows | cloud-sql-terraform-import-plan-evidence.md |
| BigQuery analytical dataset | GCP Managed BigQuery (rtdp_analytics, europe-west1) | Analytical warehouse; three Terraform-managed tables: market_events_raw (DAY partition on event_timestamp, clustered by symbol/event_type), market_event_minute_aggregates (DAY on window_start, clustered by symbol/event_type), market_event_daily_aggregates (DAY on event_date, clustered by symbol); worker service account granted bigquery.dataEditor and bigquery.jobUser | bigquery-terraform-apply-evidence.md, bigquery-bounded-backfill-evidence.md |
| Pub/Sub topic / subscription / DLQ | GCP Managed | market-events-raw topic; push subscription with deadLetterPolicy | production-pubsub-dlq-evidence.md |
| Cloud Monitoring | GCP Managed | 4 logs-based metrics, 4-panel dashboard, 2 alert policies, email channel | cloud-alert-policies-evidence.md |

---

## Infrastructure And Deployment Model

Terraform manages all runtime GCP resources via a GCS-backed remote state
(`rtdp-terraform-state-project-42987e01-2123-446b-ac7`, `europe-west1`). Existing
infrastructure was imported in phased batches (Pub/Sub, Scheduler, Monitoring, Cloud Run,
Cloud SQL, Secret Manager, service accounts, IAM, Workload Identity, Artifact Registry).
Each batch was validated with a zero-diff `terraform plan` before being committed.
Terraform import phases did not use apply. Any later apply operations are documented
in their own scoped evidence files.

Workload Identity Federation (GitHub Actions OIDC provider) is imported into Terraform
state and authenticates the Terraform Plan CI workflow without stored service account keys.

CI/CD workflows:

- `ci.yml` -- push to main and pull requests; ruff lint, pytest, import smoke test.
- `terraform-plan.yml` -- changes to `infra/` paths; `terraform plan` via Workload
  Identity; no apply.
- `deploy-worker-cloud-run.yml` -- manual `workflow_dispatch`; builds and pushes
  `rtdp-pubsub-worker` to Artifact Registry with a commit-SHA image tag, then deploys to
  Cloud Run.
- `deploy-api-cloud-run.yml` -- manual `workflow_dispatch`; builds and pushes `rtdp-api`
  to Artifact Registry with a commit-SHA image tag, then deploys to Cloud Run.
- `deploy-dbt-refresh-cloud-run.yml` -- manual `workflow_dispatch`; builds and pushes the
  `rtdp-dbt-refresh-job` image to Artifact Registry only. Terraform owns
  `google_cloud_run_v2_job.rtdp_dbt_refresh_job`; the Cloud Run Job was deployed via
  `terraform apply` on `feat/dbt-refresh-cloud-run-deploy` (zero-diff plan confirmed;
  `CREATE_TIME=2026-05-13T19:16:23Z`). Execution evidence accepted
  (`docs/dbt-refresh-job-execution-proof-evidence.md`). Scheduler switched to target
  `rtdp-dbt-refresh-job:run` (`docs/dbt-scheduler-switch-evidence.md`).

No deploy workflow triggers automatically on merge to main.

---

## Data Model And Processing

The PostgreSQL database (`realtime_platform`) uses a medallion schema layout:

- `bronze.market_events` -- raw validated events; append-only, full fidelity.
- `silver.market_event_minute_aggregates` -- per-symbol per-minute rollup aggregates,
  populated by `silver.refresh_market_event_minute_aggregates()`.
- `gold` -- `gold.market_event_daily_aggregates` table and
  `gold.refresh_market_event_daily_aggregates()` function deployed to Cloud SQL and
  validated through API readback.
- `observability.pipeline_metrics` -- consumer metric time-series (local consumer only).
- `ai.market_event_embeddings` -- pgvector-enabled table; schema created, not populated.

The `MarketEvent` contract (Pydantic v2) is defined once in `packages/contracts` and
imported by both producer and consumer. The `event_id` field is the idempotency key;
persistence uses `ON CONFLICT(event_id) DO NOTHING`. A `schema_version` literal field
enables forward-compatible contract evolution.

The BigQuery dataset `rtdp_analytics` provides the analytical tier, separate from the
Cloud SQL operational store:

- `market_events_raw` -- raw event history mirrored from bronze.market_events; DAY
  partition on event_timestamp; clustered by symbol, event_type. Populated by bounded
  batch backfill (6,104 rows accepted); no continuous streaming path exists yet.
- `market_event_minute_aggregates` -- curated minute aggregate schema; DAY partition on
  window_start; clustered by symbol, event_type. Schema provisioned via Terraform;
  population from BigQuery-native transformations is not yet implemented.
- `market_event_daily_aggregates` -- curated daily aggregate schema; DAY partition on
  event_date; clustered by symbol. Schema provisioned via Terraform; population from
  BigQuery-native transformations is not yet implemented.

---

## Observability And Reliability

- **Structured logs**: Cloud Run worker and silver refresh job emit structured `jsonPayload`
  logs to Cloud Logging, validated in gcp-worker-cloud-validation.md.
- **Logs-based metrics**: four Cloud Monitoring metrics with confirmed timeSeries datapoints:
  `worker_message_processed_count`, `worker_message_error_count`,
  `silver_refresh_success_count`, `silver_refresh_error_count`.
- **Dashboard**: RTDP Pipeline Overview 4-panel dashboard visualises all four metrics.
  Definition version-controlled at `infra/monitoring/dashboards/rtdp-pipeline-overview.json`.
- **Alert policies**: two enabled policies -- RTDP Worker Message Error Alert and RTDP
  Silver Refresh Error Alert -- both with an email notification channel attached.
- **Pub/Sub DLQ**: production push subscription has `deadLetterPolicy` with
  `maxDeliveryAttempts=5`, 10s/60s backoff, routing failed deliveries to
  `market-events-raw-dlq`.
- **Scheduler execution proof**: `rtdp-silver-refresh-scheduler` previously dispatched
  `rtdp-silver-refresh-job` (silver_refresh_success_count confirmed TOTAL=1 in Cloud
  Monitoring). Scheduler has since been switched to target `rtdp-dbt-refresh-job:run`; a
  controlled scheduler-triggered execution (`rtdp-dbt-refresh-job-6zb52`) completed with
  `dbt run` PASS=2 and `dbt test` PASS=22. Scheduler remains PAUSED by default.
- **Cloud SQL cost control**: `rtdp-postgres` is kept `NEVER / STOPPED` outside bounded
  validation windows; confirmed in every evidence document.

---

## Cost Control

Cloud SQL (`rtdp-postgres`) is kept `NEVER / STOPPED` by default, started only during
bounded validation windows and stopped immediately afterwards. Cloud Scheduler
(`rtdp-silver-refresh-scheduler`) targets `rtdp-dbt-refresh-job:run` and is kept `PAUSED`
by default; it is resumed only for controlled execution proofs. All deployments are manually
triggered; no continuous pipeline incurs unexpected build or runtime costs.

This platform operates under a production-light constraint model: compute resources are
inactive outside defined validation windows. It is not a continuously running production
service.

---

## Validated Capabilities

| Capability | Evidence |
|---|---|
| Local pipeline tests pass | ci.yml -- 116 tests, ruff clean |
| GCP end-to-end validation | gcp-end-to-end-validation.md |
| Pub/Sub worker processing | gcp-worker-cloud-validation.md |
| API manual deploy (workflow_dispatch) | api-manual-deploy-evidence.md |
| Worker manual deploy (workflow_dispatch) | cloud-run-worker-manual-deploy-evidence.md |
| Terraform zero-diff plan (all resources) | All *-import-plan-evidence.md files |
| GCS remote backend active | terraform-remote-backend-migration-evidence.md |
| Artifact Registry commit-SHA image tags | api-manual-deploy-evidence.md, cloud-run-worker-manual-deploy-evidence.md |
| Cloud Monitoring metrics with datapoints | cloud-logs-based-metrics-datapoint-validation.md |
| Alert policies with email notification | cloud-alert-policies-evidence.md |
| 4-panel Cloud Monitoring dashboard | cloud-monitoring-dashboard-evidence.md |
| 100-event cloud load test (accepted) | load-test-100-cloud-evidence.md |
| 1,000-event cloud load test (accepted) | load-test-1000-cloud-evidence.md |
| 5,000-event cloud load test (accepted) | load-test-5000-cloud-evidence.md |
| DLQ / deadLetterPolicy configured | production-pubsub-dlq-evidence.md |
| Scheduler / silver refresh execution proof | silver-refresh-scheduler-execution-proof-evidence.md |
| dbt Cloud Run Job deployment (Terraform apply, zero-diff plan) | dbt-refresh-cloud-run-deploy-evidence.md |
| dbt refresh job execution proof (dbt run PASS=2, dbt test PASS=22, API readback HTTP 200) | dbt-refresh-job-execution-proof-evidence.md |
| Scheduler switched to dbt refresh job; scheduler-triggered execution accepted | dbt-scheduler-switch-evidence.md |
| BigQuery analytical tier scaffold: dataset rtdp_analytics + 3 tables + IAM (6 Terraform resources applied; PLAN_EXIT=0) | bigquery-terraform-apply-evidence.md |
| BigQuery bounded backfill: 6,104 rows from Cloud SQL bronze.market_events to BigQuery market_events_raw; source/target count match accepted; analytical query by symbol/event_type confirmed; PLAN_EXIT=0; Cloud SQL NEVER / STOPPED | bigquery-bounded-backfill-evidence.md |

---

## Key Trade-offs

- **Cloud SQL as operational serving store; BigQuery as analytical warehouse**: Cloud SQL
  provides the row-level access patterns required for the FastAPI serving layer. BigQuery
  (`rtdp_analytics`) provides the analytical tier: three Terraform-managed, DAY-partitioned,
  clustered tables. A bounded backfill of 6,104 rows from `bronze.market_events` to
  `market_events_raw` has been executed and validated with source-to-target count match and
  an analytical query by symbol/event_type. Continuous streaming from Pub/Sub to BigQuery
  is not yet implemented. Dataflow remains a future architectural target.
- **Pub/Sub + Cloud Run instead of Dataflow**: serverless and lower operational overhead
  for bounded event volumes; Dataflow would be appropriate for windowed aggregations and
  stateful streaming at higher scale.
- **Manual deploy workflows before automatic CD**: workflow_dispatch provides a controlled
  deployment gate without the risk of unintended deploys on every merge to main.
- **Cloud SQL stopped by default**: reduces idle compute cost; the operational constraint
  is a mandatory start step before each validation window.
- **dbt as the accepted operational scheduled transformation path**: dbt now runs silver and
  gold model refreshes on Cloud Run, scheduled by Cloud Scheduler (PAUSED by default). Stored
  functions (`silver.refresh_market_event_minute_aggregates()`,
  `gold.refresh_market_event_daily_aggregates()`) are preserved as a rollback path but are not
  actively scheduled. dbt provides SQL transformation governance, lineage tracking, and
  integrated testing that stored functions do not.
- **Evidence-first documentation**: raw evidence documents are verbose but provide
  traceable, audit-safe records of each execution.
- **Synthetic market-style data for validation**: deterministic event-ID prefixes allow
  precise scoping of log and metric queries; real-world data variability is not exercised.

---

## Known Remaining Gaps

- **BigQuery incremental append / recurring data movement**: The BigQuery analytical tier
  scaffold (dataset `rtdp_analytics`, three Terraform-managed tables) is implemented, and a
  bounded backfill of 6,104 rows from `bronze.market_events` has been accepted
  (bigquery-bounded-backfill-evidence.md). The remaining gap is the incremental append path:
  Pub/Sub fan-out, native BigQuery subscription, or scheduled batch export for continuous
  data movement. No continuous streaming to BigQuery exists. Dataflow remains future and is
  not implemented.
- **Automatic deploy-on-merge**: both deploy workflows require explicit manual dispatch;
  CI/CD pipeline automation is a planned next step.
- **Incremental dbt models**: silver and gold models use full-refresh table materialization;
  conversion to incremental merge on `(symbol, window_start)` / `(symbol, event_date)`
  remains open.
- **Sustained throughput above 5,000 events**: load tests cover bounded bursts only;
  sustained streaming throughput is not validated.
- **Stored-function retirement**: `silver.refresh_market_event_minute_aggregates()` and
  `gold.refresh_market_event_daily_aggregates()` are preserved as a dbt rollback path;
  retirement is deferred pending long-term operational confidence in the dbt job.
- **SLO / incident response documentation**: SLO targets and incident response runbooks are
  defined in docs/SLO_AND_INCIDENT_RESPONSE.md; operational validation remains
  production-light and scoped to controlled validation windows.

---

## How To Review Evidence

Recommended entry path for reviewers:

1. [README.md](../README.md) -- project overview and GCP status summary
2. [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) -- curated map of all evidence by category
3. [docs/gcp-architecture.md](gcp-architecture.md) -- GCP service mapping and target flow
4. [docs/api-manual-deploy-evidence.md](api-manual-deploy-evidence.md) -- API deployment path evidence
5. [docs/cloud-run-worker-manual-deploy-evidence.md](cloud-run-worker-manual-deploy-evidence.md) -- worker deployment evidence
6. [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) -- bounded throughput validation
