# Dataflow Bounded Proof Prerequisites Evidence

**Branch:** `infra/dataflow-bounded-proof-prereqs`
**Date:** 2026-05-23
**Status:** VALIDATED -- 9 Dataflow proof prerequisite resources applied; CI Terraform Plan IAM custom role fix applied (2 resources; APPLY_EXIT=0); post-fix PLAN_EXIT=0.

---

## Purpose

Provision the minimal Terraform-managed GCP infrastructure required to support a future bounded
DataflowRunner proof on the branch `feat/dataflow-bounded-market-events-proof`.

This is Phase 2 of the proof sequence defined in
[docs/dataflow-apache-beam-architecture-decision.md](dataflow-apache-beam-architecture-decision.md),
Section 6.2.

Phase 1 (DirectRunner local proof) was completed on branch
`feat/beam-directrunner-market-events-pipeline` and is documented in
[docs/beam-directrunner-pipeline-evidence.md](beam-directrunner-pipeline-evidence.md).

No Beam pipeline code is modified. No DataflowRunner job is executed. No GCP workloads are
started. All changes are Terraform resource definitions only.

---

## Resources Added

All resources are defined in `infra/terraform/gcp/dataflow.tf`.
The proof table schema is defined in `infra/terraform/gcp/schemas/market_events_beam_proof.json`.

| Resource | Type | Name / ID |
|---|---|---|
| Service account | `google_service_account` | `rtdp-dataflow-sa` |
| GCS staging bucket | `google_storage_bucket` | `rtdp-dataflow-staging-project-42987e01-2123-446b-ac7` |
| Pub/Sub pull subscription | `google_pubsub_subscription` | `market-events-raw-beam-proof-sub` |
| BigQuery proof table | `google_bigquery_table` | `rtdp_analytics.market_events_beam_proof` |
| IAM: Dataflow worker | `google_project_iam_member` | `roles/dataflow.worker` on `rtdp-dataflow-sa` (project-level) |
| IAM: BigQuery job user | `google_project_iam_member` | `roles/bigquery.jobUser` on `rtdp-dataflow-sa` (project-level) |
| IAM: Storage object admin | `google_storage_bucket_iam_member` | `roles/storage.objectAdmin` on staging bucket only |
| IAM: Pub/Sub subscriber | `google_pubsub_subscription_iam_member` | `roles/pubsub.subscriber` on proof subscription only |
| IAM: BigQuery data editor | `google_bigquery_table_iam_member` | `roles/bigquery.dataEditor` on proof table only |

**Total: 9 new resources. 0 existing resources changed.**

### GCS Bucket Details

- Name: `rtdp-dataflow-staging-project-42987e01-2123-446b-ac7`
- Location: `europe-west1` (aligned with existing platform region)
- Uniform bucket-level access: enabled
- Lifecycle rule: delete all objects after 7 days
- force_destroy: true (staging bucket; all objects are temporary)
- Public access: none granted

### Pub/Sub Subscription Details

- Name: `market-events-raw-beam-proof-sub`
- Topic: `market-events-raw` (existing production topic; read-only attachment)
- Type: **pull** (no push_config block)
- ack_deadline_seconds: 60
- message_retention_duration: 600s
- This subscription is entirely separate from `market-events-raw-worker-push`.
  The production Cloud Run worker is not affected.

### BigQuery Proof Table Details

- Dataset: `rtdp_analytics` (existing)
- Table: `market_events_beam_proof`
- deletion_protection: false (proof table; not production)
- Partitioning: DAY on `event_timestamp` (consistent with `market_events_raw`)
- Clustering: `[symbol, event_type]` (consistent with `market_events_raw`)
- Schema: minimal subset matching current pipeline output fields

```json
[
  { "name": "event_id",        "type": "STRING",    "mode": "REQUIRED" },
  { "name": "event_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED" },
  { "name": "symbol",          "type": "STRING",    "mode": "REQUIRED" },
  { "name": "event_type",      "type": "STRING",    "mode": "REQUIRED" },
  { "name": "price",           "type": "NUMERIC",   "mode": "NULLABLE" },
  { "name": "quantity",        "type": "NUMERIC",   "mode": "NULLABLE" }
]
```

Schema rationale: the existing `pipelines/beam_market_events.py` `ParseAndValidateDoFn`
outputs exactly these six fields. The production `market_events_raw` schema also includes
`source`, `ingest_timestamp`, and `bq_load_timestamp`; those are omitted from the proof
table because the current pipeline does not populate them, and the pipeline code is not
modified in this branch.

---

## IAM Rationale

Least-privilege was applied as narrowly as GCP allows for each grant type.

| Binding | Scope | Reason for scope |
|---|---|---|
| `roles/dataflow.worker` | Project | GCP requirement. No resource-level scoping exists for the Dataflow worker role. Required for Dataflow worker process startup and internal job coordination. |
| `roles/bigquery.jobUser` | Project | GCP requirement. No resource-level scoping exists for BigQuery job submission. Required to run write jobs to BigQuery from Dataflow workers. |
| `roles/storage.objectAdmin` | Staging bucket only | Scoped via `google_storage_bucket_iam_member`. Grants read/write/delete on `rtdp-dataflow-staging-project-42987e01-2123-446b-ac7` only. All other buckets (including Terraform state bucket) are untouched. |
| `roles/pubsub.subscriber` | Proof subscription only | Scoped via `google_pubsub_subscription_iam_member`. Grants read access to `market-events-raw-beam-proof-sub` only. The production `market-events-raw-worker-push` subscription is not accessible. |
| `roles/bigquery.dataEditor` | Proof table only | Scoped via `google_bigquery_table_iam_member`. Grants read/write on `rtdp_analytics.market_events_beam_proof` only. The production `market_events_raw` table is not accessible. |

Roles explicitly NOT granted: `Owner`, `Editor`, `BigQuery Admin`, `Storage Admin`,
`Pub/Sub Admin`, `roles/dataflow.admin`.

The two unavoidable project-level grants (`roles/dataflow.worker`,
`roles/bigquery.jobUser`) are standard GCP requirements for Dataflow pipelines and are
documented as such in GCP's Dataflow security documentation. No broader alternative exists.

---

## Explicit Non-Claims

As of 2026-05-23 on branch `infra/dataflow-bounded-proof-prereqs`:

- **DataflowRunner NOT executed.** No Dataflow job has been launched. No `gcloud dataflow jobs`
  command has been run. The pipeline module `pipelines/beam_market_events.py` still rejects
  any runner other than `DirectRunner`.
- **Dataflow job NOT launched.** No job ID exists. No GCP Dataflow worker has been started.
- **Apache Beam DirectRunner local proof already exists** (branch
  `feat/beam-directrunner-market-events-pipeline`; 361 pytest passing), but this branch does
  NOT modify it. Pipeline code is unchanged.
- **No Pub/Sub messages published.** The proof subscription `market-events-raw-beam-proof-sub`
  is provisioned but has received no messages. No `gcloud pubsub` publish command has been run.
- **No BigQuery writes executed.** The proof table `market_events_beam_proof` is provisioned
  (post-apply) but contains 0 rows. No BigQuery DML or load job has been submitted.
- **Cloud SQL NOT started.** `rtdp-postgres` activation policy is NEVER / STOPPED throughout.
  No Cloud SQL connections have been made.
- **Schedulers NOT activated.** Both `rtdp-silver-refresh-scheduler` and
  `rtdp-bigquery-append-scheduler` remain PAUSED. No scheduler execution has been triggered.
- **No production resources modified.** The existing `market-events-raw-worker-push`
  subscription, `market_events_raw` BigQuery table, and all Cloud Run services are unchanged.
- **Dataflow API enablement** is a prerequisite for the next branch
  (`feat/dataflow-bounded-market-events-proof`) and must be confirmed before any Dataflow job
  is launched. This branch does not enable or verify the Dataflow API.

---

## Validation Outputs

### pytest

```
uv run pytest -q
```

```
361 passed, 10 warnings in 11.92s
```

### ruff

```
uv run ruff check .
```

```
All checks passed!
```

### terraform fmt

```
terraform fmt -check -recursive infra/terraform/gcp
```

```
FMT_EXIT=0
```

### terraform validate

```
terraform -chdir=infra/terraform/gcp validate
```

```
Success! The configuration is valid.
VALIDATE_EXIT=0
```

### terraform plan (pre-apply)

```
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo PLAN_EXIT=$?
```

```
Plan: 9 to add, 0 to change, 0 to destroy.
PLAN_EXIT=2
```

Resources planned:
- `google_service_account.rtdp_dataflow_sa`
- `google_storage_bucket.rtdp_dataflow_staging`
- `google_pubsub_subscription.market_events_raw_beam_proof_sub`
- `google_bigquery_table.market_events_beam_proof`
- `google_project_iam_member.dataflow_sa_dataflow_worker`
- `google_project_iam_member.dataflow_sa_bigquery_job_user`
- `google_storage_bucket_iam_member.dataflow_sa_staging_object_admin`
- `google_pubsub_subscription_iam_member.dataflow_sa_proof_sub_subscriber`
- `google_bigquery_table_iam_member.dataflow_sa_proof_table_editor`

No existing resources changed. No existing resources destroyed.

### terraform apply

```
terraform -chdir=infra/terraform/gcp apply -input=false
```

```
Apply complete! Resources: 9 added, 0 changed, 0 destroyed.
APPLY_EXIT=0
```

Resources applied:

- `google_service_account.rtdp_dataflow_sa` → `rtdp-dataflow-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com`
- `google_storage_bucket.rtdp_dataflow_staging` → `gs://rtdp-dataflow-staging-project-42987e01-2123-446b-ac7`
- `google_pubsub_subscription.market_events_raw_beam_proof_sub` → `market-events-raw-beam-proof-sub`
- `google_bigquery_table.market_events_beam_proof` → `rtdp_analytics.market_events_beam_proof`
- `google_project_iam_member.dataflow_sa_dataflow_worker`
- `google_project_iam_member.dataflow_sa_bigquery_job_user`
- `google_storage_bucket_iam_member.dataflow_sa_staging_object_admin`
- `google_pubsub_subscription_iam_member.dataflow_sa_proof_sub_subscriber`
- `google_bigquery_table_iam_member.dataflow_sa_proof_table_editor`

### terraform plan (post-apply)

```
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"
```

```
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

### Cloud SQL state

```
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state,settings.activationPolicy)"
```

```
NAME           STATE    ACTIVATION_POLICY
rtdp-postgres  STOPPED  NEVER
```

### Cloud Scheduler state

```
gcloud scheduler jobs list \
  --project=project-42987e01-2123-446b-ac7 \
  --location=europe-west1 \
  --format="table(id,state,schedule)"
```

```
ID  STATE   SCHEDULE
    PAUSED  */15 * * * *
    PAUSED  0 * * * *
```

Both schedulers confirmed PAUSED. Cloud SQL confirmed STOPPED / NEVER.

---

## CI Terraform Plan IAM fix

### Root cause

GitHub Actions Terraform Plan (PR #211) failed with:

```
permission: pubsub.subscriptions.getIamPolicy
reason: IAM_PERMISSION_DENIED
Failing resource: google_pubsub_subscription_iam_member.dataflow_sa_proof_sub_subscriber
```

The CI Terraform Plan service account (`rtdp-terraform-plan-ci`) holds `roles/viewer` at
project level, which does not include `pubsub.subscriptions.getIamPolicy`. This permission
is required for Terraform to read the current IAM policy on the Pub/Sub subscription when
planning `google_pubsub_subscription_iam_member` resources. The plan never reached the GCS
bucket or BigQuery table IAM resources; those are treated as precautionary cases below.

### Fix

Three resource-scoped IAM bindings added to `infra/terraform/gcp/dataflow.tf` for the CI
Terraform Plan SA. All bindings are scoped to the specific proof resource only; no
project-level roles are added.

| Resource | Role | Scope | Permission rationale |
|---|---|---|---|
| `google_pubsub_subscription_iam_member.terraform_plan_ci_proof_sub_viewer` | `roles/pubsub.viewer` | Proof subscription only | `pubsub.subscriptions.getIamPolicy` — confirmed CI failure |
| `google_storage_bucket_iam_member.terraform_plan_ci_staging_bucket_reader` | `roles/storage.legacyBucketReader` | Staging bucket only | `storage.buckets.get` — precautionary; GCS IAM not yet reached by CI plan |
| `google_bigquery_table_iam_member.terraform_plan_ci_proof_table_viewer` | `roles/bigquery.dataViewer` | Proof table only | `bigquery.tables.getIamPolicy` — precautionary; BQ IAM not yet reached by CI plan |

Roles explicitly NOT granted: `Owner`, `Editor`, `BigQuery Admin`, `Storage Admin`,
`Pub/Sub Admin`, or any project-level IAM admin role.

### CI fix validation

#### terraform apply

```
terraform -chdir=infra/terraform/gcp apply -input=false
```

```
Apply complete! Resources: 3 added, 0 changed, 0 destroyed.
APPLY_EXIT=0
```

Resources applied:

- `google_pubsub_subscription_iam_member.terraform_plan_ci_proof_sub_viewer`
- `google_storage_bucket_iam_member.terraform_plan_ci_staging_bucket_reader`
- `google_bigquery_table_iam_member.terraform_plan_ci_proof_table_viewer`

No existing resources changed. No existing resources destroyed. The 9 originally applied
Dataflow proof prerequisite resources are unchanged.

#### terraform plan (post-fix)

```
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"
```

```
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

### Correction (2026-05-24): resource-scoped viewer bindings insufficient — custom role required

PR #211 still failed after the 3 resource-scoped viewer bindings were applied:

```
storage.buckets.getIamPolicy DENIED
  resource: google_storage_bucket_iam_member.dataflow_sa_staging_object_admin

pubsub.subscriptions.getIamPolicy DENIED
  resources: google_pubsub_subscription_iam_member.dataflow_sa_proof_sub_subscriber
             google_pubsub_subscription_iam_member.terraform_plan_ci_proof_sub_viewer
```

**Root cause of correction:** Resource-scoped viewer bindings cannot break the circular
dependency. For Terraform to plan any `*_iam_member` resource, it must call `GetIamPolicy`
on the target resource. That includes the viewer bindings themselves — so the CI SA needed
`getIamPolicy` before those bindings could be read, which they could not grant.
`roles/storage.legacyBucketReader` also confirmed not to include
`storage.buckets.getIamPolicy`.

**Operative fix:** A project-level custom IAM role with exactly three permissions grants
the CI SA unconditional `getIamPolicy` on all proof resources without the circular
dependency:

| Permission | Covers |
|---|---|
| `pubsub.subscriptions.getIamPolicy` | `google_pubsub_subscription_iam_member.*` |
| `storage.buckets.getIamPolicy` | `google_storage_bucket_iam_member.*` |
| `bigquery.tables.getIamPolicy` | `google_bigquery_table_iam_member.*` |

No metadata reads added: `roles/viewer` (already held project-wide) covers
`pubsub.subscriptions.get`, `storage.buckets.get`, and `bigquery.tables.get`.

Terraform resources added to `infra/terraform/gcp/dataflow.tf`:

```
google_project_iam_custom_role.terraform_plan_ci_dataflow_proof_iam_viewer
  role_id:     rtdpTerraformPlanDataflowProofIamViewer
  permissions: bigquery.tables.getIamPolicy
               pubsub.subscriptions.getIamPolicy
               storage.buckets.getIamPolicy

google_project_iam_member.terraform_plan_ci_dataflow_proof_iam_viewer
  role:   projects/project-42987e01-2123-446b-ac7/roles/rtdpTerraformPlanDataflowProofIamViewer
  member: rtdp-terraform-plan-ci@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com
```

The three previous resource-scoped bindings (`terraform_plan_ci_proof_sub_viewer`,
`terraform_plan_ci_staging_bucket_reader`, `terraform_plan_ci_proof_table_viewer`) are
**retained** to avoid unplanned destroys. They are not the operative CI unblocker.

#### terraform apply (custom role correction)

```
terraform -chdir=infra/terraform/gcp apply -input=false
```

```
Apply complete! Resources: 2 added, 0 changed, 0 destroyed.
APPLY_EXIT=0
```

Resources applied:

- `google_project_iam_custom_role.terraform_plan_ci_dataflow_proof_iam_viewer`
- `google_project_iam_member.terraform_plan_ci_dataflow_proof_iam_viewer`

No existing resources changed. No existing resources destroyed. All 12 previously applied
resources (9 proof prereqs + 3 CI reader bindings) are unchanged.

#### terraform plan (post-custom-role-fix)

```
terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false; echo "PLAN_EXIT=$?"
```

```
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

### Explicit non-claims (unchanged)

- **DataflowRunner NOT executed.**
- **Dataflow job NOT launched.**
- **No Pub/Sub messages published.**
- **No BigQuery writes executed.**
- **Cloud SQL NOT started.** Confirmed STOPPED / NEVER.
- **Schedulers NOT activated.** Both remain PAUSED.
- **No production resources modified.**

---

## Next Step

Branch `feat/dataflow-bounded-market-events-proof`:

- Extend `pipelines/beam_market_events.py` to support `DataflowRunner` with
  `ReadFromPubSub` → `ParseAndValidate` → `WriteToBigQuery` targeting
  `rtdp_analytics.market_events_beam_proof`.
- Execute a bounded Dataflow job (N test events; explicit drain/cancel within 10-minute ceiling).
- Capture job ID, final state (DONE or DRAINED), BigQuery row count, Cloud Logging excerpt,
  and cost estimate as evidence.
- Verify Cloud SQL STOPPED/NEVER and schedulers PAUSED after job completion.

---

## Evidence Links

| Document | Relevance |
|---|---|
| [docs/dataflow-apache-beam-architecture-decision.md](dataflow-apache-beam-architecture-decision.md) | ADR defining proof design; Section 6.2 is the source of requirements for this branch |
| [docs/beam-directrunner-pipeline-evidence.md](beam-directrunner-pipeline-evidence.md) | Phase 1 DirectRunner proof; 361 pytest passing |
| [docs/EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | Master evidence catalog |
| [infra/terraform/gcp/dataflow.tf](../infra/terraform/gcp/dataflow.tf) | New Terraform file defining all proof prerequisites |
| [infra/terraform/gcp/schemas/market_events_beam_proof.json](../infra/terraform/gcp/schemas/market_events_beam_proof.json) | BigQuery proof table schema |
