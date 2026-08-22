FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app \
    FASTF1_CACHE=/app/cache/fastf1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/requirements-api.txt /app/deploy/requirements-api.txt
RUN pip install --no-cache-dir -r /app/deploy/requirements-api.txt

COPY backend /app/backend
COPY src /app/src
COPY data/tracks /app/data/tracks
COPY data/compounds /app/data/compounds
COPY models/circuit_deg_slopes.json /app/models/circuit_deg_slopes.json

RUN mkdir -p /app/cache/fastf1

EXPOSE 8080
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
