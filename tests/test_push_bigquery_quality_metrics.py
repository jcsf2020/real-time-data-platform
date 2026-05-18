"""Tests for scripts/push_bigquery_quality_metrics.py."""

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

SCRIPT = Path(__file__).parent.parent / "scripts" / "push_bigquery_quality_metrics.py"

FIXED_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
PROJECT_ID = "project-42987e01-2123-446b-ac7"


class _FakeResponse:
    """Minimal context manager mimicking a successful urllib.request.urlopen response."""

    def __init__(self, body: bytes = b"{}"):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _gcloud_ok(args, **kwargs):
    """Fake subprocess.run that succeeds for gcloud auth print-access-token."""
    return subprocess.CompletedProcess(
        args=args, returncode=0, stdout="fake_token\n", stderr=""
    )


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("push_bigquery_quality_metrics", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_report(
    *,
    status: str = "ok",
    failed_checks: list[str] | None = None,
    checks: list[dict] | None = None,
) -> dict:
    if failed_checks is None:
        failed_checks = []
    if checks is None:
        checks = [
            {
                "name": "row_count_minimum",
                "status": "pass",
                "observed": 6120,
                "expected": "row_count >= 1",
                "sql": "SELECT COUNT(*) AS row_count FROM t",
            },
            {
                "name": "row_count_positive",
                "status": "pass",
                "observed": 6120,
                "expected": "row_count > 0",
                "sql": "SELECT COUNT(*) AS row_count FROM t",
            },
        ]
    return {
        "status": status,
        "failed_checks": failed_checks,
        "checks": checks,
        "generated_at_utc": "2026-05-18T12:00:00+00:00",
        "project_id": PROJECT_ID,
        "dataset": "rtdp_analytics",
        "table": "market_events_raw",
    }


def _ts_by_type(time_series: list[dict], metric_suffix: str) -> list[dict]:
    return [
        ts for ts in time_series
        if ts["metric"]["type"].endswith(f"/{metric_suffix}")
    ]


# ---------------------------------------------------------------------------
# build_time_series — status metric
# ---------------------------------------------------------------------------


def test_status_ok_emits_value_1():
    module = load_module()
    report = _make_report(status="ok")

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)

    status_ts = _ts_by_type(ts_list, "status")
    assert len(status_ts) == 1
    assert status_ts[0]["points"][0]["value"]["int64Value"] == "1"
    assert status_ts[0]["metricKind"] == "GAUGE"
    assert status_ts[0]["valueType"] == "INT64"


def test_status_error_emits_value_0():
    module = load_module()
    report = _make_report(status="error", failed_checks=["row_count_minimum"])

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)

    status_ts = _ts_by_type(ts_list, "status")
    assert len(status_ts) == 1
    assert status_ts[0]["points"][0]["value"]["int64Value"] == "0"


def test_status_missing_treated_as_error():
    module = load_module()
    report = _make_report()
    del report["status"]

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)

    status_ts = _ts_by_type(ts_list, "status")
    assert status_ts[0]["points"][0]["value"]["int64Value"] == "0"


# ---------------------------------------------------------------------------
# build_time_series — failed_checks_count metric
# ---------------------------------------------------------------------------


def test_failed_checks_count_zero_when_all_pass():
    module = load_module()
    report = _make_report(status="ok", failed_checks=[])

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)

    fc_ts = _ts_by_type(ts_list, "failed_checks_count")
    assert len(fc_ts) == 1
    assert fc_ts[0]["points"][0]["value"]["int64Value"] == "0"


def test_failed_checks_count_reflects_failure_list():
    module = load_module()
    report = _make_report(
        status="error",
        failed_checks=["row_count_minimum", "event_id_unique"],
        checks=[
            {"name": "row_count_minimum", "status": "fail", "observed": 0, "expected": ">=1", "sql": ""},
            {"name": "event_id_unique", "status": "fail", "observed": 3, "expected": "==0", "sql": ""},
        ],
    )

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)

    fc_ts = _ts_by_type(ts_list, "failed_checks_count")
    assert fc_ts[0]["points"][0]["value"]["int64Value"] == "2"


# ---------------------------------------------------------------------------
# build_time_series — check_pass metric
# ---------------------------------------------------------------------------


def test_check_pass_emitted_for_each_check():
    module = load_module()
    checks = [
        {"name": "row_count_minimum", "status": "pass", "observed": 100, "expected": ">=1", "sql": ""},
        {"name": "event_id_unique", "status": "fail", "observed": 1, "expected": "==0", "sql": ""},
        {"name": "freshness_available", "status": "pass", "observed": {}, "expected": ">0", "sql": ""},
    ]
    report = _make_report(checks=checks)

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)

    cp_ts = _ts_by_type(ts_list, "check_pass")
    assert len(cp_ts) == 3

    by_name = {ts["metric"]["labels"]["check_name"]: ts for ts in cp_ts}
    assert set(by_name.keys()) == {"row_count_minimum", "event_id_unique", "freshness_available"}

    assert by_name["row_count_minimum"]["points"][0]["value"]["int64Value"] == "1"
    assert by_name["event_id_unique"]["points"][0]["value"]["int64Value"] == "0"
    assert by_name["freshness_available"]["points"][0]["value"]["int64Value"] == "1"


def test_check_pass_metric_kind_and_type():
    module = load_module()
    checks = [
        {"name": "row_count_minimum", "status": "pass", "observed": 50, "expected": ">=1", "sql": ""},
    ]
    report = _make_report(checks=checks)

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)

    cp_ts = _ts_by_type(ts_list, "check_pass")
    assert cp_ts[0]["metricKind"] == "GAUGE"
    assert cp_ts[0]["valueType"] == "INT64"
    assert cp_ts[0]["metric"]["type"] == "custom.googleapis.com/rtdp/bigquery_quality/check_pass"


# ---------------------------------------------------------------------------
# extract_row_count
# ---------------------------------------------------------------------------


def test_row_count_from_row_count_minimum():
    module = load_module()
    report = _make_report(
        checks=[
            {"name": "row_count_minimum", "status": "pass", "observed": 9999, "expected": ">=1", "sql": ""},
            {"name": "row_count_positive", "status": "pass", "observed": 9999, "expected": ">0", "sql": ""},
        ]
    )

    assert module.extract_row_count(report) == 9999

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)
    rc_ts = _ts_by_type(ts_list, "row_count")
    assert len(rc_ts) == 1
    assert rc_ts[0]["points"][0]["value"]["int64Value"] == "9999"


def test_row_count_fallback_from_row_count_positive():
    module = load_module()
    report = _make_report(
        checks=[
            {"name": "row_count_positive", "status": "pass", "observed": 4321, "expected": ">0", "sql": ""},
        ]
    )

    assert module.extract_row_count(report) == 4321

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)
    rc_ts = _ts_by_type(ts_list, "row_count")
    assert len(rc_ts) == 1
    assert rc_ts[0]["points"][0]["value"]["int64Value"] == "4321"


def test_row_count_absent_when_no_matching_check():
    module = load_module()
    report = _make_report(
        checks=[
            {"name": "event_id_unique", "status": "pass", "observed": 0, "expected": "==0", "sql": ""},
        ]
    )

    assert module.extract_row_count(report) is None

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)
    rc_ts = _ts_by_type(ts_list, "row_count")
    assert len(rc_ts) == 0


# ---------------------------------------------------------------------------
# extract_freshness_age_hours
# ---------------------------------------------------------------------------


def test_freshness_age_hours_emitted_when_available():
    module = load_module()
    report = _make_report(
        checks=[
            {
                "name": "freshness_max_age_hours",
                "status": "pass",
                "observed": {"max_ingest_timestamp": "2026-05-18T11:00:00Z", "age_hours": 1.5},
                "expected": "age_hours <= 24",
                "sql": "",
            },
        ]
    )

    assert module.extract_freshness_age_hours(report) == 1.5

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)
    fah_ts = _ts_by_type(ts_list, "freshness_age_hours")
    assert len(fah_ts) == 1
    assert fah_ts[0]["points"][0]["value"]["doubleValue"] == 1.5
    assert fah_ts[0]["valueType"] == "DOUBLE"
    assert fah_ts[0]["metricKind"] == "GAUGE"


def test_freshness_age_hours_omitted_when_check_absent():
    module = load_module()
    report = _make_report(
        checks=[
            {"name": "row_count_minimum", "status": "pass", "observed": 100, "expected": ">=1", "sql": ""},
        ]
    )

    assert module.extract_freshness_age_hours(report) is None

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)
    fah_ts = _ts_by_type(ts_list, "freshness_age_hours")
    assert len(fah_ts) == 0


def test_freshness_age_hours_omitted_when_age_is_none():
    module = load_module()
    report = _make_report(
        checks=[
            {
                "name": "freshness_max_age_hours",
                "status": "fail",
                "observed": {"max_ingest_timestamp": None, "age_hours": None},
                "expected": "age_hours <= 24",
                "sql": "",
            },
        ]
    )

    assert module.extract_freshness_age_hours(report) is None

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)
    fah_ts = _ts_by_type(ts_list, "freshness_age_hours")
    assert len(fah_ts) == 0


# ---------------------------------------------------------------------------
# resource labels and timestamp
# ---------------------------------------------------------------------------


def test_time_series_resource_has_project_id():
    module = load_module()
    report = _make_report()

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)

    for ts in ts_list:
        assert ts["resource"]["type"] == "global"
        assert ts["resource"]["labels"]["project_id"] == PROJECT_ID


def test_time_series_end_time_matches_now():
    module = load_module()
    report = _make_report()

    ts_list = module.build_time_series(report, PROJECT_ID, FIXED_NOW)

    for ts in ts_list:
        assert ts["points"][0]["interval"]["endTime"] == "2026-05-18T12:00:00Z"


# ---------------------------------------------------------------------------
# push_time_series — subprocess.run mocked
# ---------------------------------------------------------------------------


def test_push_time_series_calls_gcloud_auth_then_urlopen(monkeypatch):
    module = load_module()

    subprocess_calls: list[list] = []
    urlopen_requests: list = []

    def fake_run(args, **kwargs):
        subprocess_calls.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="fake_token\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda req: (urlopen_requests.append(req), _FakeResponse())[1])

    time_series = [
        {
            "metric": {"type": "custom.googleapis.com/rtdp/bigquery_quality/status"},
            "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
            "metricKind": "GAUGE",
            "valueType": "INT64",
            "points": [{"interval": {"endTime": "2026-05-18T12:00:00Z"}, "value": {"int64Value": "1"}}],
        }
    ]

    module.push_time_series(time_series)

    assert len(subprocess_calls) == 1
    assert subprocess_calls[0] == ["gcloud", "auth", "print-access-token"]

    assert len(urlopen_requests) == 1
    req = urlopen_requests[0]
    assert "monitoring.googleapis.com" in req.full_url
    assert PROJECT_ID in req.full_url
    assert req.get_header("Authorization") == "Bearer fake_token"
    assert req.get_header("Content-type") == "application/json"


def test_push_time_series_token_not_in_subprocess_args(monkeypatch):
    module = load_module()

    subprocess_calls: list[list] = []

    def fake_run(args, **kwargs):
        subprocess_calls.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="secret_bearer_token\n", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda req: _FakeResponse())

    time_series = [
        {
            "metric": {"type": "custom.googleapis.com/rtdp/bigquery_quality/status"},
            "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
            "metricKind": "GAUGE",
            "valueType": "INT64",
            "points": [{"interval": {"endTime": "2026-05-18T12:00:00Z"}, "value": {"int64Value": "1"}}],
        }
    ]

    module.push_time_series(time_series)

    for call_args in subprocess_calls:
        for arg in call_args:
            assert "secret_bearer_token" not in str(arg)


def test_push_time_series_empty_list_skips_subprocess(monkeypatch):
    module = load_module()

    calls: list = []
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: calls.append(a))

    module.push_time_series([])

    assert len(calls) == 0


def test_push_time_series_raises_on_gcloud_failure(monkeypatch):
    module = load_module()

    def fake_run(args, **kwargs):
        if args[0] == "gcloud":
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="auth error")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    time_series = [
        {
            "metric": {"type": "custom.googleapis.com/rtdp/bigquery_quality/status"},
            "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
            "metricKind": "GAUGE",
            "valueType": "INT64",
            "points": [{"interval": {"endTime": "2026-05-18T12:00:00Z"}, "value": {"int64Value": "1"}}],
        }
    ]

    try:
        module.push_time_series(time_series)
    except RuntimeError as exc:
        assert "gcloud auth print-access-token failed" in str(exc)
        assert "auth error" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_push_time_series_raises_on_http_error(monkeypatch):
    module = load_module()

    monkeypatch.setattr(module.subprocess, "run", _gcloud_ok)

    def fake_urlopen(req):
        raise urllib.error.HTTPError(
            url=req.full_url, code=403, msg="Forbidden", hdrs={}, fp=io.BytesIO(b"")
        )

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    time_series = [
        {
            "metric": {"type": "custom.googleapis.com/rtdp/bigquery_quality/status"},
            "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
            "metricKind": "GAUGE",
            "valueType": "INT64",
            "points": [{"interval": {"endTime": "2026-05-18T12:00:00Z"}, "value": {"int64Value": "1"}}],
        }
    ]

    try:
        module.push_time_series(time_series)
    except RuntimeError as exc:
        assert "Cloud Monitoring push failed" in str(exc)
        assert "403" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_push_time_series_raises_on_url_error(monkeypatch):
    module = load_module()

    monkeypatch.setattr(module.subprocess, "run", _gcloud_ok)

    def fake_urlopen(req):
        raise urllib.error.URLError(reason="connection refused")

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    time_series = [
        {
            "metric": {"type": "custom.googleapis.com/rtdp/bigquery_quality/status"},
            "resource": {"type": "global", "labels": {"project_id": PROJECT_ID}},
            "metricKind": "GAUGE",
            "valueType": "INT64",
            "points": [{"interval": {"endTime": "2026-05-18T12:00:00Z"}, "value": {"int64Value": "1"}}],
        }
    ]

    try:
        module.push_time_series(time_series)
    except RuntimeError as exc:
        assert "Cloud Monitoring push failed" in str(exc)
        assert "connection refused" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


# ---------------------------------------------------------------------------
# no secrets printed
# ---------------------------------------------------------------------------


def test_no_secrets_printed(monkeypatch, capsys, tmp_path):
    module = load_module()

    fake_token = "super_secret_access_token_xyz987"

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(
            args=args, returncode=0, stdout=f"{fake_token}\n", stderr=""
        ),
    )
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda req: _FakeResponse())

    report = _make_report()
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(report))

    module.main(["--report-path", str(report_file), "--project-id", PROJECT_ID])

    captured = capsys.readouterr()
    assert fake_token not in captured.out
    assert fake_token not in captured.err


# ---------------------------------------------------------------------------
# main exit codes
# ---------------------------------------------------------------------------


def test_main_exits_0_on_successful_push(monkeypatch, tmp_path):
    module = load_module()

    monkeypatch.setattr(module.subprocess, "run", _gcloud_ok)
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda req: _FakeResponse())

    report = _make_report(status="ok")
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(report))

    result = module.main(["--report-path", str(report_file), "--project-id", PROJECT_ID])

    assert result == 0


def test_main_exits_0_on_error_status_report(monkeypatch, tmp_path):
    module = load_module()

    monkeypatch.setattr(module.subprocess, "run", _gcloud_ok)
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda req: _FakeResponse())

    report = _make_report(status="error", failed_checks=["row_count_minimum"])
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(report))

    result = module.main(["--report-path", str(report_file), "--project-id", PROJECT_ID])

    assert result == 0


def test_main_exits_nonzero_on_missing_report_path(tmp_path):
    module = load_module()

    missing = tmp_path / "does_not_exist.json"
    result = module.main(["--report-path", str(missing), "--project-id", PROJECT_ID])

    assert result != 0


def test_main_exits_nonzero_on_invalid_json(tmp_path):
    module = load_module()

    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not valid json {{")

    result = module.main(["--report-path", str(bad_file), "--project-id", PROJECT_ID])

    assert result != 0


def test_main_exits_nonzero_on_push_failure(monkeypatch, tmp_path):
    module = load_module()

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(
            args=args, returncode=1, stdout="", stderr="auth failed"
        ),
    )

    report = _make_report()
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(report))

    result = module.main(["--report-path", str(report_file), "--project-id", PROJECT_ID])

    assert result != 0


# ---------------------------------------------------------------------------
# load_report
# ---------------------------------------------------------------------------


def test_load_report_parses_valid_json(tmp_path):
    module = load_module()

    data = {"status": "ok", "checks": []}
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(data))

    result = module.load_report(str(report_file))

    assert result == data


def test_load_report_raises_on_missing_file(tmp_path):
    module = load_module()

    missing = tmp_path / "missing.json"

    try:
        module.load_report(str(missing))
    except FileNotFoundError as exc:
        assert "not found" in str(exc).lower()
    else:
        raise AssertionError("Expected FileNotFoundError")
