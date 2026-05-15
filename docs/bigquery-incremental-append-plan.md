# BigQuery Incremental Append Plan

**Status: Plan only — no implementation has been performed. No infrastructure has been applied. No data has been moved.**

**Branch:** `docs/bigquery-incremental-append-plan`
**Target implementation branch:** `feat/bigquery-incremental-append`
**Last updated:** 2026-05-15

---

## 1. Title and Status

This document defines the design, option analysis, idempotency requirements, validation runbook, and safety constraints for the next implementation branch of the Real-Time Data Platform BigQuery analytical tier: recurring incremental data movement from Cloud SQL to BigQuery.

The bounded backfill (6,104 rows) is accepted evidence. This plan addresses what comes after: a controlled, idempotency-proven incremental append path that demonstrates recurring analytical data movement without duplicating existing rows.

---

## 2. Current Accepted Baseline

| Component | State |
|-----------|-------|
| BigQuery dataset `rtdp_analytics` | Active — created via Terraform |
| BigQuery table `market_events_raw` | 6,104 rows — bounded backfill accepted |
| BigQuery table `market_event_minute_aggregates` | Created via Terraform, empty |
| BigQuery table `market_event_daily_aggregates` | Created via Terraform, empty |
| Cloud SQL `rtdp-postgres` | `NEVER / STOPPED` — cost-controlled |
| Cloud Scheduler `rtdp-silver-refresh-scheduler` | `PAUSED` — not to be resumed |
| Terraform remote backend | Active — GCS backend |
| Terraform plan exit code | `PLAN_EXIT=0` — zero diff after backfill |
| Test suite | 156 passed |
| Ruff | Clean |

### Backfill row distribution (source of truth)

| Symbol | Count |
|--------|-------|
| BTCUSDT | 2,036 |
| ETHUSDT | 2,034 |
| SOLUSDT | 2,033 |
| ADAUSDT | 1 |
| **Total** | **6,104** |

Source/target count match was confirmed: Cloud SQL `bronze.market_events` = 6,104 rows, BigQuery `market_events_raw` = 6,104 rows.

---

## 3. Objective

Implement and evidence a **safe, idempotency-proven incremental append path** from Cloud SQL `bronze.market_events` to BigQuery `rtdp_analytics.market_events_raw`.

The path must:

1. Append only new rows that do not yet exist in BigQuery.
2. Produce a verifiable count: `6104 + N` rows after one controlled batch of N new events.
3. Remain stable under repeated execution: a second run must not change the count.
4. Deduplicate on `event_id` — no duplicate event identifiers in BigQuery after any number of runs.
5. Leave Cloud SQL in `NEVER / STOPPED` state and the Scheduler `PAUSED` on branch completion.

This capability closes the remaining gap between the initial backfill and a production-pattern recurring data movement implementation.

---

## 4. Non-Goals

The following are explicitly out of scope for `feat/bigquery-incremental-append`:

- **No Dataflow** — Dataflow is deferred until the incremental append pattern is proven with a simpler path.
- **No changes to the existing Cloud Run worker `rtdp-pubsub-worker`** — The worker must not be modified. The append path is a separate concern.
- **No changes to dbt models or stored functions** — Transformation logic is unchanged.
- **No resumption of `rtdp-silver-refresh-scheduler`** — The scheduler remains `PAUSED` throughout.
- **No continuous streaming inserts** — The initial incremental path is a scheduled or manually triggered batch job, not a persistent streaming connection.
- **No BI tooling or dashboard** — Looker Studio or equivalent is out of scope.
- **No `dbt/profiles.yml`** — This file must not be committed in any implementation branch.
- **No changes to `apps/silver-refresh-job/`** — The legacy rollback job is not touched.
- **No update to `docs/ARCHITECTURE_REVIEW.md` or `docs/b2b-gap-audit-2026-refresh.md`** — These are updated only after executed evidence exists.

---

## 5. Option Analysis

Five approaches to recurring BigQuery data movement are evaluated below.

---

### Option 1 — Scheduled Incremental Batch Export from Cloud SQL to BigQuery

**Description:**
A dedicated Cloud Run Job reads rows from Cloud SQL `bronze.market_events` that have not yet been appended to BigQuery, based on an export cursor such as the latest `ingest_timestamp` already present in BigQuery. The job exports only the delta, loads it to a BigQuery staging table, and applies a `MERGE` or anti-join insert to the target table using `event_id` as the idempotency key. The job can be triggered manually, by Cloud Scheduler, or by a CI step.

**Operational complexity:** Low. The job is a standalone Python script with a BigQuery client and a Cloud SQL connection. No new GCP services are required beyond what already exists. A Cloud Run Job is the correct container for a batch workload: it runs to completion and stops.

**Cost/control profile:** Lowest cost of all recurring options. Cloud Run Job pricing is per-second of CPU/memory during execution. A delta export of tens or hundreds of rows costs negligible amounts. The job is fully controllable: it can be invoked, paused, or rolled back without affecting any other component.

**Idempotency model:** Explicit. The job computes a cursor using the latest `ingest_timestamp` already present in BigQuery, exports rows beyond that cursor from Cloud SQL, and inserts via `MERGE` on `event_id`. Re-running the job after it has already executed produces zero new inserts because the cursor has caught up and the `MERGE` rejects already-loaded `event_id` values.

**Evidence quality:** High. Row counts before and after each run are directly observable. The idempotency proof requires exactly two sequential runs and two count comparisons, both executable in a bounded evidence window.

**Why selected:** This is the recommended approach. It is the safest path to a proven idempotency demonstration. It requires Cloud SQL to be started only in a bounded window, uses the existing BigQuery table schema without modification, and introduces a new job with a single responsibility. It directly extends the bounded backfill pattern already evidenced.

---

### Option 2 — Pub/Sub Fan-Out to BigQuery Sink Worker

**Description:**
A second Cloud Run service subscribes to a new Pub/Sub pull or push subscription on `market-events-raw`. It receives messages in parallel with the existing `rtdp-pubsub-worker` and writes them to BigQuery via the Storage Write API (buffered mode) or streaming inserts. Events flow to both Cloud SQL and BigQuery in near-real time.

**Operational complexity:** Medium-high. Requires a new Cloud Run service, a new Pub/Sub subscription, and a BigQuery writer implementation. The fan-out pattern introduces a second stateful consumer on the same topic. Any message delivery failure must be handled by both consumers independently, which doubles the retry and dead-letter surface area.

**Cost/control profile:** Higher than batch. Streaming inserts are billed per-row. Storage Write API in buffered mode reduces cost but requires a more complex client implementation. For a production-light platform, continuous streaming cost is difficult to justify when a scheduled batch path provides equivalent analytical value with full cost control.

**Idempotency model:** Non-trivial. Pub/Sub guarantees at-least-once delivery. The BigQuery writer must deduplicate on `event_id` to prevent duplicate rows from message redelivery. Storage Write API in committed mode supports exactly-once semantics but requires explicit stream management.

**Evidence quality:** Good for real-time latency claims, but requires a persistent running service to generate evidence, which conflicts with the cost-controlled operational model of this platform. Streaming inserts appear in BigQuery with a small delay before they are fully queryable, which complicates synchronous validation.

**Why deferred:** This option is appropriate after the incremental batch path is evidenced and the schema is stable. It provides stronger technical hiring relevance for real-time pipeline roles but carries higher cost and operational risk. Recommended as a Phase 4 option.

---

### Option 3 — Native BigQuery Subscription (Pub/Sub BigQuery sink)

**Description:**
A Pub/Sub subscription of type `BIGQUERY` delivers messages directly to a BigQuery table without any application code. GCP manages delivery, retry, and write concurrency. The BigQuery table schema must match the Pub/Sub message schema.

**Operational complexity:** Low for initial setup; high for schema alignment. The `market-events-raw` Pub/Sub messages currently use a JSON payload format aligned to the `bronze.market_events` Cloud SQL schema, not the BigQuery `market_events_raw` schema. Aligning the two schemas requires either modifying the producer or mapping fields in the subscription message transform — which may not be supported without a Dataflow or Cloud Functions intermediary.

**Cost/control profile:** Low operational cost once configured. No application code to maintain. However, the BigQuery native subscription streams messages continuously — this is not a cost-controlled batch pattern.

**Idempotency model:** Weak. Native BigQuery subscriptions do not deduplicate on `event_id` by default. Pub/Sub message redelivery (due to nack or visibility timeout) produces duplicate rows. Deduplication requires a downstream job (e.g., a periodic `DELETE FROM ... WHERE event_id IN (SELECT event_id ...)` or a `MERGE` sweep), which adds operational complexity that defeats the simplicity argument.

**Evidence quality:** Limited for this platform stage. Schema alignment is a prerequisite that has not been validated. Without confirmed message schema compatibility, this option cannot be implemented without touching the producer, which is forbidden for this branch.

**Why deferred:** Schema alignment must be verified before this option is viable. Recommended for evaluation in Phase 4 after the batch incremental path is evidenced and the BigQuery schema is stable.

---

### Option 4 — Worker Streaming Inserts (modify existing `rtdp-pubsub-worker`)

**Description:**
Modify the existing `rtdp-pubsub-worker` to write each event to both Cloud SQL (existing path) and BigQuery (new path) within the same message handler. The worker becomes a dual-sink: it writes to Cloud SQL for the operational path and to BigQuery for the analytical path simultaneously.

**Operational complexity:** Low to add initially; high to maintain. Adding a BigQuery client to the existing worker couples two concerns in a single service. If BigQuery writes fail, the worker must decide whether to nack the message (risking Cloud SQL re-processing) or ack it (accepting BigQuery loss). The error handling logic becomes significantly more complex.

**Cost/control profile:** Higher than batch. Streaming inserts are per-row. The worker processes events continuously when the platform is active. For a production-light platform, this creates ongoing cost without a bounded execution window.

**Idempotency model:** Complex. The worker already implements idempotent Cloud SQL writes. Adding BigQuery writes introduces a second idempotency surface. If the worker acks after a successful Cloud SQL write but before a failed BigQuery write, the event is lost from BigQuery. This dual-ack problem is a known failure mode that requires careful implementation.

**Evidence quality:** Moderate. Mixing concerns in the worker makes it harder to isolate the BigQuery append path as an independently testable component. Validation evidence would need to exercise the full message processing path, which requires Cloud SQL to be running.

**Why deferred:** Modifying the existing worker to add BigQuery writes is forbidden for this branch by the safety constraints. Even setting aside the safety constraint, this option is architecturally weaker than a dedicated append job because it couples two unrelated concerns and complicates error handling. Revisit only if a dual-sink pattern is explicitly required.

---

### Option 5 — Dataflow Streaming Pipeline

**Description:**
A Dataflow streaming job (Apache Beam, Python or Java) reads from `market-events-raw` via a Pub/Sub subscription, applies optional transformations or windowed aggregations, and writes to BigQuery via the Storage Write API. This is the canonical GCP streaming architecture for analytical data movement.

**Operational complexity:** High. Dataflow requires Beam pipeline code, a Dataflow worker pool, and a persistent streaming job. The Dataflow job lifecycle (start, drain, cancel, update) is distinct from Cloud Run Job management. Cost accrues continuously regardless of event volume.

**Cost/control profile:** Highest of all options. Dataflow minimum cost is approximately $0.04/vCPU-hour for streaming workers. For a production-light platform processing bounded test events, Dataflow cost is disproportionate to the analytical value produced. Cost is not controllable on a per-run basis.

**Idempotency model:** Dataflow with Storage Write API in exactly-once mode provides strong idempotency guarantees. However, achieving exactly-once requires careful pipeline design and is not a starting-point capability.

**Evidence quality:** Highest signal for senior Data Engineer roles — when working. A broken or abandoned Dataflow pipeline produces negative evidence. The implementation complexity makes it difficult to evidence in a bounded test window.

**Why deferred:** Dataflow is the right long-term path for windowed aggregations and real-time enrichment. It is the wrong starting point for recurring incremental append. Without a stable BigQuery schema and a validated incremental pattern, Dataflow would require schema changes mid-implementation. Recommended for Phase 4+ after the incremental batch path is evidenced and the analytical schema is proven.

---

## 6. Selected Approach

**Selected: Option 1 — Scheduled Incremental Batch Export from Cloud SQL to BigQuery.**

Rationale:

- The bounded backfill pattern is already evidenced. The incremental batch export is a direct extension: instead of exporting all rows, it exports only rows beyond the current BigQuery export cursor, preferably based on `ingest_timestamp`, while still deduplicating with `event_id`.
- A dedicated Cloud Run Job (new, not the existing worker) maintains single-responsibility design. The existing worker is not modified.
- Idempotency is explicit and provable within a bounded test window. The validation runbook (Section 9) produces falsifiable row count evidence.
- Cloud SQL is started only for the duration of the export query and stopped immediately after — consistent with the established cost-control pattern.
- No continuous running service is required. The job runs to completion and stops. Cost is per-execution, not per-hour.
- The implementation provides a clean foundation for a future scheduled recurring export (via Cloud Scheduler, kept `PAUSED` by default) without requiring any change to the existing worker, API, or dbt path.

---

## 7. Proposed Architecture

### Data flow for incremental append

```
Cloud SQL: bronze.market_events
    (started for bounded export window)
          │
          │  SELECT WHERE ingested_at > cursor
          │  (cursor = latest ingest_timestamp in BigQuery)
          ▼
apps/bigquery-append-job/
    (new Cloud Run Job, dedicated)
          │
          │  Load delta rows to staging table
          ▼
BigQuery: rtdp_analytics.market_events_raw_staging
    (temporary staging table, same schema as target)
          │
          │  MERGE on event_id
          │  (or anti-join INSERT SELECT)
          ▼
BigQuery: rtdp_analytics.market_events_raw
    (target table, 6104 rows + delta appended)
```

### ASCII architecture diagram

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │                     GCP: europe-west1                               │
 │                                                                     │
 │  ┌──────────────┐     ┌───────────────────┐     ┌───────────────┐  │
 │  │  Pub/Sub     │────▶│  Cloud Run Worker │────▶│  Cloud SQL    │  │
 │  │  market-     │     │  rtdp-pubsub-     │     │  rtdp-postgres│  │
 │  │  events-raw  │     │  worker           │     │  (NEVER/STOP) │  │
 │  └──────────────┘     └───────────────────┘     └───────┬───────┘  │
 │                                                          │           │
 │                                                  bounded │ window    │
 │                                                          ▼           │
 │                                               ┌────────────────────┐│
 │                                               │ bigquery-append-job││
 │                                               │ (Cloud Run Job)    ││
 │                                               │ NEW — dedicated    ││
 │                                               └────────┬───────────┘│
 │                                                        │             │
 │                                    ┌───────────────────▼──────────┐ │
 │                                    │  BigQuery: rtdp_analytics    │ │
 │                                    │  ┌──────────────────────────┐│ │
 │                                    │  │ market_events_raw_staging││ │
 │                                    │  │ (staging, ephemeral)     ││ │
 │                                    │  └────────────┬─────────────┘│ │
 │                                    │               │ MERGE on      │ │
 │                                    │               │ event_id      │ │
 │                                    │               ▼               │ │
 │                                    │  ┌──────────────────────────┐│ │
 │                                    │  │ market_events_raw        ││ │
 │                                    │  │ 6104 rows + delta        ││ │
 │                                    │  └──────────────────────────┘│ │
 │                                    └──────────────────────────────┘ │
 └─────────────────────────────────────────────────────────────────────┘
```

### Export cursor strategy

The append job determines what to export from Cloud SQL using a time-based cursor, preferably `ingested_at` from `bronze.market_events`, with `event_id` used only as the idempotency key. `event_id` must not be treated as an ordered export cursor unless its generation format is explicitly proven to be monotonic.

Recommended delta predicate:

```
delta = cloud_sql.bronze.market_events
WHERE ingested_at > bq_max_ingest_timestamp
   OR (ingested_at = bq_max_ingest_timestamp AND event_id NOT IN already_loaded_event_ids_for_that_timestamp)
```

The merge into BigQuery must still deduplicate on `event_id`. This separates the export cursor (`ingested_at`) from the idempotency key (`event_id`) and avoids relying on lexical ordering of event identifiers.

### Staging table approach

The delta rows are loaded to a staging table (`market_events_raw_staging`) in the same BigQuery dataset before being merged into the target. This separates the load step from the merge step, making each independently observable and rollback-safe:

1. Load delta to staging → verify staging row count == delta count from Cloud SQL.
2. Merge staging into target → verify target count increased by exactly the delta count.
3. Drop or truncate staging.

---

## 8. Idempotency Design

### Dedupe key

`event_id` is the primary idempotency key. It is a UUID generated by the event producer and stored in `bronze.market_events.event_id` and `rtdp_analytics.market_events_raw.event_id`. No two events with the same `event_id` must exist in BigQuery after any number of append job executions.

### MERGE approach (recommended)

```sql
MERGE `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw` AS target
USING `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw_staging` AS source
ON target.event_id = source.event_id
WHEN NOT MATCHED BY TARGET THEN
  INSERT (event_id, event_timestamp, symbol, event_type, price, quantity,
          source, ingest_timestamp, bq_load_timestamp)
  VALUES (source.event_id, source.event_timestamp, source.symbol, source.event_type,
          source.price, source.quantity, source.source, source.ingest_timestamp,
          source.bq_load_timestamp);
```

Re-running this MERGE when all staging rows already exist in the target produces zero inserts. This is the idempotency guarantee.

### Anti-join insert approach (alternative)

```sql
INSERT INTO `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`
SELECT s.*
FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw_staging` s
WHERE NOT EXISTS (
  SELECT 1
  FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw` t
  WHERE t.event_id = s.event_id
);
```

The anti-join insert is simpler than MERGE for append-only targets and produces equivalent idempotency guarantees. It does not require a `WHEN MATCHED` clause because the target is append-only — no updates occur.

### Recommendation

Use `MERGE` for the initial implementation. The explicit `WHEN NOT MATCHED` clause documents intent clearly. The `MERGE` pattern is also directly extensible if a future phase requires update semantics (e.g., correcting a field on an existing event).

### Pre-filtered export approach (not recommended)

An alternative is to query Cloud SQL with `WHERE event_id NOT IN (SELECT event_id FROM BigQuery)` — exporting only rows that do not yet exist in BigQuery. This avoids the staging table entirely. This approach is rejected because:

- It requires a cross-system query at export time, which is slow and fragile.
- It couples the export step to the BigQuery state, making re-runs non-deterministic if the BigQuery state changes between query and load.
- The staging + MERGE pattern provides a clean audit trail: staging row count and merge insert count are independently verifiable.

### Duplicate verification query

After each append run, the following query must return zero rows:

```sql
SELECT event_id, COUNT(*) AS cnt
FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`
GROUP BY event_id
HAVING cnt > 1;
```

Zero rows returned = no duplicate `event_id` values in BigQuery. This query is required as part of the evidence runbook.

---

## 9. Validation Runbook for the Future Execution Branch

This runbook defines the exact sequence of steps required to evidence the incremental append implementation. It is written for execution in `feat/bigquery-incremental-append`. **No steps in this runbook should be executed on the current documentation branch.**

### Prerequisites

- Cloud SQL `rtdp-postgres` is in `NEVER / STOPPED` state before the test begins.
- BigQuery `market_events_raw` contains exactly 6,104 rows (baseline).
- `apps/bigquery-append-job/` is implemented and passing tests.
- Terraform plan exits with code 0 (no unintended infra changes).

### Step 1 — Confirm baseline BigQuery count

```bash
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) AS row_count FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`'
```

Expected: `row_count = 6104`. This is the baseline. Capture output as evidence.

### Step 2 — Start Cloud SQL in a bounded window

```bash
gcloud sql instances patch rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --activation-policy=ALWAYS
```

Wait for instance to reach `RUNNABLE` state before proceeding.

### Step 3 — Insert N controlled new events into Cloud SQL

Insert a small, known batch of N new events into `bronze.market_events`. The value of N must be recorded before insertion. Recommended: N = 10 to 100 events with predictable `event_id` values and a distinct `symbol` or `event_type` for easy verification.

```sql
-- Example: insert 10 new events with sequential UUIDs
-- Record exact N before execution
-- Record event_id values for later verification
```

After insertion, confirm Cloud SQL count:

```sql
SELECT COUNT(*) FROM bronze.market_events;
```

Expected: `6104 + N`. Capture output as evidence.

### Step 4 — Run the incremental append job (first run)

```bash
gcloud run jobs execute bigquery-append-job \
  --project=project-42987e01-2123-446b-ac7 \
  --region=europe-west1 \
  --wait
```

Capture job execution log output as evidence, including:
- Cursor read from BigQuery before export.
- Row count exported from Cloud SQL.
- Staging table row count after load.
- MERGE or insert count.
- Final BigQuery count.

### Step 5 — Confirm BigQuery count after first run

```bash
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) AS row_count FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`'
```

Expected: `row_count = 6104 + N`. Capture output as evidence.

### Step 6 — Run the incremental append job (second run — idempotency check)

```bash
gcloud run jobs execute bigquery-append-job \
  --project=project-42987e01-2123-446b-ac7 \
  --region=europe-west1 \
  --wait
```

The second run must produce zero new inserts. Capture job log showing insert count = 0.

### Step 7 — Confirm BigQuery count is unchanged after second run

```bash
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) AS row_count FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`'
```

Expected: `row_count = 6104 + N` (unchanged from Step 5). Capture output as evidence.

### Step 8 — Run analytical query to confirm new rows are queryable

```sql
SELECT
  symbol,
  event_type,
  COUNT(*) AS event_count,
  MIN(event_timestamp) AS earliest,
  MAX(event_timestamp) AS latest
FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`
GROUP BY symbol, event_type
ORDER BY event_count DESC;
```

Confirm new rows appear in the expected `symbol` / `event_type` bucket. Capture output as evidence.

### Step 9 — Verify no duplicate event_id values

```sql
SELECT event_id, COUNT(*) AS cnt
FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`
GROUP BY event_id
HAVING cnt > 1;
```

Expected: zero rows returned. Capture output as evidence.

### Step 10 — Stop Cloud SQL

```bash
gcloud sql instances patch rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --activation-policy=NEVER
```

Confirm state:

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER STOPPED`. Capture output as evidence.

### Step 11 — Confirm Scheduler remains PAUSED

```bash
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --project=project-42987e01-2123-446b-ac7 \
  --location=europe-west1 \
  --format="value(state,httpTarget.uri)"
```

Expected: `PAUSED`. Capture output as evidence.

### Step 12 — Confirm Terraform plan is clean

```bash
cd infra/terraform/gcp && terraform plan -detailed-exitcode
```

Expected exit code: `0` (no changes). Capture output as evidence.

### Step 13 — Confirm test suite passes

```bash
pytest --tb=short -q
```

Expected: 156+ passed, 0 failed. Capture output as evidence.

---

## 10. Safety Constraints

The following constraints apply to the current documentation branch and to `feat/bigquery-incremental-append`. They are not negotiable and must be verified at branch completion.

| Constraint | Rationale |
|------------|-----------|
| Do NOT modify `apps/silver-refresh-job/` | Legacy rollback path — must remain unmodified |
| Do NOT commit `dbt/profiles.yml` | File is gitignored and must remain absent |
| Do NOT commit dbt target artifacts | Generated files, not source |
| Do NOT resume `rtdp-silver-refresh-scheduler` | Scheduler must remain `PAUSED` throughout |
| Do NOT start Cloud SQL outside a bounded test window | Cost control — instance must be stopped after every test step |
| Do NOT apply Terraform changes to unrelated resources | Only BigQuery append job infrastructure is in scope |
| Do NOT modify the existing worker, API, or dbt runtime | New job is a separate concern |
| Do NOT update `docs/ARCHITECTURE_REVIEW.md` on this branch | Update only after evidence exists |
| Do NOT update `docs/b2b-gap-audit-2026-refresh.md` on this branch | Update only after evidence exists |
| Do NOT create evidence documents before execution | Evidence documents describe real executed steps only |
| Do NOT expose or inspect secrets | Secret values must not appear in logs, evidence, or commits |

---

## 11. Expected Files for Implementation Branch

### Files likely to be created

| Path | Purpose |
|------|---------|
| `apps/bigquery-append-job/` | New Cloud Run Job source: cursor read, delta export, staging load, MERGE |
| `apps/bigquery-append-job/main.py` | Job entrypoint |
| `apps/bigquery-append-job/requirements.txt` | Dependencies (google-cloud-bigquery, psycopg2, etc.) |
| `apps/bigquery-append-job/Dockerfile` | Container definition |
| `tests/test_bigquery_append_job.py` | Unit/integration tests for the append job |
| `docs/bigquery-incremental-append-evidence.md` | Executed evidence for the incremental append validation runbook |

### Files likely to be modified

| Path | Purpose |
|------|---------|
| `infra/terraform/gcp/cloud_run_jobs.tf` | Add Cloud Run Job resource for `bigquery-append-job` |
| `infra/terraform/gcp/scheduler.tf` | Optionally add a new scheduler entry for the append job, kept `PAUSED` by default |
| `docs/EVIDENCE_INDEX.md` | Add new evidence entry for incremental append |

### Files forbidden in this branch

| Path | Reason |
|------|--------|
| `apps/silver-refresh-job/` | Legacy rollback — do not touch |
| `dbt/profiles.yml` | Must remain absent |
| `dbt/target/` | Generated dbt artifacts |
| Any stored function definition | Out of scope unless explicitly required by the append job |
| Unrelated Terraform resources | Only append job infrastructure is in scope |
| `docs/ARCHITECTURE_REVIEW.md` | Requires evidence before update |
| `docs/b2b-gap-audit-2026-refresh.md` | Requires evidence before update |

---

## 12. Acceptance Criteria

All criteria below must be met before `feat/bigquery-incremental-append` is considered complete.

| Criterion | Verification |
|-----------|-------------|
| BigQuery `market_events_raw` count = 6104 before test | `SELECT COUNT(*)` = 6104 |
| N new events inserted into Cloud SQL | Cloud SQL `SELECT COUNT(*)` = 6104 + N |
| First append run: BigQuery count = 6104 + N | `SELECT COUNT(*)` after first run = 6104 + N |
| Second append run: BigQuery count unchanged | `SELECT COUNT(*)` after second run = 6104 + N |
| No duplicate `event_id` in BigQuery | Duplicate check query returns zero rows |
| New rows are queryable by symbol/event_type | Analytical GROUP BY query confirms new rows |
| Cloud SQL returned to `NEVER / STOPPED` | `gcloud sql instances describe` → `NEVER STOPPED` |
| Scheduler remains `PAUSED` | `gcloud scheduler jobs describe` → `PAUSED` |
| Terraform plan exits with code 0 | `terraform plan -detailed-exitcode` → exit 0 |
| Test suite passes | `pytest` → 0 failed |
| No forbidden files committed | `git diff --name-only` shows only expected files |
| `dbt/profiles.yml` absent | `git status` shows no profiles.yml |
| Evidence document written | `docs/bigquery-incremental-append-evidence.md` exists and contains executed output |

---

## 13. Stop Conditions

Execution of `feat/bigquery-incremental-append` must be paused and the branch must be assessed if any of the following conditions occur:

| Condition | Required action |
|-----------|----------------|
| Cloud SQL fails to reach `RUNNABLE` within 5 minutes of patch | Stop the test window; do not proceed; diagnose before retry |
| Cloud SQL cannot be returned to `NEVER / STOPPED` after the test window | Immediate priority: stop the instance manually via `gcloud sql instances patch --activation-policy=NEVER`; do not merge until confirmed |
| BigQuery `market_events_raw` count after first run does not equal 6104 + N | Do not run second step; investigate staging table and MERGE output; do not merge |
| Duplicate `event_id` values detected | Do not continue; investigate dedupe logic; delete duplicates before merging |
| Terraform plan shows unexpected resource changes | Do not apply; investigate Terraform state; do not merge |
| Test suite introduces new failures | Do not merge until all failures are resolved or explicitly accepted as pre-existing |
| The append job modifies any file in `apps/silver-refresh-job/`, `dbt/`, or the worker | Revert immediately; do not merge |

---

## 14. Rollback / Cleanup Plan

### If BigQuery rows were incorrectly inserted (duplicates or wrong data)

1. Identify the run that produced bad data from job logs.
2. Delete the affected rows using a targeted `DELETE` with the known `event_id` values from the bad run.
3. Verify the duplicate check query returns zero rows.
4. Re-run the append job with corrected logic.

```sql
-- Example: delete rows from a bad run using known event_id values
DELETE FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`
WHERE event_id IN ('uuid-1', 'uuid-2', ...);
```

### If Cloud SQL was left running

```bash
gcloud sql instances patch rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --activation-policy=NEVER
```

Verify:

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER STOPPED`.

### If the staging table was not cleaned up

```bash
bq rm -f project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_raw_staging
```

### If the branch introduced Terraform drift

Investigate with `terraform plan`. If only the new Cloud Run Job resource is in drift, this is expected and should be applied. If any other resource shows changes, investigate before applying.

### If the branch must be abandoned before merge

1. Stop Cloud SQL if running.
2. Confirm Scheduler is `PAUSED`.
3. Do not delete the BigQuery target table — the 6,104 baseline rows must be preserved.
4. Clean up the staging table if it exists.
5. Discard or archive the branch. The baseline state is fully recoverable.

---

## 15. Evidence Document Expected Later

When `feat/bigquery-incremental-append` is executed and validated, the following evidence document must be created:

**`docs/bigquery-incremental-append-evidence.md`**

It must contain:

- Timestamp and branch of execution.
- BigQuery `COUNT(*)` before test: 6,104.
- Cloud SQL count after N-event insert: 6,104 + N.
- BigQuery `COUNT(*)` after first append run: 6,104 + N.
- BigQuery `COUNT(*)` after second append run: 6,104 + N (unchanged — idempotency confirmed).
- Output of the duplicate `event_id` check query: zero rows.
- Output of the analytical GROUP BY query confirming new rows are queryable.
- `gcloud sql instances describe` output: `NEVER STOPPED`.
- `gcloud scheduler jobs describe` output: `PAUSED`.
- `terraform plan` exit code: 0.
- `pytest` output: passed count, 0 failed.

After this evidence document exists, the following documents may be updated:

- `docs/EVIDENCE_INDEX.md` — add the incremental append evidence entry.
- `docs/ARCHITECTURE_REVIEW.md` — reflect the incremental append path as implemented.
- `docs/b2b-gap-audit-2026-refresh.md` — update the remaining gap assessment.

---

*Branch: docs/bigquery-incremental-append-plan*
*Status: Plan only — no infrastructure applied, no data moved, no execution performed*
