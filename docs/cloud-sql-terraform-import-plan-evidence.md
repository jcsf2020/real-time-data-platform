# Cloud SQL Terraform Import Plan Evidence

## 1. Status

Cloud SQL Terraform import completed and validated.

| Item | Result |
| --- | --- |
| Cloud SQL instance imported | Yes |
| Terraform plan | Zero diff |
| `terraform apply` executed | No |
| Cloud SQL started | No |
| Cloud SQL replaced | No |
| Cloud SQL final state | `NEVER STOPPED` |

---

## 2. Branch

```text
exec/cloud-sql-terraform-import-plan
```

---

## 3. Scope

This execution branch imported the existing Cloud SQL PostgreSQL instance into Terraform state and added matching HCL.

Imported resource:

```text
google_sql_database_instance.rtdp_postgres
```

New Terraform file:

```text
infra/terraform/gcp/cloud_sql.tf
```

The branch did not execute `terraform apply`. The Cloud SQL instance was imported into state only.

---

## 4. Preflight

Before adding Cloud SQL HCL or importing the instance, the branch started from a clean Terraform baseline.

Preflight results:

```text
Git branch: exec/cloud-sql-terraform-import-plan
Terraform state before Cloud SQL import: 14 existing resources
Terraform plan before Cloud SQL HCL: No changes
Cloud SQL instance present: rtdp-postgres
Cloud SQL activation policy: NEVER
Cloud SQL state: STOPPED
```

Existing pre-import Terraform state resources included Pub/Sub, Scheduler, Monitoring, Cloud Run services, and the Cloud Run job.

---

## 5. Cloud SQL Runtime Snapshot

Cloud SQL instance snapshot before import:

| Field | Value |
| --- | --- |
| Name | `rtdp-postgres` |
| Database version | `POSTGRES_16` |
| Region | `europe-west1` |
| State | `STOPPED` |
| Tier | `db-custom-1-3840` |
| Activation policy | `NEVER` |
| Availability type | `ZONAL` |
| Edition | `ENTERPRISE` |
| Disk type | `PD_HDD` |
| Disk size | `10` GB |
| Deletion protection enabled | `false` |
| Terraform deletion protection | `true` |
| Backup enabled | `false` |
| IPv4 enabled | `true` |
| SSL mode | `ALLOW_UNENCRYPTED_AND_ENCRYPTED` |
| Require SSL | `false` |
| Authorized network | `37.189.31.189/32` |
| Zone | `europe-west1-b` |

The instance remained stopped throughout the import.

---

## 6. HCL Added

`infra/terraform/gcp/cloud_sql.tf` defines:

```text
google_sql_database_instance.rtdp_postgres
```

The HCL preserves:

- Cloud SQL instance name;
- project and region;
- PostgreSQL version;
- tier;
- availability type;
- edition;
- disk type and size;
- disk autoresize setting;
- activation policy `NEVER`;
- backup disabled state;
- public IPv4 configuration;
- SSL mode;
- authorized network;
- location preference zone;
- Terraform `prevent_destroy` lifecycle guard.

---

## 7. Import Command Executed

```bash
terraform -chdir=infra/terraform/gcp import \
  google_sql_database_instance.rtdp_postgres \
  project-42987e01-2123-446b-ac7/rtdp-postgres
```

Result:

```text
Import successful.
```

---

## 8. Drift Found and Resolved

Initial post-import plan showed an in-place update risk.

Drift areas:

```text
deletion_protection: true -> false
disk_autoresize: false -> true
enable_dataplex_integration: true -> null
```

Terraform state inspection also showed additional fields that needed to be preserved explicitly:

```text
backup start_time = "00:00"
transaction_log_retention_days = 7
backup_retention_settings = 7 COUNT
data_cache_config = false
location_preference.zone = europe-west1-b
authorized_networks.name omitted/null
```

Resolution:

- HCL was aligned to imported Terraform state.
- `deletion_protection = true` was preserved at Terraform resource level.
- `settings.disk_autoresize = false` was preserved.
- `settings.enable_dataplex_integration = true` was preserved.
- Backup retention, data cache, and location preference were represented in HCL.
- Authorized network was represented without forcing an empty name.
- Final plan reached zero change.

---

## 9. Final Terraform State

Final Cloud SQL resource in Terraform state:

```text
google_sql_database_instance.rtdp_postgres
```

The resource now lives in the GCS-backed Terraform state together with the previously imported Pub/Sub, Scheduler, Monitoring, and Cloud Run resources.

---

## 10. Final Validation

Final validation commands executed:

```bash
terraform fmt -recursive infra/terraform/gcp
terraform -chdir=infra/terraform/gcp validate
terraform -chdir=infra/terraform/gcp plan
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="value(settings.activationPolicy,state)"
```

Final validation results:

```text
terraform -chdir=infra/terraform/gcp validate: success
terraform -chdir=infra/terraform/gcp plan: No changes
Cloud SQL final state: NEVER STOPPED
```

---

## 11. Explicit Non-Actions

The following actions were not performed:

- No `terraform apply`
- No Cloud SQL start
- No Cloud SQL replacement
- No Cloud SQL deletion
- No database version change
- No tier change
- No IP configuration mutation
- No backup policy mutation
- No Secret Manager import
- No secret value read
- No IAM import
- No IAM policy update
- No Scheduler run
- No Cloud Run Job execution
- No Pub/Sub publishing
- No application code changes
- No test changes

---

## 12. Acceptance Result

Accepted.

Cloud SQL PostgreSQL instance `rtdp-postgres` is now imported into Terraform state with final zero-diff plan.

Terraform now manages the following Cloud SQL resource:

```text
google_sql_database_instance.rtdp_postgres
```

No infrastructure mutation was applied. The migration was state-only plus matching HCL.
