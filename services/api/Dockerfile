FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

ARG BUILD_CONTEXT=.
COPY ${BUILD_CONTEXT} .
RUN uv pip install --system --no-cache -e ".[dev]"

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD []
