import os
from typing import Any

import psycopg
from fastapi import FastAPI


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


@app.get("/health")
def health() -> dict[str, str]:
    fetch_all("SELECT 1 AS ok")
    return {
        "status": "ok",
        "service": "rtdp-api",
        "database": "reachable",
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
