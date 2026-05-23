"""Tests for the Apache Beam DirectRunner MarketEvent pipeline."""

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

from pipelines.beam_market_events import DEAD_LETTER_TAG, ParseAndValidateDoFn, run


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


# --- runner guard ---


def test_runner_guard_rejects_dataflow_runner() -> None:
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


# --- safety: no GCP env vars or clients ---


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
    assert callable(m.main)


def test_no_pubsub_bigquery_clients_in_module_source() -> None:
    import pipelines.beam_market_events as m

    source = inspect.getsource(m)
    for forbidden in [
        "google.cloud.pubsub",
        "google.cloud.bigquery",
        "from google.cloud import pubsub",
        "from google.cloud import bigquery",
        "ReadFromPubSub",
        "WriteToBigQuery",
    ]:
        assert forbidden not in source, f"Forbidden reference found in source: {forbidden}"


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


def test_cli_subprocess_rejects_dataflow_runner() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        input_path = d / "input.jsonl"
        input_path.write_text(_valid_event_jsonl(1) + "\n")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pipelines.beam_market_events",
                "--input-jsonl",
                str(input_path),
                "--output-jsonl",
                str(d / "out.jsonl"),
                "--dead-letter-jsonl",
                str(d / "dl.jsonl"),
                "--runner",
                "DataflowRunner",
            ],
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
        )

        assert result.returncode != 0, "CLI must exit non-zero when DataflowRunner is requested"
        assert "DataflowRunner" in result.stderr, (
            f"stderr must name the rejected runner.\nstderr: {result.stderr}"
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
