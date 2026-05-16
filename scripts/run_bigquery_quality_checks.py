#!/usr/bin/env python3
"""Run read-only BigQuery data quality checks for the RTDP analytics table.

This script intentionally has no third-party Python dependencies. It shells out to
the installed `bq` CLI and returns a deterministic JSON report.

Default target:
  project-42987e01-2123-446b-ac7.rtdp_analytics.market_events_raw

The checks are read-only:
  - row_count_positive
  - required_columns_not_null
  - event_id_unique
  - event_type_accepted_values
  - freshness_available
  - staging_table_empty
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_PROJECT_ID = "project-42987e01-2123-446b-ac7"
DEFAULT_DATASET = "rtdp_analytics"
DEFAULT_TABLE = "market_events_raw"
DEFAULT_STAGING_TABLE = "market_events_raw_staging"
DEFAULT_ACCEPTED_EVENT_TYPES = ("trade",)


@dataclass(frozen=True)
class QualityCheck:
    name: str
    status: str
    observed: Any
    expected: str
    sql: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run read-only BigQuery quality checks and emit a JSON report.",
    )
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--staging-table", default=DEFAULT_STAGING_TABLE)
    parser.add_argument(
        "--accepted-event-types",
        default=",".join(DEFAULT_ACCEPTED_EVENT_TYPES),
        help="Comma-separated list of accepted event_type values.",
    )
    parser.add_argument(
        "--report-output",
        default="",
        help="Optional path to write the JSON report. If omitted, prints to stdout.",
    )
    return parser.parse_args()


def table_ref(project_id: str, dataset: str, table: str) -> str:
    return f"`{project_id}.{dataset}.{table}`"


def bq_query(sql: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["bq", "--quiet", "query", "--nouse_legacy_sql", "--format=json", sql],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "bq query failed\n"
            f"exit_code={result.returncode}\n"
            f"stderr={result.stderr.strip()}\n"
            f"sql={sql}"
        )

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        stdout_preview = result.stdout[:500].replace("\n", "\\n")
        stderr_preview = result.stderr[:500].replace("\n", "\\n")
        raise RuntimeError(
            "bq returned invalid JSON\n"
            f"json_error={exc}\n"
            f"stdout_preview={stdout_preview!r}\n"
            f"stderr_preview={stderr_preview!r}"
        ) from exc

    if not isinstance(parsed, list):
        raise RuntimeError(f"bq returned unexpected payload type: {type(parsed).__name__}")

    return parsed


def first_value(rows: list[dict[str, Any]], key: str) -> Any:
    if not rows:
        raise RuntimeError(f"bq returned no rows for key={key}")
    return rows[0].get(key)


def scalar_int(sql: str, key: str) -> int:
    value = first_value(bq_query(sql), key)
    if value is None:
        return 0
    return int(value)


def scalar_string(sql: str, key: str) -> str | None:
    value = first_value(bq_query(sql), key)
    if value is None:
        return None
    return str(value)


def check_row_count_positive(raw_table: str) -> QualityCheck:
    sql = f"SELECT COUNT(*) AS row_count FROM {raw_table}"
    row_count = scalar_int(sql, "row_count")
    return QualityCheck(
        name="row_count_positive",
        status="pass" if row_count > 0 else "fail",
        observed=row_count,
        expected="row_count > 0",
        sql=sql,
    )


def check_required_columns_not_null(raw_table: str) -> QualityCheck:
    required_columns = [
        "event_id",
        "event_timestamp",
        "symbol",
        "event_type",
        "ingest_timestamp",
        "bq_load_timestamp",
    ]

    null_expressions = [
        f"COUNTIF({column} IS NULL) AS {column}_nulls" for column in required_columns
    ]

    sql = f"SELECT {', '.join(null_expressions)} FROM {raw_table}"
    rows = bq_query(sql)
    observed = rows[0] if rows else {}
    total_nulls = sum(int(observed.get(f"{column}_nulls", 0)) for column in required_columns)

    return QualityCheck(
        name="required_columns_not_null",
        status="pass" if total_nulls == 0 else "fail",
        observed=observed,
        expected="all required column null counts == 0",
        sql=sql,
    )


def check_event_id_unique(raw_table: str) -> QualityCheck:
    sql = f"""
SELECT COUNT(*) AS duplicate_event_ids
FROM (
  SELECT event_id
  FROM {raw_table}
  GROUP BY event_id
  HAVING COUNT(*) > 1
)
""".strip()
    duplicate_event_ids = scalar_int(sql, "duplicate_event_ids")
    return QualityCheck(
        name="event_id_unique",
        status="pass" if duplicate_event_ids == 0 else "fail",
        observed=duplicate_event_ids,
        expected="duplicate_event_ids == 0",
        sql=sql,
    )


def check_event_type_accepted_values(
    raw_table: str,
    accepted_event_types: tuple[str, ...],
) -> QualityCheck:
    accepted_values_sql = ", ".join(f"'{value}'" for value in accepted_event_types)
    sql = f"""
SELECT COUNT(*) AS invalid_event_type_rows
FROM {raw_table}
WHERE event_type NOT IN ({accepted_values_sql})
""".strip()
    invalid_event_type_rows = scalar_int(sql, "invalid_event_type_rows")
    return QualityCheck(
        name="event_type_accepted_values",
        status="pass" if invalid_event_type_rows == 0 else "fail",
        observed={
            "invalid_event_type_rows": invalid_event_type_rows,
            "accepted_event_types": list(accepted_event_types),
        },
        expected="event_type must be in accepted_event_types",
        sql=sql,
    )


def check_freshness_available(raw_table: str) -> QualityCheck:
    sql = f"""
SELECT
  CAST(MAX(ingest_timestamp) AS STRING) AS max_ingest_timestamp,
  COUNT(*) AS row_count
FROM {raw_table}
""".strip()
    rows = bq_query(sql)
    max_ingest_timestamp = first_value(rows, "max_ingest_timestamp")
    row_count = int(first_value(rows, "row_count") or 0)

    return QualityCheck(
        name="freshness_available",
        status="pass" if row_count > 0 and max_ingest_timestamp else "fail",
        observed={
            "row_count": row_count,
            "max_ingest_timestamp": max_ingest_timestamp,
        },
        expected="row_count > 0 and max_ingest_timestamp is not null",
        sql=sql,
    )


def check_staging_table_empty(staging_table: str) -> QualityCheck:
    sql = f"SELECT COUNT(*) AS staging_row_count FROM {staging_table}"
    staging_row_count = scalar_int(sql, "staging_row_count")
    return QualityCheck(
        name="staging_table_empty",
        status="pass" if staging_row_count == 0 else "fail",
        observed=staging_row_count,
        expected="staging_row_count == 0",
        sql=sql,
    )


def run_checks(args: argparse.Namespace) -> dict[str, Any]:
    accepted_event_types = tuple(
        value.strip() for value in args.accepted_event_types.split(",") if value.strip()
    )

    if not accepted_event_types:
        raise ValueError("accepted_event_types cannot be empty")

    raw_table = table_ref(args.project_id, args.dataset, args.table)
    staging_table = table_ref(args.project_id, args.dataset, args.staging_table)

    checks = [
        check_row_count_positive(raw_table),
        check_required_columns_not_null(raw_table),
        check_event_id_unique(raw_table),
        check_event_type_accepted_values(raw_table, accepted_event_types),
        check_freshness_available(raw_table),
        check_staging_table_empty(staging_table),
    ]

    failed_checks = [check.name for check in checks if check.status != "pass"]

    return {
        "status": "ok" if not failed_checks else "error",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "project_id": args.project_id,
        "dataset": args.dataset,
        "table": args.table,
        "staging_table": args.staging_table,
        "accepted_event_types": list(accepted_event_types),
        "checks": [asdict(check) for check in checks],
        "failed_checks": failed_checks,
    }


def write_report(report: dict[str, Any], output_path: str) -> None:
    rendered = json.dumps(report, indent=2, sort_keys=True)

    if not output_path:
        print(rendered)
        return

    path = Path(output_path)
    if path.parent and not path.parent.exists():
        raise FileNotFoundError(f"Report output parent does not exist: {path.parent}")

    path.write_text(rendered + "\n")


def main() -> int:
    args = parse_args()

    try:
        report = run_checks(args)
        write_report(report, args.report_output)
    except Exception as exc:
        error_report = {
            "status": "error",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "error": str(exc),
        }
        print(json.dumps(error_report, indent=2, sort_keys=True))
        return 1

    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
