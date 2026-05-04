"""Cloud Run-compatible HTTP runtime for the Pub/Sub worker."""

import base64
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import DATABASE_URL, process_message


def extract_pubsub_data(envelope: dict) -> bytes:
    """Extract and base64-decode `message.data` from a Pub/Sub push envelope.

    Raises ValueError on a missing/malformed envelope or invalid base64.
    """
    message = envelope.get("message")
    if not isinstance(message, dict):
        raise ValueError("envelope missing 'message' object")
    data_b64 = message.get("data")
    if data_b64 is None:
        raise ValueError("message missing 'data' field")
    try:
        return base64.b64decode(data_b64, validate=True)
    except Exception as exc:
        raise ValueError(f"invalid base64 in message.data: {exc}") from exc


def create_app() -> FastAPI:
    database_url = DATABASE_URL
    app = FastAPI(title="rtdp-pubsub-worker-http")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/pubsub/push")
    async def pubsub_push(request: Request) -> JSONResponse:
        try:
            envelope = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"detail": "invalid JSON body"})
        try:
            data = extract_pubsub_data(envelope)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"detail": str(exc)})
        result = process_message(data, database_url)
        if result["status"] != "ok":
            return JSONResponse(status_code=500, content=result)
        return JSONResponse(status_code=200, content=result)

    return app


def main() -> None:
    app = create_app()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host=host, port=port)
