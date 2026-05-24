# Gaps Resolved vs Remaining Report

**Status:** CURRENT SNAPSHOT - 2026-05-18
**Branch:** `docs/refresh-gaps-after-alert-proof`
**Baseline:** 210 tests passed · ruff clean · dbt/profiles.yml absent · Cloud SQL NEVER/STOPPED

---

## Executive Summary

The Real-Time Data Platform is a production-light, evidence-backed GCP data engineering
portfolio project. As of this snapshot, the platform demonstrates a complete event
ingestion and analytical pipeline: Pub/Sub → Cloud Run → Cloud SQL → BigQuery, with full
Terraform IaC coverage, governed dbt transformations, operational observability, and a
validated data quality layer with threshold-based checks and a proven controlled failure path.

The most recent evidence sequence (PRs #145–#151) delivered two new threshold-based quality
checks (`row_count_minimum` always included; `freshness_max_age_hours` skipped when not
supplied), `workflow_dispatch` inputs wired end-to-end into the quality script, and a
controlled failure proof: Run ID **26007909020** concluded `failure` with
`row_count_minimum` failing at threshold 999999999 against observed 6120 rows, artifact
preserved, exit code 1 visible in logs, and the GitHub Actions UI failure surface observable.
Run ID **26007825072** (safe inputs: min_row_count=1) confirmed the passing path.

The GitHub Actions UI failure surface is **proven**. Email notification delivery, GitHub
notification bell delivery, and Cloud Monitoring alerting are **NOT PROVEN**. Real scheduled
event execution is **NOT YET PROVEN**.

The platform is not a continuously running production service. Every capability is backed
by a scoped runbook and an accepted evidence document. The framing is intentionally
conservative: no overclaiming, no production-scale assertions beyond the evidence.

---

## Current Baseline

| Check | Result |
|---|---|
| `uv run pytest -q` | **210 passed** |
| `uv run ruff check .` | All checks passed |
| `test ! -f dbt/profiles.yml` | `REPO_DBT_PROFILE_ABSENT=true` |
| Terraform plan | `PLAN_EXIT=0` |
| BigQuery quality workflow — safe run | Run ID **26007825072** · conclusion: **success** · `row_count_minimum` pass (6120 >= 1) |
| BigQuery quality workflow — controlled failure | Run ID **26007909020** · conclusion: **failure** · `row_count_minimum` fail (6120 < 999999999) · artifact preserved |
| GitHub Actions UI failure surface | **observable** |
| Scheduled trigger (`15 6 * * *`) | present on `main`; scheduled event real execution is NOT YET PROVEN |
| Cloud SQL | `NEVER / STOPPED` |
| Schedulers | Both `PAUSED` |

---

## Architecture at a Glance

```
Producer → Redpanda/Kafka → Consumer → PostgreSQL → FastAPI     [local path]

Pub/Sub (market-events-raw)
  → push subscription
    → Cloud Run Worker (rtdp-pubsub-worker)
      → Cloud SQL (bronze.market_events)
        → FastAPI API (rtdp-api)           [GCP serving path]

Cloud Scheduler (rtdp-silver-refresh-scheduler, PAUSED)
  → Cloud Run Job (rtdp-dbt-refresh-job)
    → dbt run (silver + gold) + dbt test (22 tests)  [transformation path]

Cloud SQL bronze.market_events
  → incremental cursor-based MERGE (rtdp-bigquery-append-job, PAUSED scheduler)
    → BigQuery rtdp_analytics.market_events_raw [analytical path]
      → read-only quality checks (manual workflow_dispatch + schedule cron)
        · row_count_minimum · freshness_max_age_hours (skip when 0)

Cloud Logging → logs-based metrics → alert policies / dashboard  [observability]
```

---

## Gaps Resolved

The following gaps have been resolved and evidenced since the 2026-05 audit baseline.
Each entry names the PR sequence and evidence document.

### BigQuery Incremental Append (PRs #127–#128)

| Item | Detail |
|---|---|
| Implementation | Cursor-based MERGE job (`rtdp-bigquery-append-job` Cloud Run Job) |
| Terraform | Cloud Run Job + staging table (`market_events_raw_staging`) via Terraform; `PLAN_EXIT=0` |
| First run | 6,104 → 6,114 (+10 rows, EVIDENCEUSDT symbol) |
| Second run | Idempotent: 6,114 unchanged, 0 net inserts |
| Staging | Truncated before load and after merge; `num_rows=0` post-job |
| Duplicate check | 0 rows |
| Evidence | `docs/bigquery-incremental-append-evidence.md` |

The incremental append path closes the dual-store architecture gap: new events can be
moved from Cloud SQL to BigQuery without a full reload, cursor-safe and MERGE-idempotent.

### BigQuery Append Scheduler Proof (PRs #129–#130)

| Item | Detail |
|---|---|
| Scheduler | `rtdp-bigquery-append-scheduler`; target `rtdp-bigquery-append-job:run`; `0 * * * *` Europe/Lisbon |
| Proof executions | `p9hkt` + `7pn6g` (corrected image SHA `3e0db6f`) |
| BQ row delta | 6,117 → 6,120 (+3 exact); second run idempotent (6,120 unchanged) |
| Log contract | `source_rows_exported` confirmed (not legacy `rows_appended`) |
| Staging | `num_rows=0` after both runs |
| Duplicate count | 0 |
| Scheduler state | Both schedulers PAUSED after proof |
| Evidence | `docs/bigquery-append-scheduler-proof-evidence.md` |

Cloud Scheduler can dispatch the BigQuery append job with correct image and idempotent results.
The scheduler remains PAUSED — this is proof of dispatch mechanics, not continuous execution.

### Scheduler IAM Hardening (PRs #131–#132)

| Item | Detail |
|---|---|
| Change | Replaced project-level `roles/run.invoker` on `rtdp-scheduler-sa` with two job-scoped `google_cloud_run_v2_job_iam_member` bindings |
| Jobs covered | `rtdp-bigquery-append-job` + `rtdp-dbt-refresh-job` |
| Project-level binding | Removed; confirmed absent via `gcloud projects get-iam-policy` (no rows returned) |
| Blast radius | Reduced from "any Cloud Run resource in project" to exactly the two scheduler targets |
| `rtdp-silver-refresh-job` | No invoker binding (expected; no scheduler targets it) |
| Terraform | `PLAN_EXIT=0` after apply |
| Evidence | `docs/scheduler-job-scoped-iam-proof-evidence.md` |

### BigQuery Quality Checks (PRs #133–#137)

| Item | Detail |
|---|---|
| Script | `scripts/run_bigquery_quality_checks.py` — read-only, no third-party deps, uses `bq` CLI |
| Target | `rtdp_analytics.market_events_raw` + `market_events_raw_staging` |
| Checks | 6: row_count_positive, required_columns_not_null, event_id_unique, event_type_accepted_values, freshness_available, staging_table_empty |
| Local result | 6/6 pass; row_count=6120; staging=0 |
| Mutations | None — all SELECTs |
| Unit tests | 10 tests added; full suite at 197 passed at merge |
| Parser fix | `bq` CLI emits warning prefix before JSON; parser updated to scan for first `[`/`{` (PR #137) |
| Evidence | `docs/bigquery-quality-checks-evidence.md` |

### Manual BigQuery Quality Workflow (PRs #134, #138–#139)

| Item | Detail |
|---|---|
| Workflow | `.github/workflows/bigquery-quality-checks.yml` |
| Trigger | `workflow_dispatch` (manual only) |
| Auth | OIDC / Workload Identity Federation |
| Run ID | **25982120058** |
| Conclusion | **success** |
| Artifact | `bigquery-quality-checks-report/ci-report.json` — downloadable, `status: ok` |
| Checks | **6/6 passed** |
| row_count | 6,120 |
| staging_table_empty | 0 |
| Cloud SQL started | No |
| Scheduler executed | No |
| BigQuery mutated | No |
| Evidence | `docs/bigquery-quality-workflow-proof-evidence.md` |

The manual `workflow_dispatch` BigQuery quality workflow is **proven**. OIDC auth, `bq` CLI
execution, 6 read-only checks, and artifact report generation are all confirmed in CI.

### BigQuery Quality Thresholds (PRs #145–#147)

| Item | Detail |
|---|---|
| New flags | `--min-row-count` (default 1) · `--freshness-max-age-hours` (default 0.0; skipped when ≤ 0) |
| New checks | `row_count_minimum` always included; `freshness_max_age_hours` included when flag > 0 |
| Live result | `row_count_minimum` pass: observed 6120 >= threshold 6000; `freshness_max_age_hours` skipped (flag not supplied) |
| Baseline checks | All 6 preserved and passing |
| Total checks in live report | 7 (6 baseline + `row_count_minimum`) |
| Unit tests added | 13 new tests; focused file: 23 passed |
| Full suite | **210 passed** |
| Mutations | None — all SELECTs |
| BigQuery not mutated | Yes |
| Cloud SQL not started | Yes |
| Cloud Scheduler not executed | Yes |
| Evidence | `docs/bigquery-quality-thresholds-evidence.md` |

`row_count_minimum` is implemented, unit-tested, and live-proven. `freshness_max_age_hours`
is implemented and unit-tested; live pass/fail validation is **NOT YET PROVEN** — the live
run intentionally omitted the flag.

### BigQuery Quality Alert Proof / Controlled Failure (PRs #148–#151)

| Item | Detail |
|---|---|
| Workflow inputs | `min_row_count` (default "1") · `freshness_max_age_hours` (default "0") wired via PR #149 |
| Safe run | Run ID **26007825072** · event: workflow_dispatch · conclusion: **success** · `row_count_minimum` pass (observed 6120 >= 1) · status: ok |
| Controlled failure run | Run ID **26007909020** · event: workflow_dispatch · conclusion: **failure** · `row_count_minimum` fail (observed 6120 < 999999999) · status: error |
| failed_checks | `["row_count_minimum"]` |
| Artifact | Preserved despite failure (`if: always()`) |
| Exit code | 1 visible in failed run logs |
| GitHub Actions UI failure surface | **observable** — red failure badge and step-level failure annotation |
| Baseline checks during failure | All 6 passed — check isolation confirmed |
| BigQuery not mutated | Yes |
| Cloud SQL not started | Yes |
| Cloud Scheduler not executed | Yes |
| Evidence | `docs/bigquery-quality-alert-notification-proof-evidence.md` |

The controlled failure path is **proven**. The GitHub Actions UI failure surface is **proven**.
email notification delivery NOT PROVEN · GitHub notification bell delivery NOT PROVEN ·
Cloud Monitoring alerting NOT PROVEN · real scheduled event execution NOT YET PROVEN.

### SLO Quality Gates Alignment (docs/slo-quality-gates-alignment)

| Item | Detail |
|---|---|
| Document | `docs/slo-quality-gates-alignment.md` |
| Scope | Aligns BigQuery quality checks with existing SLO/incident response model |
| Quality SLIs | 6 SLIs formally defined with severity classifications (P1/P2) |
| Severity model | Extended from existing SLO model; P3/SEV3 targets defined but not yet implemented |
| Incident runbook | Quality gate failure runbook defined; mapped to existing runbooks |
| Alerting gap | Explicitly stated as NOT YET PROVEN |
| Scheduled execution gap | Explicitly stated as NOT YET PROVEN |

### Test Suite Growth

| Milestone | Tests |
|---|---|
| 2026-05 gap audit baseline | 156 |
| Post incremental append | 178 |
| Post scheduler IAM proof | 187 |
| Post quality checks | 197 |
| Post quality workflow proof | 201 |
| Post quality thresholds (PRs #145–#147) | **210** |

Tests grew by 54 (35%) during the BigQuery quality evidence sequence without regressions.

### Previously Resolved (Pre-Sequence Baseline)

| Capability | Evidence |
|---|---|
| Real-time ingestion: Pub/Sub → Cloud Run → Cloud SQL → FastAPI | `gcp-end-to-end-validation.md` |
| Bounded load tests: 100 / 1,000 / 5,000 events | `load-test-*-cloud-evidence.md` |
| Pub/Sub DLQ (`deadLetterPolicy`, maxDeliveryAttempts=5) | `production-pubsub-dlq-evidence.md` |
| dbt transformation layer (22 tests, CI, Cloud SQL parity) | `dbt-cloud-sql-validation-evidence.md` |
| dbt Cloud Run Job deployment + scheduler-triggered execution | `dbt-scheduler-switch-evidence.md` |
| BigQuery analytical tier scaffold (3 Terraform-managed tables) | `bigquery-terraform-apply-evidence.md` |
| BigQuery bounded backfill (6,104 rows, analytical query confirmed) | `bigquery-bounded-backfill-evidence.md` |
| Terraform IaC: 100% GCP resources, GCS remote state, zero-diff plans | All `*-import-plan-evidence.md` |
| Workload Identity Federation (OIDC) for GitHub Actions | `workload-identity-terraform-import-plan-evidence.md` |
| Cloud Monitoring: 4 metrics, 4-panel dashboard, 2 alert policies, email channel | `cloud-monitoring-dashboard-evidence.md` |
| SLO and incident response documentation | `docs/SLO_AND_INCIDENT_RESPONSE.md` |
| Cost control: Cloud SQL NEVER/STOPPED, schedulers PAUSED | Verified throughout all evidence |

---

## Gaps Remaining

The following gaps are confirmed as of 2026-05-18. Each entry is ranked by B2B / recruiter
value and implementation feasibility.

| # | Gap | Description | B2B Value | Risk | Priority |
|---|---|---|---|---|---|
| 1 | Scheduled BigQuery quality workflow — real event execution | Schedule cron `15 6 * * *` is present on `main`. Manual `workflow_dispatch` is proven. A run triggered by a real `event: schedule` has not been observed. Real scheduled event execution is **NOT YET PROVEN**. | High | Low | P0 |
| 2 | Email and bell notification delivery | The GitHub Actions UI failure surface is proven (Run ID 26007909020). Email notification delivery is **NOT PROVEN**. GitHub notification bell delivery is **NOT PROVEN**. No proven path from workflow failure to delivered notification exists. | High | Low | P0 |
| 3 | Cloud Monitoring alerting | Cloud Monitoring does not receive BigQuery quality metrics. No alert policy monitors quality check results. Cloud Monitoring alerting is **NOT PROVEN**. | High | Low | P1 |
| 4 | `freshness_max_age_hours` live validation | `freshness_max_age_hours` is implemented and unit-tested. Live pass/fail validation is **NOT YET PROVEN** — the live run omitted `--freshness-max-age-hours`. | Medium | Low | P1 |
| 5 | Analytics layer depth — distribution anomalies | Current checks cover row count, nulls, uniqueness, accepted values, freshness, staging empty, and volume threshold. Distribution anomalies and advanced freshness SLA enforcement are not yet implemented. | Medium | Low | P2 |
| 6 | Automatic deploy-on-merge (CD) | Both deploy workflows require manual `workflow_dispatch`. No deploy happens automatically on merge to main. | Medium | Low | P2 |
| 7 | Incremental dbt models | Silver and gold models use full-refresh table materialization. Conversion to incremental merge on `(symbol, window_start)` / `(symbol, event_date)` is not yet done. | Medium | Low | P2 |
| 8 | Dataflow / streaming enrichment | Bounded Apache Beam / DataflowRunner proof validated (JOB_STATE_DRAINED; 10 proof rows to rtdp_analytics.market_events_beam_proof; see dataflow-bounded-runner-proof-evidence.md). The previous binary gap "no Dataflow evidence" is closed. Remaining gap: production windowed/stateful Dataflow streaming. No sustained always-on Dataflow pipeline exists. | Low | High | P3 |
| 9 | Sustained throughput above 5,000 events | Load tests are bounded bursts only. Sustained steady-state streaming throughput is not validated. | Low | Low | P3 |
| 10 | Multi-environment (staging) | Single GCP project. No staging environment, no canary, no multi-region. | Low | High | P3 |

### Key Distinctions: Proven vs Planned

| Item | Status |
|---|---|
| Manual BigQuery quality workflow (Run ID 25982120058) | **PROVEN** |
| `workflow_dispatch` inputs wired end-to-end (PR #149) | **PROVEN** |
| Safe input run (Run ID 26007825072): conclusion success, `row_count_minimum` pass | **PROVEN** |
| Controlled failure run (Run ID 26007909020): conclusion failure, `row_count_minimum` fail | **PROVEN** |
| GitHub Actions UI failure surface observable | **PROVEN** |
| Artifact preserved despite workflow failure | **PROVEN** |
| `row_count_minimum` implemented, unit-tested, live-proven | **PROVEN** |
| `freshness_max_age_hours` implemented and unit-tested | **PROVEN** |
| `freshness_max_age_hours` live pass/fail validation | **NOT YET PROVEN** |
| Scheduled (automated) BigQuery quality workflow — real `event: schedule` execution | **NOT YET PROVEN** |
| Email notification delivery on quality failure | **NOT PROVEN** |
| GitHub notification bell delivery on quality failure | **NOT PROVEN** |
| Cloud Monitoring alerting on quality failure | **NOT PROVEN** |
| Cloud Monitoring quality metrics — any emission | **NOT PROVEN** |
| BigQuery data mutation from quality checks | **NOT APPLICABLE** — checks are read-only SELECTs only |
| Cloud SQL started during quality workflow proofs | **No** — confirmed absent in both Run IDs 26007825072 and 26007909020 |
| Scheduler executed during quality workflow proofs | **No** — confirmed absent |

---

## B2B / Recruiter Value

### What This Platform Demonstrates

The platform signals four capabilities that distinguish a senior Data/Platform Engineer
candidate from a junior one:

1. **IaC discipline at 100% coverage.** Every GCP resource is Terraform-managed with
   zero-diff plans and a GCS remote state. No manual console mutations. Workload Identity
   Federation removes stored service account keys from CI. This is the IaC standard a
   senior platform hire is expected to bring, not learn.

2. **Governed transformation with integrated testing.** dbt silver and gold models run
   on Cloud Run, scheduled by Cloud Scheduler (PAUSED), with 22 dbt tests passing in CI
   on every push against an ephemeral pgvector container. The dbt job writes a temporary
   `profiles.yml` at runtime and deletes it after execution — `dbt/profiles.yml` is
   never committed to the repo.

3. **Evidence-first delivery.** Every execution is documented in a scoped runbook and
   evidence file. EVIDENCE_INDEX.md catalogs 50+ evidence documents by category. No
   capability is claimed without a trace. This directly addresses the "how do I know this
   actually works?" question a technical hiring manager asks.

4. **Cost-controlled operational discipline.** Cloud SQL is `NEVER / STOPPED` outside
   bounded windows. Schedulers are `PAUSED` by default. No surprise compute bills. This
   signals awareness of the cost model a real platform engineer must manage.

### Capability Scorecard

| Dimension | Score (0–10) | Basis |
|---|---|---|
| GCP breadth | 9 | Pub/Sub, Cloud Run (services + jobs), Cloud SQL, BigQuery, Secret Manager, Artifact Registry, Workload Identity, Cloud Monitoring, Cloud Scheduler all deployed and IaC-managed. Bounded DataflowRunner proof validated; no production streaming Dataflow. |
| Real-time / event-driven architecture | 7 | Full Pub/Sub → Cloud Run → Cloud SQL path at 5,000 events. DLQ configured. Incremental append to BigQuery proven. Bounded DataflowRunner proof validated; no production windowed Dataflow streaming. Bounded bursts only. |
| IaC maturity | 8 | 100% resources in Terraform. GCS remote state. Zero-diff plans. Workload Identity for CI. Phased import approach documented. |
| dbt / transformation | 8 | 22 dbt tests. CI on every push. Cloud SQL parity confirmed. Scheduler-triggered execution accepted. Stored functions preserved as rollback. Incremental models not yet implemented. |
| Data quality | 8 | 8-check quality script (`row_count_minimum` always included; `freshness_max_age_hours` skipped when 0). Manual CI workflow proven (Run ID 25982120058). Controlled failure proven (Run ID 26007909020). Artifact preserved on failure. GitHub Actions UI failure surface observable. `freshness_max_age_hours` live validation and email/bell/Cloud Monitoring NOT PROVEN. Scheduled execution NOT YET PROVEN. |
| Observability | 7 | 4 logs-based metrics with datapoints. 4-panel dashboard. 2 alert policies. Email notification. DLQ. BigQuery quality signals not in dashboard. No distributed tracing. |
| CI/CD | 7 | CI green on every push (210 tests + ruff). Terraform Plan CI on infra changes. Manual deploy workflows validated. `workflow_dispatch` inputs proven (controlled failure). No auto-deploy-on-merge. |
| Reliability / rollback | 7 | DLQ with maxDeliveryAttempts=5. Alert policies enabled. Stored functions as dbt rollback. SLO documented. Quality gate failure runbook defined. Not continuously running. |
| Cost control | 9 | Cloud SQL NEVER/STOPPED throughout all evidence. Schedulers PAUSED by default. Manual-only deploys. No unexpected idle compute. |
| Evidence / documentation | 9 | 50+ evidence documents. EVIDENCE_INDEX, ARCHITECTURE_REVIEW, SLO document current. Zero overclaiming. Conservative production-light framing. |
| Enterprise production readiness | 6 | Production-light single-environment platform. Not continuously running. No multi-region. No staging. No real traffic. Appropriate for a portfolio platform at this stage. |

---

## 2026–2028 Relevance

### Why This Stack Stays Relevant

| Trend | Platform Signal |
|---|---|
| GCP remains a dominant hyperscaler for data engineering | Full GCP stack with proven IaC coverage |
| BigQuery adoption continues to grow as primary analytical store | Terraform-managed BigQuery tier with incremental append, threshold quality checks, and controlled failure proof |
| Data quality / data contracts gaining hiring weight | Read-only quality checks with CI workflow, artifact reports, parser hardening, threshold-based checks, controlled failure proof |
| dbt adoption now expected at senior DE level | Governed dbt path with 22 tests, CI, scheduler-triggered execution |
| OIDC / keyless CI auth becoming standard | Workload Identity Federation proven and Terraform-imported |
| Medallion architecture standard in lakehouse designs | Bronze/Silver/Gold in Cloud SQL + BigQuery analytical tier |
| IaC-first engineering as senior signal | 100% Terraform, zero-diff plans, GCS state, phased import evidence |

### What Would Increase Relevance Further

- Real scheduled event execution captured — first `event: schedule` GitHub Actions run evidenced
- Email or GitHub bell notification delivery proven on quality failure
- Cloud Monitoring quality metrics — push quality results as custom metrics, alert on failure
- `freshness_max_age_hours` live validation against fresh data
- dbt incremental materialization — standard production dbt pattern

---

## Highest-Value Next Branches

Ranked by B2B impact vs implementation cost:

| # | Branch | Objective | B2B Signal |
|---|---|---|---|
| 1 | `docs/bigquery-quality-scheduled-run-evidence` | Capture the first real `event: schedule` run (cron `15 6 * * *` already on main); confirm `event: schedule` field in run metadata | Closes the scheduled execution gap; shows quality execution is not just manual |
| 2 | `feat/github-notification-delivery-proof` or `docs/github-notification-delivery-evidence` | Prove email or GitHub bell notification delivery when a quality check fails | Closes the email/bell notification gap; shows the alerting loop at the notification layer |
| 3 | `feat/bigquery-quality-cloud-monitoring-metrics` | Push quality check results as custom metrics to Cloud Monitoring; create alert policy on quality failure | Closes the Cloud Monitoring alerting gap; surfaces quality signals in the existing dashboard |
| 4 | `feat/freshness-live-validation` | Execute a live run with `--freshness-max-age-hours` > 0 against data with a known age; prove pass or fail | Closes the `freshness_max_age_hours` live validation gap |
| 5 | `docs/portfolio-b2b-narrative` | Consolidate platform evidence into a recruiter-facing one-pager: capabilities, evidence links, honest limitations | Directly accelerates hiring signal |

---

## Recommended Execution Order

```
1. docs/bigquery-quality-scheduled-run-evidence
   ├── Wait for a real event: schedule run from cron "15 6 * * *"
   ├── Confirm event field == "schedule" (not workflow_dispatch)
   └── Document Run ID, generated_at_utc, artifact ci-report.json

2. feat/github-notification-delivery-proof
   ├── Trigger workflow_dispatch with min_row_count = 999999999
   ├── Capture delivered email at jcsf2020@gmail.com OR GitHub bell entry
   └── Document notification delivery as proven

3. feat/bigquery-quality-cloud-monitoring-metrics
   ├── Push quality check results to Cloud Monitoring custom metrics after each run
   ├── Create alert policy on quality failure metric
   └── Document Cloud Monitoring receives quality metrics

4. feat/freshness-live-validation
   ├── Execute live run with --freshness-max-age-hours > 0
   ├── Confirm pass or expected fail against known data age
   └── Document freshness_max_age_hours as live-proven

5. docs/portfolio-b2b-narrative
   ├── One-page recruiter-facing summary: capabilities + evidence links + limitations
   └── Distilled from EVIDENCE_INDEX, this report, and ARCHITECTURE_REVIEW
```

---

## Risk and Overclaim Guardrails

The following claims must NOT be made from the current evidence:

| Overclaim | Correct Statement |
|---|---|
| "BigQuery quality checks run automatically on a schedule" | Manual `workflow_dispatch` is proven. Real scheduled event execution (cron `15 6 * * *`) is NOT YET PROVEN. |
| "Quality failures trigger email or notification alerts" | GitHub Actions UI failure surface is proven (Run ID 26007909020). Email notification delivery is NOT PROVEN. GitHub notification bell delivery is NOT PROVEN. |
| "Cloud Monitoring monitors quality check results" | Cloud Monitoring does not receive BigQuery quality metrics. Cloud Monitoring alerting is NOT PROVEN. |
| "freshness_max_age_hours is live-proven" | `freshness_max_age_hours` is implemented and unit-tested only. Live pass/fail validation is NOT YET PROVEN. |
| "Cloud SQL was started during the quality workflow proofs" | Cloud SQL was NOT started during Run ID 26007825072 or Run ID 26007909020. |
| "Schedulers were executed during the quality workflow proofs" | No schedulers were executed during Run ID 26007825072 or Run ID 26007909020. |
| "BigQuery data was modified by quality checks" | All quality check SQL is read-only SELECT only. No mutation. |
| "Platform handles production-scale continuous traffic" | Platform operates in bounded validation windows. Cloud SQL is NEVER/STOPPED by default. Not a continuously running production service. |
| "Production streaming Dataflow is implemented" | Bounded Apache Beam / DataflowRunner proof validated (10 proof rows, JOB_STATE_DRAINED; see dataflow-bounded-runner-proof-evidence.md). Production streaming Dataflow is not claimed. No windowed or stateful production Dataflow pipeline exists. No sustained always-on Dataflow pipeline. |
| "Automated deploy on merge" | Both deploy workflows require manual workflow_dispatch. |

---

## Final Conclusion

The platform has advanced significantly since the 2026-05 gap audit baseline. The evidence
sequence through PR #151 delivers:

- **BigQuery incremental append** — cursor-based MERGE, idempotent, PLAN_EXIT=0
- **Scheduler dispatch proof** — two executions with corrected image, exact +3 row delta confirmed
- **Job-scoped IAM hardening** — project-level invoker replaced by two resource-scoped bindings; blast radius minimized
- **6-check read-only quality script** — no mutations, no Cloud SQL start, CI-compatible
- **Manual CI quality workflow** — Run ID 25982120058, conclusion: success, 6/6 checks, artifact confirmed
- **Quality thresholds** — `row_count_minimum` implemented, unit-tested, live-proven (6120 >= 6000); `freshness_max_age_hours` implemented and unit-tested; live validation NOT YET PROVEN
- **Controlled failure proof** — Run ID 26007909020: `row_count_minimum` fail, observed 6120 < 999999999, artifact preserved, exit code 1, GitHub Actions UI failure surface observable
- **SLO quality gates alignment** — 6 quality SLIs formally defined with severity classifications; incident runbook drafted
- **210 tests passing** — 54 new tests added without regressions; ruff clean throughout

Three gaps remain the highest-priority next investments:

1. **Real scheduled event execution** — the cron trigger is on `main`; capturing the first
   `event: schedule` run in `docs/bigquery-quality-scheduled-run-evidence.md` requires no
   code change.
2. **Email or bell notification delivery** — the GitHub Actions failure signal is proven;
   proving that a notification reaches a subscriber closes the most visible alerting gap.
3. **Cloud Monitoring quality metrics** — connecting quality results to Cloud Monitoring
   would close the observability gap and enable alert policies on quality failures.

The platform is at a stage where the evidence base is strong enough to carry a senior
Data Engineer / Data Platform Engineer portfolio review. The controlled failure proof,
threshold checks, and SLO alignment add operational maturity signal that distinguishes
this platform from a one-pass demo.
