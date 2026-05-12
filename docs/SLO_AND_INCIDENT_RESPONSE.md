# SLO And Incident Response

This document defines production-light SLOs and incident response procedures for the
Real-Time Data Platform (RTDP). These are internal engineering objectives; no contractual
SLA is provided or implied. Scope is the current validated RTDP GCP architecture,
operating as a cost-controlled, evidence-driven portfolio-grade platform.

---

## Scope

This document covers the following RTDP components:

- Cloud Run API (`rtdp-api`)
- Cloud Run Pub/Sub worker (`rtdp-pubsub-worker`)
- Pub/Sub topic (`market-events-raw`), push subscription (`market-events-raw-worker-push`),
  and DLQ topic (`market-events-raw-dlq`)
- Cloud Run silver refresh job (`rtdp-silver-refresh-job`)
- Cloud Scheduler (`rtdp-silver-refresh-scheduler`, PAUSED by default)
- Cloud SQL PostgreSQL (`rtdp-postgres`, activation policy NEVER/STOPPED by default)
- Cloud Monitoring logs-based metrics, alert policies, and 4-panel dashboard
- GitHub Actions CI (`ci.yml`) and manual deploy workflows (`deploy-api-cloud-run.yml`,
  `deploy-worker-cloud-run.yml`)

---

## SLI, SLO, SLA Definitions

- **SLI (Service Level Indicator):** A measured signal used to assess service behaviour.
  Examples: request success rate, error counter value, job completion status.
- **SLO (Service Level Objective):** An internal engineering target set against an SLI.
  SLOs are aspirational and operational; they are not contractual commitments.
- **SLA (Service Level Agreement):** An external contract with defined penalties for breach.

This project defines SLOs only. No SLA is defined or implied.

---

## Production-Light SLO Targets

All targets apply during controlled validation windows only. Outside a validation window,
many components are intentionally stopped (Cloud SQL: NEVER/STOPPED, Scheduler: PAUSED).
Targets reflect the validated state of the current evidence record and must not be read as
claims of continuous production availability.

| Area | SLI | SLO Target | Measurement Source | Evidence |
|---|---|---|---|---|
| API readiness | /readiness HTTP 200 during controlled validation | >= 99% of controlled validation checks pass | API readback; gcp-end-to-end-validation.md | [gcp-end-to-end-validation.md](gcp-end-to-end-validation.md) |
| Worker processing | Valid Pub/Sub messages produce status=ok worker logs | >= 99% valid messages processed per controlled run | worker_message_processed_count; Cloud Logging | [load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) |
| Worker errors | worker_message_error_count > 0 | Zero unexpected worker errors per controlled run | Logs-based metric; RTDP Worker Message Error Alert | [cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md) |
| Silver refresh | silver refresh job exits with status=ok | >= 95% successful controlled executions | silver_refresh_success_count | [silver-refresh-scheduler-execution-proof-evidence.md](silver-refresh-scheduler-execution-proof-evidence.md) |
| Silver refresh errors | silver_refresh_error_count > 0 | Zero unexpected refresh errors per controlled run | Logs-based metric; RTDP Silver Refresh Error Alert | [cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md) |
| DLQ | DLQ message count during valid-event runs | DLQ remains empty during valid-event runs | market-events-raw-dlq; load-test evidence | [production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md) |
| CI | pytest and ruff pass on every PR | 100% green before merge to main | GitHub Actions ci.yml | [.github/workflows/ci.yml](../.github/workflows/ci.yml) |
| Terraform plan | terraform plan returns zero diff or expected additive diff | No unreviewed infrastructure drift before merge | terraform-plan.yml | [.github/workflows/terraform-plan.yml](../.github/workflows/terraform-plan.yml) |

---

## Error Budget

Error budget for this project is conceptual, not a contractual monthly budget.

For each controlled validation window, the branch error budget is defined as:

- Any unexpected `worker_message_error_count > 0` consumes the branch worker error budget.
- Any unexpected `silver_refresh_error_count > 0` consumes the branch refresh error budget.
- Any failed CI run on a PR at merge review consumes the branch CI budget.
- Any `terraform plan` showing unreviewed destructive changes consumes the Terraform budget.
- Any DLQ message during a valid-event run consumes the DLQ budget.

If any branch error budget is consumed, feature work must stop. Root cause must be
identified and documented before any further merge or deploy proceeds.

---

## Incident Severity

| Severity | Triggers |
|---|---|
| SEV1 | Data loss risk; Cloud SQL unavailable during an active validation window; production Cloud Run service not serving after a completed deploy; terraform plan shows unexpected destructive change |
| SEV2 | worker_message_error_count > 0; silver_refresh_error_count > 0; DLQ receives messages during a valid-event run; API /readiness fails during a controlled validation window |
| SEV3 | CI failure on PR; documentation or evidence mismatch; dashboard metric missing or stale; non-critical deploy workflow failure with no confirmed runtime impact |

---

## Incident Response Runbooks

### API Readiness Failure

1. Check `/health` and `/readiness` response codes on the Cloud Run API endpoint.
2. Inspect Cloud Run latest revision status (`gcloud run revisions list --service rtdp-api`).
3. Confirm the runtime service account has Cloud SQL client and Secret Manager accessor roles.
4. Confirm the `rtdp-database-url` secret is accessible and correctly versioned in Secret Manager.
5. Check Cloud SQL instance state. If `NEVER / STOPPED` and outside a bounded validation
   window, the readiness failure is expected behaviour. Do not start Cloud SQL outside a
   scoped runbook.
6. If inside a validation window and Cloud SQL is running, check Cloud Logging for connection
   timeout or authentication errors on the `rtdp-api` service.
7. Do not mutate any GCP resource without a scoped branch and a documented runbook.

---

### Worker Error Alert

1. Query Cloud Monitoring for `worker_message_error_count` timeSeries to identify the
   error window and event count.
2. Query Cloud Logging for `jsonPayload.status="error"` on the `rtdp-pubsub-worker` service.
3. Check Pub/Sub subscription delivery attempt counts for the affected message window.
4. Determine whether the triggering messages were malformed or structurally valid.
5. If this occurred during a valid-event run, stop publishing immediately and preserve all
   Cloud Logging evidence before any further action.
6. Do not delete DLQ messages before root cause is captured and documented.

---

### DLQ Growth

1. Confirm DLQ topic (`market-events-raw-dlq`) state and message count in GCP console.
2. Capture the current message count before any action.
3. Sample DLQ messages only within a controlled validation context; do not acknowledge or
   consume messages before evidence is recorded.
4. Identify whether root cause is a schema/contract mismatch, a worker processing bug,
   or a Pub/Sub delivery configuration error.
5. Do not purge the DLQ before root cause is documented.
6. Open a dedicated fix branch after root cause is confirmed.

---

### Silver Refresh Failure

1. Check `silver_refresh_error_count` in Cloud Monitoring for the failure window.
2. Inspect Cloud Run Job execution logs for `rtdp-silver-refresh-job` in Cloud Logging.
3. Confirm the `rtdp-database-url` secret is accessible from the job runtime service account.
4. Confirm Cloud SQL is in `ALWAYS / RUNNABLE` state during the validation window.
5. Re-run the silver refresh job only if inside a bounded controlled validation window.
6. Preserve failure logs and metrics before any retry or cleanup.

---

### Cloud SQL Unavailable

1. Confirm expected Cloud SQL state: `NEVER / STOPPED` is the normal resting state for
   `rtdp-postgres`.
2. If outside a validation window, a stopped instance is not an incident unless a service
   is expected to be running against it.
3. If inside a validation window, check instance state in GCP console and inspect Cloud
   Logging for connection timeout errors from dependent services.
4. Do not change the Cloud SQL activation policy outside a scoped runbook. Uncontrolled
   starts introduce cost and safety risk.

---

### Deploy Workflow Failure

1. Confirm whether the Cloud Run runtime changed; check `latestReadyRevision` for the
   affected service.
2. Inspect the GitHub Actions workflow run logs for the failed step.
3. Check Artifact Registry for the expected commit-SHA tagged image.
4. Check Cloud Run revision status after any partial deploy.
5. If the workflow failed before the Cloud Run deploy step, document that no runtime impact
   occurred and no rollback is needed.
6. If the workflow failed after the Cloud Run deploy step, compare `latestReadyRevision`
   to the previous known-good revision and roll back if required.

---

### Terraform Drift Or Destructive Plan

1. Stop immediately. Do not run `terraform apply`.
2. Capture the full `terraform plan` output before any further action.
3. Identify the scope: which resource, which field, and whether the change is additive or
   destructive.
4. Open a dedicated fix or import branch. Do not attempt to resolve drift on the current
   feature branch.

---

## Rollback And Safety Rules

- No `terraform apply` during an incident without an explicit scoped runbook reviewed
  before execution.
- Prefer rolling back to the previous known-good Cloud Run revision for any runtime deploy
  issue rather than building and re-deploying under pressure.
- Preserve Cloud Logging evidence and Cloud Monitoring metric state before any cleanup or
  resource deletion.
- Do not delete DLQ messages before root cause is captured and documented.
- Keep Cloud SQL cost-control state explicit: default is `NEVER / STOPPED`; starts require
  a bounded validation window with documented start and stop steps.
- Both deploy workflows (worker and API) are manual `workflow_dispatch` only. No automatic
  deploy-on-merge is currently configured.

---

## Evidence Links

- [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md)
- [docs/ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md)
- [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md)
- [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md)
- [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md)
- [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md)
- [docs/silver-refresh-scheduler-execution-proof-evidence.md](silver-refresh-scheduler-execution-proof-evidence.md)
- [docs/api-manual-deploy-evidence.md](api-manual-deploy-evidence.md)
- [docs/cloud-run-worker-manual-deploy-evidence.md](cloud-run-worker-manual-deploy-evidence.md)
- [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md)
