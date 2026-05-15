# BigQuery Bounded Backfill Evidence

**Date:** 2026-05-15
**Branch:** `exec/bigquery-bounded-backfill-evidence`
**Status:** ACCEPTED

---

## Summary

A bounded backfill was executed from Cloud SQL `bronze.market_events` into BigQuery `rtdp_analytics.market_events_raw`.

The objective was to prove that the platform can move historical operational event data from the Cloud SQL serving store into the BigQuery analytical tier.

This closes the first BigQuery data movement evidence step.

---

## Source

Cloud SQL instance:

```text
rtdp-postgres
```

Source table:

```text
bronze.market_events
```

Source row count:

```text
6104
```

Source schema inspected:

```text
event_id        text                     NO
symbol          text                     NO
event_type      text                     NO
price           numeric                  NO
quantity        numeric                  NO
event_timestamp timestamp with time zone NO
ingested_at     timestamp with time zone NO
source_topic    text                     NO
raw_payload     jsonb                    NO
```

---

## Target

BigQuery dataset:

```text
project-42987e01-2123-446b-ac7.rtdp_analytics
```

Target table:

```text
project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw
```

Pre-load target count:

```text
0
```

Post-load target count:

```text
6104
```

---

## Column Mapping

| Cloud SQL column | BigQuery column |
|---|---|
| `event_id` | `event_id` |
| `event_timestamp` | `event_timestamp` |
| `symbol` | `symbol` |
| `event_type` | `event_type` |
| `price` | `price` |
| `quantity` | `quantity` |
| `source_topic` | `source` |
| `ingested_at` | `ingest_timestamp` |
| `now()` | `bq_load_timestamp` |

---

## Export Evidence

The source table was exported to a local bounded CSV file:

```text
/tmp/rtdp_market_events_raw_backfill.csv
```

Export result:

```text
COPY 6104
```

CSV line count:

```text
6105 /tmp/rtdp_market_events_raw_backfill.csv
```

This equals 6104 data rows plus one CSV header row.

---

## BigQuery Load Evidence

The CSV was loaded into BigQuery using `bq load`.

Load result:

```text
Upload complete.
Current status: DONE
```

Post-load count:

```text
+----------------------------+
| bq_market_events_raw_count |
+----------------------------+
|                       6104 |
+----------------------------+
```

Source-to-target count match:

```text
Cloud SQL source: 6104
BigQuery target: 6104
Match: OK
```

---

## Analytical Query Evidence

A BigQuery analytical query was executed over the loaded event history.

Result:

```text
+---------+------------+-------------+-----------------------+----------------------+----------------+----------------+
| symbol  | event_type | event_count | first_event_timestamp | last_event_timestamp | total_quantity |   avg_price    |
+---------+------------+-------------+-----------------------+----------------------+----------------+----------------+
| BTCUSDT | trade      |        2036 |   2026-01-01 00:00:00 |  2026-05-04 06:30:00 |        121.109 | 67500.49483792 |
| ETHUSDT | trade      |        2034 |   2026-01-01 00:00:01 |  2026-05-04 09:05:00 |        121.014 |  3200.49451327 |
| SOLUSDT | trade      |        2033 |   2026-01-01 00:00:02 |  2026-05-05 06:30:00 |        122.937 |   150.49270536 |
| ADAUSDT | trade      |           1 |   2026-05-05 14:00:00 |  2026-05-05 14:00:00 |            100 |           0.45 |
+---------+------------+-------------+-----------------------+----------------------+----------------+----------------+
```

This proves that BigQuery is not only populated, but queryable for analytical workloads.

---

## Terraform State

Final Terraform plan after the BigQuery load:

```text
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

---

## Safety Controls

Cloud SQL was stopped after the validation window.

Final Cloud SQL state:

```text
NEVER   STOPPED
```

Cloud SQL proxy was stopped.

No scheduler resume was required.

No Cloud Run Job execution was required.

No dbt profile was committed.

---

## Acceptance Criteria

| Criterion | Result |
|---|---|
| BigQuery dataset exists | accepted |
| BigQuery table exists | accepted |
| Source row count captured | accepted |
| Target pre-load count captured | accepted |
| CSV export completed | accepted |
| BigQuery load completed | accepted |
| Source and target row counts match | accepted |
| Analytical query returns rows | accepted |
| Terraform final plan is zero-diff | accepted |
| Cloud SQL returned to `NEVER / STOPPED` | accepted |
| No generated artifacts committed | accepted |

---

## Next

Update architecture and audit documentation to mark the BigQuery analytical tier as implemented for bounded backfill evidence.

Recommended next branch:

```text
docs/post-bigquery-evidence-refresh
```

---

**ACCEPTED**
