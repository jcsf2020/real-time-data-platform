# Replay and Backfill Strategy

**Status:** STRATEGY -- replay and backfill semantics for the validated GCP data platform
**Date:** 2026-05-22
**Branch:** `docs/replay-backfill-strategy`
**Author intent:** Rigorous operational strategy. No unsupported claims. No implementation on this branch.

---

## 1. Context

### Current Validated Architecture

The Real-Time Data Platform operates on the following proven path:

```
Pub/Sub topic (market-events-raw)
  → Cloud Run worker (rtdp-pubsub-worker, push subscription, maxScale=1, concurrency=1)
    → Cloud SQL PostgreSQL (rtdp-postgres, bronze.market_events)

Cloud SQL PostgreSQL
  → BigQuery analytical append job (rtdp-bigquery-append-job, cursor-based MERGE)
    → BigQuery rtdp_analytics.market_events_raw (DAY-partitioned)

Cloud SQL PostgreSQL
  → dbt incremental models (rtdp-dbt-refresh-job)
    → Cloud SQL silver.market_event_minute_aggregates
    → Cloud SQL gold.market_event_daily_aggregates

BigQuery quality checks (bigquery-quality-checks.yml)
  → Cloud Monitoring custom metrics
    → alert policies
      → email notification delivery
```

All components are Terraform-managed with GCS remote state. PLAN_EXIT=0 is verified
across all validated branches. Cloud SQL is kept at activation policy `NEVER / STOPPED`
outside controlled validation windows. Cloud Scheduler jobs remain `PAUSED` by default.

### Why Replay and Backfill Matter

A data platform without documented replay and backfill semantics has an operational blind
spot. At some point, a downstream table will be accidentally truncated, a scheduled job
will fail silently, or a pipeline configuration will be changed and historical data will
need to be reconciled. The ability to answer "what do we do when data is missing or
wrong?" is a direct measure of data platform credibility and operational maturity.

Replay and backfill are also interview-critical topics. Any data engineering position
that involves operating a GCP data pipeline will expect the candidate to articulate:

- What is the authoritative source of truth for events?
- How do you recover a downstream analytical table after a failure?
- How do you handle duplicate processing without double-counting?
- What is the boundary between what you can recover and what you cannot?

This document closes the replay/backfill gap at the strategy level. It documents the
current operational source of truth, the proven replay paths, the known limitations,
and the explicit non-claims.

### This Is a Docs-Only Branch

This branch (`docs/replay-backfill-strategy`) is documentation only. It does not:

- Implement any replay or backfill automation.
- Modify any GCP resource configuration.
- Start Cloud SQL or resume Cloud Scheduler jobs.
- Execute any Terraform apply operations.
- Implement a DLQ production consumer.
- Run any validation commands against live GCP resources beyond read-only queries.

All runbooks in Section 8 are skeletons for future implementation branches. Commands
described in runbook sections are design targets, not executed commands.

---

## 2. Definitions

| Term | Definition |
|---|---|
| **Replay** | Re-processing a set of events or rows that have already been processed once, typically to rebuild a downstream table to a correct state. Replay assumes the source data is intact and the downstream table is stale, wrong, or missing. |
| **Backfill** | Loading data for a historical time window into a downstream table that was not populated during that window. Backfill is a one-time or bounded operation to fill a gap in downstream coverage. The 6,104-row Cloud SQL to BigQuery migration is an example of a bounded backfill. |
| **Reprocessing** | A general term covering both replay and backfill. Used when the distinction between the two is not important. Reprocessing always implies reading from the source of truth and writing to a downstream table. |
| **Idempotency** | A property of an operation whereby executing it more than once produces the same result as executing it once. The Cloud SQL `ON CONFLICT(event_id) DO NOTHING` write is idempotent: inserting the same event twice leaves exactly one row. The BigQuery MERGE in the incremental append job is idempotent: re-running the MERGE for the same cursor window leaves the same rows. |
| **Deduplication** | The act of identifying and discarding duplicate records before or during processing. Deduplication is the mechanism by which idempotency is achieved in practice. `event_id` is the primary deduplication key for all RTDP event processing. |
| **Source of truth** | The authoritative store from which downstream tables are rebuilt in a replay or backfill operation. See Section 5 for the explicit source-of-truth decision for this platform. |
| **Cursor** | A bookmark that tracks the high-water-mark of processed data. The BigQuery incremental append job uses a cursor (the maximum `ingest_timestamp` in `market_events_raw`) to determine which rows in Cloud SQL have not yet been appended to BigQuery. Cursor-based processing is safe to replay because rows with timestamps at or below the cursor are skipped by the MERGE condition. |
| **DLQ recovery** | The process of inspecting messages that were routed to the Dead Letter Queue (`market-events-raw-dlq`) after exceeding `maxDeliveryAttempts=5`, classifying them, deduplicating them, and deciding whether to reprocess, discard, or escalate them. |
| **Bounded validation window** | A controlled time window during which Cloud SQL is started, a specific number of events is processed, and Cloud SQL is stopped again. Bounded validation windows are the operational model for all RTDP evidence collection and are the proposed model for replay execution in a non-production portfolio context. |
| **Production-like replay** | A replay operation that is idempotent, evidence-backed, bounded in scope, executed from the correct source of truth, and validated by a row-count or quality check after completion. A production-like replay is not the same as an automated production replay service; it means the operation is performed correctly and its results are verified. |

---

## 3. Current Proven Capabilities

| Capability | Evidence | Current Status | Limitation |
|---|---|---|---|
| Cloud SQL bronze.market_events as operational source | 50,000-event load test; 18,000-event sustained test; `ON CONFLICT(event_id) DO NOTHING` | VALIDATED -- 50,000 rows with 0 duplicate event_ids; 18,000 rows with 0 missing worker events | Cloud SQL must be started for reads; activation policy is NEVER/STOPPED; multi-day production stability not proven |
| BigQuery bounded backfill | [docs/bigquery-bounded-backfill-evidence.md](bigquery-bounded-backfill-evidence.md) | VALIDATED -- 6,104 rows exported from bronze.market_events and loaded into market_events_raw; source/target count match | One-time bounded operation; not an automated backfill service; Cloud SQL must be started to read source |
| BigQuery incremental append / MERGE | [docs/bigquery-incremental-append-evidence.md](bigquery-incremental-append-evidence.md); [docs/bigquery-append-scheduler-proof-evidence.md](bigquery-append-scheduler-proof-evidence.md) | VALIDATED -- cursor-based MERGE; second run idempotent (6114 unchanged); 0 duplicates; scheduler proof (+3 exact rows on two consecutive executions) | Cursor is based on ingest_timestamp; events with identical ingest_timestamp at cursor boundary require careful handling; staging table must be empty before a safe re-run |
| dbt incremental models (silver and gold) | [docs/dbt-cloud-sql-incremental-execution-proof.md](dbt-cloud-sql-incremental-execution-proof.md) | VALIDATED -- Cloud SQL live execution; dbt run PASS=2; gold INSERT 0 7; silver INSERT 0 13; dbt test PASS=22 | Requires Cloud SQL to be started; lookback window is bounded (10-minute silver, 3-day gold); full rebuild requires `--full-refresh`; no Cloud SQL persisted latency columns |
| DLQ malformed-message routing | [docs/dlq-malformed-message-validation-evidence.md](dlq-malformed-message-validation-evidence.md) | VALIDATED WITH CAVEAT -- one malformed publish produced 12 DLQ entries for the same test_marker; routing mechanism proven | Exactly-once DLQ routing not claimed; no production DLQ consumer implemented; manual inspection only; re-ack cleanup issues observed |
| event_id deduplication / idempotent write path | 50,000-event load test (0 duplicates); 18,000-event sustained test (0 duplicates) | VALIDATED -- ON CONFLICT(event_id) DO NOTHING proven at bounded scale | Exactly-once delivery not claimed; at-least-once with application-layer deduplication; multi-day deduplication drift not characterized |
| Cloud Monitoring / alerting | [docs/bigquery-quality-incident-notification-delivery-proof.md](bigquery-quality-incident-notification-delivery-proof.md) | VALIDATED -- quality failure → Cloud Monitoring incident OPEN → email notification delivered | Alert is triggered by BigQuery quality check failures; replay validation must include a quality check run to produce monitoring evidence |

---

## 4. Replay and Backfill Scenarios

| Scenario | Current Recovery Path | Existing Evidence | Gap | Recommended Future Branch / Action |
|---|---|---|---|---|
| BigQuery table accidentally truncated | Run BigQuery bounded backfill from Cloud SQL (Section 6A), then BigQuery incremental append (Section 6B) | bigquery-bounded-backfill-evidence.md; bigquery-incremental-append-evidence.md | No automated recovery; requires manual Cloud SQL start and bounded backfill execution; no tested full-table recovery runbook | `feat/bigquery-recovery-runbook-validation` -- execute a full backfill in a bounded test window and collect row-count evidence |
| BigQuery append job failed for one scheduler window | Identify the last successful cursor position; re-run the incremental append job; MERGE is idempotent so re-run is safe | bigquery-append-scheduler-proof-evidence.md | No alerting on failed append job execution; cursor gap not automatically detected; operator must identify the missed window manually | `docs/dbt-observability-metrics-plan` -- add metrics for append job success/failure per run |
| dbt model output stale or wrong | Re-run dbt incremental refresh job; use `--full-refresh` flag if incremental lookback window is insufficient | dbt-cloud-sql-incremental-execution-proof.md | `--full-refresh` has not been executed against Cloud SQL live; recovery from a full-refresh perspective not proven in evidence | `feat/dbt-full-refresh-validation` -- execute `dbt run --full-refresh` against Cloud SQL and collect evidence |
| Malformed messages landed in DLQ | Inspect DLQ subscription; deduplicate by event_id or payload_sha256; classify rejection reason; decide whether to discard or manually reprocess | dlq-malformed-message-validation-evidence.md; dlq-deduplication-strategy.md | No DLQ consumer implemented; reprocessing is manual; deduplication is a documented strategy, not implemented code; DLQ subscription must be active to inspect | `feat/dlq-consumer-implementation` -- implement deduplication-aware DLQ consumer |
| Duplicate messages delivered by Pub/Sub | Cloud SQL ON CONFLICT(event_id) DO NOTHING discards duplicates at write time; BigQuery MERGE skips rows with matching event_id | 50,000-event test (0 duplicate event_ids); 18,000-event sustained test (0 duplicates) | At-least-once delivery is the proven model; exactly-once not claimed; duplicate rate under high load not characterized; DLQ duplicate count not capped | Document deduplication boundary explicitly in all runbooks |
| Cloud Run worker unavailable during a publish window | Pub/Sub retains messages for the configured retention period (must be verified from subscription/topic configuration before any replay operation); when worker resumes, undelivered messages are delivered | load-test evidence (0 DLQ messages during valid-event runs) | Pub/Sub seek/replay to a specific timestamp has not been validated; retention window has not been verified explicitly; worker resume after gap not tested | `feat/pubsub-seek-replay-validation` -- test Pub/Sub subscription seek to a timestamp and confirm re-delivery |
| Cloud SQL contains correct bronze rows but downstream tables are stale | Run BigQuery incremental append (Section 6B) and/or dbt incremental refresh (Section 6C); MERGE and incremental strategy are both idempotent | bigquery-incremental-append-evidence.md; dbt-cloud-sql-incremental-execution-proof.md | Requires Cloud SQL to be started; no automated staleness detection; no row-count comparison tool between Cloud SQL and BigQuery layers | `docs/dbt-observability-metrics-plan` -- add cross-layer row-count drift metric |
| Cloud SQL missing source events | This scenario is not recoverable from Cloud SQL alone; source must be Pub/Sub (if within retention window) or an upstream re-publish | No evidence for Pub/Sub seek/replay | Pub/Sub seek/replay not validated; upstream re-publish path not documented; Cloud SQL is the current source of truth and its data loss is not recoverable without upstream data | `feat/pubsub-seek-replay-validation` -- define and test the Pub/Sub recovery path |
| Schema evolution requires historical reprocessing | Full Cloud SQL to BigQuery backfill with new schema mapping; dbt `--full-refresh` for transformed layers | bigquery-bounded-backfill-evidence.md | No schema migration runbook for BigQuery analytical tier; no tested schema evolution replay path; dbt model schema changes require `--full-refresh` | `docs/schema-evolution-runbook` -- document schema migration procedure for BigQuery and dbt layers |
| Late-arriving events need correction | Cloud SQL ON CONFLICT is idempotent; events can be inserted after the fact; BigQuery incremental append will pick them up at next cursor advance | bigquery-incremental-append-evidence.md | No event-time ordering guarantee; processing-time cursor may advance past the late event's ingest_timestamp if the event arrives after the cursor; late events with timestamps before the cursor may not be re-appended automatically | Design cursor boundary handling for late events in `feat/bigquery-recovery-runbook-validation` |

---

## 5. Source of Truth Decision

The following decisions are explicit and binding for all replay and backfill operations
on the Real-Time Data Platform as of this document.

**Cloud SQL `bronze.market_events` is the current operational source of truth for replay into downstream analytical layers.**

This means:
- When BigQuery analytical tables need to be rebuilt, the source is Cloud SQL bronze rows.
- When dbt silver and gold layers are rebuilt, the source is Cloud SQL bronze rows via dbt incremental or full-refresh execution.
- Cloud SQL is not a recovery source for events that were never written to it (e.g., events that failed Cloud Run processing).

**BigQuery is an analytical sink, not the primary operational source of truth.**

BigQuery `rtdp_analytics.market_events_raw` is derived from Cloud SQL. It should not be
used as the source for replay operations. It may be used for post-replay validation
(row count comparison, quality checks). BigQuery is not the origin.

**Pub/Sub is a delivery layer, not a durable long-term event store.**

Pub/Sub message retention is time-bounded and must be verified from the subscription or
topic configuration before any replay operation. No specific retention duration is claimed
in this document; the configured window has not been explicitly verified. After the
retention window, messages are not recoverable from Pub/Sub. Pub/Sub retention is a
short-term buffer, not an archival event log. Pub/Sub seek/replay is a time-bounded
recovery mechanism, not a general-purpose historical replay capability. Pub/Sub seek/replay
remains a future/limited option and has not been validated in this project.

**DLQ is an exception queue, not a canonical replay store.**

The DLQ (`market-events-raw-dlq`) contains only messages that failed processing after
`maxDeliveryAttempts=5`. It is not a copy of all events. DLQ entries may be duplicated
(one malformed publish produced 12 DLQ entries per the validated evidence). DLQ must
not be used as a source of truth for replay without explicit deduplication.

**Dataflow is not part of the current replay path.**

Dataflow has not been implemented. No Dataflow-based replay or backfill path exists or
is claimed. See Section 11 for the Dataflow relationship.

---

## 6. Current Replay Paths

### A. Cloud SQL → BigQuery Bounded Backfill

**What it recovers:** All rows in Cloud SQL `bronze.market_events` that are not yet in
BigQuery `rtdp_analytics.market_events_raw`. A bounded time window can be specified
using a `WHERE event_timestamp BETWEEN start AND end` filter on the Cloud SQL query.

**What it does not recover:** Events that were never written to Cloud SQL (e.g., lost
in Cloud Run worker processing, or published after the Pub/Sub retention window without
Cloud Run availability). Events that were written to Cloud SQL but have `event_id`
values that already exist in BigQuery (these are skipped by the MERGE deduplication).

**Current evidence:** [docs/bigquery-bounded-backfill-evidence.md](bigquery-bounded-backfill-evidence.md) --
6,104 rows exported from Cloud SQL bronze.market_events and loaded into BigQuery
market_events_raw; source/target count match accepted.

**Limitations:**
- Cloud SQL must be started for the backfill read operation.
- No automated backfill service exists; this is a manual, operator-initiated operation.
- The backfill script (`scripts/bigquery_append_job.py` or equivalent) must be executed
  in a controlled, bounded window.
- A full-table backfill replaces all historical data; it must not be run while new events
  are being actively appended (potential cursor conflict).

**Safe non-claims:**
- No automated backfill service is claimed.
- No real-time backfill capability is claimed.
- No guarantee of backfill completion time is claimed.

---

### B. Cloud SQL → BigQuery Incremental Append

**What it recovers:** Rows in Cloud SQL `bronze.market_events` with `ingest_timestamp`
greater than the current cursor position in BigQuery (the maximum `ingest_timestamp` in
`market_events_raw`). The cursor-based MERGE skips rows already in BigQuery and appends
new rows only.

**What it does not recover:** Rows with `ingest_timestamp` at or before the current
cursor. If a Cloud SQL row was written with a timestamp that fell below the cursor at
the time of the last successful append, it will not be picked up by the incremental job.
This is the late-arriving event gap described in Section 4.

**Current evidence:** [docs/bigquery-incremental-append-evidence.md](bigquery-incremental-append-evidence.md);
[docs/bigquery-append-scheduler-proof-evidence.md](bigquery-append-scheduler-proof-evidence.md) --
cursor-based MERGE proven; second run idempotent (6114 unchanged); scheduler proof
(+3 exact rows on consecutive executions); 0 duplicates.

**Limitations:**
- Re-running the incremental append job is safe and idempotent due to MERGE semantics.
- Staging table must be empty (`rtdp_analytics.market_events_raw_staging` numRows=0) before
  re-running; a non-empty staging table indicates a previous run did not complete cleanly.
- Cloud SQL must be started.
- The cursor is a single timestamp; it does not handle out-of-order writes cleanly.

**Safe non-claims:**
- No exactly-once write semantics are claimed.
- No sub-minute data freshness is claimed; the scheduler runs hourly.

---

### C. Cloud SQL → dbt Incremental Rebuild / Refresh

**What it recovers:** Silver and gold aggregation layers derived from Cloud SQL bronze
rows. The incremental strategy uses a lookback window (10 minutes for silver, 3 days for
gold) to reprocess a recent slice of data. A `--full-refresh` execution rebuilds the
entire model from scratch.

**What it does not recover:** Rows not present in Cloud SQL at the time of the dbt run.
dbt transformations are reads from Cloud SQL; they do not ingest new data. If bronze.market_events
is incomplete, all downstream layers are incomplete.

**Current evidence:** [docs/dbt-cloud-sql-incremental-execution-proof.md](dbt-cloud-sql-incremental-execution-proof.md) --
Cloud SQL live incremental execution; dbt run PASS=2; gold INSERT 0 7; silver INSERT 0 13;
dbt test PASS=22.

**Limitations:**
- The incremental lookback window may not be sufficient for large gaps; `--full-refresh`
  is required if the stale window exceeds the lookback period.
- `dbt run --full-refresh` against Cloud SQL live has not been tested; this is a known gap.
- Cloud SQL must be started.
- dbt test PASS=22 validates transformation logic but not the completeness of source data.

**Safe non-claims:**
- No claim that dbt `--full-refresh` has been validated against live Cloud SQL.
- No claim of event-time windowed aggregations; dbt models use processing-time aggregations.

---

### D. DLQ Manual Inspection and Deduplication-Aware Handling

**What it recovers:** Insight into which messages failed processing and why. With manual
inspection and deduplication, an operator can determine the set of original malformed or
undeliverable messages and decide whether to discard them or reprocess them by re-publishing
corrected versions.

**What it does not recover:** Events that were lost before reaching the DLQ (e.g.,
never published to Pub/Sub, or dropped before `maxDeliveryAttempts` was reached). The
DLQ contains only messages that were received and rejected N times by the worker.

**Current evidence:** [docs/dlq-malformed-message-validation-evidence.md](dlq-malformed-message-validation-evidence.md) --
malformed payload reached DLQ; multiple DLQ entries observed for same test_marker;
[docs/dlq-deduplication-strategy.md](dlq-deduplication-strategy.md) -- deduplication key
hierarchy defined (event_id > payload_sha256 > test_marker > composite fallback).

**Limitations:**
- No DLQ production consumer is implemented. Inspection is manual via `gcloud pubsub subscriptions pull`.
- DLQ entries are deduplicated by strategy only; no deduplication store has been implemented.
- Re-ack cleanup (`--ack-ids-file`) was observed to be unsupported; `--auto-ack` and
  subscription deletion were used as alternatives in the evidence run.
- Replaying a corrected version of a DLQ message requires a manual re-publish; no
  automated replay exists.

**Safe non-claims:**
- No automated DLQ consumer is claimed.
- No exactly-once DLQ routing is claimed.
- No production poison-message handling is claimed.

---

### E. Pub/Sub Retention-Based Replay (Future / Limited Option)

**What it could recover:** Messages published to `market-events-raw` that were not
successfully processed by the Cloud Run worker, if the replay is executed within the
Pub/Sub retention window. The actual retention duration must be verified from the
subscription or topic configuration before any seek/replay operation is attempted.
No specific retention duration is claimed in this document.

**Current mechanism:** Pub/Sub subscriptions support a `Seek` operation to reset the
subscription acknowledgment cursor to a specific timestamp. This would cause unacked
messages from that point forward to be re-delivered to the worker.

**Current evidence:** None. Pub/Sub seek/replay has not been validated in this project.
No seek operation has been executed against any production Pub/Sub subscription.

**Limitations:**
- Pub/Sub seek/replay is time-bounded by the message retention period.
- Seeking a subscription to an earlier timestamp will re-deliver messages that were
  already successfully processed; the Cloud Run worker and Cloud SQL `ON CONFLICT` must
  be relied upon for deduplication during re-delivery.
- Cloud Run worker must be active to receive re-delivered messages; Cloud SQL must be
  started to receive the writes.
- Re-delivery may cause duplicate DLQ entries if messages fail again.

**Safe non-claims:**
- Pub/Sub seek/replay is not claimed as a validated capability.
- No retention window configuration has been explicitly verified.
- Re-delivery deduplication has not been tested under replay conditions.

---

## 7. Idempotency and Deduplication Strategy

### event_id as Primary Deduplication Key

Every RTDP event is produced with a UUID `event_id` field, set by the producer at
publish time. `event_id` uniquely identifies a business event and is used as the
primary deduplication key at every layer of the platform.

`event_id` is stable across:
- Re-delivery by Pub/Sub (same event_id on re-delivery).
- Replay via BigQuery MERGE (MERGE ON clause uses event_id).
- DLQ recovery (event_id is Priority 1 in the deduplication key hierarchy).

`event_id` is set once at the producer and never mutated downstream.

### Cloud SQL ON CONFLICT Behaviour

The Cloud Run worker inserts events into Cloud SQL `bronze.market_events` using:

```sql
INSERT INTO bronze.market_events (...) VALUES (...)
ON CONFLICT (event_id) DO NOTHING;
```

This means:
- The first insert for a given `event_id` creates the row.
- Subsequent inserts for the same `event_id` are silently discarded.
- The row in Cloud SQL reflects the first-seen version of the event; no updates.

**Evidence:** 50,000-event bounded load test (0 duplicate event_ids in Cloud SQL);
18,000-event sustained test (0 duplicate event_ids). `ON CONFLICT` has not been
explicitly tested with deliberate duplicate publishes; deduplication evidence is
from the absence of duplicates under normal load conditions.

### BigQuery MERGE / Cursor Behaviour

The BigQuery incremental append job performs a cursor-based MERGE:

1. Export rows from Cloud SQL where `ingest_timestamp > cursor`.
2. Load to BigQuery staging table.
3. MERGE staging into `market_events_raw` ON `event_id`.
4. Delete staging rows.
5. Update cursor to new maximum `ingest_timestamp`.

MERGE ON `event_id` means re-running the append job for the same cursor window will not
create duplicates in `market_events_raw`. The MERGE semantics are idempotent.

**Evidence:** Second incremental append run was idempotent (6114 unchanged after second
run); scheduler proof showed +3 exact rows on consecutive executions with 0 duplicate_count.

### DLQ Deduplication Strategy

See [docs/dlq-deduplication-strategy.md](dlq-deduplication-strategy.md) for the full
specification. Summary:

- **Priority 1:** `event_id` -- use when the DLQ payload is a valid event with a parseable event_id.
- **Priority 2:** `payload_sha256` -- use when the payload is malformed or does not conform to the event contract.
- **Priority 3:** `test_marker` -- use only in controlled validation scenarios.
- **Priority 4:** `source_subscription + publish_time + payload_hash` -- composite fallback.

`messageId` from the DLQ entry must not be used as the business deduplication key.
Different DLQ entries for the same original message carry different `messageId` values.

### Why Exactly-Once Production Semantics Are Not Claimed

Pub/Sub guarantees at-least-once delivery. A message may be delivered more than once
to the worker, especially under retry conditions (transient worker errors, Cloud Run
restarts, push subscription retries). The `ON CONFLICT(event_id) DO NOTHING` at Cloud
SQL provides application-layer idempotency: the second delivery of a valid event does
not create a duplicate row.

This is **deduplicated at-least-once delivery**, not **exactly-once delivery**.

The distinction matters because:
- Exactly-once delivery requires either transport-layer guarantees (not provided by Pub/Sub)
  or a two-phase commit / exactly-once write API (not implemented in this project).
- Deduplicated at-least-once means the observable outcome is identical to exactly-once
  (one row per event_id in Cloud SQL) but the processing may have occurred more than once.
- Side effects of duplicate processing (log writes, metric increments, alerts) may be
  counted more than once even when the Cloud SQL row count is correct.

The 0-duplicate result across 50,000 events and 18,000 sustained events means that at
the observed operating rate and conditions, duplicates were not observed. This does not
preclude duplicates at higher rates or under different failure conditions.

---

## 8. Proposed Operational Runbooks

The following runbooks are skeletons. Commands are design targets, not executed commands.
Each runbook must be implemented and validated in a separate execution branch before use
in a live environment.

> **WARNING -- not approved for execution.** The command blocks below are future
> implementation sketches only. They are not approved execution commands. They must be
> converted into validated runbooks in a separate branch (e.g.,
> `feat/bigquery-recovery-runbook-validation`) with its own preflight checks, cost
> controls, and evidence document before any live use.

---

### Runbook R-01: Replay BigQuery from Cloud SQL for a Bounded Time Window

**Purpose:** Rebuild a bounded time window in `rtdp_analytics.market_events_raw` from
Cloud SQL `bronze.market_events`.

**Preconditions:**
- Cloud SQL `rtdp-postgres` is stopped (activation policy NEVER/STOPPED).
- BigQuery staging table `rtdp_analytics.market_events_raw_staging` is empty (numRows=0).
- A time window `[replay_start, replay_end]` has been identified.
- Terraform plan shows PLAN_EXIT=0 (no pending infrastructure changes).
- No active Cloud Scheduler jobs are running append or dbt jobs.

**Future command sketch -- not approved for execution:**
```
# 1. Start Cloud SQL (controlled window)
gcloud sql instances patch rtdp-postgres --activation-policy=ALWAYS

# 2. Run bounded backfill for the time window
#    (script to be designed in feat/bigquery-recovery-runbook-validation)
uv run python scripts/bigquery_bounded_backfill.py \
  --start-timestamp REPLAY_START \
  --end-timestamp REPLAY_END \
  --dry-run  # run dry first; remove for live execution

# 3. Verify row count in BigQuery for the window
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM rtdp_analytics.market_events_raw
   WHERE event_timestamp BETWEEN 'REPLAY_START' AND 'REPLAY_END'"

# 4. Stop Cloud SQL
gcloud sql instances patch rtdp-postgres --activation-policy=NEVER
```

**Safety controls:**
- Cloud SQL must be stopped immediately after the replay operation.
- The `--dry-run` flag must be used first to verify row counts before live execution.
- Replay must not be run while the scheduler is active (append job could conflict).
- BigQuery staging table (`rtdp_analytics.market_events_raw_staging`) must be empty before starting.

**Validation evidence to capture:**
- Cloud SQL row count for the window before and after.
- BigQuery row count for the window before and after.
- Staging table row count = 0 after replay.
- PLAN_EXIT=0 confirmed after operation.
- Cloud SQL state = STOPPED/NEVER after operation.

**Rollback / stop condition:**
- If BigQuery row count after replay does not match Cloud SQL source count: halt,
  inspect staging table, re-run with `--dry-run` before attempting again.
- If Cloud SQL fails to stop after replay: immediate manual stop via Cloud Console.

**Non-claims:**
- This runbook does not cover events that were never in Cloud SQL.
- This runbook does not cover events with timestamps outside the specified window.

---

### Runbook R-02: Re-Run BigQuery Incremental Append Safely

**Purpose:** Re-run the `rtdp-bigquery-append-job` for a missed or failed scheduler window.

**Preconditions:**
- BigQuery staging table is empty (numRows=0).
- Cloud SQL `rtdp-postgres` is stopped.
- Identify the last successful cursor position (max `ingest_timestamp` in `market_events_raw`).
- PLAN_EXIT=0 confirmed.

**Future command sketch -- not approved for execution:**
```
# 1. Check staging table is empty
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM rtdp_analytics.market_events_raw_staging"

# 2. Start Cloud SQL
gcloud sql instances patch rtdp-postgres --activation-policy=ALWAYS

# 3. Trigger append job manually
gcloud run jobs execute rtdp-bigquery-append-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# 4. Monitor job execution
gcloud run jobs executions describe EXECUTION_ID \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# 5. Verify row count increase
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM rtdp_analytics.market_events_raw"

# 6. Stop Cloud SQL
gcloud sql instances patch rtdp-postgres --activation-policy=NEVER
```

**Safety controls:**
- Run is idempotent; re-running the same window will not create duplicates.
- If staging table is non-empty before starting, investigate the prior run first.
- Cloud SQL must be stopped after the operation.

**Validation evidence to capture:**
- Row count before and after in `market_events_raw`.
- `duplicate_count=0` from job logs.
- `rtdp_analytics.market_events_raw_staging` numRows=0 after completion.
- Job execution ID and final state (SUCCEEDED).
- Cloud SQL state = STOPPED/NEVER after operation.

**Rollback / stop condition:**
- If duplicate_count > 0: halt; investigate MERGE condition; do not run again until root
  cause is identified.
- If `market_events_raw_staging` is non-empty after job: staging was not cleaned up;
  investigate before running again.

**Non-claims:**
- This runbook does not cover rows with `ingest_timestamp` before the current cursor.

---

### Runbook R-03: Re-Run dbt Incremental Models Safely

**Purpose:** Refresh silver and gold dbt models to incorporate recent Cloud SQL data.

**Preconditions:**
- Cloud SQL `rtdp-postgres` is stopped.
- PLAN_EXIT=0 confirmed.
- Identify whether the lookback window (10 min silver, 3 day gold) is sufficient.
  If not, `--full-refresh` is required (see caveat below).

**Future command sketch -- not approved for execution:**
```
# 1. Start Cloud SQL
gcloud sql instances patch rtdp-postgres --activation-policy=ALWAYS

# 2. Run dbt refresh job (incremental)
gcloud run jobs execute rtdp-dbt-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# OR for a full rebuild:
# NOTE: full-refresh against Cloud SQL live has not been validated
# gcloud run jobs execute rtdp-dbt-refresh-job \
#   --region=europe-west1 \
#   --args="--full-refresh"

# 3. Monitor execution
gcloud run jobs executions describe EXECUTION_ID \
  --region=europe-west1

# 4. Stop Cloud SQL
gcloud sql instances patch rtdp-postgres --activation-policy=NEVER
```

**Safety controls:**
- Incremental re-run is safe; lookback window will reprocess recent data correctly.
- `--full-refresh` must be used carefully; it drops and recreates the model from scratch.
- `--full-refresh` against Cloud SQL live is not yet validated; treat as experimental.
- Cloud SQL must be stopped after the operation.

**Validation evidence to capture:**
- dbt run output: PASS count for silver and gold models.
- dbt test output: PASS count for all 22 tests.
- Row counts in silver and gold tables before and after.
- Cloud SQL state = STOPPED/NEVER after operation.

**Rollback / stop condition:**
- If dbt run shows FAIL: inspect model SQL and source data before re-running.
- If dbt test FAIL: data quality issue in source or transformation; escalate before merge.

**Non-claims:**
- `--full-refresh` against Cloud SQL live has not been validated.
- dbt transformations do not ingest new events; they transform existing Cloud SQL bronze rows.

---

### Runbook R-04: Inspect DLQ and Classify Poison Messages

**Purpose:** Enumerate and classify messages that were routed to the DLQ.

**Preconditions:**
- DLQ topic `market-events-raw-dlq` has a pull subscription active.
- Cloud SQL is stopped (this runbook does not require Cloud SQL).
- PLAN_EXIT=0 confirmed.

**Future command sketch -- not approved for execution:**
```
# 1. Pull sample DLQ messages
gcloud pubsub subscriptions pull market-events-raw-dlq-sub \
  --limit=10 \
  --format=json

# 2. For each message, extract:
#    - messageId
#    - publishTime
#    - CloudPubSubDeadLetterSourceDeliveryCount attribute
#    - CloudPubSubDeadLetterSourceSubscription attribute
#    - Payload (base64-decoded)

# 3. Compute payload_sha256 for each entry
#    python3 -c "import hashlib; print(hashlib.sha256(b'PAYLOAD').hexdigest())"

# 4. Classify rejection reason
#    - Missing required fields?
#    - Schema version mismatch?
#    - Non-parseable JSON?
#    - Unknown event_type?
```

**Safety controls:**
- Pull without ack; do not acknowledge messages until classification is complete.
- Do not re-publish to main topic without explicit operator decision.
- Do not start Cloud SQL during inspection.

**Validation evidence to capture:**
- DLQ entry count before and after inspection.
- Deduplication key for each canonical poison message.
- Classification reason for each canonical poison message.
- No Cloud SQL writes during inspection.

**Rollback / stop condition:**
- If DLQ entries appear to contain PII or secrets: halt; escalate to operator;
  do not print payload content to shared logs.

**Non-claims:**
- No automated DLQ consumer exists.
- DLQ inspection does not recover the original events.

---

### Runbook R-05: Reprocess DLQ Messages Manually

**Purpose:** Re-publish corrected versions of poison messages to the main Pub/Sub topic.

**Preconditions:**
- Runbook R-04 has been completed for the same set of messages.
- Canonical poison message records have been created (deduplication complete).
- Operator has explicitly approved each message for replay (replay_status = "approved").
- Cloud Run worker is active.
- Cloud SQL is running.

**Future command sketch -- not approved for execution:**
```
# For each approved poison message:
# 1. Construct corrected payload
# 2. Re-publish to main topic
gcloud pubsub topics publish market-events-raw \
  --message='CORRECTED_PAYLOAD' \
  --attribute=replay_source=dlq_recovery,original_event_id=ORIGINAL_ID

# 3. Verify worker processed the corrected message
gcloud logging read \
  "resource.type=cloud_run_revision AND
   jsonPayload.event_id=ORIGINAL_ID AND
   jsonPayload.status=ok" \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=5

# 4. Verify no new DLQ entry for the corrected message
```

**Safety controls:**
- Never replay automatically; operator approval is mandatory before each re-publish.
- Include `replay_source=dlq_recovery` attribute on re-published messages to distinguish
  from original publishes in logs.
- Cloud SQL `ON CONFLICT` will discard duplicates if the original event_id was already
  written successfully.
- Cloud SQL must be stopped after the operation.

**Validation evidence to capture:**
- Corrected message published successfully (publish ack).
- Worker log shows status=ok for the corrected event_id.
- No new DLQ entry created.
- Cloud SQL row exists for the event_id.
- Cloud SQL state = STOPPED/NEVER after operation.

**Rollback / stop condition:**
- If corrected message routes to DLQ again: halt replay; investigate root cause before
  attempting further re-publishes.

**Non-claims:**
- No automated replay service is claimed.
- Re-published messages are counted as new events by Cloud Monitoring metrics.

---

### Runbook R-06: Recover from Failed Scheduled Append Window

**Purpose:** Detect and recover from a BigQuery incremental append job that failed during
a scheduled execution window.

**Preconditions:**
- BigQuery row count is lower than expected based on event rate.
- Cloud Scheduler job log shows a failed execution.
- BigQuery staging table is empty (numRows=0).
- PLAN_EXIT=0 confirmed.

**Future command sketch -- not approved for execution:**
```
# 1. Check Cloud Scheduler job execution history
gcloud scheduler jobs describe rtdp-bigquery-append-scheduler \
  --location=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# 2. Check Cloud Run job execution list for failures
gcloud run jobs executions list \
  --job=rtdp-bigquery-append-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# 3. Identify current cursor position
bq query --use_legacy_sql=false \
  "SELECT MAX(ingest_timestamp) as cursor FROM rtdp_analytics.market_events_raw"

# 4. Follow Runbook R-02 to re-run the append job
```

**Safety controls:**
- Verify staging table is empty before re-run.
- Do not manually advance the cursor; let the job compute it from BigQuery.

**Validation evidence to capture:**
- Row count before recovery.
- Row count after recovery.
- Execution ID of recovery run.
- Scheduler state = PAUSED after investigation.

**Rollback / stop condition:**
- If row count does not increase after recovery run: inspect Cloud SQL row count for
  the same window to confirm data exists in the source.

**Non-claims:**
- No alert currently fires on failed append job execution; detection is manual.

---

### Runbook R-07: Validate Downstream Row Counts After Replay

**Purpose:** Confirm that a replay or backfill operation produced the expected results.

**Preconditions:**
- Replay or backfill operation (R-01 through R-06) has completed.
- Cloud SQL has been returned to STOPPED/NEVER.
- BigQuery quality check workflow is available.

**Future command sketch -- not approved for execution:**
```
# 1. Check BigQuery row count
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) as total_rows,
          COUNT(DISTINCT event_id) as unique_events,
          MIN(event_timestamp) as earliest,
          MAX(event_timestamp) as latest
   FROM rtdp_analytics.market_events_raw"

# 2. Compare with Cloud SQL source count (if Cloud SQL can be started briefly)
#    SELECT COUNT(*) FROM bronze.market_events
#    WHERE event_timestamp BETWEEN replay_start AND replay_end

# 3. Run BigQuery quality checks
#    (workflow_dispatch on bigquery-quality-checks.yml)
gh workflow run bigquery-quality-checks.yml \
  --field min_row_count=EXPECTED_MIN \
  --field freshness_max_age_hours=0

# 4. Confirm duplicate count = 0
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM (
     SELECT event_id, COUNT(*) as cnt
     FROM rtdp_analytics.market_events_raw
     GROUP BY event_id
     HAVING cnt > 1
   )"

# 5. Confirm staging table is empty
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM rtdp_analytics.market_events_raw_staging"
```

**Safety controls:**
- This runbook is read-only; no writes to BigQuery or Cloud SQL.
- Cloud SQL start is optional and should be bounded to the count verification step.

**Validation evidence to capture:**
- Total row count in market_events_raw after replay.
- Unique event_id count = total row count (0 duplicates).
- BigQuery quality check conclusion: success.
- `rtdp_analytics.market_events_raw_staging` numRows=0.
- Cloud SQL state = STOPPED/NEVER after operation.

---

## 9. Failure Mode Matrix

| Failure Mode | Detection Signal | Existing Alert / Evidence | Recovery Owner | Replay / Backfill Path | Evidence Required After Recovery | Remaining Gap |
|---|---|---|---|---|---|---|
| BigQuery table truncated accidentally | Row count drops to 0; BigQuery quality check fails (`row_count_minimum`) | `RTDP BigQuery Quality Failure` alert policy (bigquery-quality-incident-notification-delivery-proof.md) | Operator | R-01: Bounded backfill from Cloud SQL; then R-07 | Row count restored; 0 duplicates; quality check pass; Cloud SQL STOPPED/NEVER | No automated truncation detection; R-01 runbook not yet validated live |
| BigQuery append job failed (scheduler window) | Row count not increasing; scheduler execution log shows failure | No dedicated alert for append job failure; manual inspection required | Operator | R-06: Identify failed window; R-02: Re-run incremental append; R-07: Validate | Row count increase; execution SUCCEEDED; 0 duplicate_count; staging=0 | No alert on failed append job; gap detection is manual |
| dbt model output stale | Stale `max(window_start)` in silver; stale `max(event_date)` in gold; quality check does not cover dbt layers | No alert on dbt model staleness in current platform | Operator | R-03: Re-run dbt incremental refresh; if lookback insufficient, `--full-refresh` | dbt run PASS=2; dbt test PASS=22; row counts updated | No Cloud Monitoring metric for dbt model staleness; this gap is addressed by `docs/dbt-observability-metrics-plan` |
| Cloud Run worker unavailable during publish window | Worker error logs; `worker_message_error_count > 0` in Cloud Monitoring; undelivered message backlog growth in Pub/Sub | `RTDP Worker Message Error Alert` alert policy | Operator | E: Pub/Sub retention-based re-delivery (if within retention window); worker resume; R-07: Validate after recovery | Worker error count = 0 after recovery; Cloud SQL row count matches expected | Pub/Sub seek/replay not validated; retention window not explicitly verified; worker unavailability detection lag |
| DLQ receives messages unexpectedly | DLQ subscription backlog growth; Cloud Monitoring logs-based metric (not currently configured for DLQ backlog) | No current alert for DLQ backlog growth | Operator | R-04: Inspect and classify; R-05: Manual reprocess if approved | Canonical poison message records; classification complete; no new DLQ entries after reprocess | No DLQ consumer implemented; no DLQ backlog alert; DLQ inspection is manual |
| Duplicate events in Cloud SQL | event_id duplicate count > 0 in Cloud SQL | No current Cloud SQL duplicate alert; detected by post-load query in load tests | Operator | Cloud SQL `ON CONFLICT` discards duplicates at write time; duplicates in source re-publishes are absorbed | `SELECT COUNT(*) - COUNT(DISTINCT event_id) = 0` in bronze.market_events | No automated duplicate monitoring in Cloud SQL layer |
| Cloud SQL data loss (corruption or accidental deletion) | Row count drop in Cloud SQL; downstream BigQuery quality failures | BigQuery quality failure alert (indirectly) | Operator | Cloud SQL backups (if configured and enabled); re-ingestion from Pub/Sub (if within retention); Dataflow not available | Cloud SQL row count restored; source/target count match | Cloud SQL backup configuration not documented; Pub/Sub seek/replay not validated; no DR drill performed |
| Schema mismatch causes event rejection | Worker error logs (`schema_validation_error`); DLQ backlog growth | Worker error alert; DLQ backlog (manual inspection) | Operator | Fix schema in producer or worker; re-publish corrected events; R-05 for DLQ entries | Worker processes corrected events without error; DLQ backlog drains | No schema registry in current path; schema version is a field in the event payload only |
| Late-arriving events missed by cursor | Row count in BigQuery < row count in Cloud SQL for a time window | BigQuery quality check (row_count_minimum) | Operator | Identify events with `ingest_timestamp < cursor`; design bounded re-backfill for the gap window using R-01 | Row count match for the affected window; 0 duplicates after backfill | Cursor boundary handling for late events not designed; late event definition not specified |
| Terraform state drift | `PLAN_EXIT != 0` in CI | Terraform plan CI (terraform-plan.yml) | Operator | Identify drift source; reconcile with `terraform import` or controlled `terraform apply` | PLAN_EXIT=0 restored; no destructive changes applied | Automated PLAN_EXIT != 0 alert not configured |

---

## 10. Production-Likeness Assessment

### What Is Production-Like

The following aspects of the replay/backfill capabilities are production-like:

- **Source of truth decision is explicit and documented.** Cloud SQL bronze.market_events
  is the authoritative event store for downstream reconstruction. This mirrors production
  operational practice where the transactional database is the source of truth for batch
  analytical rebuilds.
- **Idempotent write paths exist at every layer.** Cloud SQL `ON CONFLICT`, BigQuery
  MERGE, and dbt incremental `unique_key` all protect against duplicate row creation
  during replay operations. This is a production-grade design pattern.
- **Cursor-based incremental append is operationally sound.** The cursor tracks the
  high-water-mark of processed data; re-running the append job within the same window
  is safe. This is standard practice for batch-mode analytical ingestion pipelines.
- **Deduplication strategy is documented and key hierarchy is explicit.** The DLQ
  deduplication strategy defines a deterministic, auditable approach that mirrors
  production poison-message handling designs.
- **Failure mode matrix defines detection signals and recovery owners.** Having an
  explicit owner and recovery path for each failure mode is a production operations
  requirement.

### What Is Portfolio-Grade Only

The following aspects are documented at a portfolio or design level but not production-validated:

- **No automated recovery service exists.** All replay and backfill operations require
  manual, operator-initiated execution. A production platform would have automated
  detection and at least semi-automated recovery triggers.
- **No end-to-end recovery drill has been executed.** The runbooks in Section 8 are
  skeletons. None have been executed against a live failure scenario. A production
  platform would require periodic fire drills.
- **Pub/Sub seek/replay is not validated.** The retention-based replay path (Section 6E)
  is a design option, not a proven capability.
- **dbt `--full-refresh` against Cloud SQL live is not proven.** The incremental path is
  proven, but a full model rebuild in recovery scenario has not been tested.
- **No cross-layer row-count comparison tool exists.** Validating that Cloud SQL and
  BigQuery agree on row counts for a given time window requires manual queries; no
  automated drift metric exists.

### What Is Missing for Enterprise Production

The following are missing for a real production deployment:

- Automated failure detection with sub-minute alerting on missing append windows.
- Automated or operator-assisted recovery workflows (e.g., Cloud Workflows or Cloud Run
  Jobs triggered by alert conditions).
- A DLQ consumer service with deduplication store and operator approval workflow.
- Cloud SQL automated backups with verified restore drills.
- A staging/production environment split (all infrastructure is in one GCP project).
- A Pub/Sub retention window verification and seek/replay validation.
- Disaster recovery restore test with documented RTO and RPO.
- Multi-day production stability evidence.
- Exactly-once semantics on the write path to BigQuery.

### What Can Be Safely Said in Interviews

- "I documented the operational source of truth for all replay operations: Cloud SQL
  bronze.market_events. All downstream layers -- BigQuery, silver, gold -- can be
  rebuilt from Cloud SQL."
- "The BigQuery write path uses cursor-based MERGE and is idempotent; re-running the
  append job for a missed window does not create duplicates. This has been validated with
  two consecutive runs producing the expected +3 row delta and a confirmed idempotent
  second run."
- "The Cloud SQL write path uses ON CONFLICT(event_id) DO NOTHING, which I have validated
  across 50,000 events with 0 duplicate event_ids."
- "I documented a DLQ deduplication strategy after observing that one malformed publish
  produced 12 DLQ entries. I do not claim a production DLQ consumer; I claim the design."
- "I documented a replay/backfill strategy with explicit runbook skeletons, a failure
  mode matrix, and explicit non-claims. No automated production replay service is claimed."

---

## 11. Relationship to Dataflow

### Dataflow Is Not Needed for Current Replay Semantics

The current replay and backfill strategy is built entirely on Cloud SQL, BigQuery MERGE,
and dbt. None of these components require Dataflow. Dataflow is not part of any current
recovery path and is not needed to document or execute the replay operations described
in this document.

The source of truth decision (Cloud SQL), the cursor-based append, the dbt incremental
refresh, and the DLQ inspection process are all valid and actionable without any Dataflow
implementation.

### Dataflow Could Improve Future Replay Paths (Under Specific Conditions)

If the platform is extended with Dataflow, the replay path could be enhanced:

- **Pub/Sub seek-based replay through a Beam pipeline** would allow replaying a historical
  window of events through the same transformation logic used in real-time processing.
  This requires the Beam pipeline to be designed with idempotent BigQuery writes
  (`COMMITTED` mode) to prevent duplicates during replay.
- **Late-event handling via `AllowedLateness`** would allow events that arrive outside
  the current ingest_timestamp cursor window to be included in the correct window.
- **Event-time windowing** would produce more accurate historical aggregations than the
  current processing-time dbt approach.

None of these are implemented. They are design directions only.

### The Current Strategy Must Be Valid Before Implementing Dataflow

The replay/backfill strategy documented here is the foundation for any future Dataflow
implementation. Adding Dataflow to a platform without documented replay semantics would
create a more complex system with the same operational blind spot. This document should
be completed and reviewed before any Dataflow implementation begins.

### Do Not Claim Dataflow Replay Capability

No Dataflow replay path has been implemented, tested, or evidenced. Any claim that
Dataflow is used for replay or backfill in this project would be false.

See [docs/dataflow-decision-record.md](dataflow-decision-record.md) for the full
Dataflow architectural assessment, trigger conditions for implementation, and explicit
non-claims.

---

## 12. Explicit Non-Claims

The following are not claimed by this project as of 2026-05-22. These non-claims are
explicit and binding.

- **No automated production replay service is implemented.** All replay and backfill
  operations require manual, operator-initiated execution. No Cloud Workflows, Cloud
  Composer, or other orchestration system automates recovery.
- **No DLQ production consumer is implemented.** The DLQ deduplication strategy is
  documented in `docs/dlq-deduplication-strategy.md` but no consumer code has been
  written, deployed, or tested.
- **No Pub/Sub seek/replay validation has been executed.** The seek API exists and is
  documented as a future recovery option, but no seek operation has been performed
  against any production or test Pub/Sub subscription in this project.
- **No exactly-once production semantics are claimed.** The platform achieves
  deduplicated at-least-once semantics via `ON CONFLICT` at Cloud SQL and MERGE at
  BigQuery. Transport-layer exactly-once is not claimed.
- **No Dataflow replay path is implemented.** Dataflow is not part of any current replay
  or backfill path. See `docs/dataflow-decision-record.md`.
- **No multi-day recovery drill has been proven.** All validated recovery operations are
  bounded to single execution windows during controlled evidence-collection sessions.
- **No staging/prod isolated replay has been proven.** All infrastructure is in a single
  GCP project. No staging environment exists.
- **No disaster recovery restore has been validated.** No Cloud SQL backup restore, no
  BigQuery dataset restore from backup, and no DR RTO/RPO has been measured.
- **No automated staleness detection exists for dbt layers.** There is no Cloud Monitoring
  alert or metric that detects when silver or gold dbt models are stale.
- **No automated detection of failed append windows exists.** A missed BigQuery append
  job execution is not currently detected by any alert; it requires manual inspection.
- **No cross-layer row-count drift metric exists.** There is no automated comparison
  between Cloud SQL bronze row count and BigQuery market_events_raw row count.
- **dbt `--full-refresh` against Cloud SQL live is not validated.** Only incremental
  execution has been proven against live Cloud SQL.
- **Cloud SQL backup configuration is not documented.** Automated backup behaviour and
  retention are not verified in this evidence set.

---

## 13. Safe Recruitment Positioning

### Recruiter-Facing Paragraph

I designed and documented a rigorous replay and backfill strategy for a GCP data platform
validated at 50,000 events and 10 events/sec sustained throughput. The strategy identifies
Cloud SQL as the operational source of truth, documents idempotent BigQuery MERGE and dbt
incremental refresh paths for downstream reconstruction, and provides a DLQ deduplication
design for poison-message recovery. All paths are evidenced where they have been executed.
I do not claim an automated production replay service; I claim documented strategy with
evidence-backed building blocks and explicit runbooks for operational execution.

### Technical Interview Paragraph

The replay strategy is built on three proven mechanisms: Cloud SQL `ON CONFLICT(event_id)
DO NOTHING` for idempotent bronze layer writes (validated across 50,000 events with 0
duplicates), cursor-based BigQuery MERGE for analytical layer reconstruction (idempotent
re-run validated with expected +3 delta and confirmed 0 duplicate_count on second run),
and dbt delete+insert incremental strategy with `unique_key` for transformation layer
refresh (Cloud SQL live execution validated with dbt run PASS=2 and dbt test PASS=22).
The DLQ deduplication strategy uses a key hierarchy: event_id for valid payloads,
payload_sha256 for malformed payloads, with messageId explicitly excluded because one
malformed publish produced 12 distinct DLQ entries with different messageIds. The source
of truth is Cloud SQL; BigQuery is an analytical sink. Pub/Sub retention provides a
time-bounded recovery window for un-processed events only.

### Caveat Paragraph for Senior Reviewers

The following limitations are acknowledged: No automated recovery service is implemented;
all operations are manual. Pub/Sub seek/replay has not been validated. dbt `--full-refresh`
has not been executed against live Cloud SQL. There is no cross-layer row-count drift
metric, no automated detection of failed append windows, and no DR restore test. The
runbooks in Section 8 are skeletons requiring a dedicated implementation branch
(`feat/bigquery-recovery-runbook-validation`) before they can be considered operationally
validated. This document closes the strategy gap; it does not close the implementation gap.

---

## 14. Final Recommendation

### This Branch Closes the Replay/Backfill Strategy Gap

`docs/replay-backfill-strategy` documents the operational source of truth decision,
all current proven replay paths, the idempotency and deduplication architecture, a
failure mode matrix, runbook skeletons, production-likeness assessment, and explicit
non-claims. The strategy gap identified in `docs/dataflow-decision-record.md`,
`docs/market-value-gap-audit-2026-2027.md`, and `docs/gap-closure-snapshot-after-steady-state.md`
is closed at the documentation level.

### Next Branch: `docs/dbt-observability-metrics-plan`

The next branch should be `docs/dbt-observability-metrics-plan`. This branch:
- Defines dbt-specific Cloud Monitoring metrics (run duration, model row counts, test pass rates).
- Closes the last significant gap in the analytics engineering story.
- Is docs-only; requires no Cloud SQL start, no Terraform apply, no cloud execution.
- Directly addresses the dbt model staleness detection gap identified in Section 9 of
  this document.

### Later Branches (Prioritized)

The following implementation branches are recommended after `docs/dbt-observability-metrics-plan`:

1. **`feat/bigquery-recovery-runbook-validation`** -- Execute and validate runbooks R-01
   through R-07 in a bounded test scenario. Collect row-count evidence for a simulated
   truncation and recovery cycle.

2. **`feat/dlq-consumer-implementation`** -- Implement the deduplication-aware DLQ
   consumer defined in `docs/dlq-deduplication-strategy.md`. Requires Cloud SQL for
   the deduplication store or a BigQuery table alternative.

3. **`feat/pubsub-seek-replay-validation`** -- Define and validate the Pub/Sub seek/replay
   path. Execute a bounded seek operation and confirm re-delivery and deduplication.

4. **`docs/cloud-sql-backup-restore-plan`** -- Document Cloud SQL backup configuration,
   retention policy, and a bounded restore drill plan.

### Do Not Implement Dataflow Yet

Dataflow implementation is deferred pending trigger conditions defined in
`docs/dataflow-decision-record.md`. The replay/backfill strategy is valid and complete
at the current platform scale without Dataflow. Dataflow would improve late-event
handling and event-time windowing in future; it is not a prerequisite for operational
replay capability.

---

### Critical Corrections Before Implementation

The following items must be verified or corrected in any future implementation branch
before any runbook from Section 8 is executed. They are documented here to prevent
errors propagating into live operations.

| Item | Required Action |
|---|---|
| Staging table name | Confirm the correct staging table is `rtdp_analytics.market_events_raw_staging`. Verify against the current Terraform resource definition and BigQuery footprint before executing any append or backfill runbook. The name `market_events_staging` must not be used. |
| Pub/Sub retention duration | Read the actual retention configuration from the `market-events-raw` topic and the `market-events-raw-worker-push` subscription via `gcloud pubsub topics describe` and `gcloud pubsub subscriptions describe` before designing or executing any seek/replay operation. No specific retention duration is claimed in this document. |
| Runbook command approval | No command block in Section 8 is approved for direct execution. Each runbook must be converted into a validated execution procedure in a dedicated implementation branch with its own preflight checks, evidence document, and post-execution validation before use in any live or simulated environment. |

---

## Evidence Links

| Document | Relevance |
|---|---|
| [docs/bigquery-bounded-backfill-evidence.md](bigquery-bounded-backfill-evidence.md) | Bounded backfill: 6,104 rows Cloud SQL to BigQuery |
| [docs/bigquery-incremental-append-evidence.md](bigquery-incremental-append-evidence.md) | Cursor-based MERGE; idempotent second run proven |
| [docs/bigquery-append-scheduler-proof-evidence.md](bigquery-append-scheduler-proof-evidence.md) | Scheduler proof: +3 exact rows; 0 duplicate_count |
| [docs/dbt-cloud-sql-incremental-execution-proof.md](dbt-cloud-sql-incremental-execution-proof.md) | Cloud SQL live incremental dbt execution; PASS=2; test PASS=22 |
| [docs/dlq-malformed-message-validation-evidence.md](dlq-malformed-message-validation-evidence.md) | DLQ routing validated; 12 entries for 1 malformed publish |
| [docs/dlq-deduplication-strategy.md](dlq-deduplication-strategy.md) | DLQ deduplication key hierarchy and consumer design |
| [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md) | 50,000-event bounded load test; 0 duplicate event_ids |
| [docs/steady-state-10eps-30min-cloud-validation-evidence.md](steady-state-10eps-30min-cloud-validation-evidence.md) | 18,000-event sustained test; 0 missing worker events |
| [docs/dataflow-decision-record.md](dataflow-decision-record.md) | Dataflow deferred; trigger conditions defined |
| [docs/bigquery-quality-incident-notification-delivery-proof.md](bigquery-quality-incident-notification-delivery-proof.md) | Cloud Monitoring alerting loop validated end-to-end |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | Production-light SLOs; incident severity levels |
| [docs/gap-closure-snapshot-after-steady-state.md](gap-closure-snapshot-after-steady-state.md) | Pre-branch gap state; replay/backfill identified as open |
| [docs/market-value-gap-audit-2026-2027.md](market-value-gap-audit-2026-2027.md) | Gap prioritization; replay/backfill identified as near-term priority |
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog |
