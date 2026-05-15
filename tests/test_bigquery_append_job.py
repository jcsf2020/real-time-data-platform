"""Tests for the BigQuery incremental append job."""

import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from rtdp_bigquery_append_job import (
    build_cursor_query,
    build_duplicate_check_sql,
    build_merge_sql,
    build_source_export_query,
    map_source_row_to_bigquery_row,
    resolve_config,
    run_dry_run,
)


# --- helpers ---


def _base_env(monkeypatch) -> None:
    monkeypatch.setenv("PROJECT_ID", "test-project-123")
    monkeypatch.setenv("BQ_DATASET", "rtdp_analytics")
    monkeypatch.setenv("BQ_TARGET_TABLE", "market_events_raw")
    monkeypatch.setenv("BQ_STAGING_TABLE", "market_events_raw_staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:test_password@host:5432/db")
    monkeypatch.setenv("APPEND_BATCH_LIMIT", "500")
    monkeypatch.setenv("APPEND_DRY_RUN", "false")


def _capture_logs(capsys) -> list[dict]:
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Test 1: Config resolution masks secrets — DATABASE_URL not in log output
# ---------------------------------------------------------------------------


def test_resolve_config_does_not_expose_database_url_in_logs(monkeypatch, capsys):
    _base_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:super_secret_pw@host:5432/db")
    monkeypatch.setenv("APPEND_DRY_RUN", "true")

    cfg = resolve_config()
    run_dry_run(cfg)

    out = capsys.readouterr().out
    assert "super_secret_pw" not in out
    assert "postgresql://user:super_secret_pw@host:5432/db" not in out


# ---------------------------------------------------------------------------
# Test 2: event_id is used in MERGE ON clause
# ---------------------------------------------------------------------------


def test_merge_sql_on_clause_uses_event_id():
    sql = build_merge_sql("proj", "ds", "target_tbl", "staging_tbl")
    assert "target.event_id = source.event_id" in sql


# ---------------------------------------------------------------------------
# Test 3: MERGE has WHEN NOT MATCHED, no WHEN MATCHED update
# ---------------------------------------------------------------------------


def test_merge_sql_has_when_not_matched_no_when_matched_update():
    sql = build_merge_sql("proj", "ds", "target_tbl", "staging_tbl")
    assert "WHEN NOT MATCHED" in sql
    assert "WHEN MATCHED" not in sql


# ---------------------------------------------------------------------------
# Test 4: Cursor/source query uses ingested_at, not event_id ordering
# ---------------------------------------------------------------------------


def test_source_export_query_uses_ingested_at_cursor():
    sql = build_source_export_query("2024-01-01T00:00:00", 100)
    assert "ingested_at" in sql


def test_cursor_query_uses_ingest_timestamp_not_event_id():
    sql = build_cursor_query("proj", "ds", "tbl")
    assert "ingest_timestamp" in sql
    assert "event_id" not in sql


# ---------------------------------------------------------------------------
# Test 5: Source export query does not contain "event_id >"
# ---------------------------------------------------------------------------


def test_source_export_query_does_not_contain_event_id_greater_than():
    sql_with_cursor = build_source_export_query("2024-01-01T00:00:00", 100)
    assert "event_id >" not in sql_with_cursor

    sql_no_cursor = build_source_export_query(None, 100)
    assert "event_id >" not in sql_no_cursor


# ---------------------------------------------------------------------------
# Test 6: Duplicate check groups by event_id and returns rows where count > 1
# ---------------------------------------------------------------------------


def test_duplicate_check_sql_groups_by_event_id_with_count_filter():
    sql = build_duplicate_check_sql("proj", "ds", "tbl")
    assert "GROUP BY event_id" in sql
    assert "cnt > 1" in sql


# ---------------------------------------------------------------------------
# Test 7: Source row mapping — source_topic -> source, ingested_at -> ingest_timestamp
# ---------------------------------------------------------------------------


def test_map_source_row_maps_source_topic_and_ingested_at():
    ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    load_ts = datetime(2024, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
    row = {
        "event_id": "evt-uuid-001",
        "event_timestamp": ts,
        "symbol": "BTCUSDT",
        "event_type": "trade",
        "price": 68000.5,
        "quantity": 0.25,
        "source_topic": "market-events-raw",
        "ingested_at": ts,
    }
    result = map_source_row_to_bigquery_row(row, load_ts)

    assert result["source"] == "market-events-raw"
    assert result["ingest_timestamp"] == ts
    assert result["bq_load_timestamp"] == load_ts
    assert result["event_id"] == "evt-uuid-001"
    assert result["symbol"] == "BTCUSDT"


# ---------------------------------------------------------------------------
# Test 8: Dry-run mode does not instantiate live GCP clients or DB connections
# ---------------------------------------------------------------------------


def test_dry_run_does_not_instantiate_gcp_clients(monkeypatch, capsys):
    _base_env(monkeypatch)
    monkeypatch.setenv("APPEND_DRY_RUN", "true")

    cfg = resolve_config()

    # Patch psycopg.connect: if dry_run calls it, the test fails immediately
    with patch("psycopg.connect", side_effect=RuntimeError("unexpected DB call in dry-run")):
        run_dry_run(cfg)  # must complete without raising

    logs = _capture_logs(capsys)
    assert len(logs) > 0
    assert all(lg.get("dry_run") is True for lg in logs)


# ---------------------------------------------------------------------------
# Test 9: Dry-run logs include all planned steps
# ---------------------------------------------------------------------------


def test_dry_run_logs_include_all_planned_steps(monkeypatch, capsys):
    _base_env(monkeypatch)
    monkeypatch.setenv("APPEND_DRY_RUN", "true")

    cfg = resolve_config()
    run_dry_run(cfg)

    logs = _capture_logs(capsys)
    operations = {lg["operation"] for lg in logs}

    assert "cursor_query_prepared" in operations
    assert "source_export_query_prepared" in operations
    assert "staging_load_planned" in operations
    assert "merge_planned" in operations
    assert "duplicate_check_planned" in operations
    assert "append_job_complete" in operations


def test_dry_run_logs_contain_sql_for_each_step(monkeypatch, capsys):
    _base_env(monkeypatch)
    monkeypatch.setenv("APPEND_DRY_RUN", "true")

    cfg = resolve_config()
    run_dry_run(cfg)

    logs = _capture_logs(capsys)
    log_by_op = {lg["operation"]: lg for lg in logs}

    assert "cursor_sql" in log_by_op["cursor_query_prepared"]
    assert "source_sql" in log_by_op["source_export_query_prepared"]
    assert "merge_sql" in log_by_op["merge_planned"]
    assert "duplicate_check_sql" in log_by_op["duplicate_check_planned"]


# ---------------------------------------------------------------------------
# Test 10: Raw DATABASE_URL / password not present in any log output
# ---------------------------------------------------------------------------


def test_database_url_password_not_in_any_log(monkeypatch, capsys):
    _base_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://rtdp:hunter2@cloudsql-host:5432/realtime")
    monkeypatch.setenv("APPEND_DRY_RUN", "true")

    cfg = resolve_config()
    run_dry_run(cfg)

    out = capsys.readouterr().out
    assert "hunter2" not in out
    assert "postgresql://rtdp:hunter2@cloudsql-host:5432/realtime" not in out


# ---------------------------------------------------------------------------
# Additional: resolve_config validation
# ---------------------------------------------------------------------------


def test_resolve_config_missing_project_id_raises(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.delenv("PROJECT_ID")

    with pytest.raises(ValueError, match="PROJECT_ID"):
        resolve_config()


def test_resolve_config_missing_database_url_raises(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValueError, match="DATABASE_URL"):
        resolve_config()


def test_resolve_config_invalid_batch_limit_raises(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("APPEND_BATCH_LIMIT", "not_an_int")

    with pytest.raises(ValueError, match="APPEND_BATCH_LIMIT"):
        resolve_config()


def test_resolve_config_dry_run_flag_true(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("APPEND_DRY_RUN", "true")

    cfg = resolve_config()
    assert cfg["dry_run"] is True


def test_resolve_config_dry_run_flag_false_by_default(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.delenv("APPEND_DRY_RUN", raising=False)

    cfg = resolve_config()
    assert cfg["dry_run"] is False


# ---------------------------------------------------------------------------
# Additional: SQL builder edge cases
# ---------------------------------------------------------------------------


def test_build_source_export_query_no_cursor_omits_where():
    sql = build_source_export_query(None, 200)
    assert "WHERE" not in sql
    assert "LIMIT 200" in sql


def test_build_source_export_query_with_cursor_includes_where():
    sql = build_source_export_query("2025-01-01T00:00:00+00:00", 50)
    assert "WHERE ingested_at >=" in sql
    assert "LIMIT 50" in sql


def test_build_source_export_query_reprocesses_cursor_boundary_for_idempotent_merge():
    sql = build_source_export_query("2025-06-01T00:00:00+00:00", 100)
    assert "ingested_at >=" in sql
    assert "ORDER BY ingested_at, event_id" in sql
    assert "event_id >" not in sql


def test_build_merge_sql_references_correct_tables():
    sql = build_merge_sql("my-proj", "my_ds", "events_raw", "events_staging")
    assert "`my-proj.my_ds.events_raw`" in sql
    assert "`my-proj.my_ds.events_staging`" in sql


def test_build_duplicate_check_sql_references_correct_table():
    sql = build_duplicate_check_sql("my-proj", "my_ds", "events_raw")
    assert "`my-proj.my_ds.events_raw`" in sql


def test_map_source_row_does_not_include_source_topic_key(monkeypatch):
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    row = {
        "event_id": "e1",
        "event_timestamp": ts,
        "symbol": "ETHUSDT",
        "event_type": "trade",
        "price": 3000.0,
        "quantity": 1.0,
        "source_topic": "market-events-raw",
        "ingested_at": ts,
    }
    result = map_source_row_to_bigquery_row(row, ts)
    assert "source_topic" not in result
    assert "ingested_at" not in result
