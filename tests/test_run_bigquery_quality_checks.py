"""Tests for scripts/run_bigquery_quality_checks.py."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parent.parent / "scripts" / "run_bigquery_quality_checks.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_bigquery_quality_checks", SCRIPT)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def args(**overrides):
    defaults = {
        "project_id": "project-42987e01-2123-446b-ac7",
        "dataset": "rtdp_analytics",
        "table": "market_events_raw",
        "staging_table": "market_events_raw_staging",
        "accepted_event_types": "trade",
        "report_output": "",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_table_ref_uses_backticked_bigquery_reference():
    module = load_module()

    assert (
        module.table_ref("project-123", "analytics", "events") == "`project-123.analytics.events`"
    )


def test_run_checks_builds_expected_report_with_all_checks_passing(monkeypatch):
    module = load_module()

    responses = {
        "SELECT COUNT(*) AS row_count FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`": [
            {"row_count": "6120"}
        ],
        (
            "SELECT COUNTIF(event_id IS NULL) AS event_id_nulls, "
            "COUNTIF(event_timestamp IS NULL) AS event_timestamp_nulls, "
            "COUNTIF(symbol IS NULL) AS symbol_nulls, "
            "COUNTIF(event_type IS NULL) AS event_type_nulls, "
            "COUNTIF(ingest_timestamp IS NULL) AS ingest_timestamp_nulls, "
            "COUNTIF(bq_load_timestamp IS NULL) AS bq_load_timestamp_nulls "
            "FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`"
        ): [
            {
                "event_id_nulls": "0",
                "event_timestamp_nulls": "0",
                "symbol_nulls": "0",
                "event_type_nulls": "0",
                "ingest_timestamp_nulls": "0",
                "bq_load_timestamp_nulls": "0",
            }
        ],
        (
            "SELECT COUNT(*) AS duplicate_event_ids\n"
            "FROM (\n"
            "  SELECT event_id\n"
            "  FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`\n"
            "  GROUP BY event_id\n"
            "  HAVING COUNT(*) > 1\n"
            ")"
        ): [{"duplicate_event_ids": "0"}],
        (
            "SELECT COUNT(*) AS invalid_event_type_rows\n"
            "FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`\n"
            "WHERE event_type NOT IN ('trade')"
        ): [{"invalid_event_type_rows": "0"}],
        (
            "SELECT\n"
            "  CAST(MAX(ingest_timestamp) AS STRING) AS max_ingest_timestamp,\n"
            "  COUNT(*) AS row_count\n"
            "FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`"
        ): [{"max_ingest_timestamp": "2026-05-16 10:08:49.141452 UTC", "row_count": "6120"}],
        (
            "SELECT COUNT(*) AS staging_row_count "
            "FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw_staging`"
        ): [{"staging_row_count": "0"}],
    }

    observed_sql = []

    def fake_bq_query(sql: str):
        observed_sql.append(sql)
        return responses[sql]

    monkeypatch.setattr(module, "bq_query", fake_bq_query)

    report = module.run_checks(args())

    assert report["status"] == "ok"
    assert report["project_id"] == "project-42987e01-2123-446b-ac7"
    assert report["dataset"] == "rtdp_analytics"
    assert report["table"] == "market_events_raw"
    assert report["staging_table"] == "market_events_raw_staging"
    assert report["accepted_event_types"] == ["trade"]
    assert report["failed_checks"] == []
    assert [check["name"] for check in report["checks"]] == [
        "row_count_positive",
        "required_columns_not_null",
        "event_id_unique",
        "event_type_accepted_values",
        "freshness_available",
        "staging_table_empty",
    ]
    assert all(check["status"] == "pass" for check in report["checks"])
    assert len(observed_sql) == 6


def test_run_checks_reports_failures(monkeypatch):
    module = load_module()

    responses = {
        "SELECT COUNT(*) AS row_count FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`": [
            {"row_count": "0"}
        ],
        (
            "SELECT COUNTIF(event_id IS NULL) AS event_id_nulls, "
            "COUNTIF(event_timestamp IS NULL) AS event_timestamp_nulls, "
            "COUNTIF(symbol IS NULL) AS symbol_nulls, "
            "COUNTIF(event_type IS NULL) AS event_type_nulls, "
            "COUNTIF(ingest_timestamp IS NULL) AS ingest_timestamp_nulls, "
            "COUNTIF(bq_load_timestamp IS NULL) AS bq_load_timestamp_nulls "
            "FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`"
        ): [
            {
                "event_id_nulls": "1",
                "event_timestamp_nulls": "0",
                "symbol_nulls": "0",
                "event_type_nulls": "0",
                "ingest_timestamp_nulls": "0",
                "bq_load_timestamp_nulls": "0",
            }
        ],
        (
            "SELECT COUNT(*) AS duplicate_event_ids\n"
            "FROM (\n"
            "  SELECT event_id\n"
            "  FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`\n"
            "  GROUP BY event_id\n"
            "  HAVING COUNT(*) > 1\n"
            ")"
        ): [{"duplicate_event_ids": "2"}],
        (
            "SELECT COUNT(*) AS invalid_event_type_rows\n"
            "FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`\n"
            "WHERE event_type NOT IN ('trade')"
        ): [{"invalid_event_type_rows": "3"}],
        (
            "SELECT\n"
            "  CAST(MAX(ingest_timestamp) AS STRING) AS max_ingest_timestamp,\n"
            "  COUNT(*) AS row_count\n"
            "FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw`"
        ): [{"max_ingest_timestamp": None, "row_count": "0"}],
        (
            "SELECT COUNT(*) AS staging_row_count "
            "FROM `project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw_staging`"
        ): [{"staging_row_count": "5"}],
    }

    monkeypatch.setattr(module, "bq_query", lambda sql: responses[sql])

    report = module.run_checks(args())

    assert report["status"] == "error"
    assert report["failed_checks"] == [
        "row_count_positive",
        "required_columns_not_null",
        "event_id_unique",
        "event_type_accepted_values",
        "freshness_available",
        "staging_table_empty",
    ]


def test_accepted_event_types_are_parsed_and_used_in_sql(monkeypatch):
    module = load_module()

    captured_sql = []

    def fake_scalar_int(sql: str, key: str) -> int:
        captured_sql.append((sql, key))
        return 0

    monkeypatch.setattr(module, "scalar_int", fake_scalar_int)

    check = module.check_event_type_accepted_values(
        "`project.dataset.table`",
        ("trade", "quote"),
    )

    assert check.status == "pass"
    assert check.observed == {
        "invalid_event_type_rows": 0,
        "accepted_event_types": ["trade", "quote"],
    }
    assert "WHERE event_type NOT IN ('trade', 'quote')" in captured_sql[0][0]


def test_empty_accepted_event_types_fails():
    module = load_module()

    try:
        module.run_checks(args(accepted_event_types=", ,"))
    except ValueError as exc:
        assert str(exc) == "accepted_event_types cannot be empty"
    else:
        raise AssertionError("Expected ValueError for empty accepted event types")


def test_bq_query_uses_quiet_json_mode(monkeypatch):
    module = load_module()
    observed = {}

    def fake_run(args, capture_output, text, check):
        observed["args"] = args
        observed["capture_output"] = capture_output
        observed["text"] = text
        observed["check"] = check
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='[{"row_count": "1"}]',
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    rows = module.bq_query("SELECT 1 AS row_count")

    assert rows == [{"row_count": "1"}]
    assert observed["args"] == [
        "bq",
        "--quiet",
        "query",
        "--nouse_legacy_sql",
        "--format=json",
        "SELECT 1 AS row_count",
    ]
    assert observed["capture_output"] is True
    assert observed["text"] is True
    assert observed["check"] is False


def test_bq_query_raises_on_cli_failure(monkeypatch):
    module = load_module()

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["bq"],
            returncode=1,
            stdout="",
            stderr="boom",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    try:
        module.bq_query("SELECT 1")
    except RuntimeError as exc:
        message = str(exc)
        assert "bq query failed" in message
        assert "exit_code=1" in message
        assert "boom" in message
        assert "SELECT 1" in message
    else:
        raise AssertionError("Expected RuntimeError")


def test_bq_query_raises_on_invalid_json(monkeypatch):
    module = load_module()

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["bq"],
            returncode=0,
            stdout="not json",
            stderr="warning from bq",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    try:
        module.bq_query("SELECT 1")
    except RuntimeError as exc:
        message = str(exc)
        assert "bq returned invalid JSON" in message
        assert "stdout_preview='not json'" in message
        assert "stderr_preview='warning from bq'" in message
    else:
        raise AssertionError("Expected RuntimeError")


def test_write_report_stdout(capsys):
    module = load_module()

    module.write_report({"status": "ok", "checks": []}, "")

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "ok", "checks": []}


def test_write_report_to_file(tmp_path):
    module = load_module()

    output = tmp_path / "quality-report.json"
    module.write_report({"status": "ok"}, str(output))

    assert json.loads(output.read_text()) == {"status": "ok"}


def test_write_report_missing_parent_fails(tmp_path):
    module = load_module()

    missing_parent = tmp_path / "missing" / "quality-report.json"

    try:
        module.write_report({"status": "ok"}, str(missing_parent))
    except FileNotFoundError as exc:
        assert "Report output parent does not exist" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")
