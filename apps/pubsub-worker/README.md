# rtdp-pubsub-worker

GCP Pub/Sub worker: decode, validate, and persist `MarketEvent` messages into `bronze.market_events`.

## Packages

| Module | Purpose |
|---|---|
| `rtdp_pubsub_worker` | Core logic: decode → validate → insert (idempotent) |
| `rtdp_pubsub_worker.http_app` | Cloud Run-compatible HTTP runtime |

## HTTP runtime

The HTTP runtime exposes two endpoints:

### `GET /health`

Liveness probe. Returns `{"status": "ok"}` with HTTP 200.

### `POST /pubsub/push`

Receives a Pub/Sub push subscription envelope:

```json
{
  "message": {
    "data": "<base64-encoded MarketEvent JSON bytes>",
    "messageId": "...",
    "publishTime": "..."
  },
  "subscription": "projects/<project>/subscriptions/<sub>"
}
```

**Behaviour:**

- Decodes the base64 `message.data` field.
- Passes the raw bytes to `process_message`, which validates and inserts to `bronze.market_events` with `ON CONFLICT DO NOTHING` idempotency.
- Returns HTTP 200 on success (Pub/Sub treats any 2xx as acknowledgement).
- Returns HTTP 400 for a malformed envelope or invalid base64 (message is dead-lettered rather than retried).
- Returns HTTP 500 on worker/DB failure (Pub/Sub retries the message).

## Running locally

```bash
# stdin mode (existing CLI)
echo '{"schema_version":"1.0","event_id":"x","symbol":"BTCUSDT","event_type":"trade","price":"100","quantity":"1","event_timestamp":"2024-01-01T00:00:00+00:00"}' \
  | uv run rtdp-pubsub-worker

# HTTP server mode
uv run rtdp-pubsub-worker-http
# Listens on 0.0.0.0:8080 by default.
# Override with HOST and PORT env vars.
```

## Implementation status

| Feature | Status |
|---|---|
| Core decode/validate/insert logic | Implemented and tested |
| HTTP runtime (`/health`, `POST /pubsub/push`) | Implemented and tested locally |
| Cloud Run deployment | **Not yet deployed** |
| Pub/Sub push subscription wired to Cloud Run | **Not yet configured** |
| Cloud SQL | Stopped (cost control); manual validation documented in `docs/gcp-worker-cloud-validation.md` |

## Tests

```bash
uv run pytest tests/test_pubsub_worker.py tests/test_pubsub_worker_http.py -v
```

All tests run without a real database or GCP connection.
