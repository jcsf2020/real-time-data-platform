"""Tests for scripts/generate_load_test_events.py"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from rtdp_pubsub_worker import validate_event

SCRIPT = Path(__file__).parent.parent / "scripts" / "generate_load_test_events.py"
TS = "20260601120000"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("size", [100, 1000, 5000])
def test_event_count(size):
    result = run("--size", str(size), "--prefix-timestamp", TS)
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == size


def test_event_id_prefix_and_zero_padding():
    result = run("--size", "100", "--prefix-timestamp", TS)
    assert result.returncode == 0
    lines = result.stdout.splitlines()
    first = json.loads(lines[0])
    last = json.loads(lines[-1])
    assert first["event_id"] == f"loadtest-100-{TS}-00001"
    assert last["event_id"] == f"loadtest-100-{TS}-00100"


def test_deterministic():
    r1 = run("--size", "100", "--prefix-timestamp", TS)
    r2 = run("--size", "100", "--prefix-timestamp", TS)
    assert r1.returncode == 0
    assert r1.stdout == r2.stdout


def test_json_lines_valid():
    result = run("--size", "100", "--prefix-timestamp", TS)
    assert result.returncode == 0
    for line in result.stdout.splitlines():
        assert isinstance(json.loads(line), dict)


def test_unsupported_size_fails():
    result = run("--size", "200", "--prefix-timestamp", TS)
    assert result.returncode != 0


@pytest.mark.parametrize("ts", ["2026-06-01", "202606011", "notadate", "2026060112000X"])
def test_invalid_timestamp_fails(ts):
    result = run("--size", "100", "--prefix-timestamp", ts)
    assert result.returncode != 0


def test_output_file(tmp_path):
    out = tmp_path / "events.jsonl"
    result = run("--size", "100", "--prefix-timestamp", TS, "--output", str(out))
    assert result.returncode == 0
    lines = out.read_text().splitlines()
    assert len(lines) == 100
    for line in lines:
        json.loads(line)


def test_missing_parent_directory_fails(tmp_path):
    out = tmp_path / "nonexistent" / "events.jsonl"
    result = run("--size", "100", "--prefix-timestamp", TS, "--output", str(out))
    assert result.returncode != 0


def test_validate_with_worker():
    """Generated payloads must pass the existing worker's validate_event."""
    result = run("--size", "100", "--prefix-timestamp", TS)
    assert result.returncode == 0
    for line in result.stdout.splitlines():
        payload = json.loads(line)
        event = validate_event(payload)
        assert event.event_id.startswith(f"loadtest-100-{TS}-")
