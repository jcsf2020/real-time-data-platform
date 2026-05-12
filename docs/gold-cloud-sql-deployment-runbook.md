# Gold Cloud SQL Deployment Runbook

This is a future execution runbook. It does not prove deployment has occurred.
Execute only in a controlled validation window on a dedicated execution branch.
Cloud SQL default resting state remains `NEVER / STOPPED`.

---

## Objective

Deploy the already implemented local gold layer to Cloud SQL (`rtdp-postgres`, `europe-west1`):

- `gold.market_event_daily_aggregates` table (`CREATE TABLE IF NOT EXISTS`)
- `gold.refresh_market_event_daily_aggregates()` function (`CREATE OR REPLACE FUNCTION`)
- Validate `GET /aggregates/daily` after refresh

---

## Current State

| Item | State |
|---|---|
| Gold SQL | Implemented in `infra/postgres/init.sql` |
| `/aggregates/daily` endpoint | Implemented in `apps/api/src/rtdp_api/__init__.py` |
| Local evidence | `docs/gold-daily-aggregates-evidence.md` |
| Cloud SQL deployment | Evidence pending -- this runbook prepares the execution path |
| Cloud SQL instance | `rtdp-postgres`, activation policy `NEVER / STOPPED` |

---

## Safety Rules

- Do not execute any deployment step on this docs branch.
- Do not connect to Cloud SQL outside of an approved execution branch.
- Do not run `terraform apply`.
- Capture baseline state before any mutation.
- Start Cloud SQL only for a bounded validation window; stop it immediately after.
- Preserve all terminal output and SQL responses as evidence files.
- Use only `CREATE SCHEMA IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`,
  `CREATE OR REPLACE FUNCTION`. No `DROP TABLE`, `DELETE`, or `TRUNCATE`.
- Document a rollback strategy on the execution branch before applying any SQL.
- If Cloud SQL cannot be stopped, treat as an incident per `docs/SLO_AND_INCIDENT_RESPONSE.md`.

---

## Pre-Execution Checklist

| Check | Expected |
|---|---|
| `git status` clean | No uncommitted changes |
| Active branch | `evidence/gold-cloud-sql-deployment` (suggested) |
| Cloud SQL state before start | `NEVER / STOPPED` |
| API current revision | Confirm via `gcloud run revisions list --service rtdp-api` |
| API current image | Confirm SHA tag from revision description |
| `/aggregates/daily` behavior pre-deploy | Likely HTTP 500 or empty if gold table absent; confirm actual behavior |
| Backup / export decision | Document whether a pre-deploy export is required |
| `DATABASE_URL` access method | Via Secret Manager secret `rtdp-database-url` |
| Database connection method | Cloud SQL Auth Proxy or existing approved proxy configuration |

---

## SQL To Apply

Extract from `infra/postgres/init.sql`. Apply in a single `psql` session.

```sql
CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.market_event_daily_aggregates (
    symbol TEXT NOT NULL,
    event_date DATE NOT NULL,
    event_count BIGINT NOT NULL,
    avg_price NUMERIC(18, 8) NOT NULL,
    min_price NUMERIC(18, 8) NOT NULL,
    max_price NUMERIC(18, 8) NOT NULL,
    total_quantity NUMERIC(18, 8) NOT NULL,
    first_event_timestamp TIMESTAMPTZ NOT NULL,
    last_event_timestamp TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, event_date)
);

CREATE OR REPLACE FUNCTION gold.refresh_market_event_daily_aggregates()
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    affected_rows BIGINT;
BEGIN
    INSERT INTO gold.market_event_daily_aggregates (
        symbol, event_date, event_count, avg_price, min_price, max_price,
        total_quantity, first_event_timestamp, last_event_timestamp, updated_at
    )
    SELECT
        symbol,
        event_timestamp::date AS event_date,
        COUNT(*) AS event_count,
        AVG(price)::NUMERIC(18, 8) AS avg_price,
        MIN(price)::NUMERIC(18, 8) AS min_price,
        MAX(price)::NUMERIC(18, 8) AS max_price,
        SUM(quantity)::NUMERIC(18, 8) AS total_quantity,
        MIN(event_timestamp) AS first_event_timestamp,
        MAX(event_timestamp) AS last_event_timestamp,
        NOW() AS updated_at
    FROM bronze.market_events
    GROUP BY symbol, event_timestamp::date
    ON CONFLICT (symbol, event_date)
    DO UPDATE SET
        event_count = EXCLUDED.event_count,
        avg_price = EXCLUDED.avg_price,
        min_price = EXCLUDED.min_price,
        max_price = EXCLUDED.max_price,
        total_quantity = EXCLUDED.total_quantity,
        first_event_timestamp = EXCLUDED.first_event_timestamp,
        last_event_timestamp = EXCLUDED.last_event_timestamp,
        updated_at = NOW();

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows;
END;
$$;
```

---

## Execution Plan

1. **Baseline capture** -- Record Cloud SQL state, API revision, and current `/aggregates/daily` response. Save to `docs/evidence/gold-cloud-sql-deployment/baseline-before-deploy.txt`.
2. **Start Cloud SQL** -- Start `rtdp-postgres`; confirm state transitions to `RUNNABLE`.
3. **Connect** -- Use Cloud SQL Auth Proxy or `$DATABASE_URL` from Secret Manager. Do not expose credentials.
4. **Apply gold SQL** -- Execute the SQL block above in a single `psql` session. Capture full output.
5. **Verify existence** -- Confirm table and function appear in `information_schema.tables` and `information_schema.routines`.
6. **Run refresh** -- `SELECT gold.refresh_market_event_daily_aggregates();`
7. **Validate counts** -- `SELECT COUNT(*) FROM gold.market_event_daily_aggregates;` and `SELECT * FROM gold.market_event_daily_aggregates ORDER BY event_date DESC, symbol LIMIT 10;`
8. **Validate API** -- `curl "$API_URL/aggregates/daily?limit=10"` -- expected HTTP 200.
9. **Capture evidence** -- Save all outputs to `docs/evidence/gold-cloud-sql-deployment/`. Create `docs/gold-cloud-sql-deployment-evidence.md`.
10. **Stop Cloud SQL** -- Stop `rtdp-postgres`; verify activation policy returns to `NEVER / STOPPED`.

---

## Validation Commands

```bash
# Confirm Cloud SQL state (before start and after stop)
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"

# Connect and run SQL (Cloud SQL Auth Proxy must be running separately)
psql "$DATABASE_URL" \
  -c "\dt gold.*" \
  -c "SELECT gold.refresh_market_event_daily_aggregates();" \
  -c "SELECT COUNT(*) FROM gold.market_event_daily_aggregates;"

# Validate API endpoint
curl "$API_URL/aggregates/daily?limit=10"

# Confirm working tree is clean
git status
```

---

## Acceptance Criteria

| Criterion | Required |
|---|---|
| Cloud SQL baseline captured before any change | Yes |
| Gold SQL applied without error | Yes |
| `gold.market_event_daily_aggregates` table exists | Yes |
| `gold.refresh_market_event_daily_aggregates` function exists | Yes |
| Refresh returns integer >= 0 | Yes |
| `COUNT(*)` from gold table captured | Yes |
| `GET /aggregates/daily` returns HTTP 200 | Yes |
| Cloud SQL returned to `NEVER / STOPPED` | Yes |
| Evidence document created | Yes |
| No `terraform apply` executed | Yes |
| No workflow files modified | Yes |

---

## Rollback / Recovery

Table creation is additive. No existing schema, data, or function is overwritten.

- SQL fails before table creation: capture error, stop Cloud SQL, no rollback needed.
- Function definition incorrect: correct on a new branch and re-apply `CREATE OR REPLACE FUNCTION`.
- API returns error after deploy: verify table existence with a direct query before code changes.
- Cloud SQL cannot be stopped: treat as P1 incident per `docs/SLO_AND_INCIDENT_RESPONSE.md`.
- `DROP TABLE`: must not be executed without a separately approved destructive rollback plan.

---

## Evidence To Capture

- `docs/evidence/gold-cloud-sql-deployment/baseline-before-deploy.txt`
- `docs/evidence/gold-cloud-sql-deployment/sql-apply-output.txt`
- `docs/evidence/gold-cloud-sql-deployment/post-deploy-validation.txt`
- `docs/evidence/gold-cloud-sql-deployment/api-daily-readback.json`
- `docs/gold-cloud-sql-deployment-evidence.md`

---

## Out Of Scope

No dbt, no BigQuery, no Dataflow, no automatic deploy-on-merge, no `terraform apply`,
no permanent change to Cloud SQL activation policy.

---

## Related Evidence

- [docs/gold-daily-aggregates-evidence.md](gold-daily-aggregates-evidence.md) -- local implementation evidence
- [docs/SLO_AND_INCIDENT_RESPONSE.md](SLO_AND_INCIDENT_RESPONSE.md) -- incident response procedures
- [docs/ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) -- architecture and known gaps
- [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) -- full evidence map
- [docs/cloud-sql-terraform-import-plan-evidence.md](cloud-sql-terraform-import-plan-evidence.md) -- Cloud SQL Terraform state
- [docs/api-manual-deploy-evidence.md](api-manual-deploy-evidence.md) -- API deployment evidence
- [docs/load-test-5000-cloud-evidence.md](load-test-5000-cloud-evidence.md) -- most recent load test evidence
