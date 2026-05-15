"""BigQuery incremental append job: cursor-based export from Cloud SQL to BigQuery."""

import json
import os
import sys
import time
from datetime import datetime, timezone

_SERVICE = "rtdp-bigquery-append-job"
_COMPONENT = "bigquery-append"
_DEFAULT_BATCH_LIMIT = 1000


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_log(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


def _safe_config(cfg: dict) -> dict:
    """Return a copy of cfg with sensitive fields removed for logging."""
    return {k: v for k, v in cfg.items() if k != "database_url"}


def resolve_config() -> dict:
    """Read and validate required env vars. Raises ValueError on missing or invalid values."""
    project_id = os.getenv("PROJECT_ID", "")
    bq_dataset = os.getenv("BQ_DATASET", "")
    bq_target_table = os.getenv("BQ_TARGET_TABLE", "")
    bq_staging_table = os.getenv("BQ_STAGING_TABLE", "")
    database_url = os.getenv("DATABASE_URL", "")

    missing = [
        k
        for k, v in {
            "PROJECT_ID": project_id,
            "BQ_DATASET": bq_dataset,
            "BQ_TARGET_TABLE": bq_target_table,
            "BQ_STAGING_TABLE": bq_staging_table,
            "DATABASE_URL": database_url,
        }.items()
        if not v
    ]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")

    raw_limit = os.getenv("APPEND_BATCH_LIMIT", str(_DEFAULT_BATCH_LIMIT))
    try:
        batch_limit = int(raw_limit)
    except ValueError:
        raise ValueError(f"APPEND_BATCH_LIMIT must be an integer, got: {raw_limit!r}")

    dry_run_val = os.getenv("APPEND_DRY_RUN", "").lower()
    dry_run = dry_run_val in ("true", "1", "yes")

    return {
        "project_id": project_id,
        "bq_dataset": bq_dataset,
        "bq_target_table": bq_target_table,
        "bq_staging_table": bq_staging_table,
        "database_url": database_url,
        "append_batch_limit": batch_limit,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Pure SQL-builder functions — testable without GCP or Cloud SQL
# ---------------------------------------------------------------------------


def build_cursor_query(project_id: str, dataset: str, table: str) -> str:
    """Return SQL that reads the latest ingest_timestamp already in BigQuery target."""
    return (
        f"SELECT MAX(ingest_timestamp) AS max_ingest_timestamp "
        f"FROM `{project_id}.{dataset}.{table}`"
    )


def build_source_export_query(cursor_ts: str | None, batch_limit: int) -> str:
    """Return SQL for exporting delta rows from Cloud SQL bronze.market_events.

    Uses ingested_at as the export cursor; event_id is NOT used for ordering.
    cursor_ts: ISO-format timestamp string or None (export all rows up to batch_limit).
    """
    cols = (
        "event_id, event_timestamp, symbol, event_type, "
        "price, quantity, source_topic, ingested_at"
    )
    base = f"SELECT {cols} FROM bronze.market_events"
    if cursor_ts is None:
        return f"{base} ORDER BY ingested_at, event_id LIMIT {batch_limit}"
    return f"{base} WHERE ingested_at >= '{cursor_ts}' ORDER BY ingested_at, event_id LIMIT {batch_limit}"


def build_merge_sql(
    project_id: str, dataset: str, target_table: str, staging_table: str
) -> str:
    """Return a BigQuery MERGE statement that inserts only new event_ids.

    WHEN NOT MATCHED BY TARGET: insert row from staging.
    No WHEN MATCHED clause — target is append-only, no updates.
    """
    target_ref = f"`{project_id}.{dataset}.{target_table}`"
    staging_ref = f"`{project_id}.{dataset}.{staging_table}`"
    return (
        f"MERGE {target_ref} AS target\n"
        f"USING {staging_ref} AS source\n"
        f"ON target.event_id = source.event_id\n"
        f"WHEN NOT MATCHED BY TARGET THEN\n"
        f"  INSERT (event_id, event_timestamp, symbol, event_type, price, quantity,\n"
        f"          source, ingest_timestamp, bq_load_timestamp)\n"
        f"  VALUES (source.event_id, source.event_timestamp, source.symbol,\n"
        f"          source.event_type, source.price, source.quantity,\n"
        f"          source.source, source.ingest_timestamp, source.bq_load_timestamp)"
    )


def build_duplicate_check_sql(project_id: str, dataset: str, table: str) -> str:
    """Return SQL that returns event_id values with more than one row in the target table."""
    return (
        f"SELECT event_id, COUNT(*) AS cnt "
        f"FROM `{project_id}.{dataset}.{table}` "
        f"GROUP BY event_id "
        f"HAVING cnt > 1"
    )


def map_source_row_to_bigquery_row(row: dict, bq_load_timestamp: datetime) -> dict:
    """Map a Cloud SQL bronze.market_events row to a BigQuery market_events_raw row.

    Column mapping:
      source_topic  -> source
      ingested_at   -> ingest_timestamp
      (load time)   -> bq_load_timestamp
    """
    return {
        "event_id": row["event_id"],
        "event_timestamp": row["event_timestamp"],
        "symbol": row["symbol"],
        "event_type": row["event_type"],
        "price": row["price"],
        "quantity": row["quantity"],
        "source": row["source_topic"],
        "ingest_timestamp": row["ingested_at"],
        "bq_load_timestamp": bq_load_timestamp,
    }


# ---------------------------------------------------------------------------
# Dry-run execution — safe to run locally and in CI (no GCP or DB connections)
# ---------------------------------------------------------------------------


def run_dry_run(cfg: dict) -> None:
    """Emit structured JSON logs describing the planned append steps; no I/O performed."""
    emit_log({
        "component": _COMPONENT,
        "dry_run": True,
        "operation": "config_resolved",
        "service": _SERVICE,
        "status": "planned",
        "timestamp_utc": utc_now_iso(),
        **_safe_config(cfg),
    })

    cursor_sql = build_cursor_query(cfg["project_id"], cfg["bq_dataset"], cfg["bq_target_table"])
    emit_log({
        "component": _COMPONENT,
        "cursor_sql": cursor_sql,
        "dry_run": True,
        "operation": "cursor_query_prepared",
        "service": _SERVICE,
        "status": "planned",
        "timestamp_utc": utc_now_iso(),
    })

    source_sql = build_source_export_query(None, cfg["append_batch_limit"])
    emit_log({
        "component": _COMPONENT,
        "dry_run": True,
        "operation": "source_export_query_prepared",
        "service": _SERVICE,
        "source_sql": source_sql,
        "status": "planned",
        "timestamp_utc": utc_now_iso(),
    })

    staging_ref = f"{cfg['project_id']}.{cfg['bq_dataset']}.{cfg['bq_staging_table']}"
    emit_log({
        "component": _COMPONENT,
        "dry_run": True,
        "operation": "staging_load_planned",
        "service": _SERVICE,
        "staging_table": staging_ref,
        "status": "planned",
        "timestamp_utc": utc_now_iso(),
    })

    merge_sql = build_merge_sql(
        cfg["project_id"], cfg["bq_dataset"], cfg["bq_target_table"], cfg["bq_staging_table"]
    )
    emit_log({
        "component": _COMPONENT,
        "dry_run": True,
        "merge_sql": merge_sql,
        "operation": "merge_planned",
        "service": _SERVICE,
        "status": "planned",
        "timestamp_utc": utc_now_iso(),
    })

    dup_sql = build_duplicate_check_sql(
        cfg["project_id"], cfg["bq_dataset"], cfg["bq_target_table"]
    )
    emit_log({
        "component": _COMPONENT,
        "dry_run": True,
        "duplicate_check_sql": dup_sql,
        "operation": "duplicate_check_planned",
        "service": _SERVICE,
        "status": "planned",
        "timestamp_utc": utc_now_iso(),
    })

    emit_log({
        "component": _COMPONENT,
        "dry_run": True,
        "operation": "append_job_complete",
        "service": _SERVICE,
        "status": "dry_run_complete",
        "timestamp_utc": utc_now_iso(),
    })


# ---------------------------------------------------------------------------
# Live execution — not exercised in tests; requires GCP credentials and Cloud SQL
# ---------------------------------------------------------------------------


def run(cfg: dict) -> int:
    """Execute the incremental append: read cursor, export delta, load staging, merge.

    Imports google-cloud-bigquery and psycopg lazily so the module remains importable
    without those packages present (e.g. in dry-run-only test environments).
    """
    try:
        import psycopg
        from google.cloud import bigquery  # type: ignore[import-untyped]
    except ImportError as exc:
        emit_log({
            "component": _COMPONENT,
            "error_message": str(exc),
            "error_type": type(exc).__name__,
            "operation": "startup",
            "service": _SERVICE,
            "status": "error",
            "timestamp_utc": utc_now_iso(),
        })
        return 1

    t0 = time.monotonic()
    project_id = cfg["project_id"]
    dataset = cfg["bq_dataset"]
    target = cfg["bq_target_table"]
    staging = cfg["bq_staging_table"]

    try:
        bq_client = bigquery.Client(project=project_id)

        # Step 1: read cursor from BigQuery
        cursor_sql = build_cursor_query(project_id, dataset, target)
        emit_log({
            "component": _COMPONENT,
            "cursor_sql": cursor_sql,
            "operation": "cursor_query_prepared",
            "service": _SERVICE,
            "status": "executing",
            "timestamp_utc": utc_now_iso(),
        })
        cursor_result = list(bq_client.query(cursor_sql).result())
        cursor_row = cursor_result[0] if cursor_result else None
        cursor_ts: datetime | None = cursor_row.max_ingest_timestamp if cursor_row else None
        emit_log({
            "component": _COMPONENT,
            "cursor_ts": cursor_ts.isoformat() if cursor_ts else None,
            "operation": "cursor_resolved",
            "service": _SERVICE,
            "status": "success",
            "timestamp_utc": utc_now_iso(),
        })

        # Step 2: export delta rows from Cloud SQL
        cursor_str = cursor_ts.isoformat() if cursor_ts else None
        emit_log({
            "component": _COMPONENT,
            "operation": "source_export_query_prepared",
            "service": _SERVICE,
            "source_sql": build_source_export_query(cursor_str, cfg["append_batch_limit"]),
            "status": "executing",
            "timestamp_utc": utc_now_iso(),
        })

        with psycopg.connect(cfg["database_url"]) as conn:
            with conn.cursor() as cur:
                if cursor_ts is not None:
                    cur.execute(
                        "SELECT event_id, event_timestamp, symbol, event_type, price, quantity,"
                        " source_topic, ingested_at"
                        " FROM bronze.market_events"
                        " WHERE ingested_at >= %s"
                        " ORDER BY ingested_at, event_id LIMIT %s",
                        [cursor_ts, cfg["append_batch_limit"]],
                    )
                else:
                    cur.execute(
                        "SELECT event_id, event_timestamp, symbol, event_type, price, quantity,"
                        " source_topic, ingested_at"
                        " FROM bronze.market_events"
                        " ORDER BY ingested_at, event_id LIMIT %s",
                        [cfg["append_batch_limit"]],
                    )
                col_names = [desc.name for desc in cur.description]
                source_rows = [dict(zip(col_names, row)) for row in cur.fetchall()]

        emit_log({
            "component": _COMPONENT,
            "operation": "source_export_complete",
            "row_count": len(source_rows),
            "service": _SERVICE,
            "status": "success",
            "timestamp_utc": utc_now_iso(),
        })

        if not source_rows:
            duration_ms = round((time.monotonic() - t0) * 1000, 3)
            emit_log({
                "component": _COMPONENT,
                "duration_ms": duration_ms,
                "operation": "append_job_complete",
                "rows_appended": 0,
                "service": _SERVICE,
                "status": "success",
                "timestamp_utc": utc_now_iso(),
            })
            return 0

        # Step 3: load delta rows to BigQuery staging
        bq_load_ts = datetime.now(timezone.utc)
        bq_rows = [map_source_row_to_bigquery_row(r, bq_load_ts) for r in source_rows]
        bq_rows_json = [
            {
                k: v.isoformat() if isinstance(v, datetime) else v
                for k, v in row.items()
            }
            for row in bq_rows
        ]

        staging_ref = f"{project_id}.{dataset}.{staging}"
        emit_log({
            "component": _COMPONENT,
            "operation": "staging_load_planned",
            "row_count": len(bq_rows_json),
            "service": _SERVICE,
            "staging_table": staging_ref,
            "status": "executing",
            "timestamp_utc": utc_now_iso(),
        })
        errors = bq_client.insert_rows_json(staging_ref, bq_rows_json)
        if errors:
            raise RuntimeError(f"BigQuery streaming insert errors: {errors}")
        emit_log({
            "component": _COMPONENT,
            "operation": "staging_load_complete",
            "row_count": len(bq_rows_json),
            "service": _SERVICE,
            "status": "success",
            "timestamp_utc": utc_now_iso(),
        })

        # Step 4: merge staging into target
        merge_sql = build_merge_sql(project_id, dataset, target, staging)
        emit_log({
            "component": _COMPONENT,
            "merge_sql": merge_sql,
            "operation": "merge_planned",
            "service": _SERVICE,
            "status": "executing",
            "timestamp_utc": utc_now_iso(),
        })
        bq_client.query(merge_sql).result()
        emit_log({
            "component": _COMPONENT,
            "operation": "merge_complete",
            "service": _SERVICE,
            "status": "success",
            "timestamp_utc": utc_now_iso(),
        })

        # Step 5: verify no duplicates
        dup_sql = build_duplicate_check_sql(project_id, dataset, target)
        emit_log({
            "component": _COMPONENT,
            "duplicate_check_sql": dup_sql,
            "operation": "duplicate_check_planned",
            "service": _SERVICE,
            "status": "executing",
            "timestamp_utc": utc_now_iso(),
        })
        dup_rows = list(bq_client.query(dup_sql).result())
        dup_status = "warning" if dup_rows else "success"
        emit_log({
            "component": _COMPONENT,
            "duplicate_count": len(dup_rows),
            "operation": "duplicate_check_complete",
            "service": _SERVICE,
            "status": dup_status,
            "timestamp_utc": utc_now_iso(),
        })

        # Step 6: clean up staging table
        bq_client.delete_table(staging_ref, not_found_ok=True)

        duration_ms = round((time.monotonic() - t0) * 1000, 3)
        emit_log({
            "component": _COMPONENT,
            "duration_ms": duration_ms,
            "operation": "append_job_complete",
            "rows_appended": len(bq_rows_json),
            "service": _SERVICE,
            "status": "success",
            "timestamp_utc": utc_now_iso(),
        })
        return 0

    except Exception as exc:
        duration_ms = round((time.monotonic() - t0) * 1000, 3)
        emit_log({
            "component": _COMPONENT,
            "duration_ms": duration_ms,
            "error_message": str(exc),
            "error_type": type(exc).__name__,
            "operation": "append_job_complete",
            "service": _SERVICE,
            "status": "error",
            "timestamp_utc": utc_now_iso(),
        })
        return 1


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    try:
        cfg = resolve_config()
    except ValueError as exc:
        emit_log({
            "component": _COMPONENT,
            "error_message": str(exc),
            "error_type": type(exc).__name__,
            "operation": "startup",
            "service": _SERVICE,
            "status": "error",
            "timestamp_utc": utc_now_iso(),
        })
        sys.exit(1)

    if cfg["dry_run"]:
        run_dry_run(cfg)
        sys.exit(0)

    sys.exit(run(cfg))
