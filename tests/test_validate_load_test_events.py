"""Tests for scripts/validate_load_test_events.py"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

VALIDATOR = Path(__file__).parent.parent / "scripts" / "validate_load_test_events.py"
GENERATOR = Path(__file__).parent.parent / "scripts" / "generate_load_test_events.py"
TS = "20260601120000"


def run_validator(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        capture_output=True,
        text=True,
    )


def generate_events_jsonl(size: int, ts: str = TS) -> str:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--size", str(size), "--prefix-timestamp", ts],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def write_jsonl(tmp_path: Path, content: str, name: str = "events.jsonl") -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def valid_event(seq: int, size: int = 100, ts: str = TS) -> dict:
    """Return a minimal valid event matching the generator's schema."""
    symbol = ["BTCUSDT", "ETHUSDT", "SOLUSDT"][seq % 3]
    return {
        "schema_version": "1.0",
        "event_id": f"loadtest-{size}-{ts}-{seq:05d}",
        "symbol": symbol,
        "event_type": "trade",
        "price": "67500.00",
        "quantity": "0.01",
        "event_timestamp": "2026-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_file_passes(tmp_path):
    content = generate_events_jsonl(100)
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["errors"] == []


def test_report_deterministic_fields(tmp_path):
    content = generate_events_jsonl(100)
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode == 0
    report = json.loads(result.stdout)

    assert report["status"] == "ok"
    assert report["input"] == str(f)
    assert report["expected_size"] == 100
    assert report["observed_count"] == 100
    assert report["prefix"] == f"loadtest-100-{TS}-"
    assert report["first_event_id"] == f"loadtest-100-{TS}-00001"
    assert report["last_event_id"] == f"loadtest-100-{TS}-00100"
    assert report["unique_event_ids"] == 100
    assert set(report["symbols"]) <= {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    assert report["worker_contract_validation"] == "passed"
    assert report["errors"] == []

    # Run again to verify determinism
    result2 = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.stdout == result2.stdout


def test_report_output_writes_to_file(tmp_path):
    content = generate_events_jsonl(100)
    f = write_jsonl(tmp_path, content)
    out = tmp_path / "report.json"
    result = run_validator(
        "--input", str(f), "--size", "100", "--prefix-timestamp", TS,
        "--report-output", str(out),
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert out.exists()
    report = json.loads(out.read_text())
    assert report["status"] == "ok"


# ---------------------------------------------------------------------------
# Argument-level failures
# ---------------------------------------------------------------------------


def test_missing_input_file_fails(tmp_path):
    result = run_validator(
        "--input", str(tmp_path / "nonexistent.jsonl"),
        "--size", "100",
        "--prefix-timestamp", TS,
    )
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert any("does not exist" in e for e in report["errors"])


def test_unsupported_size_fails(tmp_path):
    f = write_jsonl(tmp_path, "")
    result = run_validator("--input", str(f), "--size", "200", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert any("200" in e for e in report["errors"])


@pytest.mark.parametrize("ts", ["2026-06-01", "202606011", "notadate", "2026060112000X"])
def test_invalid_timestamp_fails(tmp_path, ts):
    f = write_jsonl(tmp_path, "")
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", ts)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"


def test_report_output_missing_parent_fails(tmp_path):
    content = generate_events_jsonl(100)
    f = write_jsonl(tmp_path, content)
    result = run_validator(
        "--input", str(f), "--size", "100", "--prefix-timestamp", TS,
        "--report-output", str(tmp_path / "nonexistent" / "report.json"),
    )
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"


# ---------------------------------------------------------------------------
# Content-level failures
# ---------------------------------------------------------------------------


def test_wrong_event_count_fails(tmp_path):
    events = [valid_event(i + 1) for i in range(50)]
    content = "\n".join(json.dumps(e) for e in events) + "\n"
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert report["observed_count"] == 50
    assert any("50" in e for e in report["errors"])


def test_malformed_json_line_fails(tmp_path):
    events = [valid_event(i + 1) for i in range(100)]
    lines = [json.dumps(e) for e in events]
    lines[5] = "not valid json {"
    content = "\n".join(lines) + "\n"
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert any("invalid JSON" in e for e in report["errors"])


def test_duplicate_event_id_fails(tmp_path):
    events = [valid_event(i + 1) for i in range(100)]
    events[1]["event_id"] = events[0]["event_id"]  # make line 2 a duplicate of line 1
    content = "\n".join(json.dumps(e) for e in events) + "\n"
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert any("duplicate" in e for e in report["errors"])


def test_wrong_event_id_prefix_fails(tmp_path):
    events = [valid_event(i + 1) for i in range(100)]
    for i, e in enumerate(events):
        e["event_id"] = f"wrongprefix-{i + 1:05d}"
    content = "\n".join(json.dumps(e) for e in events) + "\n"
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert any("event_id" in e for e in report["errors"])


def test_wrong_sequence_fails(tmp_path):
    events = [valid_event(i + 1) for i in range(100)]
    # Swap sequence numbers so first and second are out of order
    events[0]["event_id"] = f"loadtest-100-{TS}-00002"
    events[1]["event_id"] = f"loadtest-100-{TS}-00001"
    content = "\n".join(json.dumps(e) for e in events) + "\n"
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"


def test_invalid_schema_version_fails(tmp_path):
    events = [valid_event(i + 1) for i in range(100)]
    events[0]["schema_version"] = "2.0"
    content = "\n".join(json.dumps(e) for e in events) + "\n"
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert any("schema_version" in e for e in report["errors"])


def test_invalid_event_type_fails(tmp_path):
    events = [valid_event(i + 1) for i in range(100)]
    events[0]["event_type"] = "quote"
    content = "\n".join(json.dumps(e) for e in events) + "\n"
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert any("event_type" in e for e in report["errors"])


def test_invalid_symbol_fails(tmp_path):
    events = [valid_event(i + 1) for i in range(100)]
    events[0]["symbol"] = "XRPUSDT"
    content = "\n".join(json.dumps(e) for e in events) + "\n"
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert any("symbol" in e for e in report["errors"])


def test_invalid_worker_contract_payload_fails(tmp_path):
    """Payload passes manual field checks but fails pydantic (price <= 0)."""
    events = [valid_event(i + 1) for i in range(100)]
    events[0]["price"] = "-1.00"
    content = "\n".join(json.dumps(e) for e in events) + "\n"
    f = write_jsonl(tmp_path, content)
    result = run_validator("--input", str(f), "--size", "100", "--prefix-timestamp", TS)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "error"
    assert report["worker_contract_validation"] == "failed"
    assert any("worker contract" in e for e in report["errors"])
