# API `/events` Pagination Fix — Production Deployment Evidence

## Status

**DEPLOYED — VALIDATED IN PRODUCTION**

The pagination bug discovered during the 1000-event cloud load test has been fixed, deployed, and
validated in production. The `/events` endpoint now correctly applies `OFFSET` pagination. Two
disjoint pages were retrieved from live production data confirming the fix. Cloud SQL was returned
to `NEVER / STOPPED` immediately after validation.

---

## Context: Bug Discovered During 1000-Event Load Test

During the accepted 1000-event cloud load test (see
[docs/load-test-1000-cloud-evidence.md](load-test-1000-cloud-evidence.md)), the following defects
were observed in the `/events` endpoint:

- `GET /events?limit=1000` returned only 100 rows — the endpoint enforced a hard maximum of 100
  regardless of the `limit` parameter.
- `GET /events?limit=5&offset=0` and `GET /events?limit=5&offset=5` returned identical rows —
  the `offset` query parameter was accepted by FastAPI but silently ignored in the SQL query.
- Full ingestion of all 1000 events was confirmed independently via Cloud Logging worker
  `status=ok` log entries and `worker_message_processed_count` Cloud Monitoring metric sum = 1000.
  The API readback limitation did not affect the ingest acceptance criteria but was explicitly
  flagged as an open gap.

---

## Fix: PR #42

| Field | Value |
|---|---|
| Branch | `fix/api-events-pagination` |
| PR | #42 |
| Merge target | `main` |
| Deploy branch | `deploy/api-events-pagination` |

### Changes applied

- SQL query for `/events` now uses `ORDER BY ingested_at DESC, event_id DESC` for stable
  deterministic ordering across pages.
- SQL query now uses `LIMIT %s OFFSET %s`, passing both parameters from the request.
- FastAPI route now accepts and validates the `offset` query parameter.
- Negative offsets are rejected via FastAPI query-parameter validation (HTTP 422).
- Tests added: `tests/test_api_events_pagination.py`

### Post-merge validation

- 116 tests passed (up from 108 before the fix — 8 new pagination tests added)
- Ruff: all checks passed
- Cloud SQL was not started for the code-level validation

---

## Deployment Details

| Field | Value |
|---|---|
| Cloud Run service | `rtdp-api` |
| Region | `europe-west1` |
| Project | `project-42987e01-2123-446b-ac7` |
| Deployed revision | `rtdp-api-00006-gd8` |
| Service URL | `https://rtdp-api-892892382088.europe-west1.run.app` |
| `/version` — version field | `0.1.0-pagination-fix` |
| `/version` — environment field | `gcp-cloud-run` |
| Image digest | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/cloud-run-source-deploy/rtdp-api@sha256:0b44c36a71b305653dfe85a74d98075ae238bf19458917412d95a3a29515af78` |

---

## Apple Silicon / linux/amd64 Deployment Correction

The first deploy attempt failed because the Docker image built on Apple Silicon (ARM) produced an
OCI image index rather than a single-platform manifest:

```
Cloud Run error:
Container manifest type 'application/vnd.oci.image.index.v1+json' must support amd64/linux.
```

**Resolution:** A `linux/amd64` image was built explicitly and pushed to Artifact Registry, then
deployed to Cloud Run by digest (the SHA256 digest shown above). This is the correct procedure
for any Cloud Run deployment from an Apple Silicon machine.

---

## Production Validation Outputs

Cloud SQL was started temporarily for validation and stopped immediately after.

### Health

```
GET /health
→ {"status":"ok","service":"rtdp-api"}
```

### Version

```
GET /version
→ {"service":"rtdp-api","version":"0.1.0-pagination-fix","environment":"gcp-cloud-run"}
```

The `version` field confirms that revision `rtdp-api-00006-gd8` is serving the pagination fix.

### Readiness

```
GET /readiness
→ {"status":"ready","service":"rtdp-api","database":"reachable"}
```

Cloud SQL was reachable at the time of validation.

---

## Pagination Proof

Data used: the 1000 events ingested during the accepted 1000-event cloud load test
(`loadtest-1000-20260505223709-` prefix).

### Page 1 — `GET /events?limit=5&offset=0`

```json
[
  "loadtest-1000-20260505223709-01000",
  "loadtest-1000-20260505223709-00999",
  "loadtest-1000-20260505223709-00998",
  "loadtest-1000-20260505223709-00997",
  "loadtest-1000-20260505223709-00996"
]
```

### Page 2 — `GET /events?limit=5&offset=5`

```json
[
  "loadtest-1000-20260505223709-00995",
  "loadtest-1000-20260505223709-00994",
  "loadtest-1000-20260505223709-00993",
  "loadtest-1000-20260505223709-00992",
  "loadtest-1000-20260505223709-00991"
]
```

### Disjoint verification

```
disjoint: True
```

The two pages return completely different rows. Event IDs on page 2 continue the descending
sequence from page 1 (`-00996` → `-00995`), confirming correct `ORDER BY` and `OFFSET` behaviour.
This directly closes the gap observed in the 1000-event load test evidence.

---

## Cloud SQL Final State

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

```
NEVER   STOPPED
```

Cloud SQL was started only for the validation window and confirmed `NEVER / STOPPED` immediately
after pagination evidence was collected. Cost-control discipline maintained.

---

## Claims Now Allowed

- The `/events` endpoint now correctly implements `OFFSET`-based pagination.
- The pagination bug (`offset` parameter silently ignored) observed during the 1000-event load
  test is closed by direct production validation.
- Stable descending order (`ORDER BY ingested_at DESC, event_id DESC`) is enforced across pages,
  preventing row duplication or gaps at page boundaries.
- Negative `offset` values are rejected before reaching the database (HTTP 422).
- Production revision `rtdp-api-00006-gd8` at `0.1.0-pagination-fix` serves the fix.
- The disjoint two-page readback used live production data from the accepted 1000-event test run
  as the validation corpus.
- Cost-control discipline maintained: Cloud SQL `NEVER / STOPPED` after validation.

---

## Gaps Still Not Closed

- DLQ / retry safety under malformed-message or processing-failure conditions
- IaC (Terraform / gcloud configuration) gap — all infrastructure managed manually
- Analytics gap — BigQuery and Dataflow integration not yet executed
- Alerting and dashboard gap — logs-based metrics validated but no live alert policies active
- 5 000-event load test not yet executed
- Multi-region resilience and autoscaling limits not validated
- Worker deployment from Apple Silicon requires explicit `linux/amd64` build — no CI guard exists
  to prevent accidental ARM image push

---

## Confirmation of Exclusions

- No application code modified during this documentation step
- No test files modified during this documentation step
- No GCP resources created, modified, or destroyed during this documentation step
- No Pub/Sub messages published
- Cloud SQL not started during this documentation step
- No deployments performed during this documentation step
