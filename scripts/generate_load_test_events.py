"""Deterministic dry-run load-test event generator. No Pub/Sub publishing."""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ALLOWED_SIZES = frozenset({100, 1000, 5000})
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
_BASE_PRICES = {
    "BTCUSDT": Decimal("67500.00"),
    "ETHUSDT": Decimal("3200.00"),
    "SOLUSDT": Decimal("150.00"),
}
_BASE_TIMESTAMP = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_TIMESTAMP_RE = re.compile(r"^\d{14}$")


def generate_events(size: int, prefix_timestamp: str):
    """Yield exactly `size` deterministic MarketEvent-compatible dicts."""
    for i in range(size):
        symbol = SYMBOLS[i % len(SYMBOLS)]
        price = _BASE_PRICES[symbol] + Decimal(i % 100) * Decimal("0.01")
        quantity = Decimal("0.01") + Decimal(i % 100) * Decimal("0.001")
        yield {
            "schema_version": "1.0",
            "event_id": f"loadtest-{size}-{prefix_timestamp}-{i + 1:05d}",
            "symbol": symbol,
            "event_type": "trade",
            "price": str(price),
            "quantity": str(quantity),
            "event_timestamp": (_BASE_TIMESTAMP + timedelta(seconds=i)).isoformat(),
        }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run load-test event generator. No Pub/Sub publishing.",
    )
    parser.add_argument(
        "--size",
        type=int,
        required=True,
        help=f"Number of events to generate. Allowed: {sorted(ALLOWED_SIZES)}",
    )
    parser.add_argument(
        "--prefix-timestamp",
        required=True,
        metavar="YYYYMMDDHHMMSS",
        help="14-digit timestamp prefix embedded in every event_id.",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Write JSON Lines to FILE instead of stdout.",
    )
    args = parser.parse_args(argv)

    if args.size not in ALLOWED_SIZES:
        print(
            f"error: --size must be one of {sorted(ALLOWED_SIZES)}, got {args.size}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not _TIMESTAMP_RE.match(args.prefix_timestamp):
        print(
            f"error: --prefix-timestamp must be 14 digits (YYYYMMDDHHMMSS), "
            f"got '{args.prefix_timestamp}'",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.output is not None:
        output_path = Path(args.output)
        if not output_path.parent.exists():
            print(
                f"error: parent directory does not exist: {output_path.parent}",
                file=sys.stderr,
            )
            sys.exit(1)
        with output_path.open("w") as fh:
            for event in generate_events(args.size, args.prefix_timestamp):
                fh.write(json.dumps(event) + "\n")
    else:
        for event in generate_events(args.size, args.prefix_timestamp):
            sys.stdout.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    main()
