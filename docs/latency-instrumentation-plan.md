# Latency Instrumentation Plan

## Status

| Field | State |
|---|---|
| Document type | PLAN ONLY |
| New GCP workload execution | No |
| New events published | No |
| Cloud SQL started | No |
| Terraform apply executed | No |
| p50/p95/p99 latency validated | NOT YET PROVEN |

This document defines the instrumentation required to measure and prove event-level latency
distribution across the Pub/Sub -> Cloud Run worker -> Cloud SQL pipeline. It does not
execute any workload, publish any events, or modify any schema.

---

## Current Gap

The existing evidence proves:

- Correctness: zero worker errors during the 50,000-event bounded cloud load test.
- Idempotency: duplicate event_id count = 0 across all load tests.
- Observability: Cloud Monitoring logs-based metrics confirmed with datapoints.
- Bounded load: 50,000 events processed end-to-end with all acceptance criteria met.
- DLQ behaviour: malformed-message routing to DLQ confirmed (with observed multi-entry caveat).

What the evidence does **not** yet prove:

- Event-level latency distribution across pipeline stages.
- p50, p95, or p99 end-to-end latency.
- Pub/Sub delivery latency or Cloud Run processing latency measured per event.

This plan defines the instrumentation required to close that gap in a future execution branch.

---

## Timestamp Model

To measure per-event latency, each event must carry timestamps from production through
persistence. The following timestamps define the instrumentation model:

| Timestamp | Description |
|---|---|
| `producer_created_at` | When the producer process generated the event payload |
| `pubsub_publish_ack_at` | When the Pub/Sub client received the publish acknowledgement |
| `worker_received_at` | When the Cloud Run worker received the push delivery |
| `worker_decoded_at` | When the worker completed JSON decoding of the message |
| `worker_validated_at` | When the worker completed schema and business-rule validation |
| `db_insert_started_at` | When the worker began the database insert operation |
| `db_insert_completed_at` | When the database insert operation returned successfully |
| `worker_completed_at` | When the worker completed all processing and returned the response |

All timestamps are UTC ISO 8601 with microsecond precision.

---

## Derived Metrics

The following latency metrics are derived from the timestamp pairs above:

| Metric | Formula | What it measures |
|---|---|---|
| `publish_ack_latency_ms` | `pubsub_publish_ack_at - producer_created_at` | Time for Pub/Sub to acknowledge the publish |
| `delivery_latency_ms` | `worker_received_at - pubsub_publish_ack_at` | Time from ack to push delivery at the worker |
| `validation_latency_ms` | `worker_validated_at - worker_received_at` | Time for the worker to decode and validate the message |
| `db_write_latency_ms` | `db_insert_completed_at - db_insert_started_at` | Time for the database insert to complete |
| `worker_processing_latency_ms` | `worker_completed_at - worker_received_at` | Total time the worker spent on the event |
| `end_to_end_latency_ms` | `worker_completed_at - producer_created_at` | Total elapsed time from event creation to persistence |

**Primary metric:** `end_to_end_latency_ms`

This is the primary evidence metric. It spans the full pipeline from producer to confirmed
database write and is the most meaningful signal for production-readiness assessment.

---

## Storage Options

### Option A: Timestamps in Cloud SQL Bronze Rows

Add timestamp columns to `bronze.market_events`:

```sql
ALTER TABLE bronze.market_events ADD COLUMN producer_created_at      TIMESTAMPTZ;
ALTER TABLE bronze.market_events ADD COLUMN pubsub_publish_ack_at    TIMESTAMPTZ;
ALTER TABLE bronze.market_events ADD COLUMN worker_received_at        TIMESTAMPTZ;
ALTER TABLE bronze.market_events ADD COLUMN worker_decoded_at         TIMESTAMPTZ;
ALTER TABLE bronze.market_events ADD COLUMN worker_validated_at       TIMESTAMPTZ;
ALTER TABLE bronze.market_events ADD COLUMN db_insert_started_at      TIMESTAMPTZ;
ALTER TABLE bronze.market_events ADD COLUMN db_insert_completed_at    TIMESTAMPTZ;
ALTER TABLE bronze.market_events ADD COLUMN worker_completed_at       TIMESTAMPTZ;
```

Latency metrics are then derived via SQL at query time. This approach provides the
strongest production-like evidence: timestamps are stored alongside each event row
and percentile queries can be run directly against the database.

Requires: Cloud SQL schema migration, worker code changes, Terraform plan review.

### Option B: Execution Artifact from Joined Producer and Worker Logs

The producer writes timestamps to a local JSONL file. The worker writes structured
log entries to Cloud Logging with received/completed timestamps per event. After
the test run, a post-processing script joins producer output with worker logs by
event_id and computes latency metrics.

Requires: producer script changes, worker log structure changes, post-processing script.
Does not require Cloud SQL schema migration.

### Recommended Path

**Plan Option B first; implement Option A later.**

Option B can be proven without a schema migration and allows the latency model to be
validated end-to-end before committing to a schema change. Once Option B evidence is
accepted, Option A provides stronger production-like evidence by persisting timestamps
in the database alongside each event row.

---

## Future SQL Percentile Query

Once Option A is implemented and timestamps are stored in Cloud SQL, the following query
computes p50, p95, and p99 end-to-end latency for a given test prefix:

```sql
SELECT
    percentile_cont(0.50) WITHIN GROUP (ORDER BY end_to_end_latency_ms) AS p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY end_to_end_latency_ms) AS p95_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY end_to_end_latency_ms) AS p99_ms,
    count(*)                                                              AS row_count,
    min(end_to_end_latency_ms)                                            AS min_ms,
    max(end_to_end_latency_ms)                                            AS max_ms,
    avg(end_to_end_latency_ms)                                            AS avg_ms
FROM (
    SELECT
        EXTRACT(EPOCH FROM (worker_completed_at - producer_created_at)) * 1000
            AS end_to_end_latency_ms
    FROM bronze.market_events
    WHERE event_id LIKE 'latency-test-%'
      AND worker_completed_at IS NOT NULL
      AND producer_created_at IS NOT NULL
) sub;
```

This query will not execute until Option A is implemented and Cloud SQL is started in a
controlled execution branch.

---

## Acceptance Criteria for Future Implementation

The future execution is accepted only if all criteria pass:

| Criterion | Required result |
|---|---|
| Timestamps present | All eight timestamp fields populated for every test event |
| p50 latency computed | `percentile_cont(0.50)` returns a finite value |
| p95 latency computed | `percentile_cont(0.95)` returns a finite value |
| p99 latency computed | `percentile_cont(0.99)` returns a finite value |
| Row count | Equals the expected number of test events |
| Worker errors | 0 for the test prefix |
| Duplicate event_id count | 0 |
| DLQ messages | 0 for the test prefix |
| Cloud SQL final state | STOPPED / NEVER |
| Schedulers final state | PAUSED |
| Terraform apply | Not run unless explicitly required in the execution branch |

---

## Integration with Steady-State Throughput Plan

The latency instrumentation and steady-state throughput plans are designed to be sequenced:

1. **Implement latency instrumentation** in a controlled branch (code and/or schema changes
   depending on Option A or B).
2. **Run a small validation test**, e.g. 100 events with the latency test prefix, to confirm
   that all eight timestamps are populated and the percentile query returns plausible values.
3. **Confirm p50/p95/p99 calculation works** against real Cloud SQL data before scaling up.
4. **Run the steady-state throughput test** at 10 events/sec for 30 minutes as defined in
   [docs/steady-state-throughput-test-plan.md](steady-state-throughput-test-plan.md), with
   latency instrumentation active to capture the distribution under sustained load.

This sequencing ensures that the first run of the steady-state test also produces
latency distribution evidence. Do not run the steady-state test before confirming that
latency instrumentation works at small scale.

---

## Explicit Non-Claims

- p50/p95/p99 latency is not yet proven.
- Sustained throughput is not yet proven by this plan.
- Maximum throughput is not claimed.
- Dataflow is not implemented.
- Exactly-once production semantics are not claimed.
- Enterprise-grade latency SLO enforcement is not claimed.
- No new events are published by this plan.
- No Cloud SQL schema migration is executed by this plan.
- No Terraform apply is executed by this plan.
