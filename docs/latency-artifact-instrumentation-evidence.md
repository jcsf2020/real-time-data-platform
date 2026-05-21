# Latency Artifact Instrumentation Evidence

## Status

| Field | State |
|---|---|
| Document type | LOCAL VALIDATION |
| New GCP workload execution | No |
| New events published | No |
| Cloud SQL started | No |
| Schema migration executed | No |
| Terraform apply executed | No |
| p50/p95/p99 cloud latency validated | NOT YET PROVEN |

LOCAL VALIDATION -- latency artifact/log instrumentation implemented; cloud latency percentiles NOT YET PROVEN.

This document records local unit-test evidence for Option B latency instrumentation as defined in
[docs/latency-instrumentation-plan.md](latency-instrumentation-plan.md). No GCP workload was executed.
No events were published. No Cloud SQL was started. No schema migration was run. No Terraform apply
was executed. No p50/p95/p99 cloud latency claim is made here.

---

## What Was Implemented

### Option B: Artifact/Log-Based Latency Instrumentation

This implements Option B from `docs/latency-instrumentation-plan.md`. No Cloud SQL schema migration
is required. Timestamps are captured in producer JSONL artifacts and in worker structured logs.

---

### Publisher Changes (`apps/pubsub-publisher/src/rtdp_pubsub_publisher/__init__.py`)

- Added `utc_now_iso()` helper returning an ISO 8601 UTC string.
- Extended `serialize_event(event, extra_fields=None)` to optionally merge extra fields into the
  serialized JSON payload. Default behaviour (no `extra_fields`) is fully backward compatible.
- Extended `publish_event(publisher, project_id, topic_name, event, extra_fields=None)` to pass
  `extra_fields` through to serialization. Existing callers are unaffected.
- Added CLI arguments:
  - `--include-latency-metadata`: if set, computes `producer_created_at` before publish and
    includes it in the payload via `extra_fields`.
  - `--latency-artifact-path`: if set, appends one JSONL row to the specified file after each
    successful publish. The row contains:
    - `status`
    - `event_id`
    - `message_id`
    - `symbol`
    - `topic`
    - `producer_created_at` (null if `--include-latency-metadata` was not set)
    - `pubsub_publish_ack_at`

### Worker Changes (`apps/pubsub-worker/src/rtdp_pubsub_worker/__init__.py`)

Added `_diff_ms(start_iso, end_iso)` helper to compute millisecond differences between ISO 8601
timestamps.

Extended `process_message` to capture and emit stage timestamps in every structured log line:

| Timestamp | When captured |
|---|---|
| `worker_received_at` | Immediately on entry, before any processing |
| `worker_decoded_at` | After `decode_message` succeeds |
| `worker_validated_at` | After `validate_event` succeeds |
| `db_insert_started_at` | Immediately before `insert_bronze_event` |
| `db_insert_completed_at` | Immediately after `insert_bronze_event` returns |
| `worker_completed_at` | At the end of each path (success and error) |

Also included when available from raw payload:

- `producer_created_at` (extracted from `payload.get("producer_created_at")`)

Derived metrics emitted on the success log line when timestamps are present:

| Metric | Formula |
|---|---|
| `validation_latency_ms` | `worker_validated_at - worker_received_at` |
| `db_write_latency_ms` | `db_insert_completed_at - db_insert_started_at` |
| `worker_processing_latency_ms` | `worker_completed_at - worker_received_at` |
| `end_to_end_latency_ms` | `worker_completed_at - producer_created_at` (only if `producer_created_at` is parseable) |

On error log lines, only the timestamps that were reached before failure are included.

Database schema, `_INSERT_SQL`, and `process_message` return contract are unchanged.

---

## Local Unit-Test Evidence

All tests run against mocked dependencies. No GCP connection is required.

### Publisher Tests (`tests/test_pubsub_publisher.py`)

- `serialize_event(event)` is backward compatible: returns identical bytes to `event.model_dump_json().encode("utf-8")`.
- `serialize_event(event, extra_fields={"producer_created_at": "..."})` merges the extra field into the JSON payload.
- `publish_event` default call (no `extra_fields`) remains backward compatible.
- `publish_event` with `extra_fields` includes the extra field in the published payload.
- Latency artifact test: `main` with `--latency-artifact-path` and `--include-latency-metadata` writes exactly one JSONL row containing `status`, `event_id`, `message_id`, `symbol`, `topic`, `producer_created_at`, `pubsub_publish_ack_at`.
- Latency artifact without `--include-latency-metadata`: row is written with `producer_created_at: null`.
- No artifact written when `--latency-artifact-path` is not set.
- CLI: `--latency-artifact-path` and `--include-latency-metadata` parse correctly; both default to off.

### Worker Tests (`tests/test_pubsub_worker.py`)

- Valid message success log includes all six stage timestamps and all three derived latency metrics.
- Valid message with `producer_created_at` in payload includes `end_to_end_latency_ms`.
- Valid message without `producer_created_at` does not include `end_to_end_latency_ms`.
- Invalid JSON error log includes `worker_received_at` and `worker_completed_at`.
- Validation failure error log includes `worker_received_at`, `worker_decoded_at`, `worker_completed_at`.
- DB failure error log includes `db_insert_started_at` and `worker_completed_at`.
- `process_message` return dict is unchanged: `{"status": "ok", "event_id": ...}` on success, `{"status": "error", "error": ...}` on failure.

---

## Explicit Non-Claims

- No GCP workload was executed.
- No events were published.
- No Cloud SQL was started.
- No schema migration was run.
- No Terraform apply was executed.
- No p50/p95/p99 cloud latency claim is made.
- This is not a claim of sustained production throughput.
- Dataflow is not implemented.

---

## Next Step

Small controlled cloud validation: publish approximately 100 events with
`--include-latency-metadata` and `--latency-artifact-path`, collect worker structured logs,
join by `event_id`, and compute latency percentiles. This should be done in a separate
execution branch.
