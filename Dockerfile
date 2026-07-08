FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libsqlite3-dev \
    libpq-dev \
    postgresql-client \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY carteira_clean_web/ ./carteira_clean_web/
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY scripts/generate_build_info.py ./scripts/generate_build_info.py

RUN mkdir -p /app/carteira_clean_web/logs

# Captura o commit git rodando nesta imagem (usado por GET /api/status/deploy).
# O .git é copiado só para esta etapa e removido em seguida — não fica na imagem final.
COPY .git/ ./.git/
RUN python3 scripts/generate_build_info.py && rm -rf .git

CMD ["python3", "-m", "uvicorn", "carteira_clean_web.backend.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"]
