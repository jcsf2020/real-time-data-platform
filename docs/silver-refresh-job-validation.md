# Silver Refresh Job Validation

## Status

Validated on: 2026-05-05

Cloud Run Job silver refresh path is validated. The job built, deployed, executed, and
produced confirmed silver aggregate rows readable through the Cloud Run API.

---

## Validation Objective

Prove that `silver.refresh_market_event_minute_aggregates()` can be triggered from a
Cloud Run Job, that it reads from `bronze.market_events` in Cloud SQL, upserts into
`silver.market_event_minute_aggregates`, and that the result is readable through the
Cloud Run API at `/aggregates/minute`.

---

## Validated Path

```text
Cloud SQL bronze.market_events
  -> Cloud Run Job rtdp-silver-refresh-job
    -> SELECT silver.refresh_market_event_minute_aggregates();
      -> silver.market_event_minute_aggregates
        -> Cloud Run API /aggregates/minute
```

---

## Resources Validated

| Resource | Identifier |
|---|---|
| GCP project | `project-42987e01-2123-446b-ac7` |
| GCP project number | `892892382088` |
| Region | `europe-west1` |
| Artifact Registry repo | `rtdp` |
| Cloud SQL instance | `rtdp-postgres` |
| Cloud SQL database | `realtime_platform` |
| Secret Manager secret | `rtdp-database-url` |
| Cloud Run Job | `rtdp-silver-refresh-job` |
| Cloud Run API | `rtdp-api` |
| Cloud Run API URL | `https://rtdp-api-892892382088.europe-west1.run.app` |
| Service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| Job image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest` |

---

## Image Build and Artifact Registry Evidence

**Build command (linux/amd64, built and pushed in one step):**

```bash
docker buildx build \
  --platform linux/amd64 \
  -f apps/silver-refresh-job/Dockerfile \
  -t europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest \
  --push \
  .
```

**Relevant build output:**

```
pushing manifest for europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest@sha256:4d1b342829f87c6a8dc48223493c2f6de5a7c9b4d9d440c5afc5cdd0c40b8784
```

**Artifact Registry — confirmed image and digest:**

| Field | Value |
|---|---|
| Image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job` |
| Tag | `latest` |
| Digest | `sha256:4d1b342829f87c6a8dc48223493c2f6de5a7c9b4d9d440c5afc5cdd0c40b8784` |

---

## Deployment Evidence

### Corrected Execution Note

The deployment plan used `--add-cloudsql-instances`, which is the Cloud Run **Service** flag.
Cloud Run **Jobs** require `--set-cloudsql-instances` in the current `gcloud` version. The first
deploy attempt failed with:

```
ERROR: (gcloud.run.jobs.deploy) unrecognized arguments:
  --add-cloudsql-instances=project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres
  (did you mean '--set-cloudsql-instances'?)
```

This is a gcloud CLI flag naming difference between job and service subcommands, not a project or
infrastructure failure. The deployment plan at [docs/silver-refresh-job-deployment-plan.md](silver-refresh-job-deployment-plan.md)
has been updated to use `--set-cloudsql-instances`.

### Corrected Deploy Command and Output

```bash
gcloud run jobs deploy rtdp-silver-refresh-job \
  --image=europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --service-account=rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --set-secrets=DATABASE_URL=rtdp-database-url:latest \
  --set-cloudsql-instances=project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres \
  --tasks=1 \
  --max-retries=0 \
  --task-timeout=300s
```

**Output:**

```
Job [rtdp-silver-refresh-job] has successfully been deployed.
```

---

## Job Definition Evidence

Confirmed job definition (YAML):

```yaml
apiVersion: run.googleapis.com/v1
kind: Job
metadata:
  name: rtdp-silver-refresh-job
spec:
  template:
    metadata:
      annotations:
        run.googleapis.com/cloudsql-instances: project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres
        run.googleapis.com/execution-environment: gen2
    spec:
      taskCount: 1
      template:
        spec:
          containers:
          - env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  key: latest
                  name: rtdp-database-url
            image: europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest
            resources:
              limits:
                cpu: 1000m
                memory: 512Mi
          maxRetries: 0
          serviceAccountName: rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
          timeoutSeconds: '300'
status:
  conditions:
  - status: 'True'
    type: Ready
```

---

## Execution Evidence

Cloud SQL was started immediately before execution and stopped immediately after validation.

**Cloud SQL start:**

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS && \
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"
```

Output:

```
ALWAYS  RUNNABLE
```

**Manual job execution:**

```bash
gcloud run jobs execute rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --wait
```

Output:

```
Execution [rtdp-silver-refresh-job-x54pc] has successfully completed.
1 / 1 complete
```

---

## API Validation Evidence

**Command:**

```bash
curl -s "https://rtdp-api-892892382088.europe-west1.run.app/aggregates/minute?limit=5" && echo
```

**Response:**

```json
[
  {
    "symbol": "ETHUSDT",
    "window_start": "2026-05-04T09:05:00Z",
    "event_count": 1,
    "avg_price": 3200.0,
    "total_quantity": 0.1,
    "first_event_timestamp": "2026-05-04T09:05:00Z",
    "last_event_timestamp": "2026-05-04T09:05:00Z",
    "updated_at": "2026-05-05T06:10:02.023382Z"
  },
  {
    "symbol": "BTCUSDT",
    "window_start": "2026-05-04T06:30:00Z",
    "event_count": 1,
    "avg_price": 67500.0,
    "total_quantity": 0.01,
    "first_event_timestamp": "2026-05-04T06:30:00Z",
    "last_event_timestamp": "2026-05-04T06:30:00Z",
    "updated_at": "2026-05-05T06:10:02.023382Z"
  }
]
```

Two silver aggregate rows confirmed: `ETHUSDT` and `BTCUSDT`, both populated by the Cloud Run
Job execution.

---

## Cost-Control Final State

Cloud SQL was stopped immediately after API validation was confirmed.

**Cloud SQL stop command and verified final state:**

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER && \
gcloud sql instances describe rtdp-postgres \
  --format="value(settings.activationPolicy,state)"
```

Output:

```
NEVER   STOPPED
```

Cloud SQL is confirmed stopped. No idle cost accrues.

---

## Local Validation

```
uv sync --all-packages   →  resolved, no errors
uv run pytest -q         →  75 passed
uv run ruff check .      →  All checks passed!
Cloud SQL final state    →  NEVER   STOPPED
```

---

## What This Proves

- The `rtdp-silver-refresh-job` Docker image builds correctly for `linux/amd64` from the monorepo workspace root.
- The image is available in Artifact Registry under the correct digest.
- Cloud Run Jobs can be deployed with `--set-cloudsql-instances`, `--set-secrets`, and a dedicated service account.
- The Cloud SQL Auth Proxy sidecar connects successfully at job execution time.
- `DATABASE_URL` is injected at runtime from Secret Manager without being written to logs.
- `silver.refresh_market_event_minute_aggregates()` executes successfully against `bronze.market_events` in Cloud SQL.
- The silver layer is populated and readable through the Cloud Run API at `/aggregates/minute`.
- The job exits cleanly (exit 0) and Cloud Run reports execution complete.
- Cloud SQL can be started and stopped on demand for cost control.

---

## What This Does Not Prove Yet

- **No Cloud Scheduler recurring automation** — the job was executed once, manually. Recurring execution is not configured.
- **No BigQuery or Dataflow** — silver aggregates exist in Cloud SQL only; no analytical export is in place.
- **No high-throughput benchmark** — validated with one event per symbol; behaviour under volume is untested.
- **No Cloud Monitoring alert** — no alerting policy or dashboard is configured for job failures.
- **No load test** — the aggregate function and Cloud SQL connection pool have not been benchmarked.

---

## Honest Architecture Claim

> **Cloud silver refresh path validated through Cloud Run Job.**

Do not claim "scheduled automated refresh" until Cloud Scheduler is explicitly configured,
tested, and validated in a separate session.
