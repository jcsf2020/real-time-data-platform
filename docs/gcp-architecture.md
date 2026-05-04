# GCP Target Architecture

## Purpose

This document maps the local Real-Time Data Platform to a production-oriented Google Cloud Platform target architecture.

The current implementation is local and Docker-based. The GCP architecture described here is a target design, not a claim that the system is already deployed on GCP.

## Current Local Runtime

```text
Producer
  -> Redpanda / Kafka topic: market.events.raw
      -> Consumer
          -> Postgres: bronze.market_events
          -> Postgres: observability.pipeline_metrics
              -> FastAPI
                  -> /health
                  -> /readiness
                  -> /version
                  -> /events
                  -> /metrics
                  -> /metrics-prometheus
```

Implemented local components:

- Python producer
- Redpanda Kafka-compatible broker
- Python consumer
- Shared versioned MarketEvent contract
- Postgres operational storage
- FastAPI serving layer
- Prometheus-style metrics endpoint
- Dockerized runtime
- GitHub Actions CI

## GCP Service Mapping

| Local Component | GCP Target | Purpose |
|---|---|---|
| Redpanda / Kafka | Pub/Sub | Managed event ingestion and fan-out |
| Python producer | Cloud Run job / external source | Event publishing |
| Python consumer | Cloud Run worker or Dataflow | Event processing |
| Postgres container | Cloud SQL for PostgreSQL | Implemented managed operational storage |
| FastAPI container | Cloud Run service | HTTP serving layer |
| /metrics-prometheus | Cloud Monitoring / Managed Prometheus | Operational metrics |
| Analytical extracts | BigQuery | Analytical querying |
| Docker Compose | Cloud Run + managed services | Production runtime |
| GitHub Actions | GitHub Actions + GCP deployment pipeline | CI/CD |

## Target GCP Flow

```text
Event source
  -> Pub/Sub topic: market-events-raw
      -> Cloud Run worker or Dataflow pipeline
          -> Cloud SQL PostgreSQL for operational storage
          -> BigQuery for analytical reporting
          -> Cloud Monitoring for metrics
              -> Cloud Run API for operational access
```

## Pub/Sub Role

Pub/Sub replaces the local Kafka-compatible broker in the cloud target.

Local:

```text
Producer -> Redpanda/Kafka -> Consumer
```

GCP target:

```text
Producer -> Pub/Sub topic -> Subscriber / Cloud Run worker / Dataflow
```

Pub/Sub provides managed event ingestion, durable messaging, subscriber fan-out, retry behavior, and integration with GCP services.

## Cloud Run Role

Cloud Run is the target runtime for containerized services.

The current FastAPI service is already containerized and exposes production-style endpoints:

- /health
- /readiness
- /version
- /events
- /metrics
- /metrics-prometheus

In GCP, this API can run as a Cloud Run service. Worker components can also run on Cloud Run when processing is stateless or horizontally scalable.

## Cloud SQL Role

Cloud SQL for PostgreSQL maps to the current local Postgres container.

Current local operational tables:

- bronze.market_events
- observability.pipeline_metrics

Target production role:

- durable operational store
- validated event persistence
- idempotent writes
- API-serving queries
- audit-friendly storage

## BigQuery Role

BigQuery is the target analytical warehouse.

Cloud SQL is suitable for operational access. BigQuery is better suited for analytical queries over larger event history.

Possible BigQuery use cases:

- event volume by symbol
- time-windowed trade metrics
- historical lag analysis
- daily pipeline throughput
- analytical reporting over enriched stream outputs

## Dataflow / Apache Beam Role

Dataflow is the target managed stream processing layer for advanced streaming use cases.

Current consumer logic is simple and Python-based. Future Dataflow usage would be appropriate for:

- windowed aggregations
- late-event handling
- stateful processing
- event-time processing
- high-volume streaming transformations

Example future aggregates:

- events per symbol per minute
- average price per symbol per window
- traded volume per symbol per window
- late event count
- processing lag by window

## Observability Target

Current implementation:

```text
Consumer -> observability.pipeline_metrics -> FastAPI /metrics-prometheus
```

Target GCP implementation:

```text
Cloud Run / Dataflow metrics
  -> Cloud Monitoring / Managed Prometheus
      -> dashboards and alerts
```

Current metrics already exposed:

- events_processed_total
- latest_processed_offset
- processing_lag_seconds
- consumer_errors_total

## Production Principles

The GCP target architecture must preserve the current production principles:

- shared event contracts
- schema versioning
- idempotent persistence
- clear health and readiness endpoints
- observable processing metrics
- containerized runtime
- CI validation before merge
- no secrets committed
- no hidden manual steps
- no cloud claims without implementation or explicit target documentation

## Current Implementation vs Target Architecture

| Capability | Current Status |
|---|---|
| Local producer | Implemented |
| Kafka-compatible ingestion | Implemented with Redpanda |
| Consumer persistence | Implemented |
| Idempotent writes | Implemented |
| Shared event contract | Implemented |
| API serving layer | Implemented |
| Health/readiness/version endpoints | Implemented |
| Prometheus-style metrics endpoint | Implemented |
| Dockerized full runtime | Implemented |
| GitHub Actions CI | Implemented |
| Pub/Sub publisher (local MVP) | Implemented — publishes MarketEvent to topic; cloud-side consumer not yet deployed |
| Cloud Run deployment | Implemented |
| Cloud SQL deployment | Implemented (instance stopped; no cloud ingestion yet) |
| BigQuery analytical layer | Target architecture |
| Dataflow streaming enrichment | Target architecture |
| Cloud Monitoring dashboards | Target architecture |

## Recruiter-Relevant Summary

This project demonstrates a real-time data engineering platform with event-driven ingestion, versioned data contracts, idempotent processing, operational observability, containerized runtime, and a clear GCP production mapping.

It complements batch, lakehouse, and data modeling experience by showing streaming platform engineering and cloud-native architecture thinking.
