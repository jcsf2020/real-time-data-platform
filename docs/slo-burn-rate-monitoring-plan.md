# SLO Burn-Rate Monitoring Plan

**Status:** PLAN -- SLO burn-rate monitoring strategy for the validated GCP data platform
**Date:** 2026-05-22
**Branch:** `docs/slo-burn-rate-monitoring-plan`
**Author intent:** Rigorous SRE observability strategy. No unsupported claims. No implementation
on this branch. No alert policies created. No GCP resources mutated. No Cloud SQL started.
No Terraform applied.

---

## 1. Context

### Current Validated Architecture

The Real-Time Data Platform operates on the following proven event-processing path:

```
Pub/Sub topic (market-events-raw)
  → Cloud Run worker (rtdp-pubsub-worker, maxScale=1, concurrency=1)
    → Cloud SQL PostgreSQL (rtdp-postgres, bronze.market_events, NEVER/STOPPED by default)
      → rtdp-dbt-refresh-job (Cloud Run Job, delete+insert incremental)
          → silver.market_event_minute_aggregates
          → gold.market_event_daily_aggregates
      → rtdp-bigquery-append-job (Cloud Run Job, cursor-based MERGE)
          → BigQuery rtdp_analytics.market_events_raw (DAY-partitioned)

BigQuery quality checks (bigquery-quality-checks.yml, daily cron + workflow_dispatch)
  → Cloud Monitoring custom metrics
    → alert policy (RTDP BigQuery Quality Failure)
      → email notification channel (RTDP Operator Email Alerts)
```

All GCP resources are Terraform-managed with a GCS-backed remote state
(`rtdp-terraform-state-project-42987e01-2123-446b-ac7`, prefix `real-time-data-platform/gcp/prod`).
Terraform PLAN_EXIT=0 is the baseline discipline verified across all validated branches.

**Key validated evidence milestones:**

| Milestone | Evidence |
|---|---|
| 50,000-event bounded cloud load test | 0 publish errors; 0 worker errors; 0 duplicate event_ids |
| 10 events/sec for 30 minutes sustained | 18,000 attempted and acknowledged publishes; 0 publish errors; 0 missing worker events |
| p50/p95/p99 latency | p50=154.385 ms; p95=227.59 ms; p99=693.995 ms (producer artifact / worker log join) |
| BigQuery alerting loop | Quality failure → Cloud Monitoring incident OPEN → email notification delivery proven |
| dbt Cloud SQL live execution | dbt run PASS=2; dbt test PASS=22; execution `rtdp-dbt-refresh-job-gqrl8` |

### Current Observability Baseline

The current observability stack includes:

- Four Cloud Monitoring logs-based metrics (`worker_message_processed_count`,
  `worker_message_error_count`, `silver_refresh_success_count`, `silver_refresh_error_count`)
  with datapoints confirmed.
- Five BigQuery quality custom metrics (`custom.googleapis.com/rtdp/bigquery_quality/status`,
  `failed_checks_count`, `check_pass`, `row_count`, `freshness_age_hours`).
- Three Cloud Monitoring alert policies:
  - `RTDP Worker Message Error Alert`
  - `RTDP Silver Refresh Error Alert`
  - `RTDP BigQuery Quality Failure`
- One email notification channel: `RTDP Operator Email Alerts` (channel ID
  `1439157631105258885`), proven for incident delivery.
- One 4-panel Cloud Monitoring dashboard: `RTDP Pipeline Overview`.
- Structured JSON logs from `rtdp-pubsub-worker` and all Cloud Run jobs.

### Status of Existing SLO Documentation

`docs/SLO_AND_INCIDENT_RESPONSE.md` defines production-light SLO targets for the ingestion
and worker layer. It covers:

- API readiness (HTTP 200 during controlled validation: >= 99%).
- Worker processing (>= 99% valid messages processed per controlled run).
- Silver refresh success (>= 95% successful controlled executions).
- CI passing (100% green before merge to main).
- Terraform plan (zero diff or expected additive diff before merge).

This document is explicitly described as production-light. It does not define SLOs with
multi-window error budgets, burn-rate calculations, or multi-window alerting conditions. The
SLO targets apply during controlled validation windows only; outside those windows, many
components are intentionally stopped. No contractual SLA is defined or implied.

### This Branch Is Docs-Only

This branch (`docs/slo-burn-rate-monitoring-plan`) is documentation only. It does NOT:

- Create or modify any Cloud Monitoring alert policies.
- Create any burn-rate alert resources in Terraform.
- Create any SLO dashboard in Cloud Monitoring.
- Start Cloud SQL (`rtdp-postgres`).
- Resume any Cloud Scheduler job.
- Execute any `terraform apply`.
- Push any metric time series to Cloud Monitoring.
- Mutate any GCP resource.

All proposed SLIs, SLO targets, error budget models, burn-rate alert policies, and dashboard
panels described in this document are forward-looking implementation targets. None are active.

---

## 2. Definitions

| Term | Definition |
|---|---|
| **SLI (Service Level Indicator)** | A measured signal that describes service behaviour. An SLI is a ratio or gauge derived from real observability data. Example: `successful_worker_messages / total_worker_messages`. |
| **SLO (Service Level Objective)** | An internal engineering target set against an SLI. An SLO defines an acceptable threshold (e.g., >= 99%) over a defined rolling window (e.g., 7 days). SLOs are aspirational engineering objectives, not contractual commitments. |
| **SLA (Service Level Agreement)** | An external contract between a service provider and a customer, with defined penalties for breach. This project defines no SLA. All SLOs defined here are production-light internal objectives only. |
| **Error budget** | The allowed failure headroom implied by an SLO. If an SLO target is 99%, the error budget is 1% of events or time in the window. When the error budget is exhausted, the platform is outside the SLO; feature work should pause until it is recovered. |
| **Burn rate** | The rate at which the error budget is being consumed relative to the SLO window. A burn rate of 1 means the error budget will be exactly exhausted at the end of the window. A burn rate of 10 means it will be exhausted 10× faster — in 1/10th of the window. |
| **Multi-window multi-burn-rate alerting** | An alerting pattern that uses two independent time windows (a short window and a long window) and a burn-rate threshold to detect fast and slow consumption of the error budget. The short window catches acute spikes; the long window catches gradual degradation. Both conditions must be true simultaneously to trigger an alert, reducing false positives. |
| **Availability SLI** | An SLI measuring the fraction of time or requests during which the service is functional. Example: fraction of valid Pub/Sub messages processed without error. |
| **Correctness SLI** | An SLI measuring data quality. Example: fraction of BigQuery quality check runs that pass all configured checks. |
| **Freshness SLI** | An SLI measuring how current the data is. Example: time elapsed since the last successful silver model refresh or the last BigQuery row with a recent ingest_timestamp. |
| **Latency SLI** | An SLI measuring processing speed. Example: the p95 end-to-end latency from Pub/Sub publish acknowledgement to Cloud SQL write confirmation. |
| **Alert fatigue** | The condition in which operators receive so many alerts — including false positives and transient noise — that they stop treating alerts with urgency. Threshold-only alerts on raw counts are a common source of alert fatigue because every transient spike triggers an alert. |
| **Page-worthy alert** | An alert condition serious enough to require immediate human response, potentially interrupting the on-call operator's sleep or current work. Criteria: meaningful data loss risk, cost-control violation, or user-facing impact. |
| **Ticket-worthy alert** | An alert condition that requires investigation and resolution during business hours, but does not require an immediate response. Criteria: degraded service, growing staleness, or non-critical quality drift. |
| **Production-light SLO** | An SLO defined for a portfolio-grade platform that operates under controlled, bounded conditions rather than continuous production load. Production-light SLOs use the same conceptual framework as production SLOs but acknowledge that the measurement window is limited, the traffic volume is bounded, and the platform is not serving real users with contractual obligations. |

---

## 3. Current Observability Baseline

| Signal | Current evidence | Current status | Limitation |
|---|---|---|---|
| `worker_message_processed_count` | Logs-based metric; DELTA/INT64; filter `jsonPayload.status="ok"` on `rtdp-pubsub-worker`; datapoints confirmed at 50,002 (DELTA window alignment); `cloud-logs-based-metrics-datapoint-validation.md` | VALIDATED -- metric active with confirmed datapoints | DELTA window may add or subtract up to 1 count per alignment boundary; structured logs and Cloud SQL row count are authoritative for exact event count |
| `worker_message_error_count` | Logs-based metric; DELTA/INT64; filter `jsonPayload.status="error"` on `rtdp-pubsub-worker`; TOTAL=13 from isolated error counter validation; `isolated-error-counter-validation-evidence.md` | VALIDATED -- error counter active with confirmed datapoints | 13 error datapoints were deliberately injected in isolated validation run; not production errors |
| `silver_refresh_success_count` | Logs-based metric; DELTA/INT64; filter `jsonPayload.status="ok"` on `rtdp-silver-refresh-job`; TOTAL=1 from scheduler execution proof | VALIDATED -- success counter active | Only one proven scheduled execution (`rtdp-silver-refresh-job-npcl6`); no continuous scheduled execution history |
| `silver_refresh_error_count` | Logs-based metric; DELTA/INT64; filter updated to remove hardcoded `job_name` condition; TOTAL=1 from isolated validation; `silver-refresh-error-metric-filter-evidence.md` | VALIDATED -- error counter active with confirmed datapoints | Error datapoint was deliberately injected; no production refresh errors observed |
| BigQuery quality metrics (×5) | Custom metrics: `status`, `failed_checks_count`, `check_pass`, `row_count`, `freshness_age_hours`; 10–12 time series per run; emitted from `scripts/push_bigquery_quality_metrics.py`; `bigquery-quality-cloud-monitoring-metrics-evidence.md` | VALIDATED -- all 5 metric types confirmed with datapoints | Metrics emitted per workflow_dispatch and scheduled cron run; not continuous; no burn-rate calculation on these signals |
| BigQuery quality incident and email proof | Run ID 26089332693; controlled failure (min_row_count=999999999); `failed_checks_count=1`; alert policy OPEN state confirmed via CLI; Gmail inbox screenshot; `bigquery-quality-incident-notification-delivery-proof.md` | VALIDATED -- full alerting loop proven end-to-end | Single controlled failure scenario; no ongoing production failure history; alert triggered by threshold (failed_checks_count > 0), not burn-rate |
| 4-panel Cloud Monitoring dashboard | `RTDP Pipeline Overview`; exported to `infra/monitoring/dashboards/rtdp-pipeline-overview.json`; `cloud-monitoring-dashboard-evidence.md` | VALIDATED -- dashboard active in GCP | Threshold-style dashboard panels; no error-budget or burn-rate panel; no SLO widget |
| p50/p95/p99 latency evidence | p50=154.385 ms; p95=227.59 ms; p99=693.995 ms; computed from producer JSONL artifact + worker structured log join; `steady-state-10eps-30min-cloud-validation-evidence.md` | VALIDATED -- latency evidence from sustained 30-min run | No Cloud SQL persisted latency column; latency is computed offline from artifact/log join; not a continuous Cloud Monitoring metric; max=960,263.973 ms is a documented outlier / delayed observation, not representative tail latency |
| dbt run/test evidence | dbt run PASS=2; dbt test PASS=22; execution `rtdp-dbt-refresh-job-gqrl8`; Cloud SQL live; `dbt-cloud-sql-incremental-execution-proof.md` | VALIDATED -- incremental execution against Cloud SQL proven | One bounded execution window; no dbt-specific Cloud Monitoring metrics emitted; no ongoing dbt execution monitoring; Cloud SQL must be started for each execution |
| Terraform PLAN_EXIT=0 discipline | `terraform plan -detailed-exitcode` returns exit code 0 across all validated branches; confirmed in every evidence document | VALIDATED -- zero-diff discipline maintained throughout | Manual plan on each PR; no automated Terraform drift alert policy configured; drift detection depends on CI run frequency |

---

## 4. Current SLO Coverage

### What `docs/SLO_AND_INCIDENT_RESPONSE.md` Currently Covers

The existing SLO document provides production-light targets for the following areas:

| Area | SLI used | SLO target | Current implementation status |
|---|---|---|---|
| **Ingestion health** | Pub/Sub publish acknowledgement during controlled run | 18,000/18,000 (100%) in sustained validation | Implemented metric (`worker_message_processed_count`); threshold alert active; NO burn-rate alerting |
| **Worker health** | Valid messages producing `status=ok` logs | >= 99% per controlled run | Implemented metric; threshold alert; NO error budget; NO burn-rate |
| **Transformation health (silver refresh)** | Silver refresh job exits status=ok | >= 95% controlled executions | Implemented metric (`silver_refresh_success_count`); threshold alert active; NO burn-rate |
| **BigQuery quality health** | Quality check passes all configured checks | 6/6 pass per run | Custom metrics emitted; alert policy active; incident and email proven; NO burn-rate on quality metrics |
| **Infrastructure drift health** | Terraform plan PLAN_EXIT=0 | No unreviewed destructive changes before merge | CI plan gate enforced; NO Cloud Monitoring alert for Terraform drift; DOCUMENTED ONLY |
| **Cost-control state health** | Cloud SQL NEVER/STOPPED; schedulers PAUSED | Verified on every evidence run | Documented consistently; NO automated Cloud Monitoring alert for accidental state violations |

### Coverage Classification

| Area | Implemented metric | Documented SLO | Burn-rate alerting | Missing |
|---|---|---|---|---|
| Worker processing success rate | YES | YES (production-light) | NO | Burn-rate alert policy; error budget calculation |
| Worker error rate | YES | YES | NO | Burn-rate alert policy |
| Publish acknowledgement rate | Indirect (logs) | YES | NO | Explicit publish-rate SLI metric; burn-rate |
| End-to-end latency p95/p99 | NO (artifact-based only) | NO | NO | Continuous latency Cloud Monitoring metric |
| BigQuery quality pass rate | YES | NO formal SLO | NO | Formal SLO target; burn-rate policy |
| BigQuery freshness | YES (freshness_age_hours metric) | NO formal SLO | NO | Formal SLO target; burn-rate |
| BigQuery duplicate count | YES (implicit in quality checks) | NO | NO | Explicit metric; SLO |
| dbt run success rate | NO | NO | NO | dbt metrics; SLO; burn-rate |
| dbt test pass rate | NO | NO | NO | dbt metrics; SLO; burn-rate |
| dbt model freshness | NO | NO | NO | dbt freshness metric; SLO |
| Terraform drift status | NO | Documented only | NO | Cloud Monitoring alert for drift |
| Cloud SQL safe-state compliance | NO | Documented only | NO | Automated safe-state check |
| Scheduler safe-state compliance | NO | Documented only | NO | Automated safe-state check |

---

## 5. Proposed SLIs

The following SLIs are proposed future implementation targets. None are currently implemented
as continuous Cloud Monitoring time-series or error-budget calculations.

| SLI name | Layer | Formula | Source metric / query | Current implementation status | Proposed target | Caveat |
|---|---|---|---|---|---|---|
| Worker success rate | Ingestion / worker | `worker_message_processed_count / (worker_message_processed_count + worker_message_error_count)` | `custom.googleapis.com/logging/user/worker_message_processed_count` + `worker_message_error_count` | PARTIAL -- both metrics active; ratio not computed automatically | >= 99.0% over rolling 7 days | Low traffic volume makes percentage fragile; 1 error in 100 events = 99%; 1 error in 10 events = 90% |
| Worker error rate | Ingestion / worker | `worker_message_error_count / total_messages_attempted` | `custom.googleapis.com/logging/user/worker_message_error_count` | PARTIAL -- metric active; no rate calculation | 0 unexpected errors per controlled run | Error count > 0 during a valid-event run is the alert trigger; rate is secondary |
| Publish acknowledgement rate | Ingestion | `acknowledged_publishes / attempted_publishes` | Producer JSONL artifact; Cloud Monitoring logs; not a continuous metric | NOT IMPLEMENTED as Cloud Monitoring metric | 100% during controlled runs | Currently computed from producer artifact post-run; no real-time Cloud Monitoring signal |
| End-to-end latency p95 | Ingestion / worker | `p95(worker_ack_time - producer_publish_time)` | Producer artifact + worker log join; not a Cloud Monitoring gauge | NOT IMPLEMENTED as Cloud Monitoring metric | p95 < 500 ms during controlled validation | Currently computed offline; not a continuous signal; max outlier documented at ~960 s |
| End-to-end latency p99 | Ingestion / worker | `p99(worker_ack_time - producer_publish_time)` | Producer artifact + worker log join | NOT IMPLEMENTED as Cloud Monitoring metric | p99 < 1000 ms during controlled validation | Same caveat as p95; bounded validation only |
| BigQuery quality pass rate | Analytical quality | `passing_quality_runs / total_quality_runs` | `custom.googleapis.com/rtdp/bigquery_quality/failed_checks_count` (== 0 = pass) | PARTIAL -- metric active; pass rate not computed as ratio | >= 95% of scheduled runs pass all checks | Quality runs are daily scheduled; low frequency makes rate fragile |
| BigQuery freshness | Analytical quality | `age_hours = (NOW() - MAX(ingest_timestamp))` | `custom.googleapis.com/rtdp/bigquery_quality/freshness_age_hours` | VALIDATED -- metric emitted; age_hours=62.9712 confirmed | < 24 hours during normal operation (scheduler running) | Freshness depends on scheduler being enabled; intentionally paused = not an incident |
| BigQuery duplicate count | Analytical quality | `COUNT(*) - COUNT(DISTINCT event_id) in market_events_raw` | BigQuery quality check script; `staging_table_empty` check; implicit in MERGE idempotency | PARTIAL -- quality check script validates; no explicit Cloud Monitoring metric for duplicates | 0 duplicates at every quality run | MERGE semantics enforce idempotency; duplicate detection is a defensive check |
| dbt run success rate | Transformation | `dbt_run_success_count / (dbt_run_success_count + dbt_run_failure_count)` | Proposed `custom.googleapis.com/rtdp/dbt/dbt_run_success_count` | NOT IMPLEMENTED | >= 95% over rolling 7 days (when scheduler enabled) | Requires `feat/dbt-metric-emission-script`; scheduler is PAUSED by default |
| dbt test pass rate | Transformation | `dbt_test_pass_count / (dbt_test_pass_count + dbt_test_failure_count)` | Proposed `custom.googleapis.com/rtdp/dbt/dbt_test_pass_rate` | NOT IMPLEMENTED | 100% on every execution (any failure is SEV1) | Any dbt test failure is a data contract violation; no tolerance |
| dbt model freshness lag | Transformation | `EXTRACT(EPOCH FROM (NOW() - MAX(updated_at))) / 60` minutes | Proposed `custom.googleapis.com/rtdp/dbt/dbt_model_freshness_lag_minutes` | NOT IMPLEMENTED | < 30 min for silver; < 60 min for gold (when scheduler enabled) | Not meaningful when scheduler is intentionally PAUSED |
| Terraform drift status | Infrastructure | `PLAN_EXIT: 0 = no drift; 2 = pending changes; 1 = error` | `terraform-plan.yml` CI output; not a Cloud Monitoring metric | DOCUMENTED -- CI gate enforced; no Cloud Monitoring alert | PLAN_EXIT=0 on every PR and push | No Cloud Monitoring signal; drift detected only at CI run time |
| Cloud SQL safe-state compliance | Cost control | `activation_policy IN ('NEVER'); state = 'STOPPED'` | `gcloud sql instances describe rtdp-postgres` | DOCUMENTED -- manual verification throughout evidence base | Activation policy NEVER; state STOPPED except during bounded validation windows | No automated alert; detection is manual or via evidence-branch discipline |
| Scheduler safe-state compliance | Cost control | `state = 'PAUSED'` for both schedulers | `gcloud scheduler jobs list` | DOCUMENTED -- manual verification throughout evidence base | Both schedulers PAUSED except during bounded controlled execution windows | No automated alert; detection is manual |

---

## 6. Proposed SLO Targets

The following SLO targets are proposed future implementation targets. All targets are
production-light: they apply to controlled validation windows and do not represent
contractual commitments. The platform is not continuously live; Cloud SQL is STOPPED/NEVER
and schedulers are PAUSED outside bounded windows.

| SLO | SLI | Target | Window | Why this target | Current evidence support | Production caveat |
|---|---|---|---|---|---|---|
| Ingestion correctness | Publish acknowledgement rate | 100% of attempted publishes acknowledged | Per controlled run | 18,000/18,000 proven in sustained run; 50,000/50,000 proven in bounded load test; 0 publish errors observed | STRONG -- proven at scale; 0 publish errors across all validated runs | No continuous traffic; no multi-day window; target is per-run, not rolling |
| Worker processing reliability | Worker success rate | >= 99% of valid messages produce `status=ok` logs | Rolling 7 days (when scheduler enabled) or per controlled run | 50,000/50,000 proven; 18,000/18,000 proven; only deliberate isolated error injections produced errors | STRONG for bounded runs -- 0 unexpected errors observed | MaxScale=1, concurrency=1; not horizontally scaled; low denominator makes percentage fragile for small runs |
| Analytical quality | BigQuery quality pass rate | >= 95% of scheduled quality runs pass all checks | Rolling 30 days (when quality cron enabled) | 6/6 checks pass on all non-deliberately-failed runs; controlled failure path proven for alert delivery | MODERATE -- scheduled cron proven; alert loop proven; rate calculation requires accumulation over time | Freshness check threshold is configurable; rate depends on threshold settings |
| BigQuery freshness | BigQuery freshness (age_hours) | < 24 hours during normal operation | Per scheduled quality run | `freshness_age_hours` metric validated (62.97 hours observed in a non-production test); freshness_max_age_hours configurable | PARTIAL -- metric emitted and confirmed; SLO threshold not enforced; single run only | Scheduler must be enabled for freshness to advance; scheduler is PAUSED by default; stale freshness when intentionally paused is not an incident |
| dbt transformation correctness | dbt test pass rate | 100% on every execution | Per execution | dbt test PASS=22 on all validated executions | STRONG for executed runs -- single bounded validation | Requires dbt metrics not yet implemented; SLO cannot be monitored without `feat/dbt-metric-emission-script` |
| dbt transformation reliability | dbt run success rate | >= 95% over rolling 7 days (when scheduler enabled) | Rolling 7 days | dbt run PASS=2 on all validated executions | PARTIAL -- one validated execution; no multi-run history | Requires dbt metrics; scheduler PAUSED by default |
| Operational safe-state compliance | Cloud SQL + scheduler safe-state | 100% compliance (Cloud SQL NEVER/STOPPED, schedulers PAUSED) outside bounded windows | Continuous | Documented and verified throughout 60+ evidence documents | STRONG -- consistent discipline throughout evidence base | Manual verification; no automated monitoring signal |
| Infrastructure drift control | Terraform PLAN_EXIT=0 | 100% of PR merges produce PLAN_EXIT=0 | Per PR / push | PLAN_EXIT=0 verified on every validated branch | STRONG -- CI gate enforced on every PR | Drift between CI runs is undetected; no continuous Cloud Monitoring alert |

---

## 7. Error Budget Model

### How Error Budget Is Calculated

An error budget is the allowed failure headroom implied by the SLO. For an SLO of 99%
over a 7-day window containing 100,000 events, the error budget is 1,000 events (1%).
When 1,000 events have failed, the error budget is exhausted and the platform is outside
its SLO.

For this platform, error budget calculation is proposed but not automated. The following
describes the calculation model for each SLO.

**Event-based error budget (worker):**

```
error_budget_events = total_events_in_window * (1 - slo_target)

Example: SLO = 99%; window = 7 days; total events = 18,000
error_budget = 18,000 * 0.01 = 180 events
budget_remaining = 180 - worker_error_count
```

**Time-based error budget (freshness):**

```
error_budget_time = window_duration * (1 - slo_target)

Example: SLO = 95% availability; window = 30 days = 43,200 minutes
error_budget = 43,200 * 0.05 = 2,160 minutes
budget_consumed = total minutes with freshness_age_hours > threshold
```

### Monthly vs Weekly Windows

| Window | Use case | Advantage | Disadvantage |
|---|---|---|---|
| Rolling 7 days | Worker reliability; dbt run reliability | More responsive to recent failures; faster feedback | Lower denominator; single-event errors have larger percentage impact |
| Rolling 30 days | BigQuery quality compliance; freshness compliance | More stable; smooths transient spikes | Slow to react to sustained degradation; old events mask current state |
| Per controlled run | Ingestion correctness; safe-state compliance | Directly reflects bounded validation evidence | Not a continuous production window; cannot compute rolling rate without accumulation |

### Event-Based vs Time-Based Error Budget

| Budget type | Best for | Limitation for this platform |
|---|---|---|
| Event-based | Worker success rate; BigQuery quality checks | Very low event volumes make percentages volatile; 1 error in 10 events = 90% (SLO breach); 1 error in 10,000 events = 99.99% (well within SLO) |
| Time-based | Freshness; safe-state compliance; availability | Scheduler is PAUSED by default; time-based freshness budget assumes continuous operation |

### Why Low Traffic Makes Percentage-Based SLOs Fragile

The platform processes events during bounded validation windows. Outside those windows,
Cloud SQL is STOPPED and schedulers are PAUSED. A percentage-based SLO calculated over
a 7-day window where events occur only during a 30-minute controlled run will have a
denominator of ~18,000 events (in the best-documented case). A single unexpected error
consumes 0.0056% of the error budget. A batch of 180 unexpected errors (all that would
be needed to exhaust a 7-day 99% budget) has never been observed.

However, in a very low-traffic scenario (e.g., 100 events), a single error consumes 1% of
the error budget immediately. This is a structural fragility: the SLO target and the error
budget are both accurate, but the statistical significance of a single error is very high
at low volume.

**Recommended approach for this portfolio project:** set conservative SLO targets
(95-99%) and track error budgets per controlled run rather than over rolling time windows
until the platform operates continuously.

### Handling Intentionally Paused Schedulers / Stopped Cloud SQL

The following rules must govern error budget calculation when the platform is in its
intentional safe state:

- **Cloud SQL STOPPED/NEVER**: This is not a service failure. Error budget calculations
  for worker processing SLOs only apply during active ingestion windows. A stopped Cloud
  SQL instance outside a validation window does not consume the error budget.
- **Schedulers PAUSED**: This is not a freshness failure. Freshness SLOs and dbt run SLOs
  only apply when the corresponding scheduler is enabled. A paused scheduler does not
  consume the freshness error budget.
- **Scheduled quality check with freshness threshold = 0**: An intentionally-set
  `freshness_max_age_hours=0` is a controlled failure scenario, not a production
  freshness violation.
- **Cloud Monitoring absence-of-data**: When no events are flowing (intentional), Cloud
  Monitoring time-series will show no data points. Alert policies must be configured to
  distinguish "no data" (expected when platform is idle) from "error" (unexpected failure
  during an active window).

---

## 8. Burn-Rate Alerting Strategy

### Why Threshold-Only Alerts Are Insufficient

The current alert policies use static thresholds on absolute counts:

- `RTDP Worker Message Error Alert`: triggers if `worker_message_error_count > 0` in a
  5-minute window.
- `RTDP Silver Refresh Error Alert`: triggers if `silver_refresh_error_count > 0` in a
  5-minute window.
- `RTDP BigQuery Quality Failure`: triggers if `failed_checks_count > 0`.

These threshold alerts have two structural weaknesses:

**False positives during normal operation:** A single transient error (e.g., a Cloud SQL
connection hiccup that is retried and succeeds) triggers the alert. In a production
environment with continuous traffic, this generates noise. The operator is paged for a
condition that has already recovered.

**Insufficient sensitivity to slow burn:** If the worker is experiencing a 2% error rate
that is consistent but never produces a burst, the threshold alert may not fire (because
no single 5-minute window crosses a high count threshold). But a 2% error rate over 7 days
would exhaust a 99% SLO in approximately 3.5 days — a production-critical situation that
threshold alerts would miss.

### Why Burn-Rate Alerts Reduce Alert Fatigue

Burn-rate alerts trigger based on the rate at which the error budget is being consumed,
not on the absolute count of errors. They answer the question: "at the current error rate,
when will the SLO budget be exhausted?"

- A **high burn rate** (e.g., 14×) means the budget will be exhausted in 1/14th of the
  window — for a 30-day window, that is about 2 days. This warrants immediate (page-worthy)
  attention.
- A **low burn rate** (e.g., 2×) means the budget will be exhausted in half the window —
  about 15 days for a 30-day window. This warrants investigation but not a page.

Burn-rate alerts reduce alert fatigue because:
- Transient single-event errors do not consume enough budget to cross the burn-rate
  threshold. They do not trigger the alert.
- Sustained degradation that would breach the SLO does cross the threshold. It does
  trigger the alert — in time to investigate before budget exhaustion.

### Multi-Window Multi-Burn-Rate Model

The multi-window approach uses two independent time windows and a burn-rate multiplier to
trigger an alert. Both windows must simultaneously indicate a high burn rate. This further
reduces false positives.

**Structure:**

```
alert_condition = burn_rate_in_short_window > threshold
                  AND burn_rate_in_long_window > threshold

Example for a 99% SLO with 30-day window (2.5% error budget):
  fast burn alert: burn_rate_in_1h > 14 AND burn_rate_in_5m > 14
  slow burn alert: burn_rate_in_6h > 6 AND burn_rate_in_30m > 6
```

**Why two windows are required:** A single burst of errors in a 5-minute window might be
a transient spike that will recover. If the 1-hour window also shows a burn rate above the
threshold, it confirms the degradation is sustained. Single-window alerts on short windows
have high false-positive rates; long-window alerts have high detection latency for fast
failures.

### Fast Burn Alerts

| Parameter | Value |
|---|---|
| Short window | 5 minutes |
| Long window | 1 hour |
| Burn-rate threshold | 14× (for 99% SLO over 30 days; exhausts budget in ~50 hours) |
| Severity | SEV1 or SEV2 depending on the SLO |
| Classification | Page-worthy in production |

Fast burn alerts detect: sudden worker outages, total BigQuery quality failure, complete
pipeline unavailability. These scenarios produce very high burn rates immediately.

### Medium Burn Alerts

| Parameter | Value |
|---|---|
| Short window | 30 minutes |
| Long window | 6 hours |
| Burn-rate threshold | 6× (exhausts budget in ~5 days) |
| Severity | SEV2 |
| Classification | Page-worthy in production; ticket-worthy in portfolio mode |

Medium burn alerts detect: sustained elevated error rates, recurring dbt failures,
repeated BigQuery quality threshold violations. These are slower to develop but serious.

### Slow Burn Alerts

| Parameter | Value |
|---|---|
| Short window | 2 hours |
| Long window | 24 hours |
| Burn-rate threshold | 2–3× (exhausts budget in ~10-15 days) |
| Severity | SEV3 |
| Classification | Ticket-worthy |

Slow burn alerts detect: gradual model freshness drift, slightly elevated error rate,
Terraform plan drift observed over multiple days. These warrant investigation and a fix
within the week.

### Proposed Alert Windows Summary

| Alert type | Short window | Long window | Burn-rate threshold | Budget exhaustion at threshold |
|---|---|---|---|---|
| Fast burn | 5 minutes | 1 hour | 14× | ~50 hours (for 30-day SLO) |
| Medium burn | 30 minutes | 6 hours | 6× | ~5 days |
| Slow burn | 2 hours | 24 hours | 2× | ~15 days |

**All proposed alert windows are design targets only. None are currently implemented.**

---

## 9. Proposed Burn-Rate Alert Policies

The following table describes proposed alert policies. None are currently implemented.
All would be managed as `google_monitoring_alert_policy` Terraform resources, analogous
to the existing policies. All would reuse the existing `RTDP Operator Email Alerts`
notification channel.

| Alert name | SLO protected | Burn-rate condition | Window | Severity | Notification path | Operator action | Implementation status |
|---|---|---|---|---|---|---|---|
| `RTDP Worker Error Budget Fast Burn` | Worker processing reliability (99%) | burn_rate(`worker_error_count / total_messages`) > 14 in both 5m and 1h windows | 5m / 1h | SEV2 | RTDP Operator Email Alerts | Inspect `worker_message_error_count` time-series; check Cloud Logging for `jsonPayload.status="error"` entries; check Pub/Sub subscription delivery attempts; stop publishing if inside a valid-event window | **NOT IMPLEMENTED** |
| `RTDP Worker Error Budget Slow Burn` | Worker processing reliability (99%) | burn_rate > 2 in both 2h and 24h windows | 2h / 24h | SEV3 | RTDP Operator Email Alerts | Open a ticket; investigate whether error rate is trending upward; review recent deployments; check for DLQ growth | **NOT IMPLEMENTED** |
| `RTDP BigQuery Quality Fast Burn` | Analytical quality (95% pass rate) | `failed_checks_count > 0` within 5m; burn_rate > 14 in 5m/1h | 5m / 1h | SEV2 | RTDP Operator Email Alerts | Check quality report artifact; identify failing check(s); inspect BigQuery table for anomalies; verify freshness | **NOT IMPLEMENTED** (existing threshold alert is active; burn-rate variant is not) |
| `RTDP dbt Run Failure Fast Burn` | dbt transformation reliability (95%) | `dbt_run_failure_count > 0` within 5m; burn_rate > 14 | 5m / 1h | SEV2 | RTDP Operator Email Alerts | Check `rtdp-dbt-refresh-job` execution logs; verify Cloud SQL state; check `run_results.json` for ERROR node; do not start Cloud SQL without scoped runbook | **NOT IMPLEMENTED** (requires `feat/dbt-metric-emission-script` as prerequisite) |
| `RTDP dbt Model Freshness Slow Burn` | dbt freshness (< 30 min for silver, < 60 min for gold) | `dbt_model_freshness_lag_minutes > threshold` sustained in 2h/24h window | 2h / 24h | SEV3 | RTDP Operator Email Alerts | Check scheduler state (PAUSED = expected freshness lag, not an incident); check last dbt execution timestamp; do not start Cloud SQL without scoped runbook | **NOT IMPLEMENTED** |
| `RTDP Terraform Drift Detected` | Infrastructure drift control | Cloud Monitoring custom metric emitted by CI: `terraform_plan_exit_code > 0` | Per CI run | SEV2 | RTDP Operator Email Alerts | Stop all merges; capture full `terraform plan` output; identify drifted resource; open dedicated fix or import branch; do not run `terraform apply` without review | **NOT IMPLEMENTED** (no Cloud Monitoring metric for PLAN_EXIT; drift detected via CI only) |
| `RTDP Cloud SQL Safe-State Violation` | Cost-control safe-state compliance | `cloud_sql_state_is_runnable = 1` outside declared validation window | Continuous | SEV1 / Cost-control critical | RTDP Operator Email Alerts | Immediately inspect: `gcloud sql instances describe rtdp-postgres`; if RUNNABLE outside window, patch to NEVER; document the incident; investigate source of accidental enable | **NOT IMPLEMENTED** (no Cloud Monitoring metric for Cloud SQL instance state) |
| `RTDP Scheduler Safe-State Violation` | Cost-control safe-state compliance | `scheduler_state_is_enabled = 1` outside declared activation window | Continuous | SEV1 / Cost-control critical | RTDP Operator Email Alerts | Immediately pause: `gcloud scheduler jobs pause <job-name>`; verify Cloud SQL state (enabled scheduler may have triggered job execution); document incident | **NOT IMPLEMENTED** (no Cloud Monitoring metric for scheduler state) |

---

## 10. Page vs Ticket Policy

The following matrix defines which alert conditions are page-worthy vs ticket-worthy for
this platform. Given that the platform is portfolio-grade, the conservative interpretation
is: most alerts are ticket-worthy; only cost-control violations and acute data loss risks
are page-worthy.

| Condition | Severity | Page? | Ticket? | Reason |
|---|---|---|---|---|
| Worker error rate fast burn > 14× for 5m/1h | SEV2 | In production: YES | In portfolio mode: YES, not page | In a production system with live users, fast worker degradation warrants immediate response; in portfolio mode, this is investigation-worthy but not urgent |
| Worker error rate slow burn > 2× for 2h/24h | SEV3 | NO | YES | Gradual degradation; investigate during business hours; no immediate user impact |
| BigQuery quality failure (controlled failure run) | SEV2 | NO | YES | Deliberately triggered; close after verifying alert loop worked |
| BigQuery quality failure (unexpected production failure) | SEV2 | In production: YES | In portfolio mode: YES, not page | Unexpected quality failure indicates data integrity issue; alert loop proven end-to-end |
| BigQuery freshness > 24 hours while scheduler is enabled | SEV2 | NO | YES | Freshness lag when scheduler is running indicates a problem; investigate; not urgent enough for a page at portfolio scale |
| BigQuery freshness > threshold while scheduler is intentionally PAUSED | Not an incident | NO | NO | Intentionally paused scheduler is the expected state; freshness lag is expected behaviour |
| dbt run failure during scheduled execution window | SEV2 | NO | YES | Transformation failure needs investigation; data downstream may be stale; no page at portfolio scale |
| dbt test failure (data contract violation) | SEV1 | In production: YES | In portfolio mode: YES, not page | Any dbt test failure indicates a data quality contract violation; must be investigated immediately; treated as page-worthy in production SRE practice |
| dbt model freshness lag > threshold while scheduler is enabled | SEV3 | NO | YES | Gradual staleness; investigate during business hours |
| dbt model freshness lag > threshold while scheduler is intentionally PAUSED | Not an incident | NO | NO | Expected behaviour; not a production failure |
| Terraform PLAN_EXIT != 0 (CI failure) | SEV2 | NO | YES | Detected in CI; merges are blocked; no immediate GCP impact; investigate before next merge |
| Cloud SQL state RUNNABLE outside bounded window | SEV1 / Cost-control critical | YES | YES | Cost-control violation; unexpected Cloud SQL running may incur charges and indicates accidental or unauthorized start; immediate investigation required |
| Cloud SQL state RUNNABLE during declared bounded validation window | Not an incident | NO | NO | Intentional controlled state; expected behaviour |
| Scheduler state ENABLED outside declared activation window | SEV1 / Cost-control critical | YES | YES | An enabled scheduler will trigger Cloud Run job execution; this will cause Cloud SQL to be accessed and incur costs; immediate response required |
| Scheduler state ENABLED during declared controlled execution | Not an incident | NO | NO | Intentional; expected behaviour |
| Email notification not delivered within 5 minutes of alert OPEN | SEV2 | NO | YES | Notification delivery failure degrades the alerting loop; investigate notification channel configuration |

### Page-Worthy Summary

The following are page-worthy in portfolio mode (immediate operator action required):

1. **Cloud SQL RUNNABLE outside a declared bounded validation window** -- cost-control
   critical; every minute of unexpected Cloud SQL running incurs compute charges.
2. **Scheduler ENABLED outside a declared activation window** -- cost-control critical;
   an enabled scheduler will trigger job executions that interact with Cloud SQL.

The following are page-worthy in a production SRE context (not currently in portfolio mode):

3. Worker error budget fast burn > 14× for 1 hour -- production-critical data loss risk.
4. BigQuery quality failure with open incident -- data integrity concern.
5. dbt test failure -- data contract violation.

---

## 11. SLO Dashboard Plan

A proposed SLO dashboard (`RTDP SLO Status`) would be created as a separate
`google_monitoring_dashboard` Terraform resource from the existing `RTDP Pipeline Overview`.
It would be exported to `infra/terraform/gcp/dashboards/rtdp-slo-status.json`.

**No SLO dashboard is implemented on this branch.**

### Proposed Dashboard Panels

| Panel | Metric / source | Visualisation | Purpose |
|---|---|---|---|
| Error budget remaining (worker) | Computed from `worker_error_count / total_messages` over rolling 7 days | Gauge: 0–100%; red < 20% | Shows remaining worker error budget at a glance |
| Worker success rate (7-day) | `worker_message_processed_count / total` | Line chart; 7-day window | Trend of worker reliability over time |
| Worker error burn rate | Derived burn-rate metric from `worker_message_error_count` | Line chart with threshold line at 14× and 6× | Shows how fast the worker error budget is being consumed |
| BigQuery quality pass/fail (30-day) | `failed_checks_count == 0` per run | Scorecard or bar chart: PASS/FAIL per day | Shows quality run health history |
| dbt run/test health | `dbt_run_failure_count` + `dbt_test_failure_count` | Scorecard: PASS / FAIL / NOT IMPLEMENTED | Shows transformation layer health |
| Freshness lag (BigQuery) | `freshness_age_hours` | Line chart with threshold line at 24h | Shows analytical tier freshness trend |
| Cloud SQL safe-state | `cloud_sql_activation_policy` + `cloud_sql_state` | Scorecard: SAFE / VIOLATION | Cost-control signal |
| Scheduler safe-state | `scheduler_state_is_paused` for both schedulers | Scorecard: SAFE / VIOLATION | Cost-control signal |
| Terraform drift status | `terraform_plan_exit_code` | Scorecard: PLAN_EXIT=0 / DRIFT DETECTED | Infrastructure hygiene signal |
| Recent incidents | Cloud Monitoring incident list filtered by RTDP | Table tile | Links to open incidents for investigation |

### Relationship to Existing Dashboard

The existing `RTDP Pipeline Overview` dashboard (4 panels) monitors raw counters:
`worker_message_processed_count`, `worker_message_error_count`, `silver_refresh_success_count`,
`silver_refresh_error_count`. The proposed SLO dashboard is complementary: it would show
derived SLO/error-budget views rather than raw counts. In a future state, both dashboards
would be accessible from a single `RTDP Platform Status` index page.

---

## 12. Incident Response Integration

### How Burn-Rate Alerts Map to SLO_AND_INCIDENT_RESPONSE.md

The existing incident severity classification in `docs/SLO_AND_INCIDENT_RESPONSE.md` maps
to proposed burn-rate alert policies as follows:

| Proposed burn-rate alert | Severity mapping | Existing runbook |
|---|---|---|
| Worker error budget fast burn | SEV2 | Worker Error Alert runbook |
| Worker error budget slow burn | SEV3 | Worker Error Alert runbook (lower urgency) |
| BigQuery quality fast burn | SEV2 | No existing runbook; runbook in `docs/SLO_AND_INCIDENT_RESPONSE.md` covers deploy failures and silver refresh; BigQuery quality runbook needed |
| dbt run failure fast burn | SEV2 | Silver Refresh Failure runbook (analogous pattern) |
| dbt model freshness slow burn | SEV3 | Silver Refresh Failure runbook (analogous) |
| Terraform drift detected | SEV2 | Terraform Drift Or Destructive Plan runbook |
| Cloud SQL safe-state violation | SEV1 | Cloud SQL Unavailable runbook |
| Scheduler safe-state violation | SEV1 | No dedicated runbook; analogous to Cloud SQL safe-state |

### Post-Incident Evidence Capture

For any burn-rate alert incident, the following evidence must be captured before closing:

1. Alert incident ID from Cloud Monitoring.
2. Alert OPEN timestamp and CLOSED timestamp.
3. Burn rate at time of trigger (from Cloud Monitoring).
4. Root cause (Cloud Logging evidence: error messages, execution IDs, timestamps).
5. Resolution action taken.
6. Cloud SQL final state after resolution (STOPPED/NEVER).
7. Scheduler final states after resolution (PAUSED).
8. PLAN_EXIT=0 confirmation after resolution.
9. New error budget remaining after incident (if calculable).

### Integration with Rollback Strategy

`docs/deploy-on-merge-decision-record.md` defines the rollback procedure for Cloud Run
service deployments. When a burn-rate alert fires after a production deploy:

1. Check `gcloud run services describe` to determine if the new revision is serving.
2. If the burn rate increased immediately after a deploy, treat the deploy as the probable
   root cause.
3. Follow the rollback procedure: redeploy the previous known-good image SHA from
   Artifact Registry.
4. Verify burn rate drops to near zero after rollback.
5. Document the rollback as a production incident in `docs/SLO_AND_INCIDENT_RESPONSE.md`.

### Integration with Replay/Backfill Strategy

`docs/replay-backfill-strategy.md` defines the recovery paths for BigQuery and dbt layers.
When a BigQuery quality burn-rate alert fires:

1. Run BigQuery quality checks workflow to confirm which check(s) are failing.
2. If `row_count_minimum` failure: inspect Cloud SQL bronze row count; consider bounded
   backfill from Cloud SQL using Runbook R-01 if BigQuery row count has dropped.
3. If `freshness_age_hours` failure: check whether the append scheduler is running; if
   paused intentionally, this is expected; if paused accidentally, re-enable under a scoped
   runbook.
4. Post-recovery: run R-07 to validate downstream row counts.

### Integration with dbt Observability Plan

`docs/dbt-observability-metrics-plan.md` defines the prerequisite dbt metrics required
before dbt burn-rate alerts can be implemented. The dependency chain is:

```
feat/dbt-metric-emission-script (implements push_dbt_metrics.py)
  → dbt_run_failure_count and dbt_test_failure_count emitted to Cloud Monitoring
    → Burn-rate calculation possible
      → feat/dbt-alert-policies (implements Terraform alert policy resources)
```

Burn-rate alerting for the dbt layer is impossible until `push_dbt_metrics.py` emits
the prerequisite metrics. Designing the burn-rate policy now (as done in Section 9) does
not require the metrics to exist; the policy definitions are implementation targets.

---

## 13. Relationship to Existing Plans

### dbt Observability Metrics Plan (`docs/dbt-observability-metrics-plan.md`)

**Dependency:** dbt burn-rate alerts (Section 9) require `dbt_run_failure_count`,
`dbt_test_failure_count`, and `dbt_model_freshness_lag_minutes` to be emitted to Cloud
Monitoring. These metrics are not yet implemented. The prerequisite branch is
`feat/dbt-metric-emission-script`.

Without these metrics, the dbt burn-rate alert policies defined in this document cannot
be applied. The burn-rate policy design (thresholds, windows, severity, notification path)
is documented here and can be implemented directly once the metrics exist.

### Replay/Backfill Strategy (`docs/replay-backfill-strategy.md`)

**Dependency:** BigQuery freshness burn-rate alerts may fire after a failed append window.
The replay runbooks (R-01 through R-07) are the recovery paths. Burn-rate alerting provides
the detection signal; the replay strategy provides the recovery mechanism. Neither replaces
the other.

### Staging Environment Plan (`docs/staging-environment-plan.md`)

**Dependency:** Staging burn-rate alerts require environment labels on all custom metrics.
The staging plan establishes that all custom metrics must include an `environment` label
(`staging` or `prod`). A burn-rate alert policy targeting `environment = "prod"` must not
fire on staging errors. This label requirement must be implemented before staging and
production SLOs can be tracked independently.

Until staging exists, all SLO calculations apply to the single production-equivalent
environment only.

### Deploy-on-Merge Decision Record (`docs/deploy-on-merge-decision-record.md`)

**Integration:** The proposed promotion-gate model in the deploy-on-merge decision record
specifies that production deploys must include a post-deploy PLAN_EXIT=0 check and API
health check. This should be extended to include an SLO state check: confirm that no
burn-rate alert is OPEN before promoting to production. An open burn-rate alert during
a promotion attempt must block the production deploy.

### Dataflow Decision Record (`docs/dataflow-decision-record.md`)

**Non-dependency:** Dataflow is not required for SLO burn-rate monitoring. Burn-rate
alerting applies to the Cloud Run worker path (which is the current validated architecture)
and can be implemented entirely without Dataflow. If Dataflow is implemented in a future
branch, new SLIs for Dataflow pipeline health (system lag, backlog bytes, throughput) would
be added to the SLO framework defined here.

### Cost-Performance Summary (`docs/cost-performance-summary.md`)

**Context:** The cost-performance summary documents that Cloud SQL is the single largest
always-on cost driver. The Cloud SQL safe-state violation alert (Section 9) is the direct
cost-control complement to the SLO framework: if Cloud SQL is accidentally left running,
the cost-control SLO is breached. This alert has higher urgency than most SLO alerts
precisely because unexpected Cloud SQL activity incurs immediate and unbounded cost.

---

## 14. Implementation Roadmap

### P0 -- Docs-Only Plan (This Branch)

| Item | Branch | Files changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| SLO burn-rate monitoring plan | `docs/slo-burn-rate-monitoring-plan` | `docs/slo-burn-rate-monitoring-plan.md`, `docs/EVIDENCE_INDEX.md` | NO | NO | NONE | This document; EVIDENCE_INDEX updated |

### P1 -- dbt Metric Emission (Prerequisite for dbt Burn-Rate)

| Item | Branch | Files likely changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| dbt run/test/duration metrics | `feat/dbt-metric-emission-script` | `scripts/push_dbt_metrics.py`, `dbt/entrypoint.sh` | NO (metrics emitted without run) | YES (IAM: `roles/monitoring.metricWriter` for dbt SA) | LOW | `dbt_run_failure_count`, `dbt_test_failure_count`, `dbt_run_duration_seconds` confirmed in Cloud Monitoring |

### P2 -- SLI Calculation Script and Burn-Rate Metric Emission

| Item | Branch | Files likely changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| Worker SLI ratio calculation | `feat/worker-sli-metric-emission` | `scripts/push_worker_sli_metrics.py` | NO | YES (IAM for metric writer) | LOW | `worker_success_rate` time series in Cloud Monitoring; burn-rate calculation possible |
| dbt freshness metric | `feat/dbt-freshness-metric` | `scripts/push_dbt_freshness.py` | YES (requires `MAX(updated_at)` query) | MINOR | LOW (bounded Cloud SQL window) | `dbt_model_freshness_lag_minutes` in Cloud Monitoring |

### P3 -- Cloud Monitoring Burn-Rate Alert Policies via Terraform

| Item | Branch | Files likely changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| Worker error budget burn-rate alerts | `feat/worker-burn-rate-alert-policies` | `infra/terraform/gcp/monitoring.tf` | NO | YES | LOW (Terraform apply for alert policies) | Fast-burn and slow-burn alert policies deployed; controlled failure and recovery runs; email delivery confirmed |
| BigQuery quality burn-rate alerts | `feat/bigquery-quality-burn-rate-alerts` | `infra/terraform/gcp/monitoring.tf` | NO | YES | LOW | BigQuery quality burn-rate alert deployed; incident triggered in controlled failure |
| dbt burn-rate alert policies | `feat/dbt-burn-rate-alert-policies` | `infra/terraform/gcp/monitoring.tf` | NO | YES | LOW | Alert policies deployed; controlled failure and recovery |
| Safe-state violation alerts | `feat/safe-state-violation-alerts` | `infra/terraform/gcp/monitoring.tf`, `scripts/push_safe_state_metrics.py` | NO | YES | LOW | Cloud SQL and scheduler state metrics emitted; alert policies active |

### P4 -- SLO Dashboard

| Item | Branch | Files likely changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| SLO status dashboard | `feat/slo-dashboard` | `infra/terraform/gcp/dashboards/rtdp-slo-status.json` | NO | YES | LOW | Dashboard visible in Cloud Monitoring; error-budget panels populated |

### P5 -- Controlled Failure Drill and Incident Delivery Proof

| Item | Branch | Files likely changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| Burn-rate alert incident drill | `exec/burn-rate-drill-evidence` | `docs/burn-rate-drill-evidence.md` | Potentially YES (if worker drill requires events) | NO | LOW (bounded event injection) | Controlled failure produces burn-rate alert OPEN state; email notification delivered; incident closed after recovery; PLAN_EXIT=0 |

### P6 -- Staging/Production Label Split

| Item | Branch | Files likely changed | Cloud SQL required | Terraform apply required | GCP cost risk | Expected evidence |
|---|---|---|---|---|---|---|
| Environment label on all metrics | `feat/staging-environment-phase-1` | All metric emission scripts; Terraform monitoring resources | NO | YES | LOW | All custom metrics include `environment` label; staging alerts use `environment="staging"` filter; no staging alerts reach production notification channel |

---

## 15. Production-Likeness Assessment

### What Is Production-Like Today

| Capability | Assessment |
|---|---|
| Observability foundation | Strong -- 4 logs-based metrics with datapoints; 5 BigQuery quality metrics; 4-panel dashboard; structured JSON logs |
| Alerting loop | Strong -- threshold alert → Cloud Monitoring incident → email notification delivery proven end-to-end for BigQuery quality |
| Incident severity classification | Good -- SEV1/SEV2/SEV3 defined in `SLO_AND_INCIDENT_RESPONSE.md`; runbooks for each incident type |
| SLO documentation | Adequate -- production-light SLO targets, error budget concept, and incident response documented |
| Idempotent processing | Strong -- `ON CONFLICT(event_id) DO NOTHING` proven at 50,000 events; 0 duplicates |
| Terraform IaC | Strong -- 100% GCP resource coverage; zero-diff discipline; `prevent_destroy` guards |
| CI discipline | Strong -- 257 tests; ruff; dbt compile/run/test; Terraform plan on every push |
| Cost-control discipline | Strong -- Cloud SQL NEVER/STOPPED verified across 60+ evidence documents; schedulers PAUSED |

### What Remains Portfolio-Grade

| Gap | Assessment |
|---|---|
| No burn-rate alert policies implemented | The most critical SRE gap; threshold-only alerts are operational but not burn-rate aware |
| No SLO dashboard implemented | No error-budget view; no burn-rate trend panels |
| No automated error-budget calculation | Error budget is a conceptual framework only; no calculation is automated |
| No dbt-specific metrics | Transformation layer is a monitoring blind spot; dbt failures are only detectable via Cloud Run job exit code |
| No staging/prod SLO split | All metrics are from a single environment; no environment-labelled SLOs |
| No continuous production traffic | All validation runs are bounded windows; no multi-day SLO window is meaningful |
| Cloud SQL STOPPED/NEVER by default | Correct for cost control; not a production availability posture |
| No on-call rotation | Portfolio project; no rotating on-call schedule; no escalation path beyond email |

### What Enterprise Production Would Still Require

- True SLO burn-rate alerting with production on-call paging (PagerDuty or equivalent).
- SLO compliance reports for management review.
- Automated error-budget freeze: feature deployments blocked when error budget < 20%.
- Multi-day SLO compliance window with continuous production traffic.
- Staging/production environment separation with independent SLO tracking.
- Disaster recovery validation with documented RTO/RPO.
- Security certification (SOC 2, ISO 27001).
- Multi-region high-availability topology.
- Exactly-once streaming write semantics (requires Dataflow or equivalent).

### What Can Be Safely Said in Interviews

- "I documented a rigorous SLO burn-rate monitoring strategy including proposed SLIs for
  every layer, conservative production-light SLO targets, an error budget model that
  accounts for the platform's intentionally bounded operation, and a multi-window
  multi-burn-rate alerting design."
- "The current alerting uses threshold-only policies. I documented why burn-rate alerting
  is superior and designed the implementation path from the existing metric foundation."
- "I have threshold alerts, proven incident creation, and proven email delivery. The
  burn-rate alerting layer is designed and documented; implementing it follows a clear
  phased roadmap."
- "The platform is portfolio-grade, not continuous-production. I do not claim enterprise
  SRE maturity. I claim a production-like SRE strategy with honest evidence."

---

## 16. Devil's Advocate Review

### "Are these real SLOs or just documentation?"

**Honest answer:** These are documented SLO targets, not enforced SLO compliance.
The production-light SLOs in `SLO_AND_INCIDENT_RESPONSE.md` are supported by measured
evidence (50,000-event run, sustained 10 eps, dbt execution). The proposed SLOs in this
document are forward-looking targets without continuous measurement. Calling them "real SLOs"
requires acknowledging that: (a) the measurement window is bounded, not continuous; (b) the
error budget calculation is manual; and (c) burn-rate alerting is not yet implemented.
The honest answer to "is this production SRE?" is: the strategy is production-grade; the
implementation is portfolio-grade.

### "Where is the burn-rate alerting actually implemented?"

**Honest answer:** It is not implemented. The existing alert policies use static thresholds
(`worker_message_error_count > 0`). This document designs the burn-rate alerting layer
in full detail — SLI formulas, window combinations, burn-rate thresholds, alert policy
specifications — but the Terraform resources for these policies do not exist. The
implementation path is `feat/worker-burn-rate-alert-policies` in the P3 roadmap.

### "Can you claim production SRE maturity?"

**Honest answer:** Partial. The SRE foundations are production-like: structured observability,
proven alerting loop, incident severity classification, incident runbooks, evidence-first
discipline. What is not production-like: no burn-rate alerting, no automated error-budget
calculation, no continuous production traffic, no on-call rotation, no staging/prod split.
The claim is "production-like SRE strategy with portfolio-grade implementation," not
"production SRE maturity."

### "How do you avoid alert fatigue?"

**Honest answer:** With the current threshold-only alerts, alert fatigue is managed by
having only three alert policies and by limiting controlled failure injection. In the proposed
burn-rate design, alert fatigue is avoided structurally: the multi-window condition
(requiring both a short window and a long window to show high burn rate simultaneously)
eliminates single-event false positives. The page-vs-ticket distinction further controls
noise: most alerts are ticket-worthy; only cost-control violations are page-worthy in
portfolio mode.

### "What happens when Cloud SQL is intentionally stopped?"

**Honest answer:** Cloud SQL being STOPPED/NEVER is the expected and correct state. SLOs
that depend on Cloud SQL (worker success rate, dbt run success) only apply during
declared bounded validation windows. An absence-of-data condition in Cloud Monitoring
when no events are flowing is not an SLO breach. The error budget model in Section 7
explicitly addresses this: budget consumption only occurs during active ingestion windows.
The safe-state violation alert (Section 9) fires only when Cloud SQL is RUNNABLE
*unexpectedly* outside a declared window.

### "What makes this different from simple threshold alerts?"

**Honest answer:** Three structural differences. First, burn-rate alerts fire based on
the rate of error budget consumption, not on absolute error counts. A single error in
18,000 events consumes 0.0056% of the budget — not enough to trigger a burn-rate alert.
Second, the multi-window condition (both short and long windows must confirm the burn rate)
eliminates transient spikes from triggering alerts. Third, the burn-rate threshold is
calibrated to the SLO window: a 14× burn rate for a 30-day SLO means the budget will be
exhausted in approximately 50 hours — soon enough to warrant a page, but not triggered
by momentary noise.

---

## 17. Explicit Non-Claims

The following capabilities are **NOT** implemented and must not be claimed:

| Non-claim | Status |
|---|---|
| No burn-rate alert policies are implemented | CONFIRMED NOT IMPLEMENTED -- existing policies are threshold-only |
| No SLO dashboard is implemented | CONFIRMED NOT IMPLEMENTED -- only the `RTDP Pipeline Overview` dashboard exists |
| No contractual SLA is claimed | CONFIRMED -- this platform defines production-light SLOs only; no SLA with external parties |
| No automated error-budget calculation is implemented | CONFIRMED NOT IMPLEMENTED -- error budget is a documented concept; no calculation script or Cloud Monitoring SLO resource exists |
| No dbt SLO metrics are implemented | CONFIRMED NOT IMPLEMENTED -- dbt run/test/freshness metrics are not emitted to Cloud Monitoring |
| No staging/prod SLO split is implemented | CONFIRMED -- single GCP environment; no `environment` label on metrics; no staging SLO |
| No multi-day SLO compliance history is proven | CONFIRMED -- all validation runs are bounded windows; no rolling 7-day or 30-day compliance window is supported by current evidence |
| No automated remediation is implemented | CONFIRMED NOT IMPLEMENTED -- all incident response is manual; no Cloud Workflows or automated recovery triggered by alerts |
| No production on-call rotation is implemented | CONFIRMED -- portfolio project; no rotating on-call schedule; single email notification channel |
| No Dataflow SLOs are implemented | CONFIRMED -- Dataflow is not implemented per `docs/dataflow-decision-record.md`; no Dataflow-specific SLIs exist |
| No latency SLO is implemented as a continuous Cloud Monitoring metric | CONFIRMED -- p50/p95/p99 latency is computed offline from producer artifact / worker log join; no continuous latency time-series in Cloud Monitoring |
| No Cloud SQL or scheduler state Cloud Monitoring metrics exist | CONFIRMED -- safe-state compliance is verified manually; no automated detection |
| No Google Cloud SLO resource (native SLO object) is created | CONFIRMED -- no `google_monitoring_slo` Terraform resource exists; proposed alerts use `google_monitoring_alert_policy` only |

---

## 18. Safe Recruitment Positioning

### Recruiter-Facing Paragraph

The Real-Time Data Platform includes a rigorous SLO burn-rate monitoring strategy that
extends its proven observability foundation (4 logs-based Cloud Monitoring metrics, 5
BigQuery quality custom metrics, 3 alert policies, and a proven quality-failure-to-email
alerting loop) into a full SRE-grade burn-rate design. The strategy defines SLIs for every
platform layer — ingestion, worker, analytical quality, transformation, and infrastructure
— proposes production-light SLO targets calibrated to the platform's bounded operating model,
and designs a multi-window multi-burn-rate alerting framework with explicit page-vs-ticket
policy. The observability design is documented and phased; burn-rate alert policies are the
next implementation target following dbt metric emission.

### Technical Interview Paragraph

The current alerting stack uses threshold-only policies: `worker_message_error_count > 0`
and `BigQuery failed_checks_count > 0`. I designed a burn-rate alerting upgrade using the
multi-window model: fast-burn (5-minute / 1-hour windows, 14× threshold), medium-burn
(30-minute / 6-hour windows, 6× threshold), and slow-burn (2-hour / 24-hour windows, 2×
threshold). The burn-rate threshold is calibrated to SLO budget exhaustion time: at 14×
burn on a 30-day 99% SLO, the budget exhausts in approximately 50 hours, which is the
correct detection horizon for a page-worthy alert. The existing `RTDP Operator Email Alerts`
notification channel (proven for incident delivery in `bigquery-quality-incident-notification-delivery-proof.md`)
would be reused. The implementation dependency is `feat/dbt-metric-emission-script`, which
adds the dbt metrics required for the transformation-layer burn-rate policies.

### Senior Reviewer Caveat Paragraph

For senior technical reviewers: this document designs a production-grade SLO burn-rate
strategy but implements none of it. The current alert policies are static thresholds, not
burn-rate-aware. Error budget calculation is manual and conceptual. The platform processes
events only during bounded validation windows, which means rolling SLO windows (7 days,
30 days) have very small denominators and are structurally fragile for percentage-based
calculations. The Cloud SQL STOPPED/NEVER default and the scheduler PAUSED defaults are
correct cost-control postures but are incompatible with continuous-production SLO semantics.
The honest assessment: this is a well-designed SRE strategy for a portfolio project that
demonstrates the correct conceptual framework without claiming a running production system.

---

## 19. Final Recommendation

### This Branch Closes the SLO Burn-Rate Monitoring Gap as Documentation

`docs/slo-burn-rate-monitoring-plan` provides the full SRE strategy for burn-rate monitoring
on the Real-Time Data Platform. It:

- Defines 16 SRE terms including SLO, SLI, SLA, error budget, burn rate, and
  multi-window multi-burn-rate alerting.
- Documents the current observability baseline for all 10 existing metrics and evidence
  artifacts.
- Classifies the SLO coverage gap register across 13 SLI categories.
- Proposes 14 SLIs with formulas, source metrics, targets, and caveats.
- Defines 8 production-light SLO targets calibrated to the bounded operating model.
- Designs the error budget model for both event-based and time-based budgets, including
  correct handling of intentionally paused schedulers and stopped Cloud SQL.
- Explains the structural superiority of burn-rate alerting over threshold-only alerting.
- Designs three alert windows (fast, medium, slow) with burn-rate thresholds and severity.
- Specifies 8 proposed burn-rate alert policies with conditions, windows, severities,
  notification paths, and operator actions.
- Defines a page-vs-ticket policy matrix with 14 conditions.
- Proposes a 10-panel SLO dashboard.
- Maps burn-rate alerts to incident response, rollback strategy, replay/backfill, and
  dbt observability.
- Documents the relationship to all 5 related plans with explicit implementation dependencies.
- Provides a 6-phase implementation roadmap (P0–P6).
- Provides an honest production-likeness assessment.
- Includes 6 devil's advocate answers.
- States 13 explicit non-claims.
- Provides honest and accurate recruitment positioning.

### Next Implementation Path Depends on Priority

**Option A: `feat/dbt-metric-emission-script`** -- if the priority is completing the
observability story. This branch implements `push_dbt_metrics.py`, enabling dbt run/test
metrics in Cloud Monitoring. It is the prerequisite for dbt burn-rate alert policies.
Follows the proven `push_bigquery_quality_metrics.py` pattern. No Cloud SQL start required.
Terraform apply scope: IAM binding only.

**Option B: `feat/staging-environment-phase-1`** -- if the priority is environment separation.
This branch implements same-project prefixed staging resources. Once staging exists,
environment labels can be added to all metrics, enabling independent staging/production
SLO tracking. The staging plan is the prerequisite for deploy-on-merge and for the P6
roadmap phase.

**Option C: `docs/cloud-sql-backup-restore-plan`** -- if the priority is continuing
docs-hardening. This branch documents the Cloud SQL backup configuration, retention window,
and a bounded restore drill plan, closing the disaster recovery documentation gap identified
in `docs/replay-backfill-strategy.md`.

### Do Not Implement Dataflow Yet

Dataflow remains deferred per `docs/dataflow-decision-record.md`. The SLO burn-rate
strategy is complete without Dataflow. If Dataflow is implemented in a future branch,
Dataflow-specific SLIs (pipeline system lag, backlog bytes, throughput) should be added
to the framework defined in this document.

### Do Not Enable Deploy-on-Merge Yet

Deploy-on-merge is deferred per `docs/deploy-on-merge-decision-record.md`. The proposed
SLO state check that should gate production deploys (no open burn-rate alert before promote)
requires burn-rate alert policies to exist first.

### Keep Cloud SQL STOPPED/NEVER and Schedulers PAUSED

The Cloud SQL and scheduler safe states are not impacted by this documentation branch.
Cloud SQL remains `NEVER / STOPPED`. Both schedulers remain `PAUSED`. These states are
the correct defaults for this portfolio project and must be preserved throughout all
future documentation and implementation branches unless a bounded, scoped activation window
is explicitly declared and documented.

---

## Validation Commands

```bash
git diff --check
uv run pytest -q
uv run ruff check .
terraform fmt -check -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"
grep -En "slo-burn-rate-monitoring-plan|PLAN -- SLO burn-rate" docs/EVIDENCE_INDEX.md
grep -En "SLO|SLI|Error Budget|Burn-Rate|Burn Rate|Alerting|Page|Ticket|Dashboard|Incident|Devil|Explicit Non-Claims|Final Recommendation" docs/slo-burn-rate-monitoring-plan.md
gcloud sql instances describe rtdp-postgres --project=project-42987e01-2123-446b-ac7 --format="table(name,state,settings.activationPolicy)"
gcloud scheduler jobs list --project=project-42987e01-2123-446b-ac7 --location=europe-west1 --format="table(id,state,schedule)"
git status --short --branch
```

---

## Evidence Links

| Document | Purpose |
|---|---|
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | Production-light SLO targets; incident severity levels; incident runbooks -- extended by this plan |
| [docs/cloud-logs-based-metrics-validation.md](cloud-logs-based-metrics-validation.md) | Four logs-based metrics created and confirmed |
| [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) | Datapoints confirmed for worker and silver refresh success counters |
| [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) | Two alert policies enabled; email channel attached -- the threshold-only baseline extended by this plan |
| [docs/bigquery-quality-cloud-monitoring-alert-policy-evidence.md](bigquery-quality-cloud-monitoring-alert-policy-evidence.md) | BigQuery quality alert policy deployed; incident trigger validated |
| [docs/bigquery-quality-incident-notification-delivery-proof.md](bigquery-quality-incident-notification-delivery-proof.md) | Quality failure → Cloud Monitoring incident OPEN → email delivery proven end-to-end |
| [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md) | 4-panel RTDP Pipeline Overview dashboard -- current threshold-based dashboard |
| [docs/steady-state-10eps-30min-cloud-validation-evidence.md](steady-state-10eps-30min-cloud-validation-evidence.md) | 10 eps for 30 min; 18,000 events; p50/p95/p99 latency evidence |
| [docs/load-test-50000-cloud-evidence.md](load-test-50000-cloud-evidence.md) | 50,000-event bounded cloud load test; 0 errors; 0 duplicates |
| [docs/dbt-observability-metrics-plan.md](dbt-observability-metrics-plan.md) | dbt metrics plan -- prerequisite for dbt burn-rate alerts |
| [docs/replay-backfill-strategy.md](replay-backfill-strategy.md) | Replay/backfill runbooks -- recovery paths after burn-rate alert fires |
| [docs/staging-environment-plan.md](staging-environment-plan.md) | Staging plan -- prerequisite for environment-labelled SLOs |
| [docs/deploy-on-merge-decision-record.md](deploy-on-merge-decision-record.md) | Deploy-on-merge -- SLO state check should gate production promotion |
| [docs/dataflow-decision-record.md](dataflow-decision-record.md) | Dataflow deferred -- SLO framework does not require Dataflow |
| [docs/cost-performance-summary.md](cost-performance-summary.md) | Cost drivers; Cloud SQL STOPPED/NEVER; resource sizing |
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog -- 60+ documents indexed |
| [docs/market-value-gap-audit-2026-2027.md](market-value-gap-audit-2026-2027.md) | Gap audit; SLO burn-rate monitoring identified as a high-value documentation gap |
