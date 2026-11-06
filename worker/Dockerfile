FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build context is the repo root.
COPY shared /app/shared
COPY worker /app/worker
RUN pip install /app/shared /app/worker

ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

CMD ["python", "-m", "ledgerly_worker.main"]
