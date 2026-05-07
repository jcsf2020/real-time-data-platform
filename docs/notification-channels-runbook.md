# Cloud Monitoring Notification Channels Runbook

## Status

**RUNBOOK ONLY — NOT EXECUTED**

This is an operational runbook. No GCP write operations have been performed on this branch.

| Constraint | State |
|---|---|
| Notification channels created | **No** |
| Alert policies updated | **No** |
| IAM changes made | **No** |
| Cloud SQL started | **No** |
| Scheduler run | **No** |
| Cloud Run Job executed | **No** |
| Pub/Sub messages published | **No** |
| Application code modified | **No** |
| Anything deployed | **No** |

This runbook exists solely to define the precise, reviewable execution sequence for a future
branch or session. Read every command block as documentation, not as executed evidence.

---

## 1. Purpose

This runbook defines the controlled procedure to create an email notification channel and
attach it to both existing Cloud Monitoring alert policies, making them operator-actionable.

The project currently has two enabled alert policies:

- **RTDP Worker Message Error Alert** — fires when `worker_message_error_count > 0`
- **RTDP Silver Refresh Error Alert** — fires when `silver_refresh_error_count > 0`

Both policies are visible in the Cloud Monitoring console and will transition an incident when
their conditions are met. However, with `notificationChannels: []`, no notification is
delivered outside the console. An operator must be actively watching the dashboard to detect
an alert. This runbook closes that gap.

**Goal:** move from alert policies visible only in the console to operator-delivered
notifications via email, while preserving all existing alert policy definitions unchanged
except for the addition of the notification channel reference.

**Scope:**

- Primary: email notification channel (simplest, no secret management required)
- Future optional: Slack or webhook channel (out of scope for this runbook)
- No overengineering: one channel, two policy updates

This runbook builds on the complete observability stack:

- Logs-based metrics — validated:
  [docs/cloud-logs-based-metrics-datapoint-validation.md](cloud-logs-based-metrics-datapoint-validation.md)
- Cloud Monitoring dashboard — exists:
  [docs/cloud-monitoring-dashboard-evidence.md](cloud-monitoring-dashboard-evidence.md)
- Alert policies — created and enabled:
  [docs/cloud-alert-policies-evidence.md](cloud-alert-policies-evidence.md)
- Production Pub/Sub DLQ — configured:
  [docs/production-pubsub-dlq-evidence.md](production-pubsub-dlq-evidence.md)
- Cloud Scheduler — configured and execution-proven:
  [docs/silver-refresh-scheduler-execution-proof-evidence.md](silver-refresh-scheduler-execution-proof-evidence.md)

---

## 2. Current State

| Resource | Field | Value |
|---|---|---|
| RTDP Worker Message Error Alert | metric | `logging.googleapis.com/user/worker_message_error_count` |
| RTDP Worker Message Error Alert | enabled | `true` |
| RTDP Worker Message Error Alert | notificationChannels | `[]` |
| RTDP Silver Refresh Error Alert | metric | `logging.googleapis.com/user/silver_refresh_error_count` |
| RTDP Silver Refresh Error Alert | enabled | `true` |
| RTDP Silver Refresh Error Alert | notificationChannels | `[]` |
| Cloud Monitoring dashboard | RTDP Pipeline Overview | exists |
| Logs-based metrics | all four | validated (timeSeries datapoints confirmed) |
| Production Pub/Sub DLQ | deadLetterPolicy | configured |
| Cloud Scheduler | rtdp-silver-refresh-scheduler | PAUSED — execution proof validated |
| Notification channel | any | **absent / not configured** |

**Known limitation:** the alert policies exist but have no notification delivery target.
Alert conditions that fire produce incidents visible in the Cloud Monitoring console only —
no signal reaches an operator outside the console.

---

## 3. Proposed Notification Strategy

### Primary: email notification channel

| Field | Value |
|---|---|
| Channel type | `email` |
| Display name | `RTDP Operator Email Alerts` |
| Email address | `<OPERATOR_EMAIL>` (placeholder — resolve before execution) |

**Rationale:**

- Email is the simplest channel type: no webhook URL, no Slack workspace configuration, no
  secret management required.
- Sufficient for portfolio-grade alert delivery: demonstrates end-to-end alerting without
  overengineering.
- Can be upgraded to Slack or webhook in a future step without removing the email channel.
- GCP may require email verification depending on channel type and account behaviour. If
  verification is required, execution must pause and document the verification step before
  attaching the channel to any policy.

### Future optional: Slack / webhook channel

Out of scope for this runbook. Slack and webhook channels require a webhook URL or Slack
OAuth token. The additional secret management complexity is not justified until the email
channel is in place and confirmed working. Document and create in a separate future runbook
if needed.

---

## 4. Alert Policy IDs (from evidence)

These IDs were captured during the alert policy creation branch
(`exec/cloud-alert-policies-validation`). Verify these IDs against the live GCP state during
pre-flight before updating.

| Policy | Name resource path |
|---|---|
| RTDP Worker Message Error Alert | `projects/project-42987e01-2123-446b-ac7/alertPolicies/5769368960767699129` |
| RTDP Silver Refresh Error Alert | `projects/project-42987e01-2123-446b-ac7/alertPolicies/10553646324755759042` |

---

## 5. Safety Constraints

**Absolute constraints — do not override under any circumstances on this or any docs branch:**

- Do not create notification channels on this docs branch.
- Do not update alert policies on this docs branch.
- Do not disable existing alert policies.
- Do not change alert conditions, thresholds, metric filters, or enabled state.
- Do not trigger synthetic errors to test alert firing.
- Do not start Cloud SQL.
- Do not run the Scheduler.
- Do not publish Pub/Sub messages to any topic.
- Do not execute any Cloud Run Job.
- Do not deploy any code or container.
- Do not make IAM changes.
- Capture the current alert policy state before any update command.
- Capture the current notification channel list before any create command.
- Document the rollback command before executing any update.

---

## 6. Exact Future Execution Commands

> **Future execution only — do not run on this runbook branch.**
>
> All command blocks below are templates for a future execution session. No command here has
> been run. All placeholders must be resolved before execution. Stop if any step returns an
> unexpected result.

### Placeholder reference

| Placeholder | Meaning |
|---|---|
| `PROJECT_ID` | GCP project ID — `project-42987e01-2123-446b-ac7` |
| `REGION` | Cloud Run region — `europe-west1` |
| `<OPERATOR_EMAIL>` | The email address that will receive alert notifications — resolve before execution |
| `<CHANNEL_ID>` | The notification channel resource name returned after channel creation |
| `<WORKER_POLICY_ID>` | `5769368960767699129` (verify against live state before update) |
| `<SILVER_POLICY_ID>` | `10553646324755759042` (verify against live state before update) |

---

### Step A — Pre-flight checks

```bash
# Confirm branch is NOT this runbook branch
git status --short --branch
# Expected: branch docs/... or exec/... but NOT docs/notification-channels-runbook

# Confirm workspace is clean
uv sync --all-packages

# Confirm tests pass
uv run pytest -q
# Expected: 116 passed, 0 failed

# Confirm ruff clean
uv run ruff check .
# Expected: All checks passed

# Confirm Cloud SQL is NEVER / STOPPED
gcloud sql instances describe rtdp-postgres \
  --project=$PROJECT_ID \
  --format="value(settings.activationPolicy,state)"
# Expected: NEVER   STOPPED

# Confirm Scheduler is PAUSED
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=$REGION \
  --project=$PROJECT_ID \
  --format="value(state)"
# Expected: PAUSED

# List existing notification channels (pre-creation baseline)
gcloud monitoring channels list \
  --project=$PROJECT_ID \
  --format="table(name,displayName,type,enabled)"
# Record output — confirms no duplicate channel exists before creation

# List existing alert policies (pre-update baseline)
gcloud monitoring policies list \
  --project=$PROJECT_ID \
  --format="table(name,displayName,enabled)"
# Record output — confirms both policies exist before any update

# Describe Worker policy — confirm notificationChannels=[] before update
gcloud monitoring policies describe \
  projects/$PROJECT_ID/alertPolicies/<WORKER_POLICY_ID> \
  --project=$PROJECT_ID \
  --format="yaml"
# Verify: notificationChannels is absent or empty, enabled: true, metric filter unchanged

# Describe Silver policy — confirm notificationChannels=[] before update
gcloud monitoring policies describe \
  projects/$PROJECT_ID/alertPolicies/<SILVER_POLICY_ID> \
  --project=$PROJECT_ID \
  --format="yaml"
# Verify: notificationChannels is absent or empty, enabled: true, metric filter unchanged
```

Abort if any of the following:

- Cloud SQL is not `NEVER   STOPPED`
- Scheduler is not `PAUSED`
- Either alert policy is missing from the list
- Either alert policy already has an unexpected `notificationChannels` entry
- A notification channel named `RTDP Operator Email Alerts` already exists with unclear ownership

---

### Step B — Create email notification channel

```bash
gcloud monitoring channels create \
  --project=$PROJECT_ID \
  --display-name="RTDP Operator Email Alerts" \
  --type=email \
  --channel-labels=email_address="<OPERATOR_EMAIL>"
```

Expected output:

```
Created notification channel [projects/$PROJECT_ID/monitoringChannels/<CHANNEL_ID>].
```

Record the full resource name returned. This is `<CHANNEL_ID>` used in all subsequent steps.

**Email verification note:** GCP may require the email address to be verified before the
channel can receive notifications. If a verification email is sent, the execution branch must
pause and document:

- That a verification request was sent
- The address to which it was sent (redact if personal)
- Whether verification was completed before policy attachment
- Whether the channel shows `enabled: true` or `enabled: false` after creation

Do not attach an unverified channel to a policy without recording its verification state.

---

### Step C — Capture created notification channel ID

```bash
# List channels after creation — confirm new channel appears
gcloud monitoring channels list \
  --project=$PROJECT_ID \
  --format="table(name,displayName,type,enabled)"

# Describe the new channel to confirm display name and type
gcloud monitoring channels describe \
  projects/$PROJECT_ID/monitoringChannels/<CHANNEL_ID> \
  --project=$PROJECT_ID \
  --format="yaml"
```

Verify:

- `displayName: RTDP Operator Email Alerts`
- `type: email`
- `labels.email_address` matches `<OPERATOR_EMAIL>`
- Record the full `name` field — this is the value to add to both alert policies

---

### Step D — Update both alert policies

Use the export → edit → update-from-file pattern to avoid overwriting metric filters or
conditions. Do not commit any temporary JSON to the repository.

#### D1 — Export current Worker policy to /tmp

```bash
gcloud monitoring policies describe \
  projects/$PROJECT_ID/alertPolicies/<WORKER_POLICY_ID> \
  --project=$PROJECT_ID \
  --format=json > /tmp/rtdp-worker-error-alert-current.json
```

Review the exported file to confirm metric filter and conditions before editing:

```bash
cat /tmp/rtdp-worker-error-alert-current.json
```

Verify the exported JSON includes:
- `"displayName": "RTDP Worker Message Error Alert"`
- `"enabled": true`
- metric filter referencing `worker_message_error_count`
- `"notificationChannels": []` or the field is absent

#### D2 — Create updated Worker policy JSON

Copy to a separate file and add the notification channel:

```bash
cp /tmp/rtdp-worker-error-alert-current.json /tmp/rtdp-worker-error-alert-updated.json
```

Edit `/tmp/rtdp-worker-error-alert-updated.json` to set:

```json
"notificationChannels": [
  "projects/project-42987e01-2123-446b-ac7/monitoringChannels/<CHANNEL_ID>"
]
```

Do not change any other field. Verify the file before applying.

#### D3 — Update Worker policy from file

```bash
gcloud monitoring policies update \
  projects/$PROJECT_ID/alertPolicies/<WORKER_POLICY_ID> \
  --project=$PROJECT_ID \
  --policy-from-file=/tmp/rtdp-worker-error-alert-updated.json
```

#### D4 — Export current Silver policy to /tmp

```bash
gcloud monitoring policies describe \
  projects/$PROJECT_ID/alertPolicies/<SILVER_POLICY_ID> \
  --project=$PROJECT_ID \
  --format=json > /tmp/rtdp-silver-error-alert-current.json
```

Review the exported file:

```bash
cat /tmp/rtdp-silver-error-alert-current.json
```

Verify:
- `"displayName": "RTDP Silver Refresh Error Alert"`
- `"enabled": true`
- metric filter referencing `silver_refresh_error_count`
- `"notificationChannels": []` or field absent

#### D5 — Create updated Silver policy JSON

```bash
cp /tmp/rtdp-silver-error-alert-current.json /tmp/rtdp-silver-error-alert-updated.json
```

Edit `/tmp/rtdp-silver-error-alert-updated.json` to set:

```json
"notificationChannels": [
  "projects/project-42987e01-2123-446b-ac7/monitoringChannels/<CHANNEL_ID>"
]
```

Do not change any other field. Verify the file before applying.

#### D6 — Update Silver policy from file

```bash
gcloud monitoring policies update \
  projects/$PROJECT_ID/alertPolicies/<SILVER_POLICY_ID> \
  --project=$PROJECT_ID \
  --policy-from-file=/tmp/rtdp-silver-error-alert-updated.json
```

---

### Step E — Verify after update

```bash
# Describe Worker policy after update
gcloud monitoring policies describe \
  projects/$PROJECT_ID/alertPolicies/<WORKER_POLICY_ID> \
  --project=$PROJECT_ID \
  --format="yaml"
```

Confirm all of the following:

- `notificationChannels` contains `projects/$PROJECT_ID/monitoringChannels/<CHANNEL_ID>`
- `displayName: RTDP Worker Message Error Alert`
- `enabled: true`
- metric filter still references `logging.googleapis.com/user/worker_message_error_count`
- `resource.type="cloud_run_revision"` still present in filter
- threshold and conditions unchanged

```bash
# Describe Silver policy after update
gcloud monitoring policies describe \
  projects/$PROJECT_ID/alertPolicies/<SILVER_POLICY_ID> \
  --project=$PROJECT_ID \
  --format="yaml"
```

Confirm all of the following:

- `notificationChannels` contains `projects/$PROJECT_ID/monitoringChannels/<CHANNEL_ID>`
- `displayName: RTDP Silver Refresh Error Alert`
- `enabled: true`
- metric filter still references `logging.googleapis.com/user/silver_refresh_error_count`
- `resource.type="cloud_run_job"` still present in filter
- threshold and conditions unchanged

```bash
# Final Cloud SQL state
gcloud sql instances describe rtdp-postgres \
  --project=$PROJECT_ID \
  --format="value(settings.activationPolicy,state)"
# Expected: NEVER   STOPPED

# Final Scheduler state
gcloud scheduler jobs describe rtdp-silver-refresh-scheduler \
  --location=$REGION \
  --project=$PROJECT_ID \
  --format="value(state)"
# Expected: PAUSED

# Final tests
uv run pytest -q
# Expected: 116 passed, 0 failed

# Final ruff
uv run ruff check .
# Expected: All checks passed
```

---

### Step F — Optional test notification

Cloud Monitoring allows sending a test notification to a channel to verify delivery before
a real incident fires. This step is optional and does not create synthetic metric events or
trigger error paths.

```bash
# Send a test notification to the created channel (optional)
gcloud monitoring channels verify \
  projects/$PROJECT_ID/monitoringChannels/<CHANNEL_ID> \
  --project=$PROJECT_ID
```

If this command is available and succeeds, record the output in the evidence document. If it
is not available via gcloud CLI, test notification can be sent via the Cloud Monitoring
console (Alerting → Notification channels → Send test notification). Do not create synthetic
log entries or metric data points to test alert firing — that is out of scope for this
runbook.

---

## 7. Rollback Plan

Document and review the rollback procedure before executing Step D. The rollback removes the
notification channel reference from both policies and optionally deletes the channel.

### Rollback Step 1 — Re-export current policies

```bash
gcloud monitoring policies describe \
  projects/$PROJECT_ID/alertPolicies/<WORKER_POLICY_ID> \
  --project=$PROJECT_ID \
  --format=json > /tmp/rtdp-worker-error-alert-rollback.json

gcloud monitoring policies describe \
  projects/$PROJECT_ID/alertPolicies/<SILVER_POLICY_ID> \
  --project=$PROJECT_ID \
  --format=json > /tmp/rtdp-silver-error-alert-rollback.json
```

### Rollback Step 2 — Remove notification channel from both policy files

Edit both rollback JSON files to set:

```json
"notificationChannels": []
```

### Rollback Step 3 — Update both policies from rollback files

```bash
gcloud monitoring policies update \
  projects/$PROJECT_ID/alertPolicies/<WORKER_POLICY_ID> \
  --project=$PROJECT_ID \
  --policy-from-file=/tmp/rtdp-worker-error-alert-rollback.json

gcloud monitoring policies update \
  projects/$PROJECT_ID/alertPolicies/<SILVER_POLICY_ID> \
  --project=$PROJECT_ID \
  --policy-from-file=/tmp/rtdp-silver-error-alert-rollback.json
```

### Rollback Step 4 — Optionally delete the notification channel

**Only delete the channel if it is not referenced by any other alert policy.**

```bash
# List all alert policies and check for channel references before deleting
gcloud monitoring policies list \
  --project=$PROJECT_ID \
  --format="yaml" | grep notificationChannels

# Delete channel only if confirmed unused
gcloud monitoring channels delete \
  projects/$PROJECT_ID/monitoringChannels/<CHANNEL_ID> \
  --project=$PROJECT_ID
```

Do not delete a notification channel if it is referenced by any alert policy other than the
two policies in this runbook.

---

## 8. Evidence to Capture in Future Execution Branch

The future execution evidence document (`docs/notification-channels-evidence.md`) must
capture all of the following before the branch is considered complete:

| # | Evidence item | Description |
|---|---|---|
| 1 | Branch name | Must not be `docs/notification-channels-runbook` |
| 2 | Pre-execution `uv sync` | Must succeed |
| 3 | Pre-execution `uv run pytest -q` | Must show 116 passed, 0 failed |
| 4 | Pre-execution `uv run ruff check .` | Must be clean |
| 5 | Pre-execution Cloud SQL state | `NEVER / STOPPED` — gcloud output |
| 6 | Pre-execution Scheduler state | `PAUSED` — gcloud output |
| 7 | Pre-existing notification channels list | Output of `gcloud monitoring channels list` before creation |
| 8 | Pre-existing Worker policy describe | Full YAML — confirm `notificationChannels: []` before update |
| 9 | Pre-existing Silver policy describe | Full YAML — confirm `notificationChannels: []` before update |
| 10 | Channel create command output | Full output of `gcloud monitoring channels create` |
| 11 | Notification channel ID | Full resource name returned after creation |
| 12 | Channel describe output | Confirm display name, type, email label |
| 13 | Worker policy update output | Full output of `gcloud monitoring policies update` |
| 14 | Silver policy update output | Full output of `gcloud monitoring policies update` |
| 15 | Post-update Worker policy describe | Full YAML — confirm channel ID present, metric filter unchanged, enabled: true |
| 16 | Post-update Silver policy describe | Full YAML — confirm channel ID present, metric filter unchanged, enabled: true |
| 17 | Final Cloud SQL state | `NEVER / STOPPED` — gcloud output |
| 18 | Final Scheduler state | `PAUSED` — gcloud output |
| 19 | Final `uv run pytest -q` | Must show 116 passed, 0 failed |
| 20 | Final `uv run ruff check .` | Must be clean |
| 21 | No Pub/Sub publishing statement | Explicit statement: zero Pub/Sub messages were published |
| 22 | No Scheduler run statement | Explicit statement: Scheduler was not run during execution |
| 23 | No Cloud Run Job execution statement | Explicit statement: no Cloud Run Job was triggered |
| 24 | No deployment statement | Explicit statement: no code or container was deployed |

---

## 9. Acceptance Criteria

The future execution is accepted only if **all** of the following are true:

| Criterion | Required |
|---|---|
| Email notification channel exists | `RTDP Operator Email Alerts` present in `gcloud monitoring channels list` |
| Channel ID captured | Full resource name recorded in evidence document |
| Worker alert policy references channel ID | `describe` output includes the created channel name in `notificationChannels` |
| Silver alert policy references channel ID | `describe` output includes the created channel name in `notificationChannels` |
| Worker policy remains enabled | `enabled: true` confirmed in post-update describe |
| Silver policy remains enabled | `enabled: true` confirmed in post-update describe |
| Worker metric filter unchanged | `logging.googleapis.com/user/worker_message_error_count`, `resource.type="cloud_run_revision"` |
| Silver metric filter unchanged | `logging.googleapis.com/user/silver_refresh_error_count`, `resource.type="cloud_run_job"` |
| No alert thresholds changed | Both policies remain at threshold `> 0`, duration `0s` |
| Cloud SQL `NEVER / STOPPED` throughout | Confirmed before and after execution |
| Scheduler `PAUSED` throughout | Confirmed before and after execution |
| No Pub/Sub messages published | Zero messages published during execution window |
| No Cloud Run Job executed | No manual or scheduled job trigger |
| No deployment | No container deployed |
| Tests pass | `uv run pytest -q` exits 0 |
| Ruff clean | `uv run ruff check .` exits 0 |
| Evidence document created | `docs/notification-channels-evidence.md` committed on the execution branch |

---

## 10. Stop Conditions

Abort immediately and record the stop reason if any of the following are observed:

| Stop condition | Required action |
|---|---|
| Cloud SQL is not `NEVER / STOPPED` before execution | Abort; do not perform any GCP writes |
| Scheduler is not `PAUSED` before execution | Abort; do not perform any GCP writes |
| Either alert policy is missing from `gcloud monitoring policies list` | Abort; investigate before proceeding |
| Either alert policy already has an unexpected `notificationChannels` entry | Abort; do not update; clarify ownership before proceeding |
| `gcloud monitoring channels create` fails | Abort; record full error; do not retry without diagnosing root cause |
| Channel creation returns a duplicate or pre-existing channel with unclear ownership | Abort; do not proceed until duplicate is resolved |
| Email verification is required and cannot be completed safely in this window | Pause; document verification state; decide whether to defer channel attachment |
| `gcloud monitoring policies update` fails for either policy | Abort; do not proceed with second policy if first fails; rollback first policy if already updated |
| Post-update `describe` shows metric filter changed or `enabled: false` | Rollback immediately using the rollback procedure in Section 7 |
| Created channel ID cannot be found after creation | Abort; do not proceed to policy update |
| Any command would trigger alert incidents or synthetic metric events | Abort |
| Any command would run the Scheduler or trigger a Cloud Run Job | Abort |
| Any command would mutate Pub/Sub resources | Abort |
| Cloud SQL state changes from `NEVER / STOPPED` during execution | Stop all writes; document the state change; abort |

On abort: record the stop condition, the last known Cloud SQL state, the Scheduler state,
and which steps completed. Do not attempt the same run again without diagnosing the cause.

---

## 11. What This Runbook Does Not Do

This runbook does **not**:

- Execute now — all commands are future-execution templates only
- Create notification channels now — no GCP writes on this branch
- Update alert policies now — no GCP writes on this branch
- Test alert firing with synthetic errors or log entries
- Create a Slack or webhook notification channel
- Start Cloud SQL
- Run the Scheduler
- Execute any Cloud Run Job
- Publish messages to any Pub/Sub topic
- Add Terraform or IaC management for notification channels or alert policies
- Validate the 5,000-event load test
- Add BigQuery or Dataflow integration
- Make IAM changes of any kind

---

## 12. Roadmap Position

After this runbook is executed on a future branch and the evidence document is merged:

- The **notification channels gap** will be closed.
- Alert policies will be operator-actionable: error conditions detected by Cloud Monitoring
  will deliver email notifications to the configured operator address rather than remaining
  visible only in the console.
- The project will have a complete, end-to-end observability and alerting stack: validated
  metrics → dashboard → enabled alert policies → email delivery.

**Remaining gaps after future execution of this runbook:**

| Gap | Priority | Notes |
|---|---|---|
| Terraform / IaC | P1 | All GCP resources created imperatively; no Terraform state |
| 5,000-event load test | P1 | 100 and 1,000 tiers accepted; 5,000-tier not yet executed |
| BigQuery / Dataflow analytical tier | P1 | Silver layer is operational only; no analytical tier |
| CI/CD deploy automation | P1/P2 | All deployments are manual; no automated pipeline |
| README stale GCP wording cleanup | P2 | GCP target architecture section wording predates several completed execution branches |
