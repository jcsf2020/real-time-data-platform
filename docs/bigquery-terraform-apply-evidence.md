

# BigQuery Terraform Apply Evidence

**Status:** ACCEPTED
**Date:** 2026-05-14
**Branch:** `exec/bigquery-terraform-apply-evidence`
**GCP Project:** `project-42987e01-2123-446b-ac7`
**Region / Location:** `europe-west1`

---

## Objective

Apply the Terraform-managed BigQuery analytical tier scaffold and verify that the dataset, tables, partitioning, clustering, IAM bindings, and Terraform state are correct.

This branch validates the infrastructure layer only.

No Cloud SQL start was required. No data backfill was executed. No Cloud Run Job was executed. No scheduler was resumed.

---

## Scope

Created via Terraform:

| Resource | Purpose |
|---|---|
| `google_bigquery_dataset.rtdp_analytics` | BigQuery analytical dataset |
| `google_bigquery_table.market_events_raw` | Append-only raw event history table |
| `google_bigquery_table.market_event_minute_aggregates` | Curated minute aggregate table |
| `google_bigquery_table.market_event_daily_aggregates` | Curated daily aggregate table |
| `google_bigquery_dataset_iam_member.rtdp_worker_bigquery_data_editor` | Dataset write permissions for `rtdp-worker-sa` |
| `google_project_iam_member.rtdp_worker_bigquery_job_user` | BigQuery job execution permission for `rtdp-worker-sa` |

---

## Pre-Apply Plan

Terraform planned exactly six resources:

```text
Plan: 6 to add, 0 to change, 0 to destroy.
```

Expected resources:

```text
google_bigquery_dataset.rtdp_analytics
google_bigquery_dataset_iam_member.rtdp_worker_bigquery_data_editor
google_bigquery_table.market_event_daily_aggregates
google_bigquery_table.market_event_minute_aggregates
google_bigquery_table.market_events_raw
google_project_iam_member.rtdp_worker_bigquery_job_user
```

---

## Terraform Apply Result

Terraform apply completed successfully:

```text
Apply complete! Resources: 6 added, 0 changed, 0 destroyed.
```

Created resources:

```text
google_bigquery_dataset.rtdp_analytics
google_bigquery_dataset_iam_member.rtdp_worker_bigquery_data_editor
google_bigquery_table.market_event_daily_aggregates
google_bigquery_table.market_event_minute_aggregates
google_bigquery_table.market_events_raw
google_project_iam_member.rtdp_worker_bigquery_job_user
```

---

## Dataset Verification

Command output confirmed dataset creation:

```json
{
  "id": "project-42987e01-2123-446b-ac7:rtdp_analytics",
  "location": "europe-west1",
  "labels": {
    "environment": "prod",
    "goog-terraform-provisioned": "true",
    "platform": "rtdp",
    "tier": "analytics"
  }
}
```

Accepted:

| Check | Result |
|---|---|
| Dataset exists | yes |
| Dataset ID | `rtdp_analytics` |
| Location | `europe-west1` |
| Labels present | yes |
| Terraform provisioned label | yes |

---

## Table Verification

`bq ls` confirmed all three tables exist:

```text
market_event_daily_aggregates
market_event_minute_aggregates
market_events_raw
```

Table configuration:

| Table | Partitioning | Clustering |
|---|---|---|
| `market_events_raw` | `DAY` on `event_timestamp` | `symbol`, `event_type` |
| `market_event_minute_aggregates` | `DAY` on `window_start` | `symbol`, `event_type` |
| `market_event_daily_aggregates` | `DAY` on `event_date` | `symbol` |

---

## `market_events_raw` Schema

Verified BigQuery table reference:

```text
project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw
```

Verified partitioning:

```json
{
  "field": "event_timestamp",
  "type": "DAY"
}
```

Verified clustering:

```json
{
  "fields": [
    "symbol",
    "event_type"
  ]
}
```

Verified schema:

| Column | Type | Mode |
|---|---|---|
| `event_id` | STRING | REQUIRED |
| `event_timestamp` | TIMESTAMP | REQUIRED |
| `symbol` | STRING | REQUIRED |
| `event_type` | STRING | REQUIRED |
| `price` | NUMERIC | NULLABLE |
| `quantity` | NUMERIC | NULLABLE |
| `source` | STRING | NULLABLE |
| `ingest_timestamp` | TIMESTAMP | REQUIRED |
| `bq_load_timestamp` | TIMESTAMP | REQUIRED |

---

## `market_event_minute_aggregates` Schema

Verified BigQuery table reference:

```text
project-42987e01-2123-446b-ac7.rtdp_analytics.market_event_minute_aggregates
```

Verified partitioning:

```json
{
  "field": "window_start",
  "type": "DAY"
}
```

Verified clustering:

```json
{
  "fields": [
    "symbol",
    "event_type"
  ]
}
```

Verified schema:

| Column | Type | Mode |
|---|---|---|
| `window_start` | TIMESTAMP | REQUIRED |
| `window_end` | TIMESTAMP | REQUIRED |
| `symbol` | STRING | REQUIRED |
| `event_type` | STRING | REQUIRED |
| `open_price` | NUMERIC | NULLABLE |
| `high_price` | NUMERIC | NULLABLE |
| `low_price` | NUMERIC | NULLABLE |
| `close_price` | NUMERIC | NULLABLE |
| `total_quantity` | NUMERIC | NULLABLE |
| `event_count` | INTEGER | REQUIRED |
| `created_at` | TIMESTAMP | REQUIRED |

Note: Terraform schema uses `INT64`; BigQuery displays this as `INTEGER`. This is expected alias behavior.

---

## `market_event_daily_aggregates` Schema

Verified BigQuery table reference:

```text
project-42987e01-2123-446b-ac7.rtdp_analytics.market_event_daily_aggregates
```

Verified partitioning:

```json
{
  "field": "event_date",
  "type": "DAY"
}
```

Verified clustering:

```json
{
  "fields": [
    "symbol"
  ]
}
```

Verified schema:

| Column | Type | Mode |
|---|---|---|
| `event_date` | DATE | REQUIRED |
| `symbol` | STRING | REQUIRED |
| `event_type` | STRING | REQUIRED |
| `open_price` | NUMERIC | NULLABLE |
| `high_price` | NUMERIC | NULLABLE |
| `low_price` | NUMERIC | NULLABLE |
| `close_price` | NUMERIC | NULLABLE |
| `total_quantity` | NUMERIC | NULLABLE |
| `event_count` | INTEGER | REQUIRED |
| `updated_at` | TIMESTAMP | REQUIRED |

Note: Terraform schema uses `INT64`; BigQuery displays this as `INTEGER`. This is expected alias behavior.

---

## IAM Verification

Terraform created:

```text
google_bigquery_dataset_iam_member.rtdp_worker_bigquery_data_editor
google_project_iam_member.rtdp_worker_bigquery_job_user
```

Accepted IAM:

| Principal | Role | Scope |
|---|---|---|
| `serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | `roles/bigquery.dataEditor` | Dataset `rtdp_analytics` |
| `serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` | `roles/bigquery.jobUser` | Project `project-42987e01-2123-446b-ac7` |

This is sufficient for future bounded export jobs to write to BigQuery and run BigQuery jobs without granting project-wide BigQuery admin permissions.

---

## Post-Apply Terraform Zero-Diff

Terraform plan after apply returned zero diff:

```text
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

Accepted:

| Check | Result |
|---|---|
| Terraform state updated | yes |
| BigQuery resources tracked | yes |
| Zero-diff after apply | `PLAN_EXIT=0` |
| Drift detected | no |

---

## Safety Status

Cloud SQL remained stopped throughout the BigQuery apply.

Final Cloud SQL status:

```text
NEVER   STOPPED
```

Accepted safety controls:

| Control | Result |
|---|---|
| Cloud SQL not started | confirmed |
| Cloud SQL final state | `NEVER / STOPPED` |
| Scheduler not resumed | confirmed |
| Cloud Run Jobs not executed | confirmed |
| No data backfill executed | confirmed |
| No generated artifacts committed | confirmed |

---

## Validation Summary

| Requirement | Result |
|---|---|
| BigQuery dataset created via Terraform | accepted |
| Three BigQuery tables created via Terraform | accepted |
| Partitioning configured | accepted |
| Clustering configured | accepted |
| Worker service account BigQuery write/job IAM added | accepted |
| Terraform apply successful | accepted |
| Terraform plan zero-diff after apply | accepted |
| Cloud SQL remains `NEVER / STOPPED` | accepted |
| No Cloud SQL start | accepted |
| No backfill | accepted |

---

## What This Proves

The platform now has a Terraform-managed BigQuery analytical tier scaffold.

This closes the infrastructure foundation for the BigQuery gap identified in the post-dbt scheduler audit. The analytical warehouse now exists, but it is not yet populated.

This is infrastructure evidence only, not data movement evidence.

---

## Remaining Work

Next branch:

```text
exec/bigquery-bounded-backfill-evidence
```

Expected next objective:

- Start Cloud SQL in a bounded validation window
- Export a bounded set of events from `bronze.market_events`
- Load into `rtdp_analytics.market_events_raw`
- Validate BigQuery row count
- Run at least one analytical query
- Stop Cloud SQL immediately
- Document evidence

---

## Final Status

**ACCEPTED**

The BigQuery Terraform apply is complete and verified.

BigQuery resources are live, Terraform-managed, region-aligned, partitioned, clustered, and protected.

Cloud SQL remains cost-controlled at `NEVER / STOPPED`.