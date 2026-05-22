# dbt Metrics Runtime Proof Runbook

Branch: `feat/dbt-metrics-metadata-server-auth`

---

## 1. Purpose

This runbook validates the dbt metrics runtime integration (PR #203 + PR #204) safely.
It proves that:

- the metrics emission script can be exercised in dry-run mode without any Cloud Monitoring write;
- the runtime integration inside the dbt refresh job correctly gates execution behind `DBT_METRICS_ENABLED`;
- the Cloud Run job can be executed with metrics enabled in dry-run mode, producing observable log evidence without touching Cloud Monitoring;
- the overall safety posture (Cloud SQL STOPPED/NEVER, schedulers PAUSED) is maintained throughout every step of this proof.

This runbook does not enable live Cloud Monitoring writes. That activation path is described separately in §7.

---

## 2. Current Implementation Summary

### `scripts/push_dbt_metrics.py`

Pure Python script (no third-party dependencies) that:

- loads `dbt/target/run_results.json` from a completed dbt invocation;
- parses the artifact into structured node-level results;
- builds Cloud Monitoring time series payloads under the metric prefix `custom.googleapis.com/rtdp/dbt/*`;
- emits one JSON summary to stdout;
- **when `--dry-run` is set** (the default), skips all Cloud Monitoring writes and prints a dry-run confirmation to stderr;
- **when `--dry-run` is not set**, obtains a short-lived access token using the configured auth mode (default: `auto`), posts the time series via `urllib.request`, and never exposes the token in process arguments or stdout.

Metrics emitted:

| Metric type | Value type | Description |
|---|---|---|
| `custom.googleapis.com/rtdp/dbt/dbt_run_success_count` | INT64 | Models with status=success |
| `custom.googleapis.com/rtdp/dbt/dbt_run_failure_count` | INT64 | Models with status=error |
| `custom.googleapis.com/rtdp/dbt/dbt_run_duration_seconds` | DOUBLE | Total elapsed wall-clock time |
| `custom.googleapis.com/rtdp/dbt/dbt_test_pass_count` | INT64 | Tests with status=pass |
| `custom.googleapis.com/rtdp/dbt/dbt_test_failure_count` | INT64 | Tests with status=fail or error |
| `custom.googleapis.com/rtdp/dbt/dbt_test_pass_rate` | DOUBLE | Test pass percentage (0–100) |
| `custom.googleapis.com/rtdp/dbt/dbt_model_rows_total` | INT64 | Per-model rows_affected (one series per model, emitted only when rows_affected is present) |
| `custom.googleapis.com/rtdp/dbt/dbt_artifact_parse_error_count` | INT64 | Node-level parse failures inside the script |

All series carry `job_name` and `environment` metric labels. Model/test series carry `node_type`. Per-model series carry `model_name`.

### `apps/dbt-refresh-job/src/rtdp_dbt_refresh_job/__init__.py`

Runtime integration inside the dbt refresh orchestrator:

- `_push_dbt_metrics(cfg, ...)` is called after each `dbt run` and `dbt test` step, **only when `cfg["metrics_enabled"]` is `True`**.
- When `cfg["metrics_dry_run"]` is `True` (the default), the script is invoked with `--dry-run` appended, so no Cloud Monitoring write occurs.
- If the script exits non-zero after an explicit enablement, the entire job fails (non-zero exit propagates). This behaviour prevents silent metric emission failures from being masked.
- Log lines are emitted as structured JSON with `"command": "push dbt metrics"`, `"dry_run": true/false`, `"status": "success"/"error"`, and `duration_ms`.

### `apps/dbt-refresh-job/Dockerfile`

The `scripts/` directory is copied into the image at `/app/scripts/`:

```dockerfile
COPY scripts ./scripts
```

The runtime default is `DBT_METRICS_SCRIPT_PATH=/app/scripts/push_dbt_metrics.py`.

### `tests/test_dbt_refresh_job.py`

Runtime integration tests verifying:

- metrics are not invoked when `DBT_METRICS_ENABLED=false`;
- metrics are invoked after `dbt run` and `dbt test` when `DBT_METRICS_ENABLED=true`;
- job exits non-zero when metrics fail after enablement;
- `DBT_METRICS_DRY_RUN=true` passes `--dry-run` to the script;
- passwords are never printed in logs.

### `tests/test_push_dbt_metrics.py`

Unit and integration tests for the metrics script itself:

- all tests use `--dry-run` or call pure functions directly;
- `push_time_series()` is exercised only with mocked `subprocess` and `urllib`;
- tests cover parsing, metric construction, dry-run safety, metadata ADC path, gcloud fallback, and error paths.

---

## 3. Safety Defaults

The following env-var defaults apply in every deployment context and are enforced in `_resolve_config()`:

| Variable | Default | Effect |
|---|---|---|
| `DBT_METRICS_ENABLED` | `false` | Metrics emission is completely skipped; no subprocess call to the script |
| `DBT_METRICS_DRY_RUN` | `true` | Even when enabled, `--dry-run` is appended; no Cloud Monitoring write |

Infrastructure safety state confirmed at the time this runbook was written
(2026-05-22, branch `docs/dbt-metrics-runtime-proof-runbook`):

- **Cloud SQL `rtdp-postgres`**: `STOPPED / NEVER`
- **Cloud Scheduler `rtdp-silver-refresh-scheduler`**: `PAUSED`
- **Cloud Scheduler `rtdp-bigquery-append-scheduler`**: `PAUSED`
- **Terraform plan**: `No changes. PLAN_EXIT=0`

These states must be confirmed as preconditions before every section of this runbook.

---

## 4. Local Dry-Run Proof

The metrics-script dry-run commands below execute locally and do not require Cloud Monitoring writes. The optional safety-state checks use read-only `gcloud` commands. No Cloud SQL start. No scheduler action.

### 4.1 Verify branch and status

```bash
git status
git branch --show-current
```

Expected output: branch `docs/dbt-metrics-runtime-proof-runbook`, working tree clean.

### 4.2 Run the test suite

```bash
uv run pytest -q
```

Expected: all tests pass. As of this runbook: **335 passed**.

### 4.3 Run the linter

```bash
uv run ruff check .
```

Expected: `All checks passed!`

### 4.4 Run the metrics script in dry-run mode against an existing artifact

If a `dbt/target/run_results.json` exists from a prior local or CI run:

```bash
python3 scripts/push_dbt_metrics.py \
  --run-results-path dbt/target/run_results.json \
  --project-id project-42987e01-2123-446b-ac7 \
  --location europe-west1 \
  --job-name rtdp-dbt-refresh-job \
  --environment cloud_sql_prod \
  --dry-run
```

Expected stdout: a JSON summary containing `"dry_run": true`, model counts, test counts, and pass rate.

Expected stderr: `Dry run: would push N time series to Cloud Monitoring.`

To generate a synthetic artifact for testing without a live dbt run:

```python
import json, pathlib
artifact = {
  "metadata": {
    "dbt_schema_version": "https://schemas.getdbt.com/dbt/run-results/v5.json",
    "dbt_version": "1.9.0",
    "generated_at": "2026-05-22T12:00:00.000000Z",
    "invocation_id": "local-dry-run-proof"
  },
  "elapsed_time": 77.25,
  "results": [
    {"unique_id": "model.rtdp.silver_market_event_minute_aggregates",
     "status": "success", "execution_time": 12.3,
     "adapter_response": {"rows_affected": 13}, "failures": None, "message": "INSERT 0 13"},
    {"unique_id": "model.rtdp.gold_market_event_daily_aggregates",
     "status": "success", "execution_time": 8.9,
     "adapter_response": {"rows_affected": 7}, "failures": None, "message": "INSERT 0 7"},
    {"unique_id": "test.rtdp.not_null_silver_symbol",
     "status": "pass", "execution_time": 0.5,
     "adapter_response": {}, "failures": 0, "message": "Pass"},
    {"unique_id": "test.rtdp.not_null_gold_symbol",
     "status": "pass", "execution_time": 0.4,
     "adapter_response": {}, "failures": 0, "message": "Pass"}
  ]
}
pathlib.Path("/tmp/run_results.json").write_text(json.dumps(artifact))
```

Then run:

```bash
python3 scripts/push_dbt_metrics.py \
  --run-results-path /tmp/run_results.json \
  --project-id project-42987e01-2123-446b-ac7 \
  --dry-run
```

### 4.5 Confirm no GCP mutation

- No `gcloud` call is made when `--dry-run` is set (verified by `test_main_dry_run_does_not_call_gcloud`).
- No network request is made when `--dry-run` is set.
- Cloud SQL stays `STOPPED / NEVER`.
- Cloud Scheduler stays `PAUSED`.

To verify the Cloud SQL state at any point:

```bash
gcloud sql instances describe rtdp-postgres \
  --format="value(state,settings.activationPolicy)"
```

Expected: `STOPPED   NEVER`

To verify the scheduler states:

```bash
gcloud scheduler jobs list --location=europe-west1 \
  --format="table(name,state)"
```

Expected: both jobs listed as `PAUSED`.

---

## 5. Runtime Dry-Run Proof Path

This section describes how to exercise the Cloud Run job with metrics enabled in dry-run mode.
No Cloud Monitoring write occurs. Cloud SQL must be started only if a live dbt run is required
(see §6). This section alone does not require Cloud SQL.

### 5.1 Environment variables required

When executing the Cloud Run job manually for a metrics dry-run proof, set these additional variables alongside the existing database credentials:

```
DBT_METRICS_ENABLED=true
DBT_METRICS_DRY_RUN=true
```

With `DBT_METRICS_DRY_RUN=true`, the runtime calls:

```
python3 /app/scripts/push_dbt_metrics.py \
  --run-results-path /app/dbt/target/run_results.json \
  --project-id <project-id> \
  --job-name rtdp-dbt-refresh-job \
  --environment <DBT_TARGET> \
  --dry-run
```

No token is requested. No HTTP request is made to `monitoring.googleapis.com`.

### 5.2 Expected log evidence

After each `dbt run` or `dbt test` step, the job emits a structured JSON log line:

```json
{
  "command": "push dbt metrics",
  "component": "dbt-refresh",
  "dbt_command": "dbt run",
  "dry_run": true,
  "duration_ms": 312.5,
  "mode": "run-and-test",
  "operation": "dbt_run_metrics",
  "service": "rtdp-dbt-refresh-job",
  "status": "success",
  "target": "cloudsql",
  "timestamp_utc": "2026-05-22T12:00:00+00:00"
}
```

The presence of `"dry_run": true` in this log is the observable proof that metrics were enabled
and ran without a Cloud Monitoring write.

The script's own dry-run confirmation appears in the stderr of the subprocess (visible in Cloud Logging):

```
Dry run: would push 9 time series to Cloud Monitoring.
```

---

## 6. Controlled Cloud Run Proof Plan

This is a staged plan, not automatic execution. Each step requires an explicit operator action.

### Step 1 — Verify Cloud SQL state (precondition)

```bash
gcloud sql instances describe rtdp-postgres \
  --format="value(state,settings.activationPolicy)"
```

Expected: `STOPPED   NEVER`. Do not proceed if the instance is not stopped.

### Step 2 — Verify scheduler states (precondition)

```bash
gcloud scheduler jobs list --location=europe-west1 \
  --format="table(name,state)"
```

Expected: `rtdp-silver-refresh-scheduler PAUSED`, `rtdp-bigquery-append-scheduler PAUSED`.

### Step 3 — Start Cloud SQL (bounded window, only if needed)

Only start Cloud SQL if the execution requires a live dbt run. Start it explicitly and record the timestamp:

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS
```

Confirm it is running:

```bash
gcloud sql instances describe rtdp-postgres \
  --format="value(state,settings.activationPolicy)"
```

Expected: `RUNNABLE   ALWAYS`

### Step 4 — Execute the Cloud Run job manually

Execute with metrics enabled in dry-run mode:

```bash
gcloud run jobs execute rtdp-dbt-refresh-job \
  --region europe-west1 \
  --update-env-vars DBT_METRICS_ENABLED=true,DBT_METRICS_DRY_RUN=true \
  --wait
```

Note: confirm the exact `gcloud run jobs execute --update-env-vars` behaviour for the installed CLI version before relying on this as a non-persistent execution override. If unsure, treat this as a planned/manual proof step and verify the job definition immediately after execution.

### Step 5 — Inspect logs for `push dbt metrics`

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="rtdp-dbt-refresh-job" AND jsonPayload.command="push dbt metrics"' \
  --limit 10 \
  --format json
```

Confirm:
- `jsonPayload.dry_run` is `true`
- `jsonPayload.status` is `"success"`
- No log line contains `"Pushed N time series to Cloud Monitoring"` (that phrase only appears when dry-run is false)

Also confirm the script's stderr in Cloud Logging:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="rtdp-dbt-refresh-job" AND textPayload:"Dry run: would push"' \
  --limit 10
```

Expected: `Dry run: would push 9 time series to Cloud Monitoring.`

### Step 6 — Stop Cloud SQL immediately after proof

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER
```

Confirm:

```bash
gcloud sql instances describe rtdp-postgres \
  --format="value(state,settings.activationPolicy)"
```

Expected: `STOPPED   NEVER`

### Step 7 — Confirm scheduler states remain PAUSED

```bash
gcloud scheduler jobs list --location=europe-west1 \
  --format="table(name,state)"
```

Expected: both jobs `PAUSED`. Do not resume them as part of this proof.

---

## 7. Live Metric Write Activation Plan

**This section is titled "Not enabled by this runbook."**

The following conditions must be satisfied and explicitly verified before setting `DBT_METRICS_DRY_RUN=false` on any production or production-like execution:

1. **Auth strategy is confirmed — metadata server ADC path is now implemented.**
   `scripts/push_dbt_metrics.py` (PR from branch `feat/dbt-metrics-metadata-server-auth`)
   replaces the `gcloud auth print-access-token` subprocess with a direct HTTP call to the
   GCP instance metadata server:

   ```http
   GET http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token
   Header: Metadata-Flavor: Google
   ```

   This call is made entirely via `urllib.request` with a 2-second timeout, requires no
   additional binaries, and works with the current `python:3.12-slim` base image.
   The token is parsed from the JSON response and carried in memory only — it is never
   printed to stdout or stderr.

   The `--auth-mode` flag controls token acquisition:

   | Mode | Behaviour | Suitable for |
   | --- | --- | --- |
   | `auto` (default) | Metadata server first; gcloud fallback | Cloud Run (metadata succeeds) or local (gcloud fallback) |
   | `metadata` | Metadata server only; fails outside GCP | Production Cloud Run |
   | `gcloud` | gcloud subprocess only | Local development |

   **Note:** The metadata server is only reachable inside GCP runtimes (Cloud Run, GCE, GKE).
   When running locally, `auto` mode falls back to `gcloud`. When running on Cloud Run,
   `auto` mode uses the metadata server without requiring `gcloud` in the container image.

   A `DBT_METRICS_DRY_RUN=true` execution bypasses all token acquisition — neither the
   metadata server nor `gcloud` is called in dry-run mode.

2. **IAM `monitoring.metricWriter` is confirmed on the Cloud Run job's service account.**
   The job runs as a service account. That service account must hold `roles/monitoring.metricWriter` on the project to write to `custom.googleapis.com/rtdp/dbt/*`.
   - **Action required:** Check and apply via Terraform if missing:

     ```bash
     gcloud projects get-iam-policy project-42987e01-2123-446b-ac7 \
       --flatten="bindings[].members" \
       --filter="bindings.role=roles/monitoring.metricWriter" \
       --format="table(bindings.members)"
     ```

3. **Only then set `DBT_METRICS_DRY_RUN=false`.**
   Once steps 1–2 are satisfied, set the variable:

   ```bash
   gcloud run jobs update rtdp-dbt-refresh-job \
     --region europe-west1 \
     --update-env-vars DBT_METRICS_ENABLED=true,DBT_METRICS_DRY_RUN=false
   ```

   And confirm the first live run by checking Cloud Monitoring for new data points under `custom.googleapis.com/rtdp/dbt/*`.

---

## 8. Evidence Checklist

Complete these checkboxes before closing the proof branch.

- [ ] `uv run pytest -q` passes — all tests green
- [ ] `uv run ruff check .` passes — no lint errors
- [ ] `terraform fmt -check -recursive infra/terraform/gcp` exits 0 — Terraform files formatted
- [ ] `terraform -chdir=infra/terraform/gcp validate` exits 0 — configuration valid
- [ ] `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode` exits 0 (`PLAN_EXIT=0`) — no infrastructure drift
- [ ] Cloud SQL `rtdp-postgres` is `STOPPED / NEVER` before proof begins
- [ ] Cloud SQL `rtdp-postgres` is `STOPPED / NEVER` after proof completes
- [ ] `rtdp-silver-refresh-scheduler` is `PAUSED` before and after proof
- [ ] `rtdp-bigquery-append-scheduler` is `PAUSED` before and after proof
- [ ] Local dry-run of `push_dbt_metrics.py` produces `"dry_run": true` in JSON summary
- [ ] Local dry-run produces `Dry run: would push N time series to Cloud Monitoring.` on stderr
- [ ] `test_main_dry_run_does_not_call_gcloud` passes (no subprocess call in dry-run mode)
- [ ] Cloud Run job log contains `"command": "push dbt metrics"` with `"dry_run": true` (if §6 was executed)
- [ ] No log line contains `"Pushed N time series to Cloud Monitoring"` (live write not attempted)
- [ ] No secrets or credentials appear in any log or output

---

## 9. Rollback

The metrics integration is fully gated behind `DBT_METRICS_ENABLED`. To return the runtime to its
pre-PR-#204 behaviour:

```bash
gcloud run jobs update rtdp-dbt-refresh-job \
  --region europe-west1 \
  --update-env-vars DBT_METRICS_ENABLED=false
```

Or simply omit the variable; the default is `false`. When `DBT_METRICS_ENABLED=false`, `_push_dbt_metrics()` returns immediately without invoking the script, without reading `run_results.json`, and without any subprocess or network activity.

No Terraform change is required to roll back. No code change is required. The feature is an opt-in env-var gate.

---

## 10. Recruiter / Portfolio Value

### dbt observability

Transformation pipelines without metrics are black boxes. This feature adds per-run and per-model observability: success counts, failure counts, test pass rates, row counts, and elapsed time — all emitted as Cloud Monitoring custom metrics with structured labels for job name, environment, and node type. This is the same observability pattern used in production dbt deployments at organisations that operate Airflow, Cloud Composer, or Cloud Run-based orchestration.

### Cloud Monitoring integration design

The metrics script is deliberately written with no third-party dependencies (only `urllib.request`) and communicates with the Cloud Monitoring REST API directly. The token acquisition supports three modes via `--auth-mode`: `metadata` (GCP instance metadata server — no binary required, works in `python:3.12-slim`), `gcloud` (subprocess fallback for local development), and `auto` (metadata first, gcloud fallback). The token is carried in an HTTP `Authorization` header in memory, never printed to stdout or exposed in subprocess arguments. This follows the same token-handling pattern as `push_bigquery_quality_metrics.py` and demonstrates understanding of secure, container-safe credential management.

### Safe production rollout

The feature is introduced behind two independent feature flags (`DBT_METRICS_ENABLED=false`, `DBT_METRICS_DRY_RUN=true`). Live Cloud Monitoring writes are not enabled by this branch. The dry-run path is fully observable (structured log evidence) without risking metric namespace pollution or IAM permission failures interrupting production dbt runs. This is a standard production rollout pattern: instrument first, observe evidence, then activate writes under a controlled IAM gate.

### Operational evidence

The runbook is designed to produce verifiable, reproducible log evidence: structured JSON log lines with `dry_run: true` are machine-readable and can be queried from Cloud Logging. The evidence checklist is designed to be checked by a second engineer, not just the author.

### Analytics engineering maturity

Adding run-time metrics emission to a dbt refresh job demonstrates awareness that analytics engineering is not complete at the `dbt test PASS` boundary — it extends to operational visibility, alerting, and feedback loops that inform data consumers about transformation freshness and quality. This is the maturity level expected in senior data engineering and analytics engineering roles at organisations running dbt in production.

---

## Validation Output Captured at Runbook Creation

```
$ uv run pytest -q
335 passed in 4.92s

$ uv run ruff check .
All checks passed!

$ terraform fmt -check -recursive infra/terraform/gcp
FMT_EXIT=0

$ terraform -chdir=infra/terraform/gcp validate
Success! The configuration is valid.

$ terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0

$ gcloud sql instances describe rtdp-postgres \
    --format="value(state,settings.activationPolicy)"
STOPPED  NEVER

$ gcloud scheduler jobs list --location=europe-west1 \
    --format="table(name,state)"
ID                              STATE
rtdp-silver-refresh-scheduler   PAUSED
rtdp-bigquery-append-scheduler  PAUSED
```

## Validation Output — feat/dbt-metrics-metadata-server-auth

```
$ uv run pytest -q
348 passed in 4.96s

$ uv run ruff check .
All checks passed!

$ terraform fmt -check -recursive infra/terraform/gcp
FMT_EXIT=0

$ terraform -chdir=infra/terraform/gcp validate
Success! The configuration is valid.

$ terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0

$ gcloud sql instances describe rtdp-postgres \
    --project=project-42987e01-2123-446b-ac7 \
    --format="table(name,state,settings.activationPolicy)"
NAME           STATE    ACTIVATION_POLICY
rtdp-postgres  STOPPED  NEVER

$ gcloud scheduler jobs list \
    --project=project-42987e01-2123-446b-ac7 \
    --location=europe-west1 \
    --format="table(id,state,schedule)"
ID  STATE   SCHEDULE
    PAUSED  */15 * * * *
    PAUSED  0 * * * *
```
