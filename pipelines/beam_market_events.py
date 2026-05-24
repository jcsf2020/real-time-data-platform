"""Apache Beam pipeline for MarketEvent records.

DirectRunner: local JSONL proof (unchanged from Phase 1).
DataflowRunner: bounded GCP proof via ReadFromPubSub → WriteToBigQuery.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import apache_beam as beam
from apache_beam import pvalue
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions
from pydantic import ValidationError

from rtdp_contracts import MarketEvent

DEAD_LETTER_TAG = "dead_letter"

# Proof-only GCP targets.  Validated in run_dataflow() before any GCP call.
# The proof topic is isolated from the production topic; publishing to it
# does NOT fan out to the production worker-push subscription.
DATAFLOW_PROOF_TOPIC = (
    "projects/project-42987e01-2123-446b-ac7"
    "/topics/market-events-raw-beam-proof"
)
DATAFLOW_PROOF_SUBSCRIPTION = (
    "projects/project-42987e01-2123-446b-ac7"
    "/subscriptions/market-events-raw-beam-proof-sub"
)
DATAFLOW_PROOF_TABLE = (
    "project-42987e01-2123-446b-ac7:rtdp_analytics.market_events_beam_proof"
)

# Defensive guard: explicit rejection of the production push subscription path.
_PRODUCTION_PUSH_SUB_FRAGMENT = "worker-push"

BQ_SCHEMA = {
    "fields": [
        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "symbol", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_type", "type": "STRING", "mode": "REQUIRED"},
        {"name": "price", "type": "NUMERIC", "mode": "NULLABLE"},
        {"name": "quantity", "type": "NUMERIC", "mode": "NULLABLE"},
    ]
}


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


# ---------------------------------------------------------------------------
# DirectRunner pipeline (unchanged from Phase 1)
# ---------------------------------------------------------------------------


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
    if runner != "DirectRunner":
        raise ValueError(
            f"Runner {runner!r} is not permitted in run(). "
            "Use run_dataflow() for DataflowRunner. "
            "Only 'DirectRunner' is accepted here."
        )
    options = PipelineOptions(runner=runner)
    with beam.Pipeline(options=options) as p:
        build_pipeline(p, input_path, output_path, dead_letter_path)


# ---------------------------------------------------------------------------
# DataflowRunner pipeline (bounded GCP proof)
# ---------------------------------------------------------------------------


def _validate_dataflow_args(
    project: str,
    region: str,
    service_account_email: str,
    staging_location: str,
    temp_location: str,
    input_subscription: str,
    output_table: str,
) -> None:
    """Validate all DataflowRunner arguments before any GCP call is made.

    Uses exact-match guards for subscription and table so any path other than
    the designated proof-only resources is rejected, regardless of naming.
    """
    missing = [
        name
        for name, val in [
            ("project", project),
            ("region", region),
            ("service_account_email", service_account_email),
            ("staging_location", staging_location),
            ("temp_location", temp_location),
            ("input_subscription", input_subscription),
            ("output_table", output_table),
        ]
        if not val
    ]
    if missing:
        raise ValueError(
            f"DataflowRunner requires all arguments. Missing or empty: {missing}"
        )
    # Defensive check first: explicit guard against the production push subscription.
    if _PRODUCTION_PUSH_SUB_FRAGMENT in input_subscription:
        raise ValueError(
            f"input_subscription {input_subscription!r} contains "
            f"{_PRODUCTION_PUSH_SUB_FRAGMENT!r}. "
            "DataflowRunner proof must not use the production worker-push subscription."
        )
    # Exact-match guards: only the designated proof resources are permitted.
    if input_subscription != DATAFLOW_PROOF_SUBSCRIPTION:
        raise ValueError(
            f"input_subscription {input_subscription!r} is not the proof subscription. "
            f"Only {DATAFLOW_PROOF_SUBSCRIPTION!r} is permitted for the DataflowRunner proof."
        )
    if output_table != DATAFLOW_PROOF_TABLE:
        raise ValueError(
            f"output_table {output_table!r} is not the proof table. "
            f"Only {DATAFLOW_PROOF_TABLE!r} is permitted for the DataflowRunner proof."
        )


def build_dataflow_pipeline(
    pipeline: beam.Pipeline,
    input_subscription: str,
    output_table: str,
) -> None:
    """ReadFromPubSub → ParseAndValidate → WriteToBigQuery (proof table only)."""
    tagged = (
        pipeline
        | "ReadFromPubSub"
        >> beam.io.ReadFromPubSub(subscription=input_subscription).with_output_types(bytes)
        | "DecodeBytes" >> beam.Map(lambda b: b.decode("utf-8"))
        | "ParseAndValidate"
        >> beam.ParDo(ParseAndValidateDoFn()).with_outputs(DEAD_LETTER_TAG, main="valid")
    )
    (
        tagged["valid"]
        | "ParseToDict" >> beam.Map(json.loads)
        | "WriteToBigQuery"
        >> beam.io.WriteToBigQuery(
            output_table,
            schema=BQ_SCHEMA,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
        )
    )
    # Dead-letter records are visible in Dataflow job metrics; not written to GCP in the proof.


def run_dataflow(
    project: str,
    region: str,
    service_account_email: str,
    staging_location: str,
    temp_location: str,
    input_subscription: str,
    output_table: str,
    max_records: int | None = None,
) -> None:
    """Submit a bounded DataflowRunner streaming job to GCP.

    Validates all safety constraints before any GCP call.  Returns after job
    submission; the operator is responsible for draining/cancelling within the
    bounded time window.

    max_records is advisory: pre-publish exactly that many messages to the proof
    subscription before launching so the job has a natural drain point.
    """
    _validate_dataflow_args(
        project,
        region,
        service_account_email,
        staging_location,
        temp_location,
        input_subscription,
        output_table,
    )
    pipeline_args = [
        "--runner=DataflowRunner",
        f"--project={project}",
        f"--region={region}",
        f"--service_account_email={service_account_email}",
        f"--staging_location={staging_location}",
        f"--temp_location={temp_location}",
        "--streaming",
        "--job_name=rtdp-market-events-beam-proof",
    ]
    options = PipelineOptions(pipeline_args)
    options.view_as(SetupOptions).save_main_session = True
    p = beam.Pipeline(options=options)
    build_dataflow_pipeline(p, input_subscription, output_table)
    result = p.run()
    job_id = getattr(result, "job_id", lambda: "unknown")()
    print(f"Dataflow job submitted. Job ID: {job_id}", flush=True)
    print(
        f"Monitor: https://console.cloud.google.com/dataflow/jobs/{region}/{job_id}"
        f"?project={project}",
        flush=True,
    )
    print(
        f"Drain: gcloud dataflow jobs drain {job_id} --region={region} --project={project}",
        flush=True,
    )
    if max_records is not None:
        print(
            f"Advisory: pre-publish {max_records} messages to {input_subscription} "
            "before this job reaches steady state, then drain within the timeout window.",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Beam MarketEvent pipeline.\n"
            "DirectRunner (default): local JSONL proof.\n"
            "DataflowRunner: bounded GCP proof via Pub/Sub → BigQuery. "
            "Requires --project, --region, --service-account-email, "
            "--staging-location, --temp-location, --input-subscription, --output-table."
        )
    )
    parser.add_argument(
        "--runner",
        default="DirectRunner",
        help="Beam runner: 'DirectRunner' (default) or 'DataflowRunner'.",
    )
    # DirectRunner args
    parser.add_argument("--input-jsonl", help="Input JSONL file path (DirectRunner)")
    parser.add_argument("--output-jsonl", help="Valid output JSONL path (DirectRunner)")
    parser.add_argument("--dead-letter-jsonl", help="Dead-letter JSONL path (DirectRunner)")
    # DataflowRunner args
    parser.add_argument("--project", help="GCP project ID (DataflowRunner)")
    parser.add_argument(
        "--region", default="europe-west1", help="GCP region (DataflowRunner)"
    )
    parser.add_argument(
        "--service-account-email",
        help="Dataflow SA email (DataflowRunner)",
    )
    parser.add_argument("--staging-location", help="GCS staging URI (DataflowRunner)")
    parser.add_argument("--temp-location", help="GCS temp URI (DataflowRunner)")
    parser.add_argument(
        "--input-subscription",
        help="Pub/Sub subscription path (DataflowRunner)",
    )
    parser.add_argument(
        "--output-table",
        help="BigQuery table as project:dataset.table (DataflowRunner)",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help=(
            "Advisory: number of messages to pre-publish to the proof subscription "
            "before launching. The job must be drained by the operator within "
            "--timeout-seconds. (DataflowRunner)"
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help=(
            "Advisory operator timeout in seconds. Drain the job before this deadline. "
            "Default: 600 (10 minutes). (DataflowRunner)"
        ),
    )
    args = parser.parse_args()

    if args.runner == "DirectRunner":
        for flag, val in [
            ("--input-jsonl", args.input_jsonl),
            ("--output-jsonl", args.output_jsonl),
            ("--dead-letter-jsonl", args.dead_letter_jsonl),
        ]:
            if not val:
                print(f"ERROR: {flag} is required for DirectRunner.", file=sys.stderr)
                sys.exit(1)
        if not os.path.exists(args.input_jsonl):
            print(f"ERROR: Input file not found: {args.input_jsonl}", file=sys.stderr)
            sys.exit(1)
        try:
            run(
                input_path=args.input_jsonl,
                output_path=args.output_jsonl,
                dead_letter_path=args.dead_letter_jsonl,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

    elif args.runner == "DataflowRunner":
        try:
            run_dataflow(
                project=args.project or "",
                region=args.region or "",
                service_account_email=args.service_account_email or "",
                staging_location=args.staging_location or "",
                temp_location=args.temp_location or "",
                input_subscription=args.input_subscription or "",
                output_table=args.output_table or "",
                max_records=args.max_records,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

    else:
        print(
            f"ERROR: Runner {args.runner!r} is not supported. "
            "Use 'DirectRunner' or 'DataflowRunner'.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
