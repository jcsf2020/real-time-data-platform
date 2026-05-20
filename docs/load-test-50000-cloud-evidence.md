# Cloud Load Test -- 50,000 Events -- Evidence

**Status:** VALIDATED -- 50,000-EVENT CLOUD LOAD TEST PASSED
**Branch:** `exec/cloud-load-test-50000-evidence`
**Date:** 2026-05-20
**Project:** `project-42987e01-2123-446b-ac7`
**Region:** `europe-west1`

---

## Summary

This evidence proves a controlled 50,000-event cloud load test through the current
Pub/Sub -> Cloud Run worker -> Cloud SQL path.

The run was bounded, deterministic, and evidence-backed. It does not claim sustained
production throughput and does not implement Dataflow.

---

## Test Inputs

| Field | Value |
|---|---|
| Event count | 50,000 |
| Prefix timestamp | `20260520071943` |
| Event prefix | `loadtest-50000-20260520071943-` |
| Event file | `docs/evidence/load-test-50000-cloud/events-50000.jsonl` |
| Local validation report | `docs/evidence/load-test-50000-cloud/local-validation-report-50000.json` |
| Publish report | `docs/evidence/load-test-50000-cloud/publish-report-50000.json` |
| Cloud SQL validation report | `docs/evidence/load-test-50000-cloud/cloudsql-validation-report-50000.json` |
| Monitoring metrics report | `docs/evidence/load-test-50000-cloud/monitoring-metrics-report-50000.json` |

---

## Code Preparation

The load-test generator and validator were extended to allow `50000`.

| Commit | Purpose |
|---|---|
| `bf427aa` | Allow 50000 event load test generation |
| `5c5d8d3` | Add local 50000 event load test artifacts |

Validation after the script change:

| Check | Result |
|---|---|
| Targeted generator/validator tests | `35 passed` |
| Full test suite | `241 passed` |
| Ruff | Clean |
| Terraform fmt | Clean |
| Terraform validate | Success |
| Terraform plan baseline | `PLAN_EXIT=0` |

---

## Local Artifact Validation

| Check | Result |
|---|---|
| Generated event count | `50,000` |
| First event_id | `loadtest-50000-20260520071943-00001` |
| Last event_id | `loadtest-50000-20260520071943-50000` |
| Unique event IDs | `50,000` |
| Worker contract validation | `passed` |
| Local validation status | `ok` |

---

## API Readiness Gate

Before publishing, Cloud SQL was started temporarily and API readiness was checked.

| Check | Result |
|---|---|
| Cloud SQL active state | `RUNNABLE / ALWAYS` |
| API readiness HTTP code | `200` |
| API readiness body | `{"status":"ready","service":"rtdp-api","database":"reachable"}` |
| Schedulers | `PAUSED` |

---

## Pub/Sub Publish Result

| Metric | Value |
|---|---:|
| Expected events | 50,000 |
| Published total | 50,000 |
| Unique message IDs | 50,000 |
| Publish error count | 0 |
| Publish status | `ok` |
| Rate limit target | 50 msg/s |
| Started at UTC | `2026-05-20T07:28:08Z` |
| Ended at UTC | `2026-05-20T09:14:40Z` |
| Elapsed seconds | `3420.294` |

The effective publish rate was lower than the configured target because the script waits
for each Pub/Sub publish future to resolve before sending the next event. This was
intentional and conservative.

---

## Worker Processing Evidence

Structured Cloud Run worker logs were queried by event prefix.

| Check | Result |
|---|---:|
| Worker OK unique event_id count | 50,000 |
| Worker error count | 0 |
| Sample final event | `loadtest-50000-20260520071943-50000` |
| Final event status | `ok` |

---

## Cloud SQL Readback Evidence

Cloud SQL was queried through local Cloud SQL Auth Proxy without printing secrets.

| Check | Result |
|---|---:|
| Prefix row count | 50,000 |
| Duplicate event_id count | 0 |
| Total bronze.market_events rows after run | 66,120 |
| Validation status | `ok` |

---

## Cloud Monitoring Metrics Evidence

Cloud Monitoring was queried through the Monitoring REST API.

| Metric | Value |
|---|---:|
| worker_message_processed_count_total | 50,002 |
| worker_message_processed_count_points | 75 |
| worker_message_processed_count_series | 1 |
| worker_message_error_count_total | 0 |
| worker_message_error_count_points | 0 |
| worker_message_error_count_series | 0 |
| Metrics report status | `ok` |

Note: structured worker logs and Cloud SQL row counts are authoritative for the exact
50,000-event proof. Cloud Monitoring DELTA windows may not align exactly with publish
window boundaries; the metric showing 50,002 does not invalidate the run.

---

## Final Safety State

| Check | Result |
|---|---|
| Cloud SQL final state | `STOPPED / NEVER` |
| Schedulers final state | `PAUSED` |
| Terraform apply | Not executed |
| Dataflow | Not implemented |

---

## Non-Claims

This evidence does not claim:

- sustained production throughput;
- Dataflow implementation;
- long-running autoscaling stability;
- exactly-once semantics beyond the observed no-duplicate event_id result;
- permanent production readiness.

It proves that the current Pub/Sub -> Cloud Run worker -> Cloud SQL path processed a
bounded 50,000-event run successfully, with no publish errors, no worker errors, no
duplicate event IDs, and a clean final safe state.

---

## Interpretation

The current stack has now been validated at 50,000 events. This strengthens the evidence
base for bounded burst workloads.

Dataflow remains a future architecture option, but the justification should now be based
on higher-scale limits, latency requirements, replay semantics, or sustained throughput
requirements rather than lack of current-stack evidence.
