# dbt Scheduler Switch Evidence

**Status:** ACCEPTED
**Branch:** `feat/dbt-scheduler-switch`
**Date:** 2026-05-14
**Scheduler:** `rtdp-silver-refresh-scheduler`
**Triggered execution:** `rtdp-dbt-refresh-job-6zb52`

---

## Summary

The Cloud Scheduler job `rtdp-silver-refresh-scheduler` was switched from the legacy stored-function Cloud Run Job target to the Terraform-owned dbt refresh Cloud Run Job target.

The scheduler now targets:

```text
https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-dbt-refresh-job:run
```

The scheduler remains paused by default.

A controlled manual scheduler trigger was executed after temporarily resuming the scheduler. The trigger created a new dbt refresh Cloud Run Job execution, `rtdp-dbt-refresh-job-6zb52`, which completed successfully. The dbt run executed both silver and gold models and dbt test passed all 22 tests.

Cloud SQL was returned to `NEVER / STOPPED` immediately after the validation window.

---

## Terraform Change

File changed:

```text
infra/terraform/gcp/scheduler.tf
```

The scheduler URI was updated from:

```text
.../jobs/rtdp-silver-refresh-job:run
```

To:

```text
.../jobs/rtdp-dbt-refresh-job:run
```

The scheduler remains paused in Terraform:

```hcl
paused = true
```

Terraform apply result:

```text
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

Post-apply Terraform plan:

```text
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

---

## Scheduler State After Apply

GCP scheduler describe confirmed:

```text
PAUSED  https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-dbt-refresh-job:run
```

This confirms:

- Scheduler is paused by default.
- Scheduler now targets `rtdp-dbt-refresh-job:run`.
- The legacy `rtdp-silver-refresh-job:run` target is no longer the scheduler target.

---

## Controlled Scheduler Execution Proof

Cloud SQL was started only for the validation window:

```text
CLOUD_SQL_READY=1
ALWAYS / RUNNABLE
```

The scheduler was temporarily resumed:

```text
Job has been resumed.
```

Manual scheduler trigger succeeded:

```text
SCHED_EXIT=0
```

The scheduler was paused immediately after the manual trigger:

```text
Job has been paused.
```

A new dbt refresh Cloud Run Job execution was created:

```text
BEFORE_EXEC=rtdp-dbt-refresh-job-q6vxp
NEW_EXEC=rtdp-dbt-refresh-job-6zb52
```

Execution status:

```text
Completed=True
1 task completed successfully
Execution completed successfully in 58.05s.
```

Execution details:

```text
Execution rtdp-dbt-refresh-job-6zb52
Image: europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-dbt-refresh-job@sha256:ab84213e252dd9f445ef0d237c1a45ebf9f2a7ead4d6104025c70d32de033d95
Task Timeout: 10m
Service account: rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
SQL connections: project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres
```

---

## dbt Run Evidence

Scheduler-triggered logs confirmed the dbt run executed real models:

```text
2026-05-14T18:36:34.258185Z  rtdp-dbt-refresh-job  dbt_run  dbt run  success
2026-05-14T18:36:33.658944Z  Done. PASS=2 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=2
2026-05-14T18:36:33.658126Z  Completed successfully
2026-05-14T18:36:33.559481Z  2 of 2 OK created sql table model silver.market_event_minute_aggregates ........ [SELECT 256 in 0.11s]
2026-05-14T18:36:33.447754Z  2 of 2 START sql table model silver.market_event_minute_aggregates ............. [RUN]
2026-05-14T18:36:33.446051Z  1 of 2 OK created sql table model gold.market_event_daily_aggregates ........... [SELECT 7 in 0.41s]
2026-05-14T18:36:33.029189Z  1 of 2 START sql table model gold.market_event_daily_aggregates ................ [RUN]
```

This confirms:

- `dbt run` was not a no-op.
- Gold model ran and produced 7 rows.
- Silver model ran and produced 256 rows.

---

## dbt Test Evidence

Scheduler-triggered logs confirmed all dbt tests passed:

```text
2026-05-14T18:36:40.733634Z  rtdp-dbt-refresh-job  dbt_test  dbt test  success
2026-05-14T18:36:40.103867Z  Done. PASS=22 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=22
2026-05-14T18:36:40.103197Z  Completed successfully
```

Final orchestration status:

```text
2026-05-14T18:36:40.733813Z  rtdp-dbt-refresh-job  dbt_run_and_test  success
```

---

## Final Safety State

Final scheduler state:

```text
PAUSED  https://europe-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/project-42987e01-2123-446b-ac7/jobs/rtdp-dbt-refresh-job:run
```

Final Cloud SQL state:

```text
NEVER / STOPPED
```

Git branch state before documentation:

```text
## feat/dbt-scheduler-switch
 M infra/terraform/gcp/scheduler.tf
```

---

## Acceptance Criteria

| Criterion | Result |
|---|---|
| Scheduler URI switched to dbt job | Passed |
| Scheduler remains paused by default | Passed |
| Terraform apply updates only scheduler URI | Passed |
| Terraform plan after apply is zero-diff | `PLAN_EXIT=0` |
| Manual scheduler trigger succeeds | `SCHED_EXIT=0` |
| New dbt job execution created | `rtdp-dbt-refresh-job-6zb52` |
| Execution completed successfully | Passed |
| `dbt run` executed real models | Passed |
| Silver model output | `SELECT 256` |
| Gold model output | `SELECT 7` |
| `dbt test` | `PASS=22 WARN=0 ERROR=0` |
| Final orchestration status | `dbt_run_and_test success` |
| Scheduler returned to paused | Passed |
| Cloud SQL returned to stopped | `NEVER / STOPPED` |

---

## What Remains Pending

The scheduler switch is accepted.

Next recommended branch: update architecture and audit documents to reflect that the dbt refresh path is now the operational scheduled transformation path, while the legacy silver refresh job remains available only as rollback until a later cleanup branch.

