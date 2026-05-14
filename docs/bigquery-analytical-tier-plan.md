# BigQuery Analytical Tier Plan

**Status: Plan only — no BigQuery resources have been created. No infrastructure has been applied.**

---

## 1. Executive Summary

The latest architecture audit (`docs/b2b-gap-audit-2026-refresh.md`) identifies the absence of an analytical warehouse as the highest-priority remaining structural gap in the Real-Time Data Platform. Every other tier — ingestion (Pub/Sub), stream processing (Cloud Run worker), operational store (Cloud SQL), transformation (dbt), and API serving — is implemented and evidenced. BigQuery is the missing layer.

### Why BigQuery is the next priority

The current platform stores and serves all data through Cloud SQL. Cloud SQL is the correct choice for the operational serving path: it supports transactional queries, row-level access, and is directly consumed by the API. It is not the correct choice for analytical workloads: large scans over historical event data, aggregation across millions of rows, and portfolio-quality SQL analytics that signal GCP fluency.

BigQuery fills this gap. It provides:
- Serverless, columnar analytics over the full event history
- Separation of operational and analytical concerns — a core data engineering architectural principle
- A GCP-native demonstration of the analytical warehouse pattern
- A platform foundation for future Dataflow enrichment and BI tooling

### What this document is

This is a **planning and design document only**. No BigQuery datasets, tables, or IAM bindings have been created. No Terraform has been applied. No data has been moved. This document defines the target architecture, implementation options, phased approach, proposed schema, and acceptance criteria for a future implementation branch.

---

## 2. Current State

### Implemented and evidenced

| Component | Role | State |
|-----------|------|-------|
| Pub/Sub topic `market-events-raw` | Event ingestion | Active |
| Cloud Run worker `rtdp-pubsub-worker` | Stream consumer → Cloud SQL writer | Deployed |
| Cloud SQL `rtdp-postgres` | Operational store, bronze schema | NEVER / STOPPED (cost-controlled) |
| dbt refresh job `rtdp-dbt-refresh-job` | Silver layer transformation | Deployed |
| Cloud Scheduler `rtdp-silver-refresh-scheduler` | Triggers dbt job | PAUSED |
| API service `rtdp-api` | Serves data from Cloud SQL | Deployed |
| Legacy `rtdp-silver-refresh-job` | Rollback path only | Deployed |

### Not implemented

| Component | State |
|-----------|-------|
| BigQuery dataset | **Does not exist** |
| BigQuery tables | **Does not exist** |
| Dataflow pipeline | **Does not exist** |
| Analytical query layer | **Does not exist** |

### Current data flow

```
Pub/Sub (market-events-raw)
    └── Cloud Run Worker (rtdp-pubsub-worker)
            └── Cloud SQL postgres (bronze.market_events)
                    └── dbt (silver layer, scheduled via rtdp-dbt-refresh-job)
                            └── API (rtdp-api)
```

The Cloud SQL instance is kept stopped (`NEVER / STOPPED`) outside of explicit test windows to control cost. The scheduler is kept `PAUSED` to avoid unintended job execution.

---

## 3. Target Architecture

### Design principles

- Cloud SQL remains the **operational/serving store**. The API continues to read from it. dbt continues to transform within it.
- BigQuery becomes the **analytical store**. It holds the full event history in append-only tables and curated analytical aggregates.
- The two stores are complementary, not competing. Operational queries (current price, recent trades) stay in Cloud SQL. Analytical queries (30-day aggregates, volume trends, full history scans) move to BigQuery.
- Initial implementation should be **low-risk and bounded**. Dataflow introduces operational complexity that is not justified until the foundational BigQuery schema is proven.

### Target data flow

```
Pub/Sub (market-events-raw)
    ├── Cloud Run Worker (rtdp-pubsub-worker)
    │       └── Cloud SQL postgres (bronze.market_events)  ← operational store
    │               └── dbt (silver layer)
    │                       └── API (rtdp-api)             ← serving
    │
    └── [Phase 2+] Batch export / Pub/Sub fan-out
              └── BigQuery (rtdp_analytics)                ← analytical store
                      ├── market_events_raw
                      ├── market_event_minute_aggregates
                      └── market_event_daily_aggregates
```

### ASCII architecture diagram

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │                     GCP: europe-west1                               │
 │                                                                     │
 │  ┌──────────────┐     ┌───────────────────┐     ┌───────────────┐  │
 │  │  Pub/Sub     │────▶│  Cloud Run Worker │────▶│  Cloud SQL    │  │
 │  │  market-     │     │  rtdp-pubsub-     │     │  rtdp-postgres│  │
 │  │  events-raw  │     │  worker           │     │  (operational)│  │
 │  └──────────────┘     └───────────────────┘     └───────┬───────┘  │
 │         │                                               │           │
 │         │                                           dbt │ refresh   │
 │         │                                               ▼           │
 │         │                                       ┌───────────────┐  │
 │         │                                       │  rtdp-api     │  │
 │         │                                       │  (serving)    │  │
 │         │                                       └───────────────┘  │
 │         │                                                           │
 │         │  [Phase 2+]                                               │
 │         │  batch export or                                          │
 │         │  fan-out path                                             │
 │         ▼                                                           │
 │  ┌──────────────────────────────────────────────┐                  │
 │  │  BigQuery: rtdp_analytics  (analytical)      │                  │
 │  │  ┌────────────────────────┐                  │                  │
 │  │  │  market_events_raw     │  append-only      │                  │
 │  │  │  (partitioned by day,  │  event history    │                  │
 │  │  │   clustered by symbol) │                  │                  │
 │  │  └────────────────────────┘                  │                  │
 │  │  ┌──────────────────────────────┐            │                  │
 │  │  │  market_event_minute_aggs    │  curated   │                  │
 │  │  └──────────────────────────────┘  tables    │                  │
 │  │  ┌──────────────────────────────┐            │                  │
 │  │  │  market_event_daily_aggs     │            │                  │
 │  │  └──────────────────────────────┘            │                  │
 │  └──────────────────────────────────────────────┘                  │
 └─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Implementation Options

### Option A — Batch export from Cloud SQL `bronze.market_events` to BigQuery

**Description:** A one-time or scheduled batch job reads rows from `bronze.market_events` in Cloud SQL and writes them to BigQuery. Can be implemented as a Cloud Run Job using the BigQuery client library, or via a `bq load` command using a Cloud SQL export to GCS as an intermediate.

**Pros:**
- Uses existing Cloud SQL schema directly — no new producers needed
- Fully bounded and deterministic — can target a specific row range or date range
- Easy to validate: row count in BigQuery must equal row count in export window
- No changes to the ingestion or serving path
- Safe to run as a one-off Cloud Run Job

**Cons:**
- Requires Cloud SQL to be running during export window
- Batch cadence means BigQuery lags behind Cloud SQL by hours or a scheduled interval
- Two-hop path (Cloud SQL → GCS → BigQuery or Cloud SQL → Cloud Run → BigQuery) adds operational steps

**Cost/risk:** Low. Bounded data volume. One-time job. Cloud SQL can be stopped immediately after export.

**B2B/recruiter signal:** Demonstrates batch ELT pattern, BigQuery load jobs, and operational/analytical store separation. Credible for a 6-month portfolio project.

**Recommendation:** **Recommended as Phase 2 initial implementation.** Lowest risk, easiest to evidence, and produces a validated BigQuery dataset.

---

### Option B — Pub/Sub fan-out to a BigQuery sink worker

**Description:** Deploy a second Cloud Run worker that subscribes to `market-events-raw` (via a new Pub/Sub subscription) and writes events directly to BigQuery using the BigQuery Storage Write API or streaming insert API. Runs in parallel with the existing `rtdp-pubsub-worker`.

**Pros:**
- Events land in BigQuery in near-real-time
- Decoupled from Cloud SQL — BigQuery writer does not depend on Cloud SQL being up
- Demonstrates Pub/Sub fan-out pattern (one topic, multiple consumers)
- Stronger B2B signal: event-driven dual-sink architecture

**Cons:**
- BigQuery streaming inserts have a cost per row — not appropriate for unbounded continuous use
- BigQuery Storage Write API requires more careful client implementation
- Adds a second stateful consumer to maintain
- Deduplication becomes non-trivial for retry scenarios
- Does not backfill historical events already in Cloud SQL

**Cost/risk:** Medium. Streaming insert cost per row. Requires dedup strategy. Adds operational surface area.

**B2B/recruiter signal:** High. Demonstrates real-time dual-sink, Pub/Sub fan-out, and BigQuery streaming. Strong signal for Platform Engineer and Data Engineer roles.

**Recommendation:** **Phase 3 or 4 option.** After Phase 2 batch backfill is evidenced, a fan-out worker can be added for incremental/near-real-time appends. Should use Storage Write API in buffered mode, not streaming inserts, to control cost.

---

### Option C — Direct Pub/Sub to BigQuery native subscription

**Description:** Create a BigQuery-type Pub/Sub subscription that writes messages directly to a BigQuery table without any intermediate application code. GCP manages the delivery. Requires a BigQuery table schema that matches the Pub/Sub message schema.

**Pros:**
- No application code required — pure GCP configuration
- Managed delivery and retry by GCP
- Demonstrates knowledge of native GCP integration patterns
- Lowest code surface area of any streaming option

**Cons:**
- Message schema must match BigQuery table schema exactly — Pub/Sub message format constraints apply
- Current `market-events-raw` messages may not be in the expected format (requires verification)
- Less control over transformation logic before landing in BigQuery
- Cannot enrich or filter messages before BigQuery insert
- BigQuery subscription has its own cost model

**Cost/risk:** Low-medium. Configuration-only if schema matches, but schema alignment may require Pub/Sub message format changes which touches the producer.

**B2B/recruiter signal:** Moderate. Shows GCP-native pattern awareness. Less signal than a custom worker because it shows less engineering depth, but valid as a "right tool for the job" design choice.

**Recommendation:** **Evaluate in Phase 3 after schema is established.** If Pub/Sub message format can be aligned to BigQuery table schema without producer changes, this is a strong low-maintenance option for the incremental append path.

---

### Option D — Future Dataflow enrichment path

**Description:** Deploy a Dataflow streaming job (Apache Beam) that consumes from `market-events-raw`, applies windowed aggregations or enrichment, and writes to BigQuery. The canonical GCP streaming architecture.

**Pros:**
- Highest signal for senior Data Engineer roles — Dataflow is a GCP differentiated capability
- Supports windowed aggregations (e.g., 1-minute VWAP) natively in the pipeline
- Scales automatically
- Handles late data and watermarks correctly

**Cons:**
- Dataflow requires Beam pipeline code (Python or Java) — highest development complexity of all options
- Minimum Dataflow cost is non-trivial even for small pipelines
- Introduces a new operational component with its own failure modes
- Premature for Phase 1/2 — BigQuery schema must be established first
- Portfolio risk: a broken Dataflow pipeline is more visible than a missing one

**Cost/risk:** High upfront complexity and cost. Not appropriate until BigQuery baseline is proven.

**B2B/recruiter signal:** Very high — when evidenced. A working Dataflow job is the clearest GCP streaming data engineering signal. But an unevidenced Dataflow plan adds less value than a well-evidenced batch BigQuery path.

**Recommendation:** **Phase 4+ only.** Plan the Dataflow path now but do not implement until the BigQuery dataset, schema, and batch backfill are fully evidenced. Begin with a batch-first approach that Dataflow can replace or extend incrementally.

---

## 5. Recommended Path

### Why not start with Dataflow immediately

Dataflow is the right long-term path but the wrong starting point for three reasons:

1. **No target schema exists yet.** Dataflow writes to BigQuery. Without a validated BigQuery schema, any Dataflow job written now will likely require schema changes mid-implementation, introducing breaking changes.
2. **No baseline for validation.** Without a known-good BigQuery dataset from a bounded batch export, there is no ground truth to validate Dataflow output against. Evidence would be unverifiable.
3. **Cost and complexity risk is front-loaded.** A batch Cloud Run Job that exports 10,000 rows is bounded, cheap, and reversible. A running Dataflow job accrues cost continuously and introduces worker lifecycle complexity before the data model is stable.

The phased approach below derisks implementation by establishing the foundation before adding complexity.

---

### Phase 1 — Terraform scaffold (BigQuery dataset and table definitions)

**Branch:** `feat/bigquery-terraform-scaffold`

**Scope:**
- Add `google_bigquery_dataset` resource for `rtdp_analytics` in `europe-west1`
- Add `google_bigquery_table` resources for `market_events_raw`, `market_event_minute_aggregates`, `market_event_daily_aggregates`
- Add IAM bindings for the Cloud Run service account to write to BigQuery (BigQuery Data Editor role on the dataset)
- `terraform plan` output as evidence — no `terraform apply`
- This branch is infrastructure definition only

**Acceptance criteria:**
- `terraform plan` shows resources to create, zero errors
- No Cloud SQL start, no scheduler resume
- No BigQuery resources exist in GCP yet

---

### Phase 2 — Bounded batch backfill/export

**Branch:** `exec/bigquery-bounded-backfill-evidence`

**Scope:**
- Apply Phase 1 Terraform (creates BigQuery dataset and tables)
- Start Cloud SQL in a bounded test window
- Run a one-off Cloud Run Job that reads from `bronze.market_events` and writes to `rtdp_analytics.market_events_raw` in BigQuery
- Validate: row count in BigQuery matches row count in Cloud SQL export window
- Stop Cloud SQL immediately after validation
- Capture screenshot/CLI evidence of BigQuery row count
- Update `docs/EVIDENCE_INDEX.md`

**Acceptance criteria:**
- BigQuery dataset and tables exist via Terraform
- At least 1,000 events queryable in BigQuery
- Row counts match source for bounded test
- Cloud SQL returned to NEVER / STOPPED post-validation
- No generated artifacts committed

---

### Phase 3 — Incremental append path

**Branch:** `feat/bigquery-incremental-export`

**Scope:**
- Evaluate Option B (Pub/Sub fan-out worker) vs Option C (native BigQuery subscription)
- Implement the lower-risk option for incremental event append
- Validate with a bounded test event burst (e.g., publish 100 events, confirm they appear in BigQuery)
- Scheduler remains PAUSED

**Acceptance criteria:**
- New events published to Pub/Sub appear in `rtdp_analytics.market_events_raw` within a defined SLO
- No unbounded streaming cost — job is stopped after validation

---

### Phase 4 — Optional Pub/Sub fan-out or Dataflow

**Branch:** `feat/bigquery-dataflow-enrichment` (future)

**Scope:**
- If Dataflow is pursued: implement a Beam pipeline that consumes `market-events-raw`, computes 1-minute aggregates, and writes to `market_event_minute_aggregates`
- This phase is explicitly optional and depends on portfolio priority at the time

---

### Phase 5 — Evidence and documentation refresh

**Branch:** `docs/post-bigquery-evidence-refresh`

**Scope:**
- Update `docs/ARCHITECTURE_REVIEW.md` to reflect BigQuery as implemented
- Update `docs/b2b-gap-audit-2026-refresh.md` with BigQuery gap closed
- Update `docs/EVIDENCE_INDEX.md` with new evidence links
- No code or infra changes

---

## 6. Proposed BigQuery Dataset and Tables

### Dataset

| Property | Value |
|----------|-------|
| Dataset ID | `rtdp_analytics` |
| Location | `europe-west1` |
| Default table expiration | None (retention controlled per table) |
| Labels | `env:production`, `tier:analytical` |

---

### Table: `market_events_raw`

Append-only historical event log. One row per event received from Pub/Sub. This is the analytical source of truth for all event history.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| `event_id` | STRING | REQUIRED | Unique event identifier (UUID from producer) |
| `event_timestamp` | TIMESTAMP | REQUIRED | Timestamp of the market event itself |
| `symbol` | STRING | REQUIRED | Instrument symbol (e.g., AAPL, BTCUSD) |
| `event_type` | STRING | REQUIRED | Event type (e.g., trade, quote, tick) |
| `price` | NUMERIC | NULLABLE | Trade/quote price |
| `quantity` | NUMERIC | NULLABLE | Trade quantity / volume |
| `source` | STRING | NULLABLE | Data source identifier |
| `ingest_timestamp` | TIMESTAMP | REQUIRED | Timestamp when the event was received by the Cloud Run worker |
| `bq_load_timestamp` | TIMESTAMP | REQUIRED | Timestamp when the row was written to BigQuery (for audit) |

**Partitioning:** `DAY` on `event_timestamp`. Partitioning by event time is the standard pattern for time-series event tables. It enables partition pruning for date-range queries and controls scan cost.

**Clustering:** `symbol`, `event_type`. Clustering on symbol and event type means analytical queries filtered by instrument or event type scan only relevant data blocks.

**Why NUMERIC for price/quantity:** NUMERIC (with default precision 29, scale 9) is appropriate for financial data. FLOAT64 introduces rounding errors that are unacceptable for price data.

---

### Table: `market_event_minute_aggregates`

Curated 1-minute OHLCV-style aggregates, computed from `market_events_raw`. Populated by dbt or a Dataflow job in later phases.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| `window_start` | TIMESTAMP | REQUIRED | Start of the 1-minute window |
| `window_end` | TIMESTAMP | REQUIRED | End of the 1-minute window |
| `symbol` | STRING | REQUIRED | Instrument symbol |
| `event_type` | STRING | REQUIRED | Aggregated event type |
| `open_price` | NUMERIC | NULLABLE | First price in window |
| `high_price` | NUMERIC | NULLABLE | Max price in window |
| `low_price` | NUMERIC | NULLABLE | Min price in window |
| `close_price` | NUMERIC | NULLABLE | Last price in window |
| `total_quantity` | NUMERIC | NULLABLE | Sum of quantity in window |
| `event_count` | INT64 | REQUIRED | Number of events in window |
| `created_at` | TIMESTAMP | REQUIRED | Row creation timestamp |

**Partitioning:** `DAY` on `window_start`.

**Clustering:** `symbol`, `event_type`.

---

### Table: `market_event_daily_aggregates`

Daily roll-up of event activity per symbol. Suitable for trend analysis and portfolio reporting queries.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| `event_date` | DATE | REQUIRED | Calendar date of the aggregation |
| `symbol` | STRING | REQUIRED | Instrument symbol |
| `event_type` | STRING | REQUIRED | Aggregated event type |
| `open_price` | NUMERIC | NULLABLE | Day open price |
| `high_price` | NUMERIC | NULLABLE | Day high price |
| `low_price` | NUMERIC | NULLABLE | Day low price |
| `close_price` | NUMERIC | NULLABLE | Day close price |
| `total_quantity` | NUMERIC | NULLABLE | Total volume for the day |
| `event_count` | INT64 | REQUIRED | Total events for the day |
| `updated_at` | TIMESTAMP | REQUIRED | Last updated timestamp |

**Partitioning:** `DAY` on `event_date`.

**Clustering:** `symbol`.

---

## 7. Terraform Scope

This section defines what Terraform should create in `feat/bigquery-terraform-scaffold`. **No Terraform is applied in this document branch.**

### Resources to define

```hcl
# Dataset
resource "google_bigquery_dataset" "rtdp_analytics" {
  dataset_id    = "rtdp_analytics"
  friendly_name = "RTDP Analytics"
  description   = "Analytical warehouse for Real-Time Data Platform event history"
  location      = "europe-west1"
  project       = var.project_id

  labels = {
    env  = "production"
    tier = "analytical"
  }
}

# Table: market_events_raw
resource "google_bigquery_table" "market_events_raw" {
  dataset_id = google_bigquery_dataset.rtdp_analytics.dataset_id
  table_id   = "market_events_raw"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  clustering = ["symbol", "event_type"]

  schema = file("${path.module}/schemas/market_events_raw.json")
}

# Table: market_event_minute_aggregates
resource "google_bigquery_table" "market_event_minute_aggregates" {
  dataset_id = google_bigquery_dataset.rtdp_analytics.dataset_id
  table_id   = "market_event_minute_aggregates"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "window_start"
  }

  clustering = ["symbol", "event_type"]

  schema = file("${path.module}/schemas/market_event_minute_aggregates.json")
}

# Table: market_event_daily_aggregates
resource "google_bigquery_table" "market_event_daily_aggregates" {
  dataset_id = google_bigquery_dataset.rtdp_analytics.dataset_id
  table_id   = "market_event_daily_aggregates"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "event_date"
  }

  clustering = ["symbol"]

  schema = file("${path.module}/schemas/market_event_daily_aggregates.json")
}
```

### IAM bindings

The Cloud Run worker service account (used by `rtdp-pubsub-worker` and any future BigQuery export job) requires `roles/bigquery.dataEditor` on the dataset to write rows, and `roles/bigquery.jobUser` at the project level to run load jobs.

```hcl
# Dataset-level write access for the worker service account
resource "google_bigquery_dataset_iam_member" "worker_data_editor" {
  dataset_id = google_bigquery_dataset.rtdp_analytics.dataset_id
  project    = var.project_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.worker_service_account_email}"
}

# Project-level job runner (required for load jobs)
resource "google_project_iam_member" "worker_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.worker_service_account_email}"
}
```

**Note:** The exact service account email must be verified against the deployed `rtdp-pubsub-worker` Cloud Run service in the implementation branch. This document does not apply these bindings.

---

## 8. Data Movement Strategy

### Safest first path: bounded batch export

The recommended first data movement is a **bounded, deterministic, one-time batch export** from Cloud SQL `bronze.market_events` to BigQuery `rtdp_analytics.market_events_raw`.

**Why bounded:**
- A fixed row range (e.g., all events up to a known timestamp) produces a row count that can be exactly validated
- No risk of partial writes or duplicates from retry logic affecting validation
- Cloud SQL can be started, used, and stopped within a single evidence window

**Why deterministic:**
- Using `WHERE ingest_timestamp <= '2026-05-14T00:00:00Z'` (or equivalent) freezes the export scope
- Row count in Cloud SQL query must equal row count in BigQuery post-load
- This is the validation predicate — it is falsifiable

**Proposed export steps (for implementation branch):**

1. Start Cloud SQL (`rtdp-postgres`) — timed window
2. Run `SELECT COUNT(*) FROM bronze.market_events` — capture as baseline
3. Export to GCS as Parquet or CSV using Cloud SQL export or a Cloud Run Job
4. Load from GCS to BigQuery using `bq load` or Terraform `google_bigquery_job`
5. Run `SELECT COUNT(*) FROM rtdp_analytics.market_events_raw` in BigQuery — must match step 2
6. Run a sample analytical query (e.g., `SELECT symbol, COUNT(*) FROM ... GROUP BY symbol`) — capture output as evidence
7. Stop Cloud SQL
8. Capture `gcloud sql instances describe rtdp-postgres --format="value(settings.activationPolicy,state)"` to confirm NEVER / STOPPED

**Backfill approach:**
- Export is idempotent if the target table is truncated before load — acceptable for Phase 2 backfill
- In Phase 3 (incremental append), use `event_id` deduplication or `MERGE` to avoid duplicate rows from overlapping windows

**Validation query example (for evidence):**

```sql
-- Analytical validation: row count by symbol
SELECT
  symbol,
  COUNT(*) AS event_count,
  MIN(event_timestamp) AS earliest_event,
  MAX(event_timestamp) AS latest_event
FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`
GROUP BY symbol
ORDER BY event_count DESC;
```

This query demonstrates:
- Data is present and queryable
- Partitioning is working (BigQuery reports bytes processed)
- Symbol distribution is visible for B2B evidence screenshot

---

## 9. Validation Plan

The following acceptance criteria define a successful BigQuery analytical tier implementation. These are targets for the implementation branch (`exec/bigquery-bounded-backfill-evidence`), not this documentation branch.

| Criterion | Verification method |
|-----------|-------------------|
| BigQuery dataset `rtdp_analytics` exists | `bq ls --project_id=project-42987e01-2123-446b-ac7` |
| Dataset is in `europe-west1` | `bq show project-42987e01-2123-446b-ac7:rtdp_analytics` |
| Table `market_events_raw` exists with correct schema | `bq show project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_raw` |
| Table is partitioned by `event_timestamp` (DAY) | Schema inspection: `timePartitioning.field = event_timestamp` |
| Table is clustered by `symbol`, `event_type` | Schema inspection: `clustering.fields = [symbol, event_type]` |
| At least 1,000 events queryable in BigQuery | `SELECT COUNT(*) FROM rtdp_analytics.market_events_raw` ≥ 1000 |
| Example analytical query returns rows | Validation query from Section 8 returns non-empty result |
| Row counts match source for bounded test | Cloud SQL export count == BigQuery `SELECT COUNT(*)` |
| Terraform plan shows zero diff after apply | `terraform plan` output: "No changes" |
| Cloud SQL returned to NEVER / STOPPED | `gcloud sql instances describe rtdp-postgres --format="value(settings.activationPolicy,state)"` → `NEVER STOPPED` |
| Scheduler remains PAUSED | `gcloud scheduler jobs describe rtdp-silver-refresh-scheduler --format="value(state)"` → `PAUSED` |
| No generated artifacts committed | `git status` shows no untracked generated files |
| No infra/code/workflow/dbt/test files modified | `git diff --name-only` shows only expected files |

---

## 10. Cost and Safety Controls

### BigQuery cost controls

- **Dataset location: `europe-west1`** — consistent with all existing GCP resources. This avoids cross-region egress costs for any future Cloud SQL → BigQuery export within the same region.
- **Bounded test data** — Phase 2 backfill is a one-time export of existing rows. No continuous job. Estimated scan cost for 1,000–10,000 rows is negligible (BigQuery free tier: 1 TB/month queries, 10 GB/month storage).
- **Partitioning and clustering** — required on all tables. Queries in evidence and validation must use partition filters (`WHERE event_timestamp BETWEEN ...`). This makes the cost model predictable and demonstrates cost-aware BigQuery usage.
- **No unbounded streaming inserts in Phase 1/2** — BigQuery streaming inserts are $0.01 per 200 MB. For a portfolio project with bounded test data, streaming cost is acceptable only in Phase 3 validation windows, not as a continuous production job.
- **No continuous jobs initially** — neither a Dataflow job nor a permanent Cloud Run worker writing to BigQuery should run continuously in Phase 1 or Phase 2.

### Cloud SQL cost controls

- Cloud SQL instance `rtdp-postgres` remains `NEVER / STOPPED` outside of explicitly bounded test windows.
- Activation policy is `NEVER`, meaning the instance will not auto-start.
- Every implementation branch that requires Cloud SQL must document a stop step as part of its acceptance criteria.

### Scheduler safety

- Cloud Scheduler `rtdp-silver-refresh-scheduler` remains `PAUSED`.
- The scheduler should only be resumed during explicit dbt validation tests, and must be re-paused immediately after.
- No BigQuery implementation phase requires the scheduler to be active.

### IAM principle of least privilege

- Service accounts for BigQuery write access should be scoped to `roles/bigquery.dataEditor` on the dataset only, not project-wide `roles/bigquery.admin`.
- Read-only analytical access (for evidence queries) can use the project owner account or a dedicated reader service account.

---

## 11. B2B / Recruiter Value

### The current gap

The platform currently demonstrates:
- Real-time event ingestion (Pub/Sub)
- Stream processing (Cloud Run)
- Transactional storage (Cloud SQL)
- Scheduled transformation (dbt)
- API serving

This is a complete operational data platform. It is missing the **analytical warehouse layer** that separates junior from senior GCP data engineering portfolios.

### What BigQuery closes

**Operational vs analytical store separation** is the most fundamental data architecture pattern. A platform that uses only Cloud SQL for all data access is not a data platform — it is a web application backend. Adding BigQuery makes the architectural boundary explicit and evidenced.

**GCP-native analytical pattern** — BigQuery is Google's flagship product in the data engineering space. Fluency with BigQuery (schema design, partitioning, clustering, cost control, SQL analytics) is a required signal for senior Data Engineer and Platform Engineer roles at GCP-native companies.

**SQL analytics over event history** — The ability to write `SELECT symbol, SUM(quantity) FROM market_events_raw WHERE event_timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) GROUP BY symbol` and have it return in seconds over millions of rows is a different class of capability than Cloud SQL can provide.

**Stronger recruiter story:**
- Before: "I built a real-time ingestion pipeline that writes to Cloud SQL"
- After: "I built a real-time event platform with Cloud SQL for operational serving and BigQuery for analytical workloads, with a batch backfill path and a plan for Dataflow enrichment"

The second sentence is a data engineering architecture statement. The first is a backend engineering statement.

**Role alignment:**
- Data Engineer — BigQuery is table stakes
- Analytics Engineer — BigQuery + dbt (dbt on BigQuery is a canonical combination)
- Platform Engineer — BigQuery + Terraform IAM + cost controls
- Staff/Principal — operational/analytical store separation as an architectural decision

---

## 12. Risks and Non-Goals

### Risks

| Risk | Mitigation |
|------|-----------|
| Cloud SQL export window runs longer than planned | Define explicit time box in implementation branch; use `timeout` wrapper on export job |
| BigQuery streaming insert cost exceeds expectation | Phase 3 validation is time-boxed; streaming worker is stopped immediately after evidence |
| Schema mismatch between Cloud SQL types and BigQuery types | Map types explicitly in Phase 2 export job; use NUMERIC for all financial columns |
| Dataflow job complexity underestimated | Dataflow is Phase 4+; do not begin until BigQuery baseline is fully evidenced |
| Pub/Sub message format incompatible with native BigQuery subscription | Evaluate in Phase 3; fall back to Option B (fan-out worker) if schema alignment is not achievable without producer changes |

### Non-goals for this planning document and Phase 1/2

- **No Dataflow in Phase 1 or Phase 2** — Dataflow is explicitly deferred to Phase 4
- **No real-time BI dashboard** — Looker Studio or equivalent is out of scope for this platform stage
- **No multi-region BigQuery** — Single region `europe-west1` only; multi-region adds cost and complexity not justified for a portfolio project
- **No 24/7 production claim** — This platform operates in cost-controlled test windows. BigQuery will be similarly bounded initially.
- **No removal of Cloud SQL** — Cloud SQL remains the operational store. BigQuery is additive, not a replacement.
- **No removal of the dbt scheduled path** — dbt on Cloud SQL continues as the silver layer transformation. Future phases may add dbt on BigQuery as a parallel model set, but that is not in scope here.
- **No stored-function cleanup in this branch** — Any Cloud SQL stored functions are out of scope for this documentation branch.
- **No changes to the Pub/Sub producer or message schema** — The producer (`rtdp-api` or test publisher) is not modified as part of BigQuery tier implementation.

---

## 13. Proposed Branch Sequence

| Order | Branch | Purpose |
|-------|--------|---------|
| 1 | `docs/bigquery-analytical-tier-plan` | This document — plan only, no infra |
| 2 | `feat/bigquery-terraform-scaffold` | Terraform resource definitions, `terraform plan` evidence |
| 3 | `exec/bigquery-bounded-backfill-evidence` | Apply Terraform, run bounded export, capture BigQuery evidence |
| 4 | `feat/bigquery-incremental-export` | Incremental append path (Pub/Sub fan-out or native subscription) |
| 5 | `docs/post-bigquery-evidence-refresh` | Architecture review and evidence index refresh |

**Optional future branches (not committed):**
- `feat/bigquery-dataflow-enrichment` — Dataflow streaming aggregation job
- `feat/bigquery-dbt-models` — dbt models targeting BigQuery dataset

---

## 14. Acceptance Criteria for This Docs Branch

This branch (`docs/bigquery-analytical-tier-plan`) is complete when:

| Criterion | Status |
|-----------|--------|
| Only `docs/bigquery-analytical-tier-plan.md` changed | Required |
| No infra, code, workflow, dbt, or test files modified | Required |
| No Terraform applied | Required — Plan only |
| Cloud SQL `rtdp-postgres` state: NEVER / STOPPED | Required — do not start |
| Scheduler `rtdp-silver-refresh-scheduler` state: PAUSED | Required — do not resume |
| No BigQuery resources created | Required — Plan only |
| No Dataflow resources created | Required — Plan only |
| No generated artifacts committed | Required |
| Document covers all 14 required sections | Required |
| Plan is internally consistent with current platform state | Required |

---

*Last updated: 2026-05-14*
*Branch: docs/bigquery-analytical-tier-plan*
*Status: Plan only — no infrastructure applied*
