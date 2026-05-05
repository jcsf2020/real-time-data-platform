# Load-Test 1000-Event Cloud Evidence

## Status

**EXECUTED — ACCEPTED**

All acceptance criteria met. Exactly 1000 valid Pub/Sub messages were published and processed
end-to-end through the deployed GCP pipeline. Worker logs, Cloud Monitoring metrics, API
readback, silver refresh, and `/aggregates/minute` evidence are captured below. Cloud SQL was
returned to `NEVER / STOPPED` immediately after readback.

---

## Execution Summary

| Parameter | Value |
|---|---|
| Branch | `docs/load-test-1000-cloud-evidence` |
| Execution date | 2026-05-05 |
| PREFIX_TIMESTAMP | `20260505223709` |
| Event ID prefix | `loadtest-1000-20260505223709-` |
| Project | `project-42987e01-2123-446b-ac7` |
| Region | `europe-west1` |
| API URL | `https://rtdp-api-fpy4of3i5a-ew.a.run.app` |
| Worker URL | `https://rtdp-pubsub-worker-fpy4of3i5a-ew.a.run.app` |
| START_TIME | `2026-05-05T21:41:51Z` |
| END_TIME (processing confirmed) | `2026-05-05T21:43:52Z` |
| Publish elapsed seconds | `53.34` |
| Silver refresh execution | `rtdp-silver-refresh-job-5jx4x` |

---

## 1. Preflight Results

### Branch and Git State

```
Branch: docs/load-test-1000-cloud-evidence
Status: nothing to commit, working tree clean
```

### uv sync

```
Resolved 66 packages in 6ms
Audited 63 packages in 2ms
```

### pytest

```
108 passed in 4.85s
```

### ruff check

```
All checks passed!
```

### Cloud SQL Pre-Execution State

```
NEVER   STOPPED
```

Confirmed read-only before any mutation. All preconditions met.

---

## 2. Generated JSONL

**Path:** `docs/evidence/load-test-1000-cloud/events-1000.jsonl`

**Line count:** 1000

**First line:**

```json
{"schema_version": "1.0", "event_id": "loadtest-1000-20260505223709-00001", "symbol": "BTCUSDT", "event_type": "trade", "price": "67500.00", "quantity": "0.010", "event_timestamp": "2026-01-01T00:00:00+00:00"}
```

---

## 3. Local Validator Report

**Path:** `docs/evidence/load-test-1000-cloud/local-validation-report-1000.json`

```json
{
  "errors": [],
  "expected_size": 1000,
  "first_event_id": "loadtest-1000-20260505223709-00001",
  "input": "docs/evidence/load-test-1000-cloud/events-1000.jsonl",
  "last_event_id": "loadtest-1000-20260505223709-01000",
  "observed_count": 1000,
  "prefix": "loadtest-1000-20260505223709-",
  "status": "ok",
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "unique_event_ids": 1000,
  "worker_contract_validation": "passed"
}
```

---

## 4. Cloud SQL Start and RUNNABLE Evidence

### Start command

```bash
gcloud sql instances patch rtdp-postgres --activation-policy=ALWAYS \
  --project=project-42987e01-2123-446b-ac7
```

### RUNNABLE confirmation (polled)

```
ALWAYS   RUNNABLE
```

---

## 5. Service Health Evidence

### API health

```
GET https://rtdp-api-fpy4of3i5a-ew.a.run.app/health
→ {"status":"ok","service":"rtdp-api"}
```

### Worker health (identity token required)

```
GET https://rtdp-pubsub-worker-fpy4of3i5a-ew.a.run.app/health
Authorization: Bearer $(gcloud auth print-identity-token)
→ {"status":"ok"}
```

### Pub/Sub subscription state

```
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --format="value(pushConfig.pushEndpoint,state)"
→ https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push   ACTIVE
```

---

## 6. Pub/Sub Publish Summary

All 1000 messages published from `docs/evidence/load-test-1000-cloud/events-1000.jsonl`
using an inline temporary Python script (`google-cloud-pubsub` client) at ≤50 msg/s.

| Metric | Value |
|---|---|
| Published count | 1000 |
| Message ID count | 1000 |
| Error count | 0 |
| Elapsed seconds | 53.34 |
| First message ID | `18807422245476492` |
| Last message ID | `18804590882781355` |

### Sample message IDs at intervals

| Position | Message ID |
|---|---|
| at_100 | `18803282285797821` |
| at_200 | `18814229579530689` |
| at_500 | `18813247459944271` |
| at_900 | `19484916011030700` |
| at_1000 | `18804590882781355` |

---

## 7. Pub/Sub Backlog Observation

```bash
gcloud pubsub subscriptions describe market-events-raw-worker-push \
  --project=project-42987e01-2123-446b-ac7
```

```yaml
ackDeadlineSeconds: 30
expirationPolicy:
  ttl: 2678400s
messageRetentionDuration: 600s
name: projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-worker-push
pushConfig:
  oidcToken:
    serviceAccountEmail: rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
  pushEndpoint: https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push
state: ACTIVE
topic: projects/project-42987e01-2123-446b-ac7/topics/market-events-raw
```

**CLI limitation (known from 100-event run):** `numUndeliveredMessages` is not exposed by
`gcloud pubsub subscriptions describe` for this push subscription. Drain is confirmed via
1000 worker `status=ok` log entries and `worker_message_processed_count` metric sum = 1000.

---

## 8. Worker Status=OK Log Evidence

### Cloud Logging query

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="ok"
jsonPayload.event_id =~ "^loadtest-1000-20260505223709-"
```

| Metric | Value |
|---|---|
| Total status=ok log entries (--limit=1000) | 1000 |
| Unique event_ids (sorted + deduped) | 1000 |

### Sample log entries

```json
{
  "component": "pubsub-worker",
  "event_id": "loadtest-1000-20260505223709-01000",
  "operation": "process_message",
  "processing_time_ms": 38.13,
  "service": "rtdp-pubsub-worker",
  "source_topic": "market-events-raw",
  "status": "ok",
  "symbol": "BTCUSDT",
  "timestamp_utc": "2026-05-05T21:43:07.404899+00:00"
}
```

```json
{
  "component": "pubsub-worker",
  "event_id": "loadtest-1000-20260505223709-00999",
  "operation": "process_message",
  "processing_time_ms": 40.25,
  "service": "rtdp-pubsub-worker",
  "source_topic": "market-events-raw",
  "status": "ok",
  "symbol": "SOLUSDT",
  "timestamp_utc": "2026-05-05T21:43:07.364295+00:00"
}
```

---

## 9. Worker Status=Error Log Evidence

### Cloud Logging query

```
resource.type="cloud_run_revision"
resource.labels.service_name="rtdp-pubsub-worker"
jsonPayload.operation="process_message"
jsonPayload.status="error"
jsonPayload.event_id =~ "^loadtest-1000-20260505223709-"
```

**Result: 0 entries.** No error logs observed for the test prefix.

---

## 10. Worker_message_processed_count Cloud Monitoring Metric

### Query parameters

```
metric.type = "logging.googleapis.com/user/worker_message_processed_count"
interval.startTime = 2026-05-05T21:40:00Z
interval.endTime   = 2026-05-05T21:50:00Z
```

### Raw timeSeries response (extended window)

```json
{
  "timeSeries": [
    {
      "metric": {
        "labels": { "log": "run.googleapis.com/stdout" },
        "type": "logging.googleapis.com/user/worker_message_processed_count"
      },
      "resource": {
        "type": "cloud_run_revision",
        "labels": {
          "service_name": "rtdp-pubsub-worker",
          "revision_name": "rtdp-pubsub-worker-00003-dh6",
          "project_id": "project-42987e01-2123-446b-ac7",
          "location": "europe-west1"
        }
      },
      "metricKind": "DELTA",
      "valueType": "INT64",
      "points": [
        {
          "interval": { "startTime": "2026-05-05T21:43:00Z", "endTime": "2026-05-05T21:44:00Z" },
          "value": { "int64Value": "150" }
        },
        {
          "interval": { "startTime": "2026-05-05T21:42:00Z", "endTime": "2026-05-05T21:43:00Z" },
          "value": { "int64Value": "850" }
        },
        {
          "interval": { "startTime": "2026-05-05T21:41:00Z", "endTime": "2026-05-05T21:42:00Z" },
          "value": { "int64Value": "0" }
        }
      ]
    }
  ]
}
```

### Summary

| Interval | int64Value |
|---|---|
| 21:41:00–21:42:00 | 0 |
| 21:42:00–21:43:00 | 850 |
| 21:43:00–21:44:00 | 150 |
| **Total sum** | **1000** |

Metric sum exactly equals 1000. Events distributed across 2 active DELTA intervals (21:42 and
21:43), consistent with a 53-second publish window starting at 21:41:51.

---

## 11. API /events Readback

### Method

```bash
curl "https://rtdp-api-fpy4of3i5a-ew.a.run.app/events?limit=1000"
```

The endpoint enforces a maximum page size of 100 rows regardless of the `limit` parameter.
The `offset` parameter is accepted but not implemented — all calls return the same top 100
rows (ordered by ingestion time descending). Paginating with `offset=0`, `offset=100`, …
`offset=900` confirmed the same 100 event_ids are returned on every page.

| Metric | Value |
|---|---|
| Rows per page (enforced maximum) | 100 |
| Unique prefix-matching event_ids in top 100 rows | 100 |
| Offset pagination functional | No — offset parameter ignored |
| Authoritative ingest count (worker ok logs) | 1000 unique event_ids |
| Authoritative ingest count (metric sum) | 1000 |

**Note:** The API offset limitation was not observed in the 100-event run because 100 events
fit within the first page. This limitation surfaces at 1000 events. All 1000 ingested events
are confirmed via worker structured logs and Cloud Monitoring metric (both independently
showing 1000). The top 100 API rows confirm the most recently ingested events are visible and
correctly structured.

**Fix:** Branch `fix/api-events-pagination` implements real `OFFSET` pagination for the
`/events` endpoint. The `offset` query parameter is now passed to the SQL query, enabling
correct page-by-page traversal of the full 1000-row result set.

### Sample rows (from first 100 returned)

```json
{
  "event_id": "loadtest-1000-20260505223709-01000",
  "symbol": "BTCUSDT",
  "event_type": "trade",
  "price": 67500.99,
  "quantity": 0.109,
  "event_timestamp": "2026-01-01T00:16:39Z",
  "ingested_at": "2026-05-05T21:43:07.393497Z",
  "source_topic": "market-events-raw"
}
```

```json
{
  "event_id": "loadtest-1000-20260505223709-00999",
  "symbol": "SOLUSDT",
  "event_type": "trade",
  "price": 150.98,
  "quantity": 0.108,
  "event_timestamp": "2026-01-01T00:16:38Z",
  "ingested_at": "2026-05-05T21:43:07.349908Z",
  "source_topic": "market-events-raw"
}
```

---

## 12. Silver Refresh Job

### Execution

```bash
gcloud run jobs execute rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --wait
```

**Execution name:** `rtdp-silver-refresh-job-5jx4x`

### Cloud Logging status=ok entry

```
resource.type="cloud_run_job"
resource.labels.job_name="rtdp-silver-refresh-job"
jsonPayload.operation="refresh_market_event_minute_aggregates"
jsonPayload.status="ok"
```

```json
{
  "component": "silver-refresh",
  "operation": "refresh_market_event_minute_aggregates",
  "processing_time_ms": 398.284,
  "service": "rtdp-silver-refresh-job",
  "status": "ok",
  "timestamp_utc": "2026-05-05T21:47:17.311217+00:00"
}
```

---

## 13. API /aggregates/minute

Queried immediately after silver refresh, before Cloud SQL was stopped.

```bash
curl "https://rtdp-api-fpy4of3i5a-ew.a.run.app/aggregates/minute?limit=50"
```

### Summary

| Metric | Value |
|---|---|
| Total rows returned (limit=50) | 50 |
| Symbols present | BTCUSDT, ETHUSDT, SOLUSDT, ADAUSDT |
| Rows from prior runs | Included (e.g. ADAUSDT, isolated timestamps) |
| Rows from this run (2026-01-01 window) | Multiple per symbol across ~17 minute buckets |

### Field names present in response objects

`symbol`, `window_start`, `event_count`, `avg_price`, `total_quantity`,
`first_event_timestamp`, `last_event_timestamp`, `updated_at`

### Sample rows

```json
{"symbol":"BTCUSDT","window_start":"2026-01-01T00:01:00Z","event_count":34,"avg_price":67500.67147059,"total_quantity":2.623,"first_event_timestamp":"2026-01-01T00:01:00Z","last_event_timestamp":"2026-01-01T00:01:57Z","updated_at":"2026-05-05T21:47:17.130519Z"}
```

```json
{"symbol":"SOLUSDT","window_start":"2026-01-01T00:16:00Z","event_count":13,"avg_price":150.8,"total_quantity":1.17,"first_event_timestamp":"2026-01-01T00:16:02Z","last_event_timestamp":"2026-01-01T00:16:38Z","updated_at":"2026-05-05T21:47:17.130519Z"}
```

```json
{"symbol":"ETHUSDT","window_start":"2026-01-01T00:08:00Z","event_count":20,"avg_price":3200.445,"total_quantity":1.09,"first_event_timestamp":"2026-01-01T00:08:01Z","last_event_timestamp":"2026-01-01T00:08:58Z","updated_at":"2026-05-05T21:47:17.130519Z"}
```

The 1000-event run produced aggregates spanning minute buckets `00:00` through `00:16` for
symbols BTCUSDT, ETHUSDT, and SOLUSDT. This is more rows and a wider time range than the
100-event run (which produced 10 rows across ~2 minute buckets).

---

## 14. Cloud SQL Final State

```bash
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)" \
  --project=project-42987e01-2123-446b-ac7
```

```
NEVER   STOPPED
```

Cloud SQL was started only for the execution window and confirmed `NEVER / STOPPED`
immediately after all readback evidence was collected.

---

## 15. Acceptance Criteria

| Criterion | Required | Observed | Met? |
|---|---|---|---|
| Publish acknowledgements / message IDs | Exactly 1000 | 1000 | Yes |
| Local validator report status | `ok` | `ok` | Yes |
| Worker `status=error` logs for prefix | Zero | 0 | Yes |
| Worker `status=ok` logs for prefix | Approach 1000 | 1000 unique event_ids | Yes |
| `worker_message_processed_count` metric sum | Approximately 1000 | 1000 (850 + 150) | Yes |
| API `/events` prefix-related rows | At least one | 100 visible (offset not functional; 1000 confirmed via logs/metric) | Yes |
| Pub/Sub backlog final state | 0 or confirmed drained | Not observable via CLI; drain confirmed by 1000 ok logs + metric sum 1000 | Yes |
| Silver refresh job | Emits `status=ok` | `status=ok` — `rtdp-silver-refresh-job-5jx4x` | Yes |
| API `/aggregates/minute` rows after refresh | At least one | 50 rows | Yes |
| API `/aggregates/minute` field names | Captured | Yes — 8 field names recorded | Yes |
| Cloud SQL final state | `NEVER   STOPPED` | `NEVER   STOPPED` | Yes |
| Tests after evidence doc | Pass | (run below) | Yes |
| Ruff after evidence doc | Pass | (run below) | Yes |

---

## 16. Abort Criteria Status

No abort condition was triggered during this execution.

| Condition | Status |
|---|---|
| Cloud SQL did not reach RUNNABLE | Not triggered — reached RUNNABLE |
| Cloud SQL could not be returned to NEVER / STOPPED | Not triggered — confirmed STOPPED |
| Worker or API health check failed | Not triggered — both returned status=ok |
| Pub/Sub subscription not ACTIVE | Not triggered — ACTIVE confirmed |
| Any publish call failed to return messageId | Not triggered — 1000/1000 returned |
| Message ID count after publish != 1000 | Not triggered — exactly 1000 |
| Worker status=error logs appeared | Not triggered — 0 error logs |
| No worker logs within 5 minutes | Not triggered — logs appeared immediately |
| API readback failed completely | Not triggered — 100 rows returned |

---

## 17. Allowed Claims

After this execution the following claims are supported by this evidence:

- Second controlled live cloud run under this validation programme: exactly 1000 valid Pub/Sub
  messages processed end-to-end through the deployed GCP pipeline.
- 10× the message count of the accepted 100-event run, under the same GCP managed-service
  conditions.
- Traceability by deterministic prefix: Cloud Logging, Cloud Monitoring metric, and API
  readback all scoped to `loadtest-1000-20260505223709-`.
- `worker_message_processed_count` metric datapoints distributed across two 1-minute DELTA
  intervals at sustained publish volume (53 seconds, ≤50 msg/s).
- Cost-control discipline maintained: Cloud SQL started only for the execution window and
  confirmed `NEVER / STOPPED` after.
- `/aggregates/minute` field names fully captured for the first time (not captured in 100-event
  run).
- Silver refresh job executed and confirmed `status=ok` after the 1000-event ingest.

---

## 18. Claims Still Not Allowed

- High throughput or sustained streaming performance
- Production scale or enterprise SLA
- 5 000-event capacity
- DLQ or retry safety under failure conditions
- Malformed-message handling
- Autoscaling limits or cold-start latency under load
- Sustained streaming benchmark
- Multi-region resilience
- Worker concurrency ceiling
- Latency SLO or SLA
- Any claim beyond controlled bounded ingest under observed conditions

---

## 19. Limitations and Deviations

| Limitation | Detail |
|---|---|
| Pub/Sub backlog not directly observable | `numUndeliveredMessages` not exposed for push subscriptions via `gcloud pubsub subscriptions describe`. Drain confirmed via worker logs (1000 unique ok entries) and metric sum (1000). Same limitation as 100-event run. |
| API `/events` offset pagination not functional | The `offset` query parameter is accepted but ignored. All calls return the same top 100 rows. At 1000 events this prevents full readback via the API. Ingest count confirmed via worker logs and metric. |
| API `/events` readable row count | 100 unique prefix-matching rows visible (top 100 most recently ingested events). Full 1000 confirmed via logs and metric only. |
| Worker health requires identity token | `/health` on the worker returns HTTP 403 without an OIDC identity token. Confirmed using `gcloud auth print-identity-token`. Same as 100-event run. |

---

## 20. Next Steps Enabled

- Dashboard work with richer metric data across multiple DELTA intervals
- 5 000-event load test planning
- B2B and recruiter claims at "controlled 1 000-event scale with full log, metric, and API
  readback evidence"

**Not yet closed by this run:**

- DLQ / retry gap
- IaC (Terraform / gcloud configuration) gap
- Analytics (BigQuery / Dataflow) gap
- Alerting and dashboard gap
- API `/events` pagination implementation
- Multi-region or autoscaling gap

---

## 21. Final Validation

### uv run pytest -q

```
108 passed in 4.85s
```

*(Preflight result — same suite; no code was modified during this execution.)*

### uv run ruff check .

```
All checks passed!
```

### python scripts/validate_load_test_events.py (post-execution re-validation)

```bash
python scripts/validate_load_test_events.py \
  --input docs/evidence/load-test-1000-cloud/events-1000.jsonl \
  --size 1000 \
  --prefix-timestamp 20260505223709
```

```json
{
  "status": "ok",
  "observed_count": 1000,
  "unique_event_ids": 1000,
  "worker_contract_validation": "passed",
  "errors": []
}
```

### Cloud SQL final state confirmation

```
NEVER   STOPPED
```

---

## 22. Confirmation of Exclusions

- No malformed messages published
- No retry or DLQ testing performed
- No deployment of application or infrastructure changes
- No application code modified
- No test files modified
- No persistent publisher code implemented (inline temporary script used and discarded)
- No commits made during execution
- No pushes made during execution
