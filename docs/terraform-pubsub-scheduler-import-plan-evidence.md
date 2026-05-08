

# Terraform Pub/Sub + Scheduler Import / Plan Evidence

## Status

**VALIDATED - LOW-RISK IMPORT AND CLEAN PLAN**

This document records the Terraform import and plan evidence for the first low-risk GCP resources in the Real-Time Data Platform.

No `terraform apply` was executed. No live GCP resources were intentionally modified. The final Terraform plan is clean.

## Branch

`feat/terraform-pubsub-scheduler-import-plan`

## Scope

Imported into local Terraform state:

- `google_pubsub_topic.market_events_raw`
- `google_pubsub_topic.market_events_raw_dlq`
- `google_pubsub_subscription.market_events_raw_worker_push`
- `google_cloud_scheduler_job.silver_refresh_scheduler`

Explicitly excluded from this phase:

- Cloud SQL
- Cloud Run services/jobs
- IAM
- Secret Manager
- Cloud Monitoring metrics, dashboards, alert policies, and notification channels
- BigQuery / Dataflow
- Any deployment automation

## HCL Alignment Changes

The Terraform skeleton was adjusted to match live GCP inventory before accepting the final plan.

### Pub/Sub Push OIDC

The Pub/Sub push OIDC service account was confirmed from Phase 0 inventory and set explicitly:

```text
rtdp-pubsub-push-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

### Pub/Sub Subscription Retention

The imported subscription showed live retention of `600s`. The HCL was updated to avoid Terraform attempting to change it to the provider default of `604800s`.

```hcl
message_retention_duration = "600s"
```

### Cloud Scheduler Retry Config

The imported Scheduler job contained an explicit default retry configuration. The HCL was updated to match it exactly:

```hcl
retry_config {
  retry_count          = 0
  max_retry_duration   = "0s"
  min_backoff_duration = "5s"
  max_backoff_duration = "3600s"
  max_doublings        = 5
}
```

The Scheduler description was removed from HCL because the live resource does not have that description. Keeping it would have caused Terraform to propose an in-place update.

## Import Order

Resources were imported one at a time, with `terraform plan` checks between imports.

1. `google_pubsub_topic.market_events_raw`
2. `google_pubsub_topic.market_events_raw_dlq`
3. `google_pubsub_subscription.market_events_raw_worker_push`
4. `google_cloud_scheduler_job.silver_refresh_scheduler`

## Drift Found and Resolved

### Pub/Sub Subscription

Initial plan after importing the subscription showed:

```text
message_retention_duration = "600s" -> "604800s"
```

Resolution: explicitly declared `message_retention_duration = "600s"` in `infra/terraform/gcp/pubsub.tf`.

### Cloud Scheduler

Initial plan after importing Scheduler showed:

```text
+ description = "..."
- retry_config { ... }
```

Resolution:

- removed `description` from `infra/terraform/gcp/scheduler.tf`;
- added the live `retry_config` block to `infra/terraform/gcp/scheduler.tf`.

## Terraform State List

```text
google_cloud_scheduler_job.silver_refresh_scheduler
google_pubsub_subscription.market_events_raw_worker_push
google_pubsub_topic.market_events_raw
google_pubsub_topic.market_events_raw_dlq
```

## Final Terraform Plan

Final command:

```bash
terraform -chdir=infra/terraform/gcp plan
```

Final result:

```text
No changes. Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your configuration and found no differences, so no changes are needed.
```

## Final GCP Safety State

```text
Scheduler: PAUSED
Cloud SQL: NEVER / STOPPED
```

## Local Terraform Files Created But Not Committed

The following local Terraform files/directories were created by `terraform init` and `terraform import` and remain gitignored:

```text
infra/terraform/gcp/.terraform/
infra/terraform/gcp/.terraform.lock.hcl
infra/terraform/gcp/terraform.tfstate
infra/terraform/gcp/terraform.tfstate.backup
```

These files must not be committed during this exploratory local-state phase.

## What Was Not Done

- No `terraform apply`
- No Cloud SQL import
- No Cloud Run import
- No IAM import
- No Secret Manager import
- No Monitoring import
- No BigQuery/Dataflow work
- No GCP deployment
- No Scheduler run
- No Cloud SQL start
- No Pub/Sub publishing
- No application code changes
- No test changes

## Acceptance Result

Accepted.

The low-risk Pub/Sub and Scheduler resources are now represented by Terraform HCL and imported into local Terraform state with a clean zero-diff plan.

This closes the first Terraform import/plan phase for low-risk GCP resources.
