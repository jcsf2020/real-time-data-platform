# Apache Beam DirectRunner Pipeline Evidence

**Branch:** `feat/beam-directrunner-market-events-pipeline`
**Date:** 2026-05-23
**Status:** VALIDATED -- Apache Beam DirectRunner local proof implemented and tested.

---

## Purpose

Implement and prove the first Apache Beam pipeline capability for the Real-Time Data Platform
using the local DirectRunner only. No GCP execution. No cloud cost. No DataflowRunner.

This is Phase 1 of the proof sequence defined in
[docs/dataflow-apache-beam-architecture-decision.md](dataflow-apache-beam-architecture-decision.md),
Section 6.1.

---

## What Was Implemented

### Dependency

`apache-beam>=2.60.0` added to the root `[dependency-groups].dev` group in `pyproject.toml`.
Not added to any application package or Docker image runtime dependency.
Resolved version: `apache-beam==2.70.0` on Python 3.12.12.

### Pipeline module

`pipelines/beam_market_events.py`

- Reads MarketEvent-compatible JSONL records from a local input file via `beam.io.ReadFromText`.
- Parses each line as JSON (`ParseAndValidateDoFn`).
- Validates each record against the existing `rtdp_contracts.MarketEvent` Pydantic contract.
- Routes valid records to the main output as normalized JSON dicts containing:
  `event_id`, `event_timestamp`, `symbol`, `event_type`, `price`, `quantity`.
- Routes invalid records (JSON parse errors and schema validation failures) to a dead-letter
  side output via `pvalue.TaggedOutput`.
- Writes valid output to a local JSONL file.
- Writes dead-letter records to a separate local JSONL file.
- `ALLOWED_RUNNERS = frozenset({"DirectRunner"})` — any non-DirectRunner runner raises
  `ValueError` before the pipeline is constructed.
- No Pub/Sub import. No BigQuery import. No GCP client import. No GCP credentials required.

### CLI entrypoint

```
python -m pipelines.beam_market_events \
  --input-jsonl <path> \
  --output-jsonl <path> \
  --dead-letter-jsonl <path>
```

- Default runner: `DirectRunner`.
- Rejects any `--runner` value other than `DirectRunner` with a clear error and exit code 1.
- Exits with code 1 if the input file does not exist.
- Exits with code 0 on successful local processing.

### Tests

`tests/test_beam_market_events.py` — 13 tests, all passing.

The real CLI entrypoint (`python -m pipelines.beam_market_events`) is tested via
`subprocess.run` with `sys.executable`, verifying return code, file creation, record
counts, field values, and DataflowRunner rejection from the OS process boundary.

| Test | Layer | Description |
| --- | --- | --- |
| `test_valid_event_routed_to_main_output` | DoFn / TestPipeline | Valid JSONL → normalized dict in main output; dead-letter empty |
| `test_invalid_json_routed_to_dead_letter` | DoFn / TestPipeline | Invalid JSON → dead-letter; main output empty |
| `test_schema_invalid_event_routed_to_dead_letter` | DoFn / TestPipeline | Schema-invalid event (price ≤ 0) → dead-letter |
| `test_output_count_equals_valid_input_count` | DoFn / TestPipeline | 3 valid inputs → 3 normalized outputs; 0 dead-letter |
| `test_dead_letter_count_equals_invalid_input_count` | DoFn / TestPipeline | 2 valid + 2 invalid → 2 output + 2 dead-letter |
| `test_runner_guard_rejects_dataflow_runner` | `run()` API | `run(..., runner="DataflowRunner")` raises `ValueError` |
| `test_runner_guard_rejects_arbitrary_runner` | `run()` API | `run(..., runner="SparkRunner")` raises `ValueError` |
| `test_no_gcp_env_vars_required` | Import safety | Module imports cleanly with all GCP env vars removed |
| `test_no_pubsub_bigquery_clients_in_module_source` | Source inspection | Source confirms no Pub/Sub / BigQuery imports |
| `test_run_with_temporary_files` | `run()` API + files | `run()` with real temp files; output and dead-letter verified |
| `test_cli_subprocess_valid_and_dead_letter` | Real CLI subprocess | `python -m pipelines.beam_market_events` returncode=0; output file and dead-letter file created; 1 valid + 1 dead-letter; event_id, symbol, price, quantity verified |
| `test_cli_subprocess_rejects_dataflow_runner` | Real CLI subprocess | `--runner DataflowRunner` → returncode≠0; "DataflowRunner" in stderr; no GCP execution |
| `test_directrunner_output_is_deterministic` | `run()` API + files | Same input run twice → sorted output lines identical |

---

## Explicit Statement of Scope

- **Apache Beam DirectRunner local proof: IMPLEMENTED AND VALIDATED.**
- **DataflowRunner: NOT executed.** No Dataflow job launched against any GCP project.
- **GCP: NOT mutated.** No GCP resource created, modified, or destroyed.
- **Pub/Sub: NOT used.** No Pub/Sub client imported or called.
- **BigQuery: NOT used.** No BigQuery client imported or called.
- **Cloud SQL: NOT started.** Activation policy remains NEVER / STOPPED.
- **Schedulers: NOT activated.** Both schedulers remain PAUSED.
- **Dataflow is NOT proven.** This branch proves the local DirectRunner path only.
- **Exactly-once semantics: NOT claimed.** DirectRunner is local only; transport semantics
  are not applicable in this phase.

---

## Validation Output

### `uv sync --all-packages`

```
Resolved 125 packages in 934ms
   Building rtdp-bigquery-append-job ...
Installed 18 packages in 69ms
 + apache-beam==2.70.0
 + beartype==0.21.0
 + dnspython==2.8.0
 + fastavro==1.12.2
 + fasteners==0.20
 + grpcio==1.65.5
 + grpcio-status==1.62.3
 + httplib2==0.22.0
 + jsonpickle==3.4.2
 + numpy==2.2.6
 + objsize==0.7.1
 + pyarrow==18.1.0
 + pyarrow-hotfix==0.7
 + pymongo==4.17.0
 + pyparsing==3.3.2
 + sortedcontainers==2.4.0
 + zstandard==0.25.0
```

### `uv run pytest -q`

```
361 passed, 10 warnings in 12.23s
```

(348 prior tests all passing; 13 new Beam tests added.)

### `uv run ruff check .`

```
All checks passed!
```

### `terraform fmt -check -recursive infra/terraform/gcp`

```
FMT_EXIT=0
```

### `terraform -chdir=infra/terraform/gcp validate`

```
Success! The configuration is valid.
```

### `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false`

```
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

No Terraform resources were created, modified, or destroyed.

### Cloud SQL state

```
NAME           STATE    ACTIVATION_POLICY
rtdp-postgres  STOPPED  NEVER
```

Cloud SQL remains STOPPED / NEVER. Not started during this branch.

### Cloud Scheduler state

```
ID  STATE   SCHEDULE
    PAUSED  */15 * * * *
    PAUSED  0 * * * *
```

Both schedulers remain PAUSED. Not activated during this branch.

---

## Safety Confirmation

| Control | State |
|---|---|
| DataflowRunner executed | NO |
| GCP resources mutated | NO |
| Pub/Sub client imported | NO |
| BigQuery client imported | NO |
| Cloud SQL started | NO (STOPPED/NEVER) |
| Schedulers activated | NO (both PAUSED) |
| Terraform apply executed | NO (PLAN_EXIT=0) |
| Production table written | NO |
| Production subscription consumed | NO |

---

## Residual Risks

- The `apache-beam` package was added to the dev dependency group. It is not in any application
  package or Dockerfile runtime. Beam's transitive dependencies (numpy, pyarrow, grpcio,
  httplib2) are now present in the local venv. These do not affect Docker image sizes.
- `grpcio` was downgraded from 1.80.0 to 1.65.5 by Beam's dependency resolution. No
  application package depends on a specific grpcio version, and all 361 tests pass.
- The `TestPipeline` class name triggers a pytest collection warning
  (`PytestCollectionWarning: cannot collect test class 'TestPipeline'`). This is a known
  upstream issue in apache-beam's test utilities. It does not affect test execution.
- DirectRunner is single-process, single-machine only. All throughput characteristics from
  this proof are bounded by local resources and are not representative of DataflowRunner
  performance.

---

## Next Step

`infra/dataflow-bounded-proof-prereqs` — Terraform prerequisites for a bounded DataflowRunner
proof: Dataflow service account, GCS staging bucket, BigQuery proof table, Pub/Sub pull
subscription. No DataflowRunner execution in that branch either; infrastructure only.

See [docs/dataflow-apache-beam-architecture-decision.md](dataflow-apache-beam-architecture-decision.md)
Section 6.2 for the full specification.
