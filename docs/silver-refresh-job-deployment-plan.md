# Silver Refresh Job Deployment Plan

> **STATUS: PLAN ONLY — NOT EXECUTED**
>
> No GCP commands in this document have been run. All command blocks are reference material
> for the execution session only. Cloud SQL is currently stopped and must remain stopped
> until Phase 3.

---

## Current Implemented State

| Component | State |
|---|---|
| Runner package (`rtdp-silver-refresh-job`) | Implemented and tested |
| CLI entry point (`rtdp-silver-refresh-job`) | Implemented |
| Structured JSON logs (exit 0/1) | Implemented |
| Dockerfile (`apps/silver-refresh-job/Dockerfile`) | Exists — image not yet built for linux/amd64 |
| Tests | 75 passed |
| linux/amd64 image | **Not pushed to Artifact Registry** |
| Cloud Run Job (`rtdp-silver-refresh-job`) | **Not deployed** |
| Cloud Scheduler trigger | **Not configured** |

---

## Target Path

```text
Cloud SQL bronze.market_events
  -> Cloud Run Job rtdp-silver-refresh-job
    -> SELECT silver.refresh_market_event_minute_aggregates();
      -> silver.market_event_minute_aggregates
        -> Cloud Run API /aggregates/minute
```

---

## Resource Inventory

### Existing resources

| Resource | Identifier |
|---|---|
| GCP project | `project-42987e01-2123-446b-ac7` |
| GCP project number | `892892382088` |
| Region | `europe-west1` |
| Artifact Registry repo | `rtdp` |
| Cloud SQL instance | `rtdp-postgres` |
| Cloud SQL database | `realtime_platform` |
| Secret Manager secret | `rtdp-database-url` (use `latest` version only) |
| Cloud Run API service | `rtdp-api` |
| Cloud Run API URL | `https://rtdp-api-892892382088.europe-west1.run.app` |
| Worker service account | `rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |

### Resources to be created at execution time

| Resource | Identifier |
|---|---|
| Silver refresh job image | `europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest` |
| Cloud Run Job | `rtdp-silver-refresh-job` (region: `europe-west1`) |

---

## IAM Requirements

The Cloud Run Job can reuse the existing `rtdp-worker-sa` service account. It already requires
the same two permissions as the Pub/Sub worker:

- `roles/cloudsql.client` — connects to Cloud SQL via the Cloud SQL Auth Proxy sidecar
- `roles/secretmanager.secretAccessor` on secret `rtdp-database-url` — reads the DB URL at startup

No additional service accounts are needed. Verify the grants are still in place at the start of
the execution session (Phase 0). Do not create extra service accounts unless `gcloud iam
service-accounts describe` confirms the existing account is missing.

---

## Phase 0 — Safety Pre-checks

> Run these checks at the start of the execution session before anything else.
> Abort if any check fails.

**Check 1 — Working tree is clean:**

```bash
git status --short --branch
# Expected: no uncommitted changes on a clean branch
```

**Check 2 — Cloud SQL is stopped:**

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required output: NEVER  STOPPED
# Abort if output is anything else. Do NOT start Cloud SQL in this phase.
```

**Check 3 — Artifact Registry image state:**

```bash
gcloud artifacts docker images list \
  europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp \
  --project=project-42987e01-2123-446b-ac7
# Confirms whether an older rtdp-silver-refresh-job image already exists.
# The push in Phase 1 will overwrite :latest regardless.
```

**Check 4 — Existing Cloud Run Jobs:**

```bash
gcloud run jobs list \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
# Confirms whether rtdp-silver-refresh-job already exists.
# If it exists, Phase 2 deploy will update it (safe to proceed).
```

**Check 5 — Secret IAM policy contains rtdp-worker-sa:**

```bash
gcloud secrets get-iam-policy rtdp-database-url \
  --project=project-42987e01-2123-446b-ac7
# Must show rtdp-worker-sa with roles/secretmanager.secretAccessor.
# If missing, grant it before proceeding to Phase 2:
#   gcloud secrets add-iam-policy-binding rtdp-database-url \
#     --project=project-42987e01-2123-446b-ac7 \
#     --member="serviceAccount:rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com" \
#     --role="roles/secretmanager.secretAccessor"
```

**Check 6 — Cloud SQL client role on rtdp-worker-sa:**

```bash
gcloud projects get-iam-policy project-42987e01-2123-446b-ac7 \
  --flatten="bindings[].members" \
  --format="table(bindings.role,bindings.members)" \
  --filter="bindings.members:rtdp-worker-sa"
# Must include roles/cloudsql.client.
```

---

## Phase 1 — Build and Push linux/amd64 Image

> Run from the repository root. Cloud SQL does not need to be started for this phase.

Cloud Run runs on `linux/amd64`. Building on an Apple Silicon Mac without the `--platform` flag
produces an `arm64` image that Cloud Run will refuse at deploy or execution time. The `--push`
flag in the `buildx` command builds and pushes in a single step, avoiding a separate `docker push`.

Authenticate Docker with Artifact Registry first (one-time per machine):

```bash
gcloud auth configure-docker europe-west1-docker.pkg.dev
```

Build and push the linux/amd64 image:

```bash
docker buildx build \
  --platform linux/amd64 \
  -f apps/silver-refresh-job/Dockerfile \
  -t europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest \
  --push \
  .
```

The Docker context must be the repository root (`.`) because the Dockerfile copies the full
workspace (`apps/`, `packages/`) so `uv` can resolve the monorepo dependency graph.

Verify the image is available in Artifact Registry:

```bash
gcloud artifacts docker images list \
  europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp \
  --project=project-42987e01-2123-446b-ac7 \
  --filter="package=rtdp-silver-refresh-job"
# Expected: one entry for rtdp-silver-refresh-job:latest with a recent timestamp.
```

---

## Phase 2 — Deploy Cloud Run Job

> Run after Phase 1 confirms the image is in Artifact Registry.
> Cloud SQL must remain stopped — Cloud Run Job deployment does not require a live database.

Cloud Run Jobs differ from Cloud Run Services: they have no HTTP endpoint, they run to completion
and exit, and they are invoked explicitly (or via Cloud Scheduler). `--tasks=1` means a single
task instance runs per execution. `--max-retries=0` prevents automatic retry on failure so a
first-run error is visible in logs immediately without multiple executions against the database.

```bash
gcloud run jobs deploy rtdp-silver-refresh-job \
  --image=europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --service-account=rtdp-worker-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --set-secrets=DATABASE_URL=rtdp-database-url:latest \
  --add-cloudsql-instances=project-42987e01-2123-446b-ac7:europe-west1:rtdp-postgres \
  --tasks=1 \
  --max-retries=0 \
  --task-timeout=300s
```

`--set-secrets=DATABASE_URL=rtdp-database-url:latest` — injects the secret as an environment
variable. The runner reads `DATABASE_URL` at startup; it is never written to logs.

`--add-cloudsql-instances` — attaches the Cloud SQL Auth Proxy sidecar so the runner can connect
via Unix socket without exposing the database to the public internet.

`--max-retries=0` — one attempt only; retry policy can be adjusted after the initial validation
confirms the job is working correctly.

`--task-timeout=300s` — the aggregate function call is expected to complete in well under a
minute; 300 seconds provides a generous ceiling without letting a hung execution run indefinitely.

Confirm the job was created:

```bash
gcloud run jobs describe rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
# Expected: job definition including image, service account, and Cloud SQL attachment.
```

---

## Phase 3 — Controlled Validation Execution

> This is the only phase that requires Cloud SQL to be started.
> Start it immediately before executing the job and stop it in Phase 4 before ending the session.

**Step 3a — Start Cloud SQL:**

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=ALWAYS \
  --project=project-42987e01-2123-446b-ac7
```

**Step 3b — Wait for RUNNABLE (60–90 seconds):**

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Wait until output is: ALWAYS  RUNNABLE
# Do not proceed to Step 3c until the state is RUNNABLE.
```

**Step 3c — Execute the Cloud Run Job manually:**

```bash
gcloud run jobs execute rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --wait
# --wait blocks until the execution completes and reports success or failure.
# Expected exit: job succeeds (exit code 0 from the runner).
```

**Step 3d — Validate silver aggregates through the API:**

```bash
curl -s "https://rtdp-api-892892382088.europe-west1.run.app/aggregates/minute?limit=5"
# Expected: JSON array of silver aggregate rows (symbol, window_start, event_count, avg_price, total_quantity, first_event_timestamp, last_event_timestamp, updated_at).
# Do not claim success if the array is empty or the request errors.
```

**Step 3e — Inspect Cloud Run Job logs if the execution failed:**

```bash
gcloud run jobs executions list \
  --job=rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
# Note the most recent execution name, then:

gcloud logging read \
  'resource.type="cloud_run_job" resource.labels.job_name="rtdp-silver-refresh-job"' \
  --project=project-42987e01-2123-446b-ac7 \
  --limit=50 \
  --format="value(jsonPayload)"
# The runner emits one structured JSON log line. status="ok" means success; status="error" means failure.
```

---

## Phase 4 — Stop Cloud SQL

> Run immediately after Phase 3, whether validation succeeded or failed.
> Cloud SQL accrues cost for every minute it remains in RUNNABLE state.

```bash
gcloud sql instances patch rtdp-postgres \
  --activation-policy=NEVER \
  --project=project-42987e01-2123-446b-ac7
```

Verify final state before ending the session:

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required output: NEVER  STOPPED
# Do not end the session until this output is confirmed.
```

---

## Rollback Plan

If the deployment must be reversed after execution:

**Delete the Cloud Run Job:**

```bash
gcloud run jobs delete rtdp-silver-refresh-job \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

**Optionally delete the Artifact Registry image:**

```bash
gcloud artifacts docker images delete \
  europe-west1-docker.pkg.dev/project-42987e01-2123-446b-ac7/rtdp/rtdp-silver-refresh-job:latest \
  --project=project-42987e01-2123-446b-ac7
# Image storage is negligible; deletion is optional.
```

**Source code is unchanged — no action required.**

**Confirm Cloud SQL is stopped after rollback:**

```bash
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
# Required: NEVER  STOPPED
```

The service account `rtdp-worker-sa` is shared with the Pub/Sub worker. Do not delete it as part
of rolling back the silver refresh job alone.

---

## Cost-Control Rules

- **Cloud SQL is the main cost risk.** It must remain in `NEVER / STOPPED` state at all times
  except during the Phase 3 validation window. Verify state at the start and end of every session.
- **Cloud Run Job has no idle HTTP service cost.** Unlike a Cloud Run Service, a Job incurs cost
  only when an execution is running. Between executions there is no standing charge.
- **Artifact Registry image storage is negligible.** A single Python slim image is tens of
  megabytes; the monthly storage cost is cents.
- **Manual execution only.** Do not configure Cloud Scheduler until it is explicitly approved as a
  next step. Automated recurring executions against a stopped Cloud SQL instance will fail and
  accumulate failed-execution records.

---

## Acceptance Criteria

- [ ] linux/amd64 image pushed and visible in `gcloud artifacts docker images list`
- [ ] Cloud Run Job deployed and visible in `gcloud run jobs describe rtdp-silver-refresh-job`
- [ ] Manual job execution succeeds (`gcloud run jobs execute --wait` exits without error)
- [ ] API `/aggregates/minute` returns at least one row after execution
- [ ] Cloud SQL final state is `NEVER  STOPPED` after the session
- [ ] Evidence of execution (log output, API response) documented in a separate validation file

---

## Out of Scope

The following are explicitly excluded from this deployment plan:

- Cloud Scheduler for automated recurring execution
- Automated recurring silver refresh
- BigQuery export or Dataflow pipeline
- Terraform or any infrastructure-as-code tooling
- New SQL schema or function changes
- Source code changes
- Load testing
- Dead-letter queue for failed executions
- Cloud Monitoring dashboards or alerting policies

---

## Honest Claim After Execution

**Can be claimed only after execution succeeds:**

> Cloud silver refresh path validated through Cloud Run Job.

**Cannot yet be claimed:**

> "Scheduled automated refresh" — this claim requires Cloud Scheduler to be explicitly
> configured and validated in a future session.
