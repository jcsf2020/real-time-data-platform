#!/usr/bin/env python3
"""Parse dbt run_results.json and emit Cloud Monitoring metrics.

Parses the dbt artifact produced after a dbt run and emits custom metrics to
Cloud Monitoring for observability of the dbt transformation layer.

Usage:
  python3 scripts/push_dbt_metrics.py \
    --run-results-path dbt/target/run_results.json \
    --project-id project-42987e01-2123-446b-ac7 \
    --location europe-west1 \
    --job-name rtdp-dbt-refresh-job \
    --environment cloud_sql_prod \
    --dry-run

Safety:
- --dry-run skips all Cloud Monitoring writes.
- Tests must use --dry-run or call pure functions only.
- Does not connect to Cloud SQL.
- Does not run dbt.
- Does not print secrets or credentials.

Cloud Monitoring write code is isolated in push_time_series() and is never
called when --dry-run is set.

gcloud monitoring time-series create is not available in the stable gcloud CLI.
This script uses the Cloud Monitoring REST API via urllib.request to avoid new
Python package dependencies and to avoid exposing the access token in process
arguments, following the same pattern as push_bigquery_quality_metrics.py.
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


METRIC_PREFIX = "custom.googleapis.com/rtdp/dbt"

_NODE_TYPE_PREFIXES = (
    ("model.", "model"),
    ("test.", "test"),
    ("seed.", "seed"),
    ("snapshot.", "snapshot"),
    ("source.", "source"),
    ("exposure.", "exposure"),
    ("metric.", "metric"),
    ("analysis.", "analysis"),
)


def _infer_node_type(unique_id: str) -> str:
    for prefix, node_type in _NODE_TYPE_PREFIXES:
        if unique_id.startswith(prefix):
            return node_type
    return "unknown"


def _extract_name(unique_id: str) -> str:
    """Return the node name from a dbt unique_id of the form type.project.name."""
    parts = unique_id.split(".", 2)
    return parts[2] if len(parts) >= 3 else unique_id


def load_run_results(path: str) -> dict[str, Any]:
    """Load and parse run_results.json from the given file path."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"run_results.json not found: {path}")
    return json.loads(p.read_text())


def parse_run_results(data: dict[str, Any]) -> dict[str, Any]:
    """Extract structured metrics from parsed run_results.json data.

    Returns a dict with:
      elapsed_time      float   Total run wall-clock time from the artifact.
      invocation_id     str|None
      generated_at      str|None  ISO timestamp from metadata.
      nodes             list[dict]  Per-node results (unique_id, node_type, name,
                                    status, execution_time, rows_affected).
      parse_error_count int   Count of individual node parse failures.
    """
    nodes: list[dict[str, Any]] = []
    parse_errors = 0

    try:
        elapsed_time = float(data.get("elapsed_time") or 0.0)
    except (TypeError, ValueError):
        elapsed_time = 0.0

    metadata: dict[str, Any] = data.get("metadata") or {}
    generated_at: str | None = metadata.get("generated_at")

    # invocation_id may appear in metadata (dbt >=1.x) or args (some versions)
    invocation_id: str | None = (
        metadata.get("invocation_id")
        or (data.get("args") or {}).get("invocation_id")
        or data.get("invocation_id")
    )

    for result in data.get("results") or []:
        try:
            unique_id: str = result.get("unique_id") or ""
            node_type = _infer_node_type(unique_id)
            name = _extract_name(unique_id)
            status: str = str(result.get("status") or "").lower()

            try:
                execution_time = float(result.get("execution_time") or 0.0)
            except (TypeError, ValueError):
                execution_time = 0.0

            adapter_response: dict[str, Any] = result.get("adapter_response") or {}
            raw_rows = adapter_response.get("rows_affected")
            rows_affected: int | None = None if raw_rows is None else int(raw_rows)

            nodes.append(
                {
                    "unique_id": unique_id,
                    "node_type": node_type,
                    "name": name,
                    "status": status,
                    "execution_time": execution_time,
                    "rows_affected": rows_affected,
                }
            )
        except Exception:  # noqa: BLE001
            parse_errors += 1

    return {
        "elapsed_time": elapsed_time,
        "invocation_id": invocation_id,
        "generated_at": generated_at,
        "nodes": nodes,
        "parse_error_count": parse_errors,
    }


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
    parsed: dict[str, Any],
    project_id: str,
    job_name: str,
    environment: str,
    now: datetime,
) -> list[dict[str, Any]]:
    """Build Cloud Monitoring time series payloads from parsed run_results data.

    Returns a list of time series dicts ready for the Cloud Monitoring REST API.
    Does not call Cloud Monitoring or any external service.
    """
    nodes: list[dict[str, Any]] = parsed.get("nodes") or []
    model_nodes = [n for n in nodes if n["node_type"] == "model"]
    test_nodes = [n for n in nodes if n["node_type"] == "test"]

    base_labels: dict[str, str] = {"job_name": job_name, "environment": environment}
    model_labels: dict[str, str] = {**base_labels, "node_type": "model"}
    test_labels: dict[str, str] = {**base_labels, "node_type": "test"}

    time_series: list[dict[str, Any]] = []
    point = _make_point  # local alias

    # --- model-level summary metrics ---

    run_success = sum(1 for n in model_nodes if n["status"] == "success")
    time_series.append(
        _make_time_series(
            f"{METRIC_PREFIX}/dbt_run_success_count",
            project_id,
            point(now, int_value=run_success),
            metric_labels=model_labels,
        )
    )

    run_failure = sum(1 for n in model_nodes if n["status"] == "error")
    time_series.append(
        _make_time_series(
            f"{METRIC_PREFIX}/dbt_run_failure_count",
            project_id,
            point(now, int_value=run_failure),
            metric_labels=model_labels,
        )
    )

    # --- run-level metric ---

    elapsed_time: float = parsed.get("elapsed_time") or 0.0
    time_series.append(
        _make_time_series(
            f"{METRIC_PREFIX}/dbt_run_duration_seconds",
            project_id,
            point(now, double_value=elapsed_time),
            metric_labels=base_labels,
            value_type="DOUBLE",
        )
    )

    # --- test-level summary metrics ---

    test_pass = sum(1 for n in test_nodes if n["status"] == "pass")
    time_series.append(
        _make_time_series(
            f"{METRIC_PREFIX}/dbt_test_pass_count",
            project_id,
            point(now, int_value=test_pass),
            metric_labels=test_labels,
        )
    )

    test_fail = sum(1 for n in test_nodes if n["status"] in ("fail", "error"))
    time_series.append(
        _make_time_series(
            f"{METRIC_PREFIX}/dbt_test_failure_count",
            project_id,
            point(now, int_value=test_fail),
            metric_labels=test_labels,
        )
    )

    total_tests = test_pass + test_fail
    pass_rate = (test_pass / total_tests * 100.0) if total_tests > 0 else 0.0
    time_series.append(
        _make_time_series(
            f"{METRIC_PREFIX}/dbt_test_pass_rate",
            project_id,
            point(now, double_value=pass_rate),
            metric_labels=test_labels,
            value_type="DOUBLE",
        )
    )

    # --- per-model row count metrics ---

    for node in model_nodes:
        rows = node.get("rows_affected")
        if rows is not None:
            time_series.append(
                _make_time_series(
                    f"{METRIC_PREFIX}/dbt_model_rows_total",
                    project_id,
                    point(now, int_value=rows),
                    metric_labels={**model_labels, "model_name": node["name"]},
                )
            )

    # --- script health metric ---

    parse_errors: int = parsed.get("parse_error_count") or 0
    time_series.append(
        _make_time_series(
            f"{METRIC_PREFIX}/dbt_artifact_parse_error_count",
            project_id,
            point(now, int_value=parse_errors),
            metric_labels=base_labels,
        )
    )

    return time_series


def build_summary(
    parsed: dict[str, Any],
    job_name: str,
    environment: str,
    metrics_count: int,
    dry_run: bool,
    now: datetime,
) -> dict[str, Any]:
    """Build a JSON summary dict suitable for CI artifact output."""
    nodes: list[dict[str, Any]] = parsed.get("nodes") or []
    model_nodes = [n for n in nodes if n["node_type"] == "model"]
    test_nodes = [n for n in nodes if n["node_type"] == "test"]

    test_pass = sum(1 for n in test_nodes if n["status"] == "pass")
    test_fail = sum(1 for n in test_nodes if n["status"] in ("fail", "error"))
    total_tests = test_pass + test_fail
    pass_rate = (test_pass / total_tests * 100.0) if total_tests > 0 else 0.0

    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "job_name": job_name,
        "environment": environment,
        "invocation_id": parsed.get("invocation_id"),
        "artifact_generated_at": parsed.get("generated_at"),
        "elapsed_time_seconds": parsed.get("elapsed_time") or 0.0,
        "models": {
            "total": len(model_nodes),
            "success": sum(1 for n in model_nodes if n["status"] == "success"),
            "error": sum(1 for n in model_nodes if n["status"] == "error"),
            "skipped": sum(1 for n in model_nodes if n["status"] == "skipped"),
            "warn": sum(1 for n in model_nodes if n["status"] == "warn"),
        },
        "tests": {
            "total": len(test_nodes),
            "pass": test_pass,
            "fail": test_fail,
            "warn": sum(1 for n in test_nodes if n["status"] == "warn"),
            "skipped": sum(1 for n in test_nodes if n["status"] == "skipped"),
            "pass_rate": pass_rate,
        },
        "parse_error_count": parsed.get("parse_error_count") or 0,
        "metrics_emitted": metrics_count,
        "dry_run": dry_run,
    }


def _get_metadata_token(timeout: float = 2.0) -> str:
    """Return an ADC token from the GCP instance metadata server.

    Only works inside GCP runtimes (Cloud Run, GCE, GKE). Raises RuntimeError
    if the server is unreachable or returns an unparseable response — callers
    in auto mode should catch this and fall back to gcloud.
    """
    url = (
        "http://metadata.google.internal"
        "/computeMetadata/v1/instance/service-accounts/default/token"
    )
    req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Metadata server token acquisition failed: {exc}") from exc
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Metadata server token acquisition failed: missing access_token")
    return token


def _get_gcloud_token() -> str:
    """Return an access token via gcloud CLI (local development only)."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"gcloud auth print-access-token failed: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"gcloud auth print-access-token failed: {result.stderr.strip()}"
        )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("gcloud auth print-access-token failed: empty token")
    return token


def _get_token(auth_mode: str) -> str:
    """Acquire an access token using the specified auth mode.

    'metadata' — GCP metadata server; works in Cloud Run without gcloud in image.
    'gcloud'   — gcloud CLI subprocess; works locally with gcloud auth login.
    'auto'     — metadata first, gcloud fallback.
    """
    if auth_mode == "metadata":
        return _get_metadata_token()
    if auth_mode == "gcloud":
        return _get_gcloud_token()
    if auth_mode == "auto":
        try:
            return _get_metadata_token()
        except RuntimeError:
            return _get_gcloud_token()
    raise ValueError(f"Unsupported auth_mode: {auth_mode!r}. Use 'metadata', 'gcloud', or 'auto'.")


def push_time_series(
    time_series: list[dict[str, Any]], auth_mode: str = "auto"
) -> None:
    """Push time series to Cloud Monitoring via the REST API.

    Acquires a short-lived access token using auth_mode, then sends the payload
    via urllib.request. The token is kept in memory and never printed.

    Not called when --dry-run is set. Tests must mock urllib.request.urlopen
    (and subprocess when auth_mode includes gcloud).
    """
    if not time_series:
        return

    project_id = time_series[0]["resource"]["labels"]["project_id"]
    token = _get_token(auth_mode)

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
        raise RuntimeError(f"Cloud Monitoring push failed: {exc.reason}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse dbt run_results.json and emit Cloud Monitoring metrics.",
    )
    parser.add_argument(
        "--run-results-path", required=True, help="Path to dbt run_results.json."
    )
    parser.add_argument("--project-id", required=True, help="GCP project ID.")
    parser.add_argument(
        "--location", default="europe-west1", help="GCP region (informational only)."
    )
    parser.add_argument(
        "--job-name",
        default="rtdp-dbt-refresh-job",
        help="Cloud Run Job name used as a metric label.",
    )
    parser.add_argument(
        "--environment",
        default="cloud_sql_prod",
        help="dbt target environment used as a metric label.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and build metrics but skip Cloud Monitoring write.",
    )
    parser.add_argument(
        "--output-json", help="Path to write the JSON summary (also printed to stdout)."
    )
    parser.add_argument(
        "--auth-mode",
        choices=["metadata", "gcloud", "auto"],
        default="auto",
        help=(
            "Token acquisition mode for live Cloud Monitoring writes. "
            "'metadata' uses the GCP instance metadata server (Cloud Run, GCE). "
            "'gcloud' uses the gcloud CLI subprocess (local development). "
            "'auto' tries metadata first, then gcloud. "
            "Ignored when --dry-run is set."
        ),
    )
    args = parser.parse_args(argv)

    try:
        data = load_run_results(args.run_results_path)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    outer_parse_errors = 0
    try:
        parsed = parse_run_results(data)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR parsing run_results.json: {exc}", file=sys.stderr)
        outer_parse_errors = 1
        parsed = {
            "elapsed_time": 0.0,
            "invocation_id": None,
            "generated_at": None,
            "nodes": [],
            "parse_error_count": 0,
        }

    parsed["parse_error_count"] = parsed.get("parse_error_count", 0) + outer_parse_errors

    now = datetime.now(UTC)
    time_series = build_time_series(parsed, args.project_id, args.job_name, args.environment, now)
    summary = build_summary(
        parsed, args.job_name, args.environment, len(time_series), args.dry_run, now
    )

    summary_json = json.dumps(summary, indent=2)
    print(summary_json)

    if args.output_json:
        Path(args.output_json).write_text(summary_json)

    if args.dry_run:
        print(
            f"Dry run: would push {len(time_series)} time series to Cloud Monitoring.",
            file=sys.stderr,
        )
        return 0

    try:
        push_time_series(time_series, auth_mode=args.auth_mode)
        print(
            f"Pushed {len(time_series)} time series to Cloud Monitoring.",
            file=sys.stderr,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
