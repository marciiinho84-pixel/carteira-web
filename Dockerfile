FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libsqlite3-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY carteira_clean_web/ ./carteira_clean_web/
COPY alembic.ini .
COPY alembic/ ./alembic/

RUN mkdir -p /app/carteira_clean_web/logs

CMD ["python3", "-m", "uvicorn", "carteira_clean_web.backend.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
