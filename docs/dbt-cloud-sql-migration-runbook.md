# dbt Cloud SQL Migration Runbook

**Status: RUNBOOK ONLY — NOT EXECUTED**

Execute only on a dedicated `evidence/dbt-cloud-sql-validation` branch during a
controlled validation window. This runbook branch does not start or modify Cloud SQL;
final Cloud SQL state is captured during the execution branch.

---

## Objective

Validate the dbt silver and gold models directly against Cloud SQL (`rtdp-postgres`,
`europe-west1`) and produce a reconciled evidence record demonstrating that dbt output
is functionally equivalent to the stored-function output.

This covers governance plan section 10, step 3. It does not replace stored functions
or change the Cloud Run Job.

---

## Preconditions

| Precondition | Expected State |
|---|---|
| Active branch | `main` — all changes merged, history clean |
| CI status | Green on latest main commit (22 dbt tests + 117 pytest) |
| Cloud SQL state | `NEVER / STOPPED` confirmed |
| Scheduler state | `PAUSED` |
| No `dbt/target/` or `dbt/dbt_packages/` | Gitignored; not present as tracked files |
| Cloud SQL Auth Proxy binary | `cloud-sql-proxy` on PATH |
| `gcloud` CLI | Authenticated; Secret Manager and Cloud SQL permissions |
| `psql` client | Installed locally |

---

## Safety Guardrails

1. **Execute on the dedicated branch only.** Do not run any step on this docs branch.
2. **No `dbt/profiles.yml` in the repository.** `dbt/profiles.yml` is never committed —
   only `dbt/profiles.yml.example` is. Generate the Cloud SQL profile to
   `/tmp/rtdp-dbt-cloudsql/profiles.yml` (outside the repo tree) and delete it in cleanup.
3. **Do not print credentials.** Set `DATABASE_URL` and `PGPASSWORD` as shell variables
   only; verify non-empty without echoing values.
4. **Use libpq env vars for all psql commands.** Do not construct URLs containing
   passwords.
5. **Capture stored-function baseline before `dbt run`.** dbt table materialization drops
   and recreates silver and gold tables — there is no reconciliation window after the drop.
6. **Start Cloud SQL only at Phase 3; stop immediately after Phase 12.** If stop fails,
   treat as P1 per [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md).
7. **Do not modify runtime code, dbt models, GitHub Actions, or Terraform.**

---

## Current Authority Model

| Layer | Table | Authoritative Mechanism |
|---|---|---|
| silver | `silver.market_event_minute_aggregates` | `silver.refresh_market_event_minute_aggregates()` |
| gold | `gold.market_event_daily_aggregates` | `gold.refresh_market_event_daily_aggregates()` |

dbt is CI-validated (22 tests against an ephemeral container on every PR). Cloud SQL
automated dbt execution is not yet operational. Stored functions in
`infra/postgres/init.sql` remain authoritative until this runbook is executed and its
evidence is accepted.

---

## Controlled Validation Phases

### Phase 1 — Pre-flight checks

```bash
git checkout main && git pull origin main
git status            # must be clean
git log --oneline -3
gh run list --branch main --limit 3   # validate and dbt jobs must both be green
```

Expected: `nothing to commit, working tree clean`; latest CI run green on both jobs.

Capture as: `docs/evidence/dbt-cloud-sql-validation/baseline-git-state.txt`

---

### Phase 2 — Confirm Cloud SQL initial state

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected: `NEVER` / `STOPPED`. Do not proceed if the instance is in any other state.

Capture as: `docs/evidence/dbt-cloud-sql-validation/baseline-cloud-sql-state.txt`

---

### Phase 3 — Start Cloud SQL validation window

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy ALWAYS \
  --project=project-42987e01-2123-446b-ac7

gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Expected final state: `ALWAYS / RUNNABLE`.

Capture as: `docs/evidence/dbt-cloud-sql-validation/cloud-sql-start-window.txt`

---

### Phase 4 — Start Cloud SQL Auth Proxy via TCP

The production `DATABASE_URL` uses a Cloud Run Unix socket path not accessible on
macOS. Expose a local TCP endpoint at `127.0.0.1:5433` via the Auth Proxy.

```bash
cloud-sql-proxy project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres \
  --port=5433 &
PROXY_PID=$!
echo "Proxy PID: $PROXY_PID"
sleep 3
nc -z 127.0.0.1 5433 && echo "PROXY_TCP_LISTENING=true"
```

Capture as: `docs/evidence/dbt-cloud-sql-validation/proxy-connection-test.txt`

---

### Phase 5 — Retrieve credentials and set libpq env vars

Retrieve `DATABASE_URL` from Secret Manager silently. Extract the password and export
libpq variables so all subsequent `psql` commands connect without a URL. Do not print
any credential value.

```bash
# Retrieve secret — do NOT echo DATABASE_URL
DATABASE_URL=$(gcloud secrets versions access latest \
  --secret=rtdp-database-url \
  --project=project-42987e01-2123-446b-ac7)

[ -n "$DATABASE_URL" ] && echo "DATABASE_URL retrieved (not printed)" \
                       || { echo "ERROR: empty"; exit 1; }

# Extract password using an inline subprocess — DATABASE_URL not exported globally
PGPASSWORD=$(DATABASE_URL="$DATABASE_URL" python3 - <<'PYEOF'
import os, urllib.parse
u = urllib.parse.urlparse(os.environ.get("DATABASE_URL", ""))
print(u.password or "")
PYEOF
)
export PGPASSWORD

[ -n "$PGPASSWORD" ] && echo "Password extracted (not printed)" \
                     || { echo "ERROR: extraction failed"; exit 1; }

# Set remaining libpq vars (no credentials embedded)
export PGHOST=127.0.0.1
export PGPORT=5433
export PGUSER=rtdp
export PGDATABASE=realtime_platform
```

All subsequent `psql` commands rely on these env vars — no URL construction required.

---

### Phase 6 — Generate temporary dbt profiles.yml

Create the Cloud SQL profile in a temp directory **outside the repository tree**.
`dbt/profiles.yml` is never committed; this file must not enter the repo.

```bash
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
echo "Profile written to $PROFILES_DIR/profiles.yml (outside repo)"

# Export under the name dbt expects via env_var()
export DBT_CLOUDSQL_PASSWORD="$PGPASSWORD"

# Confirm repo is still clean
git status
```

Expected: `nothing to commit, working tree clean`.

---

### Phase 7 — dbt deps and compile

```bash
PROFILES_DIR=/tmp/rtdp-dbt-cloudsql

uv run dbt deps \
  --project-dir dbt --profiles-dir "$PROFILES_DIR" --target cloudsql

uv run dbt compile \
  --project-dir dbt --profiles-dir "$PROFILES_DIR" --target cloudsql \
  2>&1 | tee /tmp/rtdp-dbt-cloudsql/dbt-compile-output.txt
```

Expected: exit 0, no missing refs. If compile fails, stop Cloud SQL before debugging.

---

### Phase 8 — Stored-function baseline (BEFORE dbt run)

dbt table materialization will DROP and recreate silver and gold. Capture the
stored-function baseline now, before those tables are overwritten.

```bash
# Refresh using stored functions
psql -c "SELECT silver.refresh_market_event_minute_aggregates() AS silver_affected_rows;"
psql -c "SELECT gold.refresh_market_event_daily_aggregates() AS gold_affected_rows;"

# Capture counts and sample rows
psql \
  -c "SELECT COUNT(*) AS silver_row_count FROM silver.market_event_minute_aggregates;" \
  -c "SELECT COUNT(*) AS gold_row_count FROM gold.market_event_daily_aggregates;" \
  -c "SELECT symbol, window_start, event_count, avg_price FROM silver.market_event_minute_aggregates ORDER BY window_start DESC, symbol LIMIT 5;" \
  -c "SELECT symbol, event_date, event_count, avg_price, min_price, max_price FROM gold.market_event_daily_aggregates ORDER BY event_date DESC, symbol LIMIT 5;" \
  2>&1 | tee /tmp/rtdp-dbt-cloudsql/stored-function-baseline.txt
```

---

### Phase 9 — dbt run

```bash
uv run dbt run \
  --project-dir dbt --profiles-dir "$PROFILES_DIR" --target cloudsql \
  2>&1 | tee /tmp/rtdp-dbt-cloudsql/dbt-run-output.txt
```

Expected: 2 models created (`silver.market_event_minute_aggregates`,
`gold.market_event_daily_aggregates`), exit 0.

If `dbt run` fails mid-execution, proceed immediately to the rollback plan — do not
stop Cloud SQL until tables are restored.

---

### Phase 10 — dbt test

```bash
uv run dbt test \
  --project-dir dbt --profiles-dir "$PROFILES_DIR" --target cloudsql \
  2>&1 | tee /tmp/rtdp-dbt-cloudsql/dbt-test-output.txt
```

Expected: 22 passed, 0 warnings, 0 errors.

---

### Phase 11 — Post-dbt comparison

Run the same queries as Phase 8 to verify dbt produced identical results.

```bash
psql \
  -c "SELECT COUNT(*) AS silver_row_count FROM silver.market_event_minute_aggregates;" \
  -c "SELECT COUNT(*) AS gold_row_count FROM gold.market_event_daily_aggregates;" \
  -c "SELECT symbol, window_start, event_count, avg_price FROM silver.market_event_minute_aggregates ORDER BY window_start DESC, symbol LIMIT 5;" \
  -c "SELECT symbol, event_date, event_count, avg_price, min_price, max_price FROM gold.market_event_daily_aggregates ORDER BY event_date DESC, symbol LIMIT 5;" \
  2>&1 | tee /tmp/rtdp-dbt-cloudsql/dbt-output-comparison.txt
```

Acceptance: row counts must match Phase 8 baseline; sample rows must be identical.

---

### Phase 12 — FastAPI readback

```bash
API_URL="https://rtdp-api-fpy4of3i5a-ew.a.run.app"

curl -sS "${API_URL}/aggregates/minute?limit=5" \
  -w "\nHTTP_STATUS=%{http_code}\n" \
  | tee /tmp/rtdp-dbt-cloudsql/api-aggregates-minute-readback.txt

curl -sS "${API_URL}/aggregates/daily?limit=5" \
  -w "\nHTTP_STATUS=%{http_code}\n" \
  | tee /tmp/rtdp-dbt-cloudsql/api-aggregates-daily-readback.txt
```

Expected: both return `HTTP_STATUS=200` with at least one row.

---

### Phase 13 — Stop Cloud SQL

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy NEVER \
  --project=project-42987e01-2123-446b-ac7

gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)" \
  2>&1 | tee /tmp/rtdp-dbt-cloudsql/cloud-sql-stop-final.txt
```

Expected: `NEVER / STOPPED`. If not reached, P1 incident per
[docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md).
Do not proceed to cleanup until this state is confirmed.

---

### Phase 14 — Cleanup and evidence capture

```bash
# Stop proxy
kill "$PROXY_PID" 2>/dev/null || pkill -f "cloud-sql-proxy" || true
echo "Proxy stopped"

# Unset all credential variables
unset DATABASE_URL DBT_CLOUDSQL_PASSWORD PGPASSWORD PGHOST PGPORT PGUSER PGDATABASE
echo "Credential env vars unset"

# Delete temp profile
rm -f /tmp/rtdp-dbt-cloudsql/profiles.yml
echo "Temp profile deleted"

# Confirm repo is clean
git status

# Copy evidence files
mkdir -p docs/evidence/dbt-cloud-sql-validation
cp /tmp/rtdp-dbt-cloudsql/dbt-compile-output.txt        docs/evidence/dbt-cloud-sql-validation/
cp /tmp/rtdp-dbt-cloudsql/stored-function-baseline.txt   docs/evidence/dbt-cloud-sql-validation/
cp /tmp/rtdp-dbt-cloudsql/dbt-run-output.txt             docs/evidence/dbt-cloud-sql-validation/
cp /tmp/rtdp-dbt-cloudsql/dbt-test-output.txt            docs/evidence/dbt-cloud-sql-validation/
cp /tmp/rtdp-dbt-cloudsql/dbt-output-comparison.txt      docs/evidence/dbt-cloud-sql-validation/
cp /tmp/rtdp-dbt-cloudsql/api-aggregates-minute-readback.txt docs/evidence/dbt-cloud-sql-validation/
cp /tmp/rtdp-dbt-cloudsql/api-aggregates-daily-readback.txt  docs/evidence/dbt-cloud-sql-validation/
cp /tmp/rtdp-dbt-cloudsql/cloud-sql-stop-final.txt       docs/evidence/dbt-cloud-sql-validation/

ls -la docs/evidence/dbt-cloud-sql-validation/
```

Create `docs/dbt-cloud-sql-validation-evidence.md` summarising run outcomes. Follow the
format of [docs/gold-cloud-sql-deployment-evidence.md](gold-cloud-sql-deployment-evidence.md).

---

## Expected Evidence Files

All files must exist under `docs/evidence/dbt-cloud-sql-validation/` on the evidence
branch for this runbook to be considered successfully executed.

| File | Phase | Contents |
|---|---|---|
| `baseline-git-state.txt` | 1 | Clean `git status`, CI green on both jobs |
| `baseline-cloud-sql-state.txt` | 2 | `NEVER / STOPPED` before start |
| `cloud-sql-start-window.txt` | 3 | `ALWAYS / RUNNABLE` after start |
| `proxy-connection-test.txt` | 4 | Proxy PID, `PROXY_TCP_LISTENING=true` |
| `dbt-compile-output.txt` | 7 | Full compile output, exit 0 |
| `stored-function-baseline.txt` | 8 | Silver and gold counts + sample rows pre-dbt |
| `dbt-run-output.txt` | 9 | 2 models created, exit 0 |
| `dbt-test-output.txt` | 10 | 22 passed, 0 errors |
| `dbt-output-comparison.txt` | 11 | Silver and gold counts + sample rows post-dbt |
| `api-aggregates-minute-readback.txt` | 12 | HTTP 200, rows present |
| `api-aggregates-daily-readback.txt` | 12 | HTTP 200, rows present |
| `cloud-sql-stop-final.txt` | 13 | `NEVER / STOPPED` confirmed |

---

## Rollback Plan

### If `dbt run` fails mid-execution

dbt drops the original table before renaming the temp. If interrupted, the table may be
absent. With the libpq env vars still set and the proxy running:

```bash
psql -f infra/postgres/init.sql    # recreate missing tables (idempotent)
psql -c "SELECT silver.refresh_market_event_minute_aggregates();"
psql -c "SELECT gold.refresh_market_event_daily_aggregates();"
psql -c "SELECT COUNT(*) FROM silver.market_event_minute_aggregates;"
psql -c "SELECT COUNT(*) FROM gold.market_event_daily_aggregates;"
```

Capture restored state as an additional evidence file, then proceed to Phase 13.

### If FastAPI returns HTTP 5xx after dbt run

Check response body for schema mismatch. Restore with stored functions:

```bash
psql -c "SELECT silver.refresh_market_event_minute_aggregates();"
psql -c "SELECT gold.refresh_market_event_daily_aggregates();"
```

If readback still fails, stop Cloud SQL and file a bug before re-attempting.

### If Cloud SQL cannot be stopped

P1 incident per [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md).
Stop the Auth Proxy immediately. Do not commit any partial evidence.

---

## Acceptance Criteria

| Criterion | Required |
|---|---|
| Cloud SQL baseline `NEVER / STOPPED` captured before Phase 3 | Yes |
| Auth Proxy TCP connection confirmed | Yes |
| `DATABASE_URL` retrieved without printing | Yes |
| libpq env vars used; no URL with embedded password constructed | Yes |
| Temp `profiles.yml` in `/tmp/` only; not in repo; deleted in cleanup | Yes |
| `dbt compile` exits 0 | Yes |
| Stored-function baseline captured BEFORE `dbt run` | Yes |
| `dbt run` materialises both models, exits 0 | Yes |
| `dbt test` passes all 22 tests | Yes |
| Row counts match between stored-function baseline and dbt output | Yes |
| `GET /aggregates/minute` returns HTTP 200 with rows | Yes |
| `GET /aggregates/daily` returns HTTP 200 with rows | Yes |
| Cloud SQL returned to `NEVER / STOPPED` after validation | Yes |
| Proxy stopped; all credential env vars unset | Yes |
| No `dbt/profiles.yml` or Cloud SQL credentials committed | Yes |
| No `dbt/target/` or `dbt/dbt_packages/` committed | Yes |
| Git working tree clean at start and end | Yes |
| No `terraform apply` executed | Yes |
| All 12 evidence files present under `docs/evidence/dbt-cloud-sql-validation/` | Yes |
| `docs/dbt-cloud-sql-validation-evidence.md` created on evidence branch | Yes |

---

## Explicit Non-Goals

- No automatic production migration or removal of stored functions.
- No Cloud Run Job change — `rtdp-silver-refresh-job` continues calling the stored
  function. Migration to `dbt run` is gated on accepted evidence and three consecutive
  green CI builds.
- No Terraform apply.
- No incremental model conversion for this validation phase.
- No Cloud Scheduler resume.

---

## Remaining Post-Run Steps

### Evidence branch

1. Create `evidence/dbt-cloud-sql-validation` from `main`.
2. Copy the 12 evidence files to `docs/evidence/dbt-cloud-sql-validation/`.
3. Write `docs/dbt-cloud-sql-validation-evidence.md`.
4. Update `docs/EVIDENCE_INDEX.md` and `docs/ARCHITECTURE_REVIEW.md`.
5. Open PR into `main`; CI must be green before merge.

### Migration branch (only after evidence is accepted and merged)

On `feat/dbt-cloud-sql-migration`:
1. Replace the Cloud Run Job's stored-function call with `dbt run --select silver,gold`.
2. Validate three consecutive green CI builds on `main`.
3. Remove stored functions from `infra/postgres/init.sql` only after all three pass.

---

## Related Documents

| Document | Purpose |
|---|---|
| [docs/dbt-transformation-governance-plan.md](dbt-transformation-governance-plan.md) | Full migration strategy; section 10 is the source for this runbook |
| [docs/dbt-ci-validation-evidence.md](dbt-ci-validation-evidence.md) | CI validation evidence: 22 dbt tests, ephemeral container |
| [docs/gold-cloud-sql-deployment-runbook.md](gold-cloud-sql-deployment-runbook.md) | Reference: controlled Cloud SQL window pattern |
| [docs/gold-cloud-sql-deployment-evidence.md](gold-cloud-sql-deployment-evidence.md) | Reference: Auth Proxy TCP, Cloud SQL start/stop pattern |
| [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) | Incident response for P1 failures |
| [dbt/README.md](../dbt/README.md) | dbt local execution and coexistence notes |
| [infra/postgres/init.sql](../infra/postgres/init.sql) | Authoritative stored functions |
