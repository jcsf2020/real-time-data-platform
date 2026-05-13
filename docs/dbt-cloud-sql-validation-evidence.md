# dbt Cloud SQL Validation Evidence

**Status:** EXECUTED SUCCESSFULLY  
**Branch:** `evidence/dbt-cloud-sql-validation`  
**Scope:** Controlled dbt validation against Cloud SQL.

---

## Summary

This evidence records a controlled validation of the dbt transformation layer against the real Cloud SQL instance `rtdp-postgres`.

The validation confirmed that:

- Cloud SQL was started only for the validation window.
- Cloud SQL Auth Proxy TCP connection worked.
- dbt compiled successfully against Cloud SQL.
- Stored-function baseline was captured before dbt execution.
- dbt materialised the same silver and gold row counts as the stored functions.
- dbt tests passed against Cloud SQL.
- FastAPI readback returned HTTP 200 for both aggregate endpoints.
- Cloud SQL was returned to `NEVER / STOPPED`.
- Local credentials, proxy, temp profiles, and dbt artifacts were cleaned.

---

## Validation Results

| Check | Result |
|---|---|
| Baseline Cloud SQL state | `NEVER / STOPPED` |
| Cloud SQL validation state | `ALWAYS / RUNNABLE` |
| Auth Proxy TCP check | `PROXY_TCP_LISTENING=true` |
| dbt deps | Passed |
| dbt compile | Passed |
| Stored-function silver baseline | 256 rows |
| Stored-function gold baseline | 7 rows |
| dbt run silver output | 256 rows |
| dbt run gold output | 7 rows |
| dbt test | 22 passed, 0 warnings, 0 errors |
| `/aggregates/minute` API readback | HTTP 200 |
| `/aggregates/daily` API readback | HTTP 200 |
| Final Cloud SQL state | `NEVER / STOPPED` |

---

## Stored Functions vs dbt Comparison

The stored-function baseline was captured before `dbt run`.

| Layer | Stored-function baseline | dbt output | Match |
|---|---:|---:|---|
| Silver minute aggregates | 256 | 256 | Yes |
| Gold daily aggregates | 7 | 7 | Yes |

This confirms that the dbt models reproduced the current Cloud SQL transformation output for the validation dataset.

---

## API Readback

After `dbt run`, the Cloud Run API was queried against the dbt-populated Cloud SQL tables.

| Endpoint | Result |
|---|---|
| `/aggregates/minute?limit=5` | HTTP 200 with rows |
| `/aggregates/daily?limit=5` | HTTP 200 with rows |

This confirms the serving layer can read dbt-populated silver and gold tables without runtime schema mismatch.

---

## Evidence Files

Evidence artifacts are stored under:

`docs/evidence/dbt-cloud-sql-validation/`

Expected captured files:

- `baseline-git-state.txt`
- `ci-green-confirmation.txt`
- `baseline-cloud-sql-state.txt`
- `cloud-sql-start-window.txt`
- `proxy-connection-test.txt`
- `database-url-and-profile-setup.txt`
- `dbt-deps-output.txt`
- `dbt-compile-output.txt`
- `stored-function-baseline.txt`
- `dbt-run-output.txt`
- `dbt-test-output.txt`
- `dbt-output-comparison.txt`
- `api-aggregates-minute-readback.txt`
- `api-aggregates-daily-readback.txt`
- `cloud-sql-stop-final.txt`
- `local-cleanup.txt`

---

## Safety Confirmation

| Control | Status |
|---|---|
| No Terraform change | Confirmed |
| No runtime code change | Confirmed |
| No dbt model change | Confirmed |
| No GitHub Actions workflow change | Confirmed |
| Cloud SQL stopped after validation | Confirmed: `NEVER / STOPPED` |
| Auth Proxy stopped | Confirmed |
| Local credential variables unset | Confirmed |
| Temporary dbt profile removed | Confirmed |
| `dbt/profiles.yml` absent from repo | Confirmed |
| Generated dbt artifacts cleaned | Confirmed |

---

## Remaining Decision

This validation proves dbt can reproduce the stored-function outputs against Cloud SQL and that the API can read dbt-populated tables.

However, this branch does **not** migrate production execution.

Stored functions remain authoritative until a future migration branch changes the operational refresh path from stored functions to dbt.
