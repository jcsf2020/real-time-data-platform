import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query, Response
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


SERVICE_NAME = os.getenv("SERVICE_NAME", "rtdp-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rtdp:rtdp@localhost:15432/realtime_platform",
)

DB_POOL = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=0,
    max_size=int(os.getenv("DATABASE_POOL_MAX_SIZE", "5")),
    open=False,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    DB_POOL.open(wait=False)
    yield
    DB_POOL.close()


app = FastAPI(title="Real-Time Data Platform API", lifespan=lifespan)


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with DB_POOL.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)  # type: ignore[arg-type]
            return list(cur.fetchall())


def format_prometheus_metrics(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# HELP rtdp_pipeline_metric_value Latest observed pipeline metric value.",
        "# TYPE rtdp_pipeline_metric_value gauge",
    ]

    for row in rows:
        metric_name = str(row["metric_name"]).replace("\\", "\\\\").replace('"', '\\"')
        metric_value = float(row["metric_value"])
        lines.append(f'rtdp_pipeline_metric_value{{metric_name="{metric_name}"}} {metric_value}')

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
def events(
    limit: int = 20,
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
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
            ORDER BY ingested_at DESC, event_id DESC
            LIMIT %s
            OFFSET %s;
        """,
        (safe_limit, offset),
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


@app.get("/aggregates/minute")
def minute_aggregates(limit: int = 20) -> list[dict[str, Any]]:
    safe_limit = min(max(limit, 1), 200)

    return fetch_all(
        """
            SELECT
                symbol,
                window_start,
                event_count,
                avg_price::float AS avg_price,
                total_quantity::float AS total_quantity,
                first_event_timestamp,
                last_event_timestamp,
                updated_at
            FROM silver.market_event_minute_aggregates
            ORDER BY window_start DESC, symbol
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
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
