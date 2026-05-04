FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.5.31 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY apps ./apps
COPY packages ./packages

RUN uv sync --package rtdp-pubsub-worker --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

CMD ["rtdp-pubsub-worker-http"]
