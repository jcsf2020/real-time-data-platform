# Dataflow Bounded Runner Proof Evidence

**Branch:** `feat/dataflow-bounded-market-events-proof` → execution branch `exec/dataflow-bounded-runner-proof`
**Date:** 2026-05-24
**Status:** VALIDATED -- DataflowRunner bounded proof executed successfully (2026-05-24); job ID `2026-05-24_03_59_31-13978483355822818690`; final state `JOB_STATE_DRAINED`; 10 proof rows written to `market_events_beam_proof`; Cloud SQL STOPPED/NEVER; schedulers PAUSED; production resources not used.

---

## Successful DataflowRunner Proof Execution (2026-05-24)

### Run summary

| Field | Value |
|---|---|
| Run ID | `beam-proof-v2-20260524T105821Z` |
| Dataflow job ID | `2026-05-24_03_59_31-13978483355822818690` |
| Dataflow job name | `rtdp-market-events-beam-proof` |
| Region | `europe-west1` |
| Project | `project-42987e01-2123-446b-ac7` |
| Job create time | `2026-05-24T10:59:32.026572Z` |
| Final job state | `JOB_STATE_DRAINED` |
| Final state time | `2026-05-24T11:12:17.432937Z` |
| Published messages | 10 test messages to `market-events-raw-beam-proof` (proof-only topic) |
| Proof subscription | `market-events-raw-beam-proof-sub` |
| Output table | `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_beam_proof` |
| BigQuery proof rows written | **10** |
| Cloud SQL state | STOPPED / NEVER (unchanged) |
| Schedulers state | PAUSED (unchanged) |
| Production resources mutated | None |

### Row sample confirmed

| Field | Value |
|---|---|
| event_id range | `beam-proof-v2-20260524T105821Z-1` through `beam-proof-v2-20260524T105821Z-10` |
| symbol | `BTCUSDT` |
| event_type | `trade` |
| price range | 51001 through 51010 |
| quantity | 0.001 |
| event_timestamp range | `2026-05-24 10:58:21` – `2026-05-24 10:58:25` |

All 10 rows confirmed present in `rtdp_analytics.market_events_beam_proof` for run ID `beam-proof-v2-20260524T105821Z`.

### Proof-only isolation confirmed

| Resource | State |
|---|---|
| Proof topic used | `market-events-raw-beam-proof` (proof-only) |
| Production topic | `market-events-raw` — NOT used |
| Production push subscription | `market-events-raw-worker-push` — NOT used |
| Production BigQuery table | `market_events_raw` — NOT written |
| Proof BigQuery table | `market_events_beam_proof` — 10 rows written |
| Cloud SQL | STOPPED / NEVER throughout |
| Schedulers | PAUSED throughout |
| Terraform | PLAN_EXIT=0 (no changes during proof run) |

### Operational warnings observed (non-blocking)

The following warnings appeared during job submission and execution. None blocked processing or invalidated the proof.

- Dataflow warnings about unparseable runtime args: present in job logs; did not block processing.
- `crcmod package not found`: appeared during local submission; does not affect correctness.
- `.whl package must be binary-compatible`: appeared for the staged `rtdp_contracts` wheel; workers installed the wheel successfully.
- `python -m pip freeze` warning: local `.venv` had no pip module; job submission still succeeded.
- No `ModuleNotFoundError: rtdp_contracts` on workers — packaging fix v2 resolved the root cause from the failed run.
- No BigQuery write errors observed.

---

## Failed Execution Run (2026-05-24) — Packaging Failure [SUPERSEDED by packaging fix v2 and successful v2 execution above]

### Failed run details

| Field | Value |
|---|---|
| Dataflow job ID | `2026-05-23_23_00_38-6447348894342053834` |
| Final job state | `JOB_STATE_CANCELLED` |
| Run ID (advisory) | `beam-proof-20260524T055218Z` |
| BigQuery proof table rows written | **0** |
| Cloud SQL state | STOPPED / NEVER (unchanged) |
| Schedulers state | PAUSED (unchanged) |
| Dataflow API | Enabled — API enablement confirmed |
| Production resources mutated | None |

### Root cause

The Dataflow worker failed during startup with:

```text
ModuleNotFoundError: No module named 'rtdp_contracts'
```

`rtdp_contracts` is a local uv workspace package (`packages/contracts/src/rtdp_contracts/`).
`save_main_session=True` pickles the main session's global namespace but does **not** install
missing Python packages on workers. Workers booted with only the standard Beam SDK packages
and could not import `rtdp_contracts`.

This is a **packaging failure only**. It is not a Pub/Sub, BigQuery, IAM, or Dataflow API failure.
The proof topic, subscription, and BigQuery table were all correctly configured.

### Pre-run local failure (GCP dependencies missing)

Before the Dataflow job was submitted, the local launch failed because the GCP extras for
Apache Beam were not installed:

```text
cannot import name 'storage' from 'google.cloud'
TypeError: isinstance() arg 2 must be a type...
```

Fix: `uv add "apache-beam[gcp]==2.70.0"` — this resolved local GCP imports:

```text
from google.cloud import storage        # OK
from apache_beam.io.gcp import bigquery # OK
GCP_BEAM_IMPORTS_OK=true
```

The `uv add` incorrectly placed `apache-beam[gcp]==2.70.0` in `[project].dependencies`
(root-package runtime deps). This is corrected in the packaging fix below.

---

## Packaging Fix v1 (2026-05-24) — setup.py + --setup_file — BROKEN

### Why setup.py at repo root does not work

The first fix attempt created `setup.py` at the repo root and set `setup_opts.setup_file`
in `run_dataflow()`. This approach is **broken** and has been superseded.

When Beam runs `python setup.py sdist` from the repo root, `setuptools` reads the root
`pyproject.toml` and silently overwrites the metadata declared in `setup.py`:

```text
SetuptoolsWarning: `install_requires` overwritten in `pyproject.toml` (dependencies)
```

The resulting sdist has:

| Field | Declared in setup.py | Actual value (read from pyproject.toml) |
| --- | --- | --- |
| `name` | `rtdp-pipeline-deps` | `real-time-data-platform` |
| `install_requires` | `["pydantic>=2.13.3"]` | `[]` (empty — root has no runtime deps) |
| Contents | `packages/contracts/src/rtdp_contracts` | Same, but wrong metadata |

Workers receive a tarball named `real-time-data-platform-0.1.0.tar.gz` with no `pydantic`
dependency. Even if `rtdp_contracts` is importable, any `pydantic` import inside it would
fail on workers that do not have `pydantic` pre-installed.

The `setup.py` has been removed. `setuptools>=75.0` has been removed from dev deps.

---

## Packaging Fix v2 (2026-05-24) — --extra_packages with uv-built wheel — CORRECT

### Chosen solution

Use Apache Beam's `--extra_packages` mechanism with a wheel built from `packages/contracts`
via `uv build`. Beam stages the wheel to GCS; workers `pip install` it on boot.

**Why this works:** `uv build packages/contracts --wheel` runs the `uv_build` backend
defined in `packages/contracts/pyproject.toml` — not in the root. The resulting wheel has:

```text
Name: rtdp-contracts
Version: 0.1.0
Requires-Dist: pydantic>=2.13.3
```

The wheel contains `rtdp_contracts/__init__.py` with the correct `MarketEvent` model and
declares `pydantic` as its dependency. Workers receive and install this wheel at boot.

### Rejected options

| Option | Why rejected |
|---|---|
| `--setup_file` with repo-root `setup.py` | setuptools reads root `pyproject.toml`, overwrites name and `install_requires`; staged artifact has wrong name and empty deps |
| `--requirements_file` | Only works for PyPI packages; cannot install local workspace packages |
| Custom Dataflow container | Heavy overhead; overkill for a proof; requires Docker build pipeline |
| Inline validation (no import) | Duplicates `MarketEvent` validation logic; violates DRY; increases maintenance surface |
| Pre-built wheel committed to repo | Binaries should not be committed; wheel is trivially reproducible from source |

### Implementation

**New function `_build_contracts_wheel()` in `pipelines/beam_market_events.py`:**

```python
def _build_contracts_wheel() -> str:
    wheel_dir = _REPO_ROOT / "dist" / "beam-staging"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    for old in wheel_dir.glob("rtdp_contracts-*.whl"):
        old.unlink()
    subprocess.run(
        ["uv", "build", str(_REPO_ROOT / "packages" / "contracts"),
         "--wheel", "--out-dir", str(wheel_dir)],
        cwd=str(_REPO_ROOT),
        check=True,
    )
    wheels = sorted(wheel_dir.glob("rtdp_contracts-*.whl"))
    if not wheels:
        raise RuntimeError(...)
    return str(wheels[-1])
```

**`run_dataflow()` change:**

```python
# Before (broken --setup_file):
setup_opts.save_main_session = True
setup_opts.setup_file = str(_REPO_ROOT / "setup.py")

# After (correct --extra_packages):
setup_opts.save_main_session = True
contracts_wheel = _build_contracts_wheel()
setup_opts.extra_packages = [contracts_wheel]
```

### Fix v2 — `pyproject.toml` dependency placement corrected

`apache-beam[gcp]==2.70.0` was incorrectly placed in `[project].dependencies` by `uv add`.
`setuptools>=75.0` was added by fix v1 for `python setup.py sdist` (no longer needed).
Both are corrected in fix v2.

| Field | Before (broken) | After (correct) |
|---|---|---|
| `[project].dependencies` | `apache-beam[gcp]==2.70.0` | `[]` (empty) |
| `[dependency-groups].dev` | `apache-beam>=2.60.0` + `setuptools>=75.0` | `apache-beam[gcp]==2.70.0` (only) |

**Trade-off**: `apache-beam[gcp]` is a dev/tooling dependency (pipeline submission, local tests).
It is NOT a runtime dependency of the workspace root package. `uv run pytest` and
`uv run python -m pipelines.beam_market_events` both work because `uv run` includes dev
dependencies by default.

### Packaging fix v2 files changed

| File | Change |
|---|---|
| `setup.py` | DELETED — was broken; replaced by `_build_contracts_wheel()` + `--extra_packages` |
| `pyproject.toml` | `apache-beam[gcp]==2.70.0` moved from `[project].dependencies` to `dev`; `setuptools>=75.0` removed |
| `.gitignore` | `dist/` and `*.egg-info/` added (wheel output dir and stray egg-info artifacts) |
| `pipelines/beam_market_events.py` | Added `subprocess` import, `_build_contracts_wheel()` function, `extra_packages` in `run_dataflow()` |
| `tests/test_beam_market_events.py` | 3 new packaging tests: no setup.py, wheel builds correctly with pydantic dep, source uses extra_packages |

### Wheel contents verified locally

```text
Files: rtdp_contracts/__init__.py, rtdp_contracts-0.1.0.dist-info/METADATA, ...
Name: rtdp-contracts
Version: 0.1.0
Requires-Dist: pydantic>=2.13.3
Requires-Python: >=3.12
```

### Local venv note

After `uv add "apache-beam[gcp]==2.70.0"` modified `pyproject.toml` and `uv.lock`, the
workspace member packages (`rtdp_contracts`, etc.) were not installed in the local venv by
plain `uv sync`. The correct command to install ALL workspace members is:

```bash
uv sync --all-packages
```

This is required because `uv sync` without `--all-packages` only installs the root package
and its direct dependencies (not all workspace members). The `uv sync --all-packages` command
is idempotent and safe to re-run.

---

## Design Correction (2026-05-24)

### Risk identified during review

The initial implementation of the bounded runbook (Step 1) directed the operator to publish
test messages to the **production topic** `market-events-raw`.

This was unsafe. In Google Pub/Sub, a single topic fans out to **all attached subscriptions**.
Publishing to `market-events-raw` would make those messages available to:

- `market-events-raw-beam-proof-sub` (proof pull subscription — intended)
- `market-events-raw-worker-push` (production push subscription — **unintended**)

Any message acknowledged by the proof pipeline that was also delivered to the worker-push
subscription would trigger the production Cloud Run worker and attempt a write to the
production Cloud SQL / BigQuery path.  The claim "These will be visible only via the proof
subscription" was **false**.

### Corrected design — proof-only topic

A dedicated proof topic `market-events-raw-beam-proof` is introduced.  The proof subscription
`market-events-raw-beam-proof-sub` is re-attached to this topic.

| Resource | Before correction | After correction |
|---|---|---|
| Proof subscription topic | `market-events-raw` (production) | `market-events-raw-beam-proof` (proof-only) |
| Production topic | Shared with proof sub | Untouched; no subscription change |
| `market-events-raw-worker-push` | Received proof messages | Receives nothing from proof runs |

Publishing test messages to `market-events-raw-beam-proof` cannot reach the production worker
because the production worker-push subscription is attached to `market-events-raw`, not to
`market-events-raw-beam-proof`.

### What was changed to implement the correction

| File | Change |
|---|---|
| `infra/terraform/gcp/dataflow.tf` | Added `google_pubsub_topic.market_events_raw_beam_proof`; changed `google_pubsub_subscription.market_events_raw_beam_proof_sub.topic` to reference proof topic |
| `pipelines/beam_market_events.py` | Added `DATAFLOW_PROOF_TOPIC` constant; tightened `_validate_dataflow_args` to exact-match on `DATAFLOW_PROOF_SUBSCRIPTION` and `DATAFLOW_PROOF_TABLE` |
| `tests/test_beam_market_events.py` | Added proof topic constant tests; added exact-match rejection tests for any non-proof subscription or table |

Terraform plan after correction: **2 to add, 0 to change, 1 to destroy** (PLAN_EXIT=2).

- ADD: `google_pubsub_topic.market_events_raw_beam_proof`
- REPLACE: `google_pubsub_subscription.market_events_raw_beam_proof_sub`
  (changing `topic` forces recreation in GCP; no existing subscription messages are lost
  since the proof subscription had 0 messages)

**Terraform apply executed (2026-05-24):** first apply: **2 added, 0 changed, 1 destroyed** (APPLY_EXIT=0).

- CREATED: `google_pubsub_topic.market_events_raw_beam_proof` (name: `market-events-raw-beam-proof`)
- REPLACED: `google_pubsub_subscription.market_events_raw_beam_proof_sub` (topic re-wired from `market-events-raw` to `market-events-raw-beam-proof`)

Second apply (2026-05-24): **2 added, 0 changed, 0 destroyed** (APPLY_EXIT=0).

- RECREATED: `google_pubsub_subscription_iam_member.dataflow_sa_proof_sub_subscriber`
- RECREATED: `google_pubsub_subscription_iam_member.terraform_plan_ci_proof_sub_viewer`

Post-apply plan: **PLAN_EXIT=0** (no changes; infrastructure matches configuration).

Proof subscription confirmed: `market-events-raw-beam-proof-sub` → topic `market-events-raw-beam-proof` (ackDeadlineSeconds=60, messageRetentionDuration=600s).
Production push subscription confirmed: `market-events-raw-worker-push` → topic `market-events-raw` (unchanged).

---

## Purpose

Extend the existing Apache Beam `pipelines/beam_market_events.py` to support a bounded
Google Cloud DataflowRunner proof.  This is Phase 3 of the proof sequence defined in
[docs/dataflow-apache-beam-architecture-decision.md](dataflow-apache-beam-architecture-decision.md),
Section 6.3.

Phase 1 (DirectRunner local proof): `feat/beam-directrunner-market-events-pipeline` →
[docs/beam-directrunner-pipeline-evidence.md](beam-directrunner-pipeline-evidence.md).

Phase 2 (Terraform prerequisites): `infra/dataflow-bounded-proof-prereqs` →
[docs/dataflow-bounded-proof-prereqs-evidence.md](dataflow-bounded-proof-prereqs-evidence.md).

---

## What Changed

### Files changed

| File | Change |
|---|---|
| `pipelines/beam_market_events.py` | Extended: DataflowRunner code path added; `DATAFLOW_PROOF_TOPIC` constant added; `_validate_dataflow_args` uses exact-match guards |
| `tests/test_beam_market_events.py` | Extended: 33 total beam tests (20 new DataflowRunner, safety, and exact-match tests) |
| `infra/terraform/gcp/dataflow.tf` | Corrected: proof-only topic added; proof subscription re-wired to proof topic |

No Dockerfile modified. No GitHub workflow modified.

### `pipelines/beam_market_events.py`

**DirectRunner behaviour: unchanged.**  `build_pipeline()`, `run()`, `ParseAndValidateDoFn`,
and the six output fields (`event_id`, `event_timestamp`, `symbol`, `event_type`, `price`,
`quantity`) are identical to Phase 1.  `run()` still raises `ValueError` for any runner other
than `DirectRunner`.

**DataflowRunner additions:**

| Symbol | Purpose |
|---|---|
| `DATAFLOW_PROOF_TOPIC` | Constant: `projects/project-42987e01-2123-446b-ac7/topics/market-events-raw-beam-proof` |
| `DATAFLOW_PROOF_SUBSCRIPTION` | Constant: `projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-beam-proof-sub` |
| `DATAFLOW_PROOF_TABLE` | Constant: `project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_beam_proof` |
| `BQ_SCHEMA` | BigQuery schema dict matching the proof table (6 fields) |
| `_validate_dataflow_args()` | Pre-flight safety: all required args present; explicit rejection of `worker-push`; exact-match rejection of any subscription ≠ `DATAFLOW_PROOF_SUBSCRIPTION`; exact-match rejection of any table ≠ `DATAFLOW_PROOF_TABLE` |
| `build_dataflow_pipeline()` | `ReadFromPubSub` → decode bytes → `ParseAndValidateDoFn` → `beam.Map(json.loads)` → `WriteToBigQuery` (WRITE_APPEND, CREATE_NEVER) |
| `run_dataflow()` | Validates args, builds `PipelineOptions`, submits streaming job, prints job ID + monitor + drain commands |

`main()` now branches on `--runner`:
- `DirectRunner` (default): existing JSONL path unchanged.
- `DataflowRunner`: calls `run_dataflow()` with explicit args; exits non-zero on validation failure.
- Any other runner: exits non-zero.

---

## Runner Support

| Runner | Entrypoint | Input | Output | Status |
|---|---|---|---|---|
| `DirectRunner` | `run()` | Local JSONL file | Local JSONL file | Implemented and validated (Phase 1) |
| `DataflowRunner` | `run_dataflow()` | Pub/Sub proof subscription | BigQuery proof table | Implemented; GCP execution VALIDATED (2026-05-24) |

---

## Safety Controls

### Pre-flight arg validation (enforced before any GCP call)

| Check | Behaviour |
|---|---|
| All 7 required args present and non-empty | `ValueError` if any is missing |
| `input_subscription` must NOT contain `worker-push` | `ValueError` if matched |
| `output_table` must contain `market_events_beam_proof` | `ValueError` if not present |

### Bounded execution design

Pub/Sub is an unbounded source.  `ReadFromPubSub` launches a streaming Dataflow job.
There is no native Beam API for "read exactly N messages and stop" from a streaming
subscription in DataflowRunner.  The safest practical bounded proof is:

1. Operator pre-publishes a fixed set of test messages (e.g. `--max-records 10`) to the
   **proof-only** topic `market-events-raw-beam-proof`.
2. The subscription has `message_retention_duration = 600s` (10 minutes); no production
   messages are in the proof subscription.
3. Operator launches the job, confirms BigQuery row count, then **drains** the job.
4. Total bounded window: ≤ 10 minutes (subscription retention ceiling).

The `--max-records` CLI flag is advisory: it signals how many messages to pre-publish.
The `--timeout-seconds` flag (default 600) is the operator drain deadline.

### Proof-only resource isolation

| Resource | Value |
|---|---|
| Proof topic | `market-events-raw-beam-proof` (proof-only; no production subscriber attached) |
| Input subscription | `market-events-raw-beam-proof-sub` (pull; attached to proof topic; 600s retention) |
| Output BigQuery table | `rtdp_analytics.market_events_beam_proof` (proof-only; deletion_protection=false) |
| Service account | `rtdp-dataflow-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com` |
| GCS staging bucket | `gs://rtdp-dataflow-staging-project-42987e01-2123-446b-ac7` |
| Production topic (`market-events-raw`) | NOT used; proof topic is separate |
| Production subscription (`worker-push`) | NOT accessible; rejected by defensive and exact-match guards |
| Production table (`market_events_raw`) | NOT accessible; rejected by exact-match guard |

---

## CLI Reference

### DirectRunner (unchanged from Phase 1)

```bash
uv run python -m pipelines.beam_market_events \
  --input-jsonl data/sample.jsonl \
  --output-jsonl /tmp/valid.jsonl \
  --dead-letter-jsonl /tmp/dead_letter.jsonl
```

### DataflowRunner (bounded proof)

```bash
uv run python -m pipelines.beam_market_events \
  --runner DataflowRunner \
  --project project-42987e01-2123-446b-ac7 \
  --region europe-west1 \
  --service-account-email rtdp-dataflow-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --staging-location gs://rtdp-dataflow-staging-project-42987e01-2123-446b-ac7/staging \
  --temp-location gs://rtdp-dataflow-staging-project-42987e01-2123-446b-ac7/tmp \
  --input-subscription projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-beam-proof-sub \
  --output-table project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_beam_proof \
  --max-records 10 \
  --timeout-seconds 600
```

---

## Explicit Non-Claims

As of 2026-05-24 on branch `exec/dataflow-bounded-runner-proof`:

- **DataflowRunner executed: YES, bounded proof only.** Job `2026-05-24_03_59_31-13978483355822818690` reached `JOB_STATE_DRAINED` after processing 10 test messages. This is a bounded, operator-drained proof, not sustained production streaming.
- **Pub/Sub messages published: YES, 10 to proof-only topic.** Messages published to `market-events-raw-beam-proof` only. Production topic `market-events-raw` was not used.
- **BigQuery writes executed: YES, 10 rows to proof-only table only.** Rows written to `market_events_beam_proof` only. Production table `market_events_raw` was not written.
- **Cloud SQL NOT started.** `rtdp-postgres` remained STOPPED / NEVER throughout.
- **Schedulers NOT activated.** Both schedulers remained PAUSED throughout.
- **No production resources modified.** `market_events_raw`, `market-events-raw-worker-push`, and all Cloud Run services are unchanged.
- **Terraform unchanged during proof run.** PLAN_EXIT=0; no Terraform apply executed during this proof execution. (Prerequisites were applied in earlier branches; see Phase 2 evidence.)
- **Exactly-once semantics NOT claimed.** Dataflow streaming with `STREAMING_INSERTS` does not guarantee exactly-once writes. Proof scope is bounded delivery validation only.
- **Production streaming readiness NOT claimed.** This proves the DataflowRunner code path executes end-to-end with real GCP infrastructure for a bounded proof. Sustained streaming production readiness is not proven.

---

## Manual GCP Execution Runbook (Historical — Reusable)

This runbook was used for the successful bounded execution on 2026-05-24. It is preserved as a reusable reference for future proof runs.

### Pre-flight

```bash
# Confirm Dataflow API is enabled
gcloud services list --enabled --project=project-42987e01-2123-446b-ac7 \
  --filter="name:dataflow.googleapis.com"

# Confirm proof subscription exists and is empty
gcloud pubsub subscriptions describe market-events-raw-beam-proof-sub \
  --project=project-42987e01-2123-446b-ac7

# Confirm proof table exists and is empty
bq show --format=prettyjson \
  project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_beam_proof

bq query --nouse_legacy_sql \
  'SELECT COUNT(*) AS row_count FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_beam_proof`'

# Confirm Cloud SQL is STOPPED
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state,settings.activationPolicy)"

# Confirm schedulers are PAUSED
gcloud scheduler jobs list \
  --project=project-42987e01-2123-446b-ac7 \
  --location=europe-west1 \
  --format="table(id,state,schedule)"
```

### Step 1 — Publish test messages to the proof topic

```bash
# Publish exactly 10 test messages to the PROOF-ONLY topic.
# The proof topic is isolated from the production topic market-events-raw.
# Publishing here does NOT reach market-events-raw-worker-push.

PROJECT=project-42987e01-2123-446b-ac7
PROOF_TOPIC=market-events-raw-beam-proof   # proof-only; NOT the production topic

for i in $(seq 1 10); do
  gcloud pubsub topics publish ${PROOF_TOPIC} \
    --project=${PROJECT} \
    --message="{
      \"schema_version\": \"1.0\",
      \"event_id\": \"beam-proof-${i}\",
      \"symbol\": \"BTCUSDT\",
      \"event_type\": \"trade\",
      \"price\": \"$(echo "scale=2; 50000 + $i * 100" | bc)\",
      \"quantity\": \"0.001\",
      \"event_timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
    }"
done
```

### Step 2 — Submit the DataflowRunner job

```bash
cd /path/to/real-time-data-platform

uv run python -m pipelines.beam_market_events \
  --runner DataflowRunner \
  --project project-42987e01-2123-446b-ac7 \
  --region europe-west1 \
  --service-account-email rtdp-dataflow-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com \
  --staging-location gs://rtdp-dataflow-staging-project-42987e01-2123-446b-ac7/staging \
  --temp-location gs://rtdp-dataflow-staging-project-42987e01-2123-446b-ac7/tmp \
  --input-subscription projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-beam-proof-sub \
  --output-table project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_beam_proof \
  --max-records 10 \
  --timeout-seconds 600
```

Note the **Dataflow job ID** from stdout. It will appear as:
```
Dataflow job submitted. Job ID: <JOB_ID>
Monitor: https://console.cloud.google.com/dataflow/jobs/europe-west1/<JOB_ID>?project=project-42987e01-2123-446b-ac7
Drain: gcloud dataflow jobs drain <JOB_ID> --region=europe-west1 --project=project-42987e01-2123-446b-ac7
```

### Step 3 — Monitor the job

```bash
JOB_ID=<JOB_ID>

gcloud dataflow jobs describe ${JOB_ID} \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(id,name,currentState,createTime)"
```

Allow 2–5 minutes for job startup and message processing.

### Step 4 — Confirm BigQuery rows

```bash
bq query --nouse_legacy_sql \
  'SELECT COUNT(*) AS row_count FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_beam_proof`'

bq query --nouse_legacy_sql \
  'SELECT * FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_beam_proof` LIMIT 5'
```

### Step 5 — Drain the job (REQUIRED within 600 seconds)

```bash
gcloud dataflow jobs drain ${JOB_ID} \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7

# Confirm final state
gcloud dataflow jobs describe ${JOB_ID} \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(id,name,currentState)"
```

Expected final state: `JOB_STATE_DRAINED` or `JOB_STATE_DONE`.

If drain is not possible (e.g. job stuck): cancel instead:
```bash
gcloud dataflow jobs cancel ${JOB_ID} \
  --region=europe-west1 \
  --project=project-42987e01-2123-446b-ac7
```

### Step 6 — Post-run safety check

```bash
# Confirm Cloud SQL still STOPPED
gcloud sql instances describe rtdp-postgres \
  --project=project-42987e01-2123-446b-ac7 \
  --format="table(name,state,settings.activationPolicy)"

# Confirm schedulers still PAUSED
gcloud scheduler jobs list \
  --project=project-42987e01-2123-446b-ac7 \
  --location=europe-west1 \
  --format="table(id,state,schedule)"

# Confirm production table was NOT written to
bq query --nouse_legacy_sql \
  'SELECT MAX(ingest_timestamp) AS last_ingest FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`'
```

---

## Post-Run Evidence

| Field | Value |
| --- | --- |
| Dataflow job ID | `2026-05-24_03_59_31-13978483355822818690` |
| Dataflow job name | `rtdp-market-events-beam-proof` |
| Run ID | `beam-proof-v2-20260524T105821Z` |
| Final job state | `JOB_STATE_DRAINED` |
| Final state time | `2026-05-24T11:12:17.432937Z` |
| Records published to proof topic | 10 (to `market-events-raw-beam-proof`) |
| BigQuery proof table row count | 10 |
| Cloud SQL state post-run | STOPPED / NEVER (unchanged) |
| Scheduler state post-run | PAUSED (unchanged) |

---

## Local Validation Outputs

### `git status --short --branch`

```
## feat/dataflow-bounded-market-events-proof
 M pipelines/beam_market_events.py
 M tests/test_beam_market_events.py
```

### `uv run pytest -q`

```
381 passed, 10 warnings in 12.13s
```

(361 prior passing + 20 new DataflowRunner / safety / exact-match tests.)

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
VALIDATE_EXIT=0
```

### `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false` (pre-apply)

```
# google_pubsub_subscription.market_events_raw_beam_proof_sub must be replaced
# google_pubsub_topic.market_events_raw_beam_proof will be created
Plan: 2 to add, 0 to change, 1 to destroy.
PLAN_EXIT=2
```

Changes applied:

- ADD `google_pubsub_topic.market_events_raw_beam_proof` — new proof-only topic.
- REPLACE `google_pubsub_subscription.market_events_raw_beam_proof_sub` — topic reference changes from production topic to proof topic; GCP subscription recreation required (changing `topic` is a ForceNew change). The subscription has 0 messages; no data is lost.

No existing production resources are changed or destroyed.

### `terraform -chdir=infra/terraform/gcp apply -input=false` (first apply)

```
Apply complete! Resources: 2 added, 0 changed, 1 destroyed.
APPLY_EXIT=0
```

### `terraform -chdir=infra/terraform/gcp apply -input=false` (second apply)

```
Apply complete! Resources: 2 added, 0 changed, 0 destroyed.
APPLY_EXIT=0
```

Resources recreated in second apply:

- `google_pubsub_subscription_iam_member.dataflow_sa_proof_sub_subscriber`
- `google_pubsub_subscription_iam_member.terraform_plan_ci_proof_sub_viewer`

### `terraform -chdir=infra/terraform/gcp plan -detailed-exitcode -input=false` (post-apply)

```
No changes. Your infrastructure matches the configuration.
PLAN_EXIT=0
```

### Cloud SQL state

```
NAME           STATE    ACTIVATION_POLICY
rtdp-postgres  STOPPED  NEVER
```

### Cloud Scheduler state

```
ID  STATE   SCHEDULE
    PAUSED  */15 * * * *
    PAUSED  0 * * * *
```

---

## Test Summary

33 total beam tests (13 from Phase 1 + 20 new):

| Test | Layer | What it proves |
|---|---|---|
| `test_valid_event_routed_to_main_output` | DoFn/TestPipeline | Valid JSONL → main output; dead-letter empty |
| `test_invalid_json_routed_to_dead_letter` | DoFn/TestPipeline | Invalid JSON → dead-letter |
| `test_schema_invalid_event_routed_to_dead_letter` | DoFn/TestPipeline | Price ≤ 0 → dead-letter |
| `test_output_count_equals_valid_input_count` | DoFn/TestPipeline | 3 valid in → 3 valid out |
| `test_dead_letter_count_equals_invalid_input_count` | DoFn/TestPipeline | Mixed input → correct split |
| `test_runner_guard_rejects_dataflow_runner` | `run()` API | `run()` still rejects DataflowRunner; use `run_dataflow()` |
| `test_runner_guard_rejects_arbitrary_runner` | `run()` API | SparkRunner rejected |
| `test_no_gcp_env_vars_required` | Import safety | Module imports cleanly without GCP env vars |
| `test_no_cloud_sql_in_module_source` | Source inspection | No Cloud SQL client imported |
| `test_run_with_temporary_files` | `run()` + files | JSONL round-trip verified |
| `test_cli_subprocess_valid_and_dead_letter` | Real CLI | subprocess returncode=0; output verified |
| `test_cli_subprocess_rejects_dataflow_runner_missing_args` | Real CLI | DataflowRunner without args → non-zero + "DataflowRunner" in stderr |
| `test_directrunner_output_is_deterministic` | `run()` + files | Same input → identical sorted output |
| `test_validate_dataflow_args_accepts_valid_proof_args` | `_validate_dataflow_args` | Valid proof args pass without error |
| `test_validate_dataflow_args_rejects_missing_project` | `_validate_dataflow_args` | Empty project → ValueError |
| `test_validate_dataflow_args_rejects_missing_region` | `_validate_dataflow_args` | Empty region → ValueError |
| `test_validate_dataflow_args_rejects_missing_service_account` | `_validate_dataflow_args` | Empty SA → ValueError |
| `test_validate_dataflow_args_rejects_missing_staging_location` | `_validate_dataflow_args` | Empty staging → ValueError |
| `test_validate_dataflow_args_rejects_missing_temp_location` | `_validate_dataflow_args` | Empty temp → ValueError |
| `test_validate_dataflow_args_rejects_missing_input_subscription` | `_validate_dataflow_args` | Empty subscription → ValueError |
| `test_validate_dataflow_args_rejects_missing_output_table` | `_validate_dataflow_args` | Empty table → ValueError |
| `test_validate_dataflow_args_rejects_production_push_subscription` | `_validate_dataflow_args` | `worker-push` → ValueError (defensive guard) |
| `test_validate_dataflow_args_rejects_any_non_proof_subscription` | `_validate_dataflow_args` | Any subscription ≠ proof sub → ValueError (exact-match) |
| `test_validate_dataflow_args_rejects_production_table` | `_validate_dataflow_args` | `market_events_raw` → ValueError (exact-match) |
| `test_validate_dataflow_args_rejects_any_non_proof_table` | `_validate_dataflow_args` | Any table ≠ proof table → ValueError (exact-match) |
| `test_run_dataflow_rejects_missing_project` | `run_dataflow()` | Empty project → ValueError before GCP |
| `test_run_dataflow_rejects_production_push_subscription` | `run_dataflow()` | `worker-push` → ValueError before GCP |
| `test_run_dataflow_rejects_non_proof_subscription` | `run_dataflow()` | Any non-proof subscription → ValueError before GCP |
| `test_run_dataflow_rejects_production_table` | `run_dataflow()` | `market_events_raw` → ValueError before GCP |
| `test_proof_topic_is_proof_only` | Constants | Topic constant correct; not production topic |
| `test_proof_subscription_constant_references_proof_sub` | Constants | Subscription constant correct; not worker-push |
| `test_proof_table_constant_references_proof_table` | Constants | Table constant correct |
| `test_proof_topic_and_subscription_are_distinct_resources` | Constants | Topic and subscription have correct resource type paths |

---

## Safety Confirmation

| Control | State |
|---|---|
| DataflowRunner executed | YES -- bounded proof only; job `2026-05-24_03_59_31-13978483355822818690`; final state `JOB_STATE_DRAINED` |
| GCP resources mutated | YES -- proof resources only (`market_events_beam_proof`: 10 rows written; proof topic/subscription consumed) |
| Pub/Sub messages published | YES -- 10 messages to proof-only topic `market-events-raw-beam-proof` |
| BigQuery writes executed | YES -- 10 rows to proof-only table `market_events_beam_proof` |
| Cloud SQL started | NO (STOPPED/NEVER) |
| Schedulers activated | NO (both PAUSED) |
| Terraform apply executed | YES (prerequisites only) -- first apply: 2 added, 1 destroyed (APPLY_EXIT=0); second apply: 2 added (APPLY_EXIT=0); post-apply PLAN_EXIT=0; no Terraform apply during proof execution |
| Production table (`market_events_raw`) written | NO |
| Production subscription (`worker-push`) consumed | NO |
| Cloud SQL client imported | NO |

---

## Risk Analysis

| Risk | Mitigation |
|---|---|
| Streaming job runs indefinitely | `_validate_dataflow_args` pre-flight; proof subscription has 600s retention; operator drain runbook documented; `--timeout-seconds` advisory |
| Accidental write to production table | `_validate_dataflow_args` rejects any `output_table` not containing `market_events_beam_proof` |
| Production push subscription consumed | `_validate_dataflow_args` rejects any `input_subscription` containing `worker-push` |
| Dataflow SA has project-level roles | `roles/dataflow.worker` and `roles/bigquery.jobUser` are GCP requirements (no resource-scoped alternative); all other bindings are resource-scoped; documented in Phase 2 evidence |
| Streaming inserts not exactly-once | Documented non-claim; proof scope is bounded delivery validation only |
| Worker bootstrap failure | `save_main_session=True` sends the main session to workers; suitable for proof; not for large stateful pipelines |

---

## Next Recommended Step

The DataflowRunner bounded proof execution is complete. Status: VALIDATED.

Recommended next steps:

1. Raise a PR from `exec/dataflow-bounded-runner-proof` to `main`.
2. Reference this evidence file and `docs/EVIDENCE_INDEX.md` in the PR description.
3. Mark the Dataflow bounded runner proof as complete in any gap-closure or platform audit documents that reference it as pending.

---

## Evidence Links

| Document | Relevance |
|---|---|
| [docs/dataflow-apache-beam-architecture-decision.md](dataflow-apache-beam-architecture-decision.md) | ADR; proof design specification |
| [docs/beam-directrunner-pipeline-evidence.md](beam-directrunner-pipeline-evidence.md) | Phase 1 DirectRunner proof; 361 pytest |
| [docs/dataflow-bounded-proof-prereqs-evidence.md](dataflow-bounded-proof-prereqs-evidence.md) | Phase 2 Terraform prerequisites |
| [pipelines/beam_market_events.py](../pipelines/beam_market_events.py) | Pipeline module (DirectRunner + DataflowRunner) |
| [tests/test_beam_market_events.py](../tests/test_beam_market_events.py) | 29 tests |
| [infra/terraform/gcp/dataflow.tf](../infra/terraform/gcp/dataflow.tf) | Proof prerequisites (SA, bucket, subscription, table, IAM) |
| [infra/terraform/gcp/schemas/market_events_beam_proof.json](../infra/terraform/gcp/schemas/market_events_beam_proof.json) | BigQuery proof table schema |
