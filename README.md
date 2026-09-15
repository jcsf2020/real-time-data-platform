# Real-Time Data Platform

[![CI](https://github.com/jcsf2020/real-time-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/jcsf2020/real-time-data-platform/actions/workflows/ci.yml)

Evidence-first GCP Data Engineering portfolio platform demonstrating event ingestion, cloud processing, analytics, infrastructure-as-code, data quality and observability.

This is **bounded, reproducible portfolio evidence**. It is not presented as a continuously running customer production system.

## Recruiter Quick Scan

| Question | Answer |
|---|---|
| What is this? | A GCP Data Engineering proof asset with verifiable run IDs and committed evidence |
| Core stack | Python, Pub/Sub, Cloud Run, Cloud SQL, BigQuery, dbt, Terraform, FastAPI, GitHub Actions, Cloud Monitoring |
| Best-fit roles | Data Engineer, Data Platform Engineer, Analytics Engineer with platform exposure, Cloud Data Engineer, DataOps / Platform Engineer |
| Where to start | [Recruiter summary](docs/recruiter-facing-platform-summary.md) -> [Evidence index](docs/EVIDENCE_INDEX.md) -> [50k load-test evidence](docs/load-test-50000-cloud-evidence.md) |
| What is not claimed | Sustained production throughput, always-on streaming, exactly-once production semantics, multi-region customer deployment |

## Evidence Highlights

- **384 pytest tests** passing; ruff clean
- **dbt compile/run/test in CI** with 22 dbt tests against an ephemeral PostgreSQL/pgvector service
- **Terraform Plan CI** using Workload Identity / OIDC; no stored service-account key in CI
- **50,000-event bounded GCP run**: 50,000 events published, 0 worker errors, 0 duplicate `event_id` rows
- **BigQuery analytical tier** with incremental append and quality-check workflow
- **Cloud Monitoring / alerting** with controlled quality-failure incident and email-notification evidence
- **Pub/Sub DLQ evidence** with bounded malformed-message testing and alert delivery
- **60+ indexed evidence documents** linking claims to run IDs, commit SHAs and resource names
- **Cost-control posture**: Cloud SQL returned to STOPPED / NEVER and schedulers PAUSED after bounded proofs

## Latest Validated Milestone

**50,000-event bounded GCP cloud load test — 2026-05-20**

Validated path: `Pub/Sub -> Cloud Run worker -> Cloud SQL`

| Metric | Value |
|---|---:|
| Events published | 50,000 |
| Unique Pub/Sub message IDs | 50,000 |
| Publish errors | 0 |
| Worker OK logs | 50,000 |
| Worker errors | 0 |
| Cloud SQL rows | 50,000 |
| Duplicate `event_id` count | 0 |
| Terraform plan | `PLAN_EXIT=0` |
| Cloud SQL final state | STOPPED / NEVER |
| Schedulers final state | PAUSED |

Cloud Monitoring showed 50,002 processed due to DELTA window alignment; structured worker logs and Cloud SQL rows are authoritative for the exact 50,000-event proof.

Evidence: [docs/load-test-50000-cloud-evidence.md](docs/load-test-50000-cloud-evidence.md)

## What the Platform Demonstrates

- Pub/Sub ingestion with dead-letter policy and retry handling
- Python workers running on Cloud Run
- idempotent Cloud SQL / PostgreSQL writes using `ON CONFLICT`
- BigQuery analytical tier with partitioning and incremental append
- dbt silver/gold transformations and automated tests
- Terraform-managed GCP resources with GCS remote state
- Workload Identity Federation for keyless CI authentication
- Cloud Logging / Cloud Monitoring metrics, dashboards and alert policies
- BigQuery data-quality workflow with pass/fail evidence
- bounded alerting / incident-notification proof
- cost-safe operating discipline after test execution

## Evidence-First Positioning

This project is presented as **bounded, evidence-backed Data Engineering / Platform Engineering work**.

Professional Data Engineering positioning starts in **2023**. The project should be evaluated on the technical evidence and scope shown here rather than on an inflated title or backdated tenure.

### Safe interview positioning

> I validated a GCP event-processing path at 50,000 events with Pub/Sub, Cloud Run, Cloud SQL, structured logs, Cloud Monitoring, Terraform zero-diff checks and indexed evidence. I present it as bounded platform work and do not claim sustained customer-production throughput or always-on streaming.

## Explicit Non-Claims

- no sustained customer-production throughput benchmark
- no 24/7 always-on customer streaming workload
- no end-to-end exactly-once production guarantee
- no enterprise-scale customer volume claim
- no multi-region customer production deployment
- no security/compliance certification claim

## Evidence Navigation

- [Recruiter-facing platform summary](docs/recruiter-facing-platform-summary.md)
- [Evidence index](docs/EVIDENCE_INDEX.md)
- [50k load-test evidence](docs/load-test-50000-cloud-evidence.md)
- [GCP architecture](docs/gcp-architecture.md)
- [Cost / performance summary](docs/cost-performance-summary.md)
- [BigQuery quality incident notification proof](docs/bigquery-quality-incident-notification-delivery-proof.md)
- [dbt Cloud SQL incremental execution proof](docs/dbt-cloud-sql-incremental-execution-proof.md)

## Tech Stack

| Layer | Technology |
|---|---|
| Messaging | Pub/Sub; Redpanda/Kafka-compatible local path |
| Processing | Python, Cloud Run |
| Storage | Cloud SQL PostgreSQL, BigQuery |
| Transformation | dbt, SQL |
| Infrastructure | Terraform, GCS remote state |
| Serving | FastAPI |
| Quality | pytest, dbt tests, BigQuery quality workflow |
| CI | GitHub Actions, Workload Identity |
| Observability | Cloud Logging, Cloud Monitoring |

## Public Career / B2B Links

- GitHub profile: https://github.com/jcsf2020
- Portfolio: https://joao-fonseca-portfolio.vercel.app/
- LinkedIn: https://www.linkedin.com/in/joao-fonseca-data-engineer/
- Career Evidence: https://drive.google.com/drive/folders/1VaMTQ6gf-d_Zf_t8Oi_dhClvbCWBT1HE
- Famous Satellite: https://famoussatellite.com

For recruiter-led Data Engineering opportunities, the route is João-first. For B2B/end-client engagements, the commercial and contractual context is **Famous Satellite**.

## Contact

joao.fonseca@famoussatellite.com
