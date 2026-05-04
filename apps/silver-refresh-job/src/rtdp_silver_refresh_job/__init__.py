"""Silver refresh job: call silver.refresh_market_event_minute_aggregates()."""

import json
import os
import sys
import time
from datetime import datetime, timezone

import psycopg

_SQL = "SELECT silver.refresh_market_event_minute_aggregates();"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_log(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


def run_refresh(database_url: str) -> int:
    """Connect to Postgres and invoke the silver refresh function. Returns 0 on success, 1 on failure."""
    t0 = time.monotonic()
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(_SQL)
        emit_log({
            "component": "silver-refresh",
            "operation": "refresh_market_event_minute_aggregates",
            "processing_time_ms": round((time.monotonic() - t0) * 1000, 3),
            "service": "rtdp-silver-refresh-job",
            "status": "ok",
            "timestamp_utc": utc_now_iso(),
        })
        return 0
    except Exception as exc:
        emit_log({
            "component": "silver-refresh",
            "error_message": str(exc),
            "error_type": type(exc).__name__,
            "operation": "refresh_market_event_minute_aggregates",
            "processing_time_ms": round((time.monotonic() - t0) * 1000, 3),
            "service": "rtdp-silver-refresh-job",
            "status": "error",
            "timestamp_utc": utc_now_iso(),
        })
        return 1


def main(argv: list[str] | None = None) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        emit_log({
            "component": "silver-refresh",
            "error_message": "DATABASE_URL environment variable is not set",
            "error_type": "EnvironmentError",
            "operation": "refresh_market_event_minute_aggregates",
            "processing_time_ms": 0.0,
            "service": "rtdp-silver-refresh-job",
            "status": "error",
            "timestamp_utc": utc_now_iso(),
        })
        sys.exit(1)
    sys.exit(run_refresh(database_url))
