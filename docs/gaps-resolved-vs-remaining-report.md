# Gaps Resolved vs Remaining Report

**Status:** CURRENT SNAPSHOT - 2026-05-17
**Branch:** `docs/gaps-resolved-vs-remaining-report`
**Baseline:** 201 tests passed · ruff clean · dbt/profiles.yml absent · Cloud SQL NEVER/STOPPED

---

## Executive Summary

The Real-Time Data Platform is a production-light, evidence-backed GCP data engineering
portfolio project. As of this snapshot, the platform demonstrates a complete event
ingestion and analytical pipeline: Pub/Sub → Cloud Run → Cloud SQL → BigQuery, with full
Terraform IaC coverage, governed dbt transformations, operational observability, and a
validated data quality layer.

The most recent evidence sequence (PRs #127–#139) delivered BigQuery incremental append,
scheduler-triggered execution proof, job-scoped IAM hardening, and a validated manual
GitHub Actions workflow for read-only BigQuery data quality checks. All 6 quality checks
pass against the production dataset. The manual `workflow_dispatch` quality workflow is
**proven**. Scheduled (automated) quality execution is **not yet proven**.

The platform is not a continuously running production service. Every capability is backed
by a scoped runbook and an accepted evidence document. The framing is intentionally
conservative: no overclaiming, no production-scale assertions beyond the evidence.

---

## Current Baseline

| Check | Result |
|---|---|
| `uv run pytest -q` | **201 passed** |
| `uv run ruff check .` | All checks passed |
| `test ! -f dbt/profiles.yml` | `REPO_DBT_PROFILE_ABSENT=true` |
| Terraform plan | `PLAN_EXIT=0` |
| BigQuery quality workflow | Run ID **25982120058** · conclusion: **success** |
| Quality checks | **6/6 passed** · row_count=6120 · staging=0 |
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
      → read-only quality checks (manual workflow_dispatch)

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

### Test Suite Growth

| Milestone | Tests |
|---|---|
| 2026-05 gap audit baseline | 156 |
| Post incremental append | 178 |
| Post scheduler IAM proof | 187 |
| Post quality checks | 197 |
| Post quality workflow proof | **201** |

Tests grew by 45 (29%) during the BigQuery quality evidence sequence without regressions.

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

The following gaps are confirmed as of 2026-05-17. Each entry is ranked by B2B / recruiter
value and implementation feasibility.

| # | Gap | Description | B2B Value | Risk | Priority |
|---|---|---|---|---|---|
| 1 | Scheduled BigQuery quality workflow | Manual `workflow_dispatch` is proven. A scheduled trigger (e.g. `schedule:` cron in the workflow) is **not yet proven**. This is the most natural next step from current state. | High | Low | P0 |
| 2 | Quality failure alerting / notification | No proven path for alerting when a quality check fails. The SLO document and alert policies exist but are not connected to BigQuery quality outcomes. | High | Low | P0 |
| 3 | Analytics layer depth | Current checks cover row count, nulls, uniqueness, accepted values, freshness, staging empty. Volume thresholds, distribution anomalies, and freshness SLA enforcement are not yet implemented. | Medium | Low | P1 |
| 4 | SLO / quality gate alignment | `docs/SLO_AND_INCIDENT_RESPONSE.md` is defined but predates the quality workflow. BigQuery quality signals are not yet wired into formal SLO targets or error budget. | Medium | Low | P1 |
| 5 | Automatic deploy-on-merge (CD) | Both deploy workflows require manual `workflow_dispatch`. No deploy happens automatically on merge to main. | Medium | Low | P2 |
| 6 | Incremental dbt models | Silver and gold models use full-refresh table materialization. Conversion to incremental merge on `(symbol, window_start)` / `(symbol, event_date)` is not yet done. | Medium | Low | P2 |
| 7 | BigQuery quality signals in Cloud Monitoring | The 4-panel dashboard covers pipeline and refresh metrics. BigQuery quality check results are not surfaced as Cloud Monitoring metrics or dashboard panels. | Medium | Low | P2 |
| 8 | Dataflow / streaming enrichment | Pub/Sub → BigQuery via Dataflow for windowed aggregations is not implemented. Cloud Run is the worker; no stateful streaming. | Low | High | P3 |
| 9 | Sustained throughput above 5,000 events | Load tests are bounded bursts only. Sustained steady-state streaming throughput is not validated. | Low | Low | P3 |
| 10 | Multi-environment (staging) | Single GCP project. No staging environment, no canary, no multi-region. | Low | High | P3 |

### Key Distinctions: Proven vs Planned

| Item | Status |
|---|---|
| Manual BigQuery quality workflow (Run ID 25982120058) | **PROVEN** |
| Scheduled (automated) BigQuery quality workflow | **NOT YET PROVEN** |
| Quality check failure alerting / notification | **NOT YET PROVEN** |
| BigQuery data mutation from quality checks | **NOT APPLICABLE** — checks are read-only SELECTs only |
| Cloud SQL started during quality workflow proof | **No** — confirmed absent |
| Scheduler executed during quality workflow proof | **No** — confirmed absent |

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
| GCP breadth | 9 | Pub/Sub, Cloud Run (services + jobs), Cloud SQL, BigQuery, Secret Manager, Artifact Registry, Workload Identity, Cloud Monitoring, Cloud Scheduler all deployed and IaC-managed. Dataflow absent. |
| Real-time / event-driven architecture | 7 | Full Pub/Sub → Cloud Run → Cloud SQL path at 5,000 events. DLQ configured. Incremental append to BigQuery proven. No Dataflow / windowed streaming. Bounded bursts only. |
| IaC maturity | 8 | 100% resources in Terraform. GCS remote state. Zero-diff plans. Workload Identity for CI. Phased import approach documented. |
| dbt / transformation | 8 | 22 dbt tests. CI on every push. Cloud SQL parity confirmed. Scheduler-triggered execution accepted. Stored functions preserved as rollback. Incremental models not yet implemented. |
| Data quality | 7 | 6-check quality script. Manual CI workflow proven (Run ID 25982120058). Artifact report generation confirmed. Scheduled quality execution not yet proven. No alerting on failures. |
| Observability | 7 | 4 logs-based metrics with datapoints. 4-panel dashboard. 2 alert policies. Email notification. DLQ. BigQuery quality signals not in dashboard. No distributed tracing. |
| CI/CD | 7 | CI green on every push (201 tests + ruff). Terraform Plan CI on infra changes. Manual deploy workflows validated. No auto-deploy-on-merge. |
| Reliability / rollback | 7 | DLQ with maxDeliveryAttempts=5. Alert policies enabled. Stored functions as dbt rollback. SLO documented. Not continuously running. |
| Cost control | 9 | Cloud SQL NEVER/STOPPED throughout all evidence. Schedulers PAUSED by default. Manual-only deploys. No unexpected idle compute. |
| Evidence / documentation | 9 | 50+ evidence documents. EVIDENCE_INDEX, ARCHITECTURE_REVIEW, SLO document current. Zero overclaiming. Conservative production-light framing. |
| Enterprise production readiness | 6 | Production-light single-environment platform. Not continuously running. No multi-region. No staging. No real traffic. Appropriate for a portfolio platform at this stage. |

---

## 2026–2028 Relevance

### Why This Stack Stays Relevant

| Trend | Platform Signal |
|---|---|
| GCP remains a dominant hyperscaler for data engineering | Full GCP stack with proven IaC coverage |
| BigQuery adoption continues to grow as primary analytical store | Terraform-managed BigQuery tier with incremental append and quality checks |
| Data quality / data contracts gaining hiring weight | Read-only quality checks with CI workflow, artifact reports, parser hardening |
| dbt adoption now expected at senior DE level | Governed dbt path with 22 tests, CI, scheduler-triggered execution |
| OIDC / keyless CI auth becoming standard | Workload Identity Federation proven and Terraform-imported |
| Medallion architecture standard in lakehouse designs | Bronze/Silver/Gold in Cloud SQL + BigQuery analytical tier |
| IaC-first engineering as senior signal | 100% Terraform, zero-diff plans, GCS state, phased import evidence |

### What Would Increase Relevance Further

- Automated (scheduled) BigQuery quality checks — the single highest-value gap remaining
- Streaming insert path (Pub/Sub → BigQuery direct or via Dataflow) for near-real-time analytics
- dbt incremental materialization — standard production dbt pattern
- Quality alerting / notification pipeline — signals operational maturity

---

## Highest-Value Next Branches

Ranked by B2B impact vs implementation cost:

| # | Branch | Objective | B2B Signal |
|---|---|---|---|
| 1 | `feat/bigquery-quality-scheduled-workflow` or `docs/scheduled-bigquery-quality-plan` | Add scheduled trigger to the BigQuery quality workflow; prove automated execution | Closes manual-only gap; shows operational quality posture, not just one-shot proof |
| 2 | `docs/slo-quality-gates-alignment` | Connect BigQuery quality results to SLO targets and error budget definition | Shows quality gates as an engineering control, not just a script |
| 3 | `feat/bigquery-quality-thresholds` | Add volume threshold checks, freshness SLA enforcement, distribution anomaly detection to the quality script | Upgrades from baseline checks to analytical quality |
| 4 | `docs/portfolio-b2b-narrative` | Consolidate platform evidence into a recruiter-facing one-pager: capabilities, evidence links, honest limitations | Directly accelerates hiring signal |
| 5 | `feat/quality-alert-notification-proof` | Prove that a quality check failure triggers an alert (Cloud Monitoring or GitHub Actions notification) | Shows the alerting loop, which is what production teams care about |

---

## Recommended Execution Order

```
1. feat/bigquery-quality-scheduled-workflow
   ├── Add schedule: trigger to bigquery-quality-checks.yml
   ├── Prove automated execution with CI evidence
   └── Document in docs/bigquery-quality-scheduled-workflow-evidence.md

2. docs/slo-quality-gates-alignment
   ├── Update SLO_AND_INCIDENT_RESPONSE.md with BigQuery quality SLIs
   ├── Link quality workflow run to SLO measurement
   └── No code changes; docs-only branch

3. feat/bigquery-quality-thresholds
   ├── Add row_count_minimum, freshness_sla_hours, distribution checks to script
   ├── Add unit tests for new checks
   └── Run against live BigQuery; commit updated evidence

4. docs/portfolio-b2b-narrative
   ├── One-page recruiter-facing summary: capabilities + evidence links + limitations
   └── Distilled from EVIDENCE_INDEX, this report, and ARCHITECTURE_REVIEW

5. feat/quality-alert-notification-proof
   ├── Prove failure → alert path (Cloud Monitoring policy or workflow notification step)
   └── Document end-to-end alerting chain
```

---

## Risk and Overclaim Guardrails

The following claims must NOT be made from the current evidence:

| Overclaim | Correct Statement |
|---|---|
| "BigQuery quality checks run automatically on a schedule" | Manual `workflow_dispatch` only is proven. Scheduled execution is not yet proven. |
| "Failures trigger alerts" | Alert policies exist for pipeline errors; no proven path from quality check failure to notification. |
| "Cloud SQL was started during the quality workflow proof" | Cloud SQL was NOT started during Run ID 25982120058. |
| "Schedulers were executed during the quality workflow proof" | No schedulers were executed during Run ID 25982120058. |
| "BigQuery data was modified by quality checks" | All quality check SQL is read-only SELECT only. No mutation. |
| "Platform handles production-scale continuous traffic" | Platform operates in bounded validation windows. Cloud SQL is NEVER/STOPPED by default. Not a continuously running production service. |
| "Dataflow is implemented" | Dataflow is not implemented. Cloud Run is the worker; no stateful windowed streaming. |
| "Automated deploy on merge" | Both deploy workflows require manual workflow_dispatch. |

---

## Final Conclusion

The platform has advanced significantly since the 2026-05 gap audit baseline. The evidence
sequence ending with PR #139 delivers:

- **BigQuery incremental append** — cursor-based MERGE, idempotent, PLAN_EXIT=0
- **Scheduler dispatch proof** — two executions with corrected image, exact +3 row delta confirmed
- **Job-scoped IAM hardening** — project-level invoker replaced by two resource-scoped bindings; blast radius minimized
- **6-check read-only quality script** — no mutations, no Cloud SQL start, CI-compatible
- **Manual CI quality workflow** — Run ID 25982120058, conclusion: success, 6/6 checks, artifact confirmed
- **201 tests passing** — 45 new tests added without regressions; ruff clean throughout

The single highest-priority remaining gap is **scheduled (automated) BigQuery quality
execution**. The manual path is fully proven; adding a `schedule:` trigger would close
the most visible operational quality gap and is low-risk given the current workflow is
already green on `workflow_dispatch`.

The platform is at a stage where the evidence base is strong enough to carry a senior
Data Engineer / Data Platform Engineer portfolio review. The recommended investment is
in closing the automated quality loop rather than adding new architectural layers.
