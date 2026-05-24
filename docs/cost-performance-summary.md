# Cost and Performance Summary

**Status:** SUMMARY -- cost drivers, resource sizing, and performance evidence

---

## Executive Summary

The Real-Time Data Platform has completed a sustained steady-state throughput validation
(10 events/sec for 30 minutes), a 50,000-event bounded cloud load test, and a
100-event latency instrumentation run with p50/p95/p99 end-to-end measurements.
All GCP resources are sized conservatively and operated under strict cost-control
discipline: Cloud SQL is kept STOPPED with activation policy NEVER except during
bounded validation windows; Cloud Schedulers are kept PAUSED by default.

No exact EUR, USD, or GBP cost is claimed in this document. No Cloud Billing
export was analyzed in this branch. No current GCP SKU pricing was embedded here.

---

## Cost-Control Position

| Practice | State |
|---|---|
| Cloud SQL rtdp-postgres activation policy | NEVER |
| Cloud SQL rtdp-postgres instance state | STOPPED |
| Cloud Scheduler rtdp-silver-refresh-scheduler | PAUSED |
| Cloud Scheduler rtdp-bigquery-append-scheduler | PAUSED |
| Cloud Run worker max scale | 1 (hard cap) |
| Cloud Run API max scale | 20 |
| Cloud Run jobs triggered by scheduler | PAUSED; manual dispatch only for proofs |
| Terraform apply | Not executed in this branch; historical applies are documented in their own evidence files |

Cloud SQL is the single largest always-on cost driver when running. Keeping it
STOPPED / NEVER means it incurs storage charges only (10 GB PD_HDD), not compute
charges, when idle.

---

## Current Resource Sizing Inputs

### Cloud SQL

| Field | Value |
|---|---|
| Instance | rtdp-postgres |
| Database version | POSTGRES_16 |
| Region | europe-west1 |
| Tier | db-custom-1-3840 (1 vCPU, 3840 MB RAM) |
| Availability | ZONAL |
| Storage | 10 GB PD_HDD |
| Activation policy | NEVER |
| Current state | STOPPED |

### Cloud Run Services

| Service | CPU | Memory | Concurrency | Max scale |
|---|---|---|---|---|
| rtdp-pubsub-worker | 1000m | 512 Mi | 1 | 1 |
| rtdp-api | 1 vCPU | 512 Mi | 80 | 20 |

The worker is capped at max scale 1 and concurrency 1, which bounds Cloud Run
compute cost to a single instance during active ingestion.

### Cloud Run Jobs

| Job | CPU | Memory | Timeout | Max retries |
|---|---|---|---|---|
| rtdp-bigquery-append-job | 1000m | 512 Mi | 600s | 0 |
| rtdp-dbt-refresh-job | 1000m | 512 Mi | 600s | 0 |
| rtdp-silver-refresh-job | 1000m | 512 Mi | 300s | 0 |

Jobs are invoked by schedulers that are PAUSED by default. Compute charges accrue
only during execution windows.

### BigQuery Table Footprint

| Table | Rows | Bytes | Partitioning | Clustering |
|---|---|---|---|---|
| market_events_raw | 6,120 | 777,222 | event_timestamp | symbol, event_type |
| market_events_raw_staging | 0 | 0 | -- | -- |
| market_event_minute_aggregates | 0 | 0 | window_start | symbol, event_type |
| market_event_daily_aggregates | 0 | 0 | event_date | symbol |

Total BigQuery storage at time of evidence is approximately 777 KB active. No BigQuery storage cost is claimed here because no Cloud Billing export or dated SKU pricing snapshot was analyzed in this branch.

---

## Performance Evidence Summary

All performance evidence is from bounded, deterministic cloud validation runs.
Maximum throughput is not claimed. Saturation point is not claimed.
Multi-day production stability is not claimed.
Exactly-once production semantics are not claimed.
Enterprise-grade latency SLO enforcement is not claimed.

### Bounded Load Test

| Metric | Value |
|---|---|
| Test type | 50,000-event bounded cloud load test |
| attempted_publishes | 50,000 |
| acknowledged_publishes | 50,000 |
| publish_errors | 0 |
| worker_ok_logs | 50,000 |
| worker_errors | 0 |
| duplicate_event_id_count | 0 |
| DLQ_subscriptions | 0 |

### Steady-State Throughput

| Metric | Value |
|---|---|
| Test type | Sustained cloud steady-state |
| Target rate | 10 events/sec for 30 minutes |
| attempted_publishes | 18,000 |
| acknowledged_publishes | 18,000 |
| publish_errors | 0 |
| observed_rate | 10.0 events/sec |
| matched_unique_worker_events | 18,000 |
| missing_worker_events | 0 |

---

## Latency Evidence Summary

Latency was measured via Option B instrumentation: producer artifact timestamps
joined with worker structured log timestamps. The max value is an outlier caused by
the log-join / delayed-observation methodology, not a processing delay.

### End-to-End Latency (producer to worker ack)

| Percentile | Latency (ms) |
|---|---|
| p50 | 154.385 |
| p95 | 227.59 |
| p99 | 693.995 |
| max | 960,263.973 (outlier -- log-join delayed observation) |

### Worker Processing Latency

| Percentile | Latency (ms) |
|---|---|
| p50 | 28.037 |
| p95 | 35.948 |
| p99 | 45.357 |

### Database Write Latency

| Percentile | Latency (ms) |
|---|---|
| p50 | 27.911 |
| p95 | 35.807 |
| p99 | 45.208 |

The max outlier (960,263.973 ms) is explicitly documented in the latency evidence
artifact as a log-join / delayed-observation artefact, not a processing tail latency.
See [docs/steady-state-10eps-30min-cloud-validation-evidence.md](steady-state-10eps-30min-cloud-validation-evidence.md).

---

## Evidence Artifact Footprint

| Evidence directory | Size on disk |
|---|---|
| docs/evidence/load-test-50000-cloud | 10 MB |
| docs/evidence/steady-state-10eps-30min-cloud-validation | 39 MB |
| docs/evidence/latency-artifact-100-cloud-validation | 216 KB |

---

## Cost Model Inputs

The following formula is defined for future use when billing export or dated SKU
pricing evidence is available:

```
cost_per_event = total_validation_window_cost / processed_event_count
```

Where:
- `total_validation_window_cost` is the measured GCP billing charge for the
  validation window (requires Cloud Billing export or a dated GCP Pricing
  Calculator snapshot).
- `processed_event_count` is the number of events processed end-to-end
  (acknowledged publish + matched worker event).

For the steady-state run: `processed_event_count = 18,000`.
For the 50,000-event load test: `processed_event_count = 50,000`.

No exact EUR, USD, or GBP cost is claimed in this branch.
No Cloud Billing export was analyzed in this branch.
No current GCP SKU pricing was embedded in this document.

---

## Explicit Non-Claims

The following are explicitly not claimed by this document or this branch:

- No exact EUR, USD, or GBP cost per event is stated.
- No Cloud Billing export was analyzed in this branch.
- No current GCP SKU pricing was embedded in this document.
- Maximum throughput is not claimed.
- Saturation point is not claimed.
- Multi-day production stability is not claimed.
- Exactly-once production semantics are not claimed.
- Bounded Apache Beam / DataflowRunner proof validated (see dataflow-bounded-runner-proof-evidence.md). No sustained production Dataflow pipeline exists; no production Dataflow cost is claimed.
- Enterprise-grade latency SLO enforcement is not claimed.

---

## Final Verdict

The platform has validated performance and strong cost-control operations, but exact
cloud cost per event is not claimed until billing export or dated SKU pricing
evidence is attached.

Cost-control discipline is demonstrated operationally: Cloud SQL STOPPED / NEVER,
Cloud Schedulers PAUSED, Cloud Run worker hard-capped at max scale 1.
Performance is demonstrated by bounded evidence: 50,000-event load test with 0
errors, 18,000-event steady-state run at 10.0 events/sec with 0 errors, and
p50/p95/p99 end-to-end latency from producer-to-worker instrumentation.
