#!/usr/bin/env python3
"""Push BigQuery quality check results as custom metrics to Cloud Monitoring.

Reads the JSON quality report produced by run_bigquery_quality_checks.py and
emits five custom metrics to Cloud Monitoring via the REST API.

Usage:
  python3 scripts/push_bigquery_quality_metrics.py \
    --report-path docs/evidence/bigquery-quality-checks/ci-report.json \
    --project-id project-42987e01-2123-446b-ac7

Safety:
- Does not re-run BigQuery checks.
- Does not query BigQuery.
- Does not connect to Cloud SQL.
- Does not print secrets or credentials.
- Reads only the JSON report file specified by --report-path.

gcloud monitoring time-series create is not available in the stable gcloud CLI.
Live validation will confirm whether direct gcloud CLI write support is available
in the installed version. This script uses the Cloud Monitoring REST API via
urllib.request to avoid new Python package dependencies and to avoid exposing the
access token in process arguments.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


METRIC_PREFIX = "custom.googleapis.com/rtdp/bigquery_quality"


def load_report(path: str) -> dict[str, Any]:
    """Load and parse the JSON quality report from the given file path."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Report file not found: {path}")
    return json.loads(p.read_text())


def extract_row_count(report: dict[str, Any]) -> int | None:
    """Return observed row count from row_count_minimum or row_count_positive check.

    Prefers row_count_minimum (always present). Falls back to row_count_positive.
    Returns None if neither check appears in the report.
    """
    checks_by_name = {c["name"]: c for c in report.get("checks", [])}
    for name in ("row_count_minimum", "row_count_positive"):
        check = checks_by_name.get(name)
        if check is not None:
            observed = check.get("observed")
            if isinstance(observed, (int, float)):
                return int(observed)
    return None


def extract_freshness_age_hours(report: dict[str, Any]) -> float | None:
    """Return age_hours from the freshness_max_age_hours check when present.

    Returns None if the check is absent or age_hours is not available (e.g. table empty).
    """
    checks_by_name = {c["name"]: c for c in report.get("checks", [])}
    check = checks_by_name.get("freshness_max_age_hours")
    if check is None:
        return None
    observed = check.get("observed") or {}
    age = observed.get("age_hours")
    if age is None:
        return None
    return float(age)


def _make_point(
    now: datetime,
    *,
    int_value: int | None = None,
    double_value: float | None = None,
) -> dict[str, Any]:
    end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if int_value is not None:
        value: dict[str, Any] = {"int64Value": str(int_value)}
    else:
        value = {"doubleValue": double_value}
    return {"interval": {"endTime": end_time}, "value": value}


def _make_time_series(
    metric_type: str,
    project_id: str,
    point: dict[str, Any],
    *,
    metric_labels: dict[str, str] | None = None,
    value_type: str = "INT64",
) -> dict[str, Any]:
    metric: dict[str, Any] = {"type": metric_type}
    if metric_labels:
        metric["labels"] = metric_labels
    return {
        "metric": metric,
        "resource": {
            "type": "global",
            "labels": {"project_id": project_id},
        },
        "metricKind": "GAUGE",
        "valueType": value_type,
        "points": [point],
    }


def build_time_series(
    report: dict[str, Any],
    project_id: str,
    now: datetime,
) -> list[dict[str, Any]]:
    """Build Cloud Monitoring time series payloads from the quality report.

    Returns a list of time series dicts ready for the Cloud Monitoring REST API.
    Does not query BigQuery or any external service.
    """
    time_series: list[dict[str, Any]] = []

    status_value = 1 if report.get("status") == "ok" else 0
    time_series.append(
        _make_time_series(
            f"{METRIC_PREFIX}/status",
            project_id,
            _make_point(now, int_value=status_value),
        )
    )

    failed_count = len(report.get("failed_checks", []))
    time_series.append(
        _make_time_series(
            f"{METRIC_PREFIX}/failed_checks_count",
            project_id,
            _make_point(now, int_value=failed_count),
        )
    )

    for check in report.get("checks", []):
        check_value = 1 if check.get("status") == "pass" else 0
        time_series.append(
            _make_time_series(
                f"{METRIC_PREFIX}/check_pass",
                project_id,
                _make_point(now, int_value=check_value),
                metric_labels={"check_name": check["name"]},
            )
        )

    row_count = extract_row_count(report)
    if row_count is not None:
        time_series.append(
            _make_time_series(
                f"{METRIC_PREFIX}/row_count",
                project_id,
                _make_point(now, int_value=row_count),
            )
        )

    age_hours = extract_freshness_age_hours(report)
    if age_hours is not None:
        time_series.append(
            _make_time_series(
                f"{METRIC_PREFIX}/freshness_age_hours",
                project_id,
                _make_point(now, double_value=age_hours),
                value_type="DOUBLE",
            )
        )

    return time_series


def push_time_series(time_series: list[dict[str, Any]]) -> None:
    """Push time series to Cloud Monitoring via the REST API.

    Obtains a short-lived access token via gcloud (one subprocess call), then
    sends the payload using urllib.request in-process. The token is carried in
    an HTTP Authorization header in memory and is never exposed in process
    arguments or printed to stdout/stderr.

    Uses Cloud Monitoring REST API via urllib.request to avoid new Python package
    dependencies and to avoid token exposure in process arguments.

    gcloud monitoring time-series create is not available in the stable gcloud CLI.
    Live validation will confirm whether direct gcloud CLI support becomes available.
    """
    if not time_series:
        return

    project_id = time_series[0]["resource"]["labels"]["project_id"]

    token_result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=False,
    )
    if token_result.returncode != 0:
        raise RuntimeError(
            f"gcloud auth print-access-token failed: {token_result.stderr.strip()}"
        )
    token = token_result.stdout.strip()

    url = f"https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries"
    payload_bytes = json.dumps({"timeSeries": time_series}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Cloud Monitoring push failed: HTTP {exc.code} {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Cloud Monitoring push failed: {exc.reason}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Push BigQuery quality metrics to Cloud Monitoring.",
    )
    parser.add_argument("--report-path", required=True, help="Path to the JSON quality report.")
    parser.add_argument("--project-id", required=True, help="GCP project ID.")
    args = parser.parse_args(argv)

    try:
        report = load_report(args.report_path)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    now = datetime.now(UTC)
    time_series = build_time_series(report, args.project_id, now)

    try:
        push_time_series(time_series)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Pushed {len(time_series)} time series to Cloud Monitoring.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
