# Load-Test Local Sample Evidence

## Status

**LOCAL-ONLY EVIDENCE — PRE-PUBLISH ONLY**

This document records the output of a deterministic dry-run generator and local JSONL
validator. No Pub/Sub messages were published. No Cloud SQL instance was started. No GCP
resources were mutated. This is pre-publish evidence only and does not constitute throughput
validation.

---

## Purpose

The [load-test plan](load-test-plan.md) defines a controlled protocol for publishing 100 / 1 000
/ 5 000 events to Pub/Sub and validating worker processing end-to-end. Before any live
publishing run, the plan requires evidence that:

1. The deterministic generator (`scripts/generate_load_test_events.py`) produces correctly
   sequenced, schema-valid events at the planned size and prefix.
2. The local validator (`scripts/validate_load_test_events.py`) passes against that output
   using the worker's `validate_event` contract.

This document provides that pre-publish evidence for the 100-event smoke-scale size using
prefix timestamp `20260601120000`.

---

## Files Produced

| File | Description |
|---|---|
| `docs/evidence/load-test-local-sample/events-100.jsonl` | 100-event deterministic JSONL sample |
| `docs/evidence/load-test-local-sample/report-100.json` | Validator JSON report |

---

## Commands Used

All commands are local-only. No GCP authentication, network calls, Pub/Sub publishing, or Cloud
SQL access occurred.

```bash
# 1. Generate 100-event JSONL sample
uv run python scripts/generate_load_test_events.py \
  --size 100 \
  --prefix-timestamp 20260601120000 \
  --output docs/evidence/load-test-local-sample/events-100.jsonl

# 2. Validate sample and write report
uv run python scripts/validate_load_test_events.py \
  --input docs/evidence/load-test-local-sample/events-100.jsonl \
  --size 100 \
  --prefix-timestamp 20260601120000 \
  --report-output docs/evidence/load-test-local-sample/report-100.json

# 3. Read-only Cloud SQL state check (no mutation)
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"
```

---

## Validation Summary

Report file: `docs/evidence/load-test-local-sample/report-100.json`

| Field | Value |
|---|---|
| `status` | `ok` |
| `observed_count` | `100` |
| `expected_size` | `100` |
| `unique_event_ids` | `100` |
| `first_event_id` | `loadtest-100-20260601120000-00001` |
| `last_event_id` | `loadtest-100-20260601120000-00100` |
| `symbols` | `["BTCUSDT", "ETHUSDT", "SOLUSDT"]` |
| `worker_contract_validation` | `passed` |
| `errors` | `[]` |

---

## GCP State Confirmation

Cloud SQL state at time of evidence capture (read-only query, no mutation):

```
NEVER   STOPPED
```

---

## Explicit Constraints

- **No Pub/Sub messages were published.** The generator and validator are local-only tools.
  No message was sent to any Pub/Sub topic.
- **No Cloud SQL instance was started.** The `rtdp-postgres` instance was confirmed
  `NEVER / STOPPED` and was not modified.
- **No GCP resources were mutated.** All commands were either local file operations or a
  single read-only `gcloud sql instances describe` query.
- **This is pre-publish evidence only.** A passing validator report confirms that the generated
  events are schema-valid and correctly sequenced. It does not validate throughput, worker
  processing, Pub/Sub delivery, or Cloud SQL ingestion. Those steps require live publishing
  against the deployed pipeline as defined in [docs/load-test-plan.md](load-test-plan.md).

---

## Relationship to Load-Test Plan

[docs/load-test-plan.md](load-test-plan.md) — section 5 ("Producer Strategy") — defines the
dry-run generator and local validator as the pre-publish verification step. This document
provides the versioned evidence artifact for that step at the 100-event smoke-scale size. The
live execution phases (Pub/Sub publish, worker processing, Cloud SQL ingestion, silver refresh,
API readback, Cloud Monitoring validation) remain as defined in the plan and have not been
executed.
