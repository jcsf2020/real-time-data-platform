# Cloud Observability Evidence

## Status

Documented on: 2026-05-05

Read-only Cloud Logging evidence. No GCP commands were executed that modify, deploy, or start
any resource. Cloud SQL was not started during this session.

---

## Objective

Verify that deployed GCP services and jobs can be inspected through Cloud Logging without
requiring a live database or any additional deployment step. Specifically: can Cloud Run Job
execution, Cloud Run Service request handling, and container lifecycle events all be queried
from Cloud Logging after the fact?

---

## Validated Observability Path

```text
application stdout/stderr
  -> Cloud Run
    -> Cloud Logging
      -> jsonPayload / textPayload / httpRequest / audit logs
```

---

## Cloud Run Job Evidence

**Log query:**

```bash
gcloud logging read \
  'resource.type="cloud_run_job" resource.labels.job_name="rtdp-silver-refresh-job"' \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=20 \
  --format=json
```

### Job resource

| Field | Value |
|---|---|
| `resource.type` | `cloud_run_job` |
| `resource.labels.job_name` | `rtdp-silver-refresh-job` |
| `resource.labels.location` | `europe-west1` |
| `execution_name` | `rtdp-silver-refresh-job-x54pc` |

### Audit / system evidence

| Field | Value |
|---|---|
| `methodName` | `/Jobs.RunJob` |
| Status message | `Execution rtdp-silver-refresh-job-x54pc has completed successfully.` |
| `succeededCount` | `1` |
| `startTime` | `2026-05-05T06:09:38.301457Z` |
| `completionTime` | `2026-05-05T06:10:05.258025Z` |

Elapsed time: approximately 27 seconds from start to completion, including Cloud SQL Auth Proxy
startup and the aggregate function call.

### Structured application log (stdout → jsonPayload)

```json
{
  "component": "silver-refresh",
  "operation": "refresh_market_event_minute_aggregates",
  "processing_time_ms": 419.349,
  "service": "rtdp-silver-refresh-job",
  "status": "ok",
  "timestamp_utc": "2026-05-05T06:10:02.224955+00:00"
}
```

`logName: run.googleapis.com/stdout` — Cloud Run parsed the JSON-serialised stdout line into
`jsonPayload` automatically. No log agent or sidecar configuration was required.

### Container lifecycle evidence

```
textPayload = Container called exit(0).
```

The runner exited cleanly with code 0. Cloud Run recorded this as a textPayload lifecycle event
distinct from the application's own structured log.

---

## Cloud Run Worker Evidence

**Log query:**

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" resource.labels.service_name="rtdp-pubsub-worker"' \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=20 \
  --format=json
```

### Worker resource

| Field | Value |
|---|---|
| `resource.type` | `cloud_run_revision` |
| `resource.labels.service_name` | `rtdp-pubsub-worker` |
| `resource.labels.revision_name` | `rtdp-pubsub-worker-00002-xp7` |
| `resource.labels.location` | `europe-west1` |

### Request evidence (httpRequest log)

| Field | Value |
|---|---|
| `requestMethod` | `POST` |
| `requestUrl` | `https://rtdp-pubsub-worker-892892382088.europe-west1.run.app/pubsub/push` |
| `status` | `200` |
| `latency` | `3.207767544s` |
| `userAgent` | `APIs-Google` |
| `timestamp` | `2026-05-04T20:38:36.027870Z` |

A Pub/Sub push delivery from `APIs-Google` was received, processed, and returned HTTP 200.
The 3.2 s latency includes the Cloud SQL Auth Proxy connection overhead on a cold instance.

### Worker stdout evidence

```
textPayload = INFO: 169.254.169.126:53312 - "POST /pubsub/push HTTP/1.1" 200 OK
```

Uvicorn's access log confirms the request reached the application process and returned 200.

### Container lifecycle evidence

```
Default STARTUP TCP probe succeeded after 1 attempt for container "rtdp-pubsub-worker-1" on port 8080.
Application startup complete.
Application shutdown complete.
Finished server process [1].
```

Startup probe, graceful startup, and clean shutdown are all captured in Cloud Logging.

### Deployment / config evidence in logs

Cloud SQL Auth Proxy attachment:

```
run.googleapis.com/cloudsql-instances = project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres
```

Secret Manager injection:

```
secretKeyRef:
  name: rtdp-database-url
  key: latest
```

Service account:

```
serviceAccountName = rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

These fields appear in the Cloud Run resource config captured by Cloud Logging, confirming that
Secret Manager and Cloud SQL connector configuration reached the deployed revision correctly.

---

## Worker Structured Logs Status

**Query used:**

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" resource.labels.service_name="rtdp-pubsub-worker" jsonPayload.service="rtdp-pubsub-worker"' \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=10 \
  --format=json
```

**Output:**

```
[]
```

**Interpretation — known gap, not a validated feature:**

The deployed worker revision (`rtdp-pubsub-worker-00002-xp7`) does not emit structured
`jsonPayload` application logs. The likely explanation is that the deployed revision predates
the structured logging code that was subsequently added to the worker, and no Pub/Sub message
has been processed by a revision that includes that code. The Uvicorn access log (`textPayload`)
and HTTP request log confirm the push endpoint is reachable and returns 200, but the per-event
structured application payload cannot yet be verified from Cloud Logging.

This gap is resolved by redeploying the worker image from the current `main` branch — see
[Next Recommended Branch](#next-recommended-branch) below.

---

## What This Proves

- The Cloud Run Job (`rtdp-silver-refresh-job`) emits structured JSON to stdout, which Cloud Run
  parses as `jsonPayload` and routes to Cloud Logging without additional configuration.
- Cloud Logging captures a full job audit trail: `methodName`, `startTime`, `completionTime`,
  `succeededCount`, and the completion status message.
- The structured application log (`status: ok`, `processing_time_ms: 419.349`) is observable
  after the fact through a single `gcloud logging read` command.
- Cloud Logging captures Cloud Run Service request logs including method, URL, HTTP status, latency,
  and user agent for the Pub/Sub push worker.
- The worker received a Pub/Sub push `POST /pubsub/push` and returned HTTP 200 — confirmed in both
  the `httpRequest` log and the Uvicorn `textPayload` access log.
- Cloud Run container lifecycle (startup probe, application startup, shutdown) is visible in logs.
- Deployment config evidence (Cloud SQL connector, Secret Manager reference, service account) is
  captured in Cloud Logging resource metadata.
- Cloud Logging can be queried from a local terminal without starting Cloud SQL.

---

## What This Does Not Prove Yet

- **Worker structured application logs** — the deployed revision predates the structured logging
  code; `jsonPayload` query returned `[]`.
- **Logs-based metrics** — no metric extraction from log entries is configured.
- **Alerting policies** — no Cloud Monitoring alert fires on job failure or missing heartbeat.
- **Grafana dashboard** — no external dashboard is wired to Cloud Logging or Cloud Monitoring.
- **Cloud Monitoring dashboard** — no dashboard has been created in the GCP console.
- **Distributed traces** — no trace context is propagated or captured.
- **SLOs** — no service level objective is defined for job latency or error rate.

---

## Next Recommended Branch

**Branch name:** `feat/redeploy-worker-structured-logs`

**Objective:** Rebuild and redeploy the `rtdp-pubsub-worker` image from the current `main`
branch — which includes structured JSON logging — then publish one Pub/Sub test event and
confirm that `jsonPayload.service="rtdp-pubsub-worker"` appears in Cloud Logging. This closes
the known gap documented above.

**Later branch:** `docs/cloud-observability-metrics-plan` — design logs-based metrics,
alerting policies, and a Cloud Monitoring dashboard for job failure and pipeline latency.

---

## Engineer Mindset Notes

Cloud Logging receives everything a Cloud Run container writes to stdout or stderr. The
format determines how it is indexed:

| Output format | Cloud Logging field | Queryable as |
|---|---|---|
| JSON object on a single line | `jsonPayload` | `jsonPayload.status`, `jsonPayload.service`, etc. |
| Plain text line | `textPayload` | full-text string |
| HTTP request handled by Cloud Run | `httpRequest` | `httpRequest.status`, `httpRequest.latency`, etc. |
| GCP control-plane action (deploy, execute) | audit log | `methodName`, `resourceName`, etc. |

The correct production sequence is: deploy and validate observability before adding automation.
A Cloud Scheduler trigger without confirmed log visibility means failures could go undetected.
The evidence above establishes that the job and worker are both observable; the remaining gap
(worker structured logs) is one redeploy away.
