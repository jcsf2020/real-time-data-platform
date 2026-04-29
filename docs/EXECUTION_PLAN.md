# Real-Time Data Platform — Production Execution Plan

## Mission

Build a production-oriented, recruiter-ready, GCP-aligned real-time data engineering platform.

This project must be treated as a real B2B production delivery for a client, not as a tutorial, toy project, dashboard, or academic exercise.

## Portfolio Gap

Existing portfolio already covers Azure Databricks lakehouse, ADLS Gen2, Unity Catalog, Delta Lake, ADF, SQL-first Gold layer, dbt + Snowflake, dimensional modeling, SCD Type 2, Python orchestration, PostgreSQL analytics, data quality gates, API ingestion, Airflow, S3, Athena, GitHub Actions, and evidence-backed delivery.

This project must fill the missing gap:

- real-time streaming data engineering
- event-driven architecture
- Kafka/PubSub-style ingestion
- shared event contracts
- consumer reliability
- idempotent processing
- operational observability
- cloud-native runtime design
- GCP-oriented architecture
- production deployment patterns

## Current Baseline

Current local pipeline:

Python Producer -> Kafka topic market.events.raw -> Python Consumer -> Postgres bronze.market_events + observability.pipeline_metrics -> FastAPI /health /events /metrics

Validated evidence:

- producer emits market events into Kafka
- consumer reads Kafka offsets
- consumer validates events
- consumer persists bronze events into Postgres
- consumer writes observability metrics into Postgres
- API exposes health, events and metrics
- idempotency exists via ON CONFLICT(event_id) DO NOTHING

## Target Positioning

GCP-oriented real-time data engineering platform using Kafka, Python consumers, Postgres bronze storage, FastAPI serving, Prometheus-style observability, shared event contracts, idempotent writes, CI/CD and Cloud Run / PubSub-ready architecture.

## Production / B2B Standard

Every implementation decision must be judged as if this system were being delivered to a real client.

Rules:

- no fake claims
- no undocumented assumptions
- no hidden manual steps
- no fragile scripts without validation
- no feature without operational value
- no architecture without explanation
- no code that cannot be tested or reviewed
- no cloud claim unless implemented or explicitly documented as target architecture
- no secrets committed
- no unstable main branch
- no unnecessary complexity

Delivery standard:

Build locally, validate objectively, document honestly, and make the production path credible.

## Target Architecture

Event Source
-> Producer abstraction
   -> Local mode: Kafka topic market.events.raw
   -> GCP mode: Pub/Sub topic market-events-raw

Shared Event Contracts
-> Versioned MarketEvent schema
-> schema_version field
-> producer/consumer contract consistency
-> validation before publish and persistence

Stream Processing Layer
-> Python consumer
-> idempotent writes
-> processing lag metrics
-> error counters
-> offset tracking
-> windowed aggregation layer later

Storage Layer
-> Local: Postgres, bronze.market_events, observability.pipeline_metrics
-> GCP target: Cloud SQL PostgreSQL and BigQuery

Serving Layer
-> FastAPI: /health, /readiness, /events, /metrics, /metrics-prometheus, /version
-> GCP target: Cloud Run

Observability Layer
-> Current: Postgres metrics
-> Target: Prometheus endpoint, Grafana dashboard, consumer lag, throughput, errors, latency, Cloud Monitoring mapping

Cloud Alignment
-> Kafka locally
-> Pub/Sub adapter later
-> Cloud Run-compatible containers
-> Cloud SQL-compatible configuration
-> BigQuery/Dataflow architecture documentation

## Execution Rules

- Do not rebuild working components.
- Work incrementally.
- One branch at a time.
- One execution step at a time.
- Each branch must improve recruiter value.
- Each change must be locally verifiable.
- Main must remain stable.
- Do not add dashboards before platform foundations.
- Do not add cloud theater.
- Do not add unnecessary dependencies.
- Do not commit secrets.
- Do not hide known limitations.
- Every feature must support streaming, GCP alignment, observability, data contracts, production reliability, CI/CD, career evidence, or B2B production credibility.

## Roadmap

P0 — GitHub and CI Foundation
Create GitHub repository, push local repository, add GitHub Actions, add lint/test/import checks, and add basic README execution instructions.

P1 — Shared Event Contracts
Create shared contracts package, define versioned MarketEvent, add schema_version, make producer and consumer import the same contract, and add contract tests.

P2 — Test Foundation
Add unit tests for event contract, producer generation, consumer validation and API import. Run tests in CI.

P3 — Observability Standardization
Add Prometheus-style metrics endpoint. Track processed events, consumer errors, latest offset, lag, event counts by symbol and API health.

P4 — Docker Compose Full Runtime
Containerize producer, consumer and API. Extend Docker Compose with Kafka, Postgres, producer, consumer, API, Prometheus and Grafana.

P5 — GCP Architecture Alignment
Document mapping from Kafka to Pub/Sub, FastAPI to Cloud Run, Postgres to Cloud SQL, analytical export to BigQuery, metrics to Cloud Monitoring, and stream processing to Dataflow / Apache Beam.

P6 — Stream Processing Enrichment
Add windowed aggregations: events per symbol per minute, average price by symbol per window, volume by symbol per window, and late event detection.

P7 — Production Reliability
Add dead-letter handling, retry-safe persistence, readiness endpoint, structured JSON logs, graceful shutdown and environment-based config.

P8 — Career Evidence Package
Add final README, docs/career-evidence.md, CV bullets, interview pitch and evidence outputs.

## Explicit Non-Goals

This project must not become another batch lakehouse, dbt modeling project, dashboard project, fake enterprise system, Kubernetes project, ML project, quant research project or UI-first project.

The gap is real-time data platform engineering.

## Recommended Branch Sequence

1. chore/github-ci-foundation
2. feat/shared-event-contracts
3. feat/prometheus-observability
4. feat/dockerized-runtime
5. docs/gcp-architecture
6. feat/streaming-aggregates
7. feat/reliability-hardening
8. docs/career-evidence-pack

## Definition of Done

The project is portfolio-grade only when it has GitHub repository, clean README, architecture documentation, working Docker Compose runtime, producer/consumer/API running locally, shared event contracts, automated tests, GitHub Actions CI, Prometheus-style metrics, documented GCP target architecture, known limitations, career evidence page, CV bullets and interview pitch.

## Current Next Decision

Current branch is feat/shared-event-contracts.

However, before more feature work, the correct priority is P0 — GitHub and CI foundation.

Reason: without GitHub and CI, improvements remain local and are weak career evidence.
