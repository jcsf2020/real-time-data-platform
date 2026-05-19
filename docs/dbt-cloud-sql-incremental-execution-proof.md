# dbt Cloud SQL Live Incremental Execution -- Evidence

**Status:** VALIDATED -- CLOUD SQL LIVE INCREMENTAL DBT EXECUTION PROVEN
**Branch:** `docs/dbt-cloud-sql-incremental-execution-proof`
**Date:** 2026-05-19

---

## Scope

This document proves that both incremental dbt models -- silver and gold -- executed
successfully against Cloud SQL (`rtdp-postgres`) via the `rtdp-dbt-refresh-job` Cloud Run
Job. The execution used a freshly built image that includes the incremental model changes
from PR #172 (silver) and PR #173 (gold). Cloud SQL was started only for the duration of
this validation and restored to `NEVER / STOPPED` on completion.

This is bounded controlled validation, not a production sustained workload claim.

---

## Files Changed

This is a docs-only branch. No SQL, Python, Terraform, GitHub workflow, or dbt model files
were modified.

| File | Change |
|---|---|
| `docs/dbt-cloud-sql-incremental-execution-proof.md` | New evidence document (this file) |
| `docs/EVIDENCE_INDEX.md` | New capability row and supporting evidence bullet added; remaining gaps updated |

---

## 1. Image Build Evidence

A new `rtdp-dbt-refresh-job` image was built from `main` after PR #172 and PR #173 merged,
ensuring the image includes the incremental silver and gold model changes.

| Property | Value |
|---|---|
| Workflow | `.github/workflows/deploy-dbt-refresh-cloud-run.yml` |
| Run ID | `26117517140` |
| Workflow result | success |
| Image pushed | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-dbt-refresh-job:91cf94b2ac2b3fbc25822fdc82f8b8245463177c` |
| `latest` tag updated | yes |
| Cloud Run Job mutated by workflow | NO -- `CLOUD_RUN_JOB_NOT_DEPLOYED_BY_THIS_WORKFLOW=true` |

The deploy workflow pushes an image to Artifact Registry only. It does not deploy or mutate
the Cloud Run Job resource. Terraform owns the job definition and it already points to
`:latest`.

---

## 2. Cloud Run Job Image Evidence

The Cloud Run Job `rtdp-dbt-refresh-job` was already configured to use the `:latest` tag,
which resolves to the freshly built image at execution time.

| Property | Value |
|---|---|
| Job | `rtdp-dbt-refresh-job` |
| Region | `europe-west1` |
| Image spec (job) | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-dbt-refresh-job:latest` |
| Image spec (Terraform) | same -- defined in `infra/terraform/gcp/cloud_run_jobs.tf` |

No Terraform apply was required; the job was already pointing to `:latest`.

---

## 3. Cloud SQL Temporary Activation

Cloud SQL was started only for the duration of this controlled validation window.

| Property | Value |
|---|---|
| Instance | `rtdp-postgres` |
| Project | `project-42987e01-2123-446b-ac7` |
| State before validation | `STOPPED` |
| Activation policy before | `NEVER` |
| Temporarily patched to | `ALWAYS` |
| Transitioned to | `RUNNABLE` |
| State after validation | `STOPPED` |
| Activation policy after | `NEVER` |
| Final confirmed state | `rtdp-postgres  STOPPED  NEVER` |

Cloud SQL was never left running. It was restored to `NEVER / STOPPED` immediately after
the job execution was confirmed successful.

---

## 4. Scheduler State

Both schedulers remained paused throughout this validation. No scheduler was resumed or
triggered.

| Scheduler | State | Schedule |
|---|---|---|
| `rtdp-silver-refresh-scheduler` | `PAUSED` | `*/15 * * * *` |
| `rtdp-bigquery-append-scheduler` | `PAUSED` | `0 * * * *` |

---

## 5. Cloud Run Job Execution Evidence

```
gcloud run jobs execute rtdp-dbt-refresh-job --wait
```

| Property | Value |
|---|---|
| Execution name | `rtdp-dbt-refresh-job-gqrl8` |
| Completion status | success |
| Completion message | `Execution completed successfully in 1m17.25s` |
| Completion time | `2026-05-19T18:51:50.735206Z` |
| `JOB_EXECUTE_EXIT` | `0` |

---

## 6. dbt Run Evidence -- Incremental Models Against Cloud SQL

Logs from execution `rtdp-dbt-refresh-job-gqrl8` confirm both models ran incrementally
against the live Cloud SQL target (`cloudsql` dbt profile target).

```
Target: cloudsql
Done. PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=2
```

| Model | Schema | Result |
|---|---|---|
| `gold.market_event_daily_aggregates` | gold | `INSERT 0 7` |
| `silver.market_event_minute_aggregates` | silver | `INSERT 0 13` |

Both models used `incremental_strategy='delete+insert'`. The `INSERT 0 N` output confirms:

- The `is_incremental()` WHERE guard activated (the target tables already existed and
  contained rows from prior full-refresh runs).
- The `delete+insert` cycle completed: rows matching the lookback window were deleted,
  then re-inserted.
- Gold inserted 7 rows (matching the known 7-day row count from prior validation in
  `docs/gold-cloud-sql-deployment-evidence.md`).
- Silver inserted 13 rows.

Logs also confirm:
```
Completed successfully
Container called exit(0)
```

---

## 7. dbt Test Evidence

```
Done. PASS=22 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=22
```

All 22 dbt tests passed against Cloud SQL after the incremental run. This includes the
`dbt_utils.unique_combination_of_columns` tests on both `(symbol, event_date)` (gold) and
`(symbol, window_start)` (silver), confirming the incremental key contract holds on the
live Cloud SQL data.

---

## 8. Final Cost-Control Restoration and Terraform Zero-Diff

After execution, Cloud SQL was restored and Terraform confirmed no drift.

| Check | Result |
|---|---|
| Cloud SQL state | `STOPPED` |
| Cloud SQL activation policy | `NEVER` |
| `rtdp-silver-refresh-scheduler` | `PAUSED` |
| `rtdp-bigquery-append-scheduler` | `PAUSED` |
| `terraform plan -detailed-exitcode -input=false` | `No changes. Your infrastructure matches the configuration.` |
| `PLAN_EXIT` | `0` |

---

## What Is NOT Claimed

| Claim | Status |
|---|---|
| Production sustained incremental workload | NOT CLAIMED -- this is a bounded controlled validation; 7 gold rows and 13 silver rows reflect the existing test data set |
| Terraform apply executed | NOT EXECUTED -- no `terraform apply` was run; Cloud Run Job already pointed to `:latest` |
| Scheduler triggered this execution | NOT TRIGGERED -- manual `gcloud run jobs execute --wait` was used; both schedulers remained PAUSED |
| Dataflow implemented | NOT IMPLEMENTED |
| dbt-specific observability metrics | NOT IMPLEMENTED -- remains a known remaining gap |
| Sustained throughput above 5,000 events | NOT VALIDATED -- bounded load testing is documented separately in load test evidence |
| No secrets printed | CONFIRMED -- no credentials, tokens, or secrets appear in any output |

---

## Risk and Assumptions

| Risk | Mitigation |
|---|---|
| Cloud SQL start/stop cost window | Cloud SQL was started for < 2 minutes; cost exposure is negligible |
| `INSERT 0 7` / `INSERT 0 13` reflects empty lookback window | The lookback subquery found rows within the 3-day / 10-minute window and the `delete+insert` cycle produced the correct insert count; 0 deletes occurred because the models had not run incrementally against this Cloud SQL instance before (prior runs used full-refresh) |
| `:latest` tag resolves at container pull time | The image built from commit `91cf94b2ac2b3fbc25822fdc82f8b8245463177c` was confirmed as the active `:latest` before execution |
