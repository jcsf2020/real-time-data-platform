"""Tests for scripts/push_dbt_metrics.py.

All tests use --dry-run or call pure functions directly.
push_time_series() is tested only with mocked subprocess and urllib to ensure
it never touches Cloud Monitoring during the test run.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parent.parent / "scripts" / "push_dbt_metrics.py"

FIXED_NOW = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)
PROJECT_ID = "project-42987e01-2123-446b-ac7"
JOB_NAME = "rtdp-dbt-refresh-job"
ENVIRONMENT = "cloud_sql_prod"


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("push_dbt_metrics", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures / factories
# ---------------------------------------------------------------------------


def _model_result(
    name: str = "silver_market_event_minute_aggregates",
    status: str = "success",
    execution_time: float = 12.3,
    rows_affected: int | None = 13,
) -> dict:
    return {
        "unique_id": f"model.rtdp.{name}",
        "status": status,
        "execution_time": execution_time,
        "adapter_response": {"rows_affected": rows_affected},
        "failures": None,
        "message": f"INSERT 0 {rows_affected}",
    }


def _test_result(
    name: str = "not_null_silver_symbol",
    status: str = "pass",
    execution_time: float = 0.5,
) -> dict:
    return {
        "unique_id": f"test.rtdp.{name}",
        "status": status,
        "execution_time": execution_time,
        "adapter_response": {},
        "failures": 0,
        "message": "Pass",
    }


def _make_run_results(
    elapsed_time: float = 77.25,
    results: list | None = None,
    invocation_id: str = "test-invocation-abc123",
    generated_at: str = "2026-05-22T11:00:00.000000Z",
) -> dict:
    if results is None:
        results = [
            _model_result("silver_market_event_minute_aggregates", rows_affected=13),
            _model_result("gold_market_event_daily_aggregates", rows_affected=7),
            _test_result("not_null_silver_symbol"),
            _test_result("not_null_gold_symbol"),
        ]
    return {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/run-results/v5.json",
            "dbt_version": "1.9.0",
            "generated_at": generated_at,
            "invocation_id": invocation_id,
            "env": {},
        },
        "elapsed_time": elapsed_time,
        "results": results,
    }


def _ts_by_suffix(time_series: list[dict], suffix: str) -> list[dict]:
    return [ts for ts in time_series if ts["metric"]["type"].endswith(f"/{suffix}")]


class _FakeResponse:
    def __init__(self, body: bytes = b"{}"):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _gcloud_ok(args, **kwargs):
    return subprocess.CompletedProcess(
        args=args, returncode=0, stdout="fake_token\n", stderr=""
    )


# ---------------------------------------------------------------------------
# load_run_results
# ---------------------------------------------------------------------------


def test_load_run_results_parses_valid_json(tmp_path):
    module = load_module()
    data = _make_run_results()
    f = tmp_path / "run_results.json"
    f.write_text(json.dumps(data))

    result = module.load_run_results(str(f))

    assert result["elapsed_time"] == data["elapsed_time"]
    assert len(result["results"]) == 4


def test_load_run_results_raises_on_missing_file(tmp_path):
    module = load_module()
    missing = tmp_path / "run_results.json"

    try:
        module.load_run_results(str(missing))
    except FileNotFoundError as exc:
        assert "not found" in str(exc).lower()
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_load_run_results_raises_on_invalid_json(tmp_path):
    module = load_module()
    bad = tmp_path / "run_results.json"
    bad.write_text("not valid json {{{{")

    try:
        module.load_run_results(str(bad))
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("Expected JSONDecodeError")


# ---------------------------------------------------------------------------
# _infer_node_type
# ---------------------------------------------------------------------------


def test_infer_node_type_model():
    module = load_module()
    assert module._infer_node_type("model.rtdp.silver_market_event_minute_aggregates") == "model"


def test_infer_node_type_test():
    module = load_module()
    assert module._infer_node_type("test.rtdp.not_null_silver_symbol") == "test"


def test_infer_node_type_seed():
    module = load_module()
    assert module._infer_node_type("seed.rtdp.some_seed") == "seed"


def test_infer_node_type_unknown():
    module = load_module()
    assert module._infer_node_type("unknown.rtdp.something") == "unknown"


# ---------------------------------------------------------------------------
# _extract_name
# ---------------------------------------------------------------------------


def test_extract_name_model():
    module = load_module()
    assert (
        module._extract_name("model.rtdp.silver_market_event_minute_aggregates")
        == "silver_market_event_minute_aggregates"
    )


def test_extract_name_test():
    module = load_module()
    assert (
        module._extract_name("test.rtdp.unique_silver_symbol__window_start")
        == "unique_silver_symbol__window_start"
    )


def test_extract_name_short_id():
    module = load_module()
    assert module._extract_name("model") == "model"


# ---------------------------------------------------------------------------
# parse_run_results
# ---------------------------------------------------------------------------


def test_parse_extracts_elapsed_time():
    module = load_module()
    data = _make_run_results(elapsed_time=77.25)
    parsed = module.parse_run_results(data)
    assert parsed["elapsed_time"] == 77.25


def test_parse_extracts_invocation_id_from_metadata():
    module = load_module()
    data = _make_run_results(invocation_id="meta-inv-id")
    parsed = module.parse_run_results(data)
    assert parsed["invocation_id"] == "meta-inv-id"


def test_parse_extracts_invocation_id_from_args():
    module = load_module()
    data = _make_run_results()
    del data["metadata"]["invocation_id"]
    data["args"] = {"invocation_id": "args-inv-id"}
    parsed = module.parse_run_results(data)
    assert parsed["invocation_id"] == "args-inv-id"


def test_parse_invocation_id_none_when_missing():
    module = load_module()
    data = _make_run_results()
    del data["metadata"]["invocation_id"]
    parsed = module.parse_run_results(data)
    assert parsed["invocation_id"] is None


def test_parse_extracts_generated_at():
    module = load_module()
    data = _make_run_results(generated_at="2026-05-22T11:00:00.000000Z")
    parsed = module.parse_run_results(data)
    assert parsed["generated_at"] == "2026-05-22T11:00:00.000000Z"


def test_parse_produces_correct_node_count():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    assert len(parsed["nodes"]) == 4


def test_parse_node_type_model():
    module = load_module()
    data = _make_run_results(results=[_model_result("silver_market_event_minute_aggregates")])
    parsed = module.parse_run_results(data)
    assert parsed["nodes"][0]["node_type"] == "model"


def test_parse_node_type_test():
    module = load_module()
    data = _make_run_results(results=[_test_result("not_null_silver")])
    parsed = module.parse_run_results(data)
    assert parsed["nodes"][0]["node_type"] == "test"


def test_parse_node_name_extracted():
    module = load_module()
    data = _make_run_results(results=[_model_result("gold_market_event_daily_aggregates")])
    parsed = module.parse_run_results(data)
    assert parsed["nodes"][0]["name"] == "gold_market_event_daily_aggregates"


def test_parse_node_status_lowercased():
    module = load_module()
    result = _model_result()
    result["status"] = "SUCCESS"
    data = _make_run_results(results=[result])
    parsed = module.parse_run_results(data)
    assert parsed["nodes"][0]["status"] == "success"


def test_parse_rows_affected_present():
    module = load_module()
    data = _make_run_results(results=[_model_result(rows_affected=13)])
    parsed = module.parse_run_results(data)
    assert parsed["nodes"][0]["rows_affected"] == 13


def test_parse_rows_affected_none_when_absent():
    module = load_module()
    result = _model_result()
    result["adapter_response"] = {}
    data = _make_run_results(results=[result])
    parsed = module.parse_run_results(data)
    assert parsed["nodes"][0]["rows_affected"] is None


def test_parse_rows_affected_none_when_adapter_response_missing():
    module = load_module()
    result = _model_result()
    del result["adapter_response"]
    data = _make_run_results(results=[result])
    parsed = module.parse_run_results(data)
    assert parsed["nodes"][0]["rows_affected"] is None


def test_parse_zero_parse_errors_on_clean_input():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    assert parsed["parse_error_count"] == 0


def test_parse_increments_error_count_on_bad_node():
    module = load_module()
    data = _make_run_results(
        results=[
            None,  # causes AttributeError in .get()
            _model_result(),
        ]
    )
    parsed = module.parse_run_results(data)
    assert parsed["parse_error_count"] == 1
    assert len(parsed["nodes"]) == 1


def test_parse_empty_results():
    module = load_module()
    data = _make_run_results(results=[])
    parsed = module.parse_run_results(data)
    assert parsed["nodes"] == []
    assert parsed["parse_error_count"] == 0


def test_parse_missing_results_key():
    module = load_module()
    data = _make_run_results(results=[])
    del data["results"]
    parsed = module.parse_run_results(data)
    assert parsed["nodes"] == []


# ---------------------------------------------------------------------------
# build_time_series — metric presence
# ---------------------------------------------------------------------------


def test_build_produces_eight_core_metrics_plus_model_rows():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    # 6 summary metrics + 2 model rows_total (2 models with rows) + 1 parse_error
    assert len(ts) == 9


def test_build_no_model_rows_when_rows_absent():
    module = load_module()
    r = _model_result(rows_affected=None)
    r["adapter_response"] = {}
    data = _make_run_results(results=[r])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    rows_ts = _ts_by_suffix(ts, "dbt_model_rows_total")
    assert len(rows_ts) == 0


# ---------------------------------------------------------------------------
# build_time_series — dbt_run_success_count
# ---------------------------------------------------------------------------


def test_run_success_count_two_successes():
    module = load_module()
    data = _make_run_results(
        results=[_model_result(status="success"), _model_result("gold", status="success")]
    )
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_run_success_count")
    assert len(ts_list) == 1
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "2"


def test_run_success_count_zero_when_all_error():
    module = load_module()
    data = _make_run_results(results=[_model_result(status="error")])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_run_success_count")
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "0"


# ---------------------------------------------------------------------------
# build_time_series — dbt_run_failure_count
# ---------------------------------------------------------------------------


def test_run_failure_count_one_error():
    module = load_module()
    data = _make_run_results(
        results=[_model_result(status="error"), _model_result("gold", status="success")]
    )
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_run_failure_count")
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "1"


def test_run_failure_count_zero_when_all_pass():
    module = load_module()
    data = _make_run_results(results=[_model_result(status="success")])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_run_failure_count")
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "0"


# ---------------------------------------------------------------------------
# build_time_series — dbt_run_duration_seconds
# ---------------------------------------------------------------------------


def test_run_duration_seconds_value_and_type():
    module = load_module()
    data = _make_run_results(elapsed_time=77.25)
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_run_duration_seconds")
    assert len(ts_list) == 1
    assert ts_list[0]["valueType"] == "DOUBLE"
    assert ts_list[0]["points"][0]["value"]["doubleValue"] == 77.25


# ---------------------------------------------------------------------------
# build_time_series — dbt_test_pass_count / dbt_test_failure_count
# ---------------------------------------------------------------------------


def test_test_pass_count_two_passes():
    module = load_module()
    data = _make_run_results(
        results=[_test_result("t1", "pass"), _test_result("t2", "pass")]
    )
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_test_pass_count")
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "2"


def test_test_pass_count_zero_when_all_fail():
    module = load_module()
    data = _make_run_results(results=[_test_result("t1", "fail")])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_test_pass_count")
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "0"


def test_test_failure_count_counts_fail_status():
    module = load_module()
    data = _make_run_results(
        results=[_test_result("t1", "fail"), _test_result("t2", "pass")]
    )
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_test_failure_count")
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "1"


def test_test_failure_count_counts_error_status():
    module = load_module()
    data = _make_run_results(results=[_test_result("t1", "error")])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_test_failure_count")
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "1"


def test_test_failure_count_zero_when_all_pass():
    module = load_module()
    data = _make_run_results(results=[_test_result("t1", "pass")])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_test_failure_count")
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "0"


# ---------------------------------------------------------------------------
# build_time_series — dbt_test_pass_rate
# ---------------------------------------------------------------------------


def test_test_pass_rate_100_when_all_pass():
    module = load_module()
    data = _make_run_results(
        results=[_test_result("t1", "pass"), _test_result("t2", "pass")]
    )
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_test_pass_rate")
    assert ts_list[0]["valueType"] == "DOUBLE"
    assert ts_list[0]["points"][0]["value"]["doubleValue"] == 100.0


def test_test_pass_rate_0_when_all_fail():
    module = load_module()
    data = _make_run_results(results=[_test_result("t1", "fail")])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_test_pass_rate")
    assert ts_list[0]["points"][0]["value"]["doubleValue"] == 0.0


def test_test_pass_rate_50_partial():
    module = load_module()
    data = _make_run_results(
        results=[_test_result("t1", "pass"), _test_result("t2", "fail")]
    )
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_test_pass_rate")
    assert ts_list[0]["points"][0]["value"]["doubleValue"] == 50.0


def test_test_pass_rate_zero_when_no_tests():
    module = load_module()
    data = _make_run_results(results=[_model_result()])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_test_pass_rate")
    assert ts_list[0]["points"][0]["value"]["doubleValue"] == 0.0


# ---------------------------------------------------------------------------
# build_time_series — dbt_model_rows_total
# ---------------------------------------------------------------------------


def test_model_rows_total_emitted_per_model():
    module = load_module()
    data = _make_run_results(
        results=[
            _model_result("silver_market_event_minute_aggregates", rows_affected=13),
            _model_result("gold_market_event_daily_aggregates", rows_affected=7),
        ]
    )
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    rows_ts = _ts_by_suffix(ts, "dbt_model_rows_total")
    assert len(rows_ts) == 2


def test_model_rows_total_carries_model_name_label():
    module = load_module()
    data = _make_run_results(
        results=[_model_result("silver_market_event_minute_aggregates", rows_affected=13)]
    )
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    rows_ts = _ts_by_suffix(ts, "dbt_model_rows_total")
    assert rows_ts[0]["metric"]["labels"]["model_name"] == "silver_market_event_minute_aggregates"
    assert rows_ts[0]["points"][0]["value"]["int64Value"] == "13"


def test_model_rows_total_skipped_when_rows_none():
    module = load_module()
    result = _model_result(rows_affected=None)
    result["adapter_response"] = {}
    data = _make_run_results(results=[result])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    rows_ts = _ts_by_suffix(ts, "dbt_model_rows_total")
    assert len(rows_ts) == 0


# ---------------------------------------------------------------------------
# build_time_series — dbt_artifact_parse_error_count
# ---------------------------------------------------------------------------


def test_parse_error_count_zero_when_clean():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_artifact_parse_error_count")
    assert len(ts_list) == 1
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "0"


def test_parse_error_count_reflects_node_failures():
    module = load_module()
    data = _make_run_results(results=[None, _model_result()])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    ts_list = _ts_by_suffix(ts, "dbt_artifact_parse_error_count")
    assert ts_list[0]["points"][0]["value"]["int64Value"] == "1"


# ---------------------------------------------------------------------------
# build_time_series — labels, resource, timestamp
# ---------------------------------------------------------------------------


def test_summary_metrics_carry_job_name_and_environment():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    for entry in _ts_by_suffix(ts, "dbt_run_success_count"):
        assert entry["metric"]["labels"]["job_name"] == JOB_NAME
        assert entry["metric"]["labels"]["environment"] == ENVIRONMENT


def test_model_metrics_carry_node_type_model():
    module = load_module()
    data = _make_run_results(results=[_model_result()])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    for suffix in ("dbt_run_success_count", "dbt_run_failure_count"):
        for entry in _ts_by_suffix(ts, suffix):
            assert entry["metric"]["labels"]["node_type"] == "model"


def test_test_metrics_carry_node_type_test():
    module = load_module()
    data = _make_run_results(results=[_test_result()])
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    for suffix in ("dbt_test_pass_count", "dbt_test_failure_count", "dbt_test_pass_rate"):
        for entry in _ts_by_suffix(ts, suffix):
            assert entry["metric"]["labels"]["node_type"] == "test"


def test_all_metrics_have_global_resource_with_project_id():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    for entry in ts:
        assert entry["resource"]["type"] == "global"
        assert entry["resource"]["labels"]["project_id"] == PROJECT_ID


def test_all_metrics_end_time_matches_now():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    for entry in ts:
        assert entry["points"][0]["interval"]["endTime"] == "2026-05-22T12:00:00Z"


def test_all_metrics_have_gauge_metric_kind():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    for entry in ts:
        assert entry["metricKind"] == "GAUGE"


def test_metric_types_use_correct_prefix():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    ts = module.build_time_series(parsed, PROJECT_ID, JOB_NAME, ENVIRONMENT, FIXED_NOW)

    for entry in ts:
        assert entry["metric"]["type"].startswith("custom.googleapis.com/rtdp/dbt/")


# ---------------------------------------------------------------------------
# build_summary
# ---------------------------------------------------------------------------


def test_build_summary_correct_model_counts():
    module = load_module()
    data = _make_run_results(
        results=[
            _model_result("silver", status="success"),
            _model_result("gold", status="error"),
        ]
    )
    parsed = module.parse_run_results(data)
    summary = module.build_summary(parsed, JOB_NAME, ENVIRONMENT, 8, True, FIXED_NOW)

    assert summary["models"]["total"] == 2
    assert summary["models"]["success"] == 1
    assert summary["models"]["error"] == 1


def test_build_summary_correct_test_counts():
    module = load_module()
    data = _make_run_results(
        results=[_test_result("t1", "pass"), _test_result("t2", "fail")]
    )
    parsed = module.parse_run_results(data)
    summary = module.build_summary(parsed, JOB_NAME, ENVIRONMENT, 8, True, FIXED_NOW)

    assert summary["tests"]["total"] == 2
    assert summary["tests"]["pass"] == 1
    assert summary["tests"]["fail"] == 1
    assert summary["tests"]["pass_rate"] == 50.0


def test_build_summary_reflects_dry_run_flag():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)

    dry = module.build_summary(parsed, JOB_NAME, ENVIRONMENT, 8, True, FIXED_NOW)
    live = module.build_summary(parsed, JOB_NAME, ENVIRONMENT, 8, False, FIXED_NOW)

    assert dry["dry_run"] is True
    assert live["dry_run"] is False


def test_build_summary_metrics_emitted_count():
    module = load_module()
    data = _make_run_results()
    parsed = module.parse_run_results(data)
    summary = module.build_summary(parsed, JOB_NAME, ENVIRONMENT, 9, True, FIXED_NOW)

    assert summary["metrics_emitted"] == 9


def test_build_summary_has_invocation_id():
    module = load_module()
    data = _make_run_results(invocation_id="my-inv-123")
    parsed = module.parse_run_results(data)
    summary = module.build_summary(parsed, JOB_NAME, ENVIRONMENT, 8, True, FIXED_NOW)

    assert summary["invocation_id"] == "my-inv-123"


# ---------------------------------------------------------------------------
# main() — dry-run mode (no Cloud Monitoring writes)
# ---------------------------------------------------------------------------


def test_main_dry_run_returns_0(tmp_path):
    module = load_module()
    f = tmp_path / "run_results.json"
    f.write_text(json.dumps(_make_run_results()))

    result = module.main(
        [
            "--run-results-path", str(f),
            "--project-id", PROJECT_ID,
            "--dry-run",
        ]
    )

    assert result == 0


def test_main_dry_run_prints_valid_json(tmp_path, capsys):
    module = load_module()
    f = tmp_path / "run_results.json"
    f.write_text(json.dumps(_make_run_results()))

    module.main(
        [
            "--run-results-path", str(f),
            "--project-id", PROJECT_ID,
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert "models" in parsed
    assert "tests" in parsed
    assert "dry_run" in parsed
    assert parsed["dry_run"] is True


def test_main_dry_run_does_not_call_gcloud(monkeypatch, tmp_path):
    module = load_module()
    f = tmp_path / "run_results.json"
    f.write_text(json.dumps(_make_run_results()))

    calls: list = []
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: calls.append(a))

    module.main(
        [
            "--run-results-path", str(f),
            "--project-id", PROJECT_ID,
            "--dry-run",
        ]
    )

    assert len(calls) == 0


def test_main_writes_output_json(tmp_path):
    module = load_module()
    f = tmp_path / "run_results.json"
    f.write_text(json.dumps(_make_run_results()))
    out = tmp_path / "summary.json"

    module.main(
        [
            "--run-results-path", str(f),
            "--project-id", PROJECT_ID,
            "--dry-run",
            "--output-json", str(out),
        ]
    )

    assert out.exists()
    summary = json.loads(out.read_text())
    assert "models" in summary


def test_main_returns_nonzero_on_missing_file(tmp_path):
    module = load_module()
    missing = tmp_path / "run_results.json"

    result = module.main(
        [
            "--run-results-path", str(missing),
            "--project-id", PROJECT_ID,
            "--dry-run",
        ]
    )

    assert result != 0


def test_main_returns_nonzero_on_invalid_json(tmp_path):
    module = load_module()
    bad = tmp_path / "run_results.json"
    bad.write_text("not valid json")

    result = module.main(
        [
            "--run-results-path", str(bad),
            "--project-id", PROJECT_ID,
            "--dry-run",
        ]
    )

    assert result != 0


def test_main_dry_run_respects_job_name_and_environment(tmp_path, capsys):
    module = load_module()
    f = tmp_path / "run_results.json"
    f.write_text(json.dumps(_make_run_results()))

    module.main(
        [
            "--run-results-path", str(f),
            "--project-id", PROJECT_ID,
            "--job-name", "custom-dbt-job",
            "--environment", "staging",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert summary["job_name"] == "custom-dbt-job"
    assert summary["environment"] == "staging"


def test_main_dry_run_full_run_results(tmp_path, capsys):
    module = load_module()
    data = _make_run_results(
        elapsed_time=77.25,
        results=[
            _model_result("silver_market_event_minute_aggregates", rows_affected=13),
            _model_result("gold_market_event_daily_aggregates", rows_affected=7),
            _test_result("not_null_silver_symbol", "pass"),
            _test_result("not_null_gold_symbol", "pass"),
        ],
    )
    f = tmp_path / "run_results.json"
    f.write_text(json.dumps(data))

    module.main(
        [
            "--run-results-path", str(f),
            "--project-id", PROJECT_ID,
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert summary["models"]["total"] == 2
    assert summary["models"]["success"] == 2
    assert summary["tests"]["total"] == 2
    assert summary["tests"]["pass"] == 2
    assert summary["tests"]["pass_rate"] == 100.0
    assert summary["elapsed_time_seconds"] == 77.25
    assert summary["parse_error_count"] == 0


# ---------------------------------------------------------------------------
# push_time_series — subprocess and urllib mocked
# ---------------------------------------------------------------------------


def test_push_calls_gcloud_auth(monkeypatch):
    module = load_module()
    subprocess_calls: list[list] = []
    urlopen_requests: list = []

    def fake_run(args, **kwargs):
        subprocess_calls.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="tok\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda req: (urlopen_requests.append(req), _FakeResponse())[1],
    )

    module.push_time_series(
        [
            {
                "metric": {"type": "custom.googleapis.com/rtdp/dbt/dbt_run_success_count"},
                "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
                "metricKind": "GAUGE",
                "valueType": "INT64",
                "points": [{"interval": {"endTime": "2026-05-22T12:00:00Z"},
                             "value": {"int64Value": "2"}}],
            }
        ]
    )

    assert len(subprocess_calls) == 1
    assert subprocess_calls[0] == ["gcloud", "auth", "print-access-token"]
    assert len(urlopen_requests) == 1
    assert "monitoring.googleapis.com" in urlopen_requests[0].full_url
    assert PROJECT_ID in urlopen_requests[0].full_url


def test_push_token_in_authorization_header_not_in_subprocess_args(monkeypatch):
    module = load_module()

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="my_secret_token_xyz\n", stderr=""
        )

    captured_req: list = []
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda req: (captured_req.append(req), _FakeResponse())[1],
    )

    ts = [
        {
            "metric": {"type": "custom.googleapis.com/rtdp/dbt/dbt_run_success_count"},
            "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
            "metricKind": "GAUGE",
            "valueType": "INT64",
            "points": [{"interval": {"endTime": "2026-05-22T12:00:00Z"},
                        "value": {"int64Value": "1"}}],
        }
    ]
    module.push_time_series(ts)

    assert captured_req[0].get_header("Authorization") == "Bearer my_secret_token_xyz"
    # Token must not appear in any subprocess call args
    # (no subprocess call has the token since gcloud only returns it on stdout)
    assert "my_secret_token_xyz" not in str(module.subprocess.run.__name__)


def test_push_empty_list_skips_subprocess(monkeypatch):
    module = load_module()
    calls: list = []
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: calls.append(a))

    module.push_time_series([])

    assert len(calls) == 0


def test_push_raises_on_gcloud_failure(monkeypatch):
    module = load_module()

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=1, stdout="", stderr="auth error"
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    try:
        module.push_time_series(
            [
                {
                    "metric": {"type": "custom.googleapis.com/rtdp/dbt/dbt_run_success_count"},
                    "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
                    "metricKind": "GAUGE",
                    "valueType": "INT64",
                    "points": [{"interval": {"endTime": "2026-05-22T12:00:00Z"},
                                "value": {"int64Value": "1"}}],
                }
            ]
        )
    except RuntimeError as exc:
        assert "gcloud auth print-access-token failed" in str(exc)
        assert "auth error" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_push_raises_on_http_error(monkeypatch):
    module = load_module()
    monkeypatch.setattr(module.subprocess, "run", _gcloud_ok)

    def fake_urlopen(req):
        raise urllib.error.HTTPError(
            url=req.full_url, code=403, msg="Forbidden", hdrs={}, fp=io.BytesIO(b"")
        )

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    try:
        module.push_time_series(
            [
                {
                    "metric": {"type": "custom.googleapis.com/rtdp/dbt/dbt_run_success_count"},
                    "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
                    "metricKind": "GAUGE",
                    "valueType": "INT64",
                    "points": [{"interval": {"endTime": "2026-05-22T12:00:00Z"},
                                "value": {"int64Value": "1"}}],
                }
            ]
        )
    except RuntimeError as exc:
        assert "Cloud Monitoring push failed" in str(exc)
        assert "403" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_push_raises_on_url_error(monkeypatch):
    module = load_module()
    monkeypatch.setattr(module.subprocess, "run", _gcloud_ok)

    def fake_urlopen(req):
        raise urllib.error.URLError(reason="connection refused")

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    try:
        module.push_time_series(
            [
                {
                    "metric": {"type": "custom.googleapis.com/rtdp/dbt/dbt_run_success_count"},
                    "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
                    "metricKind": "GAUGE",
                    "valueType": "INT64",
                    "points": [{"interval": {"endTime": "2026-05-22T12:00:00Z"},
                                "value": {"int64Value": "1"}}],
                }
            ]
        )
    except RuntimeError as exc:
        assert "Cloud Monitoring push failed" in str(exc)
        assert "connection refused" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


# ---------------------------------------------------------------------------
# No secrets printed
# ---------------------------------------------------------------------------


def test_no_secrets_in_stdout_during_dry_run(monkeypatch, capsys, tmp_path):
    module = load_module()
    fake_token = "super_secret_gcp_token_abc999"

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(
            args=args, returncode=0, stdout=f"{fake_token}\n", stderr=""
        ),
    )
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda req: _FakeResponse())

    f = tmp_path / "run_results.json"
    f.write_text(json.dumps(_make_run_results()))

    module.main(
        [
            "--run-results-path", str(f),
            "--project-id", PROJECT_ID,
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert fake_token not in captured.out
    assert fake_token not in captured.err
