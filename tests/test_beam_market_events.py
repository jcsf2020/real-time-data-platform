"""Tests for the Apache Beam MarketEvent pipeline (DirectRunner and DataflowRunner modes)."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import apache_beam as beam
import pytest
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that, equal_to

from pipelines.beam_market_events import (
    DATAFLOW_PROOF_SUBSCRIPTION,
    DATAFLOW_PROOF_TABLE,
    DATAFLOW_PROOF_TOPIC,
    DEAD_LETTER_TAG,
    ParseAndValidateDoFn,
    _validate_dataflow_args,
    run,
    run_dataflow,
)


# --- fixtures and helpers ---


def _valid_event_dict(idx: int = 1) -> dict:
    return {
        "schema_version": "1.0",
        "event_id": f"evt-{idx}",
        "symbol": "BTCUSDT",
        "event_type": "trade",
        "price": "100.50",
        "quantity": "0.25",
        "event_timestamp": "2026-01-01T00:00:00+00:00",
    }


def _valid_event_jsonl(idx: int = 1) -> str:
    return json.dumps(_valid_event_dict(idx))


def _normalized_event_dict(idx: int = 1) -> dict:
    return {
        "event_id": f"evt-{idx}",
        "event_timestamp": "2026-01-01T00:00:00+00:00",
        "event_type": "trade",
        "price": "100.50",
        "quantity": "0.25",
        "symbol": "BTCUSDT",
    }


# --- DoFn unit tests via TestPipeline ---


def test_valid_event_routed_to_main_output() -> None:
    with TestPipeline() as p:
        results = (
            p
            | beam.Create([_valid_event_jsonl(1)])
            | beam.ParDo(ParseAndValidateDoFn()).with_outputs(DEAD_LETTER_TAG, main="valid")
        )
        assert_that(
            results["valid"] | "ParseValid" >> beam.Map(json.loads),
            equal_to([_normalized_event_dict(1)]),
            label="check_valid",
        )
        assert_that(results[DEAD_LETTER_TAG], equal_to([]), label="check_dl_empty")


def test_invalid_json_routed_to_dead_letter() -> None:
    bad = "this is not json {"
    with TestPipeline() as p:
        results = (
            p
            | beam.Create([bad])
            | beam.ParDo(ParseAndValidateDoFn()).with_outputs(DEAD_LETTER_TAG, main="valid")
        )
        assert_that(results["valid"], equal_to([]), label="check_valid_empty")
        assert_that(results[DEAD_LETTER_TAG], equal_to([bad]), label="check_dl")


def test_schema_invalid_event_routed_to_dead_letter() -> None:
    bad_event = {
        "schema_version": "1.0",
        "event_id": "evt-x",
        "symbol": "BTCUSDT",
        "event_type": "trade",
        "price": "-1",
        "quantity": "0.25",
        "event_timestamp": "2026-01-01T00:00:00+00:00",
    }
    bad_json = json.dumps(bad_event)
    with TestPipeline() as p:
        results = (
            p
            | beam.Create([bad_json])
            | beam.ParDo(ParseAndValidateDoFn()).with_outputs(DEAD_LETTER_TAG, main="valid")
        )
        assert_that(results["valid"], equal_to([]), label="check_valid_empty")
        assert_that(results[DEAD_LETTER_TAG], equal_to([bad_json]), label="check_dl")


def test_output_count_equals_valid_input_count() -> None:
    inputs = [_valid_event_jsonl(i) for i in range(1, 4)]
    with TestPipeline() as p:
        results = (
            p
            | beam.Create(inputs)
            | beam.ParDo(ParseAndValidateDoFn()).with_outputs(DEAD_LETTER_TAG, main="valid")
        )
        assert_that(
            results["valid"] | "ParseValid" >> beam.Map(json.loads),
            equal_to([_normalized_event_dict(i) for i in range(1, 4)]),
            label="check_valid_count",
        )
        assert_that(results[DEAD_LETTER_TAG], equal_to([]), label="check_dl_empty")


def test_dead_letter_count_equals_invalid_input_count() -> None:
    valid_inputs = [_valid_event_jsonl(i) for i in range(1, 3)]
    invalid_json = "not json {"
    invalid_schema = json.dumps(
        {
            "schema_version": "1.0",
            "event_id": "bad-evt",
            "symbol": "ETHUSDT",
            "event_type": "trade",
            "price": "-99",
            "quantity": "1.0",
            "event_timestamp": "2026-01-01T00:00:00+00:00",
        }
    )
    invalid_inputs = [invalid_json, invalid_schema]
    all_inputs = valid_inputs + invalid_inputs

    with TestPipeline() as p:
        results = (
            p
            | beam.Create(all_inputs)
            | beam.ParDo(ParseAndValidateDoFn()).with_outputs(DEAD_LETTER_TAG, main="valid")
        )
        assert_that(
            results["valid"] | "ParseValid" >> beam.Map(json.loads),
            equal_to([_normalized_event_dict(i) for i in range(1, 3)]),
            label="check_valid",
        )
        assert_that(
            results[DEAD_LETTER_TAG],
            equal_to(invalid_inputs),
            label="check_dl_count",
        )


# --- DirectRunner runner guard (unchanged behaviour) ---


def test_runner_guard_rejects_dataflow_runner() -> None:
    # run() is DirectRunner-only by design; DataflowRunner is handled by run_dataflow().
    with pytest.raises(ValueError, match="DataflowRunner"):
        run(
            input_path="/dev/null",
            output_path="/tmp/out_test",
            dead_letter_path="/tmp/dl_test",
            runner="DataflowRunner",
        )


def test_runner_guard_rejects_arbitrary_runner() -> None:
    with pytest.raises(ValueError):
        run(
            input_path="/dev/null",
            output_path="/tmp/out_test",
            dead_letter_path="/tmp/dl_test",
            runner="SparkRunner",
        )


# --- safety: no GCP env vars or Cloud SQL clients ---


def test_no_gcp_env_vars_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in [
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GCLOUD_PROJECT",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_PROJECT_ID",
    ]:
        monkeypatch.delenv(var, raising=False)
    import pipelines.beam_market_events as m

    assert callable(m.run)
    assert callable(m.run_dataflow)
    assert callable(m.main)


def test_no_cloud_sql_in_module_source() -> None:
    import pipelines.beam_market_events as m

    source = inspect.getsource(m)
    for forbidden in [
        "google.cloud.sql",
        "sqlalchemy",
        "psycopg2",
        "asyncpg",
        "pg8000",
        "cloud_sql_connector",
    ]:
        assert forbidden not in source, f"Forbidden Cloud SQL reference in source: {forbidden}"


# --- run() integration with temporary files ---


def test_run_with_temporary_files() -> None:
    valid = _valid_event_dict(1)
    bad = "not valid json {"

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        input_path = d / "input.jsonl"
        output_path = d / "output.jsonl"
        dl_path = d / "dead_letter.jsonl"

        input_path.write_text(json.dumps(valid) + "\n" + bad + "\n")

        run(
            input_path=str(input_path),
            output_path=str(output_path),
            dead_letter_path=str(dl_path),
        )

        assert output_path.exists(), "Output file must be created"
        assert dl_path.exists(), "Dead-letter file must be created"

        valid_lines = [ln for ln in output_path.read_text().splitlines() if ln.strip()]
        dl_lines = [ln for ln in dl_path.read_text().splitlines() if ln.strip()]

        assert len(valid_lines) == 1
        assert len(dl_lines) == 1

        parsed = json.loads(valid_lines[0])
        assert parsed["event_id"] == "evt-1"
        assert parsed["symbol"] == "BTCUSDT"
        assert parsed["price"] == "100.50"
        assert parsed["quantity"] == "0.25"


# --- real CLI entrypoint via subprocess ---

_PROJECT_ROOT = Path(__file__).parent.parent


def test_cli_subprocess_valid_and_dead_letter() -> None:
    valid = _valid_event_dict(1)
    bad = "not valid json {"

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        input_path = d / "input.jsonl"
        output_path = d / "output.jsonl"
        dl_path = d / "dead_letter.jsonl"

        input_path.write_text(json.dumps(valid) + "\n" + bad + "\n")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pipelines.beam_market_events",
                "--input-jsonl",
                str(input_path),
                "--output-jsonl",
                str(output_path),
                "--dead-letter-jsonl",
                str(dl_path),
            ],
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
        )

        assert result.returncode == 0, f"CLI exited non-zero.\nstderr: {result.stderr}"
        assert output_path.exists(), "Output file must be created by CLI"
        assert dl_path.exists(), "Dead-letter file must be created by CLI"

        valid_lines = [ln for ln in output_path.read_text().splitlines() if ln.strip()]
        dl_lines = [ln for ln in dl_path.read_text().splitlines() if ln.strip()]

        assert len(valid_lines) == 1, f"Expected 1 valid line, got {len(valid_lines)}"
        assert len(dl_lines) == 1, f"Expected 1 dead-letter line, got {len(dl_lines)}"

        parsed = json.loads(valid_lines[0])
        assert parsed["event_id"] == "evt-1"
        assert parsed["symbol"] == "BTCUSDT"
        assert parsed["price"] == "100.50"
        assert parsed["quantity"] == "0.25"


def test_cli_subprocess_rejects_dataflow_runner_missing_args() -> None:
    # DataflowRunner without required Dataflow args → non-zero exit, "DataflowRunner" in stderr.
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        input_path = d / "input.jsonl"
        input_path.write_text(_valid_event_jsonl(1) + "\n")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pipelines.beam_market_events",
                "--runner",
                "DataflowRunner",
                # Deliberately omitting --project, --input-subscription, --output-table etc.
            ],
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
        )

        assert result.returncode != 0, "CLI must exit non-zero when required Dataflow args are missing"
        assert "DataflowRunner" in result.stderr, (
            f"stderr must reference DataflowRunner.\nstderr: {result.stderr}"
        )


# --- DirectRunner determinism ---


def test_directrunner_output_is_deterministic() -> None:
    events = [_valid_event_jsonl(i) for i in range(1, 6)]

    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        in_file = d / "input.jsonl"
        in_file.write_text("\n".join(events) + "\n")

        runs: list[list[str]] = []
        for i in range(2):
            out = d / f"out_{i}.jsonl"
            dl = d / f"dl_{i}.jsonl"
            run(input_path=str(in_file), output_path=str(out), dead_letter_path=str(dl))
            lines = sorted(ln for ln in out.read_text().splitlines() if ln.strip())
            runs.append(lines)

        assert len(runs[0]) == 5
        assert runs[0] == runs[1], "DirectRunner output must be deterministic across runs"


# --- _validate_dataflow_args unit tests (no GCP calls) ---

_VALID_DATAFLOW_KWARGS = dict(
    project="project-42987e01-2123-446b-ac7",
    region="europe-west1",
    service_account_email="rtdp-dataflow-sa@project-42987e01-2123-446b-ac7.iam.gserviceaccount.com",
    staging_location="gs://rtdp-dataflow-staging-project-42987e01-2123-446b-ac7/staging",
    temp_location="gs://rtdp-dataflow-staging-project-42987e01-2123-446b-ac7/tmp",
    input_subscription=DATAFLOW_PROOF_SUBSCRIPTION,
    output_table=DATAFLOW_PROOF_TABLE,
)


def test_validate_dataflow_args_accepts_valid_proof_args() -> None:
    # Must not raise for fully-specified proof args.
    _validate_dataflow_args(**_VALID_DATAFLOW_KWARGS)


def test_validate_dataflow_args_rejects_missing_project() -> None:
    args = {**_VALID_DATAFLOW_KWARGS, "project": ""}
    with pytest.raises(ValueError, match="Missing"):
        _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_missing_region() -> None:
    args = {**_VALID_DATAFLOW_KWARGS, "region": ""}
    with pytest.raises(ValueError, match="Missing"):
        _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_missing_service_account() -> None:
    args = {**_VALID_DATAFLOW_KWARGS, "service_account_email": ""}
    with pytest.raises(ValueError, match="Missing"):
        _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_missing_staging_location() -> None:
    args = {**_VALID_DATAFLOW_KWARGS, "staging_location": ""}
    with pytest.raises(ValueError, match="Missing"):
        _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_missing_temp_location() -> None:
    args = {**_VALID_DATAFLOW_KWARGS, "temp_location": ""}
    with pytest.raises(ValueError, match="Missing"):
        _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_missing_input_subscription() -> None:
    args = {**_VALID_DATAFLOW_KWARGS, "input_subscription": ""}
    with pytest.raises(ValueError, match="Missing"):
        _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_missing_output_table() -> None:
    args = {**_VALID_DATAFLOW_KWARGS, "output_table": ""}
    with pytest.raises(ValueError, match="Missing"):
        _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_production_push_subscription() -> None:
    # Defensive check: worker-push is caught by the explicit fragment guard.
    args = {
        **_VALID_DATAFLOW_KWARGS,
        "input_subscription": "projects/myproject/subscriptions/market-events-raw-worker-push",
    }
    with pytest.raises(ValueError, match="worker-push"):
        _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_any_non_proof_subscription() -> None:
    # Exact-match guard: a non-worker-push subscription that is not the proof subscription.
    # This covers the case where someone points at market-events-raw-based subscriptions
    # or any other arbitrary subscription.
    for bad_sub in [
        "projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-something",
        "projects/project-42987e01-2123-446b-ac7/subscriptions/other-sub",
        "projects/otherproject/subscriptions/market-events-raw-beam-proof-sub",
    ]:
        args = {**_VALID_DATAFLOW_KWARGS, "input_subscription": bad_sub}
        with pytest.raises(ValueError, match="proof subscription"):
            _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_production_table() -> None:
    args = {
        **_VALID_DATAFLOW_KWARGS,
        "output_table": "project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_raw",
    }
    with pytest.raises(ValueError, match="market_events_beam_proof"):
        _validate_dataflow_args(**args)


def test_validate_dataflow_args_rejects_any_non_proof_table() -> None:
    # Exact-match guard: any table that is not DATAFLOW_PROOF_TABLE is rejected.
    for bad_table in [
        "myproject:mydataset.some_other_table",
        "project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_raw",
        "project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_beam_proof_extra",
    ]:
        args = {**_VALID_DATAFLOW_KWARGS, "output_table": bad_table}
        with pytest.raises(ValueError, match="market_events_beam_proof"):
            _validate_dataflow_args(**args)


# --- run_dataflow() rejects invalid args without GCP calls ---


def test_run_dataflow_rejects_missing_project() -> None:
    with pytest.raises(ValueError, match="Missing"):
        run_dataflow(
            project="",
            region="europe-west1",
            service_account_email="sa@example.iam.gserviceaccount.com",
            staging_location="gs://bucket/staging",
            temp_location="gs://bucket/tmp",
            input_subscription=DATAFLOW_PROOF_SUBSCRIPTION,
            output_table=DATAFLOW_PROOF_TABLE,
        )


def test_run_dataflow_rejects_production_push_subscription() -> None:
    with pytest.raises(ValueError, match="worker-push"):
        run_dataflow(
            project="myproject",
            region="europe-west1",
            service_account_email="sa@example.iam.gserviceaccount.com",
            staging_location="gs://bucket/staging",
            temp_location="gs://bucket/tmp",
            input_subscription="projects/myproject/subscriptions/market-events-raw-worker-push",
            output_table=DATAFLOW_PROOF_TABLE,
        )


def test_run_dataflow_rejects_non_proof_subscription() -> None:
    # Exact-match: a subscription that looks similar but is not the proof subscription.
    with pytest.raises(ValueError, match="proof subscription"):
        run_dataflow(
            project="myproject",
            region="europe-west1",
            service_account_email="sa@example.iam.gserviceaccount.com",
            staging_location="gs://bucket/staging",
            temp_location="gs://bucket/tmp",
            input_subscription="projects/project-42987e01-2123-446b-ac7/subscriptions/market-events-raw-something",
            output_table=DATAFLOW_PROOF_TABLE,
        )


def test_run_dataflow_rejects_production_table() -> None:
    with pytest.raises(ValueError, match="market_events_beam_proof"):
        run_dataflow(
            project="myproject",
            region="europe-west1",
            service_account_email="sa@example.iam.gserviceaccount.com",
            staging_location="gs://bucket/staging",
            temp_location="gs://bucket/tmp",
            input_subscription=DATAFLOW_PROOF_SUBSCRIPTION,
            output_table="project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_raw",
        )


# --- proof constants sanity ---


def test_proof_topic_constant_is_proof_only() -> None:
    assert "market-events-raw-beam-proof" in DATAFLOW_PROOF_TOPIC
    # Must NOT reference the production topic name directly (no suffix confusion).
    assert DATAFLOW_PROOF_TOPIC.endswith("/topics/market-events-raw-beam-proof")
    # Must NOT be the production topic.
    assert "market-events-raw-worker-push" not in DATAFLOW_PROOF_TOPIC


def test_proof_subscription_constant_references_proof_sub() -> None:
    assert "market-events-raw-beam-proof-sub" in DATAFLOW_PROOF_SUBSCRIPTION
    assert "worker-push" not in DATAFLOW_PROOF_SUBSCRIPTION
    # Subscription path must not reference the production topic name.
    assert DATAFLOW_PROOF_SUBSCRIPTION.endswith("/subscriptions/market-events-raw-beam-proof-sub")


def test_proof_table_constant_references_proof_table() -> None:
    assert "market_events_beam_proof" in DATAFLOW_PROOF_TABLE
    assert DATAFLOW_PROOF_TABLE.endswith(".market_events_beam_proof")


def test_proof_topic_and_subscription_are_distinct_resources() -> None:
    # Topic and subscription have different resource types in their paths.
    assert "/topics/" in DATAFLOW_PROOF_TOPIC
    assert "/subscriptions/" in DATAFLOW_PROOF_SUBSCRIPTION
    assert "/topics/" not in DATAFLOW_PROOF_SUBSCRIPTION


# --- Dataflow packaging: extra_packages wheel staging ---


def test_no_setup_py_at_repo_root() -> None:
    # setup.py must NOT exist: running it from repo root reads root pyproject.toml,
    # overwrites name to real-time-data-platform and install_requires to [], and stages
    # the wrong artifact with no pydantic dependency.
    assert not (_PROJECT_ROOT / "setup.py").exists(), (
        "setup.py must not exist at repo root. It reads root pyproject.toml and produces "
        "a broken sdist (wrong name, empty install_requires). Use --extra_packages instead."
    )


def test_contracts_wheel_can_be_built_and_contains_rtdp_contracts(tmp_path: Path) -> None:
    import zipfile

    result = subprocess.run(
        [
            "uv",
            "build",
            str(_PROJECT_ROOT / "packages" / "contracts"),
            "--wheel",
            "--out-dir",
            str(tmp_path),
        ],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"uv build failed:\n{result.stdout}\n{result.stderr}"
    wheels = list(tmp_path.glob("rtdp_contracts-*.whl"))
    assert wheels, f"No rtdp_contracts wheel found. uv output:\n{result.stdout}"
    with zipfile.ZipFile(wheels[0]) as zf:
        names = zf.namelist()
        meta_files = [n for n in names if n.endswith("/METADATA")]
        assert meta_files, f"No METADATA in wheel: {names}"
        metadata = zf.read(meta_files[0]).decode()
    assert any("rtdp_contracts" in n for n in names), f"rtdp_contracts not in wheel: {names}"
    assert "pydantic" in metadata.lower(), f"pydantic missing from wheel METADATA:\n{metadata[:800]}"


def test_run_dataflow_source_uses_extra_packages_not_setup_file() -> None:
    import pipelines.beam_market_events as m

    source = inspect.getsource(m)
    assert "extra_packages" in source, (
        "run_dataflow() must set extra_packages to stage rtdp_contracts wheel to workers"
    )
    assert "setup_opts.setup_file" not in source, (
        "setup_opts.setup_file must not be set: setup.py from repo root reads pyproject.toml "
        "and produces a broken sdist (wrong name, empty install_requires)"
    )
