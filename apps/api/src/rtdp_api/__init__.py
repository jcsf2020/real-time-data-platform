import os
from typing import Any

import psycopg
from fastapi import FastAPI, Response


SERVICE_NAME = os.getenv("SERVICE_NAME", "rtdp-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rtdp:rtdp@localhost:15432/realtime_platform",
)

app = FastAPI(title="Real-Time Data Platform API")


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, params)
            return list(cur.fetchall())


def format_prometheus_metrics(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# HELP rtdp_pipeline_metric_value Latest observed pipeline metric value.",
        "# TYPE rtdp_pipeline_metric_value gauge",
    ]

    for row in rows:
        metric_name = str(row["metric_name"]).replace("\\", "\\\\").replace('"', '\\"')
        metric_value = float(row["metric_value"])
        lines.append(
            f'rtdp_pipeline_metric_value{{metric_name="{metric_name}"}} {metric_value}'
        )

    return "\n".join(lines) + "\n"


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
    }


@app.get("/readiness")
def readiness() -> dict[str, str]:
    fetch_all("SELECT 1 AS ok")
    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "database": "reachable",
    }


@app.get("/version")
def version() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "environment": ENVIRONMENT,
    }


@app.get("/events")
def events(limit: int = 20) -> list[dict[str, Any]]:
    safe_limit = min(max(limit, 1), 100)

    return fetch_all(
        """
        SELECT
            event_id,
            symbol,
            event_type,
            price::float AS price,
            quantity::float AS quantity,
            event_timestamp,
            ingested_at,
            source_topic
        FROM bronze.market_events
        ORDER BY ingested_at DESC
        LIMIT %s;
        """,
        (safe_limit,),
    )


@app.get("/metrics")
def metrics(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = min(max(limit, 1), 200)

    return fetch_all(
        """
        SELECT
            metric_name,
            metric_value::float AS metric_value,
            measured_at
        FROM observability.pipeline_metrics
        ORDER BY measured_at DESC
        LIMIT %s;
        """,
        (safe_limit,),
    )


@app.get("/metrics-prometheus")
def metrics_prometheus() -> Response:
    rows = fetch_all(
        """
        SELECT DISTINCT ON (metric_name)
            metric_name,
            metric_value::float AS metric_value,
            measured_at
        FROM observability.pipeline_metrics
        ORDER BY metric_name, measured_at DESC;
        """
    )

    return Response(
        content=format_prometheus_metrics(rows),
        media_type="text/plain; version=0.0.4",
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "rtdp_api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
