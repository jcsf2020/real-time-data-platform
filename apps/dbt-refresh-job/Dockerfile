FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.5.31 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY apps ./apps
COPY packages ./packages
COPY scripts ./scripts
COPY dbt ./dbt

RUN uv sync --package rtdp-dbt-refresh-job --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV DBT_PROJECT_DIR=/app/dbt
ENV DBT_PROFILES_DIR=/tmp/rtdp-dbt-profiles

CMD ["rtdp-dbt-refresh-job"]
