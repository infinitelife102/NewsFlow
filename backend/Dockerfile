# NewsFlow Backend - Production Dockerfile
# Use for Railway/Render Docker deploy or local production run.

FROM python:3.11-slim

WORKDIR /app

# Install system deps for native packages (e.g. psycopg2, sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# PORT is provided by Railway/Render at runtime
ENV HOST=0.0.0.0
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
