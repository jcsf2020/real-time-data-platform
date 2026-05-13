# dbt Operational Migration Plan

**Status: PLAN ONLY — NOT EXECUTED**
**Branch:** `docs/dbt-operational-migration-plan`
**Scope:** Documentation only. No runtime code, dbt models, GitHub Actions workflows, Cloud SQL, or Terraform changes.

---

## Objective

Define and record the controlled migration path from the current stored-function refresh mechanism to dbt as the authoritative operational transformation engine for the RTDP silver and gold layers.

This document does not execute any migration step. It captures the decision context, proposed phases, and acceptance criteria so that the next implementation branch has a clear, evidence-backed starting point.

---

## Current State

| Component | Status |
|---|---|
| Silver refresh | `rtdp-silver-refresh-job` Cloud Run Job calls `silver.refresh_market_event_minute_aggregates()` |
| Gold refresh | `gold.refresh_market_event_daily_aggregates()` executed on demand via `psql` |
| dbt CI | Green on every push to `main`; `dbt compile → dbt run → dbt test` against an ephemeral pgvector container |
| dbt on Cloud SQL | Validated once in a controlled window (parity confirmed, tables restored, Cloud SQL stopped) |
| Authoritative refresh path | Stored functions — `infra/postgres/init.sql` is the source of truth |
| Cloud SQL | `NEVER / STOPPED` between validation windows |
| Cloud Scheduler | `rtdp-silver-refresh-scheduler` configured; kept `PAUSED` by default |

The existing Cloud Run Job (`rtdp-silver-refresh-job`) is a Python binary that executes:

```python
_SQL = "SELECT silver.refresh_market_event_minute_aggregates();"
```

It receives `DATABASE_URL` as a Cloud Run environment variable backed by Secret Manager (`rtdp-database-url`). The job image is built from `apps/silver-refresh-job/Dockerfile`; deployment workflow details must be verified before any runtime migration branch changes production job configuration.

---

## Evidence Already Completed

The following evidence records confirm that dbt is ready for operational migration planning. No further proof-of-concept validation is required before designing the operational migration branch.

| Evidence | What It Confirms |
|---|---|
| [docs/dbt-transformation-governance-plan.md](dbt-transformation-governance-plan.md) | Governance design, model mapping, test strategy, and two-phase migration strategy |
| [docs/dbt-ci-validation-evidence.md](dbt-ci-validation-evidence.md) | 22 dbt tests pass on every CI run (ephemeral container); 117 pytest; ruff clean |
| [docs/dbt-cloud-sql-migration-runbook.md](dbt-cloud-sql-migration-runbook.md) | Controlled runbook for Cloud SQL validation window |
| [docs/dbt-cloud-sql-validation-evidence.md](dbt-cloud-sql-validation-evidence.md) | dbt output parity with stored functions: silver 256 / 256, gold 7 / 7; 22 dbt tests passed; `/aggregates/minute` and `/aggregates/daily` both returned HTTP 200; Cloud SQL returned to `NEVER / STOPPED` |

The parity check from `docs/dbt-cloud-sql-validation-evidence.md`:

| Layer | Stored-function baseline | dbt output | Match |
|---|---:|---:|---|
| `silver.market_event_minute_aggregates` | 256 | 256 | Yes |
| `gold.market_event_daily_aggregates` | 7 | 7 | Yes |

---

## Target Operational State

After the migration is executed and accepted:

| Component | Before | After |
|---|---|---|
| Silver refresh trigger | `silver.refresh_market_event_minute_aggregates()` inside `rtdp-silver-refresh-job` | `dbt run --select silver,gold` inside a Cloud Run Job |
| Gold refresh trigger | `gold.refresh_market_event_daily_aggregates()` called on demand | `dbt run --select silver,gold` (gold included in the same run) |
| Transformation governance | Stored SQL in `infra/postgres/init.sql` | Version-controlled dbt models in `dbt/models/` |
| Data quality tests | None at transformation time | 22 dbt schema and business rule tests on every refresh |
| Lineage | Implicit in stored functions | Machine-readable DAG: `bronze.market_events → silver → gold` |
| Rollback path | N/A — stored functions are current authority | Stored functions remain in `infra/postgres/init.sql` and can be invoked directly |

---

## Authority Transition

| Phase | Authoritative Refresh Mechanism | Stored Functions |
|---|---|---|
| Before migration (current) | `silver.refresh_market_event_minute_aggregates()` and `gold.refresh_market_event_daily_aggregates()` | Primary path |
| During migration (coexistence) | Stored functions continue to run; dbt validated in a parallel path | Retained as rollback; not removed |
| After accepted migration | `dbt run --select silver,gold` is the operational path | Preserved in `infra/postgres/init.sql` until explicit cleanup branch |
| Cleanup (later branch only) | dbt is established and stable | Removed from `init.sql` in a scoped cleanup PR |

Stored functions are not removed in the migration branch. They are only removed in a subsequent cleanup branch, and only after three consecutive green CI builds on `main` with dbt as the runtime path.

---

## Proposed Migration Phases

### Phase 1 — Confirm main clean and CI green

Precondition before opening the migration branch:

```bash
git checkout main && git pull origin main
git status                            # must be clean
gh run list --branch main --limit 5  # validate and dbt jobs both green
```

The migration branch must diverge from a clean, fully green `main`. Do not branch from a CI-yellow state.

### Phase 2 — Confirm three consecutive green dbt CI builds on main

Before modifying any runtime component, confirm that the `dbt` CI job has passed on three consecutive `main` commits. This requirement is inherited from `docs/dbt-transformation-governance-plan.md` section 10.

Evidence: `gh run list --branch main --workflow ci.yml --limit 10` — all runs show both `validate` and `dbt` jobs green.

### Phase 3 — Design the dbt runtime execution path

Two decisions must be resolved before writing a single line of runtime code:

1. **Where does `dbt run` execute?** Inside the existing `rtdp-silver-refresh-job` Cloud Run Job, or in a new dedicated Cloud Run Job. See the Decision Matrix below.
2. **How is the dbt profile provided at runtime?** See the Credential and Profile Handling section below.

Both decisions must be documented and agreed before Phase 4.

### Phase 4 — Decide: adapt existing job or create dedicated job

Apply the Decision Matrix in this document. Record the chosen option and the rationale in the migration branch PR description before implementing. See Recommendation below.

### Phase 5 — Define credential and profile handling for Cloud Run

dbt requires a `profiles.yml` at runtime. This file must never be committed to the repository and must never contain hardcoded credentials. The accepted pattern from `docs/dbt-cloud-sql-migration-runbook.md` (Phase 6) is:

```bash
# Written to /tmp outside the repo tree; deleted in cleanup
PROFILES_DIR=/tmp/rtdp-dbt-cloudsql
mkdir -p "$PROFILES_DIR"
cat > "$PROFILES_DIR/profiles.yml" <<'EOF'
rtdp:
  target: cloudsql
  outputs:
    cloudsql:
      type: postgres
      host: 127.0.0.1
      port: 5433
      user: rtdp
      password: "{{ env_var('DBT_CLOUDSQL_PASSWORD') }}"
      dbname: realtime_platform
      schema: public
      threads: 1
EOF
```

For a Cloud Run Job, the equivalent pattern is an entrypoint script that:

1. Reads connection parameters from environment variables (supplied via Cloud Run secret references to `rtdp-database-url` or individual secrets).
2. Writes a `profiles.yml` to a temp directory inside the container filesystem at startup.
3. Runs `dbt run --profiles-dir /tmp/dbt-profiles --project-dir /app/dbt`.
4. Exits with the dbt exit code; the container runtime does not persist the generated file.

The `dbt/profiles.yml.example` already uses `{{ env_var('...') }}` references. The same pattern should be extended to a Cloud SQL `cloudsql` target. The entrypoint script does not require new secrets — it can derive host, port, user, and password from the existing `DATABASE_URL` at startup.

No new `dbt/profiles.yml` file may be committed to the repository at any point during this migration.

### Phase 6 — Add dry-run or compile-only operational validation

Before `dbt run` is executed against Cloud SQL in the Cloud Run Job, add a `dbt compile` step that validates SQL resolution against the Cloud SQL schema without materialising tables:

```bash
dbt compile --project-dir /app/dbt --profiles-dir /tmp/dbt-profiles --target cloudsql
```

This step serves as an operational pre-flight check. If compile fails, the job exits non-zero and the stored-function path can be invoked manually as rollback. The compile step should be captured in CI evidence before `dbt run` is added to the job.

### Phase 7 — Add dbt run and test operational validation against Cloud SQL

After compile is confirmed, add `dbt run --select silver,gold` and `dbt test` as subsequent steps in the Cloud Run Job. Both must pass before the scheduler is re-enabled.

Acceptance evidence for this phase:

- `dbt compile` exits 0 against live Cloud SQL.
- `dbt run` materialises both models; row counts are logged.
- `dbt test` passes all 22 tests.
- API readback: `/aggregates/minute` and `/aggregates/daily` both return HTTP 200 with rows.
- Cloud SQL is returned to `NEVER / STOPPED` after the validation window.

### Phase 8 — Keep stored functions as rollback path

Do not remove `silver.refresh_market_event_minute_aggregates()` or `gold.refresh_market_event_daily_aggregates()` from `infra/postgres/init.sql` during or after the migration branch. The stored functions remain callable as an emergency rollback:

```bash
psql -c "SELECT silver.refresh_market_event_minute_aggregates();"
psql -c "SELECT gold.refresh_market_event_daily_aggregates();"
```

These functions use upsert semantics (`ON CONFLICT ... DO UPDATE`) and are safe to call against tables that were last populated by dbt. They will overwrite dbt-materialised rows with equivalent data.

### Phase 9 — Update scheduler and job configuration only after evidence approval

Do not resume `rtdp-silver-refresh-scheduler` or change the production Cloud Run Job until the Phase 7 evidence is reviewed and accepted. The scheduler configuration change (pointing to a new job, or deploying a new image to the existing job) is a separate, explicit step documented in its own evidence file.

Scheduler final state must be `PAUSED` until Phase 7 evidence is merged into `main`.

### Phase 10 — Retire stored functions only in a later cleanup branch

After the migration branch is merged and dbt has been the operational path on `main` for at least three consecutive CI green builds:

1. Open a `chore/retire-stored-functions` branch.
2. Remove `silver.refresh_market_event_minute_aggregates()` and `gold.refresh_market_event_daily_aggregates()` from `infra/postgres/init.sql`.
3. Update `docs/ARCHITECTURE_REVIEW.md` to reflect that stored functions are retired.
4. Open a PR; CI must be green before merge.

Do not combine stored-function removal with the migration itself. Separation reduces blast radius.

---

## Decision Matrix

### Option A — Adapt the existing `rtdp-silver-refresh-job`

Modify the existing Cloud Run Job to run `dbt run --select silver,gold` instead of (or in addition to) the stored-function call.

| Dimension | Assessment |
|---|---|
| Cloud Run Job resource | Reuses existing `rtdp-silver-refresh-job` |
| Scheduler config | No scheduler change needed; Scheduler already points to this job |
| IAM / service account | No new IAM grants needed |
| Image size | Increases: Python runtime + dbt + dbt-utils + dbt-postgres adapter |
| Rollback | Requires redeploying the old image revision |
| Operational risk | Changing an active job mid-migration |
| Separation of concerns | Mixes the Python refresh job with dbt runtime concerns |
| CI/CD | Existing deploy workflow (`deploy-worker-cloud-run.yml`) already builds this image |

### Option B — Create a dedicated `rtdp-dbt-refresh-job`

Build a new Cloud Run Job (`rtdp-dbt-refresh-job`) with a purpose-built container that only runs dbt.

| Dimension | Assessment |
|---|---|
| Cloud Run Job resource | New resource required; Terraform skeleton needs a new module |
| Scheduler config | Existing `rtdp-silver-refresh-scheduler` must be updated to point to the new job, or a second scheduler job is created |
| IAM / service account | Existing `rtdp-scheduler-sa` with `roles/run.invoker` can be reused if the new job is in the same project/region |
| Image size | Smaller: Python base + dbt + dbt-postgres only (no psycopg, no consumer logic) |
| Rollback | The old `rtdp-silver-refresh-job` remains intact and can be triggered manually |
| Separation of concerns | Clean boundary: dbt job is independent of the Python refresh job |
| CI/CD | A new deploy workflow or an update to the existing workflow is needed |

### Option C — Keep stored functions; use dbt only for CI and documentation

Preserve the stored functions as the operational path indefinitely. dbt continues to validate the transformation logic in CI but never executes operationally against Cloud SQL.

| Dimension | Assessment |
|---|---|
| Operational risk | None — no runtime change |
| Technical debt | Transformation logic exists in two places; no lineage in production |
| dbt value | Limited to CI quality gate and documentation |
| Portfolio signal | Demonstrates governance planning but not operational execution |

---

## Recommendation

**Prefer Option B (dedicated `rtdp-dbt-refresh-job`).**

Rationale:

- The existing `rtdp-silver-refresh-job` is a validated production component with an established execution proof. Mutating it during the migration adds unnecessary risk to a known-good path.
- A dedicated dbt job produces a purpose-built container that is easier to reason about, test independently, and roll back without affecting the Python job.
- The existing `rtdp-scheduler-sa` and `roles/run.invoker` grant can be reused; the primary new resource is the Cloud Run Job definition itself.
- If the Terraform skeleton for the Cloud Run Job proves difficult (e.g. the existing import diverges), fall back to Option A only if Option B is blocked by a concrete structural obstacle. Document the reason.

Option A is acceptable if the migration branch reveals that adapting the existing job is lower-risk given the current Terraform state. Option C is only appropriate if the migration is deprioritised or deferred indefinitely.

---

## Credential and Profile Handling for Cloud Run Without Committing dbt/profiles.yml

The following constraints apply throughout all migration phases:

1. `dbt/profiles.yml` must never be committed to the repository. It is listed in `.gitignore`.
2. Cloud SQL credentials must never be embedded in Dockerfile build arguments or container image layers.
3. The only accepted credential pattern is runtime injection via environment variables bound to Secret Manager secrets.

**Proposed pattern for Cloud Run:**

The job's container entrypoint writes a temporary `profiles.yml` using environment variables:

```bash
#!/bin/bash
set -euo pipefail

# Write profiles.yml from env vars at container startup
PROFILES_DIR=/tmp/dbt-profiles
mkdir -p "$PROFILES_DIR"

cat > "$PROFILES_DIR/profiles.yml" <<EOF
rtdp:
  target: cloudsql
  outputs:
    cloudsql:
      type: postgres
      host: "${DBT_HOST}"
      port: ${DBT_PORT}
      user: "${DBT_USER}"
      password: "${DBT_PASSWORD}"
      dbname: "${DBT_DBNAME}"
      schema: public
      threads: 1
EOF

exec dbt run --project-dir /app/dbt --profiles-dir "$PROFILES_DIR" --target cloudsql "$@"
```

Environment variables (`DBT_HOST`, `DBT_PORT`, `DBT_USER`, `DBT_PASSWORD`, `DBT_DBNAME`) are populated at Cloud Run Job runtime from Secret Manager references. The existing `rtdp-database-url` secret can be decomposed into individual variables via a startup script, or individual secrets can be added to Secret Manager.

The generated file is written to a container-local directory (`/tmp/dbt-profiles`) that is not mounted to any volume and is discarded when the container exits. No credential ever reaches the repository.

---

## Rollback Strategy

| Scenario | Rollback Action |
|---|---|
| `dbt run` fails mid-execution (table dropped, not yet recreated) | Call stored function via `psql`: `SELECT silver.refresh_market_event_minute_aggregates();` then `SELECT gold.refresh_market_event_daily_aggregates();` |
| dbt job exits non-zero | Trigger `rtdp-silver-refresh-job` manually via Cloud Run or Cloud Console |
| API returns HTTP 5xx after dbt run | Verify schema matches; restore with stored functions; file a bug before re-attempting |
| Cloud SQL not returning to STOPPED | P1 incident per `docs/SLO_AND_INCIDENT_RESPONSE.md`; stop Auth Proxy immediately |
| New Cloud Run Job deploy fails | Revert to previous revision; do not change the scheduler config until new job is healthy |
| Scheduler points to new job; job fails on first scheduled run | Pause scheduler immediately; invoke stored function manually; investigate before resume |

The stored functions in `infra/postgres/init.sql` use `ON CONFLICT ... DO UPDATE` semantics and are safe to call against tables that were last populated by dbt. Running the stored function after a failed `dbt run` will restore or update the table without data loss.

---

## Failure Modes

| Failure | Detection | Impact | Mitigation |
|---|---|---|---|
| `dbt profiles.yml` committed accidentally | `git status` check; `grep -R profiles.yml dbt/` | Credential exposure risk | Rotate credentials immediately; remove the file from history |
| dbt drops silver table before recreating it (interrupted run) | Cloud Run Job exit code non-zero; table absent in `psql` | Silver aggregate query returns no rows | Rollback via stored function; table is recreated idempotently |
| Schema mismatch between dbt output and API expectations | `/aggregates/minute` or `/aggregates/daily` return HTTP 5xx | Serving layer degraded | Restore with stored function; verify column names in dbt model against API query |
| Cloud SQL not stopped after migration window | `NEVER / STOPPED` state not confirmed at end of validation | Cost overrun | P1 per SLO document; immediate manual stop via GCP Console or `gcloud sql instances patch` |
| Scheduler resumes before evidence approval | Scheduled dbt runs hit Cloud SQL at `*/15 * * * *` cadence | Unexpected compute cost; Cloud SQL must remain stopped | Keep scheduler in `PAUSED` state until Phase 7 evidence is accepted |
| dbt test failures after `dbt run` | `dbt test` exits non-zero | Data quality assertion failed | Do not update scheduler config; investigate failing test; restore with stored function if data is suspect |
| New Cloud Run Job image missing `dbt/` directory | `dbt: command not found` or `No such file or directory` | Job fails on first execution | Fix Dockerfile COPY paths; test locally before Cloud Run deploy |

---

## Acceptance Criteria

The migration branch is complete and ready to merge when all of the following are confirmed and evidenced:

| Criterion | Evidence Required |
|---|---|
| `main` is clean and CI green before branching | `git status` + `gh run list` captured |
| Three consecutive green dbt CI builds on `main` | GitHub Actions run list showing 3× both `validate` and `dbt` jobs green |
| Decision matrix option selected and documented | PR description |
| Credential/profile approach documented and no `dbt/profiles.yml` committed | `git status --ignored --short dbt` shows no tracked profile |
| `dbt compile` exits 0 against live Cloud SQL | Captured output file |
| `dbt run` materialises both models, row counts logged | `dbt-run-output.txt` evidence file |
| `dbt test` passes all 22 tests | `dbt-test-output.txt` evidence file |
| `/aggregates/minute` returns HTTP 200 with rows | `api-aggregates-minute-readback.txt` evidence file |
| `/aggregates/daily` returns HTTP 200 with rows | `api-aggregates-daily-readback.txt` evidence file |
| Cloud SQL returned to `NEVER / STOPPED` after validation window | `cloud-sql-stop-final.txt` evidence file |
| Stored functions still present in `infra/postgres/init.sql` | `grep -c "CREATE OR REPLACE FUNCTION" infra/postgres/init.sql` returns 2 |
| No generated dbt artifacts committed | `git status --ignored --short dbt` shows no `target/` or `dbt_packages/` |
| Scheduler remains `PAUSED` | `gcloud scheduler jobs describe` captured in evidence |
| `uv run pytest -q` passes | CI green or local capture |
| `uv run ruff check .` clean | CI green or local capture |

---

## Non-Goals

This document is planning only. The following are explicitly out of scope for the migration branch that executes this plan:

- No execution in this branch (`docs/dbt-operational-migration-plan`).
- No Cloud SQL mutation; Cloud SQL must remain `NEVER / STOPPED`.
- No production scheduler change; `rtdp-silver-refresh-scheduler` must remain `PAUSED`.
- No deletion of stored functions from `infra/postgres/init.sql`.
- No Terraform apply.
- No changes to GitHub Actions workflows.
- No changes to dbt models, macros, or tests.
- No incremental model conversion (that remains a post-migration optimisation).
- No BigQuery adapter or Dataflow integration.
- No automatic deploy-on-merge for dbt runs.

---

## Recruiter-Facing Summary

This platform has progressed from a local-first streaming pipeline to a fully evidence-backed GCP production-light deployment, covering Pub/Sub ingestion, Cloud Run workers, Cloud SQL persistence, Terraform IaC, CI/CD, observability, and load testing.

The current dbt migration track demonstrates governed, evidence-driven migration from stored SQL functions toward dbt-based transformation operations:

1. **Governance plan** (`docs/dbt-transformation-governance-plan.md`): modelled the migration strategy before writing code.
2. **Local implementation** (PR #104): silver and gold dbt models with 22 schema and business-rule tests.
3. **CI validation** (PR #105): dbt compile, run, and test on every push to `main` against an ephemeral pgvector container.
4. **Cloud SQL validation** (`docs/dbt-cloud-sql-validation-evidence.md`): controlled window proving output parity between stored functions and dbt models; API readback confirmed; Cloud SQL returned to `NEVER / STOPPED`.
5. **Operational migration plan** (this document): explicit phases, decision matrix, credential strategy, rollback paths, and acceptance criteria for the next implementation branch.

The platform now demonstrates that a real-world data engineering migration — from legacy stored functions to a governed dbt layer — can be executed safely, with evidence at each step, without breaking the operational serving path or incurring unexpected cloud costs.

The next implementation branch (`feat/dbt-cloud-sql-migration`) will execute the plan defined here.
