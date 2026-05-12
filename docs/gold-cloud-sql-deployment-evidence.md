# Gold Cloud SQL Deployment Evidence

Branch: evidence/gold-cloud-sql-deployment
Status: GOLD CLOUD SQL DEPLOYMENT VALIDATED

## Objective

Deploy the locally implemented gold daily aggregate layer to Cloud SQL and validate the API readback path.

Validated path:

```text
Cloud SQL PostgreSQL -> gold.market_event_daily_aggregates -> gold.refresh_market_event_daily_aggregates() -> Cloud Run API /aggregates/daily
```

## Baseline

- Cloud SQL baseline before execution: NEVER / STOPPED.
- Production API initially served revision rtdp-api-00007-9gd using image tag 66ac7fef54496bc11635f946928d4a9afe8ecfcb.
- Initial GET /aggregates/daily returned HTTP 404 because the production API image did not yet include the route.

## API Redeploy Before SQL

- Manual workflow: Deploy API to Cloud Run.
- Run ID: 25752320444.
- Result: success.
- New revision: rtdp-api-00008-hk7.
- New image tag: 1922a55de0112c69cc6b16c31691dc38899620c2.
- After API redeploy, GET /aggregates/daily no longer returned HTTP 404.
- The endpoint timed out while Cloud SQL remained stopped, confirming that database validation required a controlled Cloud SQL window.

## Database Access

- DATABASE_URL was retrieved from Secret Manager without exposing the password.
- The production URL uses Cloud Run Unix socket access via host=/cloudsql/project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres.
- Local macOS could not create /cloudsql because the root filesystem is read-only.
- Cloud SQL Auth Proxy was installed and used through TCP on 127.0.0.1:5433.
- Read-only psql connection succeeded against database realtime_platform as user rtdp.

## SQL Applied

Only additive/idempotent SQL was applied:

```text
CREATE SCHEMA IF NOT EXISTS gold;
CREATE TABLE IF NOT EXISTS gold.market_event_daily_aggregates (...);
CREATE OR REPLACE FUNCTION gold.refresh_market_event_daily_aggregates();
```

SQL safety check:

```text
NO_DESTRUCTIVE_SQL_FOUND=true
```

Apply output:

```text
CREATE SCHEMA
CREATE TABLE
CREATE FUNCTION
```

No DROP, DELETE, or TRUNCATE was executed.

## Validation Results

- Table exists: gold.market_event_daily_aggregates.
- Function exists: gold.refresh_market_event_daily_aggregates.
- Refresh result: affected_rows = 7.
- Gold row count: gold_daily_rows = 7.
- API readback: GET /aggregates/daily?limit=10 returned HTTP/2 200.
- API returned 7 daily aggregate rows.

## Final State

- Cloud SQL was stopped after validation.
- Final Cloud SQL state: NEVER / STOPPED.
- Local Cloud SQL Auth Proxy was stopped.

## Evidence Files

| File | Purpose |
|---|---|
| docs/evidence/gold-cloud-sql-deployment/baseline-before-deploy.txt | Initial baseline: branch, Cloud SQL state, API revision, local gold SQL and endpoint |
| docs/evidence/gold-cloud-sql-deployment/api-daily-pre-deploy-readback.txt | Initial /aggregates/daily 404 before API redeploy |
| docs/evidence/gold-cloud-sql-deployment/pre-deploy-runtime-gap.txt | Runtime gap analysis: local route existed, production image was old |
| docs/evidence/gold-cloud-sql-deployment/api-deploy-validation-before-sql.txt | Manual API deploy validation and Cloud SQL state before SQL |
| docs/evidence/gold-cloud-sql-deployment/api-route-deployed-before-sql.txt | Confirms route deployed before SQL apply |
| docs/evidence/gold-cloud-sql-deployment/cloud-sql-start-window.txt | First Cloud SQL start-window capture |
| docs/evidence/gold-cloud-sql-deployment/sql-apply-missing-database-url.txt | Failed local psql attempt due to missing shell DATABASE_URL |
| docs/evidence/gold-cloud-sql-deployment/database-url-and-connection-test.txt | Unix socket connection failure on local Mac |
| docs/evidence/gold-cloud-sql-deployment/cloud-sql-stop-after-missing-proxy.txt | Cloud SQL stopped after missing proxy issue |
| docs/evidence/gold-cloud-sql-deployment/tcp-proxy-connection-test.txt | TCP proxy setup and read-only DB connection validation |
| docs/evidence/gold-cloud-sql-deployment/sql-apply-output.txt | Gold SQL apply output |
| docs/evidence/gold-cloud-sql-deployment/post-sql-validation.txt | Table, function, refresh, count, sample row validation |
| docs/evidence/gold-cloud-sql-deployment/api-daily-readback.txt | API /aggregates/daily HTTP 200 readback |
| docs/evidence/gold-cloud-sql-deployment/cloud-sql-stop-final.txt | Final Cloud SQL stop and proxy shutdown |

## Safety Notes

- Cloud SQL was started only for controlled validation.
- Cloud SQL was returned to NEVER / STOPPED.
- Local Cloud SQL Auth Proxy was stopped.
- No Terraform change was made.
- No terraform apply was executed.
- No workflow file was changed.
- No destructive SQL was executed.
- Production API was deployed through the existing validated manual workflow.
- The gold SQL deployment was additive and idempotent.

## Gap Closed

This closes the Cloud SQL deployment evidence gap for the gold daily aggregates layer.

The project now has bronze, silver, and gold layers validated through Cloud SQL and API readback.
