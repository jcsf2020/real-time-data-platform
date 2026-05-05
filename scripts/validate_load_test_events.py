"""Local-only load-test JSONL validator. No Pub/Sub publishing. No GCP resources mutated."""

import argparse
import json
import re
import sys
from pathlib import Path

from rtdp_pubsub_worker import validate_event

ALLOWED_SIZES = frozenset({100, 1000, 5000})
SYMBOLS = frozenset({"BTCUSDT", "ETHUSDT", "SOLUSDT"})
_TIMESTAMP_RE = re.compile(r"^\d{14}$")


def _make_report(
    *,
    status: str,
    input_path: str,
    expected_size: int,
    observed_count: int,
    prefix: str,
    first_event_id: str,
    last_event_id: str,
    unique_event_ids: int,
    symbols: list,
    worker_contract_validation: str,
    errors: list,
) -> dict:
    return {
        "errors": errors,
        "expected_size": expected_size,
        "first_event_id": first_event_id,
        "input": input_path,
        "last_event_id": last_event_id,
        "observed_count": observed_count,
        "prefix": prefix,
        "status": status,
        "symbols": symbols,
        "unique_event_ids": unique_event_ids,
        "worker_contract_validation": worker_contract_validation,
    }


def _emit(report: dict, report_output: str | None) -> None:
    text = json.dumps(report, separators=(",", ":"), sort_keys=True)
    if report_output is not None:
        Path(report_output).write_text(text)
    else:
        sys.stdout.write(text + "\n")


def validate_jsonl(input_path: str, size: int, prefix_timestamp: str) -> dict:
    """Validate JSONL file and return report dict. Does not mutate any GCP resource."""
    errors: list[str] = []
    path = Path(input_path)
    prefix = f"loadtest-{size}-{prefix_timestamp}-"

    if not path.exists():
        return _make_report(
            status="error",
            input_path=input_path,
            expected_size=size,
            observed_count=0,
            prefix=prefix,
            first_event_id="",
            last_event_id="",
            unique_event_ids=0,
            symbols=[],
            worker_contract_validation="failed",
            errors=[f"input file does not exist: {input_path}"],
        )

    non_empty = [line for line in path.read_text().splitlines() if line.strip()]
    observed_count = len(non_empty)

    if observed_count != size:
        errors.append(f"expected {size} non-empty lines, got {observed_count}")

    parsed: list[dict | None] = []
    for i, line in enumerate(non_empty, 1):
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                errors.append(f"line {i}: not a JSON object")
                parsed.append(None)
            else:
                parsed.append(obj)
        except json.JSONDecodeError as exc:
            errors.append(f"line {i}: invalid JSON: {exc}")
            parsed.append(None)

    event_ids: list[str] = []
    symbols_seen: set[str] = set()
    worker_failed = False

    for i, event in enumerate(parsed, 1):
        if event is None:
            continue

        expected_id = f"{prefix}{i:05d}"
        eid = event.get("event_id", "")
        event_ids.append(eid)

        if eid != expected_id:
            errors.append(f"line {i}: expected event_id '{expected_id}', got '{eid}'")

        sv = event.get("schema_version")
        if sv != "1.0":
            errors.append(f"line {i}: expected schema_version '1.0', got '{sv}'")

        et = event.get("event_type")
        if et != "trade":
            errors.append(f"line {i}: expected event_type 'trade', got '{et}'")

        sym = event.get("symbol")
        if sym not in SYMBOLS:
            errors.append(f"line {i}: invalid symbol '{sym}', allowed: {sorted(SYMBOLS)}")
        else:
            symbols_seen.add(sym)

        if not event.get("event_timestamp"):
            errors.append(f"line {i}: event_timestamp is missing or empty")

        try:
            validate_event(event)
        except Exception as exc:
            errors.append(f"line {i}: worker contract validation failed: {exc}")
            worker_failed = True

    if len(event_ids) != len(set(event_ids)):
        from collections import Counter

        dupes = sorted(eid for eid, count in Counter(event_ids).items() if count > 1)
        errors.append(f"duplicate event_ids found: {dupes}")

    first_event_id = parsed[0].get("event_id", "") if parsed and parsed[0] is not None else ""
    last_event_id = parsed[-1].get("event_id", "") if parsed and parsed[-1] is not None else ""

    return _make_report(
        status="ok" if not errors else "error",
        input_path=input_path,
        expected_size=size,
        observed_count=observed_count,
        prefix=prefix,
        first_event_id=first_event_id,
        last_event_id=last_event_id,
        unique_event_ids=len(set(event_ids)),
        symbols=sorted(symbols_seen),
        worker_contract_validation="failed" if worker_failed else "passed",
        errors=errors,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Local-only load-test JSONL validator. No Pub/Sub publishing.",
    )
    parser.add_argument("--input", required=True, metavar="FILE", help="Path to JSON Lines file.")
    parser.add_argument(
        "--size",
        type=int,
        required=True,
        help=f"Expected event count. Allowed: {sorted(ALLOWED_SIZES)}",
    )
    parser.add_argument(
        "--prefix-timestamp",
        required=True,
        metavar="YYYYMMDDHHMMSS",
        help="14-digit timestamp prefix embedded in every event_id.",
    )
    parser.add_argument(
        "--report-output",
        default=None,
        metavar="FILE",
        help="Write JSON report to FILE instead of stdout.",
    )
    args = parser.parse_args(argv)

    arg_errors: list[str] = []

    if args.size not in ALLOWED_SIZES:
        arg_errors.append(f"--size must be one of {sorted(ALLOWED_SIZES)}, got {args.size}")

    if not _TIMESTAMP_RE.match(args.prefix_timestamp):
        arg_errors.append(
            f"--prefix-timestamp must be 14 digits (YYYYMMDDHHMMSS), "
            f"got '{args.prefix_timestamp}'"
        )

    if args.report_output is not None:
        report_parent = Path(args.report_output).parent
        if not report_parent.exists():
            arg_errors.append(
                f"--report-output parent directory does not exist: {report_parent}"
            )

    if arg_errors:
        prefix = f"loadtest-{args.size}-{args.prefix_timestamp}-"
        report = _make_report(
            status="error",
            input_path=args.input,
            expected_size=args.size,
            observed_count=0,
            prefix=prefix,
            first_event_id="",
            last_event_id="",
            unique_event_ids=0,
            symbols=[],
            worker_contract_validation="failed",
            errors=arg_errors,
        )
        _emit(report, None)
        sys.exit(1)

    report = validate_jsonl(args.input, args.size, args.prefix_timestamp)
    _emit(report, args.report_output)

    if report["status"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
