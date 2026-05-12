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
- Operates as a cost-controlled, evidence-driven portfolio-grade platform, not a
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
  --> Cloud Run Job (rtdp-silver-refresh-job)
        --> silver.market_event_minute_aggregates

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
| Silver refresh job | Cloud Run Job (rtdp-silver-refresh-job) | Calls silver.refresh_market_event_minute_aggregates() | silver-refresh-scheduler-execution-proof-evidence.md |
| Cloud Scheduler | GCP Managed | Dispatches silver refresh job on */15 * * * * UTC (PAUSED by default) | silver-refresh-scheduler-execution-proof-evidence.md |
| Cloud SQL | GCP Managed PostgreSQL 16 (rtdp-postgres) | Durable operational store for medallion schemas | cloud-sql-terraform-import-plan-evidence.md |
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

Neither deploy workflow triggers automatically on merge to main.

---

## Data Model And Processing

The PostgreSQL database (`realtime_platform`) uses a medallion schema layout:

- `bronze.market_events` -- raw validated events; append-only, full fidelity.
- `silver.market_event_minute_aggregates` -- per-symbol per-minute rollup aggregates,
  populated by `silver.refresh_market_event_minute_aggregates()`.
- `gold` -- `gold.market_event_daily_aggregates` table and `gold.refresh_market_event_daily_aggregates()` function deployed to Cloud SQL and validated through API readback.
- `observability.pipeline_metrics` -- consumer metric time-series (local consumer only).
- `ai.market_event_embeddings` -- pgvector-enabled table; schema created, not populated.

The `MarketEvent` contract (Pydantic v2) is defined once in `packages/contracts` and
imported by both producer and consumer. The `event_id` field is the idempotency key;
persistence uses `ON CONFLICT(event_id) DO NOTHING`. A `schema_version` literal field
enables forward-compatible contract evolution.

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
- **Scheduler execution proof**: `rtdp-silver-refresh-scheduler` dispatched
  `rtdp-silver-refresh-job` via `rtdp-scheduler-sa`; `silver_refresh_success_count`
  confirmed TOTAL=1 in Cloud Monitoring.
- **Cloud SQL cost control**: `rtdp-postgres` is kept `NEVER / STOPPED` outside bounded
  validation windows; confirmed in every evidence document.

---

## Cost Control

Cloud SQL (`rtdp-postgres`) is kept `NEVER / STOPPED` by default, started only during
bounded validation windows and stopped immediately afterwards. Cloud Scheduler
(`rtdp-silver-refresh-scheduler`) is kept `PAUSED` by default, resumed only for controlled
execution proofs. All deployments are manually triggered; no continuous pipeline incurs
unexpected build or runtime costs.

This setup is appropriate for a portfolio-grade production-light platform. It is not a
continuously running production service.

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

---

## Key Trade-offs

- **Cloud SQL instead of BigQuery** for current MVP persistence: provides a simpler
  operational store with row-level access for API serving; BigQuery is the target for
  analytical queries but is not yet implemented.
- **Pub/Sub + Cloud Run instead of Dataflow/Flink**: serverless and lower operational
  overhead for bounded event volumes; Dataflow would be appropriate for windowed
  aggregations and stateful streaming at higher scale.
- **Manual deploy workflows before automatic CD**: workflow_dispatch provides a controlled
  deployment gate without the risk of unintended deploys on every merge to main.
- **Cloud SQL stopped by default**: reduces idle compute cost; trade-off is a mandatory
  start step before each validation window.
- **Stored function for silver refresh instead of dbt**: simpler dependency footprint;
  no SQL transformation governance or lineage tracking.
- **Evidence-first documentation retained**: raw evidence documents are verbose but
  provide traceable, audit-safe records of each execution.
- **Synthetic market-style data for validation**: deterministic event-ID prefixes allow
  precise scoping of log and metric queries; real-world data variability is not exercised.

---

## Known Remaining Gaps

- **Gold analytics layer**: gold daily aggregates are deployed to Cloud SQL and validated through `GET /aggregates/daily`; evidence is available at `docs/gold-cloud-sql-deployment-evidence.md`.
- **dbt / transformation governance**: CI validation (compile, run, test against ephemeral Postgres) implemented in `feat/dbt-ci-validation`. Cloud SQL automated run remains pending (governance plan section 10).
- **Sustained throughput above 5,000 events**: load tests cover bounded bursts only;
  sustained streaming performance is not validated.
- **BigQuery and Dataflow**: documented as target architecture items; neither is implemented
  in the current runtime.
- **Automatic deploy-on-merge**: both deploy workflows require explicit manual dispatch;
  CI/CD pipeline automation is a planned next step.
- **SLO / incident response documentation**: SLO targets and incident response runbooks
  are defined in docs/SLO_AND_INCIDENT_RESPONSE.md; operational validation remains
  production-light and scoped to controlled validation windows.
- **API pagination behavior**: pagination should remain validated as part of future API
  evidence updates.

---

## How To Review Evidence

Recommended entry path for reviewers:

1. [README.md](../README.md) -- project overview and GCP status summary
2. [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) -- curated map of all evidence by category
3. [docs/gcp-architecture.md](gcp-architecture.md) -- GCP service mapping and target flow
4. [docs/api-manual-deploy-evidence.md](api-manual-deploy-evidence.md) -- API deployment path evidence
5. [docs/cloud-run-worker-manual-deploy-evidence.md](cloud-run-worker-manual-deploy-evidence.md) -- worker deployment evidence
6. [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) -- bounded throughput validation
