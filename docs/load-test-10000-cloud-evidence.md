# Cloud Load Test -- 10,000 Events -- Evidence

**Status:** VALIDATED -- 10,000-EVENT CLOUD LOAD TEST PASSED
**Branch:** `exec/cloud-load-test-10000-evidence`
**Date:** 2026-05-20
**Project:** `project-42987e01-2123-446b-ac7`
**Region:** `europe-west1`

---

## Summary

This evidence proves a controlled 10,000-event cloud load test through the current
Pub/Sub -> Cloud Run worker -> Cloud SQL path.

The run was bounded, deterministic, and evidence-backed. It does not claim sustained
production throughput and does not implement Dataflow.

---

## Test Inputs

| Field | Value |
|---|---|
| Event count | 10,000 |
| Prefix timestamp | `20260519215829` |
| Event prefix | `loadtest-10000-20260519215829-` |
| Event file | `docs/evidence/load-test-10000-cloud/events-10000.jsonl` |
| Local validation report | `docs/evidence/load-test-10000-cloud/local-validation-report-10000.json` |
| Publish report | `docs/evidence/load-test-10000-cloud/publish-report-10000.json` |
| Cloud SQL validation report | `docs/evidence/load-test-10000-cloud/cloudsql-validation-report-10000.json` |
| Monitoring metrics report | `docs/evidence/load-test-10000-cloud/monitoring-metrics-report-10000.json` |

---

## Preconditions

| Check | Result |
|---|---|
| Cloud SQL initial state | `STOPPED / NEVER` |
| Schedulers initial state | `PAUSED` |
| Pub/Sub topic | `market-events-raw` present |
| Push subscription | `market-events-raw-worker-push` active |
| DLQ topic | `market-events-raw-dlq` present |
| DLQ subscriptions | `Listed 0 items.` |
| Cloud Run worker | `rtdp-pubsub-worker` Ready |
| Terraform baseline | `PLAN_EXIT=0` |

---

## Code Preparation

The load-test generator and validator were extended to allow `10000`.

| Commit | Purpose |
|---|---|
| `0a73168` | Allow 10000 event load test generation |
| `6dc3e66` | Add local 10000 event load test artifacts |

Validation after the script change:

| Check | Result |
|---|---|
| Targeted generator/validator tests | `34 passed` |
| Full test suite | `240 passed` |
| Ruff | Clean |
| Terraform fmt | Clean |
| Terraform validate | Success |
| Terraform plan | `PLAN_EXIT=0` |

---

## API Readiness Gate

Before publishing, Cloud SQL was started temporarily and API readiness was checked.

| Check | Result |
|---|---|
| Cloud SQL active state | `RUNNABLE / ALWAYS` |
| API readiness HTTP code | `200` |
| API readiness body | `{"status":"ready","service":"rtdp-api","database":"reachable"}` |

The prior API readiness issue was fixed separately in PR #176 by normalizing `DATABASE_URL`
values and rotating the latest secret version to remove a trailing newline. API and worker
revisions were refreshed before this load-test publish.

---

## Publish Evidence

| Field | Value |
|---|---|
| Publish start time | `2026-05-20T05:50:53Z` |
| Publish end time | `2026-05-20T05:59:08Z` |
| Published total | `10000` |
| Unique Pub/Sub message IDs | `10000` |
| Publish error count | `0` |
| Rate limit | `50 msg/s` |
| Elapsed seconds | `493.981` |
| Publish report status | `ok` |

---

## Worker Processing Evidence

Structured worker logs confirmed all 10,000 prefixed events were processed successfully.

| Metric | Result |
|---|---|
| Worker OK unique event_id count | `10000` |
| Worker error count | `0` |

Sample tail logs confirmed the last events were processed:

| Event ID | Status |
|---|---|
| `loadtest-10000-20260519215829-10000` | `ok` |
| `loadtest-10000-20260519215829-09999` | `ok` |
| `loadtest-10000-20260519215829-09998` | `ok` |
| `loadtest-10000-20260519215829-09997` | `ok` |
| `loadtest-10000-20260519215829-09996` | `ok` |

---

## Cloud Monitoring Metrics Evidence

Cloud Monitoring logs-based metrics matched the exact worker log count.

| Metric | Result |
|---|---|
| Query start | `2026-05-20T05:50:00Z` |
| Query end | `2026-05-20T06:05:58Z` |
| `worker_message_processed_count` total | `10000` |
| `worker_message_processed_count` series | `1` |
| `worker_message_processed_count` points | `12` |
| `worker_message_error_count` total | `0` |
| `worker_message_error_count` series | `0` |
| `worker_message_error_count` points | `0` |

Structured worker logs remain the authoritative proof for exact event-level processing.
In this run, Cloud Monitoring also matched the exact 10,000-event total.

---

## DLQ Evidence

| Check | Result |
|---|---|
| DLQ topic subscriptions | `Listed 0 items.` |

No DLQ subscriptions were present and no DLQ drain was required.

---

## Cloud SQL Evidence

Cloud SQL was queried via local Cloud SQL Auth Proxy without printing secrets.

| Check | Result |
|---|---|
| Prefix row count | `10000` |
| Duplicate event_id count | `0` |
| Total `bronze.market_events` rows | `16120` |
| Cloud SQL validation report status | `ok` |

This confirms the full 10,000-event prefix reached the bronze table exactly once per
`event_id`.

---

## Final Safety State

Cloud SQL was restored immediately after evidence capture.

| Check | Result |
|---|---|
| Cloud SQL final state | `STOPPED / NEVER` |
| Schedulers final state | `PAUSED` |
| Terraform post-run drift | `PLAN_EXIT=0` |

---

## Acceptance Criteria

| Criterion | Result |
|---|---|
| 10,000 events generated | PASS |
| Local validation passes | PASS |
| Publish command succeeds | PASS |
| Worker processed count reaches 10,000 | PASS |
| Worker error count remains 0 | PASS |
| DLQ remains empty / unused | PASS |
| Cloud SQL row count includes 10,000 prefixed rows | PASS |
| Duplicate event_id count remains 0 | PASS |
| Cloud SQL final state is STOPPED / NEVER | PASS |
| Schedulers final state is PAUSED | PASS |
| No secrets printed | PASS |
| Evidence artifacts captured | PASS |

---

## Explicit Non-Claims

| Claim | Status |
|---|---|
| Sustained production throughput | NOT CLAIMED -- this was a bounded 10,000-event run |
| 50,000 / 100,000 / 500,000 events | NOT CLAIMED |
| Dataflow implemented | NOT IMPLEMENTED |
| Multi-worker scaling proven | NOT CLAIMED |
| Terraform apply executed | NOT EXECUTED |
| Scheduler-triggered load run | NOT CLAIMED -- manual controlled publish was used |

---

## B2B Relevance

This closes the immediate "above 5,000 events" throughput gap. A 10,000-event run is not
enterprise scale, but it proves the platform is no longer toy-only and creates a defensible
progression from 100 -> 1,000 -> 5,000 -> 10,000 events.

The evidence is useful in interviews because it demonstrates:

- controlled cloud load execution;
- Pub/Sub publish validation;
- Cloud Run worker processing;
- Cloud SQL write-path validation;
- idempotency via duplicate `event_id` check;
- Cloud Monitoring metric correlation;
- DLQ health;
- cost-control discipline through Cloud SQL restoration;
- evidence-first non-claims.

Dataflow remains deferred until the current stack has a stronger measured baseline, preferably
after a 50,000-event plan and execution attempt.
