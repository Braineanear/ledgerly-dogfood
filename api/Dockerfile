FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build context is the repo root. shared/ stays on disk because it holds
# alembic.ini and the migration scripts that the migrate service runs.
COPY shared /app/shared
COPY api /app/api
RUN pip install /app/shared /app/api

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "ledgerly_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
