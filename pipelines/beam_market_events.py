"""Apache Beam DirectRunner-only pipeline for MarketEvent JSONL records.

Local proof only. DirectRunner. No GCP execution. No Pub/Sub. No BigQuery.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import apache_beam as beam
from apache_beam import pvalue
from apache_beam.options.pipeline_options import PipelineOptions
from pydantic import ValidationError

from rtdp_contracts import MarketEvent

DEAD_LETTER_TAG = "dead_letter"
ALLOWED_RUNNERS = frozenset({"DirectRunner"})


class ParseAndValidateDoFn(beam.DoFn):
    def process(self, element: str):
        try:
            raw = json.loads(element)
        except (json.JSONDecodeError, ValueError):
            yield pvalue.TaggedOutput(DEAD_LETTER_TAG, element)
            return
        try:
            event = MarketEvent(**raw)
        except (ValidationError, TypeError):
            yield pvalue.TaggedOutput(DEAD_LETTER_TAG, element)
            return
        yield json.dumps(
            {
                "event_id": event.event_id,
                "event_timestamp": event.event_timestamp.isoformat(),
                "event_type": event.event_type,
                "price": str(event.price),
                "quantity": str(event.quantity),
                "symbol": event.symbol,
            },
            sort_keys=True,
        )


def build_pipeline(
    pipeline: beam.Pipeline,
    input_path: str,
    output_path: str,
    dead_letter_path: str,
) -> None:
    tagged = (
        pipeline
        | "ReadLines" >> beam.io.ReadFromText(input_path)
        | "ParseAndValidate"
        >> beam.ParDo(ParseAndValidateDoFn()).with_outputs(DEAD_LETTER_TAG, main="valid")
    )
    (
        tagged["valid"]
        | "WriteValid"
        >> beam.io.WriteToText(
            output_path,
            num_shards=1,
            shard_name_template="",
            append_trailing_newlines=True,
        )
    )
    (
        tagged[DEAD_LETTER_TAG]
        | "WriteDeadLetter"
        >> beam.io.WriteToText(
            dead_letter_path,
            num_shards=1,
            shard_name_template="",
            append_trailing_newlines=True,
        )
    )


def run(
    input_path: str,
    output_path: str,
    dead_letter_path: str,
    runner: str = "DirectRunner",
) -> None:
    if runner not in ALLOWED_RUNNERS:
        raise ValueError(
            f"Runner {runner!r} is not permitted. Only 'DirectRunner' is allowed in this module. "
            "DataflowRunner execution is not enabled here."
        )
    options = PipelineOptions(runner=runner)
    with beam.Pipeline(options=options) as p:
        build_pipeline(p, input_path, output_path, dead_letter_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Beam MarketEvent pipeline (DirectRunner only). No GCP execution."
    )
    parser.add_argument("--input-jsonl", required=True, help="Path to input JSONL file")
    parser.add_argument("--output-jsonl", required=True, help="Path for valid output JSONL")
    parser.add_argument(
        "--dead-letter-jsonl", required=True, help="Path for dead-letter JSONL"
    )
    parser.add_argument(
        "--runner",
        default="DirectRunner",
        help="Beam runner. Only 'DirectRunner' is permitted.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input_jsonl):
        print(f"ERROR: Input file not found: {args.input_jsonl}", file=sys.stderr)
        sys.exit(1)

    try:
        run(
            input_path=args.input_jsonl,
            output_path=args.output_jsonl,
            dead_letter_path=args.dead_letter_jsonl,
            runner=args.runner,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
